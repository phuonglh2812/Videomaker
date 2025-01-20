import os
from pathlib import Path
import logging
import subprocess
import time
import random
import psutil
from typing import Dict, List, Optional
from .file_manager import FileManager
from .subtitle_processor import SubtitleProcessor
from .hook_background_processor import HookBackgroundProcessor
import ffmpeg

class HookVideoProcessor:
    def __init__(self, base_path: Path):
        self.base_path = base_path
        self.file_manager = FileManager(base_path)
        self.background_processor = HookBackgroundProcessor(base_path)
        self.subtitle_processor = SubtitleProcessor()
        self.temp_dir = base_path / 'temp'
        self.temp_dir.mkdir(exist_ok=True)
        
    def _safe_delete_file(self, file_path: Path, max_retries: int = 5, initial_delay: float = 0.5):
        """Safely delete a file with retries and exponential backoff
        
        Args:
            file_path (Path): Path to the file to delete
            max_retries (int): Maximum number of retry attempts
            initial_delay (float): Initial delay between retries
        """
        if not file_path or not file_path.exists():
            return

        delay = initial_delay
        for attempt in range(max_retries):
            try:
                # Thử xóa file
                os.remove(str(file_path))
                logging.debug(f"Successfully deleted {file_path}")
                return True
            except PermissionError:
                if attempt < max_retries - 1:
                    logging.debug(f"Failed to delete {file_path}, retrying in {delay}s...")
                    time.sleep(delay)
                    delay *= 2
                else:
                    logging.warning(f"Could not delete {file_path} after {max_retries} attempts")
            except FileNotFoundError:
                logging.debug(f"File already deleted: {file_path}")
                return True
            except Exception as e:
                logging.warning(f"Error deleting {file_path}: {e}")
                return False
        return False

    def _cleanup_temp_files(self, temp_files: Optional[List[Path]] = None):
        """Clean up temporary files safely"""
        if temp_files is None:
            # If no specific files provided, clean up entire temp directory
            temp_files = list(self.temp_dir.glob('*'))
            logging.info(f"Cleaning up all files in temp directory: {len(temp_files)} files")
        
        for file_path in temp_files:
            try:
                if not isinstance(file_path, Path):
                    file_path = Path(file_path)
                
                if file_path.exists():
                    logging.debug(f"Attempting to delete temp file: {file_path}")
                    self._safe_delete_file(file_path)
                else:
                    logging.debug(f"Temp file already deleted or not found: {file_path}")
            except Exception as e:
                logging.error(f"Error while cleaning up temp file {file_path}: {e}")

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
            
    def get_encoding_settings(self, is_vertical: bool = False) -> dict:
        """Get optimized encoding settings for hook videos"""
        base_settings = {
            'hwaccel': [],  # Let CPU handle decode and filters
        }
        
        if self.check_gpu_support():
            base_settings['video_codec'] = [
                '-c:v', 'h264_nvenc',
                '-preset', 'p4',     # Optimized quality preset
                '-tune', 'hq',       # High quality tuning
                '-rc', 'cbr',        # Constant bitrate for consistent quality
                '-b:v', '4M',        # 4Mbps bitrate
                '-minrate', '4M',    # Force constant bitrate
                '-maxrate', '4M',    # Force constant bitrate
                '-bufsize', '4M',    # Match bitrate for CBR
                '-profile:v', 'high',# High profile for better quality
                '-r', '30',          # 30fps
                '-g', '60'           # Keyframe every 2 seconds
            ]
        else:
            base_settings['video_codec'] = [
                '-c:v', 'libx264',
                '-preset', 'medium',  # Balance between speed and quality
                '-crf', '23',        # Constant quality factor
                '-b:v', '4M',        # Target bitrate
                '-maxrate', '5M',    # Maximum bitrate
                '-bufsize', '8M',    # Buffer size
                '-profile:v', 'high',# High profile for better quality
                '-r', '30',          # 30fps
                '-g', '60',          # Keyframe every 2 seconds
                '-movflags', '+faststart'  # Enable fast start for web playback
            ]
            
        return base_settings

    def normalize_audio(self, input_path: Path, output_path: Path):
        """Normalize audio to 24bit 34khz stereo"""
        try:
            cmd = [
                'ffmpeg', '-y',
                '-i', str(input_path),
                '-acodec', 'pcm_s24le',  # 24-bit
                '-ar', '34000',          # 34khz
                '-ac', '2',              # stereo
                str(output_path)
            ]
            subprocess.run(cmd, check=True)
        except Exception as e:
            logging.error(f"Error normalizing audio: {e}")
            raise

    def get_audio_duration(self, audio_path: Path) -> float:
        """Get audio duration in seconds using ffprobe"""
        try:
            cmd = [
                'ffprobe', 
                '-v', 'error', 
                '-show_entries', 'format=duration', 
                '-of', 'default=noprint_wrappers=1:nokey=1', 
                str(audio_path)
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return float(result.stdout.strip())
        except Exception as e:
            logging.error(f"Error getting audio duration: {e}")
            return 0.0

    def _add_thumbnail_with_fade(self, video_path: Path, thumbnail_path: Path, 
                               audio_path: Path, output_path: Path, is_vertical: bool = False):
        """Add thumbnail with fade effect to video"""
        try:
            # Get encoding settings
            encoding_settings = self.get_encoding_settings(is_vertical)
            video_duration = self.get_video_duration(video_path)
            
            # Complex filter for overlay and fade effects
            filter_complex = [
                "[0:v][1:v]overlay=0:0:enable='between(t,0,{})'".format(video_duration),
                f"fade=t=in:st=0:d=0.5,fade=t=out:st={video_duration-0.5}:d=0.5[v]"
            ]

            command = [
                'ffmpeg',
                '-i', str(video_path),
                '-i', str(thumbnail_path),
                '-i', str(audio_path),
                '-filter_complex', ','.join(filter_complex),
                '-map', '[v]',
                '-map', '2:a'
            ]

            # Add encoding settings
            command.extend(encoding_settings['video_codec'])

            # Add audio codec
            command.extend(['-c:a', 'aac'])
            command.append(str(output_path))
            
            # Log the command for debugging
            logging.info(f"Running FFmpeg command: {' '.join(command)}")
            
            subprocess.run(command, check=True, capture_output=True, text=True)
            
        except subprocess.CalledProcessError as e:
            logging.error(f"Error adding thumbnail with fade: {e}")
            # Try without hardware acceleration
            try:
                # Remove NVENC specific options
                command = [c for c in command if not any(x in c.lower() for x in ['nvenc', 'tune', 'rc', 'bufsize'])]
                # Add CPU encoder settings
                command.extend(['-c:v', 'libx264', '-preset', 'medium'])
                subprocess.run(command, check=True, capture_output=True, text=True)
            except subprocess.CalledProcessError as e:
                logging.error(f"Error adding thumbnail with fade (CPU fallback): {e}")
                raise
        except Exception as e:
            logging.error(f"Error adding thumbnail with fade: {e}")
            raise

    def _process_video_with_subtitle(self, video_path: str, audio_path: str, 
                                   subtitle_path: str, output_path: str, 
                                   subtitle_settings: dict, is_vertical: bool = False):
        """Process video with subtitle
        
        Args:
            video_path (str): Path to input video
            audio_path (str): Path to audio file
            subtitle_path (str): Path to subtitle file
            output_path (str): Path to output video
            subtitle_settings (dict): Subtitle settings
            is_vertical (bool): Whether the video is vertical
        """
        try:
            # Convert SRT to ASS if needed
            if Path(subtitle_path).suffix.lower() == '.srt':
                ass_path = self.subtitle_processor.convert_srt_to_ass(
                    Path(subtitle_path), 
                    subtitle_settings, 
                    0,  # No start offset needed
                    is_vertical
                )
                if not ass_path or not ass_path.exists():
                    logging.error(f"Failed to convert SRT to ASS: {subtitle_path}")
                    raise ValueError(f"Failed to convert SRT to ASS: {subtitle_path}")
                subtitle_path = str(ass_path)
            
            # Kiểm tra file ASS
            if not os.path.exists(subtitle_path):
                logging.error(f"Subtitle file not found: {subtitle_path}")
                raise FileNotFoundError(f"Subtitle file not found: {subtitle_path}")

            # Chuẩn hóa đường dẫn subtitle
            subtitle_path_str = str(subtitle_path).replace("\\", "/").replace(":", "\\:")

            # Chuẩn bị lệnh FFmpeg
            cmd = [
                'ffmpeg', '-y',
                '-i', str(video_path),
                '-i', str(audio_path)
            ]

            # Sử dụng GPU cho encode cuối
            vf_filter = 'scale=1080:1920,fps=30,setpts=PTS-STARTPTS' if is_vertical else 'scale=1920:1080,fps=30,setpts=PTS-STARTPTS'
            cmd.extend([
                '-filter_complex', 
                f'[0:v]{vf_filter},ass=\'{subtitle_path_str}\'[final]',
                '-map', '[final]',
                '-map', '1:a',
                '-c:v', 'h264_nvenc',
                '-preset', 'slow',
                '-profile:v', 'high',
                '-level', '4.2',
                '-rc', 'vbr_hq',
                '-cq', '19',
                '-b:v', '0',
                '-maxrate', '20M',
                '-bufsize', '40M',
                '-pix_fmt', 'yuv420p',
                '-c:a', 'aac',
                '-b:a', '192k',
                str(output_path)
            ])

            logging.info(f"Running FFmpeg command: {' '.join(cmd)}")
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            logging.info(f"FFmpeg output: {result.stdout}")
            
            if not os.path.exists(output_path):
                logging.error(f"Output file not created: {output_path}")
                raise RuntimeError(f"Failed to create output file: {output_path}")

        except subprocess.CalledProcessError as e:
            logging.error(f"FFmpeg error processing video with subtitle: {e.stderr}")
            raise
        except Exception as e:
            logging.error(f"Error processing video with subtitle: {str(e)}")
            raise

    def concatenate_videos(self, video_paths: List[str], output_path: str):
        """Concatenate multiple videos using subprocess and ffmpeg
        
        Args:
            video_paths (List[str]): List of video paths to concatenate
            output_path (str): Path to output concatenated video
        """
        try:
            # Tạo file danh sách để nối video
            concat_list_path = str(Path(self.temp_dir) / 'concat_list.txt')
            with open(concat_list_path, 'w') as f:
                for video_path in video_paths:
                    f.write(f"file '{video_path}'\n")

            # Chuẩn bị lệnh FFmpeg
            cmd = [
                'ffmpeg', '-y',
                '-f', 'concat',
                '-safe', '0',
                '-i', concat_list_path,
                '-c', 'copy',  # Copy streams without re-encoding
                str(output_path)
            ]

            # Log FFmpeg command
            logging.info(f"FFmpeg concatenate command: {' '.join(cmd)}")

            # Chạy lệnh
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            
            # Xóa file danh sách tạm
            os.unlink(concat_list_path)
            
            logging.info(f"Successfully concatenated videos to: {output_path}")
            return output_path

        except subprocess.CalledProcessError as e:
            logging.error(f"FFmpeg concatenation error: {e.stderr}")
            raise
        except Exception as e:
            logging.error(f"Error concatenating videos: {str(e)}")
            raise

    def get_temp_filename(self, base_name: str, extension: str) -> str:
        """Generate a unique temp filename with timestamp"""
        timestamp = int(time.time())
        return f"{base_name}_{timestamp}.{extension}"

    def process_hook_video(
        self,
        hook_audio: Path,
        audio_path: Path,
        thumbnail_path: Path,
        subtitle_path: Path,
        output_path: Path,
        subtitle_settings: Dict,
        is_vertical: bool = False
    ) -> bool:
        """Process video with hook audio and background videos
        
        Args:
            hook_audio: Path to hook audio file (.mp3/.wav)
            audio_path: Path to main audio file (.mp3/.wav)
            thumbnail_path: Path to thumbnail image
            subtitle_path: Path to subtitle file
            output_path: Path to output video
            subtitle_settings: Subtitle settings dict
            is_vertical: Whether the video is vertical
        """
        try:
            retry_count = 1
            retry_delay = 5
            success = False
            temp_files = []
            
            for attempt in range(retry_count + 1):
                try:
                    temp_dir = self.temp_dir
                    
                    # Step 1: Normalize audio files
                    hook_norm_wav = Path(temp_dir) / self.get_temp_filename("normalized_hook", "wav")
                    main_norm_wav = Path(temp_dir) / self.get_temp_filename("normalized_main", "wav")
                    
                    self.normalize_audio(hook_audio, hook_norm_wav)
                    self.normalize_audio(audio_path, main_norm_wav)
                    
                    # Add to temp_files only if they exist
                    if hook_norm_wav.exists():
                        temp_files.append(hook_norm_wav)
                    if main_norm_wav.exists():
                        temp_files.append(main_norm_wav)
                    
                    # Step 2: Get audio durations
                    hook_duration = self.get_audio_duration(hook_norm_wav)
                    audio_duration = self.get_audio_duration(main_norm_wav)
                    
                    # Step 3: Process background videos
                    hook_bg, main_bg = self.background_processor.process_background_videos(
                        hook_duration, audio_duration, temp_dir, is_vertical
                    )
                    
                    # Add to temp_files only if they exist
                    hook_bg_path = Path(hook_bg)
                    main_bg_path = Path(main_bg)
                    if hook_bg_path.exists():
                        temp_files.append(hook_bg_path)
                    if main_bg_path.exists():
                        temp_files.append(main_bg_path)
                    
                    # Step 4: Add thumbnail with fade to hook background
                    hook_with_thumb = Path(temp_dir) / self.get_temp_filename("hook_with_thumbnail", "mp4")
                    self._add_thumbnail_with_fade(hook_bg, thumbnail_path, hook_norm_wav, hook_with_thumb, is_vertical)
                    if hook_with_thumb.exists():
                        temp_files.append(hook_with_thumb)
                    
                    # Step 5: Process main part with subtitle
                    main_with_sub = Path(temp_dir) / self.get_temp_filename("main_with_subtitle", "mp4")
                    self._process_video_with_subtitle(
                        main_bg, main_norm_wav, subtitle_path, main_with_sub, subtitle_settings, is_vertical
                    )
                    if main_with_sub.exists():
                        temp_files.append(main_with_sub)
                    
                    # Step 6: Concatenate final video
                    self._concatenate_videos([hook_with_thumb, main_with_sub], output_path, is_vertical)
                    success = True
                    break

                except Exception as e:
                    logging.error(f"Attempt {attempt + 1} failed: {e}")
                    if attempt < retry_count:
                        logging.info(f"Retrying in {retry_delay} seconds...")
                        time.sleep(retry_delay)
                    else:
                        raise

        except Exception as e:
            logging.error(f"Error in video processing: {e}")
            raise
        finally:
            # Log temp files before cleanup
            logging.info(f"Cleaning up {len(temp_files)} temp files: {[str(f) for f in temp_files]}")
            # Cleanup temp files
            self._cleanup_temp_files(temp_files)

    def _concatenate_videos(self, video_paths: List[Path], output_path: Path, is_vertical: bool = False):
        """Concatenate multiple videos into one with re-encoding for smooth transitions"""
        try:
            # Create temp file for video list
            temp_file = self.temp_dir / "video_list.txt"
            with open(temp_file, 'w') as f:
                for video_path in video_paths:
                    # Convert Windows path to ffmpeg format
                    safe_path = str(video_path.absolute()).replace('\\', '/')
                    f.write(f"file '{safe_path}'\n")
            
            # Get encoding settings
            encoding_settings = self.get_encoding_settings(is_vertical)
            
            # Prepare FFmpeg command with re-encoding
            cmd = [
                'ffmpeg', '-y',
                '-safe', '0',
                '-f', 'concat',
                '-i', str(temp_file)
            ]
            
            # Add hardware acceleration if available
            cmd.extend(encoding_settings['hwaccel'])
            
            # Add video encoding settings
            cmd.extend([
                '-c:v', 'h264_nvenc',  # Use NVIDIA encoder
                '-preset', 'p4',        # High quality preset
                '-tune', 'hq',          # High quality tuning
                '-rc', 'vbr',          # Variable bitrate
                '-cq', '20',           # Constant quality factor
                '-b:v', '4M',          # Target bitrate
                '-maxrate', '6M',      # Maximum bitrate
                '-bufsize', '8M',      # Buffer size
                '-profile:v', 'high',  # High profile
                '-g', '30',            # Keyframe interval
                '-keyint_min', '30',   # Minimum keyframe interval
            ])
            
            # Add audio encoding settings
            cmd.extend([
                '-c:a', 'aac',
                '-b:a', '192k',
                '-ar', '48000',
                '-ac', '2'
            ])
            
            # Output path
            cmd.append(str(output_path))
            
            logging.info(f"Running FFmpeg command: {' '.join(cmd)}")
            subprocess.run(cmd, check=True)
            logging.info(f"Successfully concatenated videos: {output_path}")
            
            # Cleanup temp file
            if temp_file.exists():
                try:
                    temp_file.unlink()
                except Exception as e:
                    logging.warning(f"Error deleting {temp_file}: {e}")
                    
        except Exception as e:
            logging.error(f"Error concatenating videos: {e}")
            raise
