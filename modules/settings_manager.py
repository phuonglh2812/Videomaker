import os
import json
import logging
from pathlib import Path
from typing import Dict, Optional, List

class SettingsManager:
    def __init__(self, base_path: str | Path):
        """
        Khởi tạo SettingsManager
        Args:
            base_path (str | Path): Đường dẫn gốc của ứng dụng
        """
        # Ensure base_path is Path object
        if isinstance(base_path, str):
            base_path = Path(base_path)
        elif not isinstance(base_path, Path):
            raise ValueError("base_path must be either str or Path")
            
        self.base_path = base_path
        self.config_dir = base_path / 'config'
        self.presets_file = self.config_dir / 'presets.json'
        self.task_history_file = self.config_dir / 'task_history.json'
        self._ensure_config_dir()
        
    def _ensure_config_dir(self):
        """Đảm bảo thư mục config và file presets tồn tại"""
        try:
            self.config_dir.mkdir(exist_ok=True)
            if not self.presets_file.exists():
                self._save_presets({})
            if not self.task_history_file.exists():
                self._save_task_history({})
        except Exception as e:
            logging.error(f"Lỗi khi tạo thư mục config: {e}")
            
    def _save_presets(self, presets: Dict):
        """Lưu presets vào file"""
        try:
            with open(self.presets_file, 'w', encoding='utf-8') as f:
                json.dump(presets, f, indent=4, ensure_ascii=False)
        except Exception as e:
            logging.error(f"Lỗi khi lưu presets: {e}")
            
    def _load_presets(self) -> Dict:
        """Load presets từ file"""
        try:
            if self.presets_file.exists():
                with open(self.presets_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return {}
        except Exception as e:
            logging.error(f"Lỗi khi load presets: {e}")
            return {}
            
    def _save_task_history(self, history: Dict):
        """Lưu task history vào file"""
        try:
            with open(self.task_history_file, 'w', encoding='utf-8') as f:
                json.dump(history, f, indent=4, ensure_ascii=False)
        except Exception as e:
            logging.error(f"Lỗi khi lưu task history: {e}")
            
    def _load_task_history(self) -> Dict:
        """Load task history từ file"""
        try:
            if self.task_history_file.exists():
                with open(self.task_history_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return {}
        except Exception as e:
            logging.error(f"Lỗi khi load task history: {e}")
            return {}
            
    def save_preset(self, name: str, settings: Dict) -> bool:
        """
        Lưu một preset mới
        Args:
            name (str): Tên preset
            settings (Dict): Các cài đặt cần lưu
        Returns:
            bool: True nếu lưu thành công
        """
        try:
            presets = self._load_presets()
            presets[name] = settings
            self._save_presets(presets)
            logging.info(f"Đã lưu preset: {name}")
            return True
        except Exception as e:
            logging.error(f"Lỗi khi lưu preset {name}: {e}")
            return False
            
    def load_preset(self, name: str) -> Optional[Dict]:
        """
        Load một preset theo tên
        Args:
            name (str): Tên preset cần load
        Returns:
            Optional[Dict]: Settings nếu tìm thấy, None nếu không
        """
        try:
            presets = self._load_presets()
            if name in presets:
                logging.info(f"Đã load preset: {name}")
                return presets[name]
            logging.warning(f"Không tìm thấy preset: {name}")
            return None
        except Exception as e:
            logging.error(f"Lỗi khi load preset {name}: {e}")
            return None
            
    def delete_preset(self, name: str) -> bool:
        """
        Xóa một preset
        Args:
            name (str): Tên preset cần xóa
        Returns:
            bool: True nếu xóa thành công
        """
        try:
            presets = self._load_presets()
            if name in presets:
                del presets[name]
                self._save_presets(presets)
                logging.info(f"Đã xóa preset: {name}")
                return True
            return False
        except Exception as e:
            logging.error(f"Lỗi khi xóa preset {name}: {e}")
            return False
            
    def get_preset_names(self) -> List[str]:
        """
        Lấy danh sách tên các preset
        Returns:
            List[str]: Danh sách tên preset
        """
        try:
            presets = self._load_presets()
            return list(presets.keys())
        except Exception as e:
            logging.error(f"Lỗi khi lấy danh sách preset: {e}")
            return []
            
    def update_preset(self, name: str, settings: Dict) -> bool:
        """
        Cập nhật một preset đã tồn tại
        Args:
            name (str): Tên preset
            settings (Dict): Settings mới
        Returns:
            bool: True nếu cập nhật thành công
        """
        try:
            presets = self._load_presets()
            if name in presets:
                presets[name].update(settings)
                self._save_presets(presets)
                logging.info(f"Đã cập nhật preset: {name}")
                return True
            return False
        except Exception as e:
            logging.error(f"Lỗi khi cập nhật preset {name}: {e}")
            return False
            
    def save_task_status(self, task_id: str, status: Dict) -> bool:
        """Lưu task status vào history"""
        try:
            history = self._load_task_history()
            history[task_id] = status
            self._save_task_history(history)
            return True
        except Exception as e:
            logging.error(f"Lỗi khi lưu task status: {e}")
            return False
            
    def get_task_status(self, task_id: str) -> Optional[Dict]:
        """Lấy task status từ history"""
        try:
            history = self._load_task_history()
            return history.get(task_id)
        except Exception as e:
            logging.error(f"Lỗi khi lấy task status: {e}")
            return None
