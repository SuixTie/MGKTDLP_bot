import requests
from bs4 import BeautifulSoup
import os
import re
from datetime import datetime


def download_schedules_from_site(site_url, output_folder="downloaded_schedules"):
    """
    Скачивает все доступные .doc или .docx файлы расписания с сайта и переименовывает их по реальному дню недели,
    определяя день недели по дате в имени файла.

    Args:
        site_url (str): URL страницы с расписаниями.
        output_folder (str): Папка для сохранения скачанных файлов.
    """
    # Создаём выходную папку, если её нет
    os.makedirs(output_folder, exist_ok=True)

    # Получаем содержимое страницы
    try:
        response = requests.get(site_url)
        response.raise_for_status()  # Проверяем на ошибки HTTP
    except requests.exceptions.RequestException as e:
        print(f"Ошибка при получении страницы: {e}")
        return

    # Парсим HTML страницы
    soup = BeautifulSoup(response.text, 'html.parser')

    # Находим все ссылки <a> на .doc или .docx файлы
    doc_links = []
    for link in soup.find_all('a'):
        href = link.get('href')
        if href and (href.endswith('.doc') or href.endswith('.docx')):
            # Полный URL, если относительный
            if not href.startswith('http'):
                href = requests.urljoin(site_url, href)

            # Извлекаем дату из имени файла (например, rasp08.09.25.doc)
            file_name = os.path.basename(href)
            date_match = re.search(r'(\d{2})\.(\d{2})\.(\d{2,4})', file_name)
            file_date = None
            if date_match:
                day, month, year = date_match.groups()
                year = f"20{year}" if len(year) == 2 else year  # Преобразуем 25 в 2025
                try:
                    file_date = datetime.strptime(f"{day}.{month}.{year}", "%d.%m.%Y")
                except ValueError:
                    print(f"Некорректная дата в имени файла: {file_name}")
            else:
                # Для файлов без полной даты (например, rasp09.09-.doc) пытаемся извлечь DD.MM
                date_match_short = re.search(r'(\d{2})\.(\d{2})', file_name)
                if date_match_short:
                    day, month = date_match_short.groups()
                    # Предполагаем текущий год для коротких дат
                    current_year = datetime.now().year
                    try:
                        file_date = datetime.strptime(f"{day}.{month}.{current_year}", "%d.%m.%Y")
                        print(f"  Использован текущий год {current_year} для {file_name}")
                    except ValueError:
                        print(f"Некорректная короткая дата в имени файла: {file_name}")

            doc_links.append((file_name, href, file_date))

            # Отладочная информация
            date_str = file_date.strftime('%d.%m.%Y') if file_date else 'Не указана'
            print(f"Найдена ссылка: {file_name} -> {href} (Дата: {date_str})")

    if not doc_links:
        print("Не найдено ссылок на .doc или .docx файлы на странице.")

        # Дополнительная отладка: выводим все ссылки на странице
        print("\nВсе ссылки на странице:")
        all_links = soup.find_all('a')
        for link in all_links:
            href = link.get('href')
            text = link.get_text().strip()
            if href:
                print(f"- {text}: {href}")

        return

    # Маппинг номеров дней недели к английским названиям
    day_mapping = {
        0: 'rasp_monday.doc',  # Понедельник
        1: 'rasp_tuesday.doc',  # Вторник
        2: 'rasp_wednesday.doc',  # Среда
        3: 'rasp_thursday.doc',  # Четверг
        4: 'rasp_friday.doc',  # Пятница
        5: 'rasp_saturday.doc'  # Суббота
    }

    successful = 0
    failed = 0

    print(f"\nНайдено {len(doc_links)} файлов для скачивания:")
    for file_name, file_url, file_date in doc_links:
        date_str = file_date.strftime('%d.%m.%Y') if file_date else 'Не указана'
        print(f"- {file_name}: {file_url} (Дата: {date_str})")

    # Присваиваем имена по реальному дню недели
    for original_file_name, file_url, file_date in doc_links:
        if not file_date:
            print(f"Пропущен файл {original_file_name}: не удалось извлечь дату")
            failed += 1
            continue

        # Определяем день недели по дате файла (0 = понедельник, 6 = воскресенье)
        weekday_num = file_date.weekday()

        # Проверяем, что это рабочий день (0-5, суббота = 5)
        if weekday_num > 5:  # Воскресенье
            print(f"Пропущен файл {original_file_name}: дата приходится на воскресенье")
            failed += 1
            continue

        # Получаем имя файла по дню недели
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

            # Проверяем размер ответа (чтобы убедиться, что это не HTML ошибка)
            content_size = len(file_response.content)
            print(f"  Размер ответа: {content_size} байт")

            if content_size < 1000:  # Если файл слишком маленький, вероятно, это HTML ошибка
                print(f"  ⚠️ Файл слишком маленький, возможно, ошибка 404 или редирект")
                print(f"  Содержимое (первые 200 символов): {file_response.content[:200]}")
            else:
                # Сохраняем файл
                with open(file_path, 'wb') as f:
                    f.write(file_response.content)
                successful += 1
                print(f"  ✓ Успешно скачано и сохранено как: {target_file_name}")

                # Проверяем, что файл не пустой
                if os.path.getsize(file_path) > 0:
                    print(f"  ✓ Размер сохранённого файла: {os.path.getsize(file_path)} байт")
                else:
                    print(f"  ❌ Сохранённый файл пустой!")
                    os.remove(file_path)  # Удаляем пустой файл
                    failed += 1
                    successful -= 1
        except requests.exceptions.RequestException as e:
            failed += 1
            print(f"  ✗ Ошибка при скачивании {file_url}: {e}")
        except Exception as e:
            failed += 1
            print(f"  ✗ Неожиданная ошибка: {e}")

        # Удаляем старые файлы для этого конкретного дня недели
        try:
            for existing_file in os.listdir(output_folder):
                if existing_file.endswith('.doc') or existing_file.endswith('.docx'):
                    if existing_file == target_file_name:
                        # Если это тот же файл, но с другой датой, удаляем только если размер меньше
                        old_file_path = os.path.join(output_folder, existing_file)
                        if os.path.exists(old_file_path):
                            old_size = os.path.getsize(old_file_path)
                            new_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0
                            if new_size > old_size:
                                os.remove(old_file_path)
                                print(f"  Удалён старый файл {existing_file} (размер {old_size} < {new_size})")
                            else:
                                print(f"  Старый файл {existing_file} сохранён (новый меньше)")
                    else:
                        # Удаляем другие файлы, если они не соответствуют текущему дню
                        continue
        except Exception as e:
            print(f"  Ошибка при удалении старых файлов: {e}")

    print(f"\nОбработка завершена: {successful} успешно скачано, {failed} ошибок")


if __name__ == "__main__":
    # URL страницы с расписаниями
    site_url = "http://coltechdis.by/obuchayushhimsya/raspisanie-zanyatij/"

    # Папка для сохранения скачанных файлов
    output_folder = "downloaded_schedules"

    # Если нужно изменить папку, раскомментируй и измени:
    # output_folder = r"C:\Users\YourName\Documents\Schedules"

    download_schedules_from_site(site_url, output_folder)