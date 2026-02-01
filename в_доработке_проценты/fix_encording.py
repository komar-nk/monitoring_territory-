# fix_encoding.py
import os
import sys
import locale
import shutil
from pathlib import Path, PureWindowsPath


def setup_encoding():
    """Настроить правильную кодировку для Windows"""
    if sys.platform == "win32":
        # Пробуем разные кодировки
        for encoding in ['utf-8', 'cp1251', 'cp1252', 'cp866']:
            try:
                sys.stdout.reconfigure(encoding=encoding)
                sys.stderr.reconfigure(encoding=encoding)
                break
            except:
                pass

        # Устанавливаем locale
        locale.setlocale(locale.LC_ALL, '')

        # Для Windows используем mbcs (multi-byte character system)
        os.environ['PYTHONIOENCODING'] = 'utf-8'
        os.environ['PYTHONUTF8'] = '1'


def get_correct_path(path_str):
    """Получить правильный путь для Windows"""
    try:
        # Пробуем разные подходы
        if isinstance(path_str, str):
            # Подход 1: Используем pathlib
            path = Path(path_str)
            # Подход 2: Если есть кириллица, кодируем/декодируем
            try:
                return str(path.resolve())
            except:
                # Подход 3: Используем Windows путь
                return str(PureWindowsPath(path_str))
    except:
        return path_str
    return path_str


def test_encoding():
    """Тест кодировки"""
    print("=" * 60)
    print("ТЕСТ КОДИРОВКИ")
    print("=" * 60)

    # Тест 1: Вывод русских символов
    print(f"1. Русский текст: Леснитый")

    # Тест 2: Чтение файлов
    test_dir = "satellite_images/original"
    if os.path.exists(test_dir):
        print(f"\n2. Файлы в {test_dir}:")
        for file in os.listdir(test_dir):
            print(f"   - {file}")

    # Тест 3: Кодировка системы
    print(f"\n3. Системная кодировка:")
    print(f"   - sys.getfilesystemencoding(): {sys.getfilesystemencoding()}")
    print(f"   - locale.getpreferredencoding(): {locale.getpreferredencoding()}")
    print(f"   - sys.stdout.encoding: {sys.stdout.encoding}")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    setup_encoding()
    test_encoding()