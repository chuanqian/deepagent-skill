SELECT DISTINCT eqpid
FROM rtd6.fabrtdlog
WHERE 1=1
  AND eqpid IN ('EQP01')
  AND INSTR(rtdinfo, 'KEYLOT') > 0
  AND txntime > '2025-05-14 09:00:00'
  AND txntime <= '2025-05-14 09:30:00'
ORDER BY eqpid
