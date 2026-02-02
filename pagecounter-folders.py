import os
import time
import json
import subprocess
import argparse
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from PyPDF2 import PdfReader
import threading
import re
import hashlib

# Try to import fcntl (Unix only)
try:
    import fcntl
    HAS_FCNTL = True
except ImportError:
    HAS_FCNTL = False

def count_pdf_pages_fast(file_path):
    """
    Counts pages of a single PDF file in an optimized way
    """
    try:
        with open(file_path, "rb") as pdf_file:
            pdf_reader = PdfReader(pdf_file)
            return len(pdf_reader.pages)
    except Exception as e:
        print(f"Error processing {file_path}: {e}")
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
                log_message(f"Error reading config.json: {e}. Using default path.")
                root_directory = 'G:/My Drive/XABLAU/'
        else:
            root_directory = 'G:/My Drive/XABLAU/'
    
    log_message(f"📂 Pasta raiz configurada para contagem: {root_directory}")
    if not os.path.exists(root_directory):
        log_message(f"❌ Pasta raiz não existe: {root_directory}")
        return {}, {}

    folder_pages_normal = {}
    folder_pages_victoria = {}
    
    # List all folders in root that start with a digit
    root_folders = [
        item for item in os.listdir(root_directory)
        if os.path.isdir(os.path.join(root_directory, item)) and item[:1].isdigit()
    ]
    log_message(f"📁 Pastas detectadas para contagem: {len(root_folders)}")

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
                log_message(f"🔎 Iniciando contagem da pasta: {label} ({folder_path})")
                future = executor.submit(count_pages_in_directory_parallel, folder_path)
                future_to_label[future] = label
            
            # Collect results
            for future in as_completed(future_to_label):
                label = future_to_label[future]
                try:
                    pages = future.result()
                    folder_pages_normal[label] = pages
                    log_message(f"✅ Contagem concluída: {label} -> {pages} páginas")
                except Exception as e:
                    log_message(f"Error processing folder {label}: {e}")
                    folder_pages_normal[label] = 0
    
    # Process VICTORIA folders in parallel
    if targets_victoria:
        with ThreadPoolExecutor(max_workers=min(len(targets_victoria), 4)) as executor:
            future_to_label = {}
            
            for label, folder_path in targets_victoria:
                log_message(f"🔎 Iniciando contagem da pasta VICTORIA: {label} ({folder_path})")
                future = executor.submit(count_pages_in_directory_parallel, folder_path)
                future_to_label[future] = label
            
            # Collect results
            for future in as_completed(future_to_label):
                label = future_to_label[future]
                try:
                    pages = future.result()
                    folder_pages_victoria[label] = pages
                    log_message(f"✅ Contagem VICTORIA concluída: {label} -> {pages} páginas")
                except Exception as e:
                    log_message(f"Error processing folder {label}: {e}")
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

def get_lock_file_path():
    """
    Returns the lock file path to prevent concurrent executions
    """
    script_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(script_dir, '.pagecounter.lock')

def get_last_message_file_path():
    """
    Returns the path to store the last sent message hash
    """
    script_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(script_dir, '.last_message.json')

def get_log_file_path():
    """
    Returns the path for the execution log file
    """
    script_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(script_dir, 'pagecounter.log')

def log_message(message):
    """
    Appends a timestamped line to the log file and prints it
    """
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"[{timestamp}] {message}"
        print(message)
        with open(get_log_file_path(), 'a', encoding='utf-8') as f:
            f.write(line + "\n")
    except Exception as e:
        # Fallback to console only if logging fails
        print(f"Logging failed: {e}")

def acquire_lock():
    """
    Acquires a lock file to prevent concurrent script executions
    Returns lock file handle or None if already locked
    """
    lock_path = get_lock_file_path()
    
    # Check if lock file already exists
    if os.path.exists(lock_path):
        try:
            # Check if the process is still running
            with open(lock_path, 'r') as f:
                pid = f.read().strip()
                # On Windows, we can't easily check if process exists, so we'll just warn
                # On Unix, we can check if process is still running
                if HAS_FCNTL:
                    try:
                        os.kill(int(pid), 0)  # Check if process exists
                        print(f"⚠️ Script already running (PID: {pid}). Skipping execution.")
                        return None
                    except (OSError, ValueError):
                        # Process doesn't exist, remove stale lock
                        os.remove(lock_path)
                else:
                    # Windows: check if file is recent (less than 5 minutes old)
                    file_age = time.time() - os.path.getmtime(lock_path)
                    if file_age < 300:  # 5 minutes
                        print(f"⚠️ Script may be running (lock file exists). Skipping execution.")
                        return None
                    else:
                        # Stale lock, remove it
                        os.remove(lock_path)
        except:
            # If we can't read it, try to remove and continue
            try:
                os.remove(lock_path)
            except:
                pass
    
    try:
        # Create lock file
        lock_file = open(lock_path, 'w')
        lock_file.write(str(os.getpid()))
        lock_file.flush()
        
        # On Unix, try to acquire exclusive lock
        if HAS_FCNTL:
            try:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except (IOError, OSError):
                lock_file.close()
                print("⚠️ Could not acquire lock. Script may already be running.")
                return None
        
        return lock_file
    except (IOError, OSError) as e:
        print(f"⚠️ Could not create lock file: {e}")
        return None

