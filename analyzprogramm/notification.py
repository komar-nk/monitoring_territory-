"""
Менеджер уведомлений для отправки email с изображениями изменений
Улучшенная версия с обработкой ошибок и гарантированной отправкой
"""

import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime
from typing import Dict, Any, Optional, List
import traceback
from PIL import Image, ImageDraw
import cv2
import numpy as np


class NotificationManager:
    def __init__(self, config=None):
        """
        Инициализация менеджера уведомлений

        Args:
            config: Конфигурация с настройками email
        """
        self.config = config
        self.last_error = None
        self.sent_count = 0

        if config:
            print(f"✓ NotificationManager инициализирован")
            if hasattr(config, 'EMAIL_ENABLED') and config.EMAIL_ENABLED:
                print(f"  Email уведомления: ВКЛЮЧЕНЫ")
                print(f"  Получатель: {config.EMAIL_TO}")
                print(f"  Порог: {config.CHANGE_THRESHOLD}%")
            else:
                print(f"  Email уведомления: ВЫКЛЮЧЕНЫ")
        else:
            print(f"⚠ NotificationManager: конфиг не предоставлен")

    # ========== ОСНОВНЫЕ ФУНКЦИИ ==========

    def send_change_notification(self, territory_info: Dict[str, Any],
                                 change_data: Dict[str, Any],
                                 latest_image_path: Optional[str] = None,
                                 old_image_path: Optional[str] = None,
                                 grid_image_path: Optional[str] = None,
                                 heatmap_path: Optional[str] = None,
                                 visualization_path: Optional[str] = None,
                                 changes_visualization_path: Optional[str] = None,
                                 comparison_grid_path: Optional[str] = None,
                                 grid_comparison_path: Optional[str] = None) -> bool:
        """
        Основная функция отправки уведомлений об изменениях
        с поддержкой всех типов визуализаций

        Returns:
            bool: True если отправка успешна, False если ошибка
        """
        print(f"\n{'=' * 60}")
        print(" ОТПРАВКА УВЕДОМЛЕНИЯ ОБ ИЗМЕНЕНИЯХ")
        print(f"{'=' * 60}")

        # Проверяем конфигурацию
        if not self._check_config():
            return False

        # Проверяем наличие необходимых данных
        if not self._validate_input_data(territory_info, change_data):
            return False

        # Собираем информацию о ВСЕХ файлах
        files_info = self._collect_files_info({
            'latest_image': latest_image_path,
            'old_image': old_image_path,
            'grid_visualization': grid_image_path,
            'heatmap': heatmap_path,
            'visualization': visualization_path,
            'changes_highlighted': changes_visualization_path,
            'comparison_grid': comparison_grid_path,
            'grid_comparison': grid_comparison_path,
            'comparison': change_data.get('comparison_path'),
            'grid_analysis': change_data.get('grid_analysis_path'),
            'changes_grid': change_data.get('changes_grid_path'),
        })

        # Создаем сравнительное изображение, если есть оба изображения
        comparison_path = None
        if old_image_path and latest_image_path:
            comparison_path = self._create_comparison_image(
                old_image_path, latest_image_path, change_data, territory_info
            )
            if comparison_path:
                files_info['comparison_auto'] = {
                    'path': comparison_path,
                    'exists': True,
                    'name': os.path.basename(comparison_path)
                }

        # Проверяем есть ли файлы сеточного анализа
        has_grid_files = (grid_image_path or heatmap_path or visualization_path or
                          changes_visualization_path or comparison_grid_path or grid_comparison_path)

        if has_grid_files:
            print("  📐 Обнаружены файлы сеточного анализа...")

        print("  📧 Подготовка email со всеми файлами...")
        success = self._send_email_with_attachments(
            territory_info, change_data, files_info
        )

        # Очищаем временные файлы
        if comparison_path and os.path.exists(comparison_path):
            try:
                os.remove(comparison_path)
                print(f"  🗑️ Удален временный файл: {comparison_path}")
            except:
                pass

        return success
    def send_notification_with_grid(self, territory_info: Dict[str, Any],
                                    change_data: Dict[str, Any],
                                    grid_files: Dict[str, str]) -> bool:
        """
        Отправка уведомления с сеточными визуализациями

        Args:
            territory_info: Информация о территории
            change_data: Данные об изменениях
            grid_files: Словарь с путями к файлам сетки

        Returns:
            bool: True если отправка успешна
        """
        print(f"\n ОТПРАВКА УВЕДОМЛЕНИЯ С СЕТКОЙ")

        if not self._check_config():
            return False

        # Собираем все файлы
        all_files = {
            'visualization': change_data.get('visualization_path', ''),
            'comparison': change_data.get('comparison_path', ''),
            'grid_image': grid_files.get('grid_image', ''),
            'grid_analysis': grid_files.get('grid_analysis', ''),
            'comparison_grid': grid_files.get('comparison_grid', ''),
            'latest': change_data.get('latest_image_path', ''),
            'old': change_data.get('old_image_path', '')
        }

        # Проверяем существование файлов
        files_info = self._collect_files_info(all_files)

        # Создаем HTML с описанием сетки
        html_grid_content = self._create_html_with_grid(territory_info, change_data, grid_files)

        # Создаем тему письма
        subject = f"📐 АНАЛИЗ С СЕТКОЙ: {territory_info.get('name', '')} - {change_data.get('change_percentage', 0):.1f}%"

        # Отправляем email
        return self._send_email_with_grid(subject, territory_info, change_data, files_info, html_grid_content)

    # ========== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==========

    def _check_config(self) -> bool:
        """Проверка конфигурации email"""
        if not self.config:
            print(" Ошибка: конфигурация email не предоставлена")
            self.last_error = "Конфигурация email не предоставлена"
            return False

        if not hasattr(self.config, 'EMAIL_ENABLED') or not self.config.EMAIL_ENABLED:
            print("ℹ Email уведомления отключены в настройках")
            return False

        required_fields = ['EMAIL_FROM', 'EMAIL_PASSWORD', 'EMAIL_TO',
                           'SMTP_SERVER', 'SMTP_PORT']

        for field in required_fields:
            if not hasattr(self.config, field) or not getattr(self.config, field):
                print(f" Ошибка: не указано поле {field} в конфигурации")
                self.last_error = f"Не указано поле {field} в конфигурации"
                return False

        return True

    def _validate_input_data(self, territory_info: Dict[str, Any],
                             change_data: Dict[str, Any]) -> bool:
        """Проверка входных данных"""
        if 'name' not in territory_info or not territory_info['name']:
            print(" Ошибка: отсутствует название территории")
            return False

        if 'change_percentage' not in change_data:
            print(" Ошибка: отсутствует процент изменений")
            return False

        return True

    def _collect_files_info(self, file_paths: Dict[str, Any]) -> Dict[str, Dict]:
        """Собирает информацию о файлах"""
        files_info = {}

        for file_type, file_path in file_paths.items():
            # Пропускаем None
            if file_path is None:
                continue

            # Если уже словарь
            if isinstance(file_path, dict):
                if 'exists' in file_path and file_path['exists']:
                    files_info[file_type] = file_path
                continue

            # Если это кортеж/список - берем первый элемент
            if isinstance(file_path, (tuple, list)):
                if file_path:
                    # Ищем строку или словарь с путем
                    for item in file_path:
                        if isinstance(item, str) and os.path.exists(item):
                            file_path = item
                            break
                        elif isinstance(item, dict) and 'path' in item and os.path.exists(item['path']):
                            file_path = item['path']
                            break
                    else:
                        continue  # Не нашли подходящий элемент
                else:
                    continue  # Пустой список/кортеж

            # Проверяем что это строка
            if not isinstance(file_path, str):
                continue

            # Проверяем существование файла
            if os.path.exists(file_path):
                try:
                    file_size = os.path.getsize(file_path) / 1024  # KB
                    files_info[file_type] = {
                        'path': file_path,
                        'size_kb': file_size,
                        'exists': True,
                        'name': os.path.basename(file_path)
                    }
                    print(f"   {file_type}: {os.path.basename(file_path)} ({file_size:.1f} KB)")
                except Exception as e:
                    print(f"  ️ Ошибка проверки файла {file_path}: {e}")
            elif file_path:
                print(f"   {file_type}: файл не существует - {file_path}")

        return files_info

    def _create_comparison_image(self, old_path: str, new_path: str,
                                 change_data: Dict[str, Any], territory_info: Dict[str, Any]) -> Optional[str]:
        """Создает сравнительное изображение"""
        try:
            print("  🖼 Creating comparison image...")

            # Используем OpenCV
            old_img = cv2.imread(old_path)
            new_img = cv2.imread(new_path)

            if old_img is None or new_img is None:
                print("   Failed to load images")
                return None

            # Приводим к одинаковому размеру
            height = min(old_img.shape[0], new_img.shape[0])
            width = min(old_img.shape[1], new_img.shape[1])

            old_img = cv2.resize(old_img, (width, height))
            new_img = cv2.resize(new_img, (width, height))

            # Создаем подложку
            comparison = np.zeros((height + 80, width * 2, 3), dtype=np.uint8)
            comparison.fill(40)

            # Добавляем изображения
            comparison[80:, :width] = old_img
            comparison[80:, width:] = new_img

            # Добавляем текст (английский)
            font = cv2.FONT_HERSHEY_SIMPLEX
            change_percent = change_data.get('change_percentage', 0)
            territory_name = territory_info.get('name', 'Unknown territory')

            # Заголовки (английский)
            cv2.putText(comparison, "BEFORE", (10, 25),
                        font, 0.8, (255, 255, 255), 2)
            cv2.putText(comparison, "AFTER", (width + 10, 25),
                        font, 0.8, (255, 255, 255), 2)

            # Процент изменений
            cv2.putText(comparison, f"Changes: {change_percent:.1f}%",
                        (10, 55), font, 0.7, (255, 255, 150), 2)

            # Название территории
            name_x = width - cv2.getTextSize(territory_name, font, 0.6, 2)[0][0] - 10
            cv2.putText(comparison, territory_name, (name_x, 55),
                        font, 0.6, (200, 255, 200), 2)

            # Даты снимков
            old_date = change_data.get('old_image_date', '')
            new_date = change_data.get('new_image_date', '')

            if old_date:
                cv2.putText(comparison, f"Date: {old_date}", (10, height + 60),
                            font, 0.5, (200, 200, 255), 1)
            if new_date:
                cv2.putText(comparison, f"Date: {new_date}", (width + 10, height + 60),
                            font, 0.5, (200, 200, 255), 1)

            # Сохраняем
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            comparison_path = f"comparison_{timestamp}.jpg"
            cv2.imwrite(comparison_path, comparison, [cv2.IMWRITE_JPEG_QUALITY, 85])

            print(f"   Comparison created: {comparison_path}")
            return comparison_path

        except Exception as e:
            print(f"   Error creating comparison: {e}")
            return None

    # ========== EMAIL ФУНКЦИИ ==========

    def _send_email_with_attachments(self, territory_info: Dict[str, Any],
                                     change_data: Dict[str, Any],
                                     files_info: Dict[str, Dict]) -> bool:
        """Отправка email с вложениями"""
        try:
            print("\n✉ ПОДГОТОВКА EMAIL...")

            # Создаем тему письма
            subject = self._create_email_subject(territory_info, change_data)

            # Создаем сообщение
            msg = MIMEMultipart('mixed')
            msg['Subject'] = subject
            msg['From'] = self.config.EMAIL_FROM
            msg['To'] = self.config.EMAIL_TO

            # Добавляем текстовую и HTML версии
            text_content = self._create_text_content(territory_info, change_data)
            html_content = self._create_html_content(territory_info, change_data, files_info)

            msg.attach(MIMEText(text_content, 'plain', 'utf-8'))
            msg.attach(MIMEText(html_content, 'html', 'utf-8'))

            # Прикрепляем файлы
            attachments_added = self._attach_files(msg, files_info)
            print(f"  📎 Прикреплено файлов: {attachments_added}")

            # Отправляем email
            return self._send_smtp_email(msg)

        except Exception as e:
            print(f" Ошибка подготовки email: {e}")
            self.last_error = str(e)
            return False

    def _create_email_subject(self, territory_info: Dict[str, Any],
                              change_data: Dict[str, Any]) -> str:
        """Создание темы письма"""
        change_percent = change_data.get('change_percentage', 0)
        territory_name = territory_info.get('name', 'Территория')

        # Определяем эмодзи в зависимости от процента изменений
        if change_percent > 50:
            emoji = "🚨🚨🚨"
            level = "КРИТИЧЕСКИЙ"
        elif change_percent > 20:
            emoji = "🚨🚨"
            level = "ВЫСОКИЙ"
        elif change_percent > 10:
            emoji = "🚨"
            level = "СРЕДНИЙ"
        elif change_percent > 5:
            emoji = "⚠️"
            level = "НИЗКИЙ"
        else:
            emoji = "ℹ️"
            level = "МИНИМАЛЬНЫЙ"

        return f"{emoji} {level} изменения на {territory_name} - {change_percent:.1f}%"

    def _create_text_content(self, territory_info: Dict[str, Any],
                             change_data: Dict[str, Any]) -> str:
        """Создание текстового содержимого письма"""
        change_percent = change_data.get('change_percentage', 0)
        territory_name = territory_info.get('name', 'Неизвестная территория')

        return f"""
{'=' * 60}
🚨 ОБНАРУЖЕНЫ ИЗМЕНЕНИЯ НА ТЕРРИТОРИИ
{'=' * 60}

📌 ТЕРРИТОРИЯ: {territory_name}
📊 ИЗМЕНЕНИЯ: {change_percent:.1f}%
📅 ДАТЫ: {change_data.get('old_image_date', '?')} → {change_data.get('new_image_date', '?')}
⏰ ВРЕМЯ: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

📎 В письме прикреплены изображения с изменениями.
{'=' * 60}
Автоматическая система мониторинга
{'=' * 60}
"""

    def _create_html_content(self, territory_info: Dict[str, Any],
                             change_data: Dict[str, Any],
                             files_info: Dict[str, Dict]) -> str:
        """Создание HTML содержимого письма"""
        change_percent = change_data.get('change_percentage', 0)
        territory_name = territory_info.get('name', 'Неизвестная территория')

        # Берем реальный процент изменений, если есть
        real_change_percent = change_data.get('real_change_percentage', change_percent)
        base_percent = change_data.get('base_percentage', change_percent)

        # Информация о детекторе
        change_type = change_data.get('change_type_detailed', change_data.get('change_type', 'неизвестно'))
        is_seasonal = change_data.get('is_seasonal', False)
        changed_pixels = change_data.get('changed_pixels', 0)
        total_pixels = change_data.get('total_pixels', 0)

        # Детали анализа
        details = change_data.get('details', {})

        # Определяем цвет
        if change_percent > 50:
            color = "#ff4444"
            header_text = "🚨 КРИТИЧЕСКИЕ ИЗМЕНЕНИЯ"
        elif change_percent > 20:
            color = "#ff8800"
            header_text = "⚠️ ЗНАЧИТЕЛЬНЫЕ ИЗМЕНЕНИЯ"
        elif change_percent > 10:
            color = "#44aa44"
            header_text = "📊 ЗАМЕТНЫЕ ИЗМЕНЕНИЯ"
        else:
            color = "#4444ff"
            header_text = "ℹ️ ИЗМЕНЕНИЯ"

        # Формируем детали анализа
        details_html = ""
        if details:
            details_html = "<h3>📊 ДЕТАЛИ АНАЛИЗА</h3><table>"
            for key, value in details.items():
                details_html += f"<tr><td><strong>{key}:</strong></td><td>{value:.2f if isinstance(value, float) else value}</td></tr>"
            details_html += "</table>"

        # Информация о сезонности
        seasonal_html = ""
        if is_seasonal:
            seasonal_html = """
            <div style="margin: 10px 0; padding: 10px; background: #fff3cd; border-left: 4px solid #ffc107; border-radius: 5px;">
                <strong>⚠️ СЕЗОННЫЕ ИЗМЕНЕНИЯ</strong>
                <p>Обнаружены изменения, которые могут быть вызваны сезонными факторами (смена сезона, освещение и т.д.)</p>
            </div>
            """
        else:
            seasonal_html = """
            <div style="margin: 10px 0; padding: 10px; background: #d1ecf1; border-left: 4px solid #0dcaf0; border-radius: 5px;">
                <strong>✅ РЕАЛЬНЫЕ ИЗМЕНЕНИЯ</strong>
                <p>Обнаружены реальные изменения на территории (не связанные с сезонными факторами)</p>
            </div>
            """

        # Процент изменений с деталями
        percent_html = ""
        if real_change_percent != base_percent:
            percent_html = f"""
            <div style="margin: 15px 0; padding: 15px; background: #f8f9fa; border-radius: 8px;">
                <h4>Процент изменений:</h4>
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px;">
                    <div style="text-align: center;">
                        <div style="font-size: 24px; font-weight: bold; color: #dc3545;">{real_change_percent:.1f}%</div>
                        <div style="font-size: 12px; color: #666;">реальные изменения</div>
                    </div>
                    <div style="text-align: center;">
                        <div style="font-size: 18px; color: #6c757d;">{base_percent:.1f}%</div>
                        <div style="font-size: 12px; color: #666;">общие изменения</div>
                    </div>
                </div>
            </div>
            """
        else:
            percent_html = f"""
            <div style="margin: 15px 0; padding: 15px; background: #f8f9fa; border-radius: 8px; text-align: center;">
                <div style="font-size: 28px; font-weight: bold; color: {color};">{change_percent:.1f}%</div>
                <div style="font-size: 14px; color: #666;">изменений территории</div>
            </div>
            """

        # Информация о пикселях
        pixels_html = ""
        if total_pixels > 0:
            pixels_percent = (changed_pixels / total_pixels) * 100
            pixels_html = f"""
            <div style="margin: 10px 0; padding: 10px; background: #e8f4f8; border-radius: 5px;">
                <strong>📈 Статистика пикселей:</strong>
                <div style="margin-top: 5px;">
                    <div style="display: flex; justify-content: space-between;">
                        <span>Изменено:</span>
                        <span><strong>{changed_pixels:,}</strong> пикселей ({pixels_percent:.1f}%)</span>
                    </div>
                    <div style="display: flex; justify-content: space-between;">
                        <span>Всего:</span>
                        <span><strong>{total_pixels:,}</strong> пикселей</span>
                    </div>
                </div>
            </div>
            """

        # Тип изменений
        type_html = f"""
        <div style="margin: 10px 0; padding: 10px; background: #f8f9fa; border-radius: 5px;">
            <strong>🏷️ Тип изменений:</strong>
            <div style="margin-top: 5px; font-size: 16px; font-weight: bold; color: {color};">{change_type}</div>
        </div>
        """

        # Список вложений
        attachments_list = ""
        for file_type, info in files_info.items():
            if isinstance(info, dict) and info.get('exists'):
                size = info.get('size_kb', 0)
                name = info.get('name', file_type)
                attachments_list += f"<li><strong>{file_type}:</strong> {name} ({size:.1f} KB)</li>"

        return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }}
            .container {{ max-width: 800px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
            .header {{ background: {color}; color: white; padding: 25px; border-radius: 10px; margin: -30px -30px 30px -30px; text-align: center; }}
            table {{ width: 100%; border-collapse: collapse; margin: 10px 0; }}
            th, td {{ padding: 10px; border-bottom: 1px solid #ddd; text-align: left; }}
            th {{ background: #f8f9fa; font-weight: bold; }}
            .footer {{ margin-top: 30px; padding-top: 20px; border-top: 1px solid #ddd; color: #666; text-align: center; }}
            .info-box {{ margin: 15px 0; padding: 15px; border-radius: 8px; }}
            .details-box {{ background: #f8f9fa; padding: 15px; border-radius: 8px; margin: 15px 0; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>{header_text}</h1>
                <h2>{territory_name}</h2>
            </div>

            {seasonal_html}
            {percent_html}
            {type_html}
            {pixels_html}

            <h3>📋 Информация о территории</h3>
            <table>
                <tr><th>Параметр</th><th>Значение</th></tr>
                <tr><td>Название</td><td>{territory_name}</td></tr>
                <tr><td>Координаты</td><td>{territory_info.get('latitude', 'N/A'):.6f}, {territory_info.get('longitude', 'N/A'):.6f}</td></tr>
                <tr><td>Дата старого снимка</td><td>{change_data.get('old_image_date', 'Неизвестно')}</td></tr>
                <tr><td>Дата нового снимка</td><td>{change_data.get('new_image_date', 'Неизвестно')}</td></tr>
                <tr><td>Уровень значимости</td><td>{change_data.get('significance', 'Неизвестно')}</td></tr>
            </table>

            {details_html}

            <h3>📎 Вложения ({len(files_info)})</h3>
            <ul>{attachments_list}</ul>

            <div class="footer">
                <p>📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                <p>🚨 Автоматическое уведомление системы мониторинга</p>
                <p style="font-size: 12px; color: #888; margin-top: 10px;">
                    Использован улучшенный детектор с фильтрацией сезонных изменений
                </p>
            </div>
        </div>
    </body>
    </html>
    """

    def _attach_files(self, msg: MIMEMultipart, files_info: Dict[str, Dict]) -> int:
        """Прикрепление файлов к email"""
        attachments_added = 0

        for file_type, info in files_info.items():
            if not isinstance(info, dict) or not info.get('exists'):
                continue

            file_path = info.get('path', '')
            if not file_path or not os.path.exists(file_path):
                continue

            try:
                with open(file_path, 'rb') as f:
                    file_data = f.read()

                filename = os.path.basename(file_path)

                if filename.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.bmp')):
                    img = MIMEImage(file_data, name=filename)
                    img.add_header('Content-Disposition', 'attachment', filename=filename)
                    msg.attach(img)
                else:
                    part = MIMEBase('application', 'octet-stream')
                    part.set_payload(file_data)
                    encoders.encode_base64(part)
                    part.add_header('Content-Disposition', 'attachment', filename=filename)
                    msg.attach(part)

                attachments_added += 1

            except Exception as e:
                print(f"  ⚠ Ошибка прикрепления {file_path}: {e}")

        return attachments_added

    def _send_smtp_email(self, msg: MIMEMultipart) -> bool:
        """Отправка email через SMTP"""
        try:
            print(f"  🔗 Подключение к SMTP серверу...")
            print(f"    Сервер: {self.config.SMTP_SERVER}:{self.config.SMTP_PORT}")

            server = smtplib.SMTP(self.config.SMTP_SERVER, self.config.SMTP_PORT, timeout=30)

            if self.config.SMTP_PORT == 587:
                server.starttls()
                print("     TLS включен")

            print(f"     Авторизация...")
            server.login(self.config.EMAIL_FROM, self.config.EMAIL_PASSWORD)

            print(f"     Отправка письма...")
            server.send_message(msg)
            server.quit()

            print(f"     Email успешно отправлен!")
            print(f"       Тема: {msg['Subject']}")
            print(f"       Кому: {self.config.EMAIL_TO}")

            self.sent_count += 1
            return True

        except smtplib.SMTPAuthenticationError:
            print(" Ошибка аутентификации: неверный логин или пароль")
            print("   Для Gmail используйте пароль приложения, а не обычный пароль!")
            self.last_error = "Ошибка аутентификации"
            return False
        except Exception as e:
            print(f" Ошибка отправки: {e}")
            self.last_error = str(e)
            return False

    def _send_email_with_grid(self, subject: str,
                              territory_info: Dict[str, Any],
                              change_data: Dict[str, Any],
                              files_info: Dict[str, Dict],
                              html_grid_content: str) -> bool:
        """Отправка email с сеточными визуализациями"""
        try:
            msg = MIMEMultipart('mixed')
            msg['Subject'] = subject
            msg['From'] = self.config.EMAIL_FROM
            msg['To'] = self.config.EMAIL_TO

            # Текстовая версия
            text_content = self._create_text_content(territory_info, change_data)
            msg.attach(MIMEText(text_content, 'plain', 'utf-8'))

            # HTML версия с сеткой
            html_content = self._create_html_content(territory_info, change_data, files_info)
            html_full = html_content.replace('</body>', f'{html_grid_content}</body>')
            msg.attach(MIMEText(html_full, 'html', 'utf-8'))

            # Прикрепляем файлы
            self._attach_files(msg, files_info)

            # Отправляем
            return self._send_smtp_email(msg)

        except Exception as e:
            print(f" Ошибка отправки email с сеткой: {e}")
            return False

    def _create_html_with_grid(self, territory_info: Dict[str, Any],
                               change_data: Dict[str, Any],
                               grid_files: Dict[str, str]) -> str:
        """Создание HTML с информацией о сеточном анализе"""
        return """
        <div style="margin: 20px 0; padding: 20px; background: #f0f8ff; border-radius: 10px; border: 2px solid #4CAF50;">
            <h3>📐 АНАЛИЗ ПО КООРДИНАТНОЙ СЕТКЕ 16x16</h3>
            <p><strong>Территория разбита на 256 ячеек для точного анализа</strong></p>

            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin: 20px 0;">
                <div style="text-align: center;">
                    <h4>🔍 Анализ по ячейкам</h4>
                    <p>Цвет показывает процент изменений в каждой ячейке:</p>
                    <ul style="text-align: left;">
                        <li>🔴 <strong>Красный:</strong> >50% (критические)</li>
                        <li>🟠 <strong>Оранжевый:</strong> 25-50% (высокие)</li>
                        <li>🟡 <strong>Желтый:</strong> 10-25% (средние)</li>
                        <li>🟢 <strong>Зеленый:</strong> <10% (низкие)</li>
                    </ul>
                </div>

                <div style="text-align: center;">
                    <h4>🎯 Преимущества сеточного анализа:</h4>
                    <ul style="text-align: left;">
                        <li>✅ Точно определяет координаты изменений</li>
                        <li>✅ Показывает распределение изменений</li>
                        <li>✅ Фильтрует сезонные изменения</li>
                        <li>✅ Обеспечивает повторяемость измерений</li>
                    </ul>
                </div>
            </div>
        </div>
        """

    def test_connection(self) -> bool:
        """Тестирование подключения к SMTP серверу"""
        if not self._check_config():
            return False

        try:
            print(f"\n🔍 ТЕСТ ПОДКЛЮЧЕНИЯ К SMTP...")
            server = smtplib.SMTP(self.config.SMTP_SERVER, self.config.SMTP_PORT, timeout=10)

            if self.config.SMTP_PORT == 587:
                server.starttls()

            server.login(self.config.EMAIL_FROM, self.config.EMAIL_PASSWORD)
            server.quit()

            print(f"   Подключение успешно!")
            return True

        except Exception as e:
            print(f"   Ошибка подключения: {e}")
            return False


# ========== КОНФИГУРАЦИОННЫЙ КЛАСС ==========

class EmailConfig:
    """Класс для хранения конфигурации email"""

    def __init__(self, dotenv_file: str = '.env'):
        try:
            from dotenv import load_dotenv
            load_dotenv(dotenv_file)

            self.EMAIL_ENABLED = os.getenv('EMAIL_ENABLED', 'False').lower() == 'true'
            self.SMTP_SERVER = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
            self.SMTP_PORT = int(os.getenv('SMTP_PORT', '587'))
            self.EMAIL_FROM = os.getenv('EMAIL_FROM', '')
            self.EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD', '')
            self.EMAIL_TO = os.getenv('EMAIL_TO', '')
            self.CHANGE_THRESHOLD = float(os.getenv('CHANGE_THRESHOLD', '5.0'))

            if self.EMAIL_ENABLED and self.EMAIL_FROM and self.EMAIL_PASSWORD:
                print(f"✓ Конфигурация email загружена")
            else:
                print(f"⚠ Конфигурация email неполная или отключена")

        except Exception as e:
            print(f" Ошибка загрузки конфигурации: {e}")
            self.EMAIL_ENABLED = False


# ========== ПРОСТАЯ ВЕРСИЯ ДЛЯ СОВМЕСТИМОСТИ ==========

def send_simple_notification(territory_info: Dict[str, Any],
                             change_data: Dict[str, Any],
                             config: Any = None) -> bool:
    """Простая функция для отправки уведомления"""
    try:
        if config is None:
            config = EmailConfig()

        notifier = NotificationManager(config)
        return notifier.send_change_notification(territory_info, change_data)

    except Exception as e:
        print(f" Ошибка отправки уведомления: {e}")
        return False


# ========== ТЕСТИРОВАНИЕ ==========

if __name__ == "__main__":
    print(" ТЕСТИРОВАНИЕ NOTIFICATION MANAGER")
    print("=" * 50)

    # Создаем конфигурацию
    config = EmailConfig()

    if not config.EMAIL_ENABLED:
        print(" Email уведомления отключены в .env файле")
        print("   Установите EMAIL_ENABLED=true в файле .env")
        exit(1)

    if not config.EMAIL_FROM or not config.EMAIL_PASSWORD:
        print(" Не указан email или пароль в .env файле")
        print("   Заполните EMAIL_FROM и EMAIL_PASSWORD в файле .env")
        exit(1)

    # Создаем менеджер уведомлений
    notifier = NotificationManager(config)

    # Тестируем подключение
    print("\n1. Тестирование подключения к SMTP...")
    if notifier.test_connection():
        print("    Подключение успешно")
    else:
        print("    Не удалось подключиться")
        exit(1)

    print("\n Менеджер уведомлений готов к работе!")
    print("   Для отправки уведомлений используйте:")
    print("   notifier.send_change_notification(territory_info, change_data, ...)")