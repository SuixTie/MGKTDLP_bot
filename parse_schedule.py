import re
import os
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import logging
import time

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Словарь для хранения номеров групп пользователей (user_id: group_id)
user_groups = {}

def retry_api_call(func, *args, retries=3, delay=1, **kwargs):
    """Повторяет вызов Telegram API при сетевых ошибках."""
    for attempt in range(retries):
        try:
            logging.info(f"Отправка сообщения: {kwargs.get('text', 'N/A')}")
            return func(*args, **kwargs)
        except Exception as e:
            logging.error(f"Ошибка API (попытка {attempt+1}): {e}")
            if attempt < retries - 1:
                time.sleep(delay)
            else:
                raise

def save_schedule(groups, block_schedule, schedules):
    """Сохраняет расписание для групп в словаре schedules."""
    try:
        for col, group in enumerate(groups):
            group = group.strip()
            lessons = []
            for lesson in block_schedule[col]:
                if lesson:
                    cleaned = re.sub(r'^\d+\s*', '', lesson).strip()
                    cleaned = re.sub(r'\s+', ' ', cleaned.replace('\xa0', ' '))
                    subject_pattern = r'^[^0-9]*'
                    subject_match = re.search(subject_pattern, cleaned)
                    if subject_match and subject_match.group(0).strip():
                        subject = subject_match.group(0).rstrip('/').strip()
                        rooms = cleaned[subject_match.end():].strip()
                        rooms = re.sub(r'\bпр', '', rooms)
                        cleaned = f"{subject} ({rooms})" if rooms else subject
                    else:
                        subject = cleaned
                        cleaned = subject
                    lessons.append(cleaned)
                else:
                    lessons.append('')
            schedules[group] = lessons
    except Exception as e:
        logging.error(f"Ошибка при сохранении расписания: {e}")

def parse_schedule(file_path, group_id):
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read()
    except FileNotFoundError:
        logging.warning(f"Файл {file_path} не найден")
        return None, None

    content = content.rstrip('\n')
    lines = content.splitlines()

    date = None
    if lines:
        first_line = lines[0].strip()
        date_match = re.search(r'\d{2}\.\d{2}\.\d{4}', first_line)
        date = date_match.group(0) if date_match else "Не указана"

    schedules = {}
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        logging.info(f"Строка [{i}] в файле {file_path}: '{line}'")
        if not line:
            i += 1
            continue
        if line.startswith('┌') or (line.startswith('│') and line.count('│') >= 3):
            logging.info(f"  Проверяем как потенциальную строку с группами: '{line}'")
            line = line.replace('\xa0', ' ').replace('\u200b', '').replace('\ufeff', '')
            cells = [cell.strip() for cell in line.split('│')[1:-1]]
            logging.info(f"  После split и strip: {cells}")
            is_group_line = cells and all(
                cell and re.match(r'^\\w+$', cell) and (
                    re.match(r'.*[a-zA-ZА-Яа-я].*', cell) or
                    (re.match(r'^\d+$', cell) and len(cell) >= 3)
                ) for cell in cells
            )
            if not is_group_line and line.startswith('│'):
                logging.info(f"  Строка не распознана как группы в файле {file_path}: {cells}")
                for cell in cells:
                    if not cell:
                        logging.warning(f"    Проблема: Пустая ячейка")
                    elif not re.match(r'^\\w+$', cell):
                        logging.warning(f"    Проблема: Ячейка '{cell}' не соответствует шаблону ^\\w+$")
                    elif not (re.match(r'.*[a-zA-ZА-Яа-я].*', cell) or
                              (re.match(r'^\d+$', cell) and len(cell) >= 3)):
                        logging.warning(f"    Проблема: Ячейка '{cell}' не является буквенной или числом >= 3 символов")
                i += 1
                continue
            if i >= len(lines):
                break
            group_line = lines[i].strip() if line.startswith('┌') else line
            group_line = group_line.replace('\xa0', ' ').replace('\u200b', '').replace('\ufeff', '')
            groups = [id.strip() for id in group_line.split('│')[1:-1] if id.strip()]
            logging.info(f"  Группы из строки: {groups}")
            if not groups:
                i += 1
                continue

            num_columns = len(groups)
            i += 1
            if i >= len(lines):
                break
            connector_line = lines[i].strip()
            if not connector_line.startswith('├'):
                i += 1
                continue

            block_schedule = [[] for _ in range(num_columns)]
            i += 1
            while i < len(lines):
                line = lines[i].strip()
                if not line:
                    i += 1
                    continue
                line = line.replace('\xa0', ' ').replace('\u200b', '').replace('\ufeff', '')
                cells = [cell.strip() for cell in line.split('│')[1:-1]]
                if line.startswith('┌') or line.startswith('└'):
                    if groups and block_schedule:
                        save_schedule(groups, block_schedule, schedules)
                    break
                if line.startswith('│') and line.count('│') >= 3 and all(
                        cell and re.match(r'^\\w+$', cell.strip()) and (
                            re.match(r'.*[a-zA-ZА-Яа-я].*', cell) or
                            (re.match(r'^\d+$', cell) and len(cell) >= 3)
                        ) for cell in cells
                ):
                    if groups and block_schedule:
                        save_schedule(groups, block_schedule, schedules)
                    i -= 1
                    break
                if len(cells) != num_columns:
                    cells += [''] * (num_columns - len(cells))
                for col, cell in enumerate(cells):
                    block_schedule[col].append(cell)
                i += 1

            if groups and block_schedule and i >= len(lines):
                save_schedule(groups, block_schedule, schedules)

        i += 1

    group_id = group_id.strip()
    if group_id in schedules and any(schedules[group_id]):
        return schedules[group_id], date
    else:
        return None, date

def get_schedule_files(folder_path="extracted_schedules"):
    days_order = ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота']
    days_map = {
        'rasp_monday.txt': 'Понедельник',
        'rasp_tuesday.txt': 'Вторник',
        'rasp_wednesday.txt': 'Среда',
        'rasp_thursday.txt': 'Четверг',
        'rasp_friday.txt': 'Пятница',
        'rasp_saturday.txt': 'Суббота'
    }
    schedule_files = {}
    if not os.path.exists(folder_path):
        logging.error(f"Папка {folder_path} не найдена")
        return schedule_files
    for filename in os.listdir(folder_path):
        if filename.endswith('.txt') and filename in days_map:
            file_path = os.path.join(folder_path, filename)
            day_name = days_map[filename]
            schedule_files[day_name] = file_path
    sorted_schedule_files = {day: schedule_files[day] for day in days_order if day in schedule_files}
    return sorted_schedule_files

def get_available_groups(folder_path="extracted_schedules"):
    groups = set()
    schedule_files = get_schedule_files(folder_path)
    for day, file_path in schedule_files.items():
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                content = file.read()
            lines = content.rstrip('\n').splitlines()
            for i, line in enumerate(lines):
                line = line.strip()
                if line.startswith('┌') or (line.startswith('│') and line.count('│') >= 3):
                    line = line.replace('\xa0', ' ').replace('\u200b', '').replace('\ufeff', '')
                    cells = [cell.strip() for cell in line.split('│')[1:-1]]
                    is_group_line = cells and all(
                        cell and re.match(r'^\\w+$', cell) and (
                            re.match(r'.*[a-zA-ZА-Яа-я].*', cell) or
                            (re.match(r'^\d+$', cell) and len(cell) >= 3)
                        ) for cell in cells
                    )
                    if is_group_line:
                        groups.update(cell.strip() for cell in cells if cell.strip())
        except FileNotFoundError:
            logging.warning(f"Файл {file_path} не найден")
            continue
        except UnicodeDecodeError:
            logging.warning(f"Ошибка декодирования файла {file_path}")
            continue

    numeric_groups = [g for g in groups if g.isdigit()]
    special_groups = ["8ТО", "9ТО", "10ТО"]
    letter_groups = [g for g in groups if not g.isdigit() and g not in special_groups]
    numeric_groups.sort(key=lambda x: int(x), reverse=True)
    letter_groups.sort()
    sorted_groups = numeric_groups + letter_groups + [g for g in special_groups if g in groups]
    logging.info(f"Доступные группы: {sorted_groups}")
    return sorted_groups

def get_main_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(InlineKeyboardButton("🔔 Расписание звонков", callback_data="bells"))
    keyboard.add(InlineKeyboardButton("📚 Расписание уроков", callback_data="lessons"))
    keyboard.add(InlineKeyboardButton("👥 Выбрать группу", callback_data="select_group"))
    return keyboard

def get_groups_keyboard(groups, context="select", page=1):
    keyboard = InlineKeyboardMarkup(row_width=3)
    total_groups = len(groups)
    per_page = (total_groups + 1) // 2
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    current_groups = groups[start_idx:end_idx]
    for i in range(0, len(current_groups), 3):
        row = [InlineKeyboardButton(group, callback_data=f"group_{group}_{context}") for group in current_groups[i:i + 3]]
        keyboard.row(*row)
    nav_buttons = []
    if page == 1 and total_groups > per_page:
        nav_buttons.append(InlineKeyboardButton("Вперёд ➡️", callback_data=f"page_2_{context}"))
    elif page == 2:
        nav_buttons.append(InlineKeyboardButton("⬅️ Назад", callback_data=f"page_1_{context}"))
    nav_buttons.append(InlineKeyboardButton("🔙 Вернуться", callback_data="back_main"))
    if nav_buttons:
        keyboard.row(*nav_buttons)
    return keyboard

def get_days_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=2)
    days = ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота']
    buttons = [InlineKeyboardButton(f"📅 {day}", callback_data=day) for day in days]
    keyboard.add(*buttons)
    keyboard.add(InlineKeyboardButton("🔄 Сменить группу", callback_data="change_group"))
    keyboard.add(InlineKeyboardButton("🔙 Вернуться", callback_data="back_main"))
    return keyboard

def register_handlers(bot):
    @bot.message_handler(commands=['start'])
    def start(message):
        groups = get_available_groups()
        if not groups:
            retry_api_call(
                bot.send_message,
                message.chat.id,
                "❌ Не удалось найти группы\. Убедитесь, что файлы расписания находятся в папке 'extracted_schedules'\.",
                parse_mode='MarkdownV2'
            )
            return
        retry_api_call(
            bot.send_message,
            message.chat.id,
            "Привет\! 👋 \nЯ помогу тебе узнать расписание звонков и занятий колледжа\.\nВыбери, что тебе нужно\:",
            reply_markup=get_main_keyboard(),
            parse_mode='MarkdownV2'
        )

    @bot.message_handler(commands=['group'])
    def change_group_command(message):
        groups = get_available_groups()
        if not groups:
            retry_api_call(
                bot.send_message,
                message.chat.id,
                "❌ Не удалось найти группы\. Убедитесь, что файлы расписания находятся в папке 'extracted_schedules'\.",
                parse_mode='MarkdownV2'
            )
            return
        retry_api_call(
            bot.send_message,
            message.chat.id,
            "🔄 Выберите новую группу\:",
            reply_markup=get_groups_keyboard(groups, context="select", page=1),
            parse_mode='MarkdownV2'
        )

    @bot.callback_query_handler(func=lambda call: True)
    def callback_handler(call):
        retry_api_call(bot.answer_callback_query, call.id)
        if call.data == "bells":
            bells_schedule = "*🔔 Расписание звонков 🔔*\n\n" \
                            "*1 Занятие*: 8:30 – 9:15\n\n" \
                            "*2 Занятие*: 9:25 – 10:10\n\n" \
                            "*3 Занятие*: 10:20 – 11:05\n\n" \
                            "*4 Занятие*: 11:15 – 12:00\n\n" \
                            "*• Большой перерыв (1–2 курс)*\n\n" \
                            "*5 Занятие (1–2 курс)*: 12:55 – 13:40\n\n" \
                            "*5 Занятие (3–4 курс)*: 12:10 – 12:55\n\n" \
                            "*• Большой перерыв (3–4 курс)*\n\n" \
                            "*6 Занятие*: 13:50 – 14:35\n\n" \
                            "*7 Занятие*: 14:45 – 15:30\n\n" \
                            "*8 Занятие*: 15:40 – 16:25\n\n" \
                            "*9 Занятие*: 16:35 – 17:20\n\n" \
                            "*10 Занятие*: 17:30 – 18:15"
            # Экранируем специальные символы для MarkdownV2
            bells_schedule = bells_schedule.replace('*', '\*').replace('(', '\(').replace(')', '\)').replace('–', '\–')
            retry_api_call(
                bot.edit_message_text,
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=bells_schedule,
                reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Вернуться назад", callback_data="back_main")),
                parse_mode='MarkdownV2'
            )
        elif call.data == "lessons":
            groups = get_available_groups()
            if not groups:
                retry_api_call(
                    bot.send_message,
                    call.message.chat.id,
                    "❌ Не удалось найти группы\. Убедитесь, что файлы расписания находятся в папке 'extracted_schedules'\.",
                    parse_mode='MarkdownV2'
                )
                return
            user_id = call.from_user.id
            if user_id not in user_groups or not user_groups[user_id]:
                retry_api_call(
                    bot.edit_message_text,
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    text="📚 Сначала выберите группу\:",
                    reply_markup=get_groups_keyboard(groups, context="lessons", page=1),
                    parse_mode='MarkdownV2'
                )
            else:
                group_id = user_groups[user_id]
                retry_api_call(
                    bot.edit_message_text,
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    text=f"✅ Группа установлена: *{group_id}*\nВыберите день недели для просмотра расписания\:",
                    reply_markup=get_days_keyboard(),
                    parse_mode='MarkdownV2'
                )
        elif call.data == "select_group":
            groups = get_available_groups()
            if not groups:
                retry_api_call(
                    bot.send_message,
                    call.message.chat.id,
                    "❌ Не удалось найти группы\. Убедитесь, что файлы расписания находятся в папке 'extracted_schedules'\.",
                    parse_mode='MarkdownV2'
                )
                return
            retry_api_call(
                bot.edit_message_text,
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text="👥 Выберите группу\:",
                reply_markup=get_groups_keyboard(groups, context="select", page=1),
                parse_mode='MarkdownV2'
            )
        elif call.data.startswith("group_"):
            parts = call.data.split('_')
            if len(parts) < 3:
                retry_api_call(
                    bot.send_message,
                    call.message.chat.id,
                    "❌ Ошибка в обработке выбора группы\.",
                    parse_mode='MarkdownV2'
                )
                return
            group_id = parts[1]
            context = parts[2]
            user_groups[call.from_user.id] = group_id
            if context == "lessons":
                retry_api_call(
                    bot.edit_message_text,
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    text=f"✅ Группа установлена: *{group_id}*\nВыберите день недели для просмотра расписания\:",
                    reply_markup=get_days_keyboard(),
                    parse_mode='MarkdownV2'
                )
            else:
                retry_api_call(
                    bot.edit_message_text,
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    text=f"✅ Группа установлена: *{group_id}*",
                    reply_markup=get_main_keyboard(),
                    parse_mode='MarkdownV2'
                )
        elif call.data.startswith("page_"):
            parts = call.data.split('_')
            if len(parts) < 3:
                retry_api_call(
                    bot.send_message,
                    call.message.chat.id,
                    "❌ Ошибка в обработке страниц\.",
                    parse_mode='MarkdownV2'
                )
                return
            page = int(parts[1])
            context = parts[2]
            groups = get_available_groups()
            if not groups:
                retry_api_call(
                    bot.send_message,
                    call.message.chat.id,
                    "❌ Не удалось найти группы\. Убедитесь, что файлы расписания находятся в папке 'extracted_schedules'\.",
                    parse_mode='MarkdownV2'
                )
                return
            text = "📚 Сначала выберите группу\:" if context == "lessons" else "👥 Выберите группу\:"
            retry_api_call(
                bot.edit_message_text,
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=text,
                reply_markup=get_groups_keyboard(groups, context=context, page=page),
                parse_mode='MarkdownV2'
            )
        elif call.data == "change_group":
            groups = get_available_groups()
            if not groups:
                retry_api_call(
                    bot.send_message,
                    call.message.chat.id,
                    "❌ Не удалось найти группы\. Убедитесь, что файлы расписания находятся в папке 'extracted_schedules'\.",
                    parse_mode='MarkdownV2'
                )
                return
            retry_api_call(
                bot.edit_message_text,
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text="🔄 Выберите новую группу\:",
                reply_markup=get_groups_keyboard(groups, context="select", page=1),
                parse_mode='MarkdownV2'
            )
        elif call.data == "back_main":
            retry_api_call(
                bot.edit_message_text,
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text="👋 Выберите опцию\:",
                reply_markup=get_main_keyboard(),
                parse_mode='MarkdownV2'
            )
        else:
            day = call.data
            user_id = call.from_user.id
            if user_id not in user_groups:
                retry_api_call(
                    bot.send_message,
                    call.message.chat.id,
                    "❌ Сначала выберите группу с помощью /start или /group\.",
                    parse_mode='MarkdownV2'
                )
                return
            group_id = user_groups[user_id]
            schedules_folder = "extracted_schedules"
            available_schedules = get_schedule_files(schedules_folder)
            if day in available_schedules:
                selected_file = available_schedules[day]
                schedule, date = parse_schedule(selected_file, group_id)
                if schedule:
                    response = f"📚 *Расписание для группы {group_id} на {day} ({date}):*\n\n"
                    for idx, lesson in enumerate(schedule, start=1):
                        if lesson:
                            # Экранируем специальные символы в уроках
                            lesson = lesson.replace('*', '\*').replace('(', '\(').replace(')', '\)').replace('.', '\.')
                            response += f"*{idx}\.* {lesson}\n"
                        else:
                            response += f"*{idx}\.* Нет урока\n"
                    retry_api_call(
                        bot.edit_message_text,
                        chat_id=call.message.chat.id,
                        message_id=call.message.message_id,
                        text=response.replace('(', '\(').replace(')', '\)').replace('.', '\.'),
                        reply_markup=get_days_keyboard(),
                        parse_mode='MarkdownV2'
                    )
                else:
                    retry_api_call(
                        bot.edit_message_text,
                        chat_id=call.message.chat.id,
                        message_id=call.message.message_id,
                        text=f"❌ Группа *{group_id}* не найдена в расписании на *{day}*\.",
                        reply_markup=get_days_keyboard(),
                        parse_mode='MarkdownV2'
                    )
            else:
                retry_api_call(
                    bot.edit_message_text,
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    text=f"❌ Расписание на *{day}* не найдено\.",
                    reply_markup=get_days_keyboard(),
                    parse_mode='MarkdownV2'
                )
