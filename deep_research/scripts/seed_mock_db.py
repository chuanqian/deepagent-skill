"""Seed the local MySQL with the three databases / tables the sorting-diagnose
skill queries, plus a small set of mock rows covering KEYLOT / INTERNALPRI /
PRIOR_1 scenarios.

Re-running is safe: databases use CREATE IF NOT EXISTS, tables are dropped
and recreated each run so the demo always sees a known data set.

Connects via the same credentials as the skill scripts (HOST=localhost,
USER=root, PASSWORD=123456, PORT=3306). Override via env: DB_HOST / DB_PORT
/ DB_USER / DB_PASSWORD.

Run:
    python scripts/seed_mock_db.py
"""

from __future__ import annotations

import os

import pymysql


DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_PORT = int(os.environ.get("DB_PORT", "3306"))
DB_USER = os.environ.get("DB_USER", "root")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "123456")


# --- Schema ------------------------------------------------------------------

DDL = [
    "CREATE DATABASE IF NOT EXISTS rtd6 CHARACTER SET utf8mb4",
    "CREATE DATABASE IF NOT EXISTS rpt6 CHARACTER SET utf8mb4",
    "CREATE DATABASE IF NOT EXISTS `MFGCIM_SYN` CHARACTER SET utf8mb4",

    "DROP TABLE IF EXISTS rtd6.fabrtdlog",
    """
    CREATE TABLE rtd6.fabrtdlog (
        eqpid    VARCHAR(64)  NOT NULL,
        lotid    VARCHAR(64)  NOT NULL,
        txntime  DATETIME     NOT NULL,
        stepseq  VARCHAR(64),
        rtdseq   INT,
        rtdinfo  TEXT,
        KEY idx_lot_txn (lotid, txntime),
        KEY idx_eqp_txn (eqpid, txntime)
    ) CHARACTER SET utf8mb4
    """,

    "DROP TABLE IF EXISTS rpt6.lot_history",
    """
    CREATE TABLE rpt6.lot_history (
        lotname           VARCHAR(64) NOT NULL,
        eventtime         DATETIME    NOT NULL,
        priority          INT,
        internalpriority  INT,
        KEY idx_lot_event (lotname, eventtime)
    ) CHARACTER SET utf8mb4
    """,

    "DROP TABLE IF EXISTS `MFGCIM_SYN`.tb_quota_apply_info",
    """
    CREATE TABLE `MFGCIM_SYN`.tb_quota_apply_info (
        lotname  VARCHAR(64) NOT NULL,
        status   VARCHAR(32),
        KEYLOT   INT,
        KEY idx_lot (lotname)
    ) CHARACTER SET utf8mb4
    """,
]


# --- Mock data ---------------------------------------------------------------
#
# Time window for the demo: 2025-05-14 09:00 ~ 09:30, stepseq 1000.
#
# Scenarios:
#   LOT0001 (KEYLOT case, "为什么 KEYLOT 没生效")
#     - dispatched on EQP01 twice
#     - rtdinfo contains "KEYLOT=0" (Sorting didn't fire)
#     - NOT in MFGCIM_SYN whitelist → theoretical KEYLOT = 0 → matches actual
#
#   LOT0002 (KEYLOT positive case, plus PRIOR_1 demo)
#     - dispatched on EQP02
#     - rtdinfo "KEYLOT=1;InternalPri=5;PRIOR_1=-105"
#     - on whitelist with KEYLOT=1
#     - lot_history: priority=1, internalpriority=5 → PRIOR_1 = -105 (matches)
#
#   LOT0003 (INTERNALPRI sentinel case)
#     - dispatched on EQP03 (different stepseq=2000)
#     - rtdinfo "InternalPri=0" (sentinel = not effective)
#     - lot_history: internalpriority=0 → theoretical "not effective" → matches

FABRTDLOG_ROWS = [
    # LOT0001 — KEYLOT did not fire
    ("EQP01", "LOT0001", "2025-05-14 09:10:00", "1000", 1,
     "KEYLOT=0;InternalPri=2;PRIOR_1=-9999"),
    ("EQP01", "LOT0001", "2025-05-14 09:20:00", "1000", 2,
     "KEYLOT=0;InternalPri=2;PRIOR_1=-9999"),

    # LOT0002 — KEYLOT fired, PRIOR_1 = -105
    ("EQP02", "LOT0002", "2025-05-14 09:15:00", "1000", 1,
     "KEYLOT=1;InternalPri=5;PRIOR_1=-105"),

    # LOT0003 — InternalPri sentinel
    ("EQP03", "LOT0003", "2025-05-14 09:25:00", "2000", 1,
     "InternalPri=0"),
]

LOT_HISTORY_ROWS = [
    # LOT0001: priority != 1, so PRIOR_1 theoretical = -9999
    ("LOT0001", "2025-05-14 09:05:00", 2, 2),

    # LOT0002: priority=1, internalpriority=5 → PRIOR_1 = -1*concat("1","05") = -105
    ("LOT0002", "2025-05-14 09:05:00", 1, 5),

    # LOT0003: InternalPri sentinel 0
    ("LOT0003", "2025-05-14 09:05:00", 2, 0),
]

QUOTA_ROWS = [
    # LOT0002 on the whitelist (status spelled COMFIRM, matching production)
    ("LOT0002", "COMFIRM", 1),
    # A pending row that should NOT count (wrong status)
    ("LOT0004", "PENDING",  1),
    # A row with KEYLOT=0 that should NOT count
    ("LOT0005", "COMFIRM",  0),
]


def main() -> None:
    conn = pymysql.connect(
        host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASSWORD,
        charset="utf8mb4", autocommit=False,
    )
    try:
        with conn.cursor() as cur:
            for stmt in DDL:
                cur.execute(stmt)

            cur.executemany(
                "INSERT INTO rtd6.fabrtdlog "
                "(eqpid, lotid, txntime, stepseq, rtdseq, rtdinfo) "
                "VALUES (%s, %s, %s, %s, %s, %s)",
                FABRTDLOG_ROWS,
            )
            cur.executemany(
                "INSERT INTO rpt6.lot_history "
                "(lotname, eventtime, priority, internalpriority) "
                "VALUES (%s, %s, %s, %s)",
                LOT_HISTORY_ROWS,
            )
            cur.executemany(
                "INSERT INTO `MFGCIM_SYN`.tb_quota_apply_info "
                "(lotname, status, KEYLOT) VALUES (%s, %s, %s)",
                QUOTA_ROWS,
            )
        conn.commit()
    finally:
        conn.close()

    print(
        f"Seeded: rtd6.fabrtdlog={len(FABRTDLOG_ROWS)}, "
        f"rpt6.lot_history={len(LOT_HISTORY_ROWS)}, "
        f"MFGCIM_SYN.tb_quota_apply_info={len(QUOTA_ROWS)}"
    )


if __name__ == "__main__":
    main()
