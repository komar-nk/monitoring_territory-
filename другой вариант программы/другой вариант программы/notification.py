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
            self.send_email_notification(territory_info, change_data, message, latest_image_path)
        else:
            print("Email уведомления отключены")

        print(f"Уведомление отправлено: {territory_info['name']}")

    @staticmethod
    def create_change_message(territory: Dict[str, Any], change_data: Dict[str, Any]):
        # Извлекаем данные из change_data
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

        # HTML версия сообщения (СМАЙЛИКИ ОСТАЮТСЯ)
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
            'text': text_message,
            'change_percent': change_percent
        }

    def send_email_notification(self, territory: Dict[str, Any],
                                change_data: Dict[str, Any],
                                message_data: Dict[str, str],
                                image_path: Optional[str] = None):
        try:
            # Извлекаем процент изменений
            change_percent = change_data.get('change_percentage', 0)
            change_level = change_data.get('change_level', '')

            # Создаем динамический заголовок с процентом изменений и смайликами
            if change_percent > 30:
                emoji = "🚨🚨"
            elif change_percent > 15:
                emoji = "🚨"
            elif change_percent > 5:
                emoji = "⚠️"
            else:
                emoji = "ℹ️"

            if change_level:
                subject = f"{emoji} {change_level.upper()} изменения на {territory['name']} - {change_percent:.2f}%"
            else:
                subject = f"{emoji} Изменения на {territory['name']} - {change_percent:.2f}%"

            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
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

            print(f"Email уведомление отправлено на {self.config.EMAIL_TO}")
            print(f"   Тема: {subject}")

        except Exception as e:
            print(f"Ошибка отправки email: {e}")
            import traceback
            traceback.print_exc()
