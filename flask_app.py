"""
FLASK СЕРВЕР ДЛЯ ВЕБ-ИНТЕРФЕЙСА + ПИТОНОВСКОГО БЭКЕНДА
Исправленная версия с правильным сохранением снимков
"""

import os
import sqlite3
import sys
import json
import traceback
import io
import shutil
from datetime import datetime
from pathlib import Path
from flask import Flask, request, jsonify, send_from_directory, session, send_file
from flask_cors import CORS

# Добавляем текущую директорию в путь
current_dir = Path(__file__).parent
sys.path.append(str(current_dir))

# Импортируем модули
try:
    print("=" * 60)
    print("ЗАГРУЗКА МОДУЛЕЙ СИСТЕМЫ...")
    print("=" * 60)

    # Основные модули
    from database import Database
    from gee_client import GEEClient
    from change_detector import ChangeDetector
    from grid_analyzer import GridAnalyzer
    from notification import NotificationManager, EmailConfig
    from grid_creator import GridCreator

    # Все детекторы
    from ultimate_detector import detect_changes_ultimate, UltimateDetector
    from super_forest_detector import SuperForestDetector
    from improved_change_detector import detect_changes_improved

    print("✓ Все модули загружены успешно!")

except ImportError as e:
    print(f"✗ Ошибка импорта модулей: {e}")
    traceback.print_exc()
    sys.exit(1)


# ========== FLASK APP ==========

app = Flask(__name__, static_folder='./frontend', static_url_path='/')
app.secret_key = os.urandom(32)
CORS(app, supports_credentials=True)

# Глобальные объекты
db = None
gee_client = None
change_detector = None
grid_analyzer = None
notification_manager = None
grid_creator = None
ultimate_detector = None
forest_detector = None

# Мониторинг в фоне
monitoring_threads = {}
monitoring_active = False


def ensure_original_folder():
    """Создает папку original если ее нет"""
    original_dir = Path('satellite_images') / 'original'
    original_dir.mkdir(parents=True, exist_ok=True)
    return original_dir


def move_to_original_folder(image_path, territory_name=None):
    """Перемещает изображение в папку original с правильным именем"""
    try:
        original_dir = ensure_original_folder()

        # Если файл уже в original, возвращаем как есть
        if str(image_path).startswith(str(original_dir)):
            return str(image_path)

        if territory_name:
            # Транслитерация кириллицы
            translit_dict = {
                'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd',
                'е': 'e', 'ё': 'yo', 'ж': 'zh', 'з': 'z', 'и': 'i',
                'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm', 'н': 'n',
                'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't',
                'у': 'u', 'ф': 'f', 'х': 'h', 'ц': 'ts', 'ч': 'ch',
                'ш': 'sh', 'щ': 'sch', 'ъ': '', 'ы': 'y', 'ь': '',
                'э': 'e', 'ю': 'yu', 'я': 'ya',
                'А': 'A', 'Б': 'B', 'В': 'V', 'Г': 'G', 'Д': 'D',
                'Е': 'E', 'Ё': 'Yo', 'Ж': 'Zh', 'З': 'Z', 'И': 'I',
                'Й': 'Y', 'К': 'K', 'Л': 'L', 'М': 'M', 'Н': 'N',
                'О': 'O', 'П': 'P', 'Р': 'R', 'С': 'S', 'Т': 'T',
                'У': 'U', 'Ф': 'F', 'Х': 'H', 'Ц': 'Ts', 'Ч': 'Ch',
                'Ш': 'Sh', 'Щ': 'Sch', 'Ъ': '', 'Ы': 'Y', 'Ь': '',
                'Э': 'E', 'Ю': 'Yu', 'Я': 'Ya',
                ' ': '_', '-': '_'
            }

            safe_name = ''
            for char in territory_name:
                if char in translit_dict:
                    safe_name += translit_dict[char]
                elif char.isalnum():
                    safe_name += char
                else:
                    safe_name += '_'

            safe_name = safe_name.replace(' ', '_').replace('__', '_').strip('_')
        else:
            safe_name = 'satellite'

        # Добавляем timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_name = f"{safe_name}_{timestamp}"

        # Определяем расширение
        if isinstance(image_path, str):
            ext = os.path.splitext(image_path)[1]
            if not ext:
                ext = '.jpg'
        else:
            ext = '.jpg'

        # Создаем имя файла
        filename = f"{base_name}{ext}"
        new_path = original_dir / filename

        # Если файл уже существует, добавляем номер
        counter = 1
        while new_path.exists():
            filename = f"{base_name}_{counter}{ext}"
            new_path = original_dir / filename
            counter += 1

        # Перемещаем или конвертируем файл
            try:
                from PIL import Image
                img = Image.open(image_path)
                if img.mode in ('RGBA', 'LA') or (img.mode == 'P' and 'transparency' in img.info):
                    img = img.convert('RGBA')
                    background = Image.new('RGB', img.size, (255, 255, 255))
                    background.paste(img, mask=img.split()[-1])
                    img = background
                else:
                    img = img.convert('RGB')

                img.save(new_path, 'JPEG', quality=95, optimize=True)
                os.remove(image_path)  # Удаляем PNG файл
                print(f" PNG конвертирован в JPG: {new_path}")
            except Exception as e:
                print(f"⚠ Ошибка конвертации PNG: {e}")
                shutil.move(image_path, new_path)
        else:
            # перемещаем файл
            shutil.move(image_path, new_path)

        print(f" Файл сохранен в original: {new_path}")
        return str(new_path)

    except Exception as e:
        print(f"⚠ Ошибка перемещения файла: {e}")
        traceback.print_exc()
        return image_path


def init_system():
    """Инициализация всей системы"""
    global db, gee_client, change_detector, grid_analyzer
    global notification_manager, grid_creator, ultimate_detector, forest_detector

    try:
        print("\n" + "=" * 60)
        print("ИНИЦИАЛИЗАЦИЯ СИСТЕМЫ МОНИТОРИНГА")
        print("=" * 60)


        ensure_original_folder()
        Path('satellite_images/processed').mkdir(exist_ok=True)
        Path('satellite_images/analysis').mkdir(exist_ok=True)
        Path('satellite_images/comparison').mkdir(exist_ok=True)

        # 1. База данных
        db = Database()
        print("✓ База данных инициализирована")
        db.migrate_users()

        # 2. Google Earth Engine - настраиваем для сохранения в правильную папку
        gee_client = GEEClient(cache_dir='satellite_images')
        print("✓ Google Earth Engine подключен")

        # 3. Детектор изменений
        change_detector = ChangeDetector(db, gee_client)
        print("✓ Детектор изменений готов")

        # 4. Анализатор сетки
        grid_analyzer = GridAnalyzer()
        print("✓ Анализатор сетки готов")

        # 5. Создатель сеток
        grid_creator = GridCreator(grid_size=32)
        print("✓ Создатель сеток готов")

        # 6. Детекторы
        ultimate_detector = UltimateDetector(debug=False)
        forest_detector = SuperForestDetector()
        print("✓ Улучшенные детекторы загружены")

        # 7. Email уведомления
        try:
            email_config = EmailConfig()
            if email_config.EMAIL_ENABLED:
                notification_manager = NotificationManager(email_config)
                print(f"✓ Email уведомления включены ({email_config.EMAIL_TO})")
            else:
                print("ℹ Email уведомления отключены")
        except Exception as e:
            print(f" Email уведомления: {e}")
            notification_manager = None

        print("=" * 60)
        print(" ВСЯ СИСТЕМА ГОТОВА К РАБОТЕ!")
        print("=" * 60)

        return True

    except Exception as e:
        print(f"✗ Критическая ошибка инициализации: {e}")
        traceback.print_exc()
        return False


