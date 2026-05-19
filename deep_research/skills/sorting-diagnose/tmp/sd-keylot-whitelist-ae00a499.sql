SELECT DISTINCT lotname
FROM MFGCIM_SYN.tb_quota_apply_info
WHERE 1=1
  AND status = 'COMFIRM'
  AND KEYLOT = 1
