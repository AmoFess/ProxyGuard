import ctypes
from ctypes import wintypes
import threading
import time
import winreg

# Определение констант для работы с реестром
HKEY_CURRENT_USER = winreg.HKEY_CURRENT_USER
REG_NOTIFY_CHANGE_LAST_SET = 0x00000004  # Уведомление об изменении значения
ERROR_SUCCESS = 0

# Новое значение для ProxyOverride
NEW_PROXY_OVERRIDE_VALUE = "localhost;192.168.*.*;<local>"

# Флаг для включения/отключения вывода сообщений
VERBOSE = True  # Если False, сообщения не будут выводиться

# Информация о программе
PROGRAM_NAME = "ProxyGuard"
PROGRAM_DESCRIPTION = f"""
Программа для мониторинга и автоматической корректировки параметра ProxyOverride 
в реестре Windows.

Основные функции:
- Отслеживает изменения в ключе реестра: 
  HKEY_CURRENT_USER\\Software\\Microsoft\\Windows\\CurrentVersion\\Internet Settings
- Автоматически заменяет значение ProxyOverride на '{NEW_PROXY_OVERRIDE_VALUE}'
  при его изменении.
- Работает в фоновом режиме с минимальным потреблением ресурсов.

Разработано для обеспечения стабильности настроек прокси-сервера.
"""

def log(message):
    """
    Функция для вывода сообщений на экран, если VERBOSE=True.
    """
    if VERBOSE:
        print(message)

def show_program_info():
    """
    Функция для вывода названия программы и её описания.
    """
    log(f"=== {PROGRAM_NAME} ===")
    log(PROGRAM_DESCRIPTION.strip())  # Убираем лишние отступы в начале и конце
    log("=" * (len(PROGRAM_NAME) + 8))  # Декоративная линия

def monitor_registry_key():
    """
    Функция для мониторинга изменений в указанной ветке реестра.
    """
    # Загрузка библиотеки advapi32.dll
    advapi32 = ctypes.WinDLL('advapi32', use_last_error=True)
    advapi32.RegNotifyChangeKeyValue.argtypes = [
        wintypes.HKEY,
        wintypes.BOOL,
        wintypes.DWORD,
        wintypes.HANDLE,
        wintypes.BOOL
    ]
    advapi32.RegNotifyChangeKeyValue.restype = wintypes.LONG

    # Открываем ключ реестра с правами на чтение и запись
    reg_key_path = r"Software\Microsoft\Windows\CurrentVersion\Internet Settings"
    try:
        key = winreg.OpenKey(HKEY_CURRENT_USER, reg_key_path, 0, winreg.KEY_NOTIFY | winreg.KEY_READ | winreg.KEY_WRITE)
    except OSError as e:
        log(f"Ошибка открытия ключа реестра: {e}")
        return

    log(f"Начинаем мониторинг ключа реестра: {reg_key_path}")

    while True:
        # Создаем событие для уведомления
        event = ctypes.windll.kernel32.CreateEventW(None, False, False, None)
        if not event:
            log("Не удалось создать событие.")
            break

        # Регистрируем уведомление об изменении
        result = advapi32.RegNotifyChangeKeyValue(
            key.handle,  # Дескриптор открытого ключа
            False,       # Не следить за подключами
            REG_NOTIFY_CHANGE_LAST_SET,  # Тип уведомления
            event,       # Дескриптор события
            True         # Асинхронное уведомление
        )

        if result != ERROR_SUCCESS:
            log(f"Ошибка регистрации уведомления: {result}")
            ctypes.windll.kernel32.CloseHandle(event)
            break

        # Ожидаем событие
        wait_result = ctypes.windll.kernel32.WaitForSingleObject(event, -1)
        if wait_result == 0:  # WAIT_OBJECT_0
            log("Обнаружено изменение в ключе реестра!")
            try:
                # Читаем текущее значение ProxyOverride
                value, _ = winreg.QueryValueEx(key, "ProxyOverride")
                log(f"Текущее значение ProxyOverride: {value}")
                
                # Проверяем, отличается ли значение от требуемого
                if value != NEW_PROXY_OVERRIDE_VALUE:
                    log("Значение ProxyOverride не соответствует требуемому. Обновляем...")
                    # Записываем новое значение
                    winreg.SetValueEx(key, "ProxyOverride", 0, winreg.REG_SZ, NEW_PROXY_OVERRIDE_VALUE)
                    log(f"Значение ProxyOverride успешно изменено на: {NEW_PROXY_OVERRIDE_VALUE}")
            except FileNotFoundError:
                log("Значение ProxyOverride не найдено. Устанавливаем новое значение...")
                try:
                    # Записываем новое значение
                    winreg.SetValueEx(key, "ProxyOverride", 0, winreg.REG_SZ, NEW_PROXY_OVERRIDE_VALUE)
                    log(f"Значение ProxyOverride успешно установлено: {NEW_PROXY_OVERRIDE_VALUE}")
                except OSError as e:
                    log(f"Ошибка записи значения: {e}")
            except OSError as e:
                log(f"Ошибка чтения или записи значения: {e}")
        else:
            log("Ошибка ожидания события.")

        # Закрываем дескриптор события
        ctypes.windll.kernel32.CloseHandle(event)

    # Закрываем ключ реестра
    winreg.CloseKey(key)

def main():
    """
    Основная функция программы.
    """
    # Выводим информацию о программе
    show_program_info()

    # Запускаем мониторинг в отдельном потоке
    monitor_thread = threading.Thread(target=monitor_registry_key, daemon=True)
    monitor_thread.start()

    log("Мониторинг запущен. Нажмите Ctrl+C для выхода.")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        log("Программа завершена.")

if __name__ == "__main__":
    main()