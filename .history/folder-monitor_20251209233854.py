import os
import sys
import json
import time
import argparse
import subprocess
import threading
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class PDFChangeHandler(FileSystemEventHandler):
    """
    Handler que detecta mudanças em arquivos PDF e implementa debounce
    para executar o script apenas após um período sem mudanças
    """
    
    def __init__(self, delay_seconds, script_path):
        super().__init__()
        self.delay_seconds = delay_seconds
        self.script_path = script_path
        self.timer = None
        self.lock = threading.Lock()
        self.is_running = False
    
    def is_pdf_file(self, file_path):
        """Verifica se o arquivo é um PDF"""
        return file_path.lower().endswith('.pdf')
    
    def reset_timer(self):
        """Reseta o timer de debounce"""
        with self.lock:
            # Cancela o timer anterior se existir
            if self.timer is not None:
                self.timer.cancel()
            
            # Cria um novo timer
            self.timer = threading.Timer(self.delay_seconds, self.execute_script)
            self.timer.start()
            print(f"📁 Mudança detectada. Aguardando {self.delay_seconds}s sem novas mudanças...")
    
    def execute_script(self):
        """Executa o script de contagem de páginas"""
        with self.lock:
            if self.is_running:
                print("⚠️ Script já está em execução. Pulando...")
                return
            
            self.is_running = True
            self.timer = None
        
        try:
            print("\n" + "="*50)
            print("🚀 Executando contagem de páginas...")
            print("="*50)
            
            # Executa o script usando subprocess para manter isolamento
            script_dir = os.path.dirname(os.path.abspath(self.script_path))
            result = subprocess.run(
                [sys.executable, self.script_path],
                cwd=script_dir,
                capture_output=False,
                text=True
            )
            
            if result.returncode == 0:
                print("\n✅ Script executado com sucesso!")
            else:
                print(f"\n❌ Erro ao executar script (código: {result.returncode})")
                
        except Exception as e:
            print(f"\n❌ Erro ao executar script: {e}")
        finally:
            with self.lock:
                self.is_running = False
                print("\n" + "="*50)
                print("👀 Monitorando pasta... (Pressione Ctrl+C para parar)")
                print("="*50 + "\n")
    
    def on_created(self, event):
        """Chamado quando um arquivo é criado"""
        if not event.is_directory and self.is_pdf_file(event.src_path):
            self.reset_timer()
    
    def on_modified(self, event):
        """Chamado quando um arquivo é modificado"""
        if not event.is_directory and self.is_pdf_file(event.src_path):
            self.reset_timer()
    
    def on_moved(self, event):
        """Chamado quando um arquivo é movido/renomeado"""
        if not event.is_directory:
            # Verifica tanto o arquivo de origem quanto o destino
            if self.is_pdf_file(event.src_path) or (event.dest_path and self.is_pdf_file(event.dest_path)):
                self.reset_timer()

def load_config():
    """Carrega configurações do config.json"""
    config_path = os.path.join(os.path.dirname(__file__), 'config.json')
    default_config = {
        "monitor": {
            "delay_seconds": 30,
            "watch_path": "G:/My Drive/XABLAU/",
            "enabled": True
        }
    }
    
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                return config.get('monitor', default_config['monitor'])
        except Exception as e:
            print(f"⚠️ Erro ao carregar config.json: {e}. Usando configurações padrão.")
    
    return default_config['monitor']

def main():
    parser = argparse.ArgumentParser(
        description='Monitora mudanças em arquivos PDF e executa contagem de páginas com debounce'
    )
    parser.add_argument(
        '--delay',
        type=int,
        help='Delay em segundos após última mudança antes de executar (sobrescreve config.json)'
    )
    parser.add_argument(
        '--path',
        type=str,
        help='Caminho da pasta a monitorar (sobrescreve config.json)'
    )
    
    args = parser.parse_args()
    
    # Carrega configurações
    config = load_config()
    
    # Usa argumentos da linha de comando ou configurações do arquivo
    delay_seconds = args.delay if args.delay else config.get('delay_seconds', 30)
    watch_path = args.path if args.path else config.get('watch_path', 'G:/My Drive/XABLAU/')
    
    # Verifica se o monitoramento está habilitado
    if not config.get('enabled', True):
        print("⚠️ Monitoramento desabilitado no config.json")
        return
    
    # Valida o caminho
    if not os.path.exists(watch_path):
        print(f"❌ Erro: Pasta não encontrada: {watch_path}")
        print("Verifique o caminho no config.json ou use --path para especificar")
        return
    
    if not os.path.isdir(watch_path):
        print(f"❌ Erro: Caminho não é uma pasta: {watch_path}")
        return
    
    # Caminho do script a ser executado
    script_dir = os.path.dirname(os.path.abspath(__file__))
    script_path = os.path.join(script_dir, 'pagecounter-folders.py')
    
    if not os.path.exists(script_path):
        print(f"❌ Erro: Script não encontrado: {script_path}")
        return
    
    print("="*50)
    print("📊 Monitor de Pastas XABLAU")
    print("="*50)
    print(f"📁 Pasta monitorada: {watch_path}")
    print(f"⏱️  Delay: {delay_seconds} segundos")
    print(f"📄 Script: {script_path}")
    print("="*50)
    print("👀 Monitorando pasta... (Pressione Ctrl+C para parar)")
    print("="*50 + "\n")
    
    # Cria o handler e observer
    event_handler = PDFChangeHandler(delay_seconds, script_path)
    observer = Observer()
    observer.schedule(event_handler, watch_path, recursive=True)
    
    try:
        observer.start()
        # Mantém o script rodando
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\n🛑 Parando monitoramento...")
        observer.stop()
    
    observer.join()
    print("✅ Monitoramento encerrado.")

if __name__ == "__main__":
    main()

