import os
import winreg
import logging
from pathlib import Path

class FontManager:
    @staticmethod
    def get_windows_fonts():
        """
        Lấy danh sách font từ Windows Registry và thư mục Fonts
        Returns:
            dict: Dictionary chứa tên font và đường dẫn tương ứng
        """
        fonts_dict = {}
        try:
            # Lấy fonts từ Registry
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts") as key:
                try:
                    i = 0
                    while True:
                        name, value, _ = winreg.EnumValue(key, i)
                        # Bỏ phần "(TrueType)" hoặc tương tự từ tên
                        font_name = name.split(' (')[0]
                        
                        # Xử lý đường dẫn font
                        if not os.path.isabs(value):
                            value = os.path.join(r'C:\Windows\Fonts', value)
                            
                        if os.path.exists(value):
                            fonts_dict[font_name] = value
                        i += 1
                except WindowsError:
                    pass

            # Thêm fonts từ thư mục User Fonts
            user_fonts_dir = os.path.join(os.environ['LOCALAPPDATA'], 'Microsoft', 'Windows', 'Fonts')
            if os.path.exists(user_fonts_dir):
                for font_file in os.listdir(user_fonts_dir):
                    if font_file.lower().endswith(('.ttf', '.otf')):
                        font_path = os.path.join(user_fonts_dir, font_file)
                        font_name = os.path.splitext(font_file)[0]
                        fonts_dict[font_name] = font_path

            return fonts_dict

        except Exception as e:
            logging.error(f"Lỗi khi lấy danh sách font: {e}")
            return {'Arial': os.path.join(r'C:\Windows\Fonts', 'arial.ttf')}

    @staticmethod
    def get_font_path(font_name):
        """
        Lấy đường dẫn font từ tên font
        Args:
            font_name (str): Tên font (ví dụ: 'Arial' hoặc 'Times New Roman')
        Returns:
            str: Đường dẫn đến file font
        """
        try:
            # Nếu font_name đã là đường dẫn
            if os.path.exists(font_name):
                path = font_name
            else:
                # Lấy mapping font từ Registry
                fonts = FontManager.get_windows_fonts()
                path = fonts.get(font_name)
                
                # Nếu không tìm thấy, thử tìm không phân biệt hoa thường
                if not path:
                    font_name_lower = font_name.lower()
                    for name, font_path in fonts.items():
                        if name.lower() == font_name_lower:
                            path = font_path
                            break
                
                # Nếu vẫn không tìm thấy, dùng Arial
                if not path:
                    logging.warning(f"Không tìm thấy font {font_name}, sử dụng Arial")
                    path = fonts.get('Arial', os.path.join(r'C:\Windows\Fonts', 'arial.ttf'))

            # Thêm dấu nháy kép nếu đường dẫn có khoảng trắng
            if ' ' in path:
                path = f'"{path}"'
            
            return path

        except Exception as e:
            logging.error(f"Lỗi khi lấy đường dẫn font: {e}")
            return os.path.join(r'C:\Windows\Fonts', 'arial.ttf')

    @staticmethod
    def validate_font(font_name):
        """
        Kiểm tra xem font có tồn tại không
        Args:
            font_name (str): Tên font
        Returns:
            bool: True nếu font tồn tại, False nếu không
        """
        try:
            fonts = FontManager.get_windows_fonts()
            return font_name in fonts or any(name.lower() == font_name.lower() for name in fonts)
        except Exception as e:
            logging.error(f"Lỗi khi kiểm tra font: {e}")
            return False
