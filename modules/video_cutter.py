import subprocess
from pathlib import Path
import logging
from typing import List, Dict
import json
import random

class VideoCutter:
    def __init__(self, cut_dir: Path):
        self.cut_dir = Path(cut_dir)
        self.cut_dir.mkdir(parents=True, exist_ok=True)

    def standardize_video(self, input_path: Path, output_path: Path, gpu_enabled: bool = True) -> bool:
        """Chuẩn hóa video về 1920x1080, 30fps"""
        try:
            # Kiểm tra file input
            input_path = Path(input_path).resolve()
            if not input_path.exists():
                logging.error(f"Input file not found: {input_path}")
                return False
            
            # Chuẩn bị output path
            output_path = Path(output_path).resolve()
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Log thông tin
            logging.info(f"Standardizing video:")
            logging.info(f"Input: {input_path} (exists: {input_path.exists()})")
            logging.info(f"Output: {output_path}")
            logging.info(f"GPU enabled: {gpu_enabled}")
            
            cmd = ["ffmpeg", "-y"]
            if gpu_enabled:
                cmd.extend(["-hwaccel", "cuda"])
            
            cmd.extend([
                "-i", str(input_path),
                "-vf", "scale=1920:1080:force_original_aspect_ratio=decrease,"
                       "pad=1920:1080:(ow-iw)/2:(oh-ih)/2,fps=30",
                "-c:v", "h264_nvenc" if gpu_enabled else "libx264",
                "-preset", "p7" if gpu_enabled else "medium",
                "-rc:v", "vbr_hq" if gpu_enabled else "vbr",
                "-cq:v", "18",
                "-profile:v", "high",
                str(output_path)
            ])
            
            # Log command
            logging.info(f"FFmpeg command: {' '.join(cmd)}")
            
            try:
                # Chạy với capture_output để lấy error message
                result = subprocess.run(
                    cmd, 
                    capture_output=True,
                    text=True,
                    encoding='utf-8',
                    errors='replace'
                )
                
                # Kiểm tra kết quả
                if result.returncode != 0:
                    logging.error(f"FFmpeg error: {result.stderr}")
                    if gpu_enabled:
                        logging.warning("GPU encoding failed, falling back to CPU")
                        return self.standardize_video(input_path, output_path, False)
                    return False
                
                # Kiểm tra file output
                if not output_path.exists():
                    logging.error("Output file was not created")
                    return False
                
                return True
                
            except subprocess.CalledProcessError as e:
                logging.error(f"FFmpeg process error: {str(e)}")
                if gpu_enabled:
                    logging.warning("GPU encoding failed, falling back to CPU")
                    return self.standardize_video(input_path, output_path, False)
                return False
                
            except Exception as e:
                logging.error(f"Unexpected error running FFmpeg: {str(e)}")
                return False
                
        except Exception as e:
            logging.error(f"Error standardizing video: {str(e)}")
            return False

    def get_video_duration(self, video_path: Path) -> float:
        """Lấy thời lượng của video"""
        cmd = [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", str(video_path)
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return float(result.stdout.strip())
        except Exception as e:
            logging.error(f"Error getting video duration: {e}")
            raise

    def cut_video(self, input_path: Path, start_time: float, duration: float, 
                 output_path: Path, gpu_enabled: bool = True) -> bool:
        """Cắt một đoạn video từ input"""
        try:
            # Kiểm tra file input
            input_path = Path(input_path).resolve()
            if not input_path.exists():
                logging.error(f"Input file not found: {input_path}")
                return False
            
            # Chuẩn bị output path
            output_path = Path(output_path).resolve()
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Log thông tin
            logging.info(f"Cutting video segment:")
            logging.info(f"Input: {input_path} (exists: {input_path.exists()})")
            logging.info(f"Output: {output_path}")
            logging.info(f"Start time: {start_time}s, Duration: {duration}s")
            logging.info(f"GPU enabled: {gpu_enabled}")
            
            cmd = ["ffmpeg", "-y"]
            if gpu_enabled:
                cmd.extend(["-hwaccel", "cuda"])
            
            cmd.extend([
                "-ss", str(start_time),
                "-t", str(duration),
                "-i", str(input_path),
                "-c:v", "h264_nvenc" if gpu_enabled else "libx264",
                "-preset", "p7" if gpu_enabled else "medium",
                "-rc:v", "vbr_hq" if gpu_enabled else "vbr",
                "-cq:v", "18",
                "-profile:v", "high",
                str(output_path)
            ])
            
            # Log command
            logging.info(f"FFmpeg command: {' '.join(cmd)}")
            
            try:
                # Chạy với capture_output để lấy error message
                result = subprocess.run(
                    cmd, 
                    capture_output=True,
                    text=True,
                    encoding='utf-8',
                    errors='replace'
                )
                
                # Kiểm tra kết quả
                if result.returncode != 0:
                    logging.error(f"FFmpeg error: {result.stderr}")
                    if gpu_enabled:
                        logging.warning("GPU encoding failed, falling back to CPU")
                        return self.cut_video(input_path, start_time, duration, output_path, False)
                    return False
                
                # Kiểm tra file output
                if not output_path.exists():
                    logging.error("Output file was not created")
                    return False
                
                return True
                
            except subprocess.CalledProcessError as e:
                logging.error(f"FFmpeg process error: {str(e)}")
                if gpu_enabled:
                    logging.warning("GPU encoding failed, falling back to CPU")
                    return self.cut_video(input_path, start_time, duration, output_path, False)
                return False
                
            except Exception as e:
                logging.error(f"Unexpected error running FFmpeg: {str(e)}")
                return False
                
        except Exception as e:
            logging.error(f"Error cutting video: {str(e)}")
            return False

    def process_raw_video(self, input_path: Path, min_duration: float = 4.0, 
                         max_duration: float = 7.0) -> List[Path]:
        """Xử lý video raw: chuẩn hóa và cắt thành các đoạn nhỏ"""
        try:
            # Kiểm tra file input
            input_path = Path(input_path).resolve()
            if not input_path.exists():
                raise ValueError(f"Input file not found: {input_path}")
            
            # Log thông tin
            logging.info(f"Processing raw video:")
            logging.info(f"Input: {input_path} (exists: {input_path.exists()})")
            logging.info(f"Min duration: {min_duration}s")
            logging.info(f"Max duration: {max_duration}s")
            
            # Chuẩn hóa video trước
            std_path = self.cut_dir / f"std_{input_path.name}"
            logging.info(f"Standardizing to: {std_path}")
            
            if not self.standardize_video(input_path, std_path):
                raise ValueError("Failed to standardize video")

            # Lấy thời lượng video
            try:
                duration = self.get_video_duration(std_path)
                logging.info(f"Video duration: {duration}s")
            except Exception as e:
                std_path.unlink(missing_ok=True)
                raise ValueError(f"Failed to get video duration: {str(e)}")

            cut_files = []
            current_time = 0.0

            while current_time < duration:
                try:
                    # Random độ dài đoạn cắt
                    segment_duration = random.uniform(min_duration, max_duration)
                    if current_time + segment_duration > duration:
                        segment_duration = duration - current_time

                    # Tạo file output cho segment
                    output_path = self.cut_dir / f"cut_{len(cut_files):04d}_{input_path.stem}.mp4"
                    logging.info(f"Cutting segment {len(cut_files)+1}:")
                    logging.info(f"Start time: {current_time}s")
                    logging.info(f"Duration: {segment_duration}s")
                    logging.info(f"Output: {output_path}")
                    
                    # Cắt segment
                    if self.cut_video(std_path, current_time, segment_duration, output_path):
                        cut_files.append(output_path)
                        logging.info(f"Successfully cut segment {len(cut_files)}")
                    else:
                        logging.error(f"Failed to cut segment at {current_time}s")
                    
                    current_time += segment_duration

                except Exception as e:
                    logging.error(f"Error cutting segment: {str(e)}")
                    continue

            # Xóa file chuẩn hóa tạm
            std_path.unlink(missing_ok=True)
            
            # Kiểm tra kết quả
            if not cut_files:
                raise ValueError("No segments were created")
            
            logging.info(f"Successfully created {len(cut_files)} segments")
            return cut_files

        except Exception as e:
            logging.error(f"Error processing raw video: {str(e)}")
            raise
