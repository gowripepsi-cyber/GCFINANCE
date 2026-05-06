import os
import shutil
import zipfile
import sqlite3
import smtplib
from datetime import datetime
from email.message import EmailMessage
from PySide6.QtCore import QThread, Signal

class BackupWorker(QThread):
    progress = Signal(str)
    success = Signal(str)
    error = Signal(str)

    def __init__(self, db_path, backup_dir, email_settings):
        super().__init__()
        self.db_path = db_path
        self.backup_dir = backup_dir
        self.email_settings = email_settings

    def run(self):
        try:
            if not os.path.exists(self.db_path):
                self.error.emit("Database file not found.")
                return

            if not os.path.exists(self.backup_dir):
                os.makedirs(self.backup_dir)

            timestamp = datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
            temp_db_name = f"finance_backup_{timestamp}.db"
            temp_db_path = os.path.join(self.backup_dir, temp_db_name)
            zip_name = f"finance_backup_{timestamp}.zip"
            zip_path = os.path.join(self.backup_dir, zip_name)

            self.progress.emit("Creating safe snapshot of the database...")
            # Safely backup the database without blocking readers
            source_conn = sqlite3.connect(self.db_path)
            dest_conn = sqlite3.connect(temp_db_path)
            with dest_conn:
                source_conn.backup(dest_conn)
            source_conn.close()
            dest_conn.close()

            self.progress.emit("Compressing backup file...")
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                zipf.write(temp_db_path, temp_db_name)

            # Remove the uncompressed temp file
            if os.path.exists(temp_db_path):
                os.remove(temp_db_path)

            self.progress.emit("Sending email...")
            self.send_email(zip_path, timestamp)

            self.success.emit("Backup created and mailed successfully.")

        except Exception as e:
            self.error.emit(f"Backup failed: {str(e)}")

    def send_email(self, file_path, timestamp):
        sender = self.email_settings.get("sender_email", "")
        password = self.email_settings.get("app_password", "")
        receiver = self.email_settings.get("receiver_email", "")
        server = self.email_settings.get("smtp_server", "smtp.gmail.com")
        port_str = self.email_settings.get("smtp_port", "465")
        
        if not sender or not password or not receiver:
            raise Exception("Email settings are incomplete. Backup created locally but email was not sent.")

        try:
            port = int(port_str)
        except ValueError:
            port = 465

        msg = EmailMessage()
        date_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        msg['Subject'] = f"GC Finance Backup - {date_str}"
        msg['From'] = sender
        msg['To'] = receiver
        msg.set_content("Automatic backup generated from GC Finance Management System.\n\nPlease find the attached database backup.")

        with open(file_path, 'rb') as f:
            file_data = f.read()
            file_name = os.path.basename(file_path)

        msg.add_attachment(file_data, maintype='application', subtype='zip', filename=file_name)

        if port == 465:
            with smtplib.SMTP_SSL(server, port) as smtp:
                smtp.login(sender, password)
                smtp.send_message(msg)
        else:
            with smtplib.SMTP(server, port) as smtp:
                smtp.starttls()
                smtp.login(sender, password)
                smtp.send_message(msg)


class RestoreWorker(QThread):
    progress = Signal(str)
    success = Signal(str)
    error = Signal(str)

    def __init__(self, backup_file_path, current_db_path):
        super().__init__()
        self.backup_file_path = backup_file_path
        self.current_db_path = current_db_path

    def run(self):
        temp_extracted_db = None
        safety_backup = f"{self.current_db_path}.safety"
        
        try:
            self.progress.emit("Extracting backup...")
            # 1. Extract if zip, otherwise just use the file
            if self.backup_file_path.endswith(".zip"):
                with zipfile.ZipFile(self.backup_file_path, 'r') as zipf:
                    db_files = [f for f in zipf.namelist() if f.endswith('.db')]
                    if not db_files:
                        raise Exception("No .db file found in the zip archive.")
                    
                    extract_dir = os.path.dirname(self.backup_file_path)
                    temp_extracted_db = zipf.extract(db_files[0], extract_dir)
                    source_file = temp_extracted_db
            else:
                source_file = self.backup_file_path

            self.progress.emit("Validating database file...")
            # 2. Validate DB
            if not self.validate_db(source_file):
                raise Exception("The selected file is not a valid SQLite database or is corrupted.")

            self.progress.emit("Creating safety backup...")
            # 3. Create safety backup
            if os.path.exists(self.current_db_path):
                shutil.copy2(self.current_db_path, safety_backup)

            self.progress.emit("Replacing database...")
            # 4. Replace
            shutil.copy2(source_file, self.current_db_path)

            self.success.emit("Database restored successfully.")

        except Exception as e:
            # Rollback if failed during replace
            if os.path.exists(safety_backup) and os.path.exists(self.current_db_path):
                try:
                    shutil.copy2(safety_backup, self.current_db_path)
                except:
                    pass
            self.error.emit(f"Restore failed: {str(e)}")
        finally:
            # Cleanup
            if temp_extracted_db and os.path.exists(temp_extracted_db):
                try:
                    os.remove(temp_extracted_db)
                except:
                    pass

    def validate_db(self, db_path):
        try:
            # Check SQLite header
            with open(db_path, 'rb') as f:
                header = f.read(16)
                if header != b'SQLite format 3\000':
                    return False
            
            # Run quick PRAGMA to ensure it's openable
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("PRAGMA quick_check")
            result = cursor.fetchone()
            conn.close()
            return result and result[0] == "ok"
        except:
            return False