def release_lock(lock_file):
    """
    Releases the lock file
    """
    if lock_file:
        try:
            lock_file.close()
            lock_path = get_lock_file_path()
            if os.path.exists(lock_path):
                os.remove(lock_path)
        except:
            pass

def get_message_hash(message):
    """
    Returns a hash of the message content (excluding timestamp)
    """
    # Remove timestamp from message for comparison
    lines = message.split('\n')
    # Remove lines with timestamp
    filtered_lines = [line for line in lines if '🕒' not in line and 'Data/Hora' not in line]
    message_content = '\n'.join(filtered_lines)
    return hashlib.md5(message_content.encode('utf-8')).hexdigest()

def should_send_message(message, min_cooldown_seconds=None):
    """
    Checks if message should be sent based on cooldown and content
    Returns (should_send, reason)
    """
    # Load cooldown from config if not provided
    if min_cooldown_seconds is None:
        config_path = os.path.join(os.path.dirname(__file__), 'config.json')
        try:
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    min_cooldown_seconds = config.get('message', {}).get('min_cooldown_seconds', 60)
            else:
                min_cooldown_seconds = 60
        except:
            min_cooldown_seconds = 60
    last_message_path = get_last_message_file_path()
    
    if not os.path.exists(last_message_path):
        return True, "First message"
    
    try:
        with open(last_message_path, 'r', encoding='utf-8') as f:
            last_data = json.load(f)
        
        last_hash = last_data.get('hash')
        last_timestamp = last_data.get('timestamp')
        current_hash = get_message_hash(message)
        
        # Check if message content is the same
        if last_hash == current_hash:
            return False, "Message identical to last sent"
        
        # Check cooldown
        if last_timestamp:
            try:
                last_dt = datetime.fromisoformat(last_timestamp)
                elapsed = (datetime.now() - last_dt).total_seconds()
                if elapsed < min_cooldown_seconds:
                    remaining = int(min_cooldown_seconds - elapsed)
                    return False, f"Cooldown active ({remaining}s remaining)"
            except:
                pass
        
        return True, "Message differs and cooldown passed"
    except Exception as e:
        # If we can't read the file, allow sending
        return True, f"Could not check last message: {e}"

def save_last_message(message):
    """
    Saves the hash and timestamp of the last sent message
    """
    last_message_path = get_last_message_file_path()
    try:
        data = {
            'hash': get_message_hash(message),
            'timestamp': datetime.now().isoformat()
        }
        with open(last_message_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"Warning: Could not save last message info: {e}")

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
    
    # Normal folders (if any)
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
    
    # VICTORIA folders (already processed)
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

