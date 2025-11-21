import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
from datetime import datetime


class NotificationManager:
    def __init__(self, config):
        self.config = config

    def send_change_notification(self, location, change_data, latest_image_path):
        message = self.create_change_message(location, change_data)

        if self.config.EMAIL_ENABLED:
            self.send_email_notification(location, message, latest_image_path)
        else:
            print("📧 Email уведомления отключены")

        print(f"📢 Уведомление отправлено: {location.name}")

    @staticmethod
    def create_change_message(location, change_data):
        change_percent = change_data['change_score'] * 100
        details = change_data.get('details', {})

        # HTML версия сообщения
        html_message = f"""
        <html>
        <body>
            <h2 style="color: #ff0000;">🚨 ОБНАРУЖЕНЫ ИЗМЕНЕНИЯ!</h2>

            <table border="1" cellpadding="8" style="border-collapse: collapse;">
                <tr><td><strong>📍 Место:</strong></td><td>{location.name}</td></tr>
                <tr><td><strong>📌 Координаты:</strong></td><td>{location.latitude:.4f}, {location.longitude:.4f}</td></tr>
                <tr><td><strong>📊 Изменения:</strong></td><td>{change_percent:.1f}%</td></tr>
                <tr><td><strong>🎯 Тип:</strong></td><td>{change_data['change_type']}</td></tr>
                <tr><td><strong>✅ Уверенность:</strong></td><td>{change_data['confidence']:.1%}</td></tr>
        """

        if location.address:
            html_message += f'<tr><td><strong>🏠 Адрес:</strong></td><td>{location.address}</td></tr>'

        html_message += f"""
                <tr><td><strong>🕐 Время обнаружения:</strong></td><td>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</td></tr>
            </table>

            <p><em>Система мониторинга спутниковых снимков</em></p>
        </body>
        </html>
        """

        # Текстовая версия для почтовых клиентов без HTML
        text_message = f"""🚨 ОБНАРУЖЕНЫ ИЗМЕНЕНИЯ!

📍 Место: {location.name}
📌 Координаты: {location.latitude:.4f}, {location.longitude:.4f}
📊 Изменения: {change_percent:.1f}%
🎯 Тип: {change_data['change_type']}
✅ Уверенность: {change_data['confidence']:.1%}"""

        if location.address:
            text_message += f"\n🏠 Адрес: {location.address}"

        text_message += f"\n\n🕐 Время обнаружения: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        text_message += "\n\nСистема мониторинга спутниковых снимков"

        return {
            'html': html_message,
            'text': text_message
        }

    def send_email_notification(self, location, message_data, image_path=None):
        try:
            # Создаем сообщение
            msg = MIMEMultipart('alternative')
            msg['Subject'] = f"🚨 Изменения обнаружены: {location.name}"
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
                image.add_header('Content-ID', '<changes_image>')
                image.add_header('Content-Disposition', 'inline', filename=os.path.basename(image_path))
                msg.attach(image)

                # Добавляем ссылку на изображение в HTML
                message_data['html'] = message_data['html'].replace('</body>',
                                                                    '<p><img src="cid:changes_image" alt="Визуализация изменений" style="max-width: 100%;"></p></body>')

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

    def test_email_connection(self):
        """Тестирование подключения к почте"""
        try:
            server = smtplib.SMTP(self.config.SMTP_SERVER, self.config.SMTP_PORT)
            server.starttls()
            server.login(self.config.EMAIL_FROM, self.config.EMAIL_PASSWORD)
            server.quit()
            print("✅ Подключение к почте успешно")
            return True
        except Exception as e:
            print(f"❌ Ошибка подключения к почте: {e}")
            return False

    def send_summary_report(self, html_content, text_content, changes_count, total_locations):
        """Отправляет сводный отчет по всем изменениям"""
        try:
            if not self.config.EMAIL_ENABLED:
                print("📧 Email уведомления отключены")
                return

            # Создаем сообщение
            msg = MIMEMultipart('alternative')
            msg['Subject'] = f"📊 Сводный отчет: {changes_count} изменений в {total_locations} местах"
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