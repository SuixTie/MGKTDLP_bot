import subprocess
import sys
import os
import schedule
import time
import telebot
from flask import Flask, request, jsonify
import threading
from dotenv import load_dotenv
import signal
import logging
import parse_schedule
import requests

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

load_dotenv()
BOT_TOKEN = os.getenv('BOT_TOKEN')
if not BOT_TOKEN:
    logging.error("BOT_TOKEN не указан в переменных окружения")
    sys.exit(1)

running = True
flask_app = Flask(__name__)

bot = telebot.TeleBot(BOT_TOKEN)

parse_schedule.register_handlers(bot)
logging.info("Обработчики из parse_schedule зарегистрированы")

@flask_app.route(f'/{BOT_TOKEN}', methods=['POST'])
def webhook():
    try:
        if request.content_type == 'application/json':
            update = request.get_json()
            bot.process_new_updates([telebot.types.Update.de_json(update)])
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

def run_all_scripts_at_startup():
    scripts = ['get_schedule.py', 'extract_schedule.py']
    success_count = 0
    for script in scripts:
        if run_script(script):
            success_count += 1
        else:
            logging.error(f"Скрипт {script} завершился с ошибкой, продолжаем...")
    extracted_dir = "extracted_schedules"
    if os.path.exists(extracted_dir):
        files = os.listdir(extracted_dir)
        logging.info(f"Содержимое папки {extracted_dir}: {files}")
    else:
        logging.error(f"Папка {extracted_dir} не существует")
    logging.info(f"Все скрипты при старте выполнены: {success_count}/{len(scripts)} успешно")

def run_scheduled_task():
    if not running:
        return
    logging.info("Запуск задачи по расписанию...")
    success = run_script('get_schedule.py')
    if success:
        logging.info("get_schedule.py завершён успешно, запускаем extract_schedule.py...")
        run_script('extract_schedule.py')
        extracted_dir = "extracted_schedules"
        if os.path.exists(extracted_dir):
            files = os.listdir(extracted_dir)
            logging.info(f"Содержимое папки {extracted_dir}: {files}")
        else:
            logging.error(f"Папка {extracted_dir} не существует")
    else:
        logging.error("get_schedule.py завершился с ошибкой, extract_schedule.py не запускается.")

def check_webhook():
    try:
        response = requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getWebhookInfo")
        data = response.json()
        if data['ok']:
            logging.info(f"Webhook info: {data['result']}")
            if data['result']['url']:
                logging.info(f"Webhook активен: {data['result']['url']}")
            else:
                logging.warning("Webhook не установлен")
        else:
            logging.error(f"Ошибка при проверке webhook: {data}")
    except Exception as e:
        logging.error(f"Ошибка при запросе getWebhookInfo: {e}")

def setup_webhook():
    render_hostname = os.getenv('RENDER_EXTERNAL_HOSTNAME')
    if render_hostname:
        bot.remove_webhook()
        webhook_url = f"https://{render_hostname}/{BOT_TOKEN}"
        logging.info(f"Устанавливаем webhook: {webhook_url}")
        try:
            bot.set_webhook(url=webhook_url)
            logging.info(f"Webhook успешно установлен: {webhook_url}")
            check_webhook()
        except Exception as e:
            logging.error(f"Ошибка установки webhook: {e}")

def signal_handler(sig, frame):
    global running
    logging.info("Получен сигнал остановки. Завершаем работу...")
    running = False
    bot.remove_webhook()
    logging.info("Webhook удалён")
    sys.exit(0)

def main():
    logging.info("main.py запущен. Начинаем инициализацию...")
    logging.info(f"Текущая директория: {os.getcwd()}")
    logging.info(f"Файлы в директории: {os.listdir()}")

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    run_all_scripts_at_startup()
    threading.Thread(target=run_schedule_in_background, daemon=True).start()
    threading.Thread(target=setup_webhook, daemon=True).start()

    logging.info("Бот инициализирован и готов к работе")
    port = int(os.getenv('PORT', 10000))
    logging.info(f"Запускаем Flask на порту {port} (для Render)")
    try:
        flask_app.run(host='0.0.0.0', port=port, debug=False)
    except Exception as e:
        logging.error(f"Ошибка Flask: {e}")

def run_schedule_in_background():
    schedule.every().day.at("06:00").do(run_scheduled_task)
    schedule.every().day.at("12:00").do(run_scheduled_task)
    schedule.every().day.at("18:00").do(run_scheduled_task)
    schedule.every().day.at("24:00").do(run_scheduled_task)
    while running:
        schedule.run_pending()
        time.sleep(60)

if __name__ == "__main__":
    main()
