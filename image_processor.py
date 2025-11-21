import math
import cv2
import hashlib
import os
import random
import requests
from datetime import datetime
import numpy as np


class ImageProcessor:
    def __init__(self, config):
        self.config = config
        self.setup_directories()

    def setup_directories(self):
        os.makedirs(self.config.IMAGE_STORAGE, exist_ok=True)
        os.makedirs(self.config.PROCESSED_IMAGES, exist_ok=True)
        print("✅ Директории созданы")

    @staticmethod
    def calculate_image_hash(image_path):
        try:
            with open(image_path, 'rb') as f:
                return hashlib.md5(f.read()).hexdigest()
        except Exception as e:
            print(f"❌ Ошибка при расчете хеша: {e}")
            return None

    def download_satellite_image(self, latitude, longitude, date=None):
        if date is None:
            date = datetime.now()

        filename = f"map_{latitude:.4f}_{longitude:.4f}_{date.strftime('%Y%m%d_%H%M')}.jpg"
        image_path = os.path.join(self.config.IMAGE_STORAGE, filename)

        # Если файл уже существует, используем его
        if os.path.exists(image_path):
            print(f"📁 Используем существующий файл: {image_path}")
            return image_path

        try:
            # ТОЛЬКО tile.openstreetmap.org
            zoom = 15

            # Конвертируем координаты в tile coordinates
            lat_rad = math.radians(latitude)
            n = 2.0 ** zoom
            xtile = int((longitude + 180.0) / 360.0 * n)
            ytile = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)

            urls_to_try = [
                {
                    'url': f'https://tile.openstreetmap.org/{zoom}/{xtile}/{ytile}.png',
                    'params': {}
                },
                {
                    'url': f'https://a.tile.openstreetmap.org/{zoom}/{xtile}/{ytile}.png',
                    'params': {}
                },
                {
                    'url': f'https://b.tile.openstreetmap.org/{zoom}/{xtile}/{ytile}.png',
                    'params': {}
                },
                {
                    'url': f'https://c.tile.openstreetmap.org/{zoom}/{xtile}/{ytile}.png',
                    'params': {}
                }
            ]

            for service in urls_to_try:
                try:
                    print(f"🔄 Пробуем загрузить с {service['url']}...")

                    response = requests.get(
                        service['url'],
                        params=service['params'],
                        timeout=15,
                        headers={
                            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                        }
                    )

                    if response.status_code == 200 and len(response.content) > 1000:
                        # Сохраняем временный PNG
                        temp_path = image_path.replace('.jpg', '_temp.png')
                        with open(temp_path, 'wb') as f:
                            f.write(response.content)

                        # Конвертируем в JPG
                        img = cv2.imread(temp_path)
                        if img is not None:
                            # Увеличиваем размер до 640x480
                            img_resized = cv2.resize(img, (640, 480))
                            cv2.imwrite(image_path, img_resized, [cv2.IMWRITE_JPEG_QUALITY, 90])
                            if os.path.exists(temp_path):
                                os.remove(temp_path)
                            print(f"✅ Карта загружена: {image_path}")
                            return image_path
                        else:
                            print("❌ Не удалось обработать изображение")

                except requests.exceptions.RequestException as e:
                    print(f"❌ Ошибка сети с {service['url']}: {e}")
                    continue
                except Exception as e:
                    print(f"❌ Другая ошибка с {service['url']}: {e}")
                    continue

            # Если все сервисы не сработали
            print("❌ Все сервисы карт недоступны")
            return self._create_fallback_image(latitude, longitude, image_path)

        except Exception as e:
            print(f"❌ Критическая ошибка при загрузке карты: {e}")
            print("🔄 Создаем локальное изображение...")
            return self._create_fallback_image(latitude, longitude, image_path)

    @staticmethod
    def _create_fallback_image(lat, lon, save_path):
        """Создание локального тестового изображения"""
        print("⚠️ Создаем локальное изображение")

        try:
            width, height = 640, 480

            # Создаем изображение через numpy
            img = np.zeros((height, width, 3), dtype=np.uint8)

            # Заливаем фон (небо)
            img[:] = (200, 220, 255)  # Голубой

            # Используем координаты как seed для детерминированной генерации
            seed = int(abs(lat * 10000 + lon * 10000))
            random.seed(seed)

            # "Земля" - зеленые зоны
            land_height = random.randint(height // 3, height // 2)
            cv2.rectangle(img, (0, land_height), (width, height), (100, 200, 100), -1)

            # "Дороги" - серые линии
            for i in range(3):
                road_y = land_height + random.randint(50, height - land_height - 50)
                cv2.line(img, (0, road_y), (width, road_y), (100, 100, 100), 8)

            # "Здания" - прямоугольники
            for i in range(random.randint(8, 15)):
                x = random.randint(0, width - 30)
                y = random.randint(land_height, height - 30)
                w, h = random.randint(10, 40), random.randint(15, 50)
                color = (random.randint(80, 150), random.randint(80, 150), random.randint(80, 150))
                cv2.rectangle(img, (x, y), (x + w, y + h), color, -1)
                cv2.rectangle(img, (x, y), (x + w, y + h), (0, 0, 0), 1)

            # "Водоемы" - синие овалы
            for i in range(random.randint(2, 4)):
                x = random.randint(0, width - 60)
                y = random.randint(land_height, height - 40)
                cv2.ellipse(img, (x, y), (40, 20), 0, 0, 360, (150, 150, 200), -1)

            # Добавляем текст с координатами
            cv2.putText(img, f"{lat:.4f}, {lon:.4f}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)
            cv2.putText(img, "Local Map", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)

            # Сохраняем изображение
            success = cv2.imwrite(save_path, img)
            if success:
                print(f"✅ Локальное изображение создано: {save_path}")
                return save_path
            else:
                raise Exception("Не удалось сохранить изображение")

        except Exception as e:
            print(f"❌ Ошибка при создании локального изображения: {e}")
            return None

    def _create_no_changes_visualization(self, image, original_path):
        """Создает визуализацию когда изменений нет"""
        try:
            # Создаем копию изображения
            result = image.copy()

            # Добавляем зеленую надпись "No Changes"
            text = "No Changes Detected"
            text_size = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 1, 2)[0]
            text_x = (640 - text_size[0]) // 2
            text_y = 30

            # Зеленая надпись
            cv2.putText(result, text, (text_x, text_y), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

            # Сохранение результата
            filename = os.path.basename(original_path)
            name, ext = os.path.splitext(filename)
            result_path = os.path.join(self.config.PROCESSED_IMAGES, f"no_changes_{name}{ext}")
            cv2.imwrite(result_path, result)

            print(f"💾 Визуализация 'нет изменений' сохранена: {result_path}")
            return result_path

        except Exception as e:
            print(f"❌ Ошибка при создании визуализации: {e}")
            return None

    @staticmethod
    def add_random_map_changes(image_path):
        """Добавляет случайные изменения в изображение для тестирования"""
        try:
            img = cv2.imread(image_path)
            if img is None:
                print(f"❌ Не удалось загрузить изображение: {image_path}")
                return image_path

            height, width = img.shape[:2]

            # 70% шанс добавить изменения для тестирования
            if random.random() < 0.7:
                change_type = random.choice(['new_building', 'road_work', 'vegetation'])

                if change_type == 'new_building':
                    x = random.randint(50, width - 80)
                    y = random.randint(100, height - 60)
                    w, h = random.randint(20, 50), random.randint(30, 70)
                    color = (random.randint(80, 150), random.randint(80, 150), random.randint(80, 150))
                    cv2.rectangle(img, (x, y), (x + w, y + h), color, -1)
                    cv2.rectangle(img, (x, y), (x + w, y + h), (0, 0, 0), 2)
                    print(f"🔧 Добавлено новое здание")

                elif change_type == 'road_work':
                    # ИСПРАВЛЕННАЯ ЧАСТЬ - проверка валидного диапазона
                    min_y = 200
                    max_y = height - 100

                    if max_y > min_y:
                        road_y = random.randint(min_y, max_y)
                    else:
                        # Если диапазон некорректный, используем безопасные значения
                        road_y = random.randint(150, height - 50)

                    cv2.line(img, (0, road_y), (width, road_y), (0, 200, 200), 10)
                    for i in range(0, width, 80):
                        cv2.rectangle(img, (i, road_y - 10), (i + 15, road_y + 10), (0, 100, 255), -1)
                    print(f"🔧 Добавлены дорожные работы")

                elif change_type == 'vegetation':
                    for i in range(3):
                        x = random.randint(50, width - 50)
                        y = random.randint(100, height - 50)
                        radius = random.randint(15, 35)
                        cv2.circle(img, (x, y), radius, (0, random.randint(150, 200), 0), -1)
                    print(f"🔧 Добавлена растительность")

                # Сохраняем измененное изображение
                name, ext = os.path.splitext(image_path)
                changed_path = f"{name}_changed{ext}"
                success = cv2.imwrite(changed_path, img)
                if success:
                    print(f"✅ Изменения сохранены: {changed_path}")
                    return changed_path

            return image_path

        except Exception as e:
            print(f"❌ Ошибка при добавлении изменений: {e}")
            return image_path

    def detect_changes(self, image1_path, image2_path):
        """Обнаружение изменений между двумя изображениями"""
        try:
            print(f"🔍 Сравниваем {os.path.basename(image1_path)} и {os.path.basename(image2_path)}")

            # Проверяем существование файлов
            if not os.path.exists(image1_path) or not os.path.exists(image2_path):
                error_msg = f"Файлы не найдены: {image1_path}, {image2_path}"
                print(f"❌ {error_msg}")
                return self._error_result(error_msg)

            # Загрузка изображений
            img1 = cv2.imread(image1_path)
            img2 = cv2.imread(image2_path)

            if img1 is None or img2 is None:
                error_msg = "Не удалось загрузить изображения (cv2.imread вернул None)"
                print(f"❌ {error_msg}")
                return self._error_result(error_msg)

            # Приведение к одинаковому размеру
            img1 = cv2.resize(img1, (640, 480))
            img2 = cv2.resize(img2, (640, 480))

            # Конвертация в grayscale
            gray1 = cv2.cvtColor(img1, cv2.COLOR_BGR2GRAY)
            gray2 = cv2.cvtColor(img2, cv2.COLOR_BGR2GRAY)

            # Вычисление разности
            diff = cv2.absdiff(gray1, gray2)

            # Пороговая обработка
            _, thresh = cv2.threshold(diff, 25, 255, cv2.THRESH_BINARY)

            # Улучшение маски
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
            thresh = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel)
            thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)

            # Подсчет изменений
            changed_pixels = cv2.countNonZero(thresh)
            total_pixels = 640 * 480
            change_score = changed_pixels / total_pixels

            # ВАЖНО: Всегда возвращаем результат, даже если изменений нет!
            if changed_pixels < 50:  # Небольшой порог для фильтрации шума
                print("📊 Изменений не обнаружено")
                change_type = 'no_changes'
                result_path = self._create_no_changes_visualization(img2, image1_path)
                confidence = 0.0
            else:
                # Анализ типа изменений
                change_type = self._simple_analyze_changes(img2, thresh)
                # Создание визуализации
                result_path = self._create_changes_visualization(img2, thresh, change_type, image1_path, change_score)
                confidence = min(change_score * 10, 0.95)
                print(f"📊 Обнаружены изменения: {change_score:.1%} ({change_type})")

            details = {
                'changed_pixels': changed_pixels,
                'total_pixels': total_pixels,
                'change_percent': round(change_score * 100, 2),
                'status': 'changes_detected' if changed_pixels >= 50 else 'no_changes',
                'image1': os.path.basename(image1_path),
                'image2': os.path.basename(image2_path)
            }

            result = {
                'change_score': change_score,
                'change_type': change_type,
                'confidence': confidence,
                'details': details,
                'result_image_path': result_path,
                'status': 'completed'
            }

            return result

        except Exception as e:
            print(f"❌ Ошибка обнаружения изменений: {e}")
            return self._error_result(str(e))

    def _create_changes_visualization(self, image, thresh, change_type, original_path, change_score):
        """Создание улучшенной визуализации изменений"""
        try:
            color_map = {
                'vegetation_change': (0, 255, 0),  # Зеленый
                'water_change': (255, 0, 0),  # Синий
                'construction': (0, 165, 255),  # Оранжевый
                'building_change': (0, 0, 255),  # Красный
                'unknown_change': (128, 0, 128),  # Фиолетовый
            }

            # Создаем цветную маску
            mask_color = cv2.cvtColor(thresh, cv2.COLOR_GRAY2BGR)
            color = color_map.get(change_type, (0, 0, 255))
            mask_color[thresh == 255] = color

            # Наложение маски на изображение
            result = cv2.addWeighted(image, 0.7, mask_color, 0.3, 0)

            # Добавляем детальную информацию
            change_percent = change_score * 100

            # Заголовок
            title = f"CHANGES DETECTED: {change_type.upper()}"
            cv2.putText(result, title, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

            # Процент изменений
            percent_text = f"Changes: {change_percent:.1f}%"
            cv2.putText(result, percent_text, (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

            # Время
            time_text = f"Time: {datetime.now().strftime('%H:%M:%S')}"
            cv2.putText(result, time_text, (10, 85), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

            # Рамка вокруг изменений
            contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            for contour in contours:
                if cv2.contourArea(contour) > 100:  # Только значительные контуры
                    x, y, w, h = cv2.boundingRect(contour)
                    cv2.rectangle(result, (x, y), (x + w, y + h), color, 2)

            # Сохранение результата
            filename = os.path.basename(original_path)
            name, ext = os.path.splitext(filename)
            result_path = os.path.join(self.config.PROCESSED_IMAGES, f"changes_{name}{ext}")
            cv2.imwrite(result_path, result)

            print(f"💾 Визуализация сохранена: {result_path}")
            return result_path

        except Exception as e:
            print(f"❌ Ошибка при создании визуализации: {e}")
            return None

    @staticmethod
    def _simple_analyze_changes(img2, thresh):
        """Простой анализ типа изменений"""
        try:
            changed_area = cv2.bitwise_and(img2, img2, mask=thresh)
            mean_val = cv2.mean(changed_area, mask=thresh)
            blue, green, red = mean_val[:3]

            if green > blue + 20 and green > red + 20:
                return 'vegetation_change'
            elif blue > green + 15 and blue > red + 15:
                return 'water_change'
            elif red > 150 and green > 100:
                return 'construction'
            else:
                return 'building_change'
        except Exception as e:
            print(f"❌ Ошибка анализа изменений: {e}")
            return 'unknown_change'

    @staticmethod
    def _error_result(error_msg):
        """Создание результата с ошибкой"""
        return {
            'change_score': 0,
            'change_type': 'error',
            'confidence': 0,
            'details': {'error': error_msg},
            'result_image_path': None,
            'status': 'error'
        }

    def test_change_detection(self, location):
        """Тестирование обнаружения изменений для конкретной локации"""
        print(f"\n🧪 ТЕСТИРУЕМ ОБНАРУЖЕНИЕ ИЗМЕНЕНИЙ: {location.name}")

        # Создаем первое изображение
        image1_path = self.download_satellite_image(location.latitude, location.longitude)

        # Добавляем искусственные изменения
        image2_path = self.add_random_map_changes(image1_path)

        if image2_path != image1_path:
            # Обнаруживаем изменения
            result = self.detect_changes(image1_path, image2_path)

            print(f"🎯 РЕЗУЛЬТАТ ТЕСТА:")
            print(f"   📊 Изменения: {result['change_score']:.1%}")
            print(f"   🎯 Тип: {result['change_type']}")
            print(f"   ✅ Уверенность: {result['confidence']:.1%}")
            print(f"   📁 Визуализация: {result['result_image_path']}")

            return result
        else:
            print("❌ Тест не удался - изменения не были добавлены")
            return None