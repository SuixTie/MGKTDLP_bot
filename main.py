import subprocess
import sys
import os
import schedule
import time
import datetime


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


def run_all_scripts_manually():
    """
    Последовательно запускает все скрипты вручную.
    """
    scripts = ['get_schedule.py', 'extract_schedule.py', 'parse_schedule.py']
    for script in scripts:
        print(f"Запускаем {script}...")
        success = run_script(script)
        if not success:
            print(f"Прерываем выполнение из-за ошибки в {script}")
            sys.exit(1)
    print("Все скрипты успешно выполнены")


def main():
    """
    Основная функция: запускает скрипты вручную или по расписанию.
    """
    import argparse
    parser = argparse.ArgumentParser(description="Управление запуском скриптов расписания")
    parser.add_argument('--schedule', action='store_true', help="Запуск в режиме расписания (ежедневно в 20:00)")
    args = parser.parse_args()

    if args.schedule:
        # Режим планировщика: запуск get_schedule.py в 20:00, затем extract_schedule.py
        print("Запускаем в режиме расписания. get_schedule.py будет выполнен в 20:00 ежедневно.")
        schedule.every().day.at("20:00").do(run_scheduled_task)
        while True:
            schedule.run_pending()
            time.sleep(60)  # Проверяем каждую минуту
    else:
        # Ручной запуск всех скриптов
        print("Запускаем все скрипты вручную...")
        run_all_scripts_manually()


if __name__ == "__main__":
    main()