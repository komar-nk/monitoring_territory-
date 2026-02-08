
"""
Скрипт для исправления базы данных
"""
import sqlite3
import os
from pathlib import Path


def fix_database():
    """Добавить недостающие столбцы в таблицу changes"""
    db_path = Path("satellite_monitor.db")

    if not db_path.exists():
        print(" База данных не найдена!")
        return False

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        print(" Проверяю структуру базы данных...")

        # Проверяем существующие столбцы в таблице changes
        cursor.execute("PRAGMA table_info(changes)")
        columns = cursor.fetchall()

        print(" Существующие столбцы в таблице changes:")
        for col in columns:
            print(f"  - {col[1]} ({col[2]})")

        column_names = [col[1] for col in columns]

        # Список столбцов, которые должны быть
        required_columns = [
            'change_data',  # Для хранения JSON данных
            'comparison_type'  # Тип сравнения (auto/manual)
        ]

        # Добавляем недостающие столбцы
        for col_name in required_columns:
            if col_name not in column_names:
                print(f"➕ Добавляю столбец '{col_name}'...")

                if col_name == 'change_data':
                    cursor.execute(f"ALTER TABLE changes ADD COLUMN {col_name} TEXT")
                elif col_name == 'comparison_type':
                    cursor.execute(f"ALTER TABLE changes ADD COLUMN {col_name} TEXT DEFAULT 'auto'")

        conn.commit()

        # Проверяем результат
        cursor.execute("PRAGMA table_info(changes)")
        new_columns = cursor.fetchall()

        print("\n База данных обновлена! Новая структура:")
        for col in new_columns:
            print(f"  - {col[1]} ({col[2]})")

        conn.close()
        return True

    except Exception as e:
        print(f" Ошибка обновления базы данных: {e}")
        return False


if __name__ == "__main__":
    print("🛠️  Исправление структуры базы данных...")
    print("=" * 60)

    # Создаем резервную копию
    import shutil

    backup_path = "satellite_monitor_backup.db"
    if os.path.exists("satellite_monitor.db"):
        shutil.copy2("satellite_monitor.db", backup_path)
        print(f" Создана резервная копия: {backup_path}")

    success = fix_database()

    print("=" * 60)
    if success:
        print(" Исправление завершено успешно!")
    else:
        print(" Исправление не удалось!")

    input("Нажмите Enter для выхода...")