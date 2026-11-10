# Runs the pagoda prompt on Qwen 3.8 27B through opencode in this window, so the work can be watched.
$host.UI.RawUI.WindowTitle = 'Pagoda test - Qwen 3.8 27B (opencode)'
Set-Location C:\Users\user\strata-tests\oc-27b
$prompt = Get-Content C:\Users\user\strata-tests\pagoda-local-input.txt -Raw
[DateTimeOffset]::UtcNow.ToUnixTimeSeconds() | Out-File ..\oc-27b-t0.txt -Encoding ascii
Write-Host "Started $(Get-Date -Format HH:mm:ss). Model: Qwen 3.8 27B on llama.cpp, 160K context. Supervisor plugin on." -ForegroundColor Cyan
opencode run $prompt -m llamacpp/qwen3.8-27b --thinking
"exit $LASTEXITCODE" | Out-File ..\oc-27b-exit.txt -Encoding ascii
[DateTimeOffset]::UtcNow.ToUnixTimeSeconds() | Out-File ..\oc-27b-t1.txt -Encoding ascii
Write-Host "`nFinished $(Get-Date -Format HH:mm:ss). You can close this window." -ForegroundColor Cyan
Read-Host 'Press Enter to close'
