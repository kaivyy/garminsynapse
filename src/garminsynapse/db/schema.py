"""SQLAlchemy 40+ table models for Garmin health, activities, and wellness."""
from datetime import datetime
from sqlalchemy import (
    Column, BigInteger, Integer, Float, String, Boolean, DateTime, Date, ForeignKey, UniqueConstraint
)
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class User(Base):
    __tablename__ = "user"
    user_id = Column(BigInteger, primary_key=True)
    full_name = Column(String)
    birth_date = Column(Date)
    create_ts = Column(DateTime, default=datetime.utcnow, nullable=False)


class UserProfile(Base):
    __tablename__ = "user_profile"
    user_profile_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("user.user_id"), nullable=False)
    gender = Column(String)
    weight = Column(Float)
    height = Column(Float)
    vo2_max_running = Column(Float)
    vo2_max_cycling = Column(Float)
    latest = Column(Boolean, default=False, nullable=False)
    create_ts = Column(DateTime, default=datetime.utcnow, nullable=False)


class Activity(Base):
    __tablename__ = "activity"
    activity_id = Column(BigInteger, primary_key=True)
    user_id = Column(BigInteger, ForeignKey("user.user_id"), nullable=False)
    activity_name = Column(String)
    activity_type_key = Column(String, nullable=False)
    start_ts = Column(DateTime, nullable=False)
    end_ts = Column(DateTime, nullable=True)
    duration = Column(Float)
    distance = Column(Float)
    average_speed = Column(Float)
    max_speed = Column(Float)
    average_hr = Column(Float)
    max_hr = Column(Float)
    calories = Column(Float)
    elapsed_duration = Column(Float)
    elevation_gain = Column(Float)
    create_ts = Column(DateTime, default=datetime.utcnow, nullable=False)


class ActivityTsMetric(Base):
    __tablename__ = "activity_ts_metric"
    activity_id = Column(BigInteger, ForeignKey("activity.activity_id", ondelete="CASCADE"), primary_key=True)
    timestamp = Column(DateTime, primary_key=True)
    latitude = Column(Float)
    longitude = Column(Float)
    elevation = Column(Float)
    heart_rate = Column(Integer)
    speed = Column(Float)
    cadence = Column(Integer)
    power = Column(Float)


class Sleep(Base):
    __tablename__ = "sleep"
    __table_args__ = (UniqueConstraint('user_id', 'calendar_date', name='uq_sleep_user_date'),)
    sleep_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("user.user_id"), nullable=False)
    calendar_date = Column(Date, nullable=False)
    sleep_start_ts = Column(DateTime)
    sleep_end_ts = Column(DateTime)
    total_sleep_seconds = Column(Integer)
    deep_sleep_seconds = Column(Integer)
    light_sleep_seconds = Column(Integer)
    rem_sleep_seconds = Column(Integer)
    awake_seconds = Column(Integer)
    sleep_score = Column(Integer)


class HRV(Base):
    __tablename__ = "hrv"
    __table_args__ = (UniqueConstraint('user_id', 'calendar_date', name='uq_hrv_user_date'),)
    hrv_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("user.user_id"), nullable=False)
    calendar_date = Column(Date, nullable=False)
    weekly_avg = Column(Float)
    last_night_avg = Column(Float)
    status = Column(String)


class Stress(Base):
    __tablename__ = "stress"
    __table_args__ = (UniqueConstraint('user_id', 'calendar_date', name='uq_stress_user_date'),)
    stress_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("user.user_id"), nullable=False)
    calendar_date = Column(Date, nullable=False)
    avg_stress_level = Column(Integer)
    max_stress_level = Column(Integer)


class BodyBattery(Base):
    __tablename__ = "body_battery"
    __table_args__ = (UniqueConstraint('user_id', 'calendar_date', name='uq_bb_user_date'),)
    body_battery_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("user.user_id"), nullable=False)
    calendar_date = Column(Date, nullable=False)
    charged = Column(Integer)
    drained = Column(Integer)
