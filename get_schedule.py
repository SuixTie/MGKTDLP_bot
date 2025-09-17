import requests
from bs4 import BeautifulSoup
import os
import re
from datetime import datetime
import time  # Для пауз в retry


def is_file_locked(file_path):
    """
    Проверяет, заблокирован ли файл (например, открыт в Word).
    Возвращает True, если файл заблокирован.
    """
    if not os.path.exists(file_path):
        return False
    try:
        # Пытаемся открыть в режиме 'a' (append) — если заблокирован, выдаст PermissionError
        with open(file_path, 'a'):
            return False
    except (IOError, PermissionError):
        return True


def remove_file_safely(file_path):
    """
    Безопасно удаляет файл, если возможно (игнорирует ошибки).
    Также удаляет возможный временный файл Word (~$...).
    """
    temp_file = file_path.replace('.doc', '~$temp.doc').replace('.docx', '~$temp.docx')  # Примерный шаблон
    for f in [file_path, temp_file]:
        if os.path.exists(f):
            try:
                os.remove(f)
                print(f"  Удалён потенциально заблокированный файл: {os.path.basename(f)}")
            except (OSError, PermissionError):
                print(f"  Не удалось удалить {os.path.basename(f)} — возможно, открыт в программе")


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
                failed += 1
                continue
            else:
                # Retry-механизм для записи файла
                max_retries = 3
                success = False
                for attempt in range(max_retries):
                    try:
                        # Проверяем блокировку перед записью
                        if os.path.exists(file_path) and is_file_locked(file_path):
                            print(f"  Файл {target_file_name} заблокирован (возможно, открыт в Word). Удаляем...")
                            remove_file_safely(file_path)
                            time.sleep(1)  # Пауза 1 сек для антивируса

                        # Сохраняем файл
                        with open(file_path, 'wb') as f:
                            f.write(file_response.content)

                        # Проверяем, что файл не пустой
                        saved_size = os.path.getsize(file_path)
                        if saved_size > 0:
                            print(f"  ✓ Успешно скачано и сохранено как: {target_file_name}")
                            print(f"  ✓ Размер сохранённого файла: {saved_size} байт")
                            successful += 1
                            success = True
                            break  # Успех, выходим из retry
                        else:
                            print(f"  ❌ Сохранённый файл пустой!")
                            os.remove(file_path)  # Удаляем пустой файл
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
                    continue  # Если retry не удался, переходим к следующему файлу

        except requests.exceptions.RequestException as e:
            failed += 1
            print(f"  ✗ Ошибка при скачивании {file_url}: {e}")
        except Exception as e:
            failed += 1
            print(f"  ✗ Неожиданная ошибка: {e}")

        # Удаляем старые файлы для этого конкретного дня недели (только если новый сохранён успешно)
        if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
            try:
                print(f"  Обновлён файл {target_file_name}")
            except Exception as e:
                print(f"  Ошибка при обновлении файлов: {e}")

    print(f"\nОбработка завершена: {successful} успешно скачано, {failed} ошибок")


if __name__ == "__main__":
    # URL страницы с расписаниями
    site_url = "http://coltechdis.by/obuchayushhimsya/raspisanie-zanyatij/"

    # Папка для сохранения скачанных файлов
    output_folder = "downloaded_schedules"

    # Если нужно изменить папку, раскомментируй и измени:
    # output_folder = r"C:\Users\YourName\Documents\Schedules"

    download_schedules_from_site(site_url, output_folder)
