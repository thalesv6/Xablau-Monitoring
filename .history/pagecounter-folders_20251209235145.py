import os
import time
import json
import subprocess
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from PyPDF2 import PdfReader
import threading
import re

def count_pdf_pages_fast(file_path):
    """
    Conta páginas de um único arquivo PDF de forma otimizada
    """
    try:
        with open(file_path, "rb") as pdf_file:
            pdf_reader = PdfReader(pdf_file)
            return len(pdf_reader.pages)
    except Exception as e:
        print(f"Erro ao processar {file_path}: {e}")
        return 0

def get_pdf_files(directory):
    """
    Coleta todos os arquivos PDF de um diretório de forma eficiente
    """
    pdf_files = []
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.lower().endswith('.pdf'):
                pdf_files.append(os.path.join(root, file))
    return pdf_files

def count_pages_in_directory_parallel(directory, max_workers=4):
    """
    Conta páginas usando processamento paralelo
    """
    pdf_files = get_pdf_files(directory)
    
    if not pdf_files:
        return 0
    
    total_pages = 0
    
    # Usa ThreadPoolExecutor para processamento paralelo
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submete todas as tarefas
        future_to_file = {executor.submit(count_pdf_pages_fast, file_path): file_path 
                         for file_path in pdf_files}
        
        # Coleta os resultados conforme são completados
        for future in as_completed(future_to_file):
            file_path = future_to_file[future]
            try:
                pages = future.result()
                total_pages += pages
            except Exception as e:
                print(f"Erro ao processar {file_path}: {e}")
    
    return total_pages

def count_pages_by_folder_optimized(root_directory=None):
    """
    Versão otimizada que conta páginas por pasta usando processamento paralelo
    Retorna: (folder_pages_normal, folder_pages_victoria)
    Se root_directory não for fornecido, lê do config.json
    """
    if root_directory is None:
        # Lê o path do config.json
        config_path = os.path.join(os.path.dirname(__file__), 'config.json')
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    root_directory = config.get('monitor', {}).get('watch_path', 'G:/My Drive/XABLAU/')
            except Exception as e:
                print(f"Erro ao ler config.json: {e}. Usando path padrão.")
                root_directory = 'G:/My Drive/XABLAU/'
        else:
            root_directory = 'G:/My Drive/XABLAU/'
    folder_pages_normal = {}
    folder_pages_victoria = {}
    
    # Lista todas as pastas na raiz que começam com dígito
    root_folders = [
        item for item in os.listdir(root_directory)
        if os.path.isdir(os.path.join(root_directory, item)) and item[:1].isdigit()
    ]

    # Separa targets normais e targets VICTORIA
    targets_normal = []
    targets_victoria = []

    for folder in root_folders:
        folder_path = os.path.join(root_directory, folder)
        # Se a pasta contém VICTORIA, não adiciona ela diretamente, mas sim suas subpastas
        if "VICTORIA" in folder.upper():
            # Processa subpastas de VICTORIA separadamente
            try:
                victoria_subs = [
                    sub for sub in os.listdir(folder_path)
                    if os.path.isdir(os.path.join(folder_path, sub))
                ]
                for sub in victoria_subs:
                    sub_path = os.path.join(folder_path, sub)
                    label = f"{folder}/{sub}"
                    targets_victoria.append((label, sub_path))
            except Exception as e:
                print(f"Erro ao listar subpastas de {folder}: {e}")
        else:
            # Pasta normal, adiciona diretamente
            targets_normal.append((folder, folder_path))
    
    # Processa pastas normais em paralelo
    if targets_normal:
        with ThreadPoolExecutor(max_workers=min(len(targets_normal), 4)) as executor:
            future_to_label = {}
            
            for label, folder_path in targets_normal:
                future = executor.submit(count_pages_in_directory_parallel, folder_path)
                future_to_label[future] = label
            
            # Coleta resultados
            for future in as_completed(future_to_label):
                label = future_to_label[future]
                try:
                    pages = future.result()
                    folder_pages_normal[label] = pages
                except Exception as e:
                    print(f"Erro ao processar pasta {label}: {e}")
                    folder_pages_normal[label] = 0
    
    # Processa pastas VICTORIA em paralelo
    if targets_victoria:
        with ThreadPoolExecutor(max_workers=min(len(targets_victoria), 4)) as executor:
            future_to_label = {}
            
            for label, folder_path in targets_victoria:
                future = executor.submit(count_pages_in_directory_parallel, folder_path)
                future_to_label[future] = label
            
            # Coleta resultados
            for future in as_completed(future_to_label):
                label = future_to_label[future]
                try:
                    pages = future.result()
                    folder_pages_victoria[label] = pages
                except Exception as e:
                    print(f"Erro ao processar pasta {label}: {e}")
                    folder_pages_victoria[label] = 0
    
    return folder_pages_normal, folder_pages_victoria

