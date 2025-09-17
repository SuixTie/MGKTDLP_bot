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
                # Извлекаем текст из параграфов (заголовки, например, "СКОРРЕКТИРОВАННОЕ РАСПИСАНИЕ")
                for para in doc.paragraphs:
                    text = para.text.strip()
                    if text:
                        text_lines.append(text)
                        logging.debug(f"Извлечен параграф: {text}")

                # Извлекаем текст из таблиц
                for table in doc.tables:
                    # Определяем максимальное количество столбцов
                    max_columns = max(len(row.cells) for row in table.rows)
                    logging.debug(f"Обработка таблицы с {max_columns} столбцами")

                    # Обрабатываем каждую строку таблицы
                    for row in table.rows:
                        cells = [cell.text.strip().replace('\n', ' ') for cell in row.cells]
                        # Заполняем пустые ячейки, если их меньше, чем max_columns
                        while len(cells) < max_columns:
                            cells.append('')
                        # Формируем строку с разделителями │
                        row_text = '│' + '│'.join(cells) + '│'
                        text_lines.append(row_text)
                        logging.debug(f"Извлечена строка таблицы: {row_text}")
                    # Добавляем пустую строку между таблицами
                    text_lines.append('')
            except Exception as e:
                raise ValueError(f"Ошибка при обработке .docx файла {doc_path}: {e}")
        else:
            # Обработка .doc файлов через docx2txt (antiword менее надежен)
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
                            # Завершаем таблицу
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
                # Сохраняем последнюю таблицу, если она есть
                if current_table:
                    for row in current_table:
                        cells = row.split('│')[1:-1]
                        while len(cells) < max_columns:
                            cells.append('')
                        row_text = '│' + '│'.join(cells) + '│'
                        text_lines.append(row_text)
                        logging.debug(f"Извлечена строка таблицы (.doc): {row_text}")
            except Exception as e:
                raise ValueError(f"Ошибка при обработке .doc файла {doc_path}: {e}")

        if not text_lines or all(not line.strip() for line in text_lines):
            raise ValueError(f"Файл {doc_path} пуст или не содержит полезного текста")

        # Сохраняем в TXT файл
        os.makedirs(os.path.dirname(txt_path), exist_ok=True)
        with open(txt_path, 'w', encoding='utf-8') as txt_file:
            for line in text_lines:
                txt_file.write(line + '\n')
        logging.info(f"Текст успешно извлечён из {doc_path} и сохранён в {txt_path}")

        # Отладочный вывод содержимого файла
        with open(txt_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            logging.info(f"Содержимое файла {txt_path}:")
            for i, line in enumerate(lines, 1):
                logging.debug(f"Строка {i}: {line.strip()}")

        return True

    except Exception as e:
        logging.error(f"Ошибка при обработке {doc_path}: {e}")
        return False
