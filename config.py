# =================== CONFIG.PY - CENTRALIZED CONFIGURATION ===================
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Config:
    """Base configuration"""
    # Flask
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    DEBUG = os.getenv('DEBUG', 'False').lower() == 'true'
    
    # Database
    DATABASE_NAME = os.getenv('DATABASE_NAME', 'database.db')
    
    # Upload
    MAX_FILE_SIZE = int(os.getenv('MAX_FILE_SIZE', 5242880))  # 5MB default
    ALLOWED_EXTENSIONS = os.getenv('ALLOWED_EXTENSIONS', 'jpg,jpeg,png').split(',')
    UPLOAD_DIR = 'uploads'
    FACES_DIR = 'faces'
    
    # Face Recognition
    FACE_TOLERANCE = float(os.getenv('FACE_RECOGNITION_TOLERANCE', 0.5))
    FACE_DUPLICATE_TOLERANCE = float(os.getenv('FACE_RECOGNITION_DUPLICATE_TOLERANCE', 0.5))
    
    # Location
    SCHOOL_LAT = float(os.getenv('SCHOOL_LAT', -6.260960))
    SCHOOL_LNG = float(os.getenv('SCHOOL_LNG', 106.959603))
    RADIUS = int(os.getenv('RADIUS', 15))
    
    # Admin Default
    DEFAULT_ADMIN_USERNAME = os.getenv('DEFAULT_ADMIN_USERNAME', 'admin')
    DEFAULT_ADMIN_PASSWORD = os.getenv('DEFAULT_ADMIN_PASSWORD', 'admin123')
    
    # Session
    SESSION_PERMANENT = os.getenv('SESSION_PERMANENT', 'False').lower() == 'true'
    SESSION_COOKIE_SECURE = os.getenv('SESSION_COOKIE_SECURE', 'True').lower() == 'true'
    SESSION_COOKIE_HTTPONLY = os.getenv('SESSION_COOKIE_HTTPONLY', 'True').lower() == 'true'
    SESSION_COOKIE_SAMESITE = os.getenv('SESSION_COOKIE_SAMESITE', 'Lax')
    
    # Rate Limiting
    LOGIN_RATE_LIMIT = int(os.getenv('LOGIN_RATE_LIMIT', 5))
    LOGIN_RATE_LIMIT_PERIOD = int(os.getenv('LOGIN_RATE_LIMIT_PERIOD', 300))
    
    # File Cleanup
    CLEANUP_OLD_FILES_DAYS = int(os.getenv('CLEANUP_OLD_FILES_DAYS', 30))
    
    # Logging
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    LOG_FILE = os.getenv('LOG_FILE', 'app.log')
    
    # Timezone
    TIMEZONE = 'Asia/Jakarta'
    UTC_OFFSET = 7  # WIB

class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    SESSION_COOKIE_SECURE = False

class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    SESSION_COOKIE_SECURE = True

# Select configuration based on environment
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}

def get_config():
    """Get configuration based on FLASK_ENV"""
    env = os.getenv('FLASK_ENV', 'development')
    return config.get(env, config['default'])