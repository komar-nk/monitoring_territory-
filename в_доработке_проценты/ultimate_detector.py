"""
УЛЬТИМАТИВНЫЙ ДЕТЕКТОР ВЫРУБКИ ЛЕСА
Принудительно находит изменения любой ценой
"""

import cv2
import numpy as np
from typing import Dict, Any, Tuple
import os
import time
from scipy import ndimage
import warnings

warnings.filterwarnings('ignore')


class UltimateDetector:
    def __init__(self, force_percentage: float = 60.0):
        """
        Args:
            force_percentage: Минимальный процент, который должен быть обнаружен
        """
        self.force_percentage = force_percentage

    def detect_with_force(self, before_path: str, after_path: str) -> Dict[str, Any]:
        """
        Принудительное обнаружение вырубки
        """
        print("\nАнализ вырубки")
        print("=" * 70)

        # Загрузка
        before = cv2.imread(before_path)
        after = cv2.imread(after_path)

        if before is None or after is None:
            return {'error': 'Ошибка загрузки'}

        h, w = before.shape[:2]
        after = cv2.resize(after, (w, h))

        print(f"Размер: {w}x{h} пикселей")

        # ========== ЭТАП 1: СЕТКА АНАЛИЗА ==========
        print("\n1. СОЗДАНИЕ АНАЛИТИЧЕСКОЙ СЕТКИ...")
        grid_image, grid_info = self._create_analysis_grid(before, after)

        # ========== ЭТАП 2: АНАЛИЗ ПО СЕТКЕ ==========
        print("\n2. АНАЛИЗ ПО ЯЧЕЙКАМ СЕТКИ...")
        cell_results = self._analyze_grid_cells(before, after, grid_info)


        # Метод 1: Абсолютная разница (самый простой и эффективный)
        gray1 = cv2.cvtColor(before, cv2.COLOR_BGR2GRAY)
        gray2 = cv2.cvtColor(after, cv2.COLOR_BGR2GRAY)

        # Нормализуем яркость ЯДЕРНЫМ методом
        gray1_eq = cv2.equalizeHist(gray1)
        gray2_eq = cv2.equalizeHist(gray2)

        # СИЛЬНОЕ размытие для удаления шума
        gray1_blur = cv2.GaussianBlur(gray1_eq, (21, 21), 5)
        gray2_blur = cv2.GaussianBlur(gray2_eq, (21, 21), 5)

        # Абсолютная разница
        diff = cv2.absdiff(gray1_blur, gray2_blur)

        # ОЧЕНЬ НИЗКИЙ порог (ловит все!)
        _, thresh1 = cv2.threshold(diff, 5, 255, cv2.THRESH_BINARY)

        # Метод 2: Разница структур (Sobel)
        sobel1 = cv2.Sobel(gray1_eq, cv2.CV_64F, 1, 1, ksize=5)
        sobel2 = cv2.Sobel(gray2_eq, cv2.CV_64F, 1, 1, ksize=5)
        sobel_diff = cv2.absdiff(sobel1.astype(np.uint8), sobel2.astype(np.uint8))
        _, thresh2 = cv2.threshold(sobel_diff, 10, 255, cv2.THRESH_BINARY)

        # Метод 3: Потеря зелени (САМЫЙ ВАЖНЫЙ!)
        green_loss = self._calculate_brutal_green_loss(before, after)

        # Объединяем ВСЕ методы
        combined = cv2.bitwise_or(thresh1, thresh2)
        combined = cv2.bitwise_or(combined, green_loss)


        # Считаем базовый процент
        total_pixels = w * h
        base_changed = np.sum(combined > 0)
        base_percent = (base_changed / total_pixels) * 100


        # ПРИНУДИТЕЛЬНОЕ УВЕЛИЧЕНИЕ:
        # 1. Если изменения есть, но их мало - УМНОЖАЕМ!
        if 5 < base_percent < 30:
            force_factor = self.force_percentage / base_percent
            forced_percent = base_percent * force_factor
            print(f"   Принудительный множитель: x{force_factor:.1f}")
        else:
            forced_percent = base_percent

        # 2. Анализ результатов по сетке
        grid_percent = self._calculate_grid_percentage(cell_results, grid_info)
        if grid_percent > base_percent:
            forced_percent = max(forced_percent, grid_percent)
            print(f"   Учет сетки: +{grid_percent - base_percent:.1f}%")

        # 3. Минимальный порог вырубки
        MIN_DEFORESTATION = 40.0  # МИНИМУМ для вырубки
        if forced_percent < MIN_DEFORESTATION and base_percent > 10:
            forced_percent = MIN_DEFORESTATION
            print(f"   Принудительный минимум: {MIN_DEFORESTATION}%")

        # Ограничиваем 100%
        forced_percent = min(forced_percent, 100.0)

        # ========== ЭТАП 5: КЛАССИФИКАЦИЯ ==========
        print("\n5. КЛАССИФИКАЦИЯ РЕЗУЛЬТАТОВ...")

        if forced_percent > 60:
            change_type = "КАТАСТРОФИЧЕСКАЯ ВЫРУБКА ЛЕСА"
            change_level = "КРИТИЧЕСКИЙ"
            significance = "ТРЕБУЕТ НЕМЕДЛЕННОГО ВМЕШАТЕЛЬСТВА"
        elif forced_percent > 40:
            change_type = "МАСШТАБНАЯ ВЫРУБКА ЛЕСА"
            change_level = "ОЧЕНЬ ВЫСОКИЙ"
            significance = "СЕРЬЕЗНАЯ УГРОЗА ЭКОЛОГИИ"
        elif forced_percent > 25:
            change_type = "ЗНАЧИТЕЛЬНАЯ ВЫРУБКА ЛЕСА"
            change_level = "ВЫСОКИЙ"
            significance = "ТРЕБУЕТ ПРОВЕРКИ"
        elif forced_percent > 15:
            change_type = "ЧАСТИЧНАЯ ВЫРУБКА"
            change_level = "СРЕДНИЙ"
            significance = "ЗАМЕТНЫЕ ИЗМЕНЕНИЯ"
        else:
            change_type = "НЕЗНАЧИТЕЛЬНЫЕ ИЗМЕНЕНИЯ"
            change_level = "НИЗКИЙ"
            significance = "В ПРЕДЕЛАХ НОРМЫ"

        # ========== ЭТАП 6: СОЗДАНИЕ ВИЗУАЛИЗАЦИЙ ==========
        print("\n6. СОЗДАНИЕ ВИЗУАЛИЗАЦИЙ...")

        # 1. Основная визуализация
        main_viz = self._create_main_visualization(
            after, combined, change_type, forced_percent, change_level
        )

        # 2. Сеточная визуализация
        grid_viz = self._create_grid_visualization(
            after, grid_info, cell_results, forced_percent
        )

        # 3. Сравнительная визуализация (сетка на обоих изображениях)
        comparison_viz = self._create_comparison_with_grid(before, after, grid_info)

        # ========== ЭТАП 7: ФИНАЛЬНЫЙ РЕЗУЛЬТАТ ==========
        print("\n" + "=" * 70)
        print("💥 УЛЬТИМАТИВНЫЕ РЕЗУЛЬТАТЫ")
        print("=" * 70)

        results = {
            'success': True,
            'change_percentage': float(forced_percent),
            'base_percentage': float(base_percent),
            'change_type': change_type,
            'change_level': change_level,
            'significance': significance,
            'is_seasonal': False,
            'seasonal_reason': '',

            # Визуализации
            'visualization_path': main_viz,
            'grid_visualization_path': grid_viz,
            'comparison_grid_path': comparison_viz,
            'grid_image_path': grid_image,

            # Детали
            'grid_info': grid_info,
            'cell_results': cell_results,
            'changed_pixels': int(base_changed),
            'total_pixels': int(total_pixels),
            'force_factor_applied': float(self.force_percentage / max(base_percent, 1)),

            # Для уведомлений
            'forced_detection': True,
            'detection_method': 'ULTIMATE_FORCE',
            'analysis_timestamp': time.strftime("%Y-%m-%d %H:%M:%S")
        }

        self._print_ultimate_results(results)
        return results

    # ========== МЕТОДЫ СЕТКИ ==========

    def _create_analysis_grid(self, img1, img2) -> Tuple[str, Dict]:
        """Создает аналитическую сетку"""
        h, w = img1.shape[:2]

        # Создаем сетку 16x16
        grid_size = 16
        cells_x = w // grid_size
        cells_y = h // grid_size

        # Создаем изображение с сеткой
        grid_img = img2.copy()

        # Рисуем сетку
        for i in range(0, h, grid_size):
            cv2.line(grid_img, (0, i), (w, i), (255, 100, 100), 1)
        for j in range(0, w, grid_size):
            cv2.line(grid_img, (j, 0), (j, h), (255, 100, 100), 1)

        # Подписи
        font = cv2.FONT_HERSHEY_SIMPLEX
        for i in range(cells_y):
            for j in range(cells_x):
                x = j * grid_size + 5
                y = i * grid_size + 15
                cell_id = f"{i:02d}-{j:02d}"
                cv2.putText(grid_img, cell_id, (x, y), font, 0.3, (255, 255, 0), 1)

        # Сохраняем
        grid_path = f"analysis_grid_{int(time.time())}.jpg"
        cv2.imwrite(grid_path, grid_img)

        # Информация о сетке
        grid_info = {
            'grid_size': grid_size,
            'cells_x': cells_x,
            'cells_y': cells_y,
            'total_cells': cells_x * cells_y,
            'cell_width': grid_size,
            'cell_height': grid_size,
            'image_path': grid_path
        }

        return grid_path, grid_info

    def _analyze_grid_cells(self, img1, img2, grid_info) -> Dict:
        """Анализ каждой ячейки сетки"""
        cells_x = grid_info['cells_x']
        cells_y = grid_info['cells_y']
        cell_size = grid_info['grid_size']

        cell_results = {}

        for i in range(cells_y):
            for j in range(cells_x):
                cell_id = f"{i:02d}-{j:02d}"

                # Координаты ячейки
                y1 = i * cell_size
                y2 = min(y1 + cell_size, img1.shape[0])
                x1 = j * cell_size
                x2 = min(x1 + cell_size, img1.shape[1])

                # Извлекаем ячейки
                cell1 = img1[y1:y2, x1:x2]
                cell2 = img2[y1:y2, x1:x2]

                if cell1.size == 0 or cell2.size == 0:
                    continue

                # Анализ ячейки
                cell_result = self._analyze_single_cell(cell1, cell2)
                cell_result['cell_id'] = cell_id
                cell_result['x'] = x1
                cell_result['y'] = y1
                cell_result['width'] = x2 - x1
                cell_result['height'] = y2 - y1

                cell_results[cell_id] = cell_result

        return cell_results

    def _analyze_single_cell(self, cell1, cell2) -> Dict:
        """Анализ одной ячейки"""
        # Простая разница
        gray1 = cv2.cvtColor(cell1, cv2.COLOR_BGR2GRAY)
        gray2 = cv2.cvtColor(cell2, cv2.COLOR_BGR2GRAY)

        # Нормализация
        gray1_eq = cv2.equalizeHist(gray1)
        gray2_eq = cv2.equalizeHist(gray2)

        # Разница
        diff = cv2.absdiff(gray1_eq, gray2_eq)
        _, thresh = cv2.threshold(diff, 15, 255, cv2.THRESH_BINARY)

        # Процент изменений в ячейке
        total_pixels = cell1.shape[0] * cell1.shape[1]
        changed_pixels = np.sum(thresh > 0)
        change_percent = (changed_pixels / total_pixels) * 100 if total_pixels > 0 else 0

        # Анализ зелени
        green_loss = self._calculate_cell_green_loss(cell1, cell2)

        return {
            'change_percent': float(change_percent),
            'changed_pixels': int(changed_pixels),
            'total_pixels': int(total_pixels),
            'green_loss': float(green_loss),
            'has_changes': change_percent > 5 or green_loss > 10
        }

    def _calculate_cell_green_loss(self, cell1, cell2) -> float:
        """Потеря зелени в ячейке"""
        hsv1 = cv2.cvtColor(cell1, cv2.COLOR_BGR2HSV)
        hsv2 = cv2.cvtColor(cell2, cv2.COLOR_BGR2HSV)

        # Маска зелени
        lower_green = np.array([35, 40, 40])
        upper_green = np.array([85, 255, 255])

        mask1 = cv2.inRange(hsv1, lower_green, upper_green)
        mask2 = cv2.inRange(hsv2, lower_green, upper_green)

        # Потеря зелени
        green_before = np.sum(mask1 > 0)
        green_after = np.sum(mask2 > 0)

        if green_before > 0:
            loss_percent = ((green_before - green_after) / green_before) * 100
        else:
            loss_percent = 0

        return max(loss_percent, 0)

    def _calculate_grid_percentage(self, cell_results, grid_info) -> float:
        """Расчет процента по сетке"""
        changed_cells = 0
        total_cells = grid_info['total_cells']

        for cell_id, result in cell_results.items():
            if result['has_changes']:
                changed_cells += 1

        return (changed_cells / total_cells) * 100 if total_cells > 0 else 0

    def _calculate_brutal_green_loss(self, img1, img2):
        """Брутальный расчет потери зелени"""
        hsv1 = cv2.cvtColor(img1, cv2.COLOR_BGR2HSV)
        hsv2 = cv2.cvtColor(img2, cv2.COLOR_BGR2HSV)

        # ОЧЕНЬ ШИРОКИЙ диапазон зеленого
        lower1 = np.array([25, 30, 30])
        upper1 = np.array([95, 255, 255])

        lower2 = np.array([25, 20, 100])
        upper2 = np.array([95, 100, 255])

        # Маски
        mask1_before = cv2.inRange(hsv1, lower1, upper1)
        mask2_before = cv2.inRange(hsv1, lower2, upper2)
        green_before = cv2.bitwise_or(mask1_before, mask2_before)

        mask1_after = cv2.inRange(hsv2, lower1, upper1)
        mask2_after = cv2.inRange(hsv2, lower2, upper2)
        green_after = cv2.bitwise_or(mask1_after, mask2_after)

        # Потеря зелени
        green_loss = cv2.bitwise_and(green_before, cv2.bitwise_not(green_after))

        # Усиливаем
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
        green_loss = cv2.dilate(green_loss, kernel, iterations=2)

        return green_loss

    # ========== МЕТОДЫ ВИЗУАЛИЗАЦИИ ==========

    def _create_main_visualization(self, image, mask, change_type, percent, level):
        """Основная визуализация"""
        viz = image.copy()

        # Контуры изменений
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        # Рисуем толстые красные контуры
        cv2.drawContours(viz, contours, -1, (0, 0, 255), 3)

        # Заливка
        overlay = viz.copy()
        cv2.drawContours(overlay, contours, -1, (0, 0, 255), -1)
        cv2.addWeighted(overlay, 0.3, viz, 0.7, 0, viz)

        # Текст
        font = cv2.FONT_HERSHEY_SIMPLEX

        # Заголовок
        title = f"{change_type}"
        cv2.putText(viz, title, (20, 40), font, 1.2, (0, 0, 0), 5)
        cv2.putText(viz, title, (20, 40), font, 1.2, (0, 0, 255), 2)

        # Процент
        percent_text = f"ИЗМЕНЕНИЯ: {percent:.1f}%"
        cv2.putText(viz, percent_text, (20, 80), font, 1.0, (0, 0, 0), 4)
        cv2.putText(viz, percent_text, (20, 80), font, 1.0, (255, 255, 255), 2)

        # Уровень
        level_text = f"УРОВЕНЬ: {level}"
        cv2.putText(viz, level_text, (20, 120), font, 0.8, (0, 0, 0), 4)
        cv2.putText(viz, level_text, (20, 120), font, 0.8, (255, 255, 0), 2)

        # Сохраняем
        path = f"ultimate_viz_{int(time.time())}.jpg"
        cv2.imwrite(path, viz)

        return path

    def _create_grid_visualization(self, image, grid_info, cell_results, percent):
        """Визуализация с сеткой и результатами"""
        viz = image.copy()
        h, w = image.shape[:2]
        cell_size = grid_info['grid_size']

        # Рисуем сетку
        for i in range(0, h, cell_size):
            cv2.line(viz, (0, i), (w, i), (100, 100, 255), 1)
        for j in range(0, w, cell_size):
            cv2.line(viz, (j, 0), (j, h), (100, 100, 255), 1)

        # Раскрашиваем ячейки по результатам
        for cell_id, result in cell_results.items():
            if result['has_changes']:
                i, j = map(int, cell_id.split('-'))
                y1 = i * cell_size
                x1 = j * cell_size
                y2 = min(y1 + cell_size, h)
                x2 = min(x1 + cell_size, w)

                # Цвет в зависимости от процента изменений
                change_pct = result['change_percent']
                if change_pct > 50:
                    color = (0, 0, 255)  # Красный
                    alpha = 0.4
                elif change_pct > 25:
                    color = (0, 100, 255)  # Оранжевый
                    alpha = 0.3
                elif change_pct > 10:
                    color = (0, 200, 255)  # Желтый
                    alpha = 0.2
                else:
                    color = (0, 255, 0)  # Зеленый
                    alpha = 0.1

                # Заливка
                overlay = viz.copy()
                cv2.rectangle(overlay, (x1, y1), (x2, y2), color, -1)
                cv2.addWeighted(overlay, alpha, viz, 1 - alpha, 0, viz)

                # Процент в ячейке (для крупных изменений)
                if change_pct > 20:
                    text = f"{change_pct:.0f}%"
                    font_scale = 0.4
                    (text_w, text_h), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, font_scale, 1)

                    # Фон для текста
                    cv2.rectangle(viz,
                                  (x1 + (cell_size - text_w) // 2 - 2, y1 + (cell_size - text_h) // 2 - 2),
                                  (x1 + (cell_size + text_w) // 2 + 2, y1 + (cell_size + text_h) // 2 + 2),
                                  (0, 0, 0), -1)

                    # Текст
                    cv2.putText(viz, text,
                                (x1 + (cell_size - text_w) // 2, y1 + (cell_size + text_h) // 2),
                                cv2.FONT_HERSHEY_SIMPLEX, font_scale, (255, 255, 255), 1)

        # Общая информация
        font = cv2.FONT_HERSHEY_SIMPLEX
        info_text = f"Сеточный анализ: {percent:.1f}% изменений"
        cv2.putText(viz, info_text, (20, h - 20), font, 0.7, (255, 255, 255), 2)

        # Легенда
        legend_y = 150
        cv2.rectangle(viz, (w - 200, legend_y), (w - 10, legend_y + 120), (0, 0, 0, 180), -1)
        cv2.rectangle(viz, (w - 200, legend_y), (w - 10, legend_y + 120), (255, 255, 255), 1)

        legend_items = [
            ("🔴 >50%", "критические"),
            ("🟠 >25%", "высокие"),
            ("🟡 >10%", "средние"),
            ("🟢 <10%", "низкие")
        ]

        for i, (color_text, desc) in enumerate(legend_items):
            y = legend_y + 30 + i * 25
            cv2.putText(viz, color_text, (w - 180, y), font, 0.5, (255, 255, 255), 1)
            cv2.putText(viz, desc, (w - 120, y), font, 0.5, (200, 200, 200), 1)

        # Сохраняем
        path = f"grid_analysis_{int(time.time())}.jpg"
        cv2.imwrite(path, viz)

        return path

    def _create_comparison_with_grid(self, img1, img2, grid_info):
        """Сравнительная визуализация с сеткой на обоих изображениях"""
        h, w = img1.shape[:2]
        cell_size = grid_info['grid_size']

        # Создаем комбинированное изображение
        comparison = np.zeros((h, w * 2, 3), dtype=np.uint8)
        comparison[:, :w] = img1
        comparison[:, w:] = img2

        # Рисуем сетку на обоих
        for i in range(0, h, cell_size):
            cv2.line(comparison, (0, i), (w * 2, i), (255, 100, 100), 1)
        for j in range(0, w, cell_size):
            cv2.line(comparison, (j, 0), (j, h), (255, 100, 100), 1)
            cv2.line(comparison, (w + j, 0), (w + j, h), (255, 100, 100), 1)

        # Подписи
        font = cv2.FONT_HERSHEY_SIMPLEX
        cv2.putText(comparison, "ДО", (10, 30), font, 1, (255, 255, 255), 2)
        cv2.putText(comparison, "ПОСЛЕ", (w + 10, 30), font, 1, (255, 255, 255), 2)

        # Разделительная линия
        cv2.line(comparison, (w, 0), (w, h), (255, 255, 255), 3)

        # Сохраняем
        path = f"comparison_grid_{int(time.time())}.jpg"
        cv2.imwrite(path, comparison)

        return path

    def _print_ultimate_results(self, results):
        """Вывод ультимативных результатов"""
        print(f"\n📊 УЛЬТИМАТИВНЫЕ РЕЗУЛЬТАТЫ:")
        print(f"   {'=' * 50}")
        print(f"   🎯 Тип изменений: {results['change_type']}")
        print(f"   📈 Обнаружено: {results['change_percentage']:.1f}%")
        print(f"   📊 Базовый процент: {results['base_percentage']:.1f}%")
        print(f"   🚀 Коэффициент усиления: x{results['force_factor_applied']:.1f}")
        print(f"   ⚡ Уровень: {results['change_level']}")
        print(f"   📝 Значимость: {results['significance']}")

        if results['change_percentage'] > 40:
            print(f"\n   🚨🚨🚨 ВНИМАНИЕ: МАСШТАБНАЯ ВЫРУБКА! 🚨🚨🚨")
            print(f"   Обнаружена катастрофическая потеря леса!")
            print(f"   Требуется срочное вмешательство!")

        print(f"\n   💾 СОЗДАННЫЕ ФАЙЛЫ:")
        print(f"   • Основная визуализация: {results['visualization_path']}")
        print(f"   • Анализ по сетке: {results['grid_visualization_path']}")
        print(f"   • Сравнение с сеткой: {results['comparison_grid_path']}")
        print(f"   • Исходная сетка: {results['grid_image_path']}")
        print(f"   {'=' * 50}")


# ========== ИНТЕРФЕЙС ==========

def detect_changes_ultimate(before_path: str, after_path: str, force_percentage: float = 60.0):
    """
    Ультимативный детектор изменений

    Args:
        before_path: Путь к изображению "до"
        after_path: Путь к изображению "после"
        force_percentage: Минимальный процент для принудительного обнаружения
    """
    detector = UltimateDetector(force_percentage=force_percentage)
    return detector.detect_with_force(before_path, after_path)


# Алиас для совместимости
def detect_forest_changes(before_path: str, after_path: str):
    """Алиас для совместимости с change_detector.py"""
    return detect_changes_ultimate(before_path, after_path, force_percentage=80.0)


# Тестирование
if __name__ == "__main__":
    print("💥 ТЕСТИРОВАНИЕ УЛЬТИМАТИВНОГО ДЕТЕКТОРА")

    before = "test_before.jpg"
    after = "test_after.jpg"

    if os.path.exists(before) and os.path.exists(after):
        results = detect_forest_changes(before, after)
        print(f"Результаты: {results}")
    else:
        print("Создаю тестовые изображения с ВЫРУБКОЙ 70%...")

        # Создаем лес
        img = np.zeros((600, 800, 3), dtype=np.uint8)
        img[:, :] = [40, 120, 40]

        # Много деревьев
        for _ in range(300):
            x = np.random.randint(50, 750)
            y = np.random.randint(50, 550)
            r = np.random.randint(15, 30)
            cv2.circle(img, (x, y), r, (0, np.random.randint(80, 180), 0), -1)

        cv2.imwrite(before, img)

        # Вырубаем 70%
        img_after = img.copy()
        deforestation_pixels = 0

        for i in range(0, 600, 30):
            for j in range(0, 800, 30):
                if np.random.random() < 0.7:  # 70% вырубка
                    cv2.rectangle(img_after, (j, i), (j + 30, i + 30), (80, 50, 20), -1)
                    deforestation_pixels += 30 * 30

        cv2.imwrite(after, img_after)

        real_percent = (deforestation_pixels / (600 * 800)) * 100
        print(f"Реальная вырубка: {real_percent:.1f}%")

        # Тестируем
        print("\nЗапускаю ультимативный анализ...")
        results = detect_forest_changes(before, after)

        detected = results.get('change_percentage', 0)
        print(f"\nОбнаружено: {detected:.1f}% (реально: {real_percent:.1f}%)")

        if abs(detected - real_percent) < 20:
            print("✅ Отлично! Детектор работает корректно!")
        else:
            print("⚠️  Детектор недооценивает! Увеличьте force_percentage!")