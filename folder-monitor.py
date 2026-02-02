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
    Handler that detects changes in PDF files and implements debounce
    to execute the script only after a period without changes
    """
    
    def __init__(self, delay_seconds, script_path):
        super().__init__()
        self.delay_seconds = delay_seconds
        self.script_path = script_path
        self.timer = None
        self.lock = threading.Lock()
        self.is_running = False
    
    def is_pdf_file(self, file_path):
        """Checks if the file is a PDF"""
        return file_path.lower().endswith('.pdf')
    
    def reset_timer(self):
        """Resets the debounce timer"""
        with self.lock:
            # Cancel previous timer if it exists
            if self.timer is not None:
                self.timer.cancel()
            
            # Create a new timer
            self.timer = threading.Timer(self.delay_seconds, self.execute_script)
            self.timer.start()
            print(f"📁 Mudança detectada. Aguardando {self.delay_seconds}s sem novas mudanças...")
    
    def execute_script(self):
        """Executes the page counting script"""
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
            
            # Execute script using subprocess to maintain isolation
            script_dir = os.path.dirname(os.path.abspath(self.script_path))
            result = subprocess.run(
                [sys.executable, self.script_path],
                cwd=script_dir,
                capture_output=False,
                text=True,
                encoding='utf-8',
                errors='replace'
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
        """Called when a file is created"""
        if not event.is_directory and self.is_pdf_file(event.src_path):
            self.reset_timer()
    
    def on_modified(self, event):
        """Called when a file is modified"""
        if not event.is_directory and self.is_pdf_file(event.src_path):
            self.reset_timer()
    
    def on_moved(self, event):
        """Called when a file is moved/renamed"""
        if not event.is_directory:
            # Check both source and destination files
            if self.is_pdf_file(event.src_path) or (event.dest_path and self.is_pdf_file(event.dest_path)):
                self.reset_timer()

def load_config():
    """Loads settings from config.json"""
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
        description='Monitors changes in PDF files and executes page counting with debounce'
    )
    parser.add_argument(
        '--delay',
        type=int,
        help='Delay in seconds after last change before executing (overrides config.json)'
    )
    parser.add_argument(
        '--path',
        type=str,
        help='Path of folder to monitor (overrides config.json)'
    )
    
    args = parser.parse_args()
    
    # Load settings
    config = load_config()
    
    # Use command line arguments or file settings
    delay_seconds = args.delay if args.delay else config.get('delay_seconds', 30)
    watch_path = args.path if args.path else config.get('watch_path', 'G:/My Drive/XABLAU/')
    
    # Check if monitoring is enabled
    if not config.get('enabled', True):
        print("⚠️ Monitoramento desabilitado no config.json")
        return
    
    # Validate path
    if not os.path.exists(watch_path):
        print(f"❌ Erro: Pasta não encontrada: {watch_path}")
        print("Verifique o caminho no config.json ou use --path para especificar")
        return
    
    if not os.path.isdir(watch_path):
        print(f"❌ Erro: Caminho não é uma pasta: {watch_path}")
        return
    
    # Path of script to be executed
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
    
    # Initial state check when starting the monitor
    print("\n🔍 Verificando estado inicial da pasta...")
    print("="*50)
    try:
        script_dir = os.path.dirname(os.path.abspath(script_path))
        result = subprocess.run(
            [sys.executable, script_path],
            cwd=script_dir,
            capture_output=False,
            text=True,
            encoding='utf-8',
            errors='replace'
        )
        
        if result.returncode == 0:
            print("\n✅ Verificação inicial concluída!")
            print("ℹ️  Se não houver mudanças desde a última execução, nenhuma mensagem será enviada.")
        else:
            print(f"\n⚠️  Verificação inicial concluída com avisos (código: {result.returncode})")
    except Exception as e:
        print(f"\n❌ Erro na verificação inicial: {e}")
    
    print("\n" + "="*50)
    print("👀 Monitorando pasta... (Pressione Ctrl+C para parar)")
    print("="*50 + "\n")
    
    # Create handler and observer
    event_handler = PDFChangeHandler(delay_seconds, script_path)
    observer = Observer()
    observer.schedule(event_handler, watch_path, recursive=True)
    
    try:
        observer.start()
        # Keep script running
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\n🛑 Parando monitoramento...")
        observer.stop()
    
    observer.join()
    print("✅ Monitoramento encerrado.")

if __name__ == "__main__":
    main()

