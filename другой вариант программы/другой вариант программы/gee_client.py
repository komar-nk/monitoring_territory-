"""
Клиент для работы с Google Earth Engine
"""

import os
import sys
import logging
import hashlib
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Tuple, Dict, Any

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class GEEClient:
    """Клиент для работы с Google Earth Engine"""

    def __init__(self, credentials_path: str = 'credentials.json',
                 cache_dir: str = 'satellite_images',
                 max_cache_size: int = 100):
        """
        Инициализация клиента GEE

        Args:
            credentials_path: Путь к файлу с учетными данными GEE
            cache_dir: Директория для кэширования изображений
            max_cache_size: Максимальное количество изображений в кэше
        """
        # Импортируем обязательные модули
        self._import_required_modules()

        self.credentials_path = credentials_path
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        self.max_cache_size = max_cache_size
        self.request_count = 0
        self._cache_metadata = {}

        # Инициализация GEE
        self._init_gee()

    def _import_required_modules(self):
        """Импорт обязательных модулей"""
        try:
            import ee
            self.ee = ee
        except ImportError:
            print("Модуль 'earthengine-api' не установлен!")
            print("Установите: pip install earthengine-api")
            sys.exit(1)

        try:
            from PIL import Image, ImageEnhance, ImageFilter
            self.Image = Image
            self.ImageEnhance = ImageEnhance
            self.ImageFilter = ImageFilter
        except ImportError:
            print("Модуль 'Pillow' не установлен!")
            print("Установите: pip install pillow")
            sys.exit(1)

        try:
            import cv2
            self.cv2 = cv2
        except ImportError:
            print("Модуль 'opencv-python' не установлен!")
            print("Установите: pip install opencv-python")
            self.cv2 = None

        try:
            import requests
            self.requests = requests
        except ImportError:
            print("Модуль 'requests' не установлен!")
            print("Установите: pip install requests")
            sys.exit(1)

    def _init_gee(self) -> None:
        """Инициализация Google Earth Engine"""
        try:
            print("\n" + "=" * 60)
            print("ИНИЦИАЛИЗАЦИЯ GOOGLE EARTH ENGINE")
            print("=" * 60)

            # Твой ID проекта
            PROJECT_ID = "careful-journey-480220-j1"

            print(f"Проект: {PROJECT_ID}")

            # Пробуем инициализацию с использованием credentials.json
            if os.path.exists(self.credentials_path):
                print(f"\nНайден файл {self.credentials_path}")
                print("Инициализируем GEE...")

                try:
                    # Инициализация с проектом
                    self.ee.Initialize(project=PROJECT_ID)
                    print(f"GEE успешно инициализирован!")
                    return
                except self.ee.EEException as e:
                    print(f"Ошибка GEE: {e}")

                    # Если ошибка связана с проектом, пробуем без указания проекта
                    if "project" in str(e).lower():
                        print("Пробуем инициализацию без указания проекта...")
                        try:
                            self.ee.Initialize()
                            print("GEE инициализирован без указания проекта")
                            return
                        except Exception as e2:
                            print(f"Ошибка: {e2}")

                    raise e
            else:
                print(f"\nФайл {self.credentials_path} не найден!")
                print("Создай сервисный аккаунт в Google Cloud Console")
                print("и сохрани credentials.json в папку проекта")

                # Пробуем авторизацию через браузер
                print("\nПробуем авторизацию через браузер...")
                try:
                    self.ee.Authenticate()
                    self.ee.Initialize(project=PROJECT_ID)
                    print("Авторизация через браузер успешна!")
                    return
                except Exception as e:
                    print(f"Ошибка: {e}")

            # Если ничего не сработало
            print("\n" + "=" * 60)
            print("НЕ УДАЛОСЬ ИНИЦИАЛИЗИРОВАТЬ GEE")
            print("=" * 60)

            print("\nЧТО СДЕЛАТЬ:")
            print("1. Перейди: https://code.earthengine.google.com/")
            print("2. Нажми 'Sign Up' или 'Accept' для активации Earth Engine")
            print("3. Обычно это занимает 1-2 дня на одобрение Google")
            print("4. ИЛИ создай сервисный аккаунт в Google Cloud Console")
            print("5. Положи файл credentials.json в папку проекта")

            print("\nПрограмма завершена. Настрой GEE и попробуй снова.")
            sys.exit(0)

        except Exception as e:
            print(f"\nКритическая ошибка инициализации GEE: {e}")
            print("\nРешение:")
            print("1. Проверь интернет-соединение")
            print("2. Убедись что Earth Engine API включен для твоего проекта")
            print("3. Убедись что у сервисного аккаунта есть права Editor/Owner")
            sys.exit(1)

    @staticmethod
    def _get_cache_key(latitude: float, longitude: float, image_date: str) -> str:
        """Генерация ключа кэша для координат и даты"""
        key_str = f"{latitude:.6f}_{longitude:.6f}_{image_date}"
        return hashlib.md5(key_str.encode()).hexdigest()

    def _get_cached_image(self, latitude: float, longitude: float, image_date: str) -> Optional[str]:
        """Получение изображения из кэша если оно существует"""
        cache_key = self._get_cache_key(latitude, longitude, image_date)
        image_path = self.cache_dir / f"{cache_key}.png"

        if image_path.exists():
            self._cache_metadata[cache_key] = datetime.now()
            logger.debug(f"Изображение найдено в кэше: {image_path}")
            return str(image_path)

        return None

    def _save_to_cache(self, latitude: float, longitude: float, image_date: str, image_path: str) -> None:
        """Сохранение изображения в кэш"""
        try:
            cache_key = self._get_cache_key(latitude, longitude, image_date)

            # Очистка старых файлов если кэш переполнен
            if len(self._cache_metadata) >= self.max_cache_size:
                self._clean_old_cache()

            self._cache_metadata[cache_key] = datetime.now()
            logger.debug(f"Изображение сохранено в кэш: {image_path}")

        except Exception as cache_error:
            logger.error(f"Ошибка при сохранении в кэш: {cache_error}")

    def _clean_old_cache(self) -> None:
        """Очистка старых файлов кэша"""
        try:
            if not self._cache_metadata:
                return

            sorted_items = sorted(self._cache_metadata.items(), key=lambda item: item[1])
            to_remove = max(1, int(len(sorted_items) * 0.2))

            for cache_key, _ in sorted_items[:to_remove]:
                image_path = self.cache_dir / f"{cache_key}.png"
                if image_path.exists():
                    try:
                        image_path.unlink()
                        logger.debug(f"Удален старый файл кэша: {image_path}")
                    except OSError:
                        pass

                if cache_key in self._cache_metadata:
                    del self._cache_metadata[cache_key]

        except Exception as clean_error:
            logger.error(f"Ошибка при очистке кэша: {clean_error}")

    def _enhance_image(self, image_path: str) -> str:
        """Улучшение изображения для лучшей детекции изменений"""
        try:
            # Открываем изображение
            img = self.Image.open(image_path)

            # 1. Увеличиваем яркость (сделает детали видимыми)
            enhancer = self.ImageEnhance.Brightness(img)
            img = enhancer.enhance(1.4)  # +40% яркости

            # 2. Увеличиваем контраст (улучшит границы объектов)
            enhancer = self.ImageEnhance.Contrast(img)
            img = enhancer.enhance(1.4)  # +40% контраста

            # 3. Легкое увеличение резкости (улучшит детали)
            enhancer = self.ImageEnhance.Sharpness(img)
            img = enhancer.enhance(1.3)  # +30% резкости

            # 4. Легкое размытие для уменьшения пиксельности
            img = img.filter(self.ImageFilter.GaussianBlur(radius=0.5))

            # 5. Снова легкая резкость для компенсации
            enhancer = self.ImageEnhance.Sharpness(img)
            img = enhancer.enhance(1.1)  # +10% резкости

            # Сохраняем с высоким качеством
            img.save(image_path, 'PNG', optimize=True, quality=95)

            return image_path

        except Exception as e:
            logger.error(f"Ошибка улучшения изображения: {e}")
            return image_path

    def get_satellite_image(self, latitude: float, longitude: float,
                            date: Optional[str] = None,
                            cloud_cover_threshold: float = 30.0,
                            image_size: int = 2048) -> Tuple[bool, Optional[str], Optional[str], str]:
        """
        Получение спутникового изображения с ОПТИМАЛЬНЫМИ НАСТРОЙКАМИ

        Args:
            latitude: Широта
            longitude: Долгота
            date: Дата (YYYY-MM-DD) или None для текущей
            cloud_cover_threshold: Максимальная облачность в %
            image_size: Размер изображения (2048 = оптимально для детекции)

        Returns:
            (успех, путь_к_файлу, дата_изображения, сообщение)
        """
        try:
            # Оптимальный размер для детекции изменений
            if image_size > 2048:
                image_size = 2048  # Максимум без ошибок

            if date is None:
                actual_date = datetime.now().strftime('%Y-%m-%d')
            else:
                actual_date = date

            print(f"\nПоиск изображения для детекции изменений...")
            print(f"Координаты: {latitude:.4f}, {longitude:.4f}")
            print(f"Дата запроса: {actual_date}")
            print(f"Максимальная облачность: {cloud_cover_threshold}%")
            print(f"Размер изображения: {image_size}x{image_size} пикселей")
            print(f"Область: {image_size * 10 / 1000:.1f}x{image_size * 10 / 1000:.1f} км")

            # Проверяем кэш
            cached_image = self._get_cached_image(latitude, longitude, actual_date)
            if cached_image:
                print("Используем изображение из кэша")
                return True, cached_image, actual_date, "Изображение из кэша"

            # Создаем точку интереса
            point = self.ee.Geometry.Point([longitude, latitude])

            # Определяем диапазон дат
            try:
                target_date = datetime.strptime(actual_date, '%Y-%m-%d')
            except ValueError as date_error:
                return False, None, None, f"Некорректный формат даты: {date_error}"

            # Ищем за последние 60 дней
            start_date = (target_date - timedelta(days=60)).strftime('%Y-%m-%d')
            end_date = (target_date + timedelta(days=1)).strftime('%Y-%m-%d')

            print(f"Поиск изображений с {start_date} по {end_date}")

            # Загружаем коллекцию Sentinel-2
            collection = (self.ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
                          .filterBounds(point)
                          .filterDate(start_date, end_date)
                          .filter(self.ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', cloud_cover_threshold))
                          .sort('CLOUDY_PIXEL_PERCENTAGE'))

            # Проверяем наличие изображений
            collection_size = collection.size().getInfo()
            print(f"Найдено изображений: {collection_size}")

            if collection_size == 0:
                return False, None, None, f"Нет изображений с облачностью < {cloud_cover_threshold}%"

            # Выбираем наименее облачное изображение
            image = self.ee.Image(collection.first())

            # Получаем дату захвата
            image_date = self.ee.Date(image.get('system:time_start')).format('YYYY-MM-dd').getInfo()

            # Получаем облачность изображения
            cloud_cover = image.get('CLOUDY_PIXEL_PERCENTAGE').getInfo()
            print(f"Найдено изображение от: {image_date}")
            print(f"Облачность изображения: {cloud_cover}%")

            # Определяем область интереса (1.5x1.5 км - меньше область, больше деталей!)
            region = point.buffer(750).bounds()  # 750 метров = 1.5x1.5 км

            print("Получаем URL для скачивания...")

            # ОПТИМАЛЬНЫЕ НАСТРОЙКИ ДЛЯ ДЕТЕКЦИИ ИЗМЕНЕНИЙ:
            # Меньшая область + лучшие настройки контраста

            # Генерируем URL для скачивания
            url = image.getThumbURL({
                'region': region,
                'dimensions': f'{image_size}x{image_size}',
                'format': 'png',
                'bands': ['B4', 'B3', 'B2'],  # True Color (RGB)
                'min': 500,  # Увеличил для лучшего контраста
                'max': 3000,  # Оптимально для Sentinel-2
                'gamma': 1.0  # Нейтральная гамма
            })

            print(f"Скачиваем изображение...")

            # Скачиваем изображение
            response = self.requests.get(url, timeout=120)
            if response.status_code != 200:
                return False, None, None, f"Ошибка скачивания: {response.status_code}"

            # Сохраняем изображение
            cache_key = self._get_cache_key(latitude, longitude, image_date)
            filepath = self.cache_dir / f"{cache_key}_{image_size}.png"

            print(f"Сохраняем изображение...")

            # Сохраняем скачанное изображение
            with open(filepath, 'wb') as f:
                f.write(response.content)

            # УЛУЧШАЕМ ИЗОБРАЖЕНИЕ для детекции
            print("Улучшаем изображение для детекции изменений...")
            self._enhance_image(str(filepath))

            # Получаем информацию о размере
            pil_image = self.Image.open(filepath)
            width, height = pil_image.size
            file_size_mb = os.path.getsize(filepath) / (1024 * 1024)

            # Расчёт детализации
            area_km = (width * 10 / 1000) * (height * 10 / 1000)
            print(f"\nИЗОБРАЖЕНИЕ СОХРАНЕНО!")
            print(f"   Размер: {width}x{height} пикселей")
            print(f"   Область: {area_km:.1f} км²")
            print(f"   Детализация: {10.0 * 1000 / image_size:.1f} метров на пиксель")
            print(f"   Размер файла: {file_size_mb:.2f} MB")
            print(f"   Дата съемки: {image_date}")
            print(f"   Облачность: {cloud_cover}%")
            print(f"   Путь: {filepath}")

            # Сохраняем в кэш
            self._save_to_cache(latitude, longitude, image_date, str(filepath))
            self.request_count += 1

            return True, str(filepath), image_date, f"Успешно ({width}x{height}, {area_km:.1f}км²)"

        except self.ee.EEException as gee_error:
            return False, None, None, f"Ошибка GEE: {str(gee_error)}"
        except Exception as error:
            return False, None, None, f"Внутренняя ошибка: {str(error)}"

    def get_image_for_change_detection(self, latitude: float, longitude: float,
                                       date: Optional[str] = None) -> Tuple[bool, Optional[str], Optional[str], str]:
        """
        Специальный метод для получения изображений для детекции изменений
        (меньшая область, лучшие настройки)
        """
        return self.get_satellite_image(
            latitude, longitude, date,
            cloud_cover_threshold=20.0,  # Строже к облачности
            image_size=2048  # Максимальная детализация
        )

    def analyze_image(self, image_path: str) -> Dict[str, Any]:
        """
        Анализ изображения с помощью OpenCV

        Args:
            image_path: Путь к изображению

        Returns:
            Словарь с результатами анализа
        """
        if self.cv2 is None:
            return {'error': 'OpenCV не установлен. Установите: pip install opencv-python'}

        if not os.path.exists(image_path):
            return {'error': f'Файл не существует: {image_path}'}

        try:
            img = self.cv2.imread(image_path)
            if img is None:
                return {'error': 'Не удалось загрузить изображение'}

            height, width, channels = img.shape

            # Конвертируем в grayscale
            gray = self.cv2.cvtColor(img, self.cv2.COLOR_BGR2GRAY)

            # Статистика яркости
            brightness_mean = gray.mean()
            brightness_std = gray.std()
            min_val, max_val, _, _ = self.cv2.minMaxLoc(gray)

            # Оценка облачности
            _, bright_mask = self.cv2.threshold(gray, 200, 255, self.cv2.THRESH_BINARY)
            cloud_pixels = self.cv2.countNonZero(bright_mask)
            cloud_percentage = (cloud_pixels / (width * height)) * 100

            # Оценка резкости (важно для детекции!)
            edges = self.cv2.Canny(gray, 100, 200)
            edge_pixels = self.cv2.countNonZero(edges)
            edge_percentage = (edge_pixels / (width * height)) * 100

            # Контрастность (важно для детекции!)
            contrast = max_val - min_val

            # Определяем оценку
            cloud_assessment = 'низкая' if cloud_percentage < 10 else 'умеренная' if cloud_percentage < 30 else 'высокая'
            sharpness_assessment = 'низкая' if edge_percentage < 3 else 'средняя' if edge_percentage < 8 else 'высокая'
            contrast_assessment = 'низкий' if contrast < 100 else 'средний' if contrast < 150 else 'высокий'

            return {
                'dimensions': {'width': width, 'height': height},
                'brightness': {
                    'mean': float(brightness_mean),
                    'std': float(brightness_std),
                    'min': float(min_val),
                    'max': float(max_val)
                },
                'contrast': {
                    'value': float(contrast),
                    'assessment': contrast_assessment
                },
                'cloud_cover': {
                    'percentage': float(cloud_percentage),
                    'assessment': cloud_assessment
                },
                'sharpness': {
                    'edge_pixels': int(edge_pixels),
                    'edge_percentage': float(edge_percentage),
                    'assessment': sharpness_assessment
                },
                'suitable_for_change_detection': edge_percentage > 3 and contrast > 80 and cloud_percentage < 40
            }

        except Exception as analysis_error:
            return {'error': f'Ошибка анализа: {str(analysis_error)}'}

    def compare_images_advanced(self, image_path1: str, image_path2: str) -> Dict[str, Any]:
        """
        Улучшенное сравнение двух изображений для детекции изменений

        Args:
            image_path1: Путь к первому изображению
            image_path2: Путь ко второму изображению

        Returns:
            Словарь с результатами сравнения
        """
        if self.cv2 is None:
            return {'error': 'OpenCV не установлен'}

        if not all(os.path.exists(p) for p in [image_path1, image_path2]):
            return {'error': 'Один или оба файла не существуют'}

        try:
            img1 = self.cv2.imread(image_path1)
            img2 = self.cv2.imread(image_path2)

            if img1 is None or img2 is None:
                return {'error': 'Не удалось загрузить изображения'}

            if img1.shape != img2.shape:
                return {'error': 'Размеры изображений не совпадают'}

            # Конвертируем в grayscale
            gray1 = self.cv2.cvtColor(img1, self.cv2.COLOR_BGR2GRAY)
            gray2 = self.cv2.cvtColor(img2, self.cv2.COLOR_BGR2GRAY)

            # Нормализуем яркость
            gray1 = self.cv2.normalize(gray1, None, 0, 255, self.cv2.NORM_MINMAX)
            gray2 = self.cv2.normalize(gray2, None, 0, 255, self.cv2.NORM_MINMAX)

            # Вычисляем разницу
            diff = self.cv2.absdiff(gray1, gray2)

            # Адаптивный порог (лучше для разных условий освещения)
            thresh = self.cv2.adaptiveThreshold(diff, 255,
                                                self.cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                                self.cv2.THRESH_BINARY, 11, 2)

            # Убираем шум
            kernel = self.cv2.getStructuringElement(self.cv2.MORPH_ELLIPSE, (3, 3))
            thresh = self.cv2.morphologyEx(thresh, self.cv2.MORPH_OPEN, kernel)
            thresh = self.cv2.morphologyEx(thresh, self.cv2.MORPH_CLOSE, kernel)

            # Процент изменений
            changed_pixels = self.cv2.countNonZero(thresh)
            total_pixels = thresh.size
            change_percentage = (changed_pixels / total_pixels) * 100

            # Находим контуры изменений
            contours, _ = self.cv2.findContours(thresh, self.cv2.RETR_EXTERNAL,
                                                self.cv2.CHAIN_APPROX_SIMPLE)

            # Определяем уровень изменений
            if change_percentage < 2:
                change_level = 'минимальные'
                significance = 'Нет значимых изменений'
            elif change_percentage < 5:
                change_level = 'незначительные'
                significance = 'Мелкие изменения'
            elif change_percentage < 15:
                change_level = 'умеренные'
                significance = 'Заметные изменения'
            elif change_percentage < 30:
                change_level = 'значительные'
                significance = 'Серьезные изменения'
            else:
                change_level = 'критические'
                significance = 'Кардинальные изменения'

            return {
                'changed_pixels': int(changed_pixels),
                'total_pixels': int(total_pixels),
                'change_percentage': float(change_percentage),
                'change_level': change_level,
                'significance': significance,
                'contours_count': len(contours),
                'suggestion': 'Рекомендуется проверить' if change_percentage > 5 else 'Изменений не обнаружено'
            }

        except Exception as comparison_error:
            return {'error': f'Ошибка сравнения: {str(comparison_error)}'}

    def compare_images(self, image_path1: str, image_path2: str) -> Dict[str, Any]:
        """Алиас для обратной совместимости"""
        return self.compare_images_advanced(image_path1, image_path2)

    def clear_cache(self) -> str:
        """Очистка кэша изображений"""
        try:
            deleted_count = 0

            for file in self.cache_dir.glob("*.png"):
                try:
                    file.unlink()
                    deleted_count += 1
                except OSError:
                    pass

            self._cache_metadata.clear()

            return f"Очищено {deleted_count} файлов из кэша"

        except Exception as error:
            return f"Ошибка очистки: {error}"

    def get_cache_info(self) -> Dict[str, Any]:
        """Получение информации о кэше"""
        try:
            cache_files = list(self.cache_dir.glob("*.png"))
            total_size = sum(f.stat().st_size for f in cache_files if f.exists())

            return {
                'image_count': len(cache_files),
                'total_size_mb': round(total_size / (1024 * 1024), 2),
                'request_count': self.request_count,
                'cache_in_memory': len(self._cache_metadata)
            }

        except Exception as error:
            return {'error': str(error)}


# Тестовый запуск
if __name__ == "__main__":
    print("Тестирование GEE клиента для детекции изменений...")
    print(f"Проект: careful-journey-480220-j1")

    try:
        client = GEEClient()
        print("\nКлиент создан успешно!")

        print("\nТест 1: Получаем изображение для детекции изменений...")
        success, path, date, msg = client.get_image_for_change_detection(
            55.7558, 37.6173  # Москва
        )

        if success:
            print(f"\nИзображение получено!")
            print(f"   Путь: {path}")
            print(f"   Дата: {date}")

            # Анализ пригодности для детекции
            print(f"\nАнализируем пригодность для детекции изменений...")
            analysis = client.analyze_image(path)
            if 'error' not in analysis:
                print(f"   Размер: {analysis['dimensions']['width']}x{analysis['dimensions']['height']}")
                print(f"   Яркость: {analysis['brightness']['mean']:.1f}")
                print(f"   Контраст: {analysis['contrast']['value']:.1f} ({analysis['contrast']['assessment']})")
                print(f"   Резкость: {analysis['sharpness']['edge_percentage']:.2f}% ({analysis['sharpness']['assessment']})")
                print(f"   Облачность: {analysis['cloud_cover']['percentage']:.1f}% ({analysis['cloud_cover']['assessment']})")
                print(f"   Пригодно для детекции: {'ДА' if analysis['suitable_for_change_detection'] else 'НЕТ'}")
        else:
            print(f"\nОшибка: {msg}")

    except Exception as e:
        print(f"Ошибка: {e}")
        import traceback

        traceback.print_exc()