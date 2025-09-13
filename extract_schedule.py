import sys
import os
import re
from docx import Document
import docx2txt

def extract_doc_to_txt(doc_path, txt_path):
    """
    Извлекает текст из Word файла (.doc или .docx) и сохраняет в TXT файл,
    сохраняя отступы и структуру параграфов как в оригинале.
    Удаляет лишние символы перед первым разделителем '│' в строках с колонками.
    """
    try:
        # Проверяем, существует ли входной файл
        if not os.path.exists(doc_path):
            raise FileNotFoundError(f"Файл {doc_path} не найден")
        if not (doc_path.endswith('.doc') or doc_path.endswith('.docx')):
            raise ValueError("Входной файл должен иметь расширение .doc или .docx")

        # Инициализируем текст для записи
        text_lines = []

        if doc_path.endswith('.docx'):
            # Используем python-docx для .docx
            doc = Document(doc_path)
            # Извлекаем текст из параграфов
            for para in doc.paragraphs:
                text = para.text.strip()
                if '│' in text:
                    text = re.sub(r'^[^│]*│', '│', text)
                text_lines.append(text)

            # Извлекаем текст из таблиц
            for table in doc.tables:
                for row in table.rows:
                    row_text = '\t'.join(cell.text.strip() for cell in row.cells)
                    text_lines.append(row_text)
                text_lines.append('')
        else:
            # Используем docx2txt для .doc
            text = docx2txt.process(doc_path)
            # Разделяем на строки и обрабатываем
            for line in text.splitlines():
                line = line.strip()
                if '│' in line:
                    line = re.sub(r'^[^│]*│', '│', line)
                text_lines.append(line)

        # Сохраняем в TXT файл
        with open(txt_path, 'w', encoding='utf-8') as txt_file:
            for line in text_lines:
                if line:  # Пропускаем пустые строки, если не нужны
                    txt_file.write(line + '\n')

        print(f"Текст успешно извлечён из {doc_path} и сохранён в {txt_path}")

    except Exception as e:
        print(f"Ошибка при обработке {doc_path}: {e}")

def extract_all_schedules(input_dir="downloaded_schedules", output_dir="extracted_schedules"):
    """
    Извлекает текст из всех файлов расписания за неделю и сохраняет в отдельные TXT файлы.

    Args:
        input_dir (str): Директория с исходными .doc файлами.
        output_dir (str): Директория для сохранения .txt файлов.
    """
    os.makedirs(output_dir, exist_ok=True)

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
    input_directory = "downloaded_schedules"
    output_directory = "extracted_schedules"
    extract_all_schedules(input_directory, output_directory)