def create_test_image_bytes():
    """Создает тестовое изображение в формате bytes"""
    try:
        from PIL import Image, ImageDraw

        # Создаем изображение
        img = Image.new('RGB', (400, 300), color='#0a0a0f')
        d = ImageDraw.Draw(img)

        d.text((50, 120), 'КОСМОС МОНИТОРИНГ', fill='#4a9eff')
        d.text((50, 150), 'Спутниковый снимок', fill='white')
        d.text((50, 180), 'Используйте кнопку "Получить снимок"', fill='#a0aec0')
        d.text((50, 210), 'для загрузки реальных данных', fill='#a0aec0')

        # Добавляем сетку как на спутниковом снимке
        for i in range(0, 400, 20):
            d.line([(i, 0), (i, 300)], fill='#1a1a2e', width=1)
        for i in range(0, 300, 20):
            d.line([(0, i), (400, i)], fill='#1a1a2e', width=1)

        # Сохраняем в bytes
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='JPEG', quality=85)
        img_bytes.seek(0)

        return img_bytes
    except Exception as e:
        print(f"Ошибка создания тестового изображения: {e}")
        # Возвращаем пустой bytes если ошибка
        return io.BytesIO()


# ========== API ДЛЯ ФРОНТЕНДА ==========
@app.route('/')
def serve_index():
    return send_from_directory(app.static_folder, 'index.html')


@app.route('/api/auth/status', methods=['GET'])
def auth_status():
    """Проверка статуса авторизации"""
    user = session.get('user')
    return jsonify({
        'authenticated': user is not None,
        'user': user
    })


@app.route('/api/auth/login', methods=['POST'])
def login():
    """Вход в систему"""
    try:
        data = request.json
        username = data.get('username', '').strip()
        password = data.get('password', '').strip()

        if username and password:
            session['user'] = {
                'username': username,
                'login': username,
                'created_at': datetime.now().isoformat()
            }
            return jsonify({
                'success': True,
                'user': username,
                'message': 'Вход выполнен успешно'
            })
        return jsonify({
            'success': False,
            'message': 'Неверные данные'
        }), 401

    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Ошибка: {str(e)}'
        }), 500


@app.route('/api/auth/register', methods=['POST'])
def register():
    """Регистрация нового пользователя"""
    try:
        data = request.json
        username = data.get('username', '').strip()
        password = data.get('password', '').strip()

        if not username or not password:
            return jsonify({
                'success': False,
                'message': 'Заполните все поля'
            }), 400

        session['user'] = {
            'username': username,
            'login': username,
            'created_at': datetime.now().isoformat()
        }

        return jsonify({
            'success': True,
            'user': username,
            'message': 'Регистрация успешна'
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Ошибка: {str(e)}'
        }), 500


@app.route('/api/auth/logout', methods=['POST'])
def logout():
    """Выход из системы"""
    session.clear()
    return jsonify({'success': True, 'message': 'Выход выполнен'})


@app.route('/api/territories', methods=['GET'])
def get_territories():
    """Получение списка территорий пользователя"""
    try:
        user = session.get('user')
        if not user:
            return jsonify({'success': False, 'message': 'Не авторизован'}), 401

        username = user.get('username')
        all_territories = db.get_all_territories()

        # Фильтруем по пользователю
        user_territories = []
        for t in all_territories:
            if t.get('user') == username or str(t.get('id')).startswith(username):
                # Добавляем информацию об изображениях
                images = db.get_territory_images(t['id'])
                t['image_count'] = len(images)
                t['latest_image'] = images[0] if images else None
                t['latest_image_date'] = images[0]['capture_date'] if images else None
                user_territories.append(t)

        return jsonify({
            'success': True,
            'territories': user_territories,
            'count': len(user_territories)
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Ошибка: {str(e)}'
        }), 500


@app.route('/api/territories/add', methods=['POST'])
def add_territory():
    """Добавление новой территории БЕЗ автоматической загрузки снимка"""
    try:
        user = session.get('user')
        if not user:
            return jsonify({'success': False, 'message': 'Не авторизован'}), 401

        data = request.json
        name = data.get('name', '').strip()
        lat = data.get('lat')
        lng = data.get('lng')
        description = data.get('description', '').strip()

        if not name:
            return jsonify({
                'success': False,
                'message': 'Введите название территории'
            }), 400

        if lat is None or lng is None:
            return jsonify({
                'success': False,
                'message': 'Укажите координаты'
            }), 400

        try:
            lat = float(lat)
            lng = float(lng)
        except ValueError:
            return jsonify({
                'success': False,
                'message': 'Неверный формат координат'
            }), 400

        # Добавляем пользователя в описание
        username = user.get('username')
        if description:
            description = f"{description} (пользователь: {username})"
        else:
            description = f"Территория пользователя {username}"

        print(f" Добавление территории БЕЗ снимка: {name} ({lat}, {lng})")

        # Добавляем в базу данных
        territory_id = db.add_territory(name, lat, lng, description)
        print(f"✓ Территория сохранена в БД, ID: {territory_id}")

        territory = db.get_territory(territory_id)

        return jsonify({
            'success': True,
            'territory': territory,
            'image': None,
            'message': f'Территория "{name}" успешно добавлена. Используйте кнопку "Получить снимок" для загрузки изображения.'
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'Ошибка сервера: {str(e)}'
        }), 500
@app.route('/api/territories/add-simple', methods=['POST'])
def add_territory_simple():
    """Простое добавление территории без получения снимка (для миграции)"""
    try:
        user = session.get('user')
        if not user:
            return jsonify({'success': False, 'message': 'Не авторизован'}), 401

        data = request.json
        name = data.get('name', '').strip()
        lat = data.get('lat')
        lng = data.get('lng')
        description = data.get('description', '').strip()

        if not name:
            return jsonify({
                'success': False,
                'message': 'Введите название территории'
            }), 400

        if lat is None or lng is None:
            return jsonify({
                'success': False,
                'message': 'Укажите координаты'
            }), 400

        try:
            lat = float(lat)
            lng = float(lng)
        except ValueError:
            return jsonify({
                'success': False,
                'message': 'Неверный формат координат'
            }), 400

        # Добавляем пользователя в описание
        username = user.get('username')
        if description:
            description = f"{description} (пользователь: {username})"
        else:
            description = f"Территория пользователя {username}"

        print(f" Простое добавление территории: {name} ({lat}, {lng})")

        # Добавляем в базу данных
        territory_id = db.add_territory(name, lat, lng, description)
        print(f"✓ Территория сохранена в БД, ID: {territory_id}")

        # Получаем данные территории
        territory = db.get_territory(territory_id)

        return jsonify({
            'success': True,
            'territory': territory,
            'message': f'Территория "{name}" успешно добавлена в БД'
        })

    except Exception as e:
        print(f" Ошибка добавления территории: {e}")
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'Ошибка сервера: {str(e)}'
        }), 500

@app.route('/api/territories/<int:territory_id>/get-satellite', methods=['POST'])
def get_satellite_for_territory(territory_id):
    """Получение нового спутникового снимка для территории"""
    print(f"\n🛰 ЗАПРОС НА ПОЛУЧЕНИЕ СНИМКА ДЛЯ ТЕРРИТОРИИ {territory_id}")

    try:
        user = session.get('user')
        if not user:
            return jsonify({'success': False, 'message': 'Не авторизован'}), 401

        # Получаем данные из запроса
        data = request.json or {}
        custom_date = data.get('date')

        print(f" Запрашиваемая дата из фронтенда: {custom_date}")
        print(f" Все данные запроса: {data}")

        # Получаем территорию
        territory = db.get_territory(territory_id)
        if not territory:
            return jsonify({
                'success': False,
                'message': 'Территория не найдена'
            }), 404

        print(f" Координаты: {territory['latitude']}, {territory['longitude']}")
        print(f" Запрашиваемая дата: {custom_date if custom_date else 'автоматический поиск'}")

        # Получаем спутниковый снимок
        if custom_date:
            # Если указана дата, используем ее
            print(f" Ищем снимки за 60 дней от {custom_date}")
            result = gee_client.get_satellite_image(
                territory['latitude'],
                territory['longitude'],
                date=custom_date  # Передаем дату
            )
        else:
            print(f" Ищем снимки за 60 дней от текущей даты")
            result = gee_client.get_satellite_image(
                territory['latitude'],
                territory['longitude']
            )

        if result and result[0]:
            image_path = result[1]
            capture_date = result[2]
            message = result[3] if len(result) > 3 else "Изображение получено"

            print(f" Снимок получен!")
            print(f"   Дата съемки снимка: {capture_date}")
            print(f"   Сообщение: {message}")
            print(f"   Путь: {image_path}")

            # Перемещаем в папку original
            original_path = move_to_original_folder(image_path, territory['name'])
            print(f" Файл перемещен: {original_path}")

            # Анализ изображения
            analysis = None
            cloud_cover = None
            if hasattr(gee_client, 'analyze_image'):
                analysis = gee_client.analyze_image(original_path)
                if analysis and 'error' not in analysis:
                    cloud_cover = analysis.get('cloud_cover', {}).get('percentage')
                    print(f"☁  Облачность: {cloud_cover}%")

            file_size = os.path.getsize(original_path) if os.path.exists(original_path) else None

            # Сохраняем изображение в базу
            image_id = db.add_image(
                territory_id, original_path, capture_date,
                cloud_cover, file_size
            )
            print(f" Изображение сохранено в БД, ID: {image_id}")

            # Получаем обновленный список изображений
            images = db.get_territory_images(territory_id)

            return jsonify({
                'success': True,
                'image': {
                    'id': image_id,
                    'path': original_path,
                    'date': capture_date,
                    'cloud_cover': cloud_cover,
                    'file_size': file_size
                },
                'capture_date': capture_date,
                'images_count': len(images),
                'message': f'Новый снимок для территории "{territory["name"]}" успешно получен',
                'debug': {
                    'requested_date': custom_date,
                    'actual_capture_date': capture_date,
                    'method': 'with_date' if custom_date else 'auto'
                }
            })
        else:
            error_msg = result[3] if len(result) > 3 else 'Неизвестная ошибка'
            print(f" Ошибка получения изображения: {error_msg}")
            return jsonify({
                'success': False,
                'message': f'Ошибка получения изображения: {error_msg}',
                'debug': {
                    'requested_date': custom_date
                }
            })

    except Exception as e:
        print(f" Критическая ошибка: {e}")
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'Ошибка: {str(e)}'
        }), 500


@app.route('/api/territories/<int:territory_id>', methods=['GET'])
def get_territory(territory_id):
    """Получение информации о конкретной территории"""
    try:
        territory = db.get_territory(territory_id)
        if not territory:
            return jsonify({
                'success': False,
                'message': 'Территория не найдена'
            }), 404

        images = db.get_territory_images(territory_id)

        return jsonify({
            'success': True,
            'territory': territory,
            'images': images,
            'image_count': len(images)
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Ошибка: {str(e)}'
        }), 500


@app.route('/api/territories/<int:territory_id>/images', methods=['GET'])
def get_territory_images_api(territory_id):
    """Получение изображений территории для веб-интерфейса"""
    try:
        images = db.get_territory_images(territory_id)

        # Добавляем URL для доступа к файлам
        for img in images:
            if 'image_path' in img:
                filename = os.path.basename(img['image_path'])
                img['url'] = f'/api/images/file/{filename}'

        return jsonify({
            'success': True,
            'images': images,
            'count': len(images)
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Ошибка: {str(e)}'
        }), 500


@app.route('/api/images/<int:image_id>', methods=['GET'])
def get_image_info(image_id):
    """Получение информации об изображении"""
    try:
        image = db.get_image(image_id)
        if not image:
            return jsonify({
                'success': False,
                'message': 'Изображение не найдено'
            }), 404

        # Добавляем URL
        if 'image_path' in image:
            filename = os.path.basename(image['image_path'])
            image['url'] = f'/api/images/file/{filename}'

        return jsonify({
            'success': True,
            'image': image
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Ошибка: {str(e)}'
        }), 500


@app.route('/api/images/file/<path:filename>')
def serve_image_file(filename):
    """Отдача файлов изображений"""
    try:
        import re
        # Очищаем имя файла
        safe_filename = re.sub(r'[^a-zA-Z0-9_\-\.]', '', filename)

        print(f"📸 Запрос изображения: {safe_filename}")

        # Проверяем в папке original
        original_path = os.path.join('satellite_images', 'original', safe_filename)
        if os.path.exists(original_path):
            print(f" Найден в original: {original_path}")
            return send_file(original_path, mimetype='image/jpeg', max_age=3600)

        #  Ищем по всему пути из базы данных
        # Получаем ID из имени файла
        import re
        match = re.search(r'image_(\d+)\.', safe_filename)
        if match:
            image_id = int(match.group(1))
            try:
                # Получаем изображение из базы
                image_info = db.get_image(image_id)
                if image_info and 'image_path' in image_info:
                    db_path = image_info['image_path']
                    if os.path.exists(db_path):
                        print(f" Найден по ID из БД: {db_path}")
                        return send_file(db_path, mimetype='image/jpeg', max_age=3600)
            except:
                pass

        # Ищем во всех подпапках satellite_images
        for root, dirs, files in os.walk('satellite_images'):
            for file in files:
                if file == safe_filename:
                    found_path = os.path.join(root, file)
                    print(f" Найден в подпапке: {found_path}")
                    return send_file(found_path, mimetype='image/jpeg', max_age=3600)

        print(f" Файл не найден: {safe_filename}")

        # Возвращаем заглушку
        img_bytes = create_test_image_bytes()
        return send_file(img_bytes, mimetype='image/jpeg', max_age=60)

    except Exception as e:
        print(f"⚠ Ошибка отдачи файла: {e}")
        import traceback
        traceback.print_exc()

        # Возвращаем тестовое изображение при ошибке
        img_bytes = create_test_image_bytes()
        return send_file(img_bytes, mimetype='image/jpeg', max_age=60)

@app.route('/api/satellite/get', methods=['POST'])
def get_satellite():
    """Получение спутникового изображения по координатам (для тестирования)"""
    try:
        data = request.json
        lat = data.get('lat')
        lng = data.get('lng')
        date = data.get('date')
        name = data.get('name', 'test_point')

        if lat is None or lng is None:
            return jsonify({
                'success': False,
                'message': 'Укажите координаты'
            }), 400

        try:
            lat = float(lat)
            lng = float(lng)
        except ValueError:
            return jsonify({
                'success': False,
                'message': 'Неверный формат координат'
            }), 400

        print(f"🛰 Получение снимка для координат: {lat}, {lng}")

        # Передаем дату в GEE
        result = gee_client.get_satellite_image(lat, lng, date)

        if result and result[0]:
            image_path = result[1]
            capture_date = result[2]

            # Перемещаем в папку original
            original_path = move_to_original_folder(image_path, name)

            return jsonify({
                'success': True,
                'image_path': original_path,
                'capture_date': capture_date,
                'message': 'Изображение получено и сохранено в папку original'
            })
        else:
            error_msg = result[3] if len(result) > 3 else 'Неизвестная ошибка'
            return jsonify({
                'success': False,
                'message': f'Ошибка: {error_msg}'
            })

    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Ошибка: {str(e)}'
        }), 500


@app.route('/api/system/info', methods=['GET'])
def system_info():
    """Информация о системе"""
    try:
        stats = db.get_statistics() if hasattr(db, 'get_statistics') else {}

        # Считаем файлы в папке original
        original_count = 0
        original_size = 0
        original_dir = Path('satellite_images') / 'original'
        if original_dir.exists():
            for file in original_dir.glob('*.*'):
                if file.is_file():
                    original_count += 1
                    original_size += file.stat().st_size

        # Считаем файлы в основной папке
        main_count = 0
        main_size = 0
        main_dir = Path('satellite_images')
        if main_dir.exists():
            for file in main_dir.glob('*.*'):
                if file.is_file() and file.parent == main_dir:
                    main_count += 1
                    main_size += file.stat().st_size

        return jsonify({
            'success': True,
            'system': {
                'name': 'Космос Мониторинг',
                'version': '1.0.0',
                'territories': stats.get('territories', 0),
                'images': stats.get('images', 0),
                'changes': stats.get('changes', 0),
                'gee_connected': gee_client is not None,
                'email_enabled': notification_manager is not None,
                'monitoring_active': len(monitoring_threads) > 0,
                'files_original': original_count,
                'files_main': main_count,
                'total_files': original_count + main_count
            }
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Ошибка: {str(e)}'
        }), 500


# ========== СТАТИЧЕСКИЕ ФАЙЛЫ ==========

@app.route('/<path:page>')
def serve_page(page):
    if page.endswith('.html'):
        return send_from_directory('./frontend', page)
    return app.send_static_file(page)


@app.route('/static/<path:path>')
def serve_static(path):
    return send_from_directory('./frontend/static', path)

@app.route('/api/analysis/detect', methods=['POST'])
def detect_changes():
    """Обнаружение изменений между двумя снимками"""
    try:
        data = request.json
        territory_id = data.get('territory_id')
        old_image_id = data.get('old_image_id')
        new_image_id = data.get('new_image_id')
        detector = data.get('detector', 'ultimate')

        if not all([territory_id, old_image_id, new_image_id]):
            return jsonify({
                'success': False,
                'message': 'Не указаны ID территории и изображений'
            }), 400

        # Получаем информацию об изображениях
        old_image = db.get_image(old_image_id)
        new_image = db.get_image(new_image_id)

        if not old_image or not new_image:
            return jsonify({
                'success': False,
                'message': 'Изображения не найдены'
            }), 404

        old_path = old_image.get('image_path')
        new_path = new_image.get('image_path')

        if not os.path.exists(old_path) or not os.path.exists(new_path):
            return jsonify({
                'success': False,
                'message': 'Файлы изображений не найдены'
            }), 404

        # Используем детектор изменений
        if detector == 'ultimate' and ultimate_detector:
            result = ultimate_detector.detect_changes(old_path, new_path)
        elif detector == 'improved':
            result = detect_changes_improved(old_path, new_path)
        else:
            # Используем GEE клиент для сравнения
            result = gee_client.compare_images_advanced(old_path, new_path)

        if 'error' in result:
            return jsonify({
                'success': False,
                'message': f'Ошибка анализа: {result["error"]}'
            }), 500

        # Сохраняем результат в базу данных
        change_id = db.save_change_detection(
            territory_id=territory_id,
            old_image_id=old_image_id,
            new_image_id=new_image_id,
            change_percentage=result.get('change_percentage', 0),
            change_data=json.dumps(result),
            detected_at=datetime.now().isoformat()
        )

        return jsonify({
            'success': True,
            'analysis': result,
            'change_id': change_id,
            'message': 'Анализ изменений выполнен успешно'
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'Ошибка анализа: {str(e)}'
        }), 500


@app.route('/api/territories/<int:territory_id>/monitoring/start', methods=['POST'])
def start_monitoring(territory_id):
    """Запуск мониторинга территории"""
    try:
        user = session.get('user')
        if not user:
            return jsonify({'success': False, 'message': 'Не авторизован'}), 401

        territory = db.get_territory(territory_id)
        if not territory:
            return jsonify({
                'success': False,
                'message': 'Территория не найдена'
            }), 404


        return jsonify({
            'success': True,
            'message': f'Мониторинг территории "{territory["name"]}" запущен'
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Ошибка: {str(e)}'
        }), 500


@app.route('/api/territories/<int:territory_id>/monitoring/stop', methods=['POST'])
def stop_monitoring(territory_id):
    """Остановка мониторинга территории"""
    try:
        territory = db.get_territory(territory_id)
        if not territory:
            return jsonify({
                'success': False,
                'message': 'Территория не найдена'
            }), 404

        # Здесь можно добавить логику остановки мониторинга

        return jsonify({
            'success': True,
            'message': f'Мониторинг территории "{territory["name"]}" остановлен'
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Ошибка: {str(e)}'
        }), 500


def require_auth():
    """Проверка авторизации"""
    user = session.get('user')
    if not user:
        return jsonify({
            'success': False,
            'message': 'Не авторизован'
        }), 401
    return None


@app.route('/api/territories/<int:territory_id>/images/all', methods=['GET'])
def get_all_territory_images(territory_id):
    """Получение ВСЕХ изображений территории для выбора"""
    try:
        user = session.get('user')
        if not user:
            return jsonify({'success': False, 'message': 'Не авторизован'}), 401

        territory = db.get_territory(territory_id)
        if not territory:
            return jsonify({
                'success': False,
                'message': 'Территория не найдена'
            }), 404

        images = db.get_territory_images(territory_id, limit=100)  # Больше изображений для выбора

        # Форматируем данные для фронтенда
        formatted_images = []
        for img in images:
            # Проверяем существование файла
            file_exists = os.path.exists(img['image_path'])

            # Определяем тип файла
            if img['image_path'].lower().endswith('.png'):
                file_type = 'PNG'
            elif img['image_path'].lower().endswith('.jpg') or img['image_path'].lower().endswith('.jpeg'):
                file_type = 'JPEG'
            else:
                file_type = 'Изображение'

            # Получаем размер файла
            file_size = "Неизвестно"
            if file_exists:
                try:
                    size_bytes = os.path.getsize(img['image_path'])
                    if size_bytes < 1024:
                        file_size = f"{size_bytes} байт"
                    elif size_bytes < 1024 * 1024:
                        file_size = f"{size_bytes / 1024:.1f} KB"
                    else:
                        file_size = f"{size_bytes / (1024 * 1024):.1f} MB"
                except:
                    file_size = "Неизвестно"

            formatted_images.append({
                'id': img['id'],
                'date': img['capture_date'],
                'cloud_cover': img.get('cloud_cover'),
                'file_size': file_size,
                'file_type': file_type,
                'file_exists': file_exists,
                'url': f"/api/images/file/{os.path.basename(img['image_path'])}",
                'filename': os.path.basename(img['image_path']),
                'path': img['image_path']
            })

        return jsonify({
            'success': True,
            'territory': {
                'id': territory['id'],
                'name': territory['name']
            },
            'images': formatted_images,
            'count': len(formatted_images)
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Ошибка: {str(e)}'
        }), 500


