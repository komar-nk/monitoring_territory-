import argparse
import time
from config import Config
from monitor import SatelliteMonitor
from database import DatabaseManager


def clear_database():
    """Очищает базу данных"""
    db = DatabaseManager()
    print("🗑️ Начинаем очистку базы данных...")

    choice = input(
        "Выберите тип очистки:\n1. Удалить все данные\n2. Полностью пересоздать базу\n3. Отмена\nВаш выбор (1-3): ").strip()

    if choice == '1':
        confirm = input("❌ УДАЛИТЬ ВСЕ ДАННЫЕ? Это нельзя отменить! (y/N): ").strip().lower()
        if confirm == 'y':
            if db.clear_all_data():
                print("✅ Все данные удалены")
            else:
                print("❌ Ошибка при удалении данных")
        else:
            print("❌ Отменено")

    elif choice == '2':
        confirm = input("❌ ПОЛНОСТЬЮ ПЕРЕСОЗДАТЬ БАЗУ? Все данные будут потеряны! (y/N): ").strip().lower()
        if confirm == 'y':
            if db.reset_database():
                print("✅ База данных пересоздана")
            else:
                print("❌ Ошибка при пересоздании базы")
        else:
            print("❌ Отменено")
    else:
        print("❌ Отменено")


def main():
    parser = argparse.ArgumentParser(description='Satellite Image Monitoring System')
    parser.add_argument('--add', '-a', nargs=3, metavar=('NAME', 'LAT', 'LON'),
                        help='Добавить место для мониторинга')
    parser.add_argument('--address', help='Адрес места (опционально)')
    parser.add_argument('--check', '-c', action='store_true',
                        help='Проверить все места на изменения')
    parser.add_argument('--status', '-s', action='store_true',
                        help='Показать статус мониторинга')
    parser.add_argument('--import', '-i', dest='import_file',
                        help='Импорт мест из JSON файла')
    parser.add_argument('--daemon', '-d', action='store_true',
                        help='Запуск в режиме демона с периодической проверкой')
    parser.add_argument('--test', '-t', action='store_true',
                        help='Протестировать систему обнаружения изменений')
    parser.add_argument('--clear', action='store_true',  # НОВАЯ ОПЦИЯ
                        help='Очистить базу данных')

    args = parser.parse_args()

    config = Config()
    monitor = SatelliteMonitor(config)

    print("🛰️  Satellite Image Monitoring System")
    print("=" * 50)

    if args.add:
        name, lat_str, lon_str = args.add
        try:
            latitude = float(lat_str)
            longitude = float(lon_str)
            monitor.add_monitoring_location(name, latitude, longitude, args.address)
        except ValueError:
            print("❌ Ошибка: координаты должны быть числами")

    elif args.import_file:
        monitor.import_locations_from_file(args.import_file)

    elif args.check:
        monitor.check_all_locations()

    elif args.status:
        monitor.show_monitoring_status()

    elif args.daemon:
        print(f" Запуск в режиме мониторинга (интервал: {config.CHECK_INTERVAL} минут)")
        print("Нажмите Ctrl+C для остановки")

        try:
            while True:
                print(f"\n🕐 {time.strftime('%Y-%m-%d %H:%M:%S')} - Начало проверки...")
                monitor.check_all_locations()
                print(f"💤 Ожидание {config.CHECK_INTERVAL} минут до следующей проверки...")
                time.sleep(config.CHECK_INTERVAL * 60)
        except KeyboardInterrupt:
            print("\n👋 Остановка мониторинга")

    elif args.test:
        monitor.test_change_detection_system()

    elif args.clear:  # НОВАЯ КОМАНДА
        clear_database()

    else:
        interactive_mode(monitor)


def interactive_mode(monitor):
    while True:
        print("\n" + "=" * 50)
        print("🎮 СИСТЕМА МОНИТОРИНГА СПУТНИКОВЫХ СНИМКОВ")
        print("1. Добавить место для мониторинга")
        print("2. Проверить все места на изменения")
        print("3. Показать статус мониторинга")
        print("4. Запуск постоянного мониторинга")
        print("5. Тест email уведомлений")
        print("6. 🧪 Тест обнаружения изменений")
        print("7. 🗑️ Очистить базу данных")  # НОВАЯ ОПЦИЯ
        print("8. Выход")
        print("=" * 50)

        choice = input("Выберите действие (1-8): ").strip()

        if choice == '1':
            name = input("Название места: ").strip()
            try:
                lat = float(input("Широта: ").strip())
                lon = float(input("Долгота: ").strip())
                address = input("Адрес (опционально): ").strip() or None
                monitor.add_monitoring_location(name, lat, lon, address)
            except ValueError:
                print("❌ Ошибка: координаты должны быть числами")

        elif choice == '2':
            monitor.check_all_locations()

        elif choice == '3':
            monitor.show_monitoring_status()

        elif choice == '4':
            print("🔃 Запуск постоянного мониторинга...")
            try:
                while True:
                    monitor.check_all_locations()
                    print(f"💤 Ожидание 30 минут до следующей проверки...")
                    time.sleep(1800)
            except KeyboardInterrupt:
                print("\n👋 Остановка мониторинга")

        elif choice == '5':
            print("📧 Тестируем email подключение...")
            if monitor.notification_manager.test_email_connection():
                print("✅ Email настроен корректно!")
            else:
                print("❌ Проблемы с email настройками")

        elif choice == '6':
            print("🧪 Запуск теста системы обнаружения изменений...")
            monitor.test_change_detection_system()

        elif choice == '7':  # НОВАЯ ОПЦИЯ
            clear_database()

        elif choice == '8':
            print("👋 Выход из программы")
            break

        else:
            print("❌ Неверный выбор")


if __name__ == "__main__":
    main()