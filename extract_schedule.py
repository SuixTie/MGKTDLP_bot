import sys
import os
import re
import subprocess
from docx import Document
import docx2txt
import logging

# Настройка логирования
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

def extract_doc_to_txt(doc_path, txt_path):
    """
    Извлекает текст из Word файла (.doc или .docx) и сохраняет в TXT файл,
    сохраняя структуру таблиц и обрабатывая отступы.
    """
    try:
        if not os.path.exists(doc_path):
            raise FileNotFoundError(f"Файл {doc_path} не найден")
        if not (doc_path.endswith('.doc') or doc_path.endswith('.docx')):
            raise ValueError("Входной файл должен иметь расширение .doc или .docx")

        logging.info(f"Обработка файла: {doc_path}")
        text_lines = []

        if doc_path.endswith('.docx'):
            try:
                doc = Document(doc_path)
                logging.info(f"Открыт .docx файл: {doc_path}")
                # Извлекаем текст из параграфов
                for para in doc.paragraphs:
                    text = para.text.strip()
                    if text:
                        text_lines.append(text)
                        logging.debug(f"Извлечен параграф: {text}")

                # Извлекаем текст из таблиц
                for table in doc.tables:
                    max_columns = max(len(row.cells) for row in table.rows)
                    logging.debug(f"Обработка таблицы с {max_columns} столбцами")
                    for row in table.rows:
                        cells = [cell.text.strip().replace('\n', ' ') for cell in row.cells]
                        while len(cells) < max_columns:
                            cells.append('')
                        row_text = '│' + '│'.join(cells) + '│'
                        text_lines.append(row_text)
                        logging.debug(f"Извлечена строка таблицы: {row_text}")
                    text_lines.append('')
            except Exception as e:
                logging.error(f"Ошибка при обработке .docx файла {doc_path}: {e}")
                raise
        else:
            # Обработка .doc файлов через docx2txt
            try:
                text = docx2txt.process(doc_path)
                logging.info(f"Открыт .doc файл через docx2txt: {doc_path}")
                lines = text.splitlines()
                current_table = []
                max_columns = 0

                for line in lines:
                    line = line.strip()
                    if not line:
                        if current_table:
                            for row in current_table:
                                cells = row.split('│')[1:-1] if '│' in row else row.split()
                                while len(cells) < max_columns:
                                    cells.append('')
                                row_text = '│' + '│'.join(cells) + '│'
                                text_lines.append(row_text)
                                logging.debug(f"Извлечена строка таблицы (.doc): {row_text}")
                            text_lines.append('')
                            current_table = []
                            max_columns = 0
                        continue
                    if '│' in line:
                        line = re.sub(r'^[^│]*│', '│', line)
                        cells = line.split('│')[1:-1]
                        max_columns = max(max_columns, len(cells))
                        current_table.append(line)
                    else:
                        text_lines.append(line)
                        logging.debug(f"Извлечен текст (.doc): {line}")
                if current_table:
                    for row in current_table:
                        cells = row.split('│')[1:-1]
                        while len(cells) < max_columns:
                            cells.append('')
                        row_text = '│' + '│'.join(cells) + '│'
                        text_lines.append(row_text)
                        logging.debug(f"Извлечена строка таблицы (.doc): {row_text}")
            except Exception as e:
                logging.error(f"Ошибка при обработке .doc файла {doc_path}: {e}")
                raise

        if not text_lines or all(not line.strip() for line in text_lines):
            logging.warning(f"Файл {doc_path} пуст или не содержит полезного текста")
            return False

        # Сохраняем в TXT файл
        os.makedirs(os.path.dirname(txt_path), exist_ok=True)
        with open(txt_path, 'w', encoding='utf-8') as txt_file:
            for line in text_lines:
                txt_file.write(line + '\n')
        logging.info(f"Текст успешно извлечён из {doc_path} и сохранён в {txt_path}")

        # Проверяем содержимое файла
        if os.path.exists(txt_path):
            with open(txt_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                logging.info(f"Содержимое файла {txt_path} ({len(lines)} строк):")
                for i, line in enumerate(lines, 1):
                    logging.debug(f"Строка {i}: {line.strip()}")
            return True
        else:
            logging.error(f"Файл {txt_path} не был создан")
            return False

    except Exception as e:
        logging.error(f"Ошибка при обработке {doc_path}: {e}")
        return False

def main():
    """Основная функция для обработки всех .doc файлов в downloaded_schedules."""
    downloaded_dir = "downloaded_schedules"
    extracted_dir = "extracted_schedules"
    os.makedirs(extracted_dir, exist_ok=True)

    logging.info(f"Сканируем папку {downloaded_dir} на наличие .doc файлов")
    doc_files = [f for f in os.listdir(downloaded_dir) if f.endswith(('.doc', '.docx'))]
    logging.info(f"Найдено {len(doc_files)} файлов: {doc_files}")

    success_count = 0
    error_count = 0

    for doc_file in doc_files:
        doc_path = os.path.join(downloaded_dir, doc_file)
        txt_file = doc_file.replace('.docx', '.txt').replace('.doc', '.txt')
        txt_path = os.path.join(extracted_dir, txt_file)
        logging.info(f"Обрабатываем {doc_path} -> {txt_path}")
        if extract_doc_to_txt(doc_path, txt_path):
            success_count += 1
        else:
            error_count += 1

    logging.info(f"Обработка завершена: {success_count} успешно, {error_count} ошибок")
    if error_count > 0:
        sys.exit(1)

if __name__ == "__main__":
    main()
