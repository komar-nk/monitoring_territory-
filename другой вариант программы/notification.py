import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
from datetime import datetime
from typing import Dict, Any, Optional


class NotificationManager:
    def __init__(self, config):
        self.config = config

    def send_change_notification(self, territory_info: Dict[str, Any],
                                 change_data: Dict[str, Any],
                                 latest_image_path: Optional[str] = None):
        """
        Отправка уведомления об изменениях

        Args:
            territory_info: Информация о территории из базы данных
            change_data: Данные об изменениях
            latest_image_path: Путь к последнему изображению
        """
        message = self.create_change_message(territory_info, change_data)

        if self.config.EMAIL_ENABLED:
            self.send_email_notification(territory_info, message, latest_image_path)
        else:
            print("📧 Email уведомления отключены")

        print(f"📢 Уведомление отправлено: {territory_info['name']}")

    @staticmethod
    def create_change_message(territory: Dict[str, Any], change_data: Dict[str, Any]):
        # Извлекаем данные из change_data (используем разные возможные ключи)
        if 'change_percentage' in change_data:
            change_percent = change_data['change_percentage']
        elif 'change_score' in change_data:
            change_percent = change_data['change_score'] * 100
        else:
            change_percent = 0

        # Определяем тип изменений
        change_type = change_data.get('change_type', 'Неизвестно')
        if 'change_level' in change_data:
            change_type = change_data['change_level']

        # Уверенность/уровень изменений
        confidence = change_data.get('confidence', 0.8)

        # HTML версия сообщения
        html_message = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                h2 {{ color: #ff0000; }}
                table {{ border-collapse: collapse; width: 100%; max-width: 600px; }}
                th, td {{ border: 1px solid #ddd; padding: 12px; text-align: left; }}
                th {{ background-color: #f2f2f2; }}
                .alert {{ background-color: #fff3cd; padding: 15px; border-left: 4px solid #ffc107; }}
                .critical {{ background-color: #f8d7da; border-left: 4px solid #dc3545; }}
            </style>
        </head>
        <body>
            <h2>🚨 ОБНАРУЖЕНЫ ИЗМЕНЕНИЯ НА ТЕРРИТОРИИ!</h2>

            <div class="{'critical' if change_percent > 15 else 'alert'}">
                <strong>{"🚨 КРИТИЧЕСКИЕ ИЗМЕНЕНИЯ!" if change_percent > 15 else "⚠️ Обнаружены изменения"}</strong>
            </div>

            <h3>📋 Информация о территории:</h3>
            <table>
                <tr><th>📍 Название:</th><td>{territory['name']}</td></tr>
                <tr><th>📌 Координаты:</th><td>{territory['latitude']:.6f}, {territory['longitude']:.6f}</td></tr>
                <tr><th>📝 Описание:</th><td>{territory.get('description', 'нет')}</td></tr>
            </table>

            <h3>📊 Обнаруженные изменения:</h3>
            <table>
                <tr><th>📈 Процент изменений:</th><td>{change_percent:.2f}%</td></tr>
                <tr><th>🎯 Уровень изменений:</th><td>{change_type}</td></tr>
                <tr><th>✅ Уверенность:</th><td>{confidence:.1%}</td></tr>
                <tr><th>📅 Новый снимок:</th><td>{change_data.get('new_image_date', 'не указано')}</td></tr>
                <tr><th>📅 Старый снимок:</th><td>{change_data.get('old_image_date', 'не указано')}</td></tr>
                <tr><th>🕐 Время обнаружения:</th><td>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</td></tr>
            </table>

            <p><em>Система автоматического мониторинга спутниковых снимков</em></p>
            <p><small>Для детального просмотра откройте приложение мониторинга.</small></p>
        </body>
        </html>
        """

        # Текстовая версия
        text_message = f"""🚨 ОБНАРУЖЕНЫ ИЗМЕНЕНИЯ НА ТЕРРИТОРИИ!

📋 ИНФОРМАЦИЯ О ТЕРРИТОРИИ:
📍 Название: {territory['name']}
📌 Координаты: {territory['latitude']:.6f}, {territory['longitude']:.6f}
📝 Описание: {territory.get('description', 'нет')}

📊 ОБНАРУЖЕННЫЕ ИЗМЕНЕНИЯ:
📈 Процент изменений: {change_percent:.2f}%
🎯 Уровень изменений: {change_type}
✅ Уверенность: {confidence:.1%}
📅 Новый снимок: {change_data.get('new_image_date', 'не указано')}
📅 Старый снимок: {change_data.get('old_image_date', 'не указано')}
🕐 Время обнаружения: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Система автоматического мониторинга спутниковых снимков
"""

        return {
            'html': html_message,
            'text': text_message
        }

    def send_email_notification(self, territory: Dict[str, Any],
                                message_data: Dict[str, str],
                                image_path: Optional[str] = None):
        try:
            # Создаем сообщение
            msg = MIMEMultipart('alternative')
            msg['Subject'] = f"🚨 Изменения на {territory['name']} - {message_data.get('change_percent', 0):.1f}%"
            msg['From'] = self.config.EMAIL_FROM
            msg['To'] = self.config.EMAIL_TO

            # Добавляем текстовую и HTML версии
            part1 = MIMEText(message_data['text'], 'plain', 'utf-8')
            part2 = MIMEText(message_data['html'], 'html', 'utf-8')
            msg.attach(part1)
            msg.attach(part2)

            # Добавляем изображение если есть
            if image_path and os.path.exists(image_path):
                with open(image_path, 'rb') as f:
                    img_data = f.read()

                image = MIMEImage(img_data)
                image.add_header('Content-ID', '<latest_image>')
                image.add_header('Content-Disposition', 'inline',
                                 filename=f"{territory['name']}_{datetime.now().strftime('%Y%m%d')}.png")
                msg.attach(image)

                # Обновляем HTML с изображением
                html_with_image = message_data['html'].replace(
                    '</body>',
                    f'<h3>📷 Последний снимок:</h3>'
                    f'<img src="cid:latest_image" alt="Снимок территории {territory["name"]}" style="max-width: 600px; border: 1px solid #ddd;">'
                    f'</body>'
                )
                # Создаем новую часть с изображением
                part2 = MIMEText(html_with_image, 'html', 'utf-8')
                msg.get_payload()[1] = part2  # Заменяем HTML часть

            # Подключаемся к SMTP серверу
            server = smtplib.SMTP(self.config.SMTP_SERVER, self.config.SMTP_PORT)
            server.starttls()  # Включаем шифрование
            server.login(self.config.EMAIL_FROM, self.config.EMAIL_PASSWORD)

            # Отправляем письмо
            server.send_message(msg)
            server.quit()

            print(f"✅ Email уведомление отправлено на {self.config.EMAIL_TO}")

        except Exception as e:
            print(f"❌ Ошибка отправки email: {e}")
            import traceback
            traceback.print_exc()

    def test_email_connection(self):
        """Тестирование подключения к почте"""
        try:
            print(f"🔧 Тестирование подключения к почте...")
            print(f"   Сервер: {self.config.SMTP_SERVER}:{self.config.SMTP_PORT}")
            print(f"   От: {self.config.EMAIL_FROM}")
            print(f"   Кому: {self.config.EMAIL_TO}")

            server = smtplib.SMTP(self.config.SMTP_SERVER, self.config.SMTP_PORT, timeout=10)
            server.starttls()
            server.login(self.config.EMAIL_FROM, self.config.EMAIL_PASSWORD)
            server.quit()
            print("✅ Подключение к почте успешно")
            return True
        except Exception as e:
            print(f"❌ Ошибка подключения к почте: {e}")
            return False

    def send_summary_report(self, changes_data: list, total_locations: int):
        """Отправляет сводный отчет по всем изменениям"""
        try:
            if not self.config.EMAIL_ENABLED:
                print("📧 Email уведомления отключены")
                return

            changes_count = len(changes_data)

            # Формируем HTML отчет
            html_content = f"""
            <html>
            <head>
                <style>
                    body {{ font-family: Arial, sans-serif; margin: 20px; }}
                    h2 {{ color: #007bff; }}
                    table {{ border-collapse: collapse; width: 100%; }}
                    th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                    th {{ background-color: #f2f2f2; }}
                    .change-high {{ background-color: #ffcccc; }}
                    .change-medium {{ background-color: #fff3cd; }}
                    .change-low {{ background-color: #d4edda; }}
                </style>
            </head>
            <body>
                <h2>📊 СВОДНЫЙ ОТЧЕТ ПО МОНИТОРИНГУ</h2>
                <p>Обнаружено <strong>{changes_count}</strong> изменений на <strong>{total_locations}</strong> территориях</p>

                <table>
                    <tr>
                        <th>Территория</th>
                        <th>Изменения</th>
                        <th>Уровень</th>
                        <th>Дата нового снимка</th>
                        <th>Дата старого снимка</th>
                    </tr>
            """

            text_content = f"📊 СВОДНЫЙ ОТЧЕТ ПО МОНИТОРИНГУ\n\n"
            text_content += f"Обнаружено {changes_count} изменений на {total_locations} территориях\n\n"
            text_content += "Территория | Изменения | Уровень | Новый снимок | Старый снимок\n"
            text_content += "-" * 80 + "\n"

            for change in changes_data:
                territory_name = change.get('territory_name', 'Неизвестно')
                change_percent = change.get('change_percentage', 0)
                change_level = change.get('change_level', 'неизвестно')
                detected_at = change.get('detected_at', '')

                # Определяем класс для строки таблицы
                row_class = ''
                if change_percent > 15:
                    row_class = 'change-high'
                elif change_percent > 5:
                    row_class = 'change-medium'
                else:
                    row_class = 'change-low'

                html_content += f"""
                    <tr class="{row_class}">
                        <td>{territory_name}</td>
                        <td>{change_percent:.2f}%</td>
                        <td>{change_level}</td>
                        <td>{change.get('new_image_date', '')}</td>
                        <td>{change.get('old_image_date', '')}</td>
                    </tr>
                """

                text_content += f"{territory_name} | {change_percent:.2f}% | {change_level} | {change.get('new_image_date', '')} | {change.get('old_image_date', '')}\n"

            html_content += """
                </table>
                <p><small>Отчет сгенерирован автоматически. Время генерации: """ + datetime.now().strftime(
                '%Y-%m-%d %H:%M:%S') + """</small></p>
            </body>
            </html>
            """

            text_content += f"\nОтчет сгенерирован автоматически. Время генерации: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

            # Создаем сообщение
            msg = MIMEMultipart('alternative')
            msg['Subject'] = f"📊 Отчет мониторинга: {changes_count} изменений в {total_locations} местах"
            msg['From'] = self.config.EMAIL_FROM
            msg['To'] = self.config.EMAIL_TO

            # Добавляем текстовую и HTML версии
            part1 = MIMEText(text_content, 'plain', 'utf-8')
            part2 = MIMEText(html_content, 'html', 'utf-8')
            msg.attach(part1)
            msg.attach(part2)

            # Подключаемся к SMTP серверу
            server = smtplib.SMTP(self.config.SMTP_SERVER, self.config.SMTP_PORT)
            server.starttls()
            server.login(self.config.EMAIL_FROM, self.config.EMAIL_PASSWORD)

            # Отправляем письмо
            server.send_message(msg)
            server.quit()

            print(f"✅ Сводный отчет отправлен на {self.config.EMAIL_TO}")

        except Exception as e:
            print(f"❌ Ошибка отправки сводного отчета: {e}")

    def send_test_email(self):
        """Отправка тестового письма"""
        try:
            msg = MIMEMultipart('alternative')
            msg['Subject'] = "✅ Тестовое письмо от системы мониторинга"
            msg['From'] = self.config.EMAIL_FROM
            msg['To'] = self.config.EMAIL_TO

            html = """
            <html>
            <body>
                <h2>✅ Тестовое письмо успешно отправлено!</h2>
                <p>Система уведомлений работает корректно.</p>
                <p><small>Время отправки: """ + datetime.now().strftime('%Y-%m-%d %H:%M:%S') + """</small></p>
            </body>
            </html>
            """

            text = "✅ Тестовое письмо успешно отправлено!\nСистема уведомлений работает корректно.\nВремя отправки: " + datetime.now().strftime(
                '%Y-%m-%d %H:%M:%S')

            part1 = MIMEText(text, 'plain', 'utf-8')
            part2 = MIMEText(html, 'html', 'utf-8')
            msg.attach(part1)
            msg.attach(part2)

            server = smtplib.SMTP(self.config.SMTP_SERVER, self.config.SMTP_PORT)
            server.starttls()
            server.login(self.config.EMAIL_FROM, self.config.EMAIL_PASSWORD)
            server.send_message(msg)
            server.quit()

            print(f"✅ Тестовое письмо отправлено на {self.config.EMAIL_TO}")
            return True

        except Exception as e:
            print(f"❌ Ошибка отправки тестового письма: {e}")
            return False