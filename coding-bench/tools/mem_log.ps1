# Log memory every ~1 s until killed: unix time, GPU dedicated/shared MB (sum over adapter instances of the Radeon),
# available system RAM MB, and the model server process's working set / private bytes in MB.
#   powershell -File mem_log.ps1 <csv> <process names comma separated, e.g. llama-server,strata>
param([string]$Csv, [string]$Procs = 'llama-server,strata')
$names = $Procs -split ','
if (-not (Test-Path $Csv)) { 'unix,gpu_dedicated_mb,gpu_shared_mb,ram_available_mb,server_ws_mb,server_private_mb' | Out-File $Csv -Encoding ascii }
$ctrs = '\GPU Adapter Memory(*)\Dedicated Usage', '\GPU Adapter Memory(*)\Shared Usage', '\Memory\Available MBytes'
while ($true) {
  try {
    $s = (Get-Counter $ctrs -ErrorAction Stop).CounterSamples
    $ded = ($s | Where-Object { $_.Path -match 'dedicated usage' } | Measure-Object CookedValue -Maximum).Maximum / 1MB
    $sh = ($s | Where-Object { $_.Path -match 'shared usage' } | Measure-Object CookedValue -Maximum).Maximum / 1MB
    $av = ($s | Where-Object { $_.Path -match 'available mbytes' }).CookedValue
    $p = Get-Process -Name $names -ErrorAction SilentlyContinue
    $ws = ($p | Measure-Object WorkingSet64 -Sum).Sum / 1MB
    $pv = ($p | Measure-Object PrivateMemorySize64 -Sum).Sum / 1MB
    $t = [DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds() / 1000.0
    '{0:F1},{1:F0},{2:F0},{3:F0},{4:F0},{5:F0}' -f $t, $ded, $sh, $av, $ws, $pv | Out-File $Csv -Append -Encoding ascii
  } catch { }
  Start-Sleep -Milliseconds 500
}
