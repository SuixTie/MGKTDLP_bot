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
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Загружаем переменные окружения
load_dotenv()
BOT_TOKEN = os.getenv('BOT_TOKEN')
if not BOT_TOKEN:
    logging.error("BOT_TOKEN не указан в переменных окружения")
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
        logging.info(f"Webhook POST получен, content_type: {request.content_type}")
        if request.content_type == 'application/json':
            update = request.get_json()
            logging.info(f"JSON распарсен: {update}")
            bot.process_new_updates([telebot.types.Update.de_json(update)])
            logging.info("Обновление обработано")
            return jsonify({'status': 'ok'})
        logging.error(f"Неверный content_type: {request.content_type}")
        return 'Bad Request', 400
    except Exception as e:
        logging.error(f"Ошибка webhook: {e}")
        return 'Internal Server Error', 500

@flask_app.route('/')
def index():
    return 'Telegram Bot is running! 🚀'

def run_script(script_name):
    """Запускает скрипт с захватом вывода и явной кодировкой UTF-8."""
    logging.info(f"Начинаем запуск {script_name}...")
    if not os.path.exists(script_name):
        logging.error(f"Скрипт {script_name} не найден в текущей директории: {os.getcwd()}")
        return False
    try:
        result = subprocess.run(
            [sys.executable, script_name],
            check=True,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            timeout=300
        )
        logging.info(f"Скрипт {script_name} успешно выполнен")
        if result.stdout.strip():
            logging.info("STDOUT:")
            logging.info(result.stdout)
        if result.stderr.strip():
            logging.warning("STDERR:")
            logging.warning(result.stderr)
        return True
    except subprocess.CalledProcessError as e:
        logging.error(f"Ошибка при выполнении {script_name}: {e}")
        if e.stdout:
            logging.error(f"STDOUT (ошибка): {e.stdout}")
        if e.stderr:
            logging.error(f"STDERR (ошибка): {e.stderr}")
        return False
    except subprocess.TimeoutExpired as e:
        logging.error(f"Таймаут выполнения {script_name}: {e}")
        return False

def run_scheduled_task():
    """Выполняет get_schedule.py и, если успешно, extract_schedule.py по расписанию."""
    if not running:
        return
    logging.info(f"Запуск задачи по расписанию...")
    success = run_script('get_schedule.py')
    if success:
        logging.info("get_schedule.py завершён успешно, запускаем extract_schedule.py...")
        run_script('extract_schedule.py')
    else:
        logging.error("get_schedule.py завершился с ошибкой, extract_schedule.py не запускается.")

def run_all_scripts_at_startup():
    """Запускает скрипты при старте программы."""
    scripts = ['get_schedule.py', 'extract_schedule.py']  # Убрали parse_schedule.py
    success_count = 0
    for script in scripts:
        if run_script(script):
            success_count += 1
        else:
            logging.error(f"Скрипт {script} завершился с ошибкой, продолжаем...")
    logging.info(f"Все скрипты при старте выполнены: {success_count}/{len(scripts)} успешно")

def run_schedule_in_background():
    """Запускает schedule в фоновом потоке."""
    schedule.every().day.at("20:00").do(run_scheduled_task)
    while running:
        schedule.run_pending()
        time.sleep(60)

def setup_webhook():
    """Устанавливает webhook в фоне."""
    render_hostname = os.getenv('RENDER_EXTERNAL_HOSTNAME')
    if render_hostname:
        bot.remove_webhook()
        webhook_url = f"https://{render_hostname}/{BOT_TOKEN}"
        logging.info(f"Устанавливаем webhook: {webhook_url}")
        try:
            bot.set_webhook(url=webhook_url)
            logging.info(f"Webhook успешно установлен: {webhook_url}")
        except Exception as e:
            logging.error(f"Ошибка установки webhook: {e} (продолжаем без webhook)")

def signal_handler(sig, frame):
    """Обработчик сигналов для graceful shutdown."""
    global running
    logging.info("Получен сигнал остановки. Завершаем работу...")
    running = False
    bot.remove_webhook()
    logging.info("Webhook удалён")
    sys.exit(0)

def main():
    """Основная функция: запускает HTTP-сервер сразу, скрипты и schedule в фоне."""
    logging.info("main.py запущен. Начинаем инициализацию...")
    logging.info(f"Текущая директория: {os.getcwd()}")
    logging.info(f"Файлы в директории: {os.listdir()}")

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    threading.Thread(target=run_all_scripts_at_startup, daemon=True).start()
    threading.Thread(target=run_schedule_in_background, daemon=True).start()
    threading.Thread(target=setup_webhook, daemon=True).start()

    port = int(os.getenv('PORT', 10000))
    logging.info(f"Запускаем Flask на порту {port} (для Render)")
    try:
        flask_app.run(host='0.0.0.0', port=port, debug=False)
    except Exception as e:
        logging.error(f"Ошибка Flask: {e}")

if __name__ == "__main__":
    main()
