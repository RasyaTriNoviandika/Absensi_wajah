# =================== AUTOMATED BACKUP SYSTEM ===================
# File: backup_system.py

import os
import shutil
import sqlite3
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import zipfile
import logging

logger = logging.getLogger(__name__)


# ============= 1. DATABASE BACKUP =============
class DatabaseBackup:
    """Automated database backup system"""
    
    def __init__(self, db_name='database.db', backup_dir='backups'):
        self.db_name = db_name
        self.backup_dir = backup_dir
        self.max_backups = 30  # Keep last 30 backups
        
        # Create backup directory
        os.makedirs(backup_dir, exist_ok=True)
    
    def create_backup(self):
        """Create database backup"""
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_filename = f"db_backup_{timestamp}.db"
            backup_path = os.path.join(self.backup_dir, backup_filename)
            
            # Check if source database exists
            if not os.path.exists(self.db_name):
                logger.error(f"Source database {self.db_name} not found!")
                return False
            
            # Create backup using SQLite backup API (safer than file copy)
            source_conn = sqlite3.connect(self.db_name)
            backup_conn = sqlite3.connect(backup_path)
            
            with backup_conn:
                source_conn.backup(backup_conn)
            
            source_conn.close()
            backup_conn.close()
            
            logger.info(f"✅ Database backup created: {backup_filename}")
            
            # Cleanup old backups
            self.cleanup_old_backups()
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Backup failed: {e}")
            return False
    
    def cleanup_old_backups(self):
        """Remove old backups, keep only recent ones"""
        try:
            backups = []
            for filename in os.listdir(self.backup_dir):
                if filename.startswith('db_backup_') and filename.endswith('.db'):
                    filepath = os.path.join(self.backup_dir, filename)
                    backups.append((filepath, os.path.getmtime(filepath)))
            
            # Sort by modification time (newest first)
            backups.sort(key=lambda x: x[1], reverse=True)
            
            # Remove old backups
            if len(backups) > self.max_backups:
                for filepath, _ in backups[self.max_backups:]:
                    os.remove(filepath)
                    logger.info(f"🗑️ Removed old backup: {os.path.basename(filepath)}")
        
        except Exception as e:
            logger.error(f"Error cleaning up backups: {e}")
    
    def restore_backup(self, backup_filename):
        """Restore database from backup"""
        try:
            backup_path = os.path.join(self.backup_dir, backup_filename)
            
            if not os.path.exists(backup_path):
                logger.error(f"Backup file not found: {backup_filename}")
                return False
            
            # Create a backup of current database before restoring
            current_backup = f"before_restore_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
            shutil.copy2(self.db_name, os.path.join(self.backup_dir, current_backup))
            
            # Restore
            shutil.copy2(backup_path, self.db_name)
            
            logger.info(f"✅ Database restored from: {backup_filename}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Restore failed: {e}")
            return False
    
    def list_backups(self):
        """List all available backups"""
        try:
            backups = []
            for filename in os.listdir(self.backup_dir):
                if filename.startswith('db_backup_') and filename.endswith('.db'):
                    filepath = os.path.join(self.backup_dir, filename)
                    size = os.path.getsize(filepath)
                    mtime = datetime.fromtimestamp(os.path.getmtime(filepath))
                    
                    backups.append({
                        'filename': filename,
                        'size': size,
                        'size_mb': round(size / (1024*1024), 2),
                        'created': mtime.strftime('%Y-%m-%d %H:%M:%S')
                    })
            
            # Sort by creation time (newest first)
            backups.sort(key=lambda x: x['created'], reverse=True)
            return backups
            
        except Exception as e:
            logger.error(f"Error listing backups: {e}")
            return []


