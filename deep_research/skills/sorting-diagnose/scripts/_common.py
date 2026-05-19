"""Shared helpers for the sorting-diagnose query scripts.

All scripts in this directory follow the same contract:
- They build a SQL string from typed CLI args (no string templating by the caller)
- They either print that SQL (--print-sql) for inspection, or write it to
  tmp/sd-<tag>-<uuid>.sql under the skill root and exec ./run-query.sh
- On stdout they emit a single JSON object with the same shape as query.py:
    success: {"ok": true, "rowCount": N, "truncated": bool, "rows": [...]}
    failure: {"ok": false, "error": "...", "errorType": "..."}

Why this layer exists: the skill used to ask the LLM to substitute placeholders
into SQL and write the file by hand. Quote escaping, case sensitivity of the
rtdinfo key, and the eqpidList ('A','B') formatting were all easy to get wrong.
The scripts centralize those mechanics so every invocation is identical.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import uuid
from pathlib import Path

TIME_RE = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$")

SKILL_ROOT = Path(__file__).resolve().parent.parent
REGISTRY_PATH = SKILL_ROOT / "rules" / "_registry.md"


def load_registry() -> dict[str, str]:
    """Parse rules/_registry.md → {SORTING_UPPER: rtdinfo_key}.

    The mapping table looks like:
        | SORTING | rtdinfo key | 规则文件 | ...
        |---|---|---|...
        | KEYLOT | `KEYLOT` | ./keylot.md | ...
        | INTERNALPRI | `InternalPri` | ./internalpri.md | ...

    We scan for the header row (first column 'SORTING', second 'rtdinfo key'),
    then collect data rows until the table ends (first non-pipe line).
    Cell values are stripped of surrounding backticks and whitespace. We
    deliberately break out at the first non-pipe line so trailing HTML
    comments showing example rows do not get picked up.
    """
    out: dict[str, str] = {}
    in_table = False
    for line in REGISTRY_PATH.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not in_table:
            if (
                stripped.startswith("|")
                and "SORTING" in stripped
                and "rtdinfo key" in stripped
            ):
                in_table = True
            continue
        # In-table: any non-pipe line ends the table for good.
        if not stripped.startswith("|"):
            break
        # Separator row e.g. |---|---|...
        if stripped.startswith("|---") or stripped.startswith("| ---"):
            continue
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        if len(cells) < 2:
            continue
        sorting = cells[0].strip("` ").strip()
        rtdinfo_key = cells[1].strip("` ").strip()
        if not sorting or not rtdinfo_key:
            continue
        out[sorting.upper()] = rtdinfo_key
    return out


def resolve_sorting_key(sorting: str) -> str:
    """Map a user-facing SORTING name (case-insensitive) to its rtdinfo key.

    Raises ValueError if the Sorting is not registered — the caller should
    turn that into the standard error JSON via emit_error. We do not silently
    fall back to uppercasing the name: the whole point of this layer is to
    catch 'INTERNALPRI != InternalPri' before it produces a silent zero-result.
    """
    registry = load_registry()
    key = registry.get(sorting.upper())
    if key is None:
        known = ", ".join(sorted(registry)) or "(none)"
        raise ValueError(
            f"Sorting {sorting!r} is not registered in rules/_registry.md. "
            f"Known sortings: {known}. Add a row there (and a rule file) "
            "before diagnosing this Sorting."
        )
    return key


SCRIPTS_DIR = Path(__file__).resolve().parent
QUERY_PY = SCRIPTS_DIR / "query.py"


def escape_sql_string(value: str) -> str:
    """MySQL single-quote escape: ' -> ''.

    The SQLs here all use single-quoted literals, so this is the only escape
    we need. We deliberately do NOT do shell escaping — the SQL goes via a
    --sql-file, never a command line.
    """
    if "\x00" in value:
        raise ValueError("SQL string values must not contain NUL bytes")
    return value.replace("'", "''")


def validate_time(value: str, *, field: str) -> str:
    """Require 'YYYY-MM-DD HH:MM:SS'.

    Cheap guardrail to keep the SQLs' date literals in a single, predictable
    format. A wrong format here would otherwise silently produce an empty
    result.
    """
    if not TIME_RE.match(value):
        raise ValueError(
            f"{field} must be 'YYYY-MM-DD HH:MM:SS' (24-hour), got {value!r}"
        )
    return value


def format_eqpid_list(eqpids: list[str]) -> str:
    """Turn ['A', 'B'] into "'A','B'" for a SQL IN-list.

    Empty list is rejected — an IN () is illegal SQL, and an empty list
    almost always means the caller forgot to pass --eqpid; better to fail
    fast than to silently return no rows.
    """
    if not eqpids:
        raise ValueError("eqpid list must not be empty")
    return ",".join("'" + escape_sql_string(e) + "'" for e in eqpids)


def emit_error(message: str, *, error_type: str = "ArgumentError") -> int:
    """Print a query.py-shaped failure JSON and return exit code 1.

    Using the same shape means the model only learns one error-handling
    pattern regardless of where the error came from.
    """
    json.dump(
        {"ok": False, "error": message, "errorType": error_type},
        sys.stdout,
        ensure_ascii=False,
    )
    sys.stdout.write("\n")
    return 1


def write_sql_and_run(
    sql: str,
    *,
    tag: str,
    max_rows: int | None = None,
    print_sql: bool = False,
) -> int:
    """Either print the SQL or persist+execute it via query.py.

    The SQL file lives at <skill_root>/tmp/sd-<tag>-<uuid>.sql so the whole
    skill is self-contained. We keep the file around after execution — it's
    a useful audit trail when a later step gives surprising results.
    """
    if print_sql:
        sys.stdout.write(sql.rstrip() + "\n")
        return 0

    tmp_dir = SKILL_ROOT / "tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    sql_rel = Path("tmp") / f"sd-{tag}-{uuid.uuid4().hex[:8]}.sql"
    (SKILL_ROOT / sql_rel).write_text(sql, encoding="utf-8")

    cmd = [sys.executable, str(QUERY_PY), "--sql-file", str(sql_rel)]
    if max_rows is not None:
        cmd += ["--max-rows", str(max_rows)]

    # cwd=SKILL_ROOT so the relative --sql-file value (e.g. "tmp/sd-*.sql")
    # resolves against the skill root.
    proc = subprocess.run(cmd, cwd=SKILL_ROOT, check=False)
    return proc.returncode