def send_whatsapp_message(message, check_cooldown=True, force=False):
    """
    Sends message via WhatsApp using the Node.js script
    check_cooldown: If True, checks cooldown and message content before sending
    force: If True, ignores cooldown and duplicate message checks (for testing)
    """
    # Check if we should send the message
    if check_cooldown and not force:
        should_send, reason = should_send_message(message)
        if not should_send:
            log_message(f"⏭️ Skipping WhatsApp message: {reason}")
            return False
        else:
            log_message(f"✅ Mensagem liberada para envio: {reason}")
    elif force:
        log_message("🔧 Modo FORCE ativado: ignorando verificação de cooldown e mensagem repetida")
    
    try:
        # Read config to check if WhatsApp is enabled
        config_path = os.path.join(os.path.dirname(__file__), 'config.json')
        if not os.path.exists(config_path):
            log_message("config.json file not found. Skipping WhatsApp sending.")
            return False
        
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        if not config.get('whatsapp', {}).get('enabled', False):
            log_message("WhatsApp sending disabled in config.json")
            return False
        
        whatsapp_cfg = config.get('whatsapp', {})
        log_message(f"📨 Destino WhatsApp: tipo={whatsapp_cfg.get('type')} alvo={whatsapp_cfg.get('target')}")
        
        # Get timeout from config (in milliseconds, convert to seconds)
        # Add extra time for initialization (60s) + message timeout + buffer (30s)
        message_timeout_ms = config.get('message', {}).get('timeout', 30000)
        message_timeout_seconds = message_timeout_ms / 1000
        # Total timeout: initialization (60s) + message timeout + ACK wait (20s) + buffer (30s)
        total_timeout = 60 + message_timeout_seconds + 20 + 30
        log_message(f"⏱️ Timeout configurado: {total_timeout:.0f}s (inicialização: 60s + mensagem: {message_timeout_seconds:.0f}s + ACK: 20s + buffer: 30s)")
        
        # Get path to Node.js script
        script_dir = os.path.dirname(os.path.abspath(__file__))
        node_script = os.path.join(script_dir, 'whatsapp-sender.js')
        
        if not os.path.exists(node_script):
            print(f"whatsapp-sender.js script not found in {script_dir}")
            return False
        
        # Call Node.js script with message as argument
        # For Windows compatibility, pass message directly as list item
        log_message("Enviando resultados para WhatsApp...")
        log_message(f"ℹ️ Tamanho da mensagem: {len(message)} caracteres")
        
        # Pass message as separate argument to avoid shell escaping issues
        cmd = ['node', node_script, message]

        # Evita abrir janela do Node no Windows quando rodando em background
        creationflags = 0
        if os.name == 'nt':
            creationflags = subprocess.CREATE_NO_WINDOW
        
        start_time = time.time()
        try:
            result = subprocess.run(
                cmd,
                cwd=script_dir,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                timeout=total_timeout,
                creationflags=creationflags
            )
            elapsed_time = time.time() - start_time
            log_message(f"⏱️ Tempo de execução do WhatsApp: {elapsed_time:.2f}s")
        except subprocess.TimeoutExpired as e:
            elapsed_time = time.time() - start_time
            log_message(f"❌ Timeout ao enviar mensagem WhatsApp após {elapsed_time:.2f}s (limite: {total_timeout:.0f}s)")
            log_message("⚠️ Possíveis causas: WhatsApp Web desconectado, necessidade de reautenticação, ou conexão lenta")
            return False
        
        if result.returncode == 0:
            log_message("✅ Message sent successfully to WhatsApp!")
            if result.stdout:
                log_message(f"ℹ️ Saída do envio: {result.stdout.strip()}")
            # Save last message info
            save_last_message(message)
            return True
        else:
            log_message(f"❌ Error sending message (código: {result.returncode})")
            if result.stderr:
                log_message(f"❌ Erro: {result.stderr.strip()}")
            if result.stdout:
                log_message(f"ℹ️ Saída do script: {result.stdout.strip()}")
            return False
            
    except FileNotFoundError:
        log_message("❌ Node.js not found. Make sure Node.js is installed.")
        return False
    except Exception as e:
        log_message(f"❌ Error sending WhatsApp message: {e}")
        return False

def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description='Count PDF pages in folders and send results via WhatsApp'
    )
    parser.add_argument(
        '--force',
        action='store_true',
        help='Force send WhatsApp message even if it\'s a duplicate or cooldown is active (for testing)'
    )
    args = parser.parse_args()
    
    # Acquire lock to prevent concurrent executions
    lock_file = acquire_lock()
    if not lock_file:
        return
    
    try:
        start_time = time.time()
        
        log_message("Starting page count...")
        if args.force:
            log_message("🔧 Modo FORCE ativado via linha de comando")
        print("="*50)
        
        # Load previous results for comparison
        previous_data = load_previous_results()
        
        # Optimized folder counting (returns separated: normal and VICTORIA)
        folder_pages_normal, folder_pages_victoria = count_pages_by_folder_optimized()
        
        # Calculate total before VICTORIA folders (sum of normal folders)
        total_pages_before_victoria = sum(folder_pages_normal.values())
        
        # Calculate changes since last reading
        changes_normal, changes_victoria = calculate_changes(
            folder_pages_normal, folder_pages_victoria, previous_data
        )
        
        # Save current results for next comparison
        save_current_results(folder_pages_normal, folder_pages_victoria, total_pages_before_victoria)
        
        # Show total before VICTORIA folders
        print(f"\n📈 *Total:* {total_pages_before_victoria} páginas")
        print("="*50)
        
        # Show changes since last reading
        if changes_normal or changes_victoria:
            print("\n📊 *Mudanças desde a última leitura:*")
            
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
        
        # Show normal folders
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
        
        # Show VICTORIA folders (already processed)
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
            print("No folders found in root.")
        
        total_elapsed = time.time() - start_time
        print(f"\nTotal execution time: {total_elapsed:.2f} seconds")
        
        # Send results to WhatsApp only if there are changes or it's the first run
        if folder_pages_normal or folder_pages_victoria:
            # Only send if there are actual changes, it's the first execution, or force flag is set
            if changes_normal or changes_victoria or not previous_data or args.force:
                current_datetime = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                previous_timestamp = previous_data.get('timestamp') if previous_data else None
                message = format_whatsapp_message(
                    folder_pages_normal, folder_pages_victoria, total_pages_before_victoria,
                    changes_normal, changes_victoria, current_datetime, previous_timestamp
                )
                send_whatsapp_message(message, force=args.force)
            else:
                print("\n⏭️ No changes detected. Skipping WhatsApp message.")
                if args.force:
                    print("💡 Dica: Use --force para enviar mesmo sem mudanças")
    finally:
        # Always release lock
        release_lock(lock_file)

if __name__ == "__main__":
    main()