# ============= 2. FULL SYSTEM BACKUP =============
class SystemBackup:
    """Backup entire application (database + files)"""
    
    def __init__(self, backup_dir='backups/full'):
        self.backup_dir = backup_dir
        self.max_backups = 7  # Keep last 7 full backups
        
        os.makedirs(backup_dir, exist_ok=True)
    
    def create_full_backup(self):
        """Create full system backup (database + uploaded files)"""
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_filename = f"full_backup_{timestamp}.zip"
            backup_path = os.path.join(self.backup_dir, backup_filename)
            
            with zipfile.ZipFile(backup_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                # Backup database
                if os.path.exists('database.db'):
                    zipf.write('database.db', 'database.db')
                
                # Backup faces directory
                if os.path.exists('faces'):
                    for root, dirs, files in os.walk('faces'):
                        for file in files:
                            filepath = os.path.join(root, file)
                            zipf.write(filepath, filepath)
                
                # Backup uploads directory
                if os.path.exists('uploads'):
                    for root, dirs, files in os.walk('uploads'):
                        for file in files:
                            filepath = os.path.join(root, file)
                            zipf.write(filepath, filepath)
                
                # Backup logs (optional)
                if os.path.exists('logs'):
                    for root, dirs, files in os.walk('logs'):
                        for file in files:
                            if file.endswith('.log'):
                                filepath = os.path.join(root, file)
                                zipf.write(filepath, filepath)
            
            logger.info(f"✅ Full backup created: {backup_filename}")
            
            # Cleanup old backups
            self.cleanup_old_backups()
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Full backup failed: {e}")
            return False
    
    def cleanup_old_backups(self):
        """Remove old full backups"""
        try:
            backups = []
            for filename in os.listdir(self.backup_dir):
                if filename.startswith('full_backup_') and filename.endswith('.zip'):
                    filepath = os.path.join(self.backup_dir, filename)
                    backups.append((filepath, os.path.getmtime(filepath)))
            
            backups.sort(key=lambda x: x[1], reverse=True)
            
            if len(backups) > self.max_backups:
                for filepath, _ in backups[self.max_backups:]:
                    os.remove(filepath)
                    logger.info(f"🗑️ Removed old full backup: {os.path.basename(filepath)}")
        
        except Exception as e:
            logger.error(f"Error cleaning up full backups: {e}")


# ============= 3. SCHEDULED BACKUP =============
class BackupScheduler:
    """Schedule automated backups"""
    
    def __init__(self):
        self.scheduler = BackgroundScheduler()
        self.db_backup = DatabaseBackup()
        self.system_backup = SystemBackup()
    
    def start(self):
        """Start backup scheduler"""
        
        # Daily database backup at 2 AM
        self.scheduler.add_job(
            self.db_backup.create_backup,
            CronTrigger(hour=2, minute=0),
            id='daily_db_backup',
            name='Daily Database Backup',
            replace_existing=True
        )
        
        # Weekly full backup on Sunday at 3 AM
        self.scheduler.add_job(
            self.system_backup.create_full_backup,
            CronTrigger(day_of_week='sun', hour=3, minute=0),
            id='weekly_full_backup',
            name='Weekly Full System Backup',
            replace_existing=True
        )
        
        # Hourly backup during school hours (7 AM - 5 PM)
        self.scheduler.add_job(
            self.db_backup.create_backup,
            CronTrigger(hour='7-17', minute=0),
            id='hourly_backup',
            name='Hourly Backup (School Hours)',
            replace_existing=True
        )
        
        self.scheduler.start()
        logger.info("✅ Backup scheduler started")
    
    def stop(self):
        """Stop backup scheduler"""
        self.scheduler.shutdown()
        logger.info("Backup scheduler stopped")
    
    def get_next_run_times(self):
        """Get next scheduled backup times"""
        jobs = self.scheduler.get_jobs()
        schedule = []
        for job in jobs:
            schedule.append({
                'name': job.name,
                'next_run': job.next_run_time.strftime('%Y-%m-%d %H:%M:%S') if job.next_run_time else 'N/A'
            })
        return schedule


# ============= 4. MANUAL BACKUP TRIGGER =============
def trigger_manual_backup():
    """Trigger manual backup (for admin button)"""
    try:
        db_backup = DatabaseBackup()
        result = db_backup.create_backup()
        
        if result:
            return True, "Backup berhasil dibuat!"
        else:
            return False, "Backup gagal!"
    
    except Exception as e:
        return False, f"Error: {str(e)}"


# ============= 5. INTEGRATION EXAMPLES =============
"""
CARA PAKAI:

1. Di app.py, import:
from backup_system import BackupScheduler, DatabaseBackup, trigger_manual_backup

2. Inisialisasi scheduler saat app start:
backup_scheduler = BackupScheduler()

# Di dalam if __name__ == "__main__":
backup_scheduler.start()

# Jangan lupa stop saat shutdown
import atexit
atexit.register(lambda: backup_scheduler.stop())

3. Route untuk manual backup (Admin):
@app.route("/admin/backup/create", methods=["POST"])
@login_required
def admin_create_backup():
    success, message = trigger_manual_backup()
    
    if success:
        flash(message, "success")
        audit.log_action('manual_backup', 'system', {'status': 'success'})
    else:
        flash(message, "error")
        audit.log_action('manual_backup', 'system', {'status': 'failed'}, 'failed', message)
    
    return redirect(url_for('admin_index'))

4. Route untuk list backups:
@app.route("/admin/backup/list")
@login_required
def admin_list_backups():
    db_backup = DatabaseBackup()
    backups = db_backup.list_backups()
    
    return render_template("admin/backups.html", backups=backups)

5. Route untuk restore backup:
@app.route("/admin/backup/restore/<filename>", methods=["POST"])
@login_required
def admin_restore_backup(filename):
    # Only super admin should be able to restore
    if session.get('admin_username') != 'admin':
        flash("Hanya super admin yang bisa restore backup!", "error")
        return redirect(url_for('admin_list_backups'))
    
    db_backup = DatabaseBackup()
    success = db_backup.restore_backup(filename)
    
    if success:
        flash(f"Database berhasil di-restore dari {filename}", "success")
        audit.log_action('restore_backup', 'system', {'filename': filename})
    else:
        flash("Restore gagal!", "error")
    
    return redirect(url_for('admin_list_backups'))

6. Route untuk download backup:
from flask import send_file

@app.route("/admin/backup/download/<filename>")
@login_required
def admin_download_backup(filename):
    backup_path = os.path.join('backups', filename)
    
    if not os.path.exists(backup_path):
        flash("Backup tidak ditemukan!", "error")
        return redirect(url_for('admin_list_backups'))
    
    audit.log_action('download_backup', 'system', {'filename': filename})
    
    return send_file(backup_path, as_attachment=True)

7. Display backup schedule in admin dashboard:
@app.route("/admin")
@login_required
def admin_index():
    # ... existing code ...
    
    # Get backup schedule
    schedule = backup_scheduler.get_next_run_times()
    
    # Get recent backups
    db_backup = DatabaseBackup()
    recent_backups = db_backup.list_backups()[:5]  # Last 5 backups
    
    return render_template("admin/index.html",
                          # ... existing params ...
                          backup_schedule=schedule,
                          recent_backups=recent_backups)
"""

# ============= 6. BACKUP STATUS & MONITORING =============
def get_backup_status():
    """Get backup system status"""
    try:
        db_backup = DatabaseBackup()
        backups = db_backup.list_backups()
        
        if not backups:
            return {
                'status': 'warning',
                'message': 'Tidak ada backup',
                'last_backup': None,
                'total_backups': 0
            }
        
        last_backup = backups[0]
        last_backup_time = datetime.strptime(last_backup['created'], '%Y-%m-%d %H:%M:%S')
        hours_ago = (datetime.now() - last_backup_time).total_seconds() / 3600
        
        if hours_ago > 24:
            status = 'warning'
            message = f'Backup terakhir {int(hours_ago)} jam yang lalu'
        else:
            status = 'ok'
            message = f'Backup terakhir {int(hours_ago)} jam yang lalu'
        
        return {
            'status': status,
            'message': message,
            'last_backup': last_backup,
            'total_backups': len(backups),
            'total_size_mb': sum(b['size_mb'] for b in backups)
        }
    
    except Exception as e:
        return {
            'status': 'error',
            'message': f'Error: {str(e)}',
            'last_backup': None,
            'total_backups': 0
        }