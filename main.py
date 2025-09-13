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
import signal

# Загружаем переменные окружения
load_dotenv()
BOT_TOKEN = os.getenv('BOT_TOKEN')
if not BOT_TOKEN:
    print("Ошибка: BOT_TOKEN не указан в переменных окружения")
    sys.exit(1)

# Глобальные переменные для graceful shutdown
running = True
flask_app = Flask(__name__)

# Инициализация Telegram-бота
bot = telebot.TeleBot(BOT_TOKEN)

# Webhook-обработчик для Telegram
@flask_app.route(f'/{BOT_TOKEN}', methods=['POST'])
def webhook():
    try:
        if request.content_type == 'application/json':
            update = request.get_json()
            bot.process_new_updates([telebot.types.Update.de_json(update)])
            return jsonify({'status': 'ok'})
        return 'Bad Request', 400
    except Exception as e:
        print(f"Ошибка webhook: {e}")
        return 'Internal Server Error', 500

# Простая главная страница для проверки
@flask_app.route('/')
def index():
    return 'Telegram Bot is running!'

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
    Выполняет get_schedule.py и, если успешно, extract_schedule.py по расписанию.
    """
    if not running:
        return
    print(f"\n[{datetime.datetime.now()}] Запуск задачи по расписанию...")
    success = run_script('get_schedule.py')
    if success:
        print(f"[{datetime.datetime.now()}] get_schedule.py завершён успешно, запускаем extract_schedule.py...")
        run_script('extract_schedule.py')
    else:
        print(f"[{datetime.datetime.now()}] get_schedule.py завершился с ошибкой, extract_schedule.py не запускается.")

def run_all_scripts_at_startup():
    """
    Запускает все скрипты последовательно при старте программы.
    """
    scripts = ['get_schedule.py', 'extract_schedule.py', 'parse_schedule.py']
    success_count = 0
    for script in scripts:
        print(f"Запускаем {script} при старте...")
        if run_script(script):
            success_count += 1
        else:
            print(f"Ошибка: Скрипт {script} завершился с ошибкой, прерываем")
            return False
    print(f"Все скрипты при старте выполнены: {success_count}/3 успешно")
    return True

def run_schedule_in_background():
    """
    Запускает schedule в фоновом потоке.
    """
    schedule.every().day.at("20:00").do(run_scheduled_task)
    while running:
        schedule.run_pending()
        time.sleep(60)

def signal_handler(sig, frame):
    """
    Обработчик сигналов для graceful shutdown.
    """
    global running
    print('\nПолучен сигнал остановки. Завершаем работу...')
    running = False
    bot.remove_webhook()
    print("Webhook удалён")
    sys.exit(0)

def main():
    """
    Основная функция: запускает скрипты при старте, HTTP-сервер с webhook и schedule в фоне.
    """
    # Регистрируем обработчик сигналов
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Запускаем все скрипты при старте
    print("Запускаем скрипты при старте программы...")
    run_all_scripts_at_startup()

    # Логируем переменные для отладки
    render_hostname = os.getenv('RENDER_EXTERNAL_HOSTNAME')
    print(f"RENDER_EXTERNAL_HOSTNAME: {render_hostname}")

    # На Render: устанавливаем webhook
    bot.remove_webhook()
    webhook_url = f"https://{render_hostname}/{BOT_TOKEN}"
    print(f"Пытаемся установить webhook: {webhook_url}")
    try:
        bot.set_webhook(url=webhook_url)
        print(f"Webhook успешно установлен: {webhook_url}")
    except Exception as e:
        print(f"Ошибка установки webhook: {e}")
        sys.exit(1)  # Завершаем, так как webhook обязателен для Render

    # Запускаем schedule в отдельном потоке
    threading.Thread(target=run_schedule_in_background, daemon=True).start()

    # Запускаем Flask для деплоя
    port = int(os.getenv('PORT', 8443))
    print(f"Запускаем Flask на порту {port}")
    try:
        flask_app.run(host='0.0.0.0', port=port, debug=False)
    except KeyboardInterrupt:
        print("Flask остановлен пользователем")

if __name__ == "__main__":
    main()
