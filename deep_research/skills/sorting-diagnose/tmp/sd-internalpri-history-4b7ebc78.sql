SELECT
  eventtime,
  internalpriority
FROM rpt6.lot_history
WHERE 1=1
  AND lotname = 'LOT0003'
  AND eventtime >= '2025-05-14 09:00:00'
  AND eventtime <= '2025-05-14 09:30:00'
ORDER BY eventtime
