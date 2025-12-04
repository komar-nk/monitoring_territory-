"""
Детектор изменений на спутниковых снимках (без JSON)
"""

from typing import Optional, Dict, Any
from database import Database
from gee_client import GEEClient


class ChangeDetector:
    def __init__(self, database: Database, gee_client: GEEClient):
        self.db = database
        self.gee = gee_client

    def detect_and_save_changes(self, territory_id: int) -> Optional[Dict[str, Any]]:
        """
        Обнаружение и сохранение изменений для территории

        Args:
            territory_id: ID территории

        Returns:
            Информация об изменениях или None
        """
        # Получаем последние два изображения территории
        images = self.db.get_territory_images(territory_id, limit=2)

        if len(images) < 2:
            print(f"ℹ️  Недостаточно изображений для сравнения (нужно минимум 2)")
            return None

        new_image = images[0]  # самый новый
        old_image = images[1]  # предыдущий

        print(f"🔍 Сравнение изображений:")
        print(f"   Новое: {new_image['capture_date']}")
        print(f"   Старое: {old_image['capture_date']}")

        # Сравниваем изображения
        comparison = self.gee.compare_images(
            new_image['image_path'],
            old_image['image_path']
        )

        if 'error' in comparison:
            print(f"❌ Ошибка сравнения: {comparison['error']}")
            return None

        change_percentage = comparison['change_percentage']

        print(f"📊 Результат: {change_percentage:.2f}% изменений")
        print(f"📈 Уровень: {comparison['change_level']}")

        # Сохраняем в базу данных
        change_id = self.db.add_change(
            territory_id,
            old_image['id'],
            new_image['id'],
            change_percentage
        )

        print(f"💾 Изменения сохранены в БД с ID: {change_id}")

        # Проверяем на значительные изменения
        if change_percentage > 10:
            print(f"⚠️  ВНИМАНИЕ: Значительные изменения обнаружены!")

        return {
            'change_id': change_id,
            'change_percentage': change_percentage,
            'new_image_date': new_image['capture_date'],
            'old_image_date': old_image['capture_date']
        }