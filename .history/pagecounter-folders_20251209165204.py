import os
import time
import json
import subprocess
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from PyPDF2 import PdfReader
import threading

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

def count_pages_by_folder_optimized(root_directory='G:/My Drive/XABLAU/'):
    """
    Versão otimizada que conta páginas por pasta usando processamento paralelo
    """
    folder_pages = {}
    
    # Lista todas as pastas na raiz que começam com dígito
    root_folders = [
        item for item in os.listdir(root_directory)
        if os.path.isdir(os.path.join(root_directory, item)) and item[:1].isdigit()
    ]

    # Inclui subpastas específicas dentro de VICTORIA
    targets = []

    for folder in root_folders:
        folder_path = os.path.join(root_directory, folder)
        targets.append((folder, folder_path))

    victoria_path = os.path.join(root_directory, "VICTORIA")
    if os.path.isdir(victoria_path):
        try:
            victoria_subs = [
                sub for sub in os.listdir(victoria_path)
                if os.path.isdir(os.path.join(victoria_path, sub))
            ]
            for sub in victoria_subs:
                sub_path = os.path.join(victoria_path, sub)
                label = f"VICTORIA/{sub}"
                targets.append((label, sub_path))
        except Exception as e:
            print(f"Erro ao listar subpastas de VICTORIA: {e}")
    
    if not targets:
        return folder_pages
    
    # Processa pastas em paralelo
    with ThreadPoolExecutor(max_workers=min(len(targets), 4)) as executor:
        future_to_label = {}
        
        for label, folder_path in targets:
            future = executor.submit(count_pages_in_directory_parallel, folder_path)
            future_to_label[future] = label
        
        # Coleta resultados
        for future in as_completed(future_to_label):
            label = future_to_label[future]
            try:
                pages = future.result()
                folder_pages[label] = pages
            except Exception as e:
                print(f"Erro ao processar pasta {label}: {e}")
                folder_pages[label] = 0
    
    return folder_pages

def format_whatsapp_message(folder_pages, total_pages, current_datetime):
    """
    Formata os resultados da contagem para envio via WhatsApp
    """
    message = "📊 *Relatório diário XABLAU ENTERPRISES*\n\n"
    message += "📁 *Contagem por Pasta:*\n"
    
    if not folder_pages:
        message += "Nenhuma pasta encontrada.\n"
    else:
        for folder, pages in sorted(folder_pages.items()):
            message += f"Pasta '{folder}': {pages} páginas\n"
    
    message += f"\n📈 *Total:* {total_pages} páginas\n"
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
    
    # Contagem total otimizada
    directory = '.'
    total_pages = count_pages_in_directory_parallel(directory)
    
    elapsed_total = time.time() - start_time
    print(f"Total de páginas em todos os arquivos PDF: {total_pages}")
    print(f"Tempo total: {elapsed_total:.2f} segundos")
    
    print("\n" + "="*50)
    print("CONTAGEM POR PASTA (OTIMIZADA):")
    print("="*50)
    
    # Contagem por pasta otimizada
    folder_pages = count_pages_by_folder_optimized()
    
    if not folder_pages:
        print("Nenhuma pasta encontrada na raiz.")
        total_folder_pages = 0
    else:
        for folder, pages in sorted(folder_pages.items()):
            print(f"Pasta '{folder}': {pages} páginas")
        
        # Total das pastas
        total_folder_pages = sum(folder_pages.values())
        print(f"\nTotal de páginas nas pastas: {total_folder_pages}")
    
    total_elapsed = time.time() - start_time
    print(f"\nTempo total de execução: {total_elapsed:.2f} segundos")
    
    # Send results to WhatsApp
    if folder_pages:
        current_datetime = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        message = format_whatsapp_message(folder_pages, total_folder_pages, current_datetime)
        send_whatsapp_message(message)

if __name__ == "__main__":
    main()