@app.route('/api/analysis/compare', methods=['POST'])
def compare_selected_images():
    """Сравнение выбранных пользователем изображений"""
    try:
        user = session.get('user')
        if not user:
            return jsonify({'success': False, 'message': 'Не авторизован'}), 401

        data = request.json
        territory_id = data.get('territory_id')
        current_image_id = data.get('current_image_id')  # ID текущего снимка
        comparison_image_id = data.get('comparison_image_id')  # ID сравнительного снимка
        detector_type = data.get('detector', 'improved')

        if not all([territory_id, current_image_id, comparison_image_id]):
            return jsonify({
                'success': False,
                'message': 'Не указаны ID изображений для сравнения'
            }), 400

        # Проверяем, что это не один и тот же снимок
        if current_image_id == comparison_image_id:
            return jsonify({
                'success': False,
                'message': 'Выбраны одинаковые снимки для сравнения'
            }), 400

        # Получаем информацию об изображениях
        current_image = db.get_image(current_image_id)
        comparison_image = db.get_image(comparison_image_id)

        if not current_image or not comparison_image:
            return jsonify({
                'success': False,
                'message': 'Одно из изображений не найдено'
            }), 404

        current_path = current_image.get('image_path')
        comparison_path = comparison_image.get('image_path')

        if not os.path.exists(current_path) or not os.path.exists(comparison_path):
            return jsonify({
                'success': False,
                'message': 'Файлы изображений не найдены'
            }), 404

        print(f" Сравнение изображений:")
        print(f"   Текущее: {current_image['capture_date']} (ID: {current_image_id})")
        print(f"   Сравнение: {comparison_image['capture_date']} (ID: {comparison_image_id})")
        print(f"   Детектор: {detector_type}")

        # Выбираем детектор в зависимости от типа
        result = None
        if detector_type == 'improved':
            result = detect_changes_improved(current_path, comparison_path)
        elif detector_type == 'ultimate' and ultimate_detector:
            result = ultimate_detector.detect_changes(current_path, comparison_path)
        else:
            # Используем GEE клиент
            result = gee_client.compare_images_advanced(current_path, comparison_path)

        if 'error' in result:
            return jsonify({
                'success': False,
                'message': f'Ошибка анализа: {result["error"]}'
            }), 500

        # Сохраняем результат сравнения в базу
        change_id = db.save_change_detection(
            territory_id=territory_id,
            old_image_id=comparison_image_id,
            new_image_id=current_image_id,
            change_percentage=result.get('change_percentage', 0),
            change_data=json.dumps(result),
            detected_at=datetime.now().isoformat(),
            comparison_type='manual'
        )

        # Создаем визуализацию если ее нет
        visualization_path = result.get('visualization_path')
        if not visualization_path or not os.path.exists(visualization_path):
            try:
                # Создаем простую визуализацию с помощью OpenCV
                if hasattr(gee_client, 'cv2') and gee_client.cv2:
                    import cv2
                    import numpy as np

                    # Загружаем изображения
                    img1 = cv2.imread(current_path)
                    img2 = cv2.imread(comparison_path)

                    if img1 is not None and img2 is not None:
                        # Приводим к одинаковому размеру
                        h = min(img1.shape[0], img2.shape[0])
                        w = min(img1.shape[1], img2.shape[1])
                        img1 = cv2.resize(img1, (w, h))
                        img2 = cv2.resize(img2, (w, h))

                        # Создаем монтаж из двух изображений
                        montage = np.hstack((img1, img2))

                        # Добавляем подписи
                        font = cv2.FONT_HERSHEY_SIMPLEX
                        cv2.putText(montage, 'Текущий снимок', (10, 30), font, 1, (255, 255, 255), 2)
                        cv2.putText(montage, 'Сравнительный снимок', (w + 10, 30), font, 1, (255, 255, 255), 2)

                        # Сохраняем
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        visualization_path = f"comparison_{current_image_id}_{comparison_image_id}_{timestamp}.jpg"
                        cv2.imwrite(visualization_path, montage)
                        result['visualization_path'] = visualization_path
            except Exception as viz_error:
                print(f"Ошибка создания визуализации: {viz_error}")

        email_sent = False
        email_message = ""

        if notification_manager and getattr(notification_manager.config, 'EMAIL_ENABLED', False):
            try:
                # Получаем email пользователя из базы данных
                user_email = None
                try:
                    with sqlite3.connect(db.db_path) as conn:
                        cursor = conn.cursor()
                        cursor.execute('SELECT notification_emails FROM users WHERE username = ?', (user['username'],))
                        result_db = cursor.fetchone()

                        if result_db and result_db[0]:
                            emails_data = json.loads(result_db[0])
                            # Ищем основной email
                            primary_email = next((e['address'] for e in emails_data if e.get('isPrimary')), None)
                            if primary_email:
                                user_email = primary_email
                                print(f" Найден основной email пользователя: {user_email}")
                            elif emails_data:
                                user_email = emails_data[0]['address']
                                print(f" Найден email пользователя: {user_email}")
                except Exception as email_error:
                    print(f"⚠ Ошибка получения email пользователя: {email_error}")

                # Если email пользователя не найден, используем email из конфига
                if not user_email:
                    user_email = getattr(notification_manager.config, 'EMAIL_TO', '')
                    print(f" Используется email из конфига: {user_email}")

                if not user_email:
                    print("⚠ Email пользователя не указан")
                    email_message = "Email для уведомлений не указан в профиле"
                else:
                    import threading

                    def send_email_async():
                        try:
                            print(f" Начинаю асинхронную отправку email на {user_email}...")

                            territory = db.get_territory(territory_id)
                            if not territory:
                                print(" Территория не найдена для email")
                                return

                            territory_info = {
                                'id': territory['id'],
                                'name': territory['name'],
                                'latitude': territory['latitude'],
                                'longitude': territory['longitude'],
                                'description': territory.get('description', '')
                            }

                            # Дополняем result датами
                            result_for_email = result.copy()
                            result_for_email['old_image_date'] = comparison_image.get('capture_date', '')
                            result_for_email['new_image_date'] = current_image.get('capture_date', '')

                            # Проверяем порог
                            change_percent = result_for_email.get('change_percentage', 0)
                            threshold = getattr(notification_manager.config, 'CHANGE_THRESHOLD', 1.0)

                            print(f" Email: проверка порога {change_percent}% vs {threshold}%")

                            if change_percent >= threshold:
                                print(f" Email: отправляю уведомление на {user_email}...")

                                # Создаем сеточные визуализации
                                grid_files = {}
                                try:
                                    if grid_creator and os.path.exists(current_path):
                                        print(" Создаю сеточные визуализации...")

                                        # 1. Сетка для нового снимка
                                        grid_result = grid_creator.create_grid_for_email(
                                            image_path=current_path,
                                            lat=territory['latitude'],
                                            lon=territory['longitude'],
                                            territory_name=territory['name']
                                        )
                                        if grid_result.get('success'):
                                            grid_files['grid_image'] = grid_result.get('grid_path')
                                            print(f" Создана сетка: {grid_result.get('grid_path')}")

                                        # 2. Сравнительная сетка (если есть оба снимка)
                                        if os.path.exists(comparison_path):
                                            comparison_result = grid_creator.create_comparison_grid(
                                                before_path=comparison_path,
                                                after_path=current_path,
                                                territory_name=territory['name']
                                            )
                                            if comparison_result.get('success'):
                                                grid_files['comparison_grid'] = comparison_result.get('comparison_path')
                                                print(
                                                    f" Создана сравнительная сетка: {comparison_result.get('comparison_path')}")

                                        # 3. Сетка с изменениями (если есть визуализация изменений)
                                        if visualization_path and os.path.exists(visualization_path):
                                            changes_result = grid_creator.create_grid_with_changes(
                                                image_path=current_path,
                                                changes_mask_path=visualization_path,
                                                # Используем визуализацию как маску
                                                territory_name=territory['name']
                                            )
                                            if changes_result.get('success'):
                                                grid_files['changes_grid'] = changes_result.get('changes_grid_path')
                                                print(
                                                    f" Создана сетка с изменениями: {changes_result.get('changes_grid_path')}")

                                except Exception as grid_error:
                                    print(f"⚠ Ошибка создания сеточных визуализаций: {grid_error}")

                                success = notification_manager.send_change_notification(
                                    territory_info=territory_info,
                                    change_data=result_for_email,
                                    latest_image_path=current_path if os.path.exists(current_path) else None,
                                    old_image_path=comparison_path if os.path.exists(comparison_path) else None,
                                    visualization_path=visualization_path if visualization_path and os.path.exists(
                                        visualization_path) else None,
                                    # Передаем сеточные файлы
                                    grid_image_path=grid_files.get('grid_image'),
                                    comparison_grid_path=grid_files.get('comparison_grid'),
                                    grid_comparison_path=grid_files.get('changes_grid'),
                                    recipient_email=user_email  # ВАЖНО: передаем email пользователя
                                )

                                # Очистка временных файлов сетки
                                try:
                                    for grid_file in grid_files.values():
                                        if grid_file and os.path.exists(grid_file):
                                            os.remove(grid_file)
                                            print(f"🗑 Удален временный файл сетки: {grid_file}")
                                except Exception as clean_error:
                                    print(f"⚠ Ошибка очистки сеточных файлов: {clean_error}")

                                if success:
                                    print(f" Email успешно отправлен на {user_email}!")
                                else:
                                    print(f" Ошибка отправки email: {notification_manager.last_error}")
                            else:
                                print(f"ℹ Email: изменения {change_percent:.1f}% ниже порога {threshold}%")

                        except Exception as e:
                            print(f" Ошибка в асинхронной отправке email: {e}")
                            import traceback
                            traceback.print_exc()

                    email_thread = threading.Thread(target=send_email_async)
                    email_thread.daemon = True
                    email_thread.start()

                    email_sent = True
                    email_message = f"Уведомление поставлено в очередь отправки на {user_email}"

            except Exception as e:
                print(f" Ошибка при запуске отправки email: {e}")
                email_message = "Ошибка отправки email"
        else:
            email_message = "Email уведомления отключены"

        return jsonify({
            'success': True,
            'comparison': result,
            'change_id': change_id,
            'email_sent': email_sent,
            'email_message': email_message,
            'current_image': {
                'id': current_image_id,
                'date': current_image['capture_date'],
                'url': f"/api/images/file/{os.path.basename(current_path)}"
            },
            'comparison_image': {
                'id': comparison_image_id,
                'date': comparison_image['capture_date'],
                'url': f"/api/images/file/{os.path.basename(comparison_path)}"
            },
            'visualization_url': f"/api/images/file/{os.path.basename(visualization_path)}" if visualization_path and os.path.exists(
                visualization_path) else None,
            'message': 'Сравнение выполнено успешно'
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'Ошибка сравнения: {str(e)}'
        }), 500


