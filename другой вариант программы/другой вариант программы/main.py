"""
Главное меню системы мониторинга
"""

import sys
import os
from pathlib import Path

# Добавляем текущую директорию в путь для импортов
sys.path.append(str(Path(__file__).parent))

from database import Database
from gee_client import GEEClient
from change_detector import ChangeDetector


def print_header():
    """Печать заголовка"""
    print("\n" + "=" * 60)
    print("СИСТЕМА МОНИТОРИНГА СПУТНИКОВЫХ ИЗОБРАЖЕНИЙ")
    print("=" * 60)


def print_territories_menu():
    """Печать меню управления территориями"""
    print("\nУПРАВЛЕНИЕ ТЕРРИТОРИЯМИ:")
    print("1. Добавить новую территорию")
    print("2. Просмотреть все территории")
    print("3. Редактировать территорию")
    print("4. Удалить территорию")
    print("5. Просмотреть изображения территории")
    print("0. Назад")


def print_menu():
    """Печать главного меню"""
    print("\nГЛАВНОЕ МЕНЮ:")
    print("1. Управление территориями")
    print("2. Получить спутниковое изображение")
    print("3. Анализ изображений")
    print("4. Мониторинг и детекция изменений")
    print("5. Настройки и информация")
    print("0. Выход")


