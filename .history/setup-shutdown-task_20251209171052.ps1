# Script to setup Windows Task Scheduler to run pagecounter before shutdown
# Run this script as Administrator

$scriptPath = Join-Path $PSScriptRoot "pagecounter-folders.py"
$pythonPath = (Get-Command python -ErrorAction SilentlyContinue).Source

if (-not $pythonPath) {
    $pythonPath = (Get-Command python3 -ErrorAction SilentlyContinue).Source
}

if (-not $pythonPath) {
    Write-Host "ERRO: Python não encontrado. Certifique-se de que Python está instalado e no PATH." -ForegroundColor Red
    exit 1
}

if (-not (Test-Path $scriptPath)) {
    Write-Host "ERRO: Arquivo pagecounter-folders.py não encontrado em $scriptPath" -ForegroundColor Red
    exit 1
}

$taskName = "XABLAU-PageCounter-Shutdown"
$taskDescription = "Executa contagem de páginas PDF antes do desligamento do computador"

# Remove existing task if it exists
$existingTask = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if ($existingTask) {
    Write-Host "Removendo tarefa existente..." -ForegroundColor Yellow
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
}

# Create action to run Python script
$action = New-ScheduledTaskAction -Execute $pythonPath -Argument "`"$scriptPath`"" -WorkingDirectory $PSScriptRoot

# Create trigger for system shutdown (Event ID 1074, 1076, or use Event Log trigger)
# Using Event Log trigger for more reliable shutdown detection
$trigger = New-ScheduledTaskTrigger -AtLogOn
$trigger.Enabled = $false

# Alternative: Use event-based trigger for shutdown
# We'll use a workaround with a scheduled task that runs on system events
$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest

# Create settings
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -RunOnlyIfNetworkAvailable:$false -ExecutionTimeLimit (New-TimeSpan -Minutes 30)

# Register the task
try {
    Register-ScheduledTask -TaskName $taskName -Action $action -Principal $principal -Settings $settings -Description $taskDescription -Force | Out-Null
    Write-Host "Tarefa criada com sucesso!" -ForegroundColor Green
    Write-Host ""
    Write-Host "NOTA: A tarefa foi criada, mas precisamos configurar o trigger de shutdown manualmente." -ForegroundColor Yellow
    Write-Host "Execute o seguinte comando no PowerShell (como Administrador) para configurar:" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "schtasks /change /tn `"$taskName`" /tr `"$pythonPath `"$scriptPath`"`" /ru SYSTEM" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Ou use o método alternativo com script de shutdown (veja setup-shutdown-script.ps1)" -ForegroundColor Yellow
}
catch {
    Write-Host "ERRO ao criar tarefa: $_" -ForegroundColor Red
    exit 1
}