@app.route('/api/analysis/quick-compare', methods=['POST'])
def quick_compare():
    """Быстрое сравнение последнего снимка с предыдущим (автоматический выбор)"""
    try:
        data = request.json
        territory_id = data.get('territory_id')

        if not territory_id:
            return jsonify({
                'success': False,
                'message': 'Не указана территория'
            }), 400

        # Получаем два последних снимка
        images = db.get_territory_images(territory_id, limit=2)

        if len(images) < 2:
            return jsonify({
                'success': False,
                'message': f'Недостаточно снимков для сравнения (нужно 2, есть {len(images)})'
            }), 400

        # Самый новый снимок (первый в списке)
        new_image = images[0]
        # Предыдущий снимок (второй в списке)
        old_image = images[1]

        # Используем ChangeDetector для сравнения
        result = change_detector.detect_and_save_changes(territory_id, send_notification=False)

        if not result:
            return jsonify({
                'success': False,
                'message': 'Не удалось выполнить сравнение'
            }), 500

        return jsonify({
            'success': True,
            'comparison': result,
            'current_image': {
                'id': new_image['id'],
                'date': new_image['capture_date']
            },
            'previous_image': {
                'id': old_image['id'],
                'date': old_image['capture_date']
            },
            'message': 'Автоматическое сравнение выполнено'
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Ошибка: {str(e)}'
        }), 500


