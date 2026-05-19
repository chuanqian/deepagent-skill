#!/usr/bin/env python3
"""KEYLOT rule: fetch the set of lots flagged as Key Lots.

Source: MFGCIM_SYN.tb_quota_apply_info. A lot is a Key Lot iff there is at
least one row with status='COMFIRM' (yes, that misspelling is the production
value — see rules/keylot.md §6) and KEYLOT=1.

This query has no per-invocation parameters; the full whitelist is fetched
once and the caller decides membership client-side. Increase --max-rows if
'truncated' comes back true.

Usage:
    python scripts/keylot_whitelist.py
    python scripts/keylot_whitelist.py --max-rows 100000
    python scripts/keylot_whitelist.py --print-sql
"""

from __future__ import annotations

import argparse
import sys

from _common import write_sql_and_run


SQL = (
    "SELECT DISTINCT lotname\n"
    "FROM MFGCIM_SYN.tb_quota_apply_info\n"
    "WHERE 1=1\n"
    "  AND status = 'COMFIRM'\n"
    "  AND KEYLOT = 1\n"
)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--max-rows", type=int, default=None)
    p.add_argument("--print-sql", action="store_true")
    args = p.parse_args()

    return write_sql_and_run(
        SQL,
        tag="keylot-whitelist",
        max_rows=args.max_rows,
        print_sql=args.print_sql,
    )


if __name__ == "__main__":
    sys.exit(main())