class SatelliteMonitorApp:
    def __init__(self):
        self.db = Database()
        self.gee_client = GEEClient()
        self.change_detector = ChangeDetector(self.db, self.gee_client)

    def add_territory(self):
        """Добавление новой территории"""
        print("\n" + "-" * 60)
        print("ДОБАВЛЕНИЕ НОВОЙ ТЕРРИТОРИИ")
        print("-" * 60)

        name = input("\nНазвание территории: ").strip()
        if not name:
            print("Ошибка: Название не может быть пустым")
            return

        try:
            lat = float(input("Широта (например, 55.7558): "))
            lon = float(input("Долгота (например, 37.6173): "))
        except ValueError:
            print("Ошибка: введите числовые значения координат")
            return

        description = input("Описание (необязательно): ").strip()

        territory_id = self.db.add_territory(name, lat, lon, description)
        print(f"\nТерритория '{name}' добавлена с ID: {territory_id}")

    def view_territories(self):
        """Просмотр всех территорий"""
        print("\n" + "-" * 60)
        print("ВСЕ ТЕРРИТОРИИ")
        print("-" * 60)

        territories = self.db.get_all_territories()

        if not territories:
            print("\nТерритории не найдены")
            return

        print(f"\nНайдено территорий: {len(territories)}\n")

        for i, territory in enumerate(territories, 1):
            print(f"{i}. {territory['name']}")
            print(f"   Координаты: {territory['latitude']}, {territory['longitude']}")
            if territory['description']:
                print(f"   Описание: {territory['description']}")

            latest_image = self.db.get_latest_image(territory['id'])
            if latest_image:
                print(f"   Последний снимок: {latest_image['capture_date']}")
                print(f"   Изображений: {len(self.db.get_territory_images(territory['id']))}")
            else:
                print(f"   Нет снимков")
            print()

    def edit_territory(self):
        """Редактирование территории"""
        territories = self.db.get_all_territories()

        if not territories:
            print("\nНет территорий для редактирования")
            return

        print("\nВыберите территорию для редактирования:")
        for i, territory in enumerate(territories, 1):
            print(f"{i}. {territory['name']}")

        try:
            choice = int(input("\nНомер территории: "))
            if choice < 1 or choice > len(territories):
                print("Неверный выбор")
                return
        except ValueError:
            print("Введите число")
            return

        territory = territories[choice - 1]

        print(f"\nРедактирование: {territory['name']}")
        print("(оставьте пустым, чтобы не менять)")

        new_name = input(f"Новое название [{territory['name']}]: ").strip()
        new_lat = input(f"Новая широта [{territory['latitude']}]: ").strip()
        new_lon = input(f"Новая долгота [{territory['longitude']}]: ").strip()
        new_desc = input(f"Новое описание [{territory['description'] or 'нет'}]: ").strip()

        updates = {}
        if new_name:
            updates['name'] = new_name
        if new_lat:
            try:
                updates['latitude'] = float(new_lat)
            except ValueError:
                print("Неверный формат широты")
                return
        if new_lon:
            try:
                updates['longitude'] = float(new_lon)
            except ValueError:
                print("Неверный формат долготы")
                return
        if new_desc:
            updates['description'] = new_desc

        if updates:
            success = self.db.update_territory(territory['id'], **updates)
            if success:
                print(f"\nТерритория обновлена")
            else:
                print(f"\nОшибка при обновлении")
        else:
            print(f"\nИзменений нет")

    def delete_territory(self):
        """Удаление территории"""
        territories = self.db.get_all_territories()

        if not territories:
            print("\nНет территорий для удаления")
            return

        print("\nВыберите территорию для удаления:")
        for i, territory in enumerate(territories, 1):
            print(f"{i}. {territory['name']}")

        try:
            choice = int(input("\nНомер территории: "))
            if choice < 1 or choice > len(territories):
                print("Неверный выбор")
                return
        except ValueError:
            print("Введите число")
            return

        territory = territories[choice - 1]

        confirm = input(f"\nВы уверены, что хотите удалить '{territory['name']}'? (y/n): ").lower()
        if confirm == 'y':
            success = self.db.delete_territory(territory['id'])
            if success:
                print(f"\nТерритория '{territory['name']}' удалена")
            else:
                print(f"\nОшибка при удалении")
        else:
            print("\nУдаление отменено")

    def view_territory_images(self):
        """Просмотр изображений территории"""
        territories = self.db.get_all_territories()

        if not territories:
            print("\nНет территорий")
            return

        print("\nВыберите территорию:")
        for i, territory in enumerate(territories, 1):
            print(f"{i}. {territory['name']}")

        try:
            choice = int(input("\nНомер территории: "))
            if choice < 1 or choice > len(territories):
                print("Неверный выбор")
                return
        except ValueError:
            print("Введите число")
            return

        territory = territories[choice - 1]
        images = self.db.get_territory_images(territory['id'], limit=20)

        print(f"\nИзображения территории: {territory['name']}")
        print("-" * 40)

        if not images:
            print("Изображений не найдено")
            return

        for i, image in enumerate(images, 1):
            print(f"\n{i}. Дата: {image['capture_date']}")
            print(f"   Путь: {image['image_path']}")
            print(f"   ID: {image['id']}")
            if image['cloud_cover']:
                print(f"   Облачность: {image['cloud_cover']}%")
            if image['file_size']:
                print(f"   Размер: {image['file_size'] / 1024:.1f} KB")

            # Проверяем существует ли файл
            if os.path.exists(image['image_path']):
                print(f"   Статус файла: Существует")
            else:
                print(f"   Статус файла: Отсутствует")

    def get_satellite_image(self):
        """Получение спутникового изображения"""
        print("\n" + "-" * 60)
        print("ПОЛУЧЕНИЕ СПУТНИКОВОГО ИЗОБРАЖЕНИЯ")
        print("-" * 60)

        print("\nВыберите источник координат:")
        print("1. Выбрать из сохраненных территорий")
        print("2. Ввести координаты вручную (не сохранять)")
        print("3. Ввести координаты и сохранить как новую территорию")

        try:
            source_choice = int(input("\nВаш выбор: "))
        except ValueError:
            print("Ошибка: Введите число")
            return

        territory_id = None
        territory_name = ""

        if source_choice == 1:
            territories = self.db.get_all_territories()
            if not territories:
                print("Ошибка: Нет сохраненных территорий")
                return

            print("\nВыберите территорию:")
            for i, territory in enumerate(territories, 1):
                print(f"{i}. {territory['name']}")

            try:
                choice = int(input("\nНомер территории: "))
                if choice < 1 or choice > len(territories):
                    print("Ошибка: Неверный выбор")
                    return
            except ValueError:
                print("Ошибка: Введите число")
                return

            territory = territories[choice - 1]
            lat, lon = territory['latitude'], territory['longitude']
            territory_id = territory['id']
            territory_name = territory['name']

        elif source_choice == 2:
            try:
                lat = float(input("\nШирота: "))
                lon = float(input("Долгота: "))
                territory_name = f"Ручной ввод ({lat:.4f}, {lon:.4f})"
            except ValueError:
                print("Ошибка: Неверный формат координат")
                return

        elif source_choice == 3:
            try:
                name = input("\nНазвание новой территории: ").strip()
                if not name:
                    print("Ошибка: Название не может быть пустым")
                    return

                lat = float(input("Широта: "))
                lon = float(input("Долгота: "))
                description = input("Описание (необязательно): ").strip()

                # Сохраняем как новую территорию
                territory_id = self.db.add_territory(name, lat, lon, description)
                territory_name = name
                print(f"Территория '{name}' сохранена с ID: {territory_id}")

            except ValueError:
                print("Ошибка: Неверный формат координат")
                return
        else:
            print("Ошибка: Неверный выбор")
            return

        date_input = input("Дата (YYYY-MM-DD, Enter для сегодня): ").strip()
        date = date_input if date_input else None

        print("\nЗагрузка изображения...")

        success, path, capture_date, message = self.gee_client.get_satellite_image(
            lat, lon, date
        )

        if success:
            print(f"\nУСПЕХ!")
            print(f"   Территория: {territory_name}")
            print(f"   Файл: {path}")
            print(f"   Дата съемки: {capture_date}")

            # Анализируем изображение
            analysis = self.gee_client.analyze_image(path)

            if 'error' not in analysis:
                print(f"   Облачность: {analysis['cloud_cover']['percentage']:.1f}%")
                print(f"   Яркость: {analysis['brightness']['mean']:.1f}")

            # Сохраняем в базу всегда, даже если territory_id = None
            if territory_id is None:
                # Создаем временную территорию для ручного ввода
                territory_id = self.db.add_territory(
                    territory_name,
                    lat,
                    lon,
                    "Временная территория (ручной ввод)"
                )
                print(f"   Создана временная территория с ID: {territory_id}")

            # Сохраняем изображение в БД
            file_size = os.path.getsize(path) if os.path.exists(path) else None
            cloud_cover = analysis.get('cloud_cover', {}).get('percentage') if 'error' not in analysis else None

            image_id = self.db.add_image(
                territory_id, path, capture_date,
                cloud_cover, file_size
            )
            print(f"   Сохранено в БД с ID: {image_id}")

            # Предлагаем проанализировать изменения если есть предыдущие изображения
            previous_images = self.db.get_territory_images(territory_id, limit=1)
            if len(previous_images) > 1:
                analyze_changes = input("\nПроверить изменения по сравнению с предыдущим снимком? (y/n): ").lower()
                if analyze_changes == 'y':
                    self.change_detector.detect_and_save_changes(territory_id)
            else:
                print(f"   Это первое изображение для этой территории")
        else:
            print(f"\nОШИБКА: {message}")

    def analyze_single_image(self):
        """Анализ одного изображения"""
        print("\n" + "-" * 60)
        print("АНАЛИЗ ИЗОБРАЖЕНИЯ")
        print("-" * 60)

        image_path = input("\nПуть к изображению: ").strip()

        if not Path(image_path).exists():
            print(f"Ошибка: Файл не существует: {image_path}")
            return

        print("\nАнализ...")
        analysis = self.gee_client.analyze_image(image_path)

        if 'error' in analysis:
            print(f"Ошибка: {analysis['error']}")
        else:
            print(f"\nРЕЗУЛЬТАТЫ:")
            print(f"   Размер: {analysis['dimensions']['width']}x{analysis['dimensions']['height']}")
            print(f"   Облачность: {analysis['cloud_cover']['percentage']:.1f}%")
            print(f"   Оценка облачности: {analysis['cloud_cover']['assessment']}")
            print(f"   Яркость: {analysis['brightness']['mean']:.1f}")
            print(f"   Контрастность: {analysis['brightness']['max'] - analysis['brightness']['min']:.1f}")
            print(f"   Резкость: {analysis['sharpness']['assessment']}")

    def compare_images(self):
        """Сравнение двух изображений"""
        print("\n" + "-" * 60)
        print("СРАВНЕНИЕ ИЗОБРАЖЕНИЙ")
        print("-" * 60)

        path1 = input("\nПуть к первому изображению: ").strip()
        path2 = input("Путь ко второму изображению: ").strip()

        if not Path(path1).exists() or not Path(path2).exists():
            print("Ошибка: Один или оба файла не существуют")
            return

        print("\nСравнение...")
        comparison = self.gee_client.compare_images(path1, path2)

        if 'error' in comparison:
            print(f"Ошибка: {comparison['error']}")
        else:
            print(f"\nРЕЗУЛЬТАТЫ СРАВНЕНИЯ:")
            print(f"   Измененные пиксели: {comparison['changed_pixels']:,}")
            print(f"   Всего пикселей: {comparison['total_pixels']:,}")
            print(f"   Процент изменений: {comparison['change_percentage']:.2f}%")
            print(f"   Уровень изменений: {comparison['change_level']}")

    def check_territory_changes(self):
        """Проверка изменений на территории"""
        territories = self.db.get_all_territories()

        if not territories:
            print("\nНет территорий")
            return

        print("\nВыберите территорию:")
        for i, territory in enumerate(territories, 1):
            # Получаем количество изображений для территории
            images = self.db.get_territory_images(territory['id'])
            print(f"{i}. {territory['name']} ({len(images)} изображений)")

        try:
            choice = int(input("\nНомер территории: "))
            if choice < 1 or choice > len(territories):
                print("Ошибка: Неверный выбор")
                return
        except ValueError:
            print("Ошибка: Введите число")
            return

        territory = territories[choice - 1]

        # Проверяем сколько изображений есть
        images = self.db.get_territory_images(territory['id'])
        print(f"\nПроверка изменений: {territory['name']}")
        print(f"   Найдено изображений: {len(images)}")

        if len(images) < 2:
            print(f"   Ошибка: Недостаточно изображений для сравнения")
            print(f"   Нужно минимум 2 изображения, сейчас {len(images)}")
            print(f"   Получите новое изображение через меню 'Получить спутниковое изображение'")
            return

        # Проверяем существование файлов
        for i, img in enumerate(images[:2]):
            if not os.path.exists(img['image_path']):
                print(f"   Ошибка: Файл не найден: {img['image_path']}")
                print(f"   Возможно файл был удален или перемещен")
                return

        self.change_detector.detect_and_save_changes(territory['id'])

    def view_change_history(self):
        """Просмотр истории изменений"""
        changes = self.db.get_recent_changes(limit=20)

        if not changes:
            print("\nИзменений не обнаружено")
            return

        print(f"\nИСТОРИЯ ИЗМЕНЕНИЙ (последние {len(changes)}):")
        print("-" * 60)

        for change in changes:
            print(f"\nТерритория: {change['territory_name']}")
            print(f"Обнаружено: {change['detected_at']}")
            print(f"Изменения: {change['change_percentage']:.2f}%")
            print()

    def system_info(self):
        """Информация о системе"""
        print("\n" + "-" * 60)
        print("ИНФОРМАЦИЯ О СИСТЕМЕ")
        print("-" * 60)

        # Статистика из БД
        stats = self.db.get_statistics()
        print(f"\nСТАТИСТИКА:")
        print(f"   Активных территорий: {stats['territories']}")
        print(f"   Всего изображений: {stats['images']}")
        print(f"   Обнаружено изменений: {stats['changes']}")
        print(f"   Последнее изображение: {stats['last_image_date'] or 'нет'}")
        print(f"   Последнее изменение: {stats['last_change_date'] or 'нет'}")

        # Информация о кэше
        cache_info = self.gee_client.get_cache_info()
        print(f"\nКЭШ:")
        print(f"   Изображений в кэше: {cache_info.get('image_count', 0)}")
        print(f"   Размер кэша: {cache_info.get('total_size_mb', 0)} MB")
        print(f"   Всего запросов: {cache_info.get('request_count', 0)}")

        # Информация о email уведомлениях
        print(f"\nEMAIL УВЕДОМЛЕНИЯ:")
        if hasattr(self.change_detector, 'email_config') and self.change_detector.email_config:
            if self.change_detector.email_config.EMAIL_ENABLED:
                print(f"   Статус: Включены")
                print(f"   Отправитель: {self.change_detector.email_config.EMAIL_FROM}")
                print(f"   Получатель: {self.change_detector.email_config.EMAIL_TO}")
                print(f"   Порог: {self.change_detector.email_config.CHANGE_THRESHOLD}%")
            else:
                print(f"   Статус: Выключены")
        else:
            print(f"   Статус: Не настроены")

        # Детальная информация о территориях
        territories = self.db.get_all_territories()
        print(f"\nДЕТАЛЬНАЯ ИНФОРМАЦИЯ О ТЕРРИТОРИЯХ:")
        for territory in territories:
            images = self.db.get_territory_images(territory['id'])
            print(f"   {territory['name']}: {len(images)} изображений")

        # Информация о модулях
        print(f"\nМОДУЛИ:")
        print(f"   Google Earth Engine: {'Да' if hasattr(self.gee_client, 'ee') else 'Нет'}")
        print(f"   OpenCV: {'Да' if self.gee_client.cv2 is not None else 'Нет'}")
        print(f"   Pillow (PIL): {'Да'}")
        print(f"   Requests: {'Да'}")

    def clear_cache(self):
        """Очистка кэша"""
        print("\n" + "-" * 60)
        print("ОЧИСТКА КЭША")
        print("-" * 60)

        confirm = input("\nВНИМАНИЕ: Все изображения в кэше будут удалены. Продолжить? (y/n): ").lower()

        if confirm == 'y':
            result = self.gee_client.clear_cache()
            print(f"\n{result}")
        else:
            print("\nОчистка отменена")

    def setup_email_notifications(self):
        """Настройка email уведомлений"""
        print("\n" + "-" * 60)
        print("НАСТРОЙКА EMAIL УВЕДОМЛЕНИЙ")
        print("-" * 60)

        try:
            from config_email import setup_email_notifications
            config = setup_email_notifications()

            # Обновляем детектор изменений с новыми настройками
            self.change_detector = ChangeDetector(self.db, self.gee_client)

            if config.EMAIL_ENABLED:
                print("\nEmail уведомления активированы!")
                print(f"   Получатель: {config.EMAIL_TO}")
                print(f"   Порог изменений: {config.CHANGE_THRESHOLD}%")
                print(f"\nТеперь при значительных изменениях (> {config.CHANGE_THRESHOLD}%)")
                print(f"   уведомления будут приходить на: {config.EMAIL_TO}")
        except Exception as e:
            print(f"Ошибка настройки email: {e}")

    def run_monitor_all(self):
        """Запуск мониторинга всех территорий"""
        print("\n" + "-" * 60)
        print("МОНИТОРИНГ ВСЕХ ТЕРРИТОРИЙ")
        print("-" * 60)

        territories = self.db.get_all_territories()

        if not territories:
            print("\nНет активных территорий")
            return

        print(f"\nНайдено территорий: {len(territories)}")

        for territory in territories:
            print(f"\nТерритория: {territory['name']}")

            success, path, date, message = self.gee_client.get_satellite_image(
                territory['latitude'], territory['longitude']
            )

            if success:
                print(f"   Получен снимок от {date}")

                # Анализируем
                analysis = self.gee_client.analyze_image(path)
                if 'error' not in analysis:
                    cloud = analysis['cloud_cover']['percentage']
                    print(f"   Облачность: {cloud:.1f}%")

                # Сохраняем в БД
                file_size = os.path.getsize(path) if os.path.exists(path) else None
                cloud_cover = analysis.get('cloud_cover', {}).get('percentage') if 'error' not in analysis else None

                self.db.add_image(
                    territory['id'], path, date,
                    cloud_cover, file_size
                )

                # Проверяем изменения
                self.change_detector.detect_and_save_changes(territory['id'])
            else:
                print(f"   Ошибка: {message}")

        print(f"\nМониторинг завершен")

    def territories_menu(self):
        """Меню управления территориями"""
        while True:
            print_territories_menu()
            choice = input("\nВыберите опцию: ").strip()

            if choice == '0':
                break
            elif choice == '1':
                self.add_territory()
            elif choice == '2':
                self.view_territories()
            elif choice == '3':
                self.edit_territory()
            elif choice == '4':
                self.delete_territory()
            elif choice == '5':
                self.view_territory_images()
            else:
                print("Неверный выбор")

            input("\nНажмите Enter чтобы продолжить...")

    def analysis_menu(self):
        """Меню анализа"""
        while True:
            print("\nАНАЛИЗ ИЗОБРАЖЕНИЙ:")
            print("1. Проанализировать изображение")
            print("2. Сравнить два изображения")
            print("0. Назад")

            choice = input("\nВыберите опцию: ").strip()

            if choice == '0':
                break
            elif choice == '1':
                self.analyze_single_image()
            elif choice == '2':
                self.compare_images()
            else:
                print("Неверный выбор")

            input("\nНажмите Enter чтобы продолжить...")

    def monitoring_menu(self):
        """Меню мониторинга"""
        while True:
            print("\nМОНИТОРИНГ:")
            print("1. Проверить изменения на территории")
            print("2. Запустить мониторинг всех территорий")
            print("3. Просмотреть историю изменений")
            print("0. Назад")

            choice = input("\nВыберите опцию: ").strip()

            if choice == '0':
                break
            elif choice == '1':
                self.check_territory_changes()
            elif choice == '2':
                self.run_monitor_all()
            elif choice == '3':
                self.view_change_history()
            else:
                print("Неверный выбор")

            input("\nНажмите Enter чтобы продолжить...")

    def settings_menu(self):
        """Меню настроек"""
        while True:
            print("\nНАСТРОЙКИ:")
            print("1. Информация о системе")
            print("2. Настройка email уведомлений")
            print("3. Очистить кэш")
            print("0. Назад")

            choice = input("\nВыберите опцию: ").strip()

            if choice == '0':
                break
            elif choice == '1':
                self.system_info()
            elif choice == '2':
                self.setup_email_notifications()
            elif choice == '3':
                self.clear_cache()
            else:
                print("Неверный выбор")

            input("\nНажмите Enter чтобы продолжить...")

    def run(self):
        """Запуск главного меню"""
        print_header()

        while True:
            print_menu()

            try:
                choice = input("\nВыберите опцию (0-5): ").strip()

                if choice == '0':
                    print("\nВыход из программы. До свидания!")
                    break

                elif choice == '1':
                    self.territories_menu()
                elif choice == '2':
                    self.get_satellite_image()
                elif choice == '3':
                    self.analysis_menu()
                elif choice == '4':
                    self.monitoring_menu()
                elif choice == '5':
                    self.settings_menu()
                else:
                    print("Неверный выбор. Попробуйте снова.")

            except KeyboardInterrupt:
                print("\nПрограмма прервана пользователем")
                break
            except Exception as e:
                print(f"\nНеожиданная ошибка: {e}")
                import traceback
                traceback.print_exc()


def main():
    """Главная функция"""
    try:
        app = SatelliteMonitorApp()
        app.run()
    except KeyboardInterrupt:
        print("\nВыход")
    except Exception as e:
        print(f"\nКритическая ошибка: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()