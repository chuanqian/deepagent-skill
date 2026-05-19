#!/usr/bin/env python3
"""Step 2: find the EQPs that ran dispatching for a lot in a time window.

Queries rtd6.fabrtdlog for DISTINCT eqpid where the lot had a non-null rtdseq
within [starttime, endtime]. If --stepseq is supplied, also restrict to that
step. This is the script that backs workflow.md Step 2.

Empty result is a signal to abort the whole diagnosis (per workflow.md).
Don't widen the time window and retry — the time window is set once in Step 1.

Usage:
    python scripts/find_eqps.py \\
        --lotid LOT0001 \\
        --start '2025-05-14 09:00:00' --end '2025-05-14 09:30:00'
    python scripts/find_eqps.py ... --stepseq 1000
    python scripts/find_eqps.py ... --print-sql      # show SQL, do not execute
"""

from __future__ import annotations

import argparse
import sys

from _common import (
    emit_error,
    escape_sql_string,
    validate_time,
    write_sql_and_run,
)


def build_sql(lotid: str, starttime: str, endtime: str, stepseq: str | None) -> str:
    lotid_s = escape_sql_string(lotid)
    starttime_s = escape_sql_string(starttime)
    endtime_s = escape_sql_string(endtime)
    stepseq_clause = (
        f"  AND stepseq = '{escape_sql_string(stepseq)}'\n" if stepseq else ""
    )
    return (
        "SELECT DISTINCT eqpid\n"
        "FROM rtd6.fabrtdlog\n"
        "WHERE 1=1\n"
        f"  AND lotid = '{lotid_s}'\n"
        f"{stepseq_clause}"
        "  AND rtdseq IS NOT NULL\n"
        f"  AND txntime >= '{starttime_s}'\n"
        f"  AND txntime <= '{endtime_s}'\n"
        "ORDER BY eqpid\n"
    )


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--lotid", required=True)
    p.add_argument("--start", required=True, help="'YYYY-MM-DD HH:MM:SS' (24h)")
    p.add_argument("--end", required=True, help="'YYYY-MM-DD HH:MM:SS' (24h)")
    p.add_argument("--stepseq", help="optional: restrict to a specific stepseq")
    p.add_argument("--max-rows", type=int, default=None)
    p.add_argument("--print-sql", action="store_true")
    args = p.parse_args()

    try:
        validate_time(args.start, field="--start")
        validate_time(args.end, field="--end")
        sql = build_sql(args.lotid, args.start, args.end, args.stepseq)
    except ValueError as exc:
        return emit_error(str(exc))

    return write_sql_and_run(
        sql, tag="step2-find-eqps", max_rows=args.max_rows, print_sql=args.print_sql
    )


if __name__ == "__main__":
    sys.exit(main())
