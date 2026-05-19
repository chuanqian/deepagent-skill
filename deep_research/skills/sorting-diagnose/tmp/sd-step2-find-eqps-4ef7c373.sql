SELECT DISTINCT eqpid
FROM rtd6.fabrtdlog
WHERE 1=1
  AND lotid = 'LOT0001'
  AND rtdseq IS NOT NULL
  AND txntime >= '2025-05-14 09:00:00'
  AND txntime <= '2025-05-14 09:30:00'
ORDER BY eqpid
