import requests
from bs4 import BeautifulSoup
import os
import re
from datetime import datetime
import time


def is_file_locked(file_path):
    if not os.path.exists(file_path):
        return False
    try:
        with open(file_path, 'a'):
            return False
    except (IOError, PermissionError):
        return True


def remove_file_safely(file_path):
    temp_file = file_path.replace('.doc', '~$temp.doc').replace('.docx', '~$temp.docx')  # Примерный шаблон
    for f in [file_path, temp_file]:
        if os.path.exists(f):
            try:
                os.remove(f)
                print(f"  Удалён потенциально заблокированный файл: {os.path.basename(f)}")
            except (OSError, PermissionError):
                print(f"  Не удалось удалить {os.path.basename(f)} — возможно, открыт в программе")


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
                    print(f"Некорректная дата в имени файла: {file_name}")
            else:
                date_match_short = re.search(r'(\d{2})\.(\d{2})', file_name)
                if date_match_short:
                    day, month = date_match_short.groups()
                    current_year = datetime.now().year
                    try:
                        file_date = datetime.strptime(f"{day}.{month}.{current_year}", "%d.%m.%Y")
                        print(f"  Использован текущий год {current_year} для {file_name}")
                    except ValueError:
                        print(f"Некорректная короткая дата в имени файла: {file_name}")

            doc_links.append((file_name, href, file_date))

            date_str = file_date.strftime('%d.%m.%Y') if file_date else 'Не указана'
            print(f"Найдена ссылка: {file_name} -> {href} (Дата: {date_str})")

    if not doc_links:
        print("Не найдено ссылок на .doc или .docx файлы на странице.")

        print("\nВсе ссылки на странице:")
        all_links = soup.find_all('a')
        for link in all_links:
            href = link.get('href')
            text = link.get_text().strip()
            if href:
                print(f"- {text}: {href}")

        return

    day_mapping = {
        0: 'rasp_monday.doc',
        1: 'rasp_tuesday.doc',
        2: 'rasp_wednesday.doc',
        3: 'rasp_thursday.doc',
        4: 'rasp_friday.doc',
        5: 'rasp_saturday.doc'
    }

    successful = 0
    failed = 0

    print(f"\nНайдено {len(doc_links)} файлов для скачивания:")
    for file_name, file_url, file_date in doc_links:
        date_str = file_date.strftime('%d.%m.%Y') if file_date else 'Не указана'
        print(f"- {file_name}: {file_url} (Дата: {date_str})")

    for original_file_name, file_url, file_date in doc_links:
        if not file_date:
            print(f"Пропущен файл {original_file_name}: не удалось извлечь дату")
            failed += 1
            continue

        weekday_num = file_date.weekday()

        if weekday_num > 5:
            print(f"Пропущен файл {original_file_name}: дата приходится на воскресенье")
            failed += 1
            continue

        target_file_name = day_mapping[weekday_num]
        file_path = os.path.join(output_folder, target_file_name)

        print(f"\nСкачиваем файл:")
        print(f"  Исходный: {original_file_name}")
        print(f"  Дата: {file_date.strftime('%d.%m.%Y')}")
        print(f"  День недели: {file_date.strftime('%A')} ({weekday_num})")
        print(f"  URL: {file_url}")
        print(f"  Целевое имя: {target_file_name}")
        print(f"  Целевой путь: {file_path}")

        try:
            file_response = requests.get(file_url)
            file_response.raise_for_status()

            content_size = len(file_response.content)
            print(f"  Размер ответа: {content_size} байт")

            if content_size < 1000:
                print(f"  ⚠️ Файл слишком маленький, возможно, ошибка 404 или редирект")
                print(f"  Содержимое (первые 200 символов): {file_response.content[:200]}")
                failed += 1
                continue
            else:
                max_retries = 3
                success = False
                for attempt in range(max_retries):
                    try:
                        if os.path.exists(file_path) and is_file_locked(file_path):
                            print(f"  Файл {target_file_name} заблокирован (возможно, открыт в Word). Удаляем...")
                            remove_file_safely(file_path)
                            time.sleep(1)

                        with open(file_path, 'wb') as f:
                            f.write(file_response.content)

                        saved_size = os.path.getsize(file_path)
                        if saved_size > 0:
                            print(f"  ✓ Успешно скачано и сохранено как: {target_file_name}")
                            print(f"  ✓ Размер сохранённого файла: {saved_size} байт")
                            successful += 1
                            success = True
                            break
                        else:
                            print(f"  ❌ Сохранённый файл пустой!")
                            os.remove(file_path)
                            raise ValueError("Пустой файл после записи")

                    except (PermissionError, IOError) as e:
                        print(f"  Попытка {attempt + 1}/{max_retries} неудачна: {e}")
                        if attempt < max_retries - 1:
                            print(f"  Пробуем снова через 2 секунды...")
                            remove_file_safely(file_path)
                            time.sleep(2)
                        else:
                            print(f"  Все попытки исчерпаны. Файл не сохранён.")
                            failed += 1
                            break
                    except Exception as e:
                        print(f"  Неожиданная ошибка при записи: {e}")
                        failed += 1
                        break

                if not success:
                    continue

        except requests.exceptions.RequestException as e:
            failed += 1
            print(f"  ✗ Ошибка при скачивании {file_url}: {e}")
        except Exception as e:
            failed += 1
            print(f"  ✗ Неожиданная ошибка: {e}")

        if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
            try:
                print(f"  Обновлён файл {target_file_name}")
            except Exception as e:
                print(f"  Ошибка при обновлении файлов: {e}")

    print(f"\nОбработка завершена: {successful} успешно скачано, {failed} ошибок")


if __name__ == "__main__":
    site_url = "http://coltechdis.by/obuchayushhimsya/raspisanie-zanyatij/"
    output_folder = "downloaded_schedules"
    download_schedules_from_site(site_url, output_folder)
