# Start or stop the GPU board-power logger and the CPU RAPL logger for one model session.
#   .\power.ps1 start <name>   -> power\<name>-gpu.csv, power\<name>-cpu.csv, power\<name>-pids.txt
#   .\power.ps1 stop  <name>   -> stops only the two processes this script started (PIDs from the pids file)
# GPU: E:\strata-tests\gpu_power.py, sensor 73 = board power in W (idle ~75 W, full load ~310 W, measured 2026-10-19).
# CPU: typeperf "\Energy Meter(rapl_package0_pkg)\Power", value in mW, every 2 s (same counter the earlier runs logged).
param([ValidateSet('start','stop')][string]$Action, [string]$Name)
$dir = 'E:\strata-tests\coding-bench\power'
New-Item -ItemType Directory -Force $dir | Out-Null
$pids = "$dir\$Name-pids.txt"
if ($Action -eq 'start') {
  if (Test-Path $pids) { throw "power session $Name already exists ($pids)" }
  $g = Start-Process python -ArgumentList 'E:\strata-tests\gpu_power.py','log',"$dir\$Name-gpu.csv",'2' -WindowStyle Hidden -PassThru
  $c = Start-Process typeperf -ArgumentList '"\Energy Meter(rapl_package0_pkg)\Power"','-si','2','-f','CSV','-o',"$dir\$Name-cpu.csv",'-y' -WindowStyle Hidden -PassThru
  $m = Start-Process powershell -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-File','E:\strata-tests\coding-bench\tools\mem_log.ps1',"$dir\$Name-mem.csv" -WindowStyle Hidden -PassThru
  "$($g.Id) $($c.Id) $($m.Id)" | Out-File $pids -Encoding ascii
  "power logging started: gpu pid $($g.Id), cpu pid $($c.Id), mem pid $($m.Id)"
} else {
  if (-not (Test-Path $pids)) { throw "no power session $Name" }
  foreach ($p in (Get-Content $pids).Trim() -split '\s+') {
    $proc = Get-Process -Id $p -ErrorAction SilentlyContinue
    if ($proc -and $proc.ProcessName -match '^(python|typeperf|powershell)$') { Stop-Process -Id $p -Force; "stopped $p ($($proc.ProcessName))" }
  }
  Rename-Item $pids "$Name-pids.done.txt"
}