@app.route('/api/territories/<int:territory_id>/images/all', methods=['GET'])
def get_all_territory_images_api(territory_id):
    """Получение ВСЕХ изображений территории"""
    try:
        user = session.get('user')
        if not user:
            return jsonify({'success': False, 'message': 'Не авторизован'}), 401

        # Проверяем существование территории
        territory = db.get_territory(territory_id)
        if not territory:
            print(f"Территория {territory_id} не найдена в БД")

            # Пробуем найти любую территорию пользователя
            with sqlite3.connect(db.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                # Ищем территории пользователя
                username = user.get('username')
                cursor.execute("SELECT * FROM territories WHERE description LIKE ? OR description LIKE ? LIMIT 1",
                               (f'%{username}%', f'%пользователь: {username}%'))

                alt_territory = cursor.fetchone()
                if alt_territory:
                    territory = dict(alt_territory)
                    territory_id = territory['id']
                    print(f"Использую альтернативную территорию ID: {territory_id}")
                else:
                    # Берем первую территорию из БД
                    cursor.execute("SELECT * FROM territories ORDER BY id LIMIT 1")
                    first_territory = cursor.fetchone()
                    if first_territory:
                        territory = dict(first_territory)
                        territory_id = territory['id']
                        print(f"Использую первую территорию из БД ID: {territory_id}")
                    else:
                        return jsonify({
                            'success': False,
                            'message': 'В базе данных нет территорий'
                        }), 404

        # Получаем изображения из БД
        images = []
        try:
            with sqlite3.connect(db.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                # Проверяем существование таблицы satellite_images
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='satellite_images';")
                has_satellite_table = cursor.fetchone() is not None

                if has_satellite_table:
                    # Используем таблицу satellite_images
                    cursor.execute('''
                        SELECT * FROM satellite_images 
                        WHERE territory_id = ? 
                        ORDER BY capture_date DESC
                    ''', (territory_id,))
                else:
                    # Используем таблицу images
                    cursor.execute('''
                        SELECT * FROM images 
                        WHERE territory_id = ? 
                        ORDER BY capture_date DESC
                    ''', (territory_id,))

                db_rows = cursor.fetchall()
                images = [dict(row) for row in db_rows]

                print(f"Найдено {len(images)} изображений для территории {territory_id}")

        except Exception as db_error:
            print(f"Ошибка БД при получении изображений: {db_error}")
            import traceback
            traceback.print_exc()
            images = db.get_territory_images(territory_id, limit=100) if hasattr(db, 'get_territory_images') else []

        # Форматируем данные для фронтенда
        formatted_images = []
        for img in images:
            # Получаем путь к файлу
            image_path = img.get('image_path') or img.get('path', '')

            if not image_path:
                print(f"Изображение {img.get('id')} не имеет пути")
                continue

            file_exists = False
            real_path = ""

            search_paths = []

            # 1. Оригинальный путь из БД
            if image_path:
                search_paths.append(image_path)

            # 2. В папке original по имени файла
            filename = os.path.basename(image_path)
            if filename:
                search_paths.append(os.path.join('satellite_images', 'original', filename))

            # 3. По ID в папке original
            if img.get('id'):
                search_paths.append(f"satellite_images/original/image_{img['id']}.jpg")
                search_paths.append(f"satellite_images/original/image_{img['id']}.jpeg")
                search_paths.append(f"satellite_images/original/image_{img['id']}.png")

            # Ищем файл
            for path in search_paths:
                if os.path.exists(path):
                    file_exists = True
                    real_path = path
                    break

            if not file_exists:
                print(f"Файл не найден: {image_path}")
                continue

            # Получаем информацию о файле
            try:
                from PIL import Image
                with Image.open(real_path) as pil_img:
                    width, height = pil_img.size
                    resolution = f"{width}x{height}"
            except Exception as img_error:
                print(f"Ошибка открытия изображения {real_path}: {img_error}")
                resolution = "Неизвестно"

            # Получаем размер файла
            try:
                file_size_bytes = os.path.getsize(real_path)
                if file_size_bytes < 1024:
                    file_size_str = f"{file_size_bytes} байт"
                elif file_size_bytes < 1024 * 1024:
                    file_size_str = f"{file_size_bytes / 1024:.1f} KB"
                else:
                    file_size_str = f"{file_size_bytes / (1024 * 1024):.1f} MB"
            except:
                file_size_str = "Неизвестно"

            # Создаем URL для доступа
            final_filename = os.path.basename(real_path)
            url = f"/api/images/file/{final_filename}"

            formatted_images.append({
                'id': img.get('id'),
                'date': img.get('capture_date', img.get('date', 'Неизвестно')),
                'cloud_cover': img.get('cloud_cover'),
                'file_size': file_size_str,
                'file_exists': True,
                'url': url,
                'filename': final_filename,
                'path': real_path,
                'resolution': resolution,
                'full_url': f"http://localhost:5000{url}"
            })

        print(f"Вернул {len(formatted_images)} изображений для территории {territory_id}")

        return jsonify({
            'success': True,
            'territory': {
                'id': territory['id'],
                'name': territory['name']
            },
            'images': formatted_images,
            'count': len(formatted_images)
        })

    except Exception as e:
        print(f"Ошибка в get_all_territory_images_api: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'Ошибка сервера: {str(e)}'
        }), 500


@app.route('/api/auth/sync', methods=['POST'])
def auth_sync():
    """Синхронизация авторизации из localStorage"""
    try:
        data = request.json
        username = data.get('username')

        if not username:
            return jsonify({'success': False, 'message': 'Не указан username'}), 400

        session['user'] = {
            'username': username,
            'login': username,
            'created_at': datetime.now().isoformat(),
            'synced_from_localstorage': True
        }

        print(f" Сессия создана для пользователя: {username}")

        return jsonify({
            'success': True,
            'message': 'Сессия синхронизирована',
            'user': session['user']
        })

    except Exception as e:
        print(f" Ошибка синхронизации: {e}")
        return jsonify({
            'success': False,
            'message': f'Ошибка: {str(e)}'
        }), 500


@app.route('/api/debug/territories', methods=['GET'])
def debug_territories():
    """Диагностика - какие территории есть в БД"""
    try:
        import savedTerritories
        with sqlite3.connect(db.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Проверяем таблицу territories
            cursor.execute('SELECT * FROM territories ORDER BY id')
            territories = [dict(row) for row in cursor.fetchall()]

            # Также проверяем данные из localStorage (для отладки)
            return jsonify({
                'success': True,
                'from_db': territories,
                'from_localstorage': savedTerritories,
                'current_user': session.get('user')
            })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/territories/user', methods=['GET'])
def get_user_territories():
    """Получение территорий текущего пользователя - показываем ВСЕ"""
    try:
        user = session.get('user')
        if not user:
            return jsonify({'success': False, 'message': 'Не авторизован'}), 401

        username = user.get('username')
        print(f" Поиск территорий для пользователя: {username}")

        with sqlite3.connect(db.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute('SELECT * FROM territories WHERE is_active = 1 ORDER BY created_at DESC')
            territories = [dict(row) for row in cursor.fetchall()]

            print(f"Найдено территорий: {len(territories)}")

            # Форматируем ответ
            formatted = []
            for t in territories:
                # Количество изображений
                cursor.execute('SELECT COUNT(*) FROM images WHERE territory_id = ?', (t['id'],))
                img_count = cursor.fetchone()[0]

                formatted.append({
                    'id': t['id'],
                    'name': t['name'],
                    'latitude': t['latitude'],
                    'longitude': t['longitude'],
                    'description': t['description'],
                    'image_count': img_count,
                    'created_at': t['created_at'],
                    'is_active': t.get('is_active', 1)
                })

            return jsonify({
                'success': True,
                'territories': formatted,
                'count': len(formatted),
                'username': username,
                'note': 'Показаны все активные территории из БД'
            })

    except Exception as e:
        print(f" Ошибка получения территорий: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'Ошибка: {str(e)}'
        }), 500

@app.route('/api/debug/auth', methods=['GET'])
def debug_auth():
    """Диагностика авторизации"""
    user = session.get('user')
    return jsonify({
        'session_user': user,
        'session_keys': list(session.keys()),
        'headers': dict(request.headers),
        'cookies': dict(request.cookies)
    })


@app.route('/api/debug/check-db', methods=['GET'])
def debug_check_db():
    """Проверка что есть в базе данных"""
    try:
        with sqlite3.connect(db.db_path) as conn:
            cursor = conn.cursor()

            # 1. Какие таблицы есть
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]

            # 2. Что в таблице territories
            cursor.execute('SELECT * FROM territories')
            territories = cursor.fetchall()

            # 3. Что в таблице images
            cursor.execute('SELECT * FROM images')
            images = cursor.fetchall()

            return jsonify({
                'success': True,
                'tables': tables,
                'territories_count': len(territories),
                'territories': territories,
                'images_count': len(images),
                'images_sample': images[:5] if images else []
            })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/debug/db-structure', methods=['GET'])
def debug_db_structure():
    """Проверка структуры базы данных"""
    try:
        with sqlite3.connect(db.db_path) as conn:
            cursor = conn.cursor()

            # 1. Получить список таблиц
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = cursor.fetchall()

            # 2. Получить структуру таблицы changes
            cursor.execute("PRAGMA table_info(changes)")
            changes_columns = cursor.fetchall()

            # 3. Посмотреть существующие данные в changes
            cursor.execute("SELECT * FROM changes LIMIT 5")
            sample_data = cursor.fetchall()

            return jsonify({
                'success': True,
                'tables': [table[0] for table in tables],
                'changes_columns': changes_columns,
                'sample_data': sample_data,
                'changes_count': len(sample_data)
            })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/territories/<int:territory_id>', methods=['DELETE'])
def delete_territory_api(territory_id):
    """Удаление территории из базы данных"""
    try:
        user = session.get('user')
        if not user:
            return jsonify({'success': False, 'message': 'Не авторизован'}), 401

        print(f"🗑 Запрос на удаление территории ID: {territory_id}")

        # Простое удаление через базу данных
        success = db.delete_territory(territory_id)

        if success:
            print(f" Территория {territory_id} удалена из БД")
            return jsonify({
                'success': True,
                'message': 'Территория удалена'
            })
        else:
            print(f" Не удалось удалить территорию {territory_id}")
            return jsonify({
                'success': False,
                'message': 'Территория не найдена или ошибка удаления'
            }), 404

    except Exception as e:
        print(f" Ошибка удаления территории: {e}")
        return jsonify({
            'success': False,
            'message': f'Ошибка сервера: {str(e)}'
        }), 500


def send_email_notification(territory_info, change_data, image_files=None):
    """
    Отправка email уведомления об изменениях
    """
    try:
        print(f"\n{'=' * 60}")
        print(" ОТПРАВКА EMAIL УВЕДОМЛЕНИЯ ИЗ FLASK")
        print(f"{'=' * 60}")

        # Проверяем конфигурацию
        if not notification_manager:
            print("⚠ Менеджер уведомлений не инициализирован")
            return False

        # Проверяем порог изменений
        change_percent = change_data.get('change_percentage', 0)
        threshold = getattr(notification_manager.config, 'CHANGE_THRESHOLD', 5.0)

        if change_percent < threshold:
            print(f"ℹ Изменения ({change_percent}%) ниже порога ({threshold}%) - уведомление не отправляется")
            return False

        # Собираем информацию о файлах
        files_info = {}

        if image_files:
            # Файлы из аргументов
            for key, path in image_files.items():
                if path and os.path.exists(path):
                    files_info[key] = {'path': path, 'exists': True}
        else:
            # Пытаемся найти файлы по ID
            old_image_id = change_data.get('old_image_id')
            new_image_id = change_data.get('new_image_id')

            if old_image_id:
                old_image = db.get_image(old_image_id)
                if old_image and 'image_path' in old_image and os.path.exists(old_image['image_path']):
                    files_info['old_image'] = {'path': old_image['image_path'], 'exists': True}

            if new_image_id:
                new_image = db.get_image(new_image_id)
                if new_image and 'image_path' in new_image and os.path.exists(new_image['image_path']):
                    files_info['latest_image'] = {'path': new_image['image_path'], 'exists': True}

        # Дополнительные файлы из change_data
        additional_files = {
            'visualization': change_data.get('visualization_path'),
            'comparison': change_data.get('comparison_path'),
            'grid_analysis': change_data.get('grid_analysis_path'),
            'changes_grid': change_data.get('changes_grid_path'),
        }

        for key, path in additional_files.items():
            if path and os.path.exists(path):
                files_info[key] = {'path': path, 'exists': True}

        print(f" Файлы для отправки: {list(files_info.keys())}")

        # Отправляем уведомление
        success = notification_manager.send_change_notification(
            territory_info=territory_info,
            change_data=change_data,
            latest_image_path=files_info.get('latest_image', {}).get('path'),
            old_image_path=files_info.get('old_image', {}).get('path'),
            visualization_path=files_info.get('visualization', {}).get('path'),
            grid_analysis_path=files_info.get('grid_analysis', {}).get('path')
        )

        if success:
            print(f" Email уведомление отправлено успешно!")
            print(f"   Получатель: {notification_manager.config.EMAIL_TO}")
            print(f"   Изменения: {change_percent}%")
            return True
        else:
            print(f" Ошибка отправки email: {notification_manager.last_error}")
            return False

    except Exception as e:
        print(f" Ошибка в send_email_notification: {e}")
        import traceback
        traceback.print_exc()
        return False


def check_and_send_notification(territory_id, change_data):
    """
    Проверяет порог изменений и отправляет уведомление если нужно
    """
    try:
        # Получаем информацию о территории
        territory = db.get_territory(territory_id)
        if not territory:
            print(f" Территория {territory_id} не найдена")
            return False

        territory_info = {
            'id': territory['id'],
            'name': territory['name'],
            'latitude': territory['latitude'],
            'longitude': territory['longitude'],
            'description': territory.get('description', '')
        }

        # Проверяем порог
        change_percent = change_data.get('change_percentage', 0)
        threshold = getattr(notification_manager.config, 'CHANGE_THRESHOLD', 5.0) if notification_manager else 5.0

        print(f" Проверка порога: {change_percent}% vs {threshold}%")

        if change_percent >= threshold:
            print(f" Изменения ({change_percent}%) превышают порог ({threshold}%) - отправляем уведомление")
            return send_email_notification(territory_info, change_data)
        else:
            print(f"ℹ Изменения ({change_percent}%) ниже порога ({threshold}%) - уведомление не отправляется")
            return False

    except Exception as e:
        print(f" Ошибка в check_and_send_notification: {e}")
        return False


@app.route('/api/user/save-email', methods=['POST'])
def save_user_email():
    """Сохранение email пользователя в БД"""
    try:
        user = session.get('user')
        if not user:
            return jsonify({'success': False, 'message': 'Не авторизован'}), 401

        data = request.json
        email = data.get('email')
        username = user.get('username')

        if not email or not username:
            return jsonify({'success': False, 'message': 'Не указан email или username'}), 400

        # Проверяем email
        import re
        if not re.match(r'^[^\s@]+@[^\s@]+\.[^\s@]+$', email):
            return jsonify({'success': False, 'message': 'Неверный формат email'}), 400

        # Получаем текущие email пользователя
        with sqlite3.connect(db.db_path) as conn:
            cursor = conn.cursor()

            # Проверяем, существует ли пользователь
            cursor.execute('SELECT notification_emails FROM users WHERE username = ?', (username,))
            result = cursor.fetchone()

            if not result:
                # Создаем нового пользователя
                emails_data = [{
                    'address': email,
                    'addedAt': datetime.now().isoformat(),
                    'isPrimary': True,
                    'verified': False
                }]

                cursor.execute('''
                    INSERT INTO users (username, notification_emails)
                    VALUES (?, ?)
                ''', (username, json.dumps(emails_data)))

            else:
                # Обновляем существующего пользователя
                try:
                    existing_emails = json.loads(result[0]) if result[0] else []

                    # Удаляем старый основной email
                    for e in existing_emails:
                        e['isPrimary'] = False

                    # Добавляем новый email как основной
                    new_email = {
                        'address': email,
                        'addedAt': datetime.now().isoformat(),
                        'isPrimary': True,
                        'verified': False
                    }

                    # Удаляем дубликаты
                    existing_emails = [e for e in existing_emails if e['address'].lower() != email.lower()]
                    existing_emails.append(new_email)

                    cursor.execute('''
                        UPDATE users 
                        SET notification_emails = ?, updated_at = CURRENT_TIMESTAMP
                        WHERE username = ?
                    ''', (json.dumps(existing_emails), username))

                except json.JSONDecodeError:
                    # Если данные повреждены, создаем новый список
                    emails_data = [{
                        'address': email,
                        'addedAt': datetime.now().isoformat(),
                        'isPrimary': True,
                        'verified': False
                    }]

                    cursor.execute('''
                        UPDATE users 
                        SET notification_emails = ?, updated_at = CURRENT_TIMESTAMP
                        WHERE username = ?
                    ''', (json.dumps(emails_data), username))

            conn.commit()

        return jsonify({
            'success': True,
            'message': 'Email сохранен',
            'email': email
        })

    except Exception as e:
        print(f"Ошибка сохранения email: {e}")
        return jsonify({'success': False, 'message': f'Ошибка: {str(e)}'}), 500


@app.route('/api/user/emails', methods=['GET'])
def get_user_emails_api():
    """Получение email пользователя"""
    try:
        user = session.get('user')
        if not user:
            return jsonify({'success': False, 'message': 'Не авторизован'}), 401

        username = user.get('username')

        # Получаем email из базы данных
        emails = db.get_user_emails(username)

        return jsonify({
            'success': True,
            'emails': emails,
            'count': len(emails)
        })
    except Exception as e:
        return jsonify({'success': False, 'message': f'Ошибка: {str(e)}'}), 500


@app.route('/api/user/info', methods=['GET'])
def get_user_info():
    """Получение информации о пользователе"""
    try:
        user = session.get('user')
        if not user:
            return jsonify({'success': False, 'message': 'Не авторизован'}), 401

        username = user.get('username')

        with sqlite3.connect(db.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
            db_user = cursor.fetchone()

            if db_user:
                user_dict = dict(db_user)
                return jsonify({
                    'success': True,
                    'user': user_dict
                })
            else:
                return jsonify({
                    'success': False,
                    'message': 'Пользователь не найден'
                }), 404

    except Exception as e:
        return jsonify({'success': False, 'message': f'Ошибка: {str(e)}'}), 500


@app.route('/api/user/remove-email', methods=['POST'])
def remove_user_email():
    """Удаление email пользователя"""
    try:
        user = session.get('user')
        if not user:
            return jsonify({'success': False, 'message': 'Не авторизован'}), 401

        data = request.json
        email_to_remove = data.get('email')
        username = user.get('username')

        # Получаем текущие email
        emails = db.get_user_emails(username)

        # Фильтруем удаляемый email
        updated_emails = [e for e in emails if e['address'] != email_to_remove]

        # Если удаляем основной email и остались другие, делаем первый основной
        if emails and any(e['address'] == email_to_remove and e['isPrimary'] for e in emails):
            if updated_emails:
                updated_emails[0]['isPrimary'] = True

        # Сохраняем обратно в базу
        success = db.save_user_email(username, updated_emails)

        if success:
            return jsonify({
                'success': True,
                'message': 'Email удален'
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Ошибка удаления email'
            })

    except Exception as e:
        return jsonify({'success': False, 'message': f'Ошибка: {str(e)}'}), 500


# ========== ЗАПУСК СИСТЕМЫ ==========

if __name__ == '__main__':
    print("\n" + "=" * 60)
    print(" ЗАПУСК ИНТЕГРИРОВАННОЙ СИСТЕМЫ МОНИТОРИНГА")
    print("=" * 60)

    # Инициализация системы
    if not init_system():
        print("✗ Не удалось инициализировать систему")
        sys.exit(1)

    # Запуск Flask
    print("\n🌐 Запуск веб-сервера...")
    print(f"   Frontend: http://localhost:5000")
    print(f"   API: http://localhost:5000/api/...")
    print(f"   Папка для снимков: satellite_images/original/")
    print("\n   Для остановки: Ctrl+C")
    print("=" * 60)

    app.run(
        host='0.0.0.0',
        port=5000,
        debug=True,
        threaded=True,
        use_reloader=False
    )
