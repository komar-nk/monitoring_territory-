from datetime import datetime
import time
import json
import os
import random
from database import DatabaseManager
from image_processor import ImageProcessor
from notification import NotificationManager


class SatelliteMonitor:
    def __init__(self, config):
        self.config = config
        self.db = DatabaseManager()
        self.image_processor = ImageProcessor(config)
        self.notification_manager = NotificationManager(config)
        print("✅ Система мониторинга инициализирована")

    def add_monitoring_location(self, name, latitude, longitude, address=None):
        return self.db.add_location(name, latitude, longitude, address)

    def clear_database(self):
        """Очищает базу данных через DatabaseManager"""
        return self.db.clear_all_data()

    def reset_database(self):
        """Полностью пересоздает базу данных"""
        return self.db.reset_database()

    def check_location(self, location):
        print(f"\n🔍 Проверяем место: {location.name}")

        try:
            # Загружаем исходное изображение
            original_image_path = self.image_processor.download_satellite_image(
                location.latitude, location.longitude
            )

            if not original_image_path:
                print(f"❌ Не удалось загрузить изображение для {location.name}")
                return {'changes_detected': False, 'error': 'Image download failed'}

            # Сохраняем ОРИГИНАЛ в БД
            original_image_hash = self.image_processor.calculate_image_hash(original_image_path)
            original_image_id = self.db.save_satellite_image(
                location.id, original_image_path, datetime.now(), original_image_hash
            )

            # Ищем предыдущее изображение (исключая только что сохраненное)
            previous_image = self.db.get_previous_image(location.id, exclude_current=original_image_id)

            # Если есть предыдущее изображение - сравниваем
            if previous_image:
                print(f"📁 Найдено предыдущее изображение: {os.path.basename(previous_image.image_path)}")

                # Решаем: добавлять ли тестовые изменения
                current_image_path = original_image_path
                add_changes = random.random() < 0.4

                if add_changes:
                    print("🔧 Добавляем тестовые изменения...")
                    changed_image_path = self.image_processor.add_random_map_changes(original_image_path)

                    # Если изменения были добавлены успешно
                    if changed_image_path != original_image_path:
                        current_image_path = changed_image_path
                        # Сохраняем измененную версию
                        current_image_hash = self.image_processor.calculate_image_hash(current_image_path)
                        current_image_id = self.db.save_satellite_image(
                            location.id, current_image_path, datetime.now(), current_image_hash
                        )
                        print(f"💾 Сохранено измененное изображение: {os.path.basename(current_image_path)}")
                    else:
                        current_image_id = original_image_id
                        current_image_path = original_image_path
                else:
                    current_image_id = original_image_id
                    current_image_path = original_image_path
                    print("🔍 Используем оригинальное изображение (без тестовых изменений)")

                # Сравниваем предыдущее изображение с текущим
                print(
                    f"🔄 Сравниваем: {os.path.basename(previous_image.image_path)} vs {os.path.basename(current_image_path)}")

                change_data = self.image_processor.detect_changes(
                    previous_image.image_path, current_image_path
                )

                print(f"📊 Результат анализа: {change_data['change_score']:.1%} изменений")

                if change_data['change_score'] > self.config.CHANGE_THRESHOLD:
                    print("🚨 Значительные изменения обнаружены!")

                    change_id = self.db.save_change_detection(
                        location_id=location.id,
                        change_score=change_data['change_score'],
                        change_type=change_data['change_type'],
                        confidence=change_data['confidence'],
                        before_image_id=previous_image.id,
                        after_image_id=current_image_id,
                        processed_image_path=change_data['result_image_path'],
                        details=json.dumps(change_data['details'])
                    )

                    # Отправляем уведомление
                    self.notification_manager.send_change_notification(
                        location, change_data, change_data['result_image_path']
                    )

                    return {
                        'changes_detected': True,
                        'change_score': change_data['change_score'],
                        'change_type': change_data['change_type'],
                        'change_id': change_id,
                        'result_image': change_data['result_image_path']
                    }
                else:
                    print("✅ Изменения незначительные")
                    return {
                        'changes_detected': False,
                        'change_score': change_data['change_score'],
                        'change_type': change_data['change_type']
                    }
            else:
                print("📝 Первый снимок этого места")
                return {'changes_detected': False, 'first_image': True}

        except Exception as e:
            print(f"❌ Ошибка проверки места {location.name}: {e}")
            return {'changes_detected': False, 'error': str(e)}

    def check_all_locations(self):
        locations = self.db.get_locations(active_only=True)

        if not locations:
            print("❌ Нет активных мест для мониторинга")
            return []

        print(f"\n🔄 Начинаем проверку {len(locations)} мест...")
        print("=" * 60)

        results = []
        changes_detected_list = []

        for i, location in enumerate(locations, 1):
            print(f"\n📍 [{i}/{len(locations)}] Проверка: {location.name}")

            result = self.check_location(location)
            result['location'] = location.name
            result['location_obj'] = location
            results.append(result)

            if result.get('changes_detected'):
                changes_detected_list.append(result)

            time.sleep(2)  # Пауза между проверками

        # Отправляем сводный отчет
        if changes_detected_list:
            self._send_summary_report(changes_detected_list, len(locations))

        print(f"\n📊 ПРОВЕРКА ЗАВЕРШЕНА:")
        print(f"   ✅ Проверено мест: {len(locations)}")
        print(f"   🚨 Обнаружено изменений: {len(changes_detected_list)}")
        print(f"   📈 Эффективность: {len(changes_detected_list) / len(locations) * 100:.1f}%")

        return results

    def _send_summary_report(self, changes_list, total_locations):
        """Отправляет сводный отчет по всем изменениям"""
        try:
            if not self.config.EMAIL_ENABLED:
                print("📧 Email уведомления отключены")
                return

            print(f"\n📧 Подготавливаем сводный отчет по {len(changes_list)} изменениям...")

            # HTML отчет
            html_content = f"""
            <html>
            <head>
                <style>
                    body {{ font-family: Arial, sans-serif; margin: 20px; }}
                    .header {{ background: #ff4444; color: white; padding: 20px; border-radius: 10px; }}
                    .summary {{ background: #f8f9fa; padding: 15px; border-radius: 5px; margin: 15px 0; }}
                    .change-item {{ border: 1px solid #ddd; padding: 15px; margin: 10px 0; border-radius: 5px; }}
                    .change-high {{ background: #fff5f5; }}
                    .change-medium {{ background: #fffbf0; }}
                    .stats {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin: 20px 0; }}
                    .stat-card {{ background: white; padding: 15px; border-radius: 5px; text-align: center; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
                </style>
            </head>
            <body>
                <div class="header">
                    <h1>🚨 СВОДНЫЙ ОТЧЕТ ОБ ИЗМЕНЕНИЯХ</h1>
                    <p>Система мониторинга спутниковых снимков</p>
                </div>

                <div class="stats">
                    <div class="stat-card">
                        <h3>📊 Всего мест</h3>
                        <h2>{total_locations}</h2>
                    </div>
                    <div class="stat-card">
                        <h3>🚨 С изменениями</h3>
                        <h2 style="color: red;">{len(changes_list)}</h2>
                    </div>
                    <div class="stat-card">
                        <h3>📈 Эффективность</h3>
                        <h2>{(len(changes_list) / total_locations * 100):.1f}%</h2>
                    </div>
                </div>

                <div class="summary">
                    <h3>📋 Детали изменений:</h3>
            """

            for i, change in enumerate(changes_list, 1):
                location = change['location_obj']
                change_score = change['change_score']
                change_type = change['change_type']

                # Определяем уровень серьезности
                if change_score > 0.3:
                    change_class = "change-high"
                    emoji = "🔴"
                elif change_score > 0.1:
                    change_class = "change-medium"
                    emoji = "🟡"
                else:
                    change_class = ""
                    emoji = "🟢"

                html_content += f"""
                    <div class="change-item {change_class}">
                        <h4>{emoji} {i}. {location.name}</h4>
                        <p><strong>📌 Координаты:</strong> {location.latitude:.4f}, {location.longitude:.4f}</p>
                        <p><strong>📊 Изменения:</strong> <span style="color: red; font-weight: bold;">{change_score:.1%}</span></p>
                        <p><strong>🎯 Тип изменений:</strong> {change_type}</p>
                        <p><strong>✅ Уверенность:</strong> {change.get('confidence', 0):.1%}</p>
                """

                if location.address:
                    html_content += f'<p><strong>🏠 Адрес:</strong> {location.address}</p>'

                html_content += "</div>"

            html_content += """
                </div>
                <p><em>Отчет сгенерирован автоматически • {}</em></p>
            </body>
            </html>
            """.format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

            # Текстовая версия
            text_content = f"""
🚨 СВОДНЫЙ ОТЧЕТ ОБ ИЗМЕНЕНИЯХ

📊 Статистика:
• Всего проверено мест: {total_locations}
• Мест с изменениями: {len(changes_list)}
• Эффективность обнаружения: {(len(changes_list) / total_locations * 100):.1f}%

📋 Детали изменений:
"""

            for i, change in enumerate(changes_list, 1):
                location = change['location_obj']
                text_content += f"""
{i}. {location.name}
   📌 Координаты: {location.latitude:.4f}, {location.longitude:.4f}
   📊 Изменения: {change['change_score']:.1%}
   🎯 Тип: {change['change_type']}
   ✅ Уверенность: {change.get('confidence', 0):.1%}
"""
                if location.address:
                    text_content += f"   🏠 Адрес: {location.address}\n"

            text_content += f"\nОтчет сгенерирован: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

            # Отправляем отчет
            self.notification_manager.send_summary_report(
                html_content,
                text_content,
                len(changes_list),  # changes_count
                total_locations     # total_locations
            )

        except Exception as e:
            print(f"❌ Ошибка при отправке сводного отчета: {e}")

    def show_monitoring_status(self):
        locations = self.db.get_locations(active_only=True)

        print(f"\n{'=' * 60}")
        print("📊 СТАТУС МОНИТОРИНГА")
        print(f"{'=' * 60}")

        if not locations:
            print("❌ Нет активных мест для мониторинга")
            return

        total_changes = 0
        for location in locations:
            latest_image = self.db.get_latest_image(location.id)
            last_check = latest_image.capture_date.strftime('%Y-%m-%d %H:%M') if latest_image else "Никогда"

            changes = self.db.get_change_history(location.id, limit=1)
            last_change = changes[0].detection_date.strftime('%Y-%m-%d %H:%M') if changes else "Не обнаружены"

            if changes:
                total_changes += 1

            print(f"\n📍 {location.name}")
            print(f"   📌 Координаты: {location.latitude:.4f}, {location.longitude:.4f}")
            print(f"   🕐 Последняя проверка: {last_check}")
            print(f"   🔄 Последние изменения: {last_change}")
            if location.address:
                print(f"   🏠 Адрес: {location.address}")

        print(f"\n📈 СТАТИСТИКА:")
        print(f"   📊 Всего мест: {len(locations)}")
        print(f"   🚨 Мест с изменениями: {total_changes}")
        print(f"   📈 Активность: {(total_changes / len(locations) * 100 if locations else 0):.1f}%")

    def import_locations_from_file(self, file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                locations_data = json.load(f)

            imported_count = 0
            for loc_data in locations_data:
                location_id = self.add_monitoring_location(
                    name=loc_data['name'],
                    latitude=loc_data['latitude'],
                    longitude=loc_data['longitude'],
                    address=loc_data.get('address')
                )
                if location_id:
                    imported_count += 1

            print(f"✅ Импортировано {imported_count} мест")
            return imported_count

        except Exception as e:
            print(f"❌ Ошибка импорта: {e}")
            return 0

    def test_change_detection_system(self):
        """Тестирует систему обнаружения изменений на всех локациях"""
        print(f"\n{'=' * 60}")
        print("🧪 ЗАПУСК ТЕСТА СИСТЕМЫ ОБНАРУЖЕНИЯ ИЗМЕНЕНИЙ")
        print(f"{'=' * 60}")

        locations = self.db.get_locations(active_only=True)

        if not locations:
            print("❌ Нет активных мест для тестирования")
            return

        test_results = []

        for location in locations:
            print(f"\n🔬 Тестируем: {location.name}")
            result = self.image_processor.test_change_detection(location)

            if result:
                test_results.append({
                    'location': location.name,
                    'change_score': result['change_score'],
                    'change_type': result['change_type'],
                    'confidence': result['confidence']
                })

        # Вывод результатов теста
        print(f"\n{'=' * 60}")
        print("📊 РЕЗУЛЬТАТЫ ТЕСТИРОВАНИЯ")
        print(f"{'=' * 60}")

        for i, result in enumerate(test_results, 1):
            print(f"{i}. {result['location']}:")
            print(f"   📊 Изменения: {result['change_score']:.1%}")
            print(f"   🎯 Тип: {result['change_type']}")
            print(f"   ✅ Уверенность: {result['confidence']:.1%}")

        print(f"\n🎯 ИТОГО: Протестировано {len(test_results)} из {len(locations)} мест")

        return test_results