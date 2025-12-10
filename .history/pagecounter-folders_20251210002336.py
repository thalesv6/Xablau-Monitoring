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
    Counts pages of a single PDF file in an optimized way
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
    Collects all PDF files from a directory efficiently
    """
    pdf_files = []
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.lower().endswith('.pdf'):
                pdf_files.append(os.path.join(root, file))
    return pdf_files

def count_pages_in_directory_parallel(directory, max_workers=4):
    """
    Counts pages using parallel processing
    """
    pdf_files = get_pdf_files(directory)
    
    if not pdf_files:
        return 0
    
    total_pages = 0
    
    # Use ThreadPoolExecutor for parallel processing
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks
        future_to_file = {executor.submit(count_pdf_pages_fast, file_path): file_path 
                         for file_path in pdf_files}
        
        # Collect results as they are completed
        for future in as_completed(future_to_file):
            file_path = future_to_file[future]
            try:
                pages = future.result()
                total_pages += pages
            except Exception as e:
                print(f"Error processing {file_path}: {e}")
    
    return total_pages

def count_pages_by_folder_optimized(root_directory=None):
    """
    Optimized version that counts pages per folder using parallel processing
    Returns: (folder_pages_normal, folder_pages_victoria)
    If root_directory is not provided, reads from config.json
    """
    if root_directory is None:
        # Read path from config.json
        config_path = os.path.join(os.path.dirname(__file__), 'config.json')
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    root_directory = config.get('monitor', {}).get('watch_path', 'G:/My Drive/XABLAU/')
            except Exception as e:
                print(f"Error reading config.json: {e}. Using default path.")
                root_directory = 'G:/My Drive/XABLAU/'
        else:
            root_directory = 'G:/My Drive/XABLAU/'
    folder_pages_normal = {}
    folder_pages_victoria = {}
    
    # List all folders in root that start with a digit
    root_folders = [
        item for item in os.listdir(root_directory)
        if os.path.isdir(os.path.join(root_directory, item)) and item[:1].isdigit()
    ]

    # Separate normal targets and VICTORIA targets
    targets_normal = []
    targets_victoria = []

    for folder in root_folders:
        folder_path = os.path.join(root_directory, folder)
        # If folder contains VICTORIA, don't add it directly, but rather its subfolders
        if "VICTORIA" in folder.upper():
            # Process VICTORIA subfolders separately
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
                print(f"Error listing subfolders of {folder}: {e}")
        else:
            # Normal folder, add directly
            targets_normal.append((folder, folder_path))
    
    # Process normal folders in parallel
    if targets_normal:
        with ThreadPoolExecutor(max_workers=min(len(targets_normal), 4)) as executor:
            future_to_label = {}
            
            for label, folder_path in targets_normal:
                future = executor.submit(count_pages_in_directory_parallel, folder_path)
                future_to_label[future] = label
            
            # Collect results
            for future in as_completed(future_to_label):
                label = future_to_label[future]
                try:
                    pages = future.result()
                    folder_pages_normal[label] = pages
                except Exception as e:
                    print(f"Error processing folder {label}: {e}")
                    folder_pages_normal[label] = 0
    
    # Process VICTORIA folders in parallel
    if targets_victoria:
        with ThreadPoolExecutor(max_workers=min(len(targets_victoria), 4)) as executor:
            future_to_label = {}
            
            for label, folder_path in targets_victoria:
                future = executor.submit(count_pages_in_directory_parallel, folder_path)
                future_to_label[future] = label
            
            # Collect results
            for future in as_completed(future_to_label):
                label = future_to_label[future]
                try:
                    pages = future.result()
                    folder_pages_victoria[label] = pages
                except Exception as e:
                    print(f"Error processing folder {label}: {e}")
                    folder_pages_victoria[label] = 0
    
    return folder_pages_normal, folder_pages_victoria

def extract_employee_name(folder_name):
    """
    Extracts employee name from folder name
    Ex: "1.LEIANE" -> "LEIANE"
    """
    # Remove numbers and dots from the beginning
    name = re.sub(r'^\d+\.?\s*', '', folder_name)
    # Remove slashes and subfolders (for VICTORIA folders)
    name = name.split('/')[0]
    return name.strip()

def get_history_file_path():
    """
    Returns the history file path
    """
    script_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(script_dir, 'pagecount_history.json')

def load_previous_results():
    """
    Loads results from the last execution
    """
    history_path = get_history_file_path()
    if os.path.exists(history_path):
        try:
            with open(history_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
                print(f"Error loading history: {e}")
    return None

def save_current_results(folder_pages_normal, folder_pages_victoria, total_pages_before_victoria):
    """
    Saves current results for future comparison
    """
    history_path = get_history_file_path()
    try:
        data = {
            'timestamp': datetime.now().isoformat(),
            'folder_pages_normal': folder_pages_normal,
            'folder_pages_victoria': folder_pages_victoria,
            'total_pages_before_victoria': total_pages_before_victoria
        }
        with open(history_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
                print(f"Error saving history: {e}")

def calculate_changes(current_normal, current_victoria, previous_data):
    """
    Calculates changes by comparing with the last reading
    Returns: (changes_normal, changes_victoria)
    """
    changes_normal = {}
    changes_victoria = {}
    
    if previous_data is None:
        return changes_normal, changes_victoria
    
    prev_normal = previous_data.get('folder_pages_normal', {})
    prev_victoria = previous_data.get('folder_pages_victoria', {})
    
    # Compare normal folders
    all_folders = set(current_normal.keys()) | set(prev_normal.keys())
    for folder in all_folders:
        current = current_normal.get(folder, 0)
        previous = prev_normal.get(folder, 0)
        diff = current - previous
        if diff != 0:
            changes_normal[folder] = {
                'current': current,
                'previous': previous,
                'diff': diff
            }
    
    # Compare VICTORIA folders
    all_folders_victoria = set(current_victoria.keys()) | set(prev_victoria.keys())
    for folder in all_folders_victoria:
        current = current_victoria.get(folder, 0)
        previous = prev_victoria.get(folder, 0)
        diff = current - previous
        if diff != 0:
            changes_victoria[folder] = {
                'current': current,
                'previous': previous,
                'diff': diff
            }
    
    return changes_normal, changes_victoria

def format_whatsapp_message(folder_pages_normal, folder_pages_victoria, total_pages_before_victoria, 
                            changes_normal, changes_victoria, current_datetime, previous_timestamp=None):
    """
    Formats counting results for WhatsApp sending
    """
    message = "📊 *Relatório XABLAU ENTERPRISES*\n\n"
    
    # Total before VICTORIA folders
    message += f"📈 *Total:* {total_pages_before_victoria} páginas\n\n"
    
    # Changes since last reading
    if changes_normal or changes_victoria:
        message += "📊 *Mudanças desde a última leitura:*\n"
        
        # Group changes by employee
        employee_changes = {}
        
        # Process normal changes
        for folder, change_data in changes_normal.items():
            employee = extract_employee_name(folder)
            if employee not in employee_changes:
                employee_changes[employee] = 0
            employee_changes[employee] += change_data['diff']
        
        # Process VICTORIA changes
        for folder, change_data in changes_victoria.items():
            employee = extract_employee_name(folder)
            if employee not in employee_changes:
                employee_changes[employee] = 0
            employee_changes[employee] += change_data['diff']
        
        # Show changes by employee
        for employee, total_diff in sorted(employee_changes.items()):
            if total_diff > 0:
                message += f"➕ {employee}: +{total_diff} páginas\n"
            elif total_diff < 0:
                message += f"➖ {employee}: {total_diff} páginas\n"
        
        if previous_timestamp:
            try:
                prev_dt = datetime.fromisoformat(previous_timestamp)
                prev_str = prev_dt.strftime("%d/%m/%Y %H:%M")
                message += f"\n(Última leitura: {prev_str})\n"
            except:
                pass
        message += "\n"
    
    # Pastas normais (se houver)
    if folder_pages_normal:
        message += "📁 *Contagem por Pasta:*\n"
        for folder, pages in sorted(folder_pages_normal.items()):
            change_info = ""
            if folder in changes_normal:
                diff = changes_normal[folder]['diff']
                if diff > 0:
                    change_info = f" (+{diff})"
                elif diff < 0:
                    change_info = f" ({diff})"
            message += f"'{folder}': {pages} páginas{change_info}\n"
        message += "\n"
    
    # Pastas VICTORIA (já processadas)
    if folder_pages_victoria:
        message += "📁 *Pastas VICTORIA (Processadas):*\n"
        for folder, pages in sorted(folder_pages_victoria.items()):
            change_info = ""
            if folder in changes_victoria:
                diff = changes_victoria[folder]['diff']
                if diff > 0:
                    change_info = f" (+{diff})"
                elif diff < 0:
                    change_info = f" ({diff})"
            message += f"'{folder}': {pages} páginas{change_info}\n"
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
    
    # Carrega resultados anteriores para comparação
    previous_data = load_previous_results()
    
    # Contagem por pasta otimizada (retorna separado: normais e VICTORIA)
    folder_pages_normal, folder_pages_victoria = count_pages_by_folder_optimized()
    
    # Calcula total antes das pastas VICTORIA (soma das pastas normais)
    total_pages_before_victoria = sum(folder_pages_normal.values())
    
    # Calcula mudanças desde a última leitura
    changes_normal, changes_victoria = calculate_changes(
        folder_pages_normal, folder_pages_victoria, previous_data
    )
    
    # Salva resultados atuais para próxima comparação
    save_current_results(folder_pages_normal, folder_pages_victoria, total_pages_before_victoria)
    
    # Mostra total antes das pastas VICTORIA
    print(f"\n📈 *Total:* {total_pages_before_victoria} páginas")
    print("="*50)
    
    # Mostra mudanças desde a última leitura
    if changes_normal or changes_victoria:
        print("\n📊 *Mudanças desde a última leitura:*")
        
        # Agrupa mudanças por funcionário
        employee_changes = {}
        
        # Processa mudanças normais
        for folder, change_data in changes_normal.items():
            employee = extract_employee_name(folder)
            if employee not in employee_changes:
                employee_changes[employee] = 0
            employee_changes[employee] += change_data['diff']
        
        # Processa mudanças VICTORIA
        for folder, change_data in changes_victoria.items():
            employee = extract_employee_name(folder)
            if employee not in employee_changes:
                employee_changes[employee] = 0
            employee_changes[employee] += change_data['diff']
        
        # Mostra mudanças por funcionário
        for employee, total_diff in sorted(employee_changes.items()):
            if total_diff > 0:
                print(f"➕ {employee}: +{total_diff} páginas")
            elif total_diff < 0:
                print(f"➖ {employee}: {total_diff} páginas")
        
        if previous_data and 'timestamp' in previous_data:
            try:
                prev_dt = datetime.fromisoformat(previous_data['timestamp'])
                prev_str = prev_dt.strftime("%d/%m/%Y %H:%M")
                print(f"(Última leitura: {prev_str})")
            except:
                pass
    else:
        if previous_data:
            print("\n📊 Nenhuma mudança desde a última leitura.")
        else:
            print("\n📊 Primeira execução - histórico criado.")
    
    # Mostra pastas normais
    if folder_pages_normal:
        print("\n📁 *Contagem por Pasta:*")
        for folder, pages in sorted(folder_pages_normal.items()):
            change_info = ""
            if folder in changes_normal:
                diff = changes_normal[folder]['diff']
                if diff > 0:
                    change_info = f" (+{diff})"
                elif diff < 0:
                    change_info = f" ({diff})"
            print(f"Pasta '{folder}': {pages} páginas{change_info}")
    
    # Mostra pastas VICTORIA (já processadas)
    if folder_pages_victoria:
        print("\n📁 *Pastas VICTORIA (Processadas):*")
        for folder, pages in sorted(folder_pages_victoria.items()):
            change_info = ""
            if folder in changes_victoria:
                diff = changes_victoria[folder]['diff']
                if diff > 0:
                    change_info = f" (+{diff})"
                elif diff < 0:
                    change_info = f" ({diff})"
            print(f"Pasta '{folder}': {pages} páginas{change_info}")
    
    if not folder_pages_normal and not folder_pages_victoria:
        print("Nenhuma pasta encontrada na raiz.")
    
    total_elapsed = time.time() - start_time
    print(f"\nTempo total de execução: {total_elapsed:.2f} segundos")
    
    # Send results to WhatsApp
    if folder_pages_normal or folder_pages_victoria:
        current_datetime = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        previous_timestamp = previous_data.get('timestamp') if previous_data else None
        message = format_whatsapp_message(
            folder_pages_normal, folder_pages_victoria, total_pages_before_victoria,
            changes_normal, changes_victoria, current_datetime, previous_timestamp
        )
        send_whatsapp_message(message)

if __name__ == "__main__":
    main()