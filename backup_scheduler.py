# backup_scheduler.py
import schedule
import time
import shutil
from datetime import datetime

def backup_database():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = f"backups/database_backup_{timestamp}.db"
    shutil.copy2("database.db", backup_file)
    print(f"✅ Backup created: {backup_file}")

# Backup setiap hari jam 2 pagi
schedule.every().day.at("02:00").do(backup_database)

while True:
    schedule.run_pending()
    time.sleep(60)