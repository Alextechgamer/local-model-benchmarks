# Start Model B (Qwen3.8-27B IQ4_XS on llama.cpp b11748 Vulkan) with the locked settings from configs\model-b.json.
# OpenAI-compatible API: http://127.0.0.1:8090/v1   Log: logs\server\model-b-<time>.log
# Leaves other programs alone. Stop it with Stop-Process on the printed PID.
$cfg = Get-Content "$PSScriptRoot\model-b.json" -Raw | ConvertFrom-Json
$log = "$PSScriptRoot\..\logs\server\model-b-$(Get-Date -Format yyyyMMdd-HHmmss).log"
foreach ($p in $cfg.env.PSObject.Properties) { Set-Item "env:$($p.Name)" $p.Value }
$proc = Start-Process $cfg.exe -ArgumentList $cfg.args -RedirectStandardOutput $log -RedirectStandardError "$log.err" -WindowStyle Hidden -PassThru
"model B started: pid $($proc.Id), log $log"
