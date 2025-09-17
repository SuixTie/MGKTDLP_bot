import requests
from bs4 import BeautifulSoup
import os
import re
from datetime import datetime
import subprocess  # Для конвертации

def is_file_locked(file_path):
    if not os.path.exists(file_path):
        return False
    try:
        with open(file_path, 'a'):
            return False
    except (IOError, PermissionError):
        return True

def remove_file_safely(file_path):
    temp_file = file_path.replace('.doc', '~$temp.doc').replace('.docx', '~$temp.docx')
    for f in [file_path, temp_file]:
        if os.path.exists(f):
            try:
                os.remove(f)
                print(f"  Удалён: {os.path.basename(f)}")
            except (OSError, PermissionError):
                print(f"  Не удалось удалить {os.path.basename(f)}")

def convert_doc_to_txt(doc_path, txt_path):
    """
    Конвертирует .doc в .txt с помощью antiword (лучше сохраняет структуру таблицы).
    """
    try:
        subprocess.run(['antiword', '-i', '1', doc_path, '-o', txt_path], check=True, capture_output=True)
        print(f"  ✓ Конвертировано .doc в .txt: {os.path.basename(txt_path)}")
        # Проверяем на переносы: объединяем строки, если нужно
        with open(txt_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        with open(txt_path, 'w', encoding='utf-8') as f:
            current_line = ''
            for line in lines:
                if line.strip() and line.startswith('│') and current_line and current_line.endswith('│'):
                    current_line += line.strip()[1:]  # Объединяем ячейки
                else:
                    if current_line:
                        f.write(current_line + '\n')
                    current_line = line.strip()
            if current_line:
                f.write(current_line + '\n')
        print(f"  ✓ Объединены переносы строк в {os.path.basename(txt_path)}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"  ✗ Ошибка конвертации: {e}")
        return False
    except FileNotFoundError:
        print("  ✗ antiword не установлен. Установите: apt install antiword")
        return False

def download_schedules_from_site(site_url, output_folder="downloaded_schedules"):
    os.makedirs(output_folder, exist_ok=True)
    try:
        response = requests.get(site_url)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"Ошибка при получении страницы: {e}")
        return

    soup = BeautifulSoup(response.text, 'html.parser')
    doc_links = []
    for link in soup.find_all('a'):
        href = link.get('href')
        if href and (href.endswith('.doc') or href.endswith('.docx')):
            if not href.startswith('http'):
                href = requests.urljoin(site_url, href)
            file_name = os.path.basename(href)
            date_match = re.search(r'(\d{2})\.(\d{2})\.(\d{2,4})', file_name)
            file_date = None
            if date_match:
                day, month, year = date_match.groups()
                year = f"20{year}" if len(year) == 2 else year
                try:
                    file_date = datetime.strptime(f"{day}.{month}.{year}", "%d.%m.%Y")
                except ValueError:
                    print(f"Некорректная дата: {file_name}")
            doc_links.append((file_name, href, file_date))
            date_str = file_date.strftime('%d.%m.%Y') if file_date else 'Не указана'
            print(f"Найдена ссылка: {file_name} -> {href} (Дата: {date_str})")

    if not doc_links:
        print("Не найдено .doc/.docx файлов.")
        return

    day_mapping = {
        0: 'rasp_monday.txt',  # Изменено на .txt
        1: 'rasp_tuesday.txt',
        2: 'rasp_wednesday.txt',
        3: 'rasp_thursday.txt',
        4: 'rasp_friday.txt',
        5: 'rasp_saturday.txt'
    }

    successful = 0
    failed = 0
    print(f"\nНайдено {len(doc_links)} файлов:")
    for file_name, file_url, file_date in doc_links:
        date_str = file_date.strftime('%d.%m.%Y') if file_date else 'Не указана'
        print(f"- {file_name}: {date_str}")

    for original_file_name, file_url, file_date in doc_links:
        if not file_date:
            print(f"Пропущен {original_file_name}: нет даты")
            failed += 1
            continue

        weekday_num = file_date.weekday()
        if weekday_num > 5:
            print(f"Пропущен {original_file_name}: воскресенье")
            failed += 1
            continue

        target_txt_name = day_mapping[weekday_num]
        doc_path = os.path.join(output_folder, original_file_name)
        txt_path = os.path.join(output_folder, target_txt_name)

        print(f"\nСкачиваем {original_file_name}:")
        try:
            file_response = requests.get(file_url)
            file_response.raise_for_status()
            content_size = len(file_response.content)
            print(f"  Размер: {content_size} байт")

            if content_size < 1000:
                print(f"  ⚠️ Файл слишком маленький")
                failed += 1
                continue

            # Сохраняем .doc
            with open(doc_path, 'wb') as f:
                f.write(file_response.content)
            print(f"  ✓ Скачан .doc: {original_file_name}")

            # Конвертируем в .txt
            if convert_doc_to_txt(doc_path, txt_path):
                successful += 1
            else:
                failed += 1

            # Удаляем .doc после конвертации
            remove_file_safely(doc_path)

        except Exception as e:
            print(f"  ✗ Ошибка: {e}")
            failed += 1

    print(f"\nЗавершено: {successful} успешно, {failed} ошибок")

if __name__ == "__main__":
    site_url = "http://coltechdis.by/obuchayushhimsya/raspisanie-zanyatij/"
    output_folder = "downloaded_schedules"
    download_schedules_from_site(site_url, output_folder)
