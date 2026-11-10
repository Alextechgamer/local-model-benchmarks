# Start Model A (Qwen3.8-Flash-Next Coder IQ1_M on Strata 0.1.45, HIP) with the locked settings in configs\model-a.json.
# OpenAI-compatible API: http://127.0.0.1:8080/v1
# The locked file is not changed: a copy with its own engine-log path is written next to the logs and used.
# Leaves other programs alone. Stop it with:  taskkill /PID <printed pid> /T /F
param([int]$Port = 8080)
$root = Split-Path $PSScriptRoot -Parent
$stamp = Get-Date -Format yyyyMMdd-HHmmss
$cfg = Get-Content "$PSScriptRoot\model-a.json" -Raw | ConvertFrom-Json
$cfg.log = "$root\logs\server\model-a-$stamp.engine.log"
$run = "$root\logs\server\model-a-$stamp.config.json"
[IO.File]::WriteAllText($run, ($cfg | ConvertTo-Json -Depth 6), (New-Object Text.UTF8Encoding $false))
$py = 'C:\Users\user\Strata\.venv\Scripts\python.exe'
$server = Join-Path $cfg.cwd 'serve\server.py'
$out = "$root\logs\server\model-a-$stamp.log"
$proc = Start-Process $py -ArgumentList $server, '--engine', 'strata', '--config', $run, '--port', $Port `
  -WorkingDirectory $cfg.cwd -RedirectStandardOutput $out -RedirectStandardError "$out.err" -WindowStyle Hidden -PassThru
"model A started: pid $($proc.Id), log $out"
