import os
from pathlib import Path
import logging
import subprocess
import random
import time
from typing import Dict, List, Optional
from .file_manager import FileManager
from .video_cutter import VideoCutter
from .subtitle_processor import SubtitleProcessor

class VideoProcessor:
    def __init__(self, base_path: Path):
        self.base_path = base_path
        self.file_manager = FileManager(base_path)
        self.video_cutter = VideoCutter(base_path)
        self.subtitle_processor = SubtitleProcessor()
        
    def _safe_delete_file(self, file_path: Path, max_retries: int = 3, initial_delay: float = 0.5):
        """Safely delete a file with retries and exponential backoff"""
        if not file_path.exists():
            return

        delay = initial_delay
        for attempt in range(max_retries):
            try:
                # Wait before trying to delete
                time.sleep(delay)
                file_path.unlink()
                logging.debug(f"Successfully deleted {file_path}")
                return
            except PermissionError:
                if attempt < max_retries - 1:
                    logging.debug(f"Failed to delete {file_path}, retrying in {delay}s...")
                    delay *= 2  # Exponential backoff
                else:
                    logging.warning(f"Could not delete {file_path} after {max_retries} attempts")
            except Exception as e:
                logging.warning(f"Error deleting {file_path}: {e}")
                break

    def _cleanup_temp_files(self, temp_files: List[Path]):
        """Clean up temporary files safely"""
        for file_path in temp_files:
            self._safe_delete_file(file_path)

    def get_video_duration(self, video_path: Path) -> float:
        """Get video duration in seconds"""
        try:
            video_path = Path(video_path).resolve().absolute()
            logging.info(f"Getting duration for video: {video_path}")
            
            if not video_path.exists():
                similar_files = list(video_path.parent.glob(f"{video_path.stem}*{video_path.suffix}"))
                if similar_files:
                    video_path = similar_files[0]
                    logging.warning(f"Found similar file: {video_path}")
            
            if not video_path.exists():
                logging.error(f"Video file not found: {video_path}")
                return 0.0
            
            try:
                file_size = video_path.stat().st_size
                if file_size == 0:
                    logging.warning(f"Video file is empty: {video_path}")
                    return 0.0
            except Exception as size_err:
                logging.error(f"Error checking file size: {size_err}")
                return 0.0
            
            cmd = [
                'ffprobe', 
                '-v', 'error', 
                '-show_entries', 'format=duration', 
                '-of', 'default=noprint_wrappers=1:nokey=1', 
                str(video_path)
            ]
            
            logging.info(f"FFprobe command: {' '.join(cmd)}")
            
            try:
                result = subprocess.run(
                    cmd, 
                    capture_output=True, 
                    text=True, 
                    encoding='utf-8', 
                    errors='replace',
                    check=False
                )
            except Exception as subprocess_err:
                logging.error(f"Subprocess error: {subprocess_err}")
                return 0.0
            
            if result.returncode != 0:
                logging.error(f"FFprobe error for {video_path}")
                logging.error(f"FFprobe stderr: {result.stderr}")
                return 0.0
            
            output = result.stdout.strip()
            if not output:
                logging.warning(f"No duration found for {video_path}")
                return 0.0
            
            logging.info(f"FFprobe output: {output}")
            
            try:
                duration = float(output)
                return duration
            except ValueError:
                logging.error(f"Cannot convert duration to float: {output}")
                return 0.0
        
        except Exception as e:
            logging.error(f"Unexpected error getting video duration for {video_path}: {str(e)}")
            return 0.0

    def get_video_size(self, video_path: str) -> tuple:
        """Get video dimensions using ffprobe"""
        try:
            cmd = [
                'ffprobe', 
                '-v', 'error',
                '-select_streams', 'v:0',
                '-show_entries', 'stream=width,height',
                '-of', 'csv=s=x:p=0',
                str(video_path)
            ]
            output = subprocess.check_output(cmd).decode('utf-8').strip()
            width, height = map(int, output.split('x'))
            return width, height
        except Exception as e:
            logging.error(f"Error getting video dimensions: {str(e)}")
            return 1920, 1080  # Default size if unable to detect

    def check_gpu_support(self) -> bool:
        """Check if GPU encoding is supported"""
        try:
            result = subprocess.run(
                ['ffmpeg', '-hide_banner', '-encoders'],
                capture_output=True,
                text=True,
                check=True
            )
            return 'h264_nvenc' in result.stdout
        except Exception:
            return False
            
    def get_encoding_settings(self) -> dict:
        """Get encoding settings based on hardware support"""
        if self.check_gpu_support():
            return {
                'hwaccel': [],
                'video_codec': [
                    '-c:v', 'h264_nvenc',
                    '-preset', 'p7',
                    '-rc', 'vbr',
                    '-cq', '20',
                    '-b:v', '0'
                ]
            }
        else:
            return {
                'hwaccel': [],
                'video_codec': [
                    '-c:v', 'libx264',
                    '-preset', 'medium',
                    '-crf', '23'
                ]
            }

    def process_video(
        self,
        audio_path: Path,
        subtitle_path: Path,
        overlay1_path: Optional[Path] = None,
        overlay2_path: Optional[Path] = None,
        subtitle_config: Optional[Dict] = None,
        output_name: Optional[str] = None
    ):
        temp_files = []
        try:
            audio_path = Path(audio_path)
            subtitle_path = Path(subtitle_path)
            
            if not audio_path.exists():
                raise FileNotFoundError(f"Audio file not found: {audio_path}")
            if not subtitle_path.exists():
                raise FileNotFoundError(f"Subtitle file not found: {subtitle_path}")
            
            if subtitle_path.suffix.lower() == '.srt':
                subtitle_path = self.subtitle_processor.convert_srt_to_ass(
                    subtitle_path, 
                    subtitle_config or {}
                )
            
            if overlay1_path and not Path(overlay1_path).exists():
                logging.warning(f"Overlay1 file not found: {overlay1_path}")
                overlay1_path = None
            
            if overlay2_path and not Path(overlay2_path).exists():
                logging.warning(f"Overlay2 file not found: {overlay2_path}")
                overlay2_path = None
            
            self.base_path.joinpath('temp').mkdir(parents=True, exist_ok=True)
            self.base_path.joinpath('final').mkdir(parents=True, exist_ok=True)
            
            audio_duration = self.get_video_duration(audio_path)
            
            cut_videos = self.file_manager.get_cut_videos()
            if not cut_videos:
                raise ValueError("No cut videos available. Please run video cutter first.")
            
            selected_videos = []
            current_duration = 0
            available_videos = cut_videos.copy()
            
            while current_duration < audio_duration and available_videos:
                video = random.choice(available_videos)
                available_videos.remove(video)
                
                video_duration = self.get_video_duration(video)
                
                if video_duration <= 0:
                    logging.warning(f"Skipping video with zero duration: {video}")
                    continue
                
                if current_duration + video_duration > audio_duration:
                    cut_duration = audio_duration - current_duration
                    
                    cut_video_path = self.base_path / 'temp' / f"cut_{len(selected_videos):04d}.mp4"
                    temp_files.append(cut_video_path)
                    
                    cut_cmd = [
                        'ffmpeg', '-y', 
                        '-i', str(video), 
                        '-t', str(cut_duration),
                        '-c', 'copy',
                        str(cut_video_path)
                    ]
                    
                    subprocess.run(cut_cmd, check=True)
                    
                    selected_videos.append(cut_video_path)
                    current_duration += cut_duration
                    logging.info(f"Partially selected video: {video} (Cut duration: {cut_duration:.2f}s, Total: {current_duration:.2f}s)")
                    break
                else:
                    selected_videos.append(video)
                    current_duration += video_duration
                    logging.info(f"Selected video: {video} (Duration: {video_duration:.2f}s, Total: {current_duration:.2f}s)")
                
                if current_duration < audio_duration and not available_videos:
                    logging.warning(f"Reusing cut videos to reach target duration. Current: {current_duration:.2f}s, Target: {audio_duration:.2f}s")
                    available_videos = [v for v in cut_videos if v not in selected_videos]
                    if not available_videos:
                        available_videos = cut_videos.copy()
            
            if not selected_videos:
                raise ValueError("Could not find suitable videos for the audio duration")
            
            # Create concat file
            concat_file = self.base_path / 'temp' / 'concat.txt'
            temp_files.append(concat_file)
            
            with open(concat_file, 'w', encoding='utf-8') as f:
                for video in selected_videos:
                    f.write(f"file '{video.absolute()}'\n")
            
            # Concatenate videos
            temp_video = self.base_path / 'temp' / 'temp_concat.mp4'
            temp_files.append(temp_video)
            
            encoding_settings = self.get_encoding_settings()
            
            concat_cmd = [
                'ffmpeg', '-y'
            ]
            concat_cmd.extend(encoding_settings['hwaccel'])
            concat_cmd.extend([
                '-f', 'concat',
                '-safe', '0',
                '-i', str(concat_file)
            ])
            concat_cmd.extend(encoding_settings['video_codec'])
            concat_cmd.append(str(temp_video))
            
            subprocess.run(concat_cmd, check=True)
            
            # Add audio, subtitle and overlays
            if output_name:
                output_path = self.base_path / 'final' / output_name
            else:
                output_path = self.base_path / 'final' / f"{audio_path.stem}_final.mp4"
            output_path.parent.mkdir(exist_ok=True)

            # Build FFmpeg command
            cmd = ['ffmpeg', '-y']
            cmd.extend(encoding_settings['hwaccel'])
            cmd.extend([
                '-i', str(temp_video),
                '-i', str(audio_path)
            ])

            input_files = 2
            if overlay1_path:
                cmd.extend(['-i', str(overlay1_path)])
                input_files += 1
            if overlay2_path:
                cmd.extend(['-i', str(overlay2_path)])
                input_files += 1

            filter_complex = []
            
            filter_complex.append("[0:v]null[base]")
            last_output = "base"
            
            if overlay1_path:
                filter_complex.append(f"[{last_output}][{input_files-2}:v]overlay=(W-w)/2:(H-h)/2[ov1]")
                last_output = "ov1"
            
            if overlay2_path:
                filter_complex.append(f"[{last_output}][{input_files-1}:v]overlay=(W-w)/2:(H-h)/2[ov2]")
                last_output = "ov2"
            
            # Chuẩn hóa đường dẫn subtitle
            subtitle_path_str = str(subtitle_path).replace("\\", "/").replace(":", "\\:")
            
            # Thêm subtitle ở layer cuối cùng
            filter_complex.append(f"[{last_output}]ass='{subtitle_path_str}'[final]")
            last_output = "final"

            cmd.extend([
                '-filter_complex', ';'.join(filter_complex),
                '-map', f'[{last_output}]',
                '-map', '1:a'
            ])
            cmd.extend(encoding_settings['video_codec'])
            cmd.extend([
                '-c:a', 'aac',
                '-b:a', '192k'
            ])
            cmd.append(str(output_path))

            # Log FFmpeg command
            logging.info(f"FFmpeg command: {' '.join(cmd)}")

            subprocess.run(cmd, check=True)

            # Give ffmpeg some time to release file handles
            time.sleep(0.5)

            # Clean up temp files
            self._cleanup_temp_files(temp_files)

            return output_path

        except Exception as e:
            logging.error(f"Error processing video: {str(e)}")
            raise
