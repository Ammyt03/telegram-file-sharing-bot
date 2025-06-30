import os
from datetime import datetime, timedelta
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean


class Base(DeclarativeBase):
    pass


db = SQLAlchemy(model_class=Base)


class User(db.Model):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    telegram_id = Column(String(50), unique=True, nullable=False)
    username = Column(String(100), nullable=True)
    first_name = Column(String(100), nullable=True)
    last_name = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<User {self.telegram_id}>'


class UserToken(db.Model):
    __tablename__ = 'user_tokens'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, db.ForeignKey('users.id'), nullable=False)
    token = Column(String(255), unique=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
    is_active = Column(Boolean, default=True)
    
    user = db.relationship('User', backref=db.backref('tokens', lazy=True))
    
    def is_expired(self):
        return datetime.utcnow() > self.expires_at
    
    def __repr__(self):
        return f'<UserToken {self.token[:10]}...>'


class FileBundle(db.Model):
    __tablename__ = 'file_bundles'
    
    id = Column(Integer, primary_key=True)
    bundle_id = Column(String(255), unique=True, nullable=False)
    created_by = Column(Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    title = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    
    creator = db.relationship('User', backref=db.backref('created_bundles', lazy=True))
    
    def __repr__(self):
        return f'<FileBundle {self.bundle_id}>'


class MediaFile(db.Model):
    __tablename__ = 'media_files'
    
    id = Column(Integer, primary_key=True)
    file_id = Column(String(255), unique=True, nullable=False)
    bundle_id = Column(String(255), db.ForeignKey('file_bundles.bundle_id'), nullable=True)
    file_name = Column(String(255), nullable=True)
    file_type = Column(String(50), nullable=False)
    file_size = Column(Integer, nullable=True)
    telegram_file_id = Column(String(255), nullable=False)
    uploaded_by = Column(Integer, db.ForeignKey('users.id'), nullable=False)
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    description = Column(Text, nullable=True)
    
    uploader = db.relationship('User', backref=db.backref('uploaded_files', lazy=True))
    bundle = db.relationship('FileBundle', backref=db.backref('files', lazy=True))
    
    def __repr__(self):
        return f'<MediaFile {self.file_name}>'


class AccessLog(db.Model):
    __tablename__ = 'access_logs'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, db.ForeignKey('users.id'), nullable=False)
    file_id = Column(Integer, db.ForeignKey('media_files.id'), nullable=True)
    action = Column(String(50), nullable=False)  # 'token_refresh', 'file_access', 'ads_verification'
    timestamp = Column(DateTime, default=datetime.utcnow)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    
    user = db.relationship('User', backref=db.backref('access_logs', lazy=True))
    media_file = db.relationship('MediaFile', backref=db.backref('access_logs', lazy=True))
    
    def __repr__(self):
        return f'<AccessLog {self.action} by {self.user_id}>'
