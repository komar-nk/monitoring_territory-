"""
Детектор изменений на спутниковых снимках
"""

import os
from typing import Optional, Dict, Any
from database import Database
from gee_client import GEEClient


class ChangeDetector:
    def __init__(self, database: Database, gee_client: GEEClient):
        self.db = database
        self.gee = gee_client
        self.notifier = None
        self.email_config = None

        # Пробуем загрузить конфигурацию email
        self._load_email_config()

    def _load_email_config(self):
        """Загрузка конфигурации email из файла .env"""
        try:
            from config_email import EmailConfig
            self.email_config = EmailConfig()
            if self.email_config.EMAIL_ENABLED:
                from notification import NotificationManager
                self.notifier = NotificationManager(self.email_config)
                print("Email уведомления настроены")
        except Exception as e:
            print(f"Email уведомления недоступны: {e}")

    def detect_and_save_changes(self, territory_id: int, send_notification: bool = True) -> Optional[Dict[str, Any]]:
        """
        Обнаружение и сохранение изменений для территории

        Args:
            territory_id: ID территории
            send_notification: Отправлять ли уведомление по email

        Returns:
            Информация об изменениях или None
        """
        # Получаем последние два изображения территории
        images = self.db.get_territory_images(territory_id, limit=2)

        if len(images) < 2:
            print(f"Недостаточно изображений для сравнения (нужно минимум 2)")
            print(f"   Найдено: {len(images)} изображений")

            # Показываем какие изображения есть
            if images:
                print(f"   Доступные изображения:")
                for i, img in enumerate(images):
                    exists = "Да" if os.path.exists(img['image_path']) else "Нет"
                    print(f"     {i + 1}. {img['capture_date']} - {img['image_path']} (Файл существует: {exists})")

            return None

        new_image = images[0]  # самый новый
        old_image = images[1]  # предыдущий

        print(f"\nСравнение изображений:")
        print(f"   Новое: {new_image['capture_date']} (ID: {new_image['id']})")
        print(f"   Старое: {old_image['capture_date']} (ID: {old_image['id']})")

        # Проверяем существование файлов
        if not os.path.exists(new_image['image_path']):
            print(f"Ошибка: Файл не найден: {new_image['image_path']}")
            return None

        if not os.path.exists(old_image['image_path']):
            print(f"Ошибка: Файл не найден: {old_image['image_path']}")
            return None

        print(f"   Путь к новому: {new_image['image_path']}")
        print(f"   Путь к старому: {old_image['image_path']}")

        # Сравниваем изображения
        comparison = self.gee.compare_images(
            new_image['image_path'],
            old_image['image_path']
        )

        if 'error' in comparison:
            print(f"Ошибка сравнения: {comparison['error']}")
            return None

        change_percentage = comparison['change_percentage']

        print(f"\nРезультат: {change_percentage:.2f}% изменений")
        print(f"Уровень: {comparison['change_level']}")
        print(f"Значимость: {comparison['significance']}")

        # Сохраняем в базу данных
        change_id = self.db.add_change(
            territory_id,
            old_image['id'],
            new_image['id'],
            change_percentage
        )

        print(f"Изменения сохранены в БД с ID: {change_id}")

        # Отправляем уведомление если нужно
        if send_notification and self._should_send_notification(change_percentage):
            self._send_notification(territory_id, change_id, comparison, new_image, old_image)

        # Проверяем на значительные изменения
        if change_percentage > 10:
            print(f"ВНИМАНИЕ: Значительные изменения обнаружены!")
        elif change_percentage > 5:
            print(f"Заметные изменения обнаружены")
        else:
            print(f"Изменения незначительны")

        return {
            'change_id': change_id,
            'change_percentage': change_percentage,
            'new_image_date': new_image['capture_date'],
            'old_image_date': old_image['capture_date'],
            'change_level': comparison['change_level'],
            'significance': comparison['significance']
        }

    def _should_send_notification(self, change_percentage: float) -> bool:
        """Проверяет, нужно ли отправлять уведомление"""
        if not self.email_config or not hasattr(self.email_config, 'CHANGE_THRESHOLD'):
            return change_percentage > 5.0  # По умолчанию 5%

        if not self.email_config.EMAIL_ENABLED:
            return False

        return change_percentage > self.email_config.CHANGE_THRESHOLD

    def _send_notification(self, territory_id: int, change_id: int,
                           comparison: Dict[str, Any], new_image: Dict[str, Any],
                           old_image: Dict[str, Any]):
        """Отправка уведомления по email"""
        try:
            if not self.notifier or not self.email_config:
                print("Уведомления отключены или не настроены")
                return

            # Получаем информацию о территории
            territory = self.db.get_territory(territory_id)
            if not territory:
                print("Ошибка: Не удалось получить информацию о территории")
                return

            # Создаем данные об изменениях
            change_data = {
                'change_percentage': comparison['change_percentage'],
                'change_level': comparison['change_level'],
                'new_image_date': new_image['capture_date'],
                'old_image_date': old_image['capture_date'],
                'confidence': 0.85,  # Уверенность в изменениях
                'change_type': comparison['change_level'],
                'significance': comparison.get('significance', 'Неизвестно')
            }

            # Получаем путь к новому изображению
            latest_image_path = new_image['image_path']

            # Проверяем существует ли файл
            if not os.path.exists(latest_image_path):
                print(f"Файл изображения не найден: {latest_image_path}")
                latest_image_path = None

            # Отправляем уведомление
            self.notifier.send_change_notification(territory, change_data, latest_image_path)
            print(f"Уведомление отправлено на {self.email_config.EMAIL_TO}")

        except Exception as e:
            print(f"Ошибка при отправке уведомления: {e}")
            import traceback
            traceback.print_exc()