import subprocess
import sys
import os
import schedule
import time
import datetime
import telebot
from flask import Flask, request, jsonify
import threading
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()
BOT_TOKEN = os.getenv('BOT_TOKEN')
if not BOT_TOKEN:
    print("Ошибка: BOT_TOKEN не указан в переменных окружения")
    sys.exit(1)

# Инициализация Telegram-бота
bot = telebot.TeleBot(BOT_TOKEN)

# Инициализация Flask
app = Flask(__name__)

# Webhook-обработчик для Telegram
@app.route(f'/{BOT_TOKEN}', methods=['POST'])
def webhook():
    try:
        # Правильная проверка: Telegram отправляет application/json
        if request.content_type == 'application/json':
            update = request.get_json()
            bot.process_new_updates([telebot.types.Update.de_json(update)])
            return jsonify({'status': 'ok'})
        return 'Bad Request', 400
    except Exception as e:
        print(f"Ошибка webhook: {e}")
        return 'Internal Server Error', 500

# Простая главная страница для проверки (Render пингует её)
@app.route('/')
def index():
    return 'Telegram Bot is running!'

# Пример хендлера для бота (добавьте ваши из parse_schedule.py, если нужно)
@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, 'Привет! Я бот для расписания. Отправь /help для команд.')

@bot.message_handler(commands=['help'])
def help_command(message):
    bot.reply_to(message, 'Команды:\n/start - Запустить бота\n/help - Показать помощь\n/run - Запустить скрипты вручную')

@bot.message_handler(commands=['run'])
def run_manually(message):
    chat_id = message.chat.id
    bot.reply_to(message, 'Запускаю скрипты вручную...')
    # Запуск в фоне, чтобы не блокировать ответ
    threading.Thread(target=lambda: run_all_scripts_and_notify(chat_id)).start()

def run_all_scripts_and_notify(chat_id):
    """
    Запускает скрипты и уведомляет пользователя о результате.
    """
    try:
        scripts = ['get_schedule.py', 'extract_schedule.py', 'parse_schedule.py']
        success_count = 0
        for script in scripts:
            print(f"Запускаем {script}...")
            if run_script(script):
                success_count += 1
        status = f"Скрипты выполнены: {success_count}/3 успешно"
        bot.send_message(chat_id, status)
    except Exception as e:
        bot.send_message(chat_id, f"Ошибка при запуске: {e}")

def run_script(script_name):
    """
    Запускает скрипт с захватом вывода и явной кодировкой UTF-8.
    """
    if not os.path.exists(script_name):
        print(f"Ошибка: Скрипт {script_name} не найден в текущей директории.")
        return False

    try:
        encoding = 'utf-8'
        result = subprocess.run(
            [sys.executable, script_name],
            check=True,
            capture_output=True,
            text=True,
            encoding=encoding,
            errors='replace'
        )
        print(f"Скрипт {script_name} успешно выполнен")
        if result.stdout.strip():
            print("STDOUT:")
            print(result.stdout)
        if result.stderr.strip():
            print("STDERR:")
            print(result.stderr)
        return True
    except UnicodeDecodeError as e:
        print(f"Ошибка декодирования в UTF-8 для {script_name}. Пробуем cp1251...")
        try:
            result = subprocess.run(
                [sys.executable, script_name],
                check=True,
                capture_output=True,
                text=True,
                encoding='cp1251',
                errors='replace'
            )
            print(f"Скрипт {script_name} успешно выполнен (cp1251)")
            if result.stdout.strip():
                print("STDOUT:")
                print(result.stdout)
            if result.stderr.strip():
                print("STDERR:")
                print(result.stderr)
            return True
        except subprocess.CalledProcessError as e2:
            print(f"Ошибка при выполнении {script_name} (cp1251): {e2}")
            if e2.stderr:
                print("STDERR (raw):", repr(e2.stderr.encode('latin1')[:200]))
            return False
    except subprocess.CalledProcessError as e:
        print(f"Ошибка при выполнении {script_name}: {e}")
        if e.stdout:
            print("STDOUT (ошибка):", e.stdout)
        if e.stderr:
            print("STDERR (ошибка):", e.stderr)
        return False

def run_scheduled_task():
    """
    Выполняет get_schedule.py и, если успешно, extract_schedule.py.
    """
    print(f"\n[{datetime.datetime.now()}] Запуск задачи по расписанию...")
    success = run_script('get_schedule.py')
    if success:
        print(f"[{datetime.datetime.now()}] get_schedule.py завершён успешно, запускаем extract_schedule.py...")
        run_script('extract_schedule.py')
    else:
        print(f"[{datetime.datetime.now()}] get_schedule.py завершился с ошибкой, extract_schedule.py не запускается.")

def run_schedule_in_background():
    """
    Запускает schedule в фоновом потоке.
    """
    schedule.every().day.at("20:00").do(run_scheduled_task)
    while True:
        schedule.run_pending()
        time.sleep(60)

def main():
    """
    Основная функция: запускает HTTP-сервер с webhook и schedule в фоне.
    """
    # Логируем переменные для отладки
    render_hostname = os.getenv('RENDER_EXTERNAL_HOSTNAME')
    print(f"RENDER_EXTERNAL_HOSTNAME: {render_hostname}")

    if render_hostname:
        # На Render: устанавливаем webhook
        bot.remove_webhook()
        webhook_url = f"https://{render_hostname}/{BOT_TOKEN}"
        print(f"Пытаемся установить webhook: {webhook_url}")
        try:
            bot.set_webhook(url=webhook_url)
            print(f"Webhook успешно установлен: {webhook_url}")
        except Exception as e:
            print(f"Ошибка установки webhook: {e}")
            print("Продолжаем с polling...")
            use_polling = True
    else:
        # Локально: используем polling
        print("Локальный запуск: используем polling")
        use_polling = True

    # Запускаем schedule в отдельном потоке
    threading.Thread(target=run_schedule_in_background, daemon=True).start()

    # Запускаем Flask (всегда, для порта на Render)
    port = int(os.getenv('PORT', 8443))
    print(f"Запускаем Flask на порту {port}")
    app.run(host='0.0.0.0', port=port, debug=False)

    # Если polling (локально), запустим его после Flask (но Flask блокирует, так что для локального теста раскомментируйте ниже)
    # if use_polling:
    #     print("Запускаем polling...")
    #     bot.infinity_polling()

if __name__ == "__main__":
    main()
