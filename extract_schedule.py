import sys
import os
import re
import subprocess
from docx import Document
import docx2txt
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

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

        logging.info(f"Обработка файла: {doc_path}")
        text_lines = []

        if doc_path.endswith('.docx'):
            # Используем python-docx для .docx
            try:
                doc = Document(doc_path)
                logging.info(f"Открыт .docx файл: {doc_path}")
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
            except Exception as e:
                raise ValueError(f"Ошибка при обработке .docx файла {doc_path}: {e}")
        else:
            # Пробуем antiword для .doc
            try:
                result = subprocess.run(
                    ['antiword', doc_path],
                    capture_output=True,
                    text=True,
                    encoding='utf-8',
                    errors='replace'
                )
                logging.info(f"Открыт .doc файл через antiword: {doc_path}")
                text = result.stdout
                if result.stderr:
                    logging.warning(f"STDERR antiword: {result.stderr}")
                # Разделяем на строки и обрабатываем
                for line in text.splitlines():
                    line = line.strip()
                    if '│' in line:
                        line = re.sub(r'^[^│]*│', '│', line)
                    text_lines.append(line)
            except FileNotFoundError:
                logging.error("antiword не установлен. Пробуем docx2txt для .doc")
                try:
                    text = docx2txt.process(doc_path)
                    logging.info(f"Открыт .doc файл через docx2txt: {doc_path}")
                    for line in text.splitlines():
                        line = line.strip()
                        if '│' in line:
                            line = re.sub(r'^[^│]*│', '│', line)
                        text_lines.append(line)
                except Exception as e:
                    raise ValueError(f"Ошибка при обработке .doc файла {doc_path}: {e}")

        # Проверяем, есть ли содержимое
        if not text_lines or all(not line.strip() for line in text_lines):
            raise ValueError(f"Файл {doc_path} пуст или не содержит полезного текста")

        # Сохраняем в TXT файл
        os.makedirs(os.path.dirname(txt_path), exist_ok=True)
        with open(txt_path, 'w', encoding='utf-8') as txt_file:
            for line in text_lines:
                txt_file.write(line + '\n')
        logging.info(f"Текст успешно извлечён из {doc_path} и сохранён в {txt_path}")
        return True

    except Exception as e:
        logging.error(f"Ошибка при обработке {doc_path}: {e}")
        return False

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

    logging.info(f"Начинаем обработку расписаний из директории: {input_dir}")
    logging.info(f"Выходные файлы будут сохранены в: {output_dir}")
    logging.info(f"Файлы в {input_dir}: {os.listdir(input_dir) if os.path.exists(input_dir) else 'Папка не найдена'}")

    for doc_file in schedule_files:
        doc_path = os.path.join(input_dir, doc_file)
        txt_file = doc_file.replace('.doc', '.txt')
        txt_path = os.path.join(output_dir, txt_file)

        logging.info(f"Обрабатываем: {doc_file} -> {txt_file}")
        if extract_doc_to_txt(doc_path, txt_path):
            successful += 1
            logging.info(f"✓ Успешно обработан: {doc_file}")
        else:
            failed += 1
            logging.error(f"✗ Ошибка при обработке {doc_file}")
        logging.info("")

    logging.info(f"Обработка завершена: {successful} успешно, {failed} с ошибками")
    return successful, failed

if __name__ == "__main__":
    input_directory = "downloaded_schedules"
    output_directory = "extracted_schedules"
    extract_all_schedules(input_directory, output_directory)
