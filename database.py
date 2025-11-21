from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Text, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import datetime
import os

Base = declarative_base()


class MonitoredLocation(Base):
    __tablename__ = 'monitored_locations'

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    address = Column(String(500))
    created_date = Column(DateTime, default=datetime.datetime.utcnow)
    is_active = Column(Boolean, default=True)


class SatelliteImage(Base):
    __tablename__ = 'satellite_images'

    id = Column(Integer, primary_key=True)
    location_id = Column(Integer, nullable=False)
    image_path = Column(String(500), nullable=False)
    capture_date = Column(DateTime, nullable=False)
    file_size = Column(Integer)
    image_hash = Column(String(64))


class ChangeDetection(Base):
    __tablename__ = 'change_detections'

    id = Column(Integer, primary_key=True)
    location_id = Column(Integer, nullable=False)
    detection_date = Column(DateTime, default=datetime.datetime.utcnow)
    change_score = Column(Float, nullable=False)
    change_type = Column(String(100))
    confidence = Column(Float)
    before_image_id = Column(Integer)
    after_image_id = Column(Integer)
    processed_image_path = Column(String(500))
    details = Column(Text)


class DatabaseManager:
    def __init__(self, db_path='sqlite:///satellite_monitor.db'):
        self.engine = create_engine(db_path, echo=False)
        self.Session = sessionmaker(bind=self.engine)
        Base.metadata.create_all(self.engine)
        print("✅ База данных инициализирована")

    def add_location(self, name, latitude, longitude, address=None):
        session = self.Session()
        location = MonitoredLocation(
            name=name,
            latitude=latitude,
            longitude=longitude,
            address=address
        )
        session.add(location)
        session.commit()
        location_id = location.id
        session.close()
        print(f"✅ Место добавлено: {name} (ID: {location_id})")
        return location_id

    def get_locations(self, active_only=True):
        session = self.Session()
        query = session.query(MonitoredLocation)
        if active_only:
            query = query.filter(MonitoredLocation.is_active == True)
        locations = query.all()
        session.close()
        return locations

    def get_location_by_id(self, location_id):
        session = self.Session()
        location = session.query(MonitoredLocation).filter_by(id=location_id).first()
        session.close()
        return location

    def save_satellite_image(self, location_id, image_path, capture_date, image_hash=None):
        session = self.Session()
        image = SatelliteImage(
            location_id=location_id,
            image_path=image_path,
            capture_date=capture_date,
            file_size=os.path.getsize(image_path) if os.path.exists(image_path) else 0,
            image_hash=image_hash
        )
        session.add(image)
        session.commit()
        image_id = image.id
        session.close()
        return image_id

    def get_latest_image(self, location_id):
        session = self.Session()
        image = session.query(SatelliteImage).filter_by(
            location_id=location_id
        ).order_by(SatelliteImage.capture_date.desc()).first()
        session.close()
        return image

    def get_previous_image(self, location_id, exclude_current=None):
        """Получает предыдущее изображение, исключая текущее"""
        session = self.Session()
        query = session.query(SatelliteImage).filter_by(location_id=location_id)

        if exclude_current:
            query = query.filter(SatelliteImage.id != exclude_current)

        image = query.order_by(SatelliteImage.capture_date.desc()).first()
        session.close()
        return image

    def save_change_detection(self, location_id, change_score, change_type,
                              confidence, before_image_id, after_image_id,
                              processed_image_path, details):
        session = self.Session()
        detection = ChangeDetection(
            location_id=location_id,
            change_score=change_score,
            change_type=change_type,
            confidence=confidence,
            before_image_id=before_image_id,
            after_image_id=after_image_id,
            processed_image_path=processed_image_path,
            details=details
        )
        session.add(detection)
        session.commit()
        detection_id = detection.id
        session.close()
        return detection_id

    def get_change_history(self, location_id=None, limit=10):
        session = self.Session()
        query = session.query(ChangeDetection)
        if location_id:
            query = query.filter_by(location_id=location_id)
        changes = query.order_by(ChangeDetection.detection_date.desc()).limit(limit).all()
        session.close()
        return changes

    def clear_all_data(self):
        """Очищает все данные из базы"""
        session = self.Session()
        try:
            # Удаляем в правильном порядке из-за внешних ключей
            session.query(ChangeDetection).delete()
            session.query(SatelliteImage).delete()
            session.query(MonitoredLocation).delete()
            session.commit()
            print("🗑️ Все данные удалены из базы")
            return True
        except Exception as e:
            print(f"❌ Ошибка очистки базы: {e}")
            session.rollback()
            return False
        finally:
            session.close()

    def reset_database(self):
        """Полностью пересоздает базу данных"""
        try:
            Base.metadata.drop_all(self.engine)
            Base.metadata.create_all(self.engine)
            print("🔄 База данных пересоздана")
            return True
        except Exception as e:
            print(f"❌ Ошибка пересоздания базы: {e}")
            return False