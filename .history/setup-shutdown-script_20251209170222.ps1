# Alternative method: Setup shutdown script via Group Policy/Registry
# This method is more reliable for shutdown events
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

# Create a wrapper batch file that will be executed on shutdown
$batchFile = Join-Path $PSScriptRoot "run-on-shutdown.bat"
$batchContent = @"
@echo off
cd /d "$PSScriptRoot"
"$pythonPath" "$scriptPath"
"@

$batchContent | Out-File -FilePath $batchFile -Encoding ASCII -Force
Write-Host "Arquivo batch criado: $batchFile" -ForegroundColor Green

# Method 1: Using Registry (requires admin)
$registryPath = "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Group Policy\Scripts\Shutdown"
$scriptPathReg = $batchFile

try {
    # Create registry keys for shutdown script
    if (-not (Test-Path $registryPath)) {
        New-Item -Path $registryPath -Force | Out-Null
    }
    
    $scriptsPath = Join-Path $registryPath "0"
    if (-not (Test-Path $scriptsPath)) {
        New-Item -Path $scriptsPath -Force | Out-Null
    }
    
    Set-ItemProperty -Path $scriptsPath -Name "0" -Value $scriptPathReg -Type String -Force
    Set-ItemProperty -Path $scriptsPath -Name "0Parameters" -Value "" -Type String -Force
    
    Write-Host "Script de shutdown configurado via Registry!" -ForegroundColor Green
    Write-Host ""
    Write-Host "NOTA: Pode ser necessário usar Group Policy Editor (gpedit.msc) para garantir" -ForegroundColor Yellow
    Write-Host "que o script seja executado. Vá em:" -ForegroundColor Yellow
    Write-Host "Computer Configuration > Windows Settings > Scripts (Startup/Shutdown) > Shutdown" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Ou use o método mais simples com Task Scheduler (veja setup-shutdown-task-simple.ps1)" -ForegroundColor Yellow
    
} catch {
    Write-Host "ERRO ao configurar via Registry: $_" -ForegroundColor Red
    Write-Host "Tente usar o Group Policy Editor manualmente (gpedit.msc)" -ForegroundColor Yellow
    exit 1
}

