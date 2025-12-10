# Configuração de Execução Automática no Desligamento

Este guia explica como configurar o script `pagecounter-folders.py` para executar automaticamente antes do desligamento do computador.

## 📋 Dificuldade

**Baixa/Média** - A configuração é relativamente simples, mas requer privilégios de administrador.

## 🎯 Por que esta abordagem?

Ao invés de agendar em um horário específico (que falharia se o computador estivesse desligado), esta solução detecta o evento de desligamento do Windows e executa o script automaticamente.

## 🚀 Método Recomendado (Mais Simples)

### Passo 1: Execute o script de configuração

Abra o PowerShell **como Administrador** e execute:

```powershell
cd "D:\Trampo\xablau\XABLAU PROJECT"
.\setup-shutdown-task-simple.ps1
```

Este script irá:
- Detectar o Python instalado
- Criar uma tarefa agendada no Windows Task Scheduler
- Configurar para executar antes do desligamento usando eventos do sistema

### Passo 2: Verificar se funcionou

Para verificar se a tarefa foi criada:

```powershell
schtasks /Query /TN "XABLAU-PageCounter-Shutdown"
```

## 🔧 Métodos Alternativos

### Método 2: Usando Group Policy (Mais Confiável, mas mais complexo)

1. Execute `setup-shutdown-script.ps1` como Administrador
2. Abra o Group Policy Editor: `gpedit.msc`
3. Vá em: `Computer Configuration > Windows Settings > Scripts (Startup/Shutdown) > Shutdown`
4. Adicione o script `run-on-shutdown.bat`

### Método 3: Configuração Manual via Task Scheduler

1. Abra o Task Scheduler (`taskschd.msc`)
2. Crie uma nova tarefa
3. Na aba "Triggers", adicione um novo trigger:
   - Tipo: "On an event"
   - Log: "System"
   - Source: "USER32"
   - Event ID: "1074" ou "1076"
4. Na aba "Actions", adicione:
   - Action: "Start a program"
   - Program: caminho do Python (ex: `C:\Python\python.exe`)
   - Arguments: caminho completo do `pagecounter-folders.py`
5. Configure para executar como "SYSTEM" com privilégios elevados

## ⚠️ Limitações e Considerações

1. **Tempo de execução**: O script precisa terminar antes do Windows finalizar o desligamento. O timeout padrão é de 30 minutos, mas normalmente o script executa em segundos.

2. **Computador já desligado**: Se o computador for desligado abruptamente (queda de energia, travamento), o script não será executado. Neste caso, ele rodará na próxima vez que você desligar normalmente.

3. **Privilégios**: A tarefa roda como SYSTEM, então tem acesso total ao sistema.

4. **Teste**: Para testar sem desligar o computador, você pode simular o evento ou executar manualmente:
   ```powershell
   schtasks /Run /TN "XABLAU-PageCounter-Shutdown"
   ```

## 🗑️ Remover a Configuração

Para remover a tarefa agendada:

```powershell
schtasks /Delete /TN "XABLAU-PageCounter-Shutdown" /F
```

## 📝 Notas Técnicas

- O script usa eventos do Windows (Event ID 1074 = shutdown iniciado pelo usuário, 1076 = shutdown inesperado)
- A tarefa é configurada para executar mesmo se o computador estiver em bateria
- O timeout é de 30 minutos (mais que suficiente para a contagem de páginas)

