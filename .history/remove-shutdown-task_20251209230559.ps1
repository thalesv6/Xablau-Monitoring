# Script to remove the shutdown task
# Run this script as Administrator

$taskName = "XABLAU-PageCounter-Shutdown"

Write-Host "Removendo tarefa agendada: $taskName" -ForegroundColor Yellow

try {
    $existingTask = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
    
    if ($existingTask) {
        Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
        Write-Host "Tarefa removida com sucesso!" -ForegroundColor Green
    } else {
        Write-Host "Tarefa nao encontrada. Pode ja ter sido removida." -ForegroundColor Yellow
    }
    
    # Also try using schtasks command (alternative method)
    $result = schtasks /Delete /TN $taskName /F 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "Tarefa removida via schtasks tambem." -ForegroundColor Green
    }
    
} catch {
    Write-Host "Erro ao remover tarefa: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host ""
    Write-Host "Tente executar manualmente:" -ForegroundColor Yellow
    Write-Host "  schtasks /Delete /TN `"$taskName`" /F" -ForegroundColor White
}

