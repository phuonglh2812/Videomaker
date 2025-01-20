import logging
from pathlib import Path
from typing import List
from .video_cutter import VideoCutter
from .file_manager import FileManager

class VideoCutterProcessor:
    def __init__(self, raw_dir: Path, cut_dir: Path):
        """Khởi tạo processor để cắt video từ raw thành các segment"""
        self.raw_dir = Path(raw_dir)
        self.cut_dir = Path(cut_dir)
        self.file_manager = FileManager(raw_dir=self.raw_dir, cut_dir=self.cut_dir)
        self.video_cutter = VideoCutter(self.cut_dir)

    def process_raw_videos(self, min_duration: float = 4.0, max_duration: float = 7.0) -> List[Path]:
        """Xử lý tất cả video raw: chuẩn hóa và cắt thành các segment"""
        try:
            # Lấy danh sách raw videos
            raw_videos = self.file_manager.get_raw_videos()
            if not raw_videos:
                raise ValueError("No raw videos found in raw directory")

            logging.info(f"Found {len(raw_videos)} raw videos to process")
            processed_segments = []

            # Xử lý từng raw video
            for raw_video in raw_videos:
                try:
                    logging.info(f"Processing raw video: {raw_video}")
                    segments = self.video_cutter.process_raw_video(
                        raw_video,
                        min_duration=min_duration,
                        max_duration=max_duration
                    )
                    processed_segments.extend(segments)
                    logging.info(f"Created {len(segments)} segments from {raw_video}")
                except Exception as e:
                    logging.error(f"Error processing raw video {raw_video}: {e}")
                    continue

            # Kiểm tra kết quả
            if not processed_segments:
                raise ValueError("No segments were created from raw videos")

            logging.info(f"Successfully created {len(processed_segments)} segments from {len(raw_videos)} raw videos")
            return processed_segments

        except Exception as e:
            logging.error(f"Error in process_raw_videos: {e}")
            raise
