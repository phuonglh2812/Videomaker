import json
import logging
from pathlib import Path
from datetime import datetime, timedelta
import os

class TaskHistoryManager:
    def __init__(self, base_path):
        self.history_file = Path(base_path) / "task_history.json"
        self.max_history_days = 30  # Giữ lịch sử trong 30 ngày
        
        # Tạo file mới nếu chưa tồn tại hoặc bị lỗi
        self._initialize_history_file()
    
    def _initialize_history_file(self):
        """Khởi tạo file history, xử lý các trường hợp file lỗi"""
        try:
            if self.history_file.exists():
                # Thử đọc file hiện tại
                try:
                    with open(self.history_file, 'r', encoding='utf-8') as f:
                        json.load(f)
                except (json.JSONDecodeError, UnicodeDecodeError):
                    # Nếu file lỗi, backup và tạo mới
                    backup_path = self.history_file.with_suffix('.json.bak')
                    try:
                        os.rename(self.history_file, backup_path)
                        logging.warning(f"Corrupted history file backed up to {backup_path}")
                    except Exception as e:
                        logging.error(f"Failed to backup corrupted history file: {e}")
                        # Nếu không backup được thì xóa luôn
                        os.remove(self.history_file)
                    
                    # Tạo file mới
                    self._create_new_history_file()
            else:
                # Tạo file mới nếu chưa tồn tại
                self._create_new_history_file()
                
        except Exception as e:
            logging.error(f"Error initializing task history: {e}")
            # Đảm bảo luôn có file history hợp lệ
            self._create_new_history_file()
    
    def _create_new_history_file(self):
        """Tạo file history mới với nội dung rỗng"""
        try:
            self.history_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump({}, f, indent=2)
        except Exception as e:
            logging.error(f"Error creating new history file: {e}")
            raise
    
    def save_task(self, task_id: str, task_data: dict):
        """Lưu thông tin task vào file history"""
        try:
            # Đọc history hiện tại
            history = self._read_history()
            
            # Thêm timestamp
            task_data['saved_at'] = datetime.now().isoformat()
            
            # Lưu task
            history[task_id] = task_data
            
            # Xóa các task quá cũ
            self._cleanup_old_tasks(history)
            
            # Ghi lại file
            self._write_history(history)
            
        except Exception as e:
            logging.error(f"Error saving task history: {e}")
            # Nếu có lỗi, thử khởi tạo lại file và lưu
            try:
                self._initialize_history_file()
                history = {task_id: task_data}
                self._write_history(history)
            except Exception as e2:
                logging.error(f"Failed to recover and save task: {e2}")
    
    def get_task(self, task_id: str) -> dict:
        """Lấy thông tin task từ history"""
        try:
            history = self._read_history()
            return history.get(task_id, {"status": "not_found"})
        except Exception as e:
            logging.error(f"Error reading task history: {e}")
            return {"status": "not_found"}
    
    def _read_history(self) -> dict:
        """Đọc file history"""
        try:
            if not self.history_file.exists():
                self._create_new_history_file()
                return {}
                
            with open(self.history_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, UnicodeDecodeError):
            # Nếu file lỗi, khởi tạo lại
            self._initialize_history_file()
            return {}
        except Exception as e:
            logging.error(f"Error reading history file: {e}")
            return {}
    
    def _write_history(self, history: dict):
        """Ghi file history"""
        try:
            # Ghi vào file tạm trước
            temp_file = self.history_file.with_suffix('.json.tmp')
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(history, f, indent=2, ensure_ascii=False)
            
            # Rename file tạm thành file chính
            os.replace(temp_file, self.history_file)
            
        except Exception as e:
            logging.error(f"Error writing history file: {e}")
            # Xóa file tạm nếu có lỗi
            if temp_file.exists():
                try:
                    os.remove(temp_file)
                except:
                    pass
            raise
    
    def _cleanup_old_tasks(self, history: dict):
        """Xóa các task quá cũ"""
        now = datetime.now()
        history_copy = history.copy()
        
        for task_id, task_data in history_copy.items():
            try:
                saved_at = datetime.fromisoformat(task_data.get('saved_at', now.isoformat()))
                if now - saved_at > timedelta(days=self.max_history_days):
                    del history[task_id]
            except (ValueError, TypeError) as e:
                logging.warning(f"Invalid date format for task {task_id}: {e}")
                # Giữ lại task nếu không parse được ngày
