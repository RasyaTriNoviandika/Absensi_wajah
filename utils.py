# =================== UTILS.PY - HELPER FUNCTIONS ===================
import os
import magic
import math
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename
from config import Config

def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in Config.ALLOWED_EXTENSIONS

# Ganti fungsi validate_file_upload di utils.py
def validate_file_upload(file):
    """Validate uploaded file comprehensively"""
    errors = []
    
    if not file or file.filename == '':
        errors.append("File tidak boleh kosong")
        return False, errors
    
    # Check filename extension
    if not allowed_file(file.filename):
        errors.append(f"Format file tidak didukung. Gunakan: {', '.join(Config.ALLOWED_EXTENSIONS)}")
    
    # Check file size
    file.seek(0, os.SEEK_END)
    file_size = file.tell()
    file.seek(0)
    
    if file_size > Config.MAX_FILE_SIZE:
        max_mb = Config.MAX_FILE_SIZE / (1024 * 1024)
        errors.append(f"Ukuran file terlalu besar. Maksimal {max_mb:.1f}MB")
    
    return len(errors) == 0, errors

def secure_save_file(file, directory):
    """Securely save uploaded file"""
    os.makedirs(directory, exist_ok=True)
    
    filename = secure_filename(file.filename)
    # Add timestamp to prevent collision
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    name, ext = os.path.splitext(filename)
    unique_filename = f"{timestamp}_{name}{ext}"
    
    filepath = os.path.join(directory, unique_filename)
    file.save(filepath)
    
    return filepath

def cleanup_old_files(directory, days=30):
    """Delete files older than specified days"""
    if not os.path.exists(directory):
        return 0
    
    deleted_count = 0
    cutoff_time = datetime.now() - timedelta(days=days)
    
    for filename in os.listdir(directory):
        filepath = os.path.join(directory, filename)
        
        if os.path.isfile(filepath):
            file_time = datetime.fromtimestamp(os.path.getmtime(filepath))
            
            if file_time < cutoff_time:
                try:
                    os.remove(filepath)
                    deleted_count += 1
                except Exception as e:
                    print(f"Error deleting {filepath}: {e}")
    
    return deleted_count

def hitung_jarak(lat1, lng1, lat2, lng2):
    """Calculate distance between two coordinates in meters (Haversine formula)"""
    R = 6371000  # Earth radius in meters
    
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) *
         math.cos(math.radians(lat2)) *
         math.sin(dlng / 2) ** 2)
    
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    
    return R * c

def format_waktu_lokal(utc_time=None, offset_hours=7):
    """Convert UTC to local time (WIB default)"""
    if utc_time is None:
        utc_time = datetime.utcnow()
    elif isinstance(utc_time, str):
        utc_time = datetime.fromisoformat(utc_time)
    
    return utc_time + timedelta(hours=offset_hours)

def sanitize_input(text):
    """Sanitize user input to prevent injection"""
    if not text:
        return ""
    
    # Remove dangerous characters
    dangerous_chars = ['<', '>', '"', "'", '\\', ';', '&']
    for char in dangerous_chars:
        text = text.replace(char, '')
    
    # Limit length
    return text.strip()[:255]

def validate_coordinates(lat, lng):
    """Validate GPS coordinates"""
    try:
        lat = float(lat)
        lng = float(lng)
        
        if not (-90 <= lat <= 90):
            return False, "Latitude harus antara -90 dan 90"
        
        if not (-180 <= lng <= 180):
            return False, "Longitude harus antara -180 dan 180"
        
        return True, None
    except (ValueError, TypeError):
        return False, "Koordinat tidak valid"

def safe_delete_file(filepath):
    """Safely delete a file with error handling"""
    try:
        if os.path.exists(filepath):
            os.remove(filepath)
            return True
    except Exception as e:
        print(f"Error deleting file {filepath}: {e}")
    return False

def get_file_size_mb(filepath):
    """Get file size in MB"""
    try:
        size_bytes = os.path.getsize(filepath)
        return size_bytes / (1024 * 1024)
    except:
        return 0

def create_backup_filename(original_name):
    """Create backup filename with timestamp"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    name, ext = os.path.splitext(original_name)
    return f"{name}_backup_{timestamp}{ext}"