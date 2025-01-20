import os
import pysubs2
import logging
from pathlib import Path
from typing import Dict, Optional
from .font_manager import FontManager
import ffmpeg

class ColorConverter:
    """Xử lý chuyển đổi màu giữa các định dạng"""
    
    @staticmethod
    def normalize_color(color: str) -> str:
        """Chuẩn hóa màu về định dạng ASS"""
        # Preset colors nếu input không hợp lệ
        DEFAULT_COLORS = {
            'primary': '&HFFFFFF&',  # Trắng
            'outline': '&H000000&',  # Đen
            'back': '&H000000&'      # Đen
        }
        
        logging.debug(f"Input color: {color}")
        
        try:
            # Nếu là None hoặc empty
            if not color:
                logging.debug("Empty color, using default")
                return DEFAULT_COLORS['primary']
                
            # Bỏ các ký tự không cần thiết
            color = color.strip().replace('#', '').replace('0x', '')
            logging.debug(f"Stripped color: {color}")
            
            # Nếu đã đúng định dạng ASS
            if color.startswith('&H') and color.endswith('&'):
                hex_part = color[2:-1]
                logging.debug(f"ASS format detected, hex part: {hex_part}")
                # Kiểm tra xem phần hex có hợp lệ không
                int(hex_part, 16)
                if len(hex_part) == 6:
                    return color
                    
            # Nếu là hex RGB thông thường (RRGGBB)
            if len(color) == 6:
                try:
                    # Kiểm tra tính hợp lệ của hex
                    int(color, 16)
                    # Chuyển từ RGB sang BGR
                    r, g, b = color[:2], color[2:4], color[4:]
                    result = f"&H{b}{g}{r}&"
                    logging.debug(f"Converted RRGGBB to ASS: {result}")
                    return result
                except ValueError:
                    logging.debug(f"Invalid hex value: {color}")
                    pass
                    
            # Nếu là hex RGB ngắn (RGB)
            if len(color) == 3:
                try:
                    # Chuyển RGB ngắn thành đầy đủ
                    r, g, b = color[0]*2, color[1]*2, color[2]*2
                    result = f"&H{b}{g}{r}&"
                    logging.debug(f"Converted RGB to ASS: {result}")
                    return result
                except ValueError:
                    logging.debug(f"Invalid short hex: {color}")
                    pass
                    
            logging.warning(f"Invalid color format: {color}, using default")
            return DEFAULT_COLORS['primary']
            
        except Exception as e:
            logging.error(f"Error converting color: {str(e)}")
            return DEFAULT_COLORS['primary']

class SubtitleProcessor:
    def __init__(self):
        """Initialize SubtitleProcessor"""
        self.color_converter = ColorConverter()
        self.font_manager = FontManager()

    def convert_srt_to_ass(self, input_path: Path, config: Optional[Dict] = None, start_offset: float = 0, is_vertical: bool = False) -> Optional[Path]:
        """
        Chuyển đổi subtitle từ SRT sang ASS
        
        Args:
            input_path (Path): Đường dẫn file SRT
            config (dict, optional): Cấu hình subtitle
            start_offset (float): Offset in seconds to add to subtitle timing
            is_vertical (bool): Whether the video is vertical
        
        Returns:
            Path: Đường dẫn file ASS
        """
        try:
            if not input_path.exists():
                logging.error(f"Input SRT file not found: {input_path}")
                return None
                
            # Đọc subtitle
            try:
                subs = pysubs2.load(str(input_path), encoding='utf-8')
                logging.info(f"Successfully loaded SRT file: {input_path}")
            except Exception as e:
                logging.error(f"Error loading subtitle file: {e}")
                return None
            
            # Cấu hình mặc định cho video dọc
            if is_vertical:
                style = pysubs2.SSAStyle(
                    fontname="Arial",
                    fontsize=20,
                    primarycolor="&HFFFFFF&",  # Trắng
                    outlinecolor="&H000000&",  # Đen
                    backcolor="&H000000&",     # Đen
                    bold=0,
                    italic=0,
                    alignment=10,  # Middle-center cho video dọc (Legacy ASS)
                    marginv=20,   # Margin dọc
                    marginl=20,   # Margin trái
                    marginr=20    # Margin phải
                )
            else:
                # Cấu hình cho video ngang
                style = pysubs2.SSAStyle(
                    fontname="Arial",
                    fontsize=20,
                    primarycolor="&HFFFFFF&",  # Trắng
                    outlinecolor="&H000000&",  # Đen
                    backcolor="&H000000&",     # Đen
                    bold=0,
                    italic=0,
                    alignment=2,  # Bottom-center cho video ngang
                    marginv=10,   # Margin dọc
                    marginl=10,   # Margin trái
                    marginr=10    # Margin phải
                )
            
            # Log cấu hình ban đầu
            logging.info(f"Initial style alignment: {style.alignment}")
            
            # Cập nhật style từ config nếu có
            if config:
                logging.info(f"Applying config: {config}")
                for key, value in config.items():
                    if hasattr(style, key):
                        # Convert alignment từ string sang int nếu cần
                        if key == 'alignment' and isinstance(value, str):
                            value = int(value)
                        old_value = getattr(style, key)
                        setattr(style, key, value)
                        logging.info(f"Updated {key}: {old_value} -> {value}")
            
            # Thêm style vào subtitle
            subs.styles["Default"] = style
            logging.info(f"Final style alignment: {style.alignment}")
            
            # Áp dụng style cho tất cả dòng
            for line in subs:
                line.style = "Default"
                
                # Xóa các tag ASS cũ nếu có
                text = line.text
                while '}{' in text:
                    text = text.replace('}{', '')
                text = text.strip('{}')
                
                # Thêm alignment vào text
                line.text = "{\\an%d}%s" % (style.alignment, text)
                
                logging.debug(f"Processed line: {line.text}")
                
                # Thêm offset nếu cần
                if start_offset > 0:
                    line.start += start_offset * 1000  # Convert to ms
                    line.end += start_offset * 1000
            
            # Lưu file ASS
            output_path = input_path.with_suffix('.ass')
            subs.save(str(output_path))
            logging.info(f"Successfully saved ASS file: {output_path}")
            
            # Kiểm tra file đã được tạo
            if not output_path.exists():
                logging.error(f"Failed to create ASS file: {output_path}")
                return None
                
            return output_path
            
        except Exception as e:
            logging.error(f"Error converting SRT to ASS: {str(e)}")
            return None

    def create_ass_subtitle(self, srt_path: str, video_path: str, output_path: str, 
                          subtitle_settings: dict, start_offset: float = 0, is_vertical: bool = False):
        """Create ASS subtitle from SRT and apply to video
        
        Args:
            srt_path (str): Path to SRT file
            video_path (str): Path to video file
            output_path (str): Path to output video
            subtitle_settings (dict): Subtitle settings
            start_offset (float): Offset in seconds to add to subtitle timing
            is_vertical (bool): Whether the video is vertical
        """
        try:
            # Convert SRT to ASS if needed
            if Path(srt_path).suffix.lower() == '.srt':
                ass_path = self.convert_srt_to_ass(
                    Path(srt_path), 
                    subtitle_settings, 
                    start_offset,
                    is_vertical
                )
            else:
                ass_path = srt_path

            # Build ffmpeg command
            if is_vertical:
                stream = (
                    ffmpeg
                    .input(video_path)
                    .filter('ass', ass_path)
                    .output(output_path,
                           acodec='aac',
                           vcodec='libx264',
                           preset='medium',
                           crf=23,
                           video_bitrate='2500k',
                           audio_bitrate='192k',
                           vf='scale=1080:1920')  # Scale for vertical video
                    .overwrite_output()
                )
            else:
                stream = (
                    ffmpeg
                    .input(video_path)
                    .filter('ass', ass_path)
                    .output(output_path,
                           acodec='aac',
                           vcodec='libx264',
                           preset='medium',
                           crf=23,
                           video_bitrate='2500k',
                           audio_bitrate='192k')
                    .overwrite_output()
                )

            # Run ffmpeg command
            stream.run(capture_stdout=True, capture_stderr=True)

        except Exception as e:
            logging.error(f"Error creating ASS subtitle: {e}")
            raise

    def validate_subtitle_timing(self, subtitle_path: Path, duration: float) -> bool:
        """Always return True as we allow subtitle duration mismatch"""
        return True
