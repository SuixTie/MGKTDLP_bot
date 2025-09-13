import sys
import os
import win32com.client
import pythoncom
import re

def extract_doc_to_txt(doc_path, txt_path):
    """
    Извлекает текст из Word файла (.doc) и сохраняет в TXT файл,
    сохраняя отступы и структуру параграфов как в оригинале.
    Удаляет лишние символы перед первым разделителем '│' в строках с колонками.
    """
    try:
        # Проверяем, существует ли входной файл
        if not os.path.exists(doc_path):
            raise FileNotFoundError(f"Файл {doc_path} не найден")
        if not (doc_path.endswith('.doc') or doc_path.endswith('.docx')):
            raise ValueError("Входной файл должен иметь расширение .doc или .docx")

        # Инициализируем COM для работы с Word
        pythoncom.CoInitialize()
        word = win32com.client.Dispatch('Word.Application')
        word.Visible = False  # Word не отображается
        doc = word.Documents.Open(os.path.abspath(doc_path))

        # Извлекаем текст из параграфов
        with open(txt_path, 'w', encoding='utf-8') as txt_file:
            # Проходим по всем параграфам
            for para in doc.Paragraphs:
                text = para.Range.Text.strip()
                # Проверяем, содержит ли строка разделители '│' (то есть это строка с колонками)
                if '│' in text:
                    # Удаляем любые символы перед первым '│'
                    text = re.sub(r'^[^│]*│', '│', text)
                txt_file.write(text + '\n')

            # Извлекаем текст из таблиц (если они есть)
            for table in doc.Tables:
                for row in table.Rows:
                    row_text = '\t'.join(cell.Range.Text.strip().replace('\r\x07', '') for cell in row.Cells)
                    txt_file.write(row_text + '\n')
                txt_file.write('\n')

        # Закрываем документ и Word
        doc.Close()
        word.Quit()
        pythoncom.CoUninitialize()

        print(f"Текст успешно извлечен из {doc_path} и сохранен в {txt_path}")

    except Exception as e:
        print(f"Ошибка при обработке {doc_path}: {e}")

def extract_all_schedules(input_dir="downloaded_schedules", output_dir="extracted_schedules"):
    """
    Извлекает текст из всех файлов расписания за неделю и сохраняет в отдельные TXT файлы.

    Args:
        input_dir (str): Директория с исходными .doc файлами (по умолчанию downloaded_schedules).
        output_dir (str): Директория для сохранения .txt файлов.
    """
    # Создаём выходную директорию, если её нет
    os.makedirs(output_dir, exist_ok=True)

    # Список файлов расписания
    schedule_files = [
        'rasp_monday.doc',
        'rasp_tuesday.doc',
        'rasp_wednesday.doc',
        'rasp_thursday.doc',
        'rasp_friday.doc',
        'rasp_saturday.doc'
    ]

    successful = 0
    failed = 0

    print(f"Начинаем обработку расписаний из директории: {input_dir}")
    print(f"Выходные файлы будут сохранены в: {output_dir}")
    print("-" * 50)

    for doc_file in schedule_files:
        doc_path = os.path.join(input_dir, doc_file)
        # Генерируем имя выходного файла, заменяя .doc на .txt
        txt_file = doc_file.replace('.doc', '.txt')
        txt_path = os.path.join(output_dir, txt_file)

        print(f"Обрабатываем: {doc_file} -> {txt_file}")
        try:
            extract_doc_to_txt(doc_path, txt_path)
            successful += 1
            print(f"✓ Успешно обработан: {doc_file}")
        except Exception as e:
            failed += 1
            print(f"✗ Ошибка при обработке {doc_file}: {e}")
        print()

    print("-" * 50)
    print(f"Обработка завершена: {successful} успешно, {failed} с ошибками")

if __name__ == "__main__":
    # Директория с .doc файлами (где лежат файлы из первой программы)
    input_directory = "downloaded_schedules"  # Изменено на папку downloaded_schedules
    output_directory = "extracted_schedules"  # Папка для .txt файлов

    # Если нужно указать другие директории, раскомментируй и измени:
    # input_directory = r"C:\Users\YourName\Documents\downloaded_schedules"
    # output_directory = r"C:\Users\YourName\Documents\extracted_schedules"

    extract_all_schedules(input_directory, output_directory)