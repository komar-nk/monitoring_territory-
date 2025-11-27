import os


class Config:
    # Настройки базы данных
    DATABASE_URL = 'sqlite:///satellite_monitor.db'

    # Настройки хранения изображений
    IMAGE_STORAGE = 'images/original'
    PROCESSED_IMAGES = 'images/processed'

    # Настройки обнаружения изменений
    CHANGE_THRESHOLD = 0.05

    # Настройки email уведомлений
    EMAIL_ENABLED = False
    SMTP_SERVER = 'smtp.gmail.com'
    SMTP_PORT = 587
    EMAIL_FROM = 'your_email@gmail.com'
    EMAIL_PASSWORD = 'your_password'
    EMAIL_TO = 'recipient@email.com'

    # Интервал проверки
    CHECK_INTERVAL = 30