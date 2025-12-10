# Simple method using Task Scheduler with event-based trigger
# This is the RECOMMENDED approach - more reliable
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

# Create action
$action = New-ScheduledTaskAction -Execute $pythonPath -Argument "`"$scriptPath`"" -WorkingDirectory $PSScriptRoot

# Create event-based trigger for shutdown
# Event ID 1074 = User initiated shutdown, 1076 = Unexpected shutdown
# We'll use XML trigger for more control
$xmlTrigger = @"
<QueryList>
  <Query Id="0" Path="System">
    <Select Path="System">
      *[System[Provider[@Name='USER32'] and (EventID=1074 or EventID=1076)]]
    </Select>
  </Query>
</QueryList>
"@

$trigger = New-ScheduledTaskSettingsSet
$triggerXml = @"
<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.4" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <Triggers>
    <EventTrigger>
      <Enabled>true</Enabled>
      <Subscription>&lt;QueryList&gt;&lt;Query Id="0" Path="System"&gt;&lt;Select Path="System"&gt;*[System[Provider[@Name='USER32'] and (EventID=1074 or EventID=1076)]]&lt;/Select&gt;&lt;/Query&gt;&lt;/QueryList&gt;</Subscription>
    </EventTrigger>
  </Triggers>
</Task>
"@

# Principal (run as SYSTEM)
$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest

# Settings - allow execution even if on battery, with timeout
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 30) `
    -MultipleInstances IgnoreNew

try {
    # Register task with XML trigger
    $task = New-ScheduledTask -Action $action -Principal $principal -Settings $settings -Description $taskDescription
    
    # We need to use schtasks.exe to set the event trigger properly
    $xmlFile = Join-Path $env:TEMP "xablau-shutdown-task.xml"
    
    # Create XML for the task
    $taskXml = @"
<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.4" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Description>$taskDescription</Description>
  </RegistrationInfo>
  <Triggers>
    <EventTrigger>
      <Enabled>true</Enabled>
      <Subscription>&lt;QueryList&gt;&lt;Query Id="0" Path="System"&gt;&lt;Select Path="System"&gt;*[System[Provider[@Name='USER32'] and (EventID=1074 or EventID=1076)]]&lt;/Select&gt;&lt;/Query&gt;&lt;/QueryList&gt;</Subscription>
    </EventTrigger>
  </Triggers>
  <Actions>
    <Exec>
      <Command>$pythonPath</Command>
      <Arguments>"$scriptPath"</Arguments>
      <WorkingDirectory>$PSScriptRoot</WorkingDirectory>
    </Exec>
  </Actions>
  <Principals>
    <Principal id="Author">
      <UserId>S-1-5-18</UserId>
      <RunLevel>Highest</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <AllowStartIfOnBatteries>true</AllowStartIfOnBatteries>
    <DontStopIfGoingOnBatteries>true</DontStopIfGoingOnBatteries>
    <StartWhenAvailable>true</StartWhenAvailable>
    <ExecutionTimeLimit>PT30M</ExecutionTimeLimit>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
  </Settings>
</Task>
"@
    
    $taskXml | Out-File -FilePath $xmlFile -Encoding Unicode -Force
    
    # Import task using schtasks
    $result = schtasks /Create /TN $taskName /XML $xmlFile /F 2>&1
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✓ Tarefa criada com sucesso!" -ForegroundColor Green
        Write-Host ""
        Write-Host "A tarefa '$taskName' será executada automaticamente antes do desligamento." -ForegroundColor Cyan
        Write-Host ""
        Write-Host "Para verificar a tarefa:" -ForegroundColor Yellow
        Write-Host "  schtasks /Query /TN `"$taskName`"" -ForegroundColor White
        Write-Host ""
        Write-Host "Para remover a tarefa:" -ForegroundColor Yellow
        Write-Host "  schtasks /Delete /TN `"$taskName`" /F" -ForegroundColor White
        
        # Cleanup temp file
        Remove-Item $xmlFile -ErrorAction SilentlyContinue
    } else {
        Write-Host "ERRO ao criar tarefa:" -ForegroundColor Red
        Write-Host $result
        exit 1
    }
    
} catch {
    Write-Host "ERRO ao criar tarefa: $_" -ForegroundColor Red
    exit 1
}

