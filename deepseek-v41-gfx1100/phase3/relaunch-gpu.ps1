# Stop the DeepSeek server and start it again with Gate G config 2 as-is (AtomicChat pack, 6 experts, DSpark on,
# 36 GB RAM cache, experts on the card, matrix cores on). Used by run_task.py's NaN recovery (model C-gpu) and to
# start the server before a C-gpu run. Returns when the server answers.
$env:STRATA_DATA_DIR = 'C:\Strata'
$env:STRATA_COMPONENTS_DIR = 'C:\Strata\components'
$env:HIP_VISIBLE_DEVICES = '0'
$env:STRATA_DSV41_EXE = 'E:\strata-dsv41\engine-dsv41\0.1.58-windows-x86_64-hip-gfx1100-self\strata-dsv41.exe'
$env:DS4_CPU_SMT = '1'
$env:DS4_AHEAD_EXTRA = '2'
Remove-Item Env:STRATA_DS4_NO_TC, Env:STRATA_DENSE_PFGEMM -ErrorAction SilentlyContinue
strata launch --stop 2>&1 | Out-Null
strata launch --model-path 'E:\strata-dsv41\models\atomic-iq1_m' --model ist-das-1.75bpw --family deepseek41 `
  --context 65532 --vision off --full-quality --tune skip --access local --port 8091 --set dspark=on `
  --set ssd-cache=36 --yes --no-tui *>> 'E:\strata-dsv41\gateH\relaunch-gpu.log'
exit $LASTEXITCODE