def format_whatsapp_message(folder_pages_normal, folder_pages_victoria, total_pages_before_victoria, current_datetime):
    """
    Formata os resultados da contagem para envio via WhatsApp
    """
    message = "📊 *Relatório diário XABLAU ENTERPRISES*\n\n"
    
    # Total antes das pastas VICTORIA
    message += f"📈 *Total:* {total_pages_before_victoria} páginas\n\n"
    
    # Pastas normais (se houver)
    if folder_pages_normal:
        message += "📁 *Contagem por Pasta:*\n"
        for folder, pages in sorted(folder_pages_normal.items()):
            message += f"Pasta '{folder}': {pages} páginas\n"
        message += "\n"
    
    # Pastas VICTORIA (já processadas)
    if folder_pages_victoria:
        message += "📁 *Pastas VICTORIA (Processadas):*\n"
        for folder, pages in sorted(folder_pages_victoria.items()):
            message += f"Pasta '{folder}': {pages} páginas\n"
        message += "\n"
    
    message += f"🕒 *Data/Hora:* {current_datetime}"
    
    return message

def send_whatsapp_message(message):
    """
    Envia mensagem via WhatsApp usando o script Node.js
    """
    try:
        # Read config to check if WhatsApp is enabled
        config_path = os.path.join(os.path.dirname(__file__), 'config.json')
        if not os.path.exists(config_path):
            print("Arquivo config.json não encontrado. Pulando envio WhatsApp.")
            return False
        
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        if not config.get('whatsapp', {}).get('enabled', False):
            print("Envio WhatsApp desabilitado no config.json")
            return False
        
        # Get path to Node.js script
        script_dir = os.path.dirname(os.path.abspath(__file__))
        node_script = os.path.join(script_dir, 'whatsapp-sender.js')
        
        if not os.path.exists(node_script):
            print(f"Script whatsapp-sender.js não encontrado em {script_dir}")
            return False
        
        # Call Node.js script with message as argument
        # For Windows compatibility, pass message directly as list item
        print("\nEnviando resultados para WhatsApp...")
        
        # Pass message as separate argument to avoid shell escaping issues
        cmd = ['node', node_script, message]
        
        result = subprocess.run(
            cmd,
            cwd=script_dir,
            capture_output=True,
            text=True,
            timeout=120
        )
        
        if result.returncode == 0:
            print("Mensagem enviada com sucesso para WhatsApp!")
            return True
        else:
            print(f"Erro ao enviar mensagem: {result.stderr}")
            return False
            
    except FileNotFoundError:
        print("Node.js não encontrado. Certifique-se de que Node.js está instalado.")
        return False
    except subprocess.TimeoutExpired:
        print("Timeout ao enviar mensagem WhatsApp.")
        return False
    except Exception as e:
        print(f"Erro ao enviar mensagem WhatsApp: {e}")
        return False

def main():
    start_time = time.time()
    
    print("Iniciando contagem de páginas...")
    print("="*50)
    
    # Contagem por pasta otimizada (retorna separado: normais e VICTORIA)
    folder_pages_normal, folder_pages_victoria = count_pages_by_folder_optimized()
    
    # Calcula total antes das pastas VICTORIA (soma das pastas normais)
    total_pages_before_victoria = sum(folder_pages_normal.values())
    
    # Mostra total antes das pastas VICTORIA
    print(f"\n📈 *Total:* {total_pages_before_victoria} páginas")
    print("="*50)
    
    # Mostra pastas normais
    if folder_pages_normal:
        print("\n📁 *Contagem por Pasta:*")
        for folder, pages in sorted(folder_pages_normal.items()):
            print(f"Pasta '{folder}': {pages} páginas")
    
    # Mostra pastas VICTORIA (já processadas)
    if folder_pages_victoria:
        print("\n📁 *Pastas VICTORIA (Processadas):*")
        for folder, pages in sorted(folder_pages_victoria.items()):
            print(f"Pasta '{folder}': {pages} páginas")
    
    if not folder_pages_normal and not folder_pages_victoria:
        print("Nenhuma pasta encontrada na raiz.")
    
    total_elapsed = time.time() - start_time
    print(f"\nTempo total de execução: {total_elapsed:.2f} segundos")
    
    # Send results to WhatsApp
    if folder_pages_normal or folder_pages_victoria:
        current_datetime = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        message = format_whatsapp_message(folder_pages_normal, folder_pages_victoria, total_pages_before_victoria, current_datetime)
        send_whatsapp_message(message)

if __name__ == "__main__":
    main()