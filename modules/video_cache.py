import json
import logging
from pathlib import Path
from typing import Dict, List, Optional
import time

class VideoCache:
    def __init__(self, cache_file: Path):
        """Khởi tạo cache manager
        
        Args:
            cache_file: Đường dẫn file cache JSON
        """
        self.cache_file = Path(cache_file)
        self.cache_file.parent.mkdir(parents=True, exist_ok=True)
        self.cache: Dict[str, dict] = self._load_cache()
        
    def _load_cache(self) -> dict:
        """Load cache từ file"""
        try:
            if self.cache_file.exists():
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return {}
        except Exception as e:
            logging.error(f"Error loading cache: {e}")
            return {}
            
    def _save_cache(self):
        """Lưu cache vào file"""
        try:
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(self.cache, f, indent=2)
        except Exception as e:
            logging.error(f"Error saving cache: {e}")
            
    def update_video_info(self, video_path: Path, duration: float):
        """Cập nhật thông tin video vào cache
        
        Args:
            video_path: Đường dẫn file video
            duration: Thời lượng video (giây)
        """
        video_path = Path(video_path)
        key = str(video_path.resolve())
        
        self.cache[key] = {
            "path": key,
            "filename": video_path.name,
            "duration": duration,
            "last_updated": time.time()
        }
        self._save_cache()
        
    def get_video_info(self, video_path: Path) -> Optional[dict]:
        """Lấy thông tin video từ cache
        
        Args:
            video_path: Đường dẫn file video
            
        Returns:
            Dict chứa thông tin video hoặc None nếu không tìm thấy
        """
        key = str(Path(video_path).resolve())
        return self.cache.get(key)
        
    def clean_missing_files(self):
        """Xóa các file không còn tồn tại khỏi cache"""
        keys_to_remove = []
        
        for key in self.cache:
            if not Path(key).exists():
                keys_to_remove.append(key)
                
        for key in keys_to_remove:
            del self.cache[key]
            
        if keys_to_remove:
            self._save_cache()
            logging.info(f"Removed {len(keys_to_remove)} missing files from cache")
            
    def get_all_videos(self) -> List[dict]:
        """Lấy thông tin tất cả video trong cache
        
        Returns:
            List các dict chứa thông tin video
        """
        return list(self.cache.values())
