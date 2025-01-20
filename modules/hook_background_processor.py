import os
from pathlib import Path
import logging
import subprocess
import random
from typing import List, Tuple
from .file_manager import FileManager

class HookBackgroundProcessor:
    def __init__(self, base_path: Path):
        self.base_path = base_path
        self.file_manager = FileManager(base_path)
        self.temp_dir = base_path / 'temp'
        self.temp_dir.mkdir(exist_ok=True)
        
        # Initialize input directories
        self.input_16_9_dir = base_path / 'Input_16_9'
        self.input_16_9_dir.mkdir(exist_ok=True)
        self.input_9_16_dir = base_path / 'Input_9_16'
        self.input_9_16_dir.mkdir(exist_ok=True)
        
    def get_video_duration(self, video_path: Path) -> float:
        """Get video duration in seconds"""
        try:
            cmd = [
                'ffprobe', 
                '-v', 'error', 
                '-show_entries', 'format=duration', 
                '-of', 'default=noprint_wrappers=1:nokey=1', 
                str(video_path)
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return float(result.stdout.strip())
        except Exception as e:
            logging.error(f"Error getting video duration: {e}")
            return 0.0
            
    def select_random_videos(self, total_duration: float, input_dir: Path) -> List[Path]:
        """Select random videos that add up to the target duration"""
        if not input_dir.exists():
            raise FileNotFoundError(f"Input directory not found: {input_dir}")
            
        available_videos = list(input_dir.glob('*.mp4'))
        if not available_videos:
            raise ValueError(f"No videos found in {input_dir}")
            
        selected_videos = []
        current_duration = 0
        
        while current_duration < total_duration and available_videos:
            video = random.choice(available_videos)
            available_videos.remove(video)
            
            video_duration = self.get_video_duration(video)
            if video_duration <= 0:
                continue
                
            if current_duration + video_duration > total_duration:
                # Cut the last video to fit
                cut_duration = total_duration - current_duration
                cut_video = self.temp_dir / f"cut_{len(selected_videos):04d}.mp4"
                
                cmd = [
                    'ffmpeg', '-y',
                    '-i', str(video),
                    '-t', str(cut_duration),
                    '-c', 'copy',
                    str(cut_video)
                ]
                subprocess.run(cmd, check=True)
                
                selected_videos.append(cut_video)
                current_duration += cut_duration
                break
            else:
                selected_videos.append(video)
                current_duration += video_duration
                
            if current_duration < total_duration and not available_videos:
                available_videos = list(input_dir.glob('*.mp4'))
                
        return selected_videos
        
    def concatenate_videos(self, video_paths: List[Path], output_path: Path):
        """Concatenate multiple videos into one"""
        if not video_paths:
            raise ValueError("No videos to concatenate")
            
        try:
            # Create concat file
            concat_file = self.temp_dir / "concat.txt"
            with open(concat_file, 'w', encoding='utf-8') as f:
                for video in video_paths:
                    f.write(f"file '{video.absolute()}'\n")
                    
            import ffmpeg
            
            # Concatenate videos using ffmpeg-python
            stream = (
                ffmpeg
                .input(str(concat_file), format='concat', safe=0)
                .output(str(output_path),
                       c='copy'  # Copy both video and audio streams
                )
                .overwrite_output()
            )
            
            stream.run(capture_stdout=True, capture_stderr=True)
            
            # Cleanup concat file
            if concat_file.exists():
                concat_file.unlink()
                
        except ffmpeg.Error as e:
            logging.error(f"Error concatenating videos: {e.stderr.decode() if e.stderr else str(e)}")
            raise
        except Exception as e:
            logging.error(f"Error concatenating videos: {e}")
            raise
            
    def process_background_videos(self, hook_duration: float, audio_duration: float, temp_dir: Path, is_vertical: bool = False) -> Tuple[Path, Path]:
        """Process background videos for hook and main parts
        
        Args:
            hook_duration: Duration of hook audio in seconds
            audio_duration: Duration of main audio in seconds
            temp_dir: Directory to store temporary files
            is_vertical: Whether to use vertical videos from input_9_16 directory
            
        Returns:
            Tuple[Path, Path]: Paths to hook background and main background videos
        """
        try:
            total_duration = hook_duration + audio_duration
            
            # Select input directory based on video orientation
            input_dir = self.input_9_16_dir if is_vertical else self.input_16_9_dir
            
            # Get all mp4 files from input directory
            available_videos = list(input_dir.glob('*.mp4'))
            if not available_videos:
                raise ValueError(f"No videos found in {input_dir}")
            
            # Randomize video list
            random.shuffle(available_videos)
            
            selected_videos = []
            current_duration = 0
            
            # Select videos until we have enough duration
            for video in available_videos:
                video_duration = self.get_video_duration(video)
                if video_duration <= 0:
                    continue
                    
                selected_videos.append(video)
                current_duration += video_duration
                
                if current_duration >= total_duration:
                    break
                    
            if current_duration < total_duration:
                # If we don't have enough duration, reuse videos
                while current_duration < total_duration:
                    for video in available_videos:
                        video_duration = self.get_video_duration(video)
                        if video_duration <= 0:
                            continue
                            
                        selected_videos.append(video)
                        current_duration += video_duration
                        
                        if current_duration >= total_duration:
                            break
            
            # Now we have enough videos, let's process them
            hook_output = temp_dir / "hook_background.mp4"
            main_output = temp_dir / "main_background.mp4"
            
            # Process first video for hook part
            first_video = selected_videos[0]
            first_duration = self.get_video_duration(first_video)
            
            # Cut first video into hook part
            if is_vertical:
                cmd = [
                    'ffmpeg', '-y',
                    '-i', str(first_video),
                    '-t', str(hook_duration),
                    '-vf', 'scale=1080:1920',
                    '-r', '30',
                    '-c:v', 'h264_nvenc',
                    '-preset', 'p4',
                    '-b:v', '4M',
                    str(hook_output)
                ]
            else:
                cmd = [
                    'ffmpeg', '-y',
                    '-i', str(first_video),
                    '-t', str(hook_duration),
                    '-c', 'copy',
                    str(hook_output)
                ]
            subprocess.run(cmd, check=True)
            
            # If first video has enough duration for main part
            remaining_first = first_duration - hook_duration
            if remaining_first >= audio_duration:
                # Cut remaining part for main
                if is_vertical:
                    cmd = [
                        'ffmpeg', '-y',
                        '-i', str(first_video),
                        '-ss', str(hook_duration),
                        '-t', str(audio_duration),
                        '-vf', 'scale=1080:1920',
                        '-r', '30',
                        '-c:v', 'h264_nvenc',
                        '-preset', 'p4',
                        '-b:v', '4M',
                        str(main_output)
                    ]
                else:
                    cmd = [
                        'ffmpeg', '-y',
                        '-i', str(first_video),
                        '-ss', str(hook_duration),
                        '-t', str(audio_duration),
                        '-c', 'copy',
                        str(main_output)
                    ]
                subprocess.run(cmd, check=True)
            else:
                # Need to use more videos for main part
                temp_parts = []
                current_main_duration = 0
                
                # Use remaining part of first video
                if remaining_first > 0:
                    temp_part = temp_dir / f"main_part_0.mp4"
                    if is_vertical:
                        cmd = [
                            'ffmpeg', '-y',
                            '-i', str(first_video),
                            '-ss', str(hook_duration),
                            '-vf', 'scale=1080:1920',
                            '-r', '30',
                            '-c:v', 'h264_nvenc',
                            '-preset', 'p4',
                            '-b:v', '4M',
                            str(temp_part)
                        ]
                    else:
                        cmd = [
                            'ffmpeg', '-y',
                            '-i', str(first_video),
                            '-ss', str(hook_duration),
                            '-c', 'copy',
                            str(temp_part)
                        ]
                    subprocess.run(cmd, check=True)
                    temp_parts.append(temp_part)
                    current_main_duration += remaining_first
                
                # Process remaining videos
                for i, video in enumerate(selected_videos[1:], 1):
                    video_duration = self.get_video_duration(video)
                    remaining_needed = audio_duration - current_main_duration
                    
                    if remaining_needed <= 0:
                        break
                        
                    temp_part = temp_dir / f"main_part_{i}.mp4"
                    if video_duration > remaining_needed:
                        # Cut video to needed duration
                        if is_vertical:
                            cmd = [
                                'ffmpeg', '-y',
                                '-i', str(video),
                                '-t', str(remaining_needed),
                                '-vf', 'scale=1080:1920',
                                '-r', '30',
                                '-c:v', 'h264_nvenc',
                                '-preset', 'p4',
                                '-b:v', '4M',
                                str(temp_part)
                            ]
                        else:
                            cmd = [
                                'ffmpeg', '-y',
                                '-i', str(video),
                                '-t', str(remaining_needed),
                                '-c', 'copy',
                                str(temp_part)
                            ]
                    else:
                        # Use whole video
                        if is_vertical:
                            cmd = [
                                'ffmpeg', '-y',
                                '-i', str(video),
                                '-vf', 'scale=1080:1920',
                                '-r', '30',
                                '-c:v', 'h264_nvenc',
                                '-preset', 'p4',
                                '-b:v', '4M',
                                str(temp_part)
                            ]
                        else:
                            cmd = [
                                'ffmpeg', '-y',
                                '-i', str(video),
                                '-c', 'copy',
                                str(temp_part)
                            ]
                    
                    subprocess.run(cmd, check=True)
                    temp_parts.append(temp_part)
                    current_main_duration += min(video_duration, remaining_needed)
                
                # Concatenate all parts for main video
                self.concatenate_videos(temp_parts, main_output)
                
                # Cleanup temp parts
                for temp_part in temp_parts:
                    if temp_part.exists():
                        temp_part.unlink()
            
            return hook_output, main_output
            
        except Exception as e:
            logging.error(f"Error processing background videos: {e}")
            raise
