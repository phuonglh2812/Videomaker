import os
from pathlib import Path
import logging
import shutil
from typing import List
import uuid
import sys

class FileManager:
    @staticmethod
    def get_base_path():
        """
        Lấy đường dẫn gốc của ứng dụng
        Ưu tiên theo thứ tự:
        1. Nếu là PyInstaller executable
        2. Nếu là script Python
        3. Thư mục làm việc hiện tại
        """
        # Kiểm tra nếu đang chạy từ PyInstaller
        if getattr(sys, 'frozen', False):
            # Đường dẫn của executable
            return Path(sys.executable).parent
        
        # Nếu đang chạy script
        if hasattr(sys, '_MEIPASS'):
            # Đường dẫn của PyInstaller temporary folder
            return Path(sys._MEIPASS)
        
        # Sử dụng đường dẫn của script chính
        script_path = Path(sys.argv[0]).resolve().parent
        
        # Fallback về thư mục làm việc hiện tại
        return script_path or Path.cwd()

    def __init__(self, base_path: Path = None, raw_dir: Path = None, cut_dir: Path = None):
        """Initialize FileManager
        
        Args:
            base_path (Path, optional): Đường dẫn gốc. Defaults to None.
            raw_dir (Path, optional): Đường dẫn thư mục raw. Defaults to None.
            cut_dir (Path, optional): Đường dẫn thư mục cut. Defaults to None.
        """
        # Nếu không truyền base_path, tự động lấy
        if base_path is None:
            base_path = self.get_base_path()
        
        # Chuyển đổi thành đường dẫn tuyệt đối
        self.base_path = Path(base_path).resolve()
        
        # Log đường dẫn để debug
        logging.info(f"Base path initialized: {self.base_path}")
        
        # Define directory structure
        self.raw_dir = Path(raw_dir) if raw_dir else self.base_path / 'raw'
        self.cut_dir = Path(cut_dir) if cut_dir else self.base_path / 'cut'
        self.used_dir = self.base_path / 'used'
        self.temp_dir = self.base_path / 'temp'
        self.final_dir = self.base_path / 'final'
        
        # Create directories
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.cut_dir.mkdir(parents=True, exist_ok=True)
        self.used_dir.mkdir(parents=True, exist_ok=True)
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.final_dir.mkdir(parents=True, exist_ok=True)
        
        logging.info(f"Raw directory: {self.raw_dir}")
        logging.info(f"Cut directory: {self.cut_dir}")
        logging.info(f"Used directory: {self.used_dir}")
        logging.info(f"Temp directory: {self.temp_dir}")
        logging.info(f"Final directory: {self.final_dir}")
        
    def _create_directories(self):
        """Create necessary directories"""
        try:
            for directory in [self.raw_dir, self.used_dir, self.cut_dir, 
                            self.temp_dir, self.final_dir]:
                directory.mkdir(parents=True, exist_ok=True)
                logging.info(f"Created directory: {directory}")
        except Exception as e:
            logging.error(f"Error creating directories: {str(e)}")
            raise
            
    def get_raw_videos(self) -> List[Path]:
        """Get list of raw videos to process"""
        try:
            raw_videos = [f for f in self.raw_dir.glob('*.mp4')]
            logging.info(f"Found {len(raw_videos)} raw videos in {self.raw_dir}")
            for video in raw_videos:
                logging.info(f"Raw video: {video} (Exists: {video.exists()})")
            return raw_videos
        except Exception as e:
            logging.error(f"Error getting raw videos: {str(e)}")
            return []
            
    def get_cut_videos(self) -> List[Path]:
        """Get list of cut video segments"""
        try:
            # Log thông tin chi tiết về thư mục
            logging.info(f"Searching for cut videos in: {self.cut_dir}")
            logging.info(f"Cut directory exists: {self.cut_dir.exists()}")
            
            # Liệt kê toàn bộ nội dung thư mục
            if self.cut_dir.exists():
                logging.info("Contents of cut directory:")
                for item in self.cut_dir.iterdir():
                    logging.info(f"- {item} (Exists: {item.exists()})")
            
            # Lấy danh sách video
            cut_videos = [f for f in self.cut_dir.glob('*.mp4')]
            
            logging.info(f"Found {len(cut_videos)} cut videos")
            for video in cut_videos:
                logging.info(f"Cut video: {video} (Exists: {video.exists()})")
            
            return cut_videos
        except Exception as e:
            logging.error(f"Error getting cut videos: {str(e)}")
            return []
            
    def move_to_used(self, video_path: Path):
        """Move processed raw video to used directory"""
        try:
            if not video_path.exists():
                raise FileNotFoundError(f"Video file not found: {video_path}")
                
            target = self.used_dir / video_path.name
            shutil.move(str(video_path), str(target))
            logging.info(f"Moved {video_path} to {target}")
            
        except Exception as e:
            logging.error(f"Error moving file to used: {str(e)}")
            raise
            
    def cleanup_temp(self):
        """Clean up temporary files"""
        try:
            if self.temp_dir.exists():
                for file in self.temp_dir.glob('*'):
                    try:
                        if file.is_file():
                            file.unlink()
                    except Exception as e:
                        logging.warning(f"Could not delete temp file {file}: {str(e)}")
            logging.info("Cleaned up temporary files")
            
        except Exception as e:
            logging.error(f"Error cleaning up temp files: {str(e)}")
            
    def create_final_path(self, base_name: str) -> Path:
        """Create path for final output file"""
        try:
            final_path = self.final_dir / f"{Path(base_name).stem}_final.mp4"
            return final_path
            
        except Exception as e:
            logging.error(f"Error creating final path: {str(e)}")
            raise
            
    def generate_temp_path(self, suffix: str = ".mp4") -> Path:
        """Tạo đường dẫn file tạm với tên ngẫu nhiên"""
        return self.temp_dir / f"{uuid.uuid4()}{suffix}"
