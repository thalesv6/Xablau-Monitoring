# Simple method using Task Scheduler with event-based trigger
# This is the RECOMMENDED approach - more reliable
# Run this script as Administrator

$scriptPath = Join-Path $PSScriptRoot "pagecounter-folders.py"
$pythonPath = (Get-Command python -ErrorAction SilentlyContinue).Source

if (-not $pythonPath) {
  $pythonPath = (Get-Command python3 -ErrorAction SilentlyContinue).Source
}

if (-not $pythonPath) {
  Write-Host "ERRO: Python nao encontrado. Certifique-se de que Python esta instalado e no PATH." -ForegroundColor Red
  exit 1
}

if (-not (Test-Path $scriptPath)) {
  Write-Host "ERRO: Arquivo pagecounter-folders.py nao encontrado em $scriptPath" -ForegroundColor Red
  exit 1
}

$taskName = "XABLAU-PageCounter-Shutdown"
$taskDescription = "Executa contagem de paginas PDF antes do desligamento do computador"

# Remove existing task if it exists
$existingTask = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if ($existingTask) {
  Write-Host "Removendo tarefa existente..." -ForegroundColor Yellow
  Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
}

# Escape paths for XML
$pythonPathEscaped = $pythonPath -replace '&', '&amp;' -replace '<', '&lt;' -replace '>', '&gt;' -replace '"', '&quot;'
$scriptPathEscaped = $scriptPath -replace '&', '&amp;' -replace '<', '&lt;' -replace '>', '&gt;' -replace '"', '&quot;'
$workingDirEscaped = $PSScriptRoot -replace '&', '&amp;' -replace '<', '&lt;' -replace '>', '&gt;' -replace '"', '&quot;'
$taskDescriptionEscaped = $taskDescription -replace '&', '&amp;' -replace '<', '&lt;' -replace '>', '&gt;' -replace '"', '&quot;'

# Create XML for the task
$xmlFile = Join-Path $env:TEMP "xablau-shutdown-task.xml"

$taskXml = @"
<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.4" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Description>$taskDescriptionEscaped</Description>
  </RegistrationInfo>
  <Triggers>
    <EventTrigger>
      <Enabled>true</Enabled>
      <Subscription>&lt;QueryList&gt;&lt;Query Id="0" Path="System"&gt;&lt;Select Path="System"&gt;*[System[Provider[@Name='USER32'] and (EventID=1074 or EventID=1076)]]&lt;/Select&gt;&lt;/Query&gt;&lt;/QueryList&gt;</Subscription>
    </EventTrigger>
  </Triggers>
  <Actions>
    <Exec>
      <Command>$pythonPathEscaped</Command>
      <Arguments>$scriptPathEscaped</Arguments>
      <WorkingDirectory>$workingDirEscaped</WorkingDirectory>
    </Exec>
  </Actions>
  <Principals>
    <Principal id="Author">
      <UserId>S-1-5-18</UserId>
      <RunLevel>HighestAvailable</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <AllowHardTerminate>true</AllowHardTerminate>
    <StartWhenAvailable>true</StartWhenAvailable>
    <RunOnlyIfNetworkAvailable>false</RunOnlyIfNetworkAvailable>
    <IdleSettings>
      <StopOnIdleEnd>false</StopOnIdleEnd>
      <RestartOnIdle>false</RestartOnIdle>
    </IdleSettings>
    <AllowStartOnDemand>true</AllowStartOnDemand>
    <Enabled>true</Enabled>
    <Hidden>false</Hidden>
    <RunOnlyIfIdle>false</RunOnlyIfIdle>
    <WakeToRun>false</WakeToRun>
    <ExecutionTimeLimit>PT30M</ExecutionTimeLimit>
    <Priority>7</Priority>
  </Settings>
</Task>
"@

try {
  # Write XML file
  $taskXml | Out-File -FilePath $xmlFile -Encoding Unicode -Force
    
  # Import task using schtasks
  $result = schtasks /Create /TN $taskName /XML $xmlFile /F 2>&1
    
  if ($LASTEXITCODE -eq 0) {
    Write-Host "Tarefa criada com sucesso!" -ForegroundColor Green
    Write-Host ""
    Write-Host "A tarefa '$taskName' sera executada automaticamente antes do desligamento." -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Para verificar a tarefa:" -ForegroundColor Yellow
    Write-Host "  schtasks /Query /TN `"$taskName`"" -ForegroundColor White
    Write-Host ""
    Write-Host "Para remover a tarefa:" -ForegroundColor Yellow
    Write-Host "  schtasks /Delete /TN `"$taskName`" /F" -ForegroundColor White
        
    # Cleanup temp file
    Remove-Item $xmlFile -ErrorAction SilentlyContinue
  }
  else {
    Write-Host "ERRO ao criar tarefa:" -ForegroundColor Red
    Write-Host $result
    exit 1
  }
    
}
catch {
  Write-Host "ERRO ao criar tarefa: $($_.Exception.Message)" -ForegroundColor Red
  if (Test-Path $xmlFile) {
    Remove-Item $xmlFile -ErrorAction SilentlyContinue
  }
  exit 1
}
