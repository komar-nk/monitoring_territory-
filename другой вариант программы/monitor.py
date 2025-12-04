"""
Автоматический мониторинг территорий (без JSON)
"""

import schedule
import time
from datetime import datetime
from database import Database
from gee_client import GEEClient
from change_detector import ChangeDetector


def monitor_territory(territory, db, gee, detector):
    """Мониторинг одной территории"""
    print(f"\n📍 {territory['name']}")

    # Получаем новое изображение
    success, path, date, message = gee.get_satellite_image(
        territory['latitude'],
        territory['longitude'],
        image_size=256
    )

    if not success:
        print(f"   ❌ Ошибка: {message}")
        return False

    print(f"   ✅ Снимок от {date}")

    # Анализируем изображение
    analysis = gee.analyze_image(path)

    # Сохраняем в базу
    import os
    file_size = os.path.getsize(path) if os.path.exists(path) else None
    cloud_cover = analysis.get('cloud_cover', {}).get('percentage') if 'error' not in analysis else None

    image_id = db.add_image(
        territory['id'], path, date,
        cloud_cover, file_size
    )

    # Проверяем облачность
    if 'error' not in analysis:
        cloud = analysis['cloud_cover']['percentage']
        print(f"   ☁️  Облачность: {cloud:.1f}%")

        if cloud > 60:
            print(f"   ⚠️  Высокая облачность")

    # Проверяем изменения
    changes = detector.detect_and_save_changes(territory['id'])
    if changes and changes['change_percentage'] > 15:
        print(f"   🚨 Значительные изменения: {changes['change_percentage']:.1f}%")

    return True


def daily_monitoring():
    """Ежедневный мониторинг"""
    print(f"\n{'=' * 60}")
    print(f"📡 АВТОМАТИЧЕСКИЙ МОНИТОРИНГ - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'=' * 60}")

    db = Database()
    gee = GEEClient()
    detector = ChangeDetector(db, gee)

    territories = db.get_all_territories()

    if not territories:
        print("\n📭 Нет активных территорий для мониторинга")
        return

    print(f"\n🔍 Найдено территорий: {len(territories)}")

    successful = 0
    for territory in territories:
        if monitor_territory(territory, db, gee, detector):
            successful += 1

    print(f"\n{'=' * 60}")
    print(f"✅ Мониторинг завершен: {successful}/{len(territories)} успешно")
    print(f"{'=' * 60}")


def schedule_monitoring(hour=10, minute=0):
    """Настройка регулярного мониторинга"""
    print(f"\n⏰ Настройка расписания...")
    print(f"   Ежедневно в {hour:02d}:{minute:02d}")

    schedule.every().day.at(f"{hour:02d}:{minute:02d}").do(daily_monitoring)

    print("\n🚀 Запуск первого мониторинга...")
    daily_monitoring()

    print(f"\n✅ Система запущена (Ctrl+C для остановки)\n")

    try:
        while True:
            schedule.run_pending()
            time.sleep(60)
    except KeyboardInterrupt:
        print("\n👋 Мониторинг остановлен")


def main():
    """Главная функция"""
    print("\n" + "=" * 60)
    print("АВТОМАТИЧЕСКИЙ МОНИТОРИНГ ТЕРРИТОРИЙ")
    print("=" * 60)

    print("\nВыберите режим:")
    print("1. Ручной запуск (сейчас)")
    print("2. Автоматический (ежедневно в 10:00)")
    print("3. Автоматический с выбором времени")

    choice = input("\nВаш выбор (1-3): ").strip()

    if choice == '1':
        daily_monitoring()
    elif choice == '2':
        schedule_monitoring(hour=10, minute=0)
    elif choice == '3':
        try:
            hour = int(input("Час (0-23): "))
            minute = int(input("Минута (0-59): "))
            schedule_monitoring(hour=hour, minute=minute)
        except ValueError:
            print("❌ Ошибка: введите числа")
    else:
        print("❌ Неверный выбор")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n👋 Выход")
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")