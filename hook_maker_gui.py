from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, colorchooser
import logging
import json
from modules import FileManager, HookVideoProcessor, SubtitleProcessor, SettingsManager
from typing import Optional, List, Dict
import os
import time
import winreg

class HookMakerGUI:
    def __init__(self, root):
        self.root = root
        self.base_path = Path(os.path.dirname(os.path.abspath(__file__)))
        
        # Initialize variables
        self.hook_path_var = tk.StringVar()
        self.audio_path_var = tk.StringVar()
        self.preset_var = tk.StringVar()
        self.new_preset_var = tk.StringVar()
        
        # Font settings
        self.font_var = tk.StringVar(value="Arial")
        self.font_size_var = tk.StringVar(value="48")
        self.primary_color_var = tk.StringVar(value="&HFFFFFF&")
        self.outline_color_var = tk.StringVar(value="&H000000&")
        self.back_color_var = tk.StringVar(value="&H000000&")
        self.outline_var = tk.StringVar(value="2")
        self.shadow_var = tk.StringVar(value="0")
        self.margin_v_var = tk.StringVar(value="20")
        self.margin_h_var = tk.StringVar(value="20")
        self.alignment_var = tk.StringVar(value="2")
        self.max_chars_var = tk.StringVar(value="40")
        
        # Initialize subtitle settings
        self.subtitle_settings = {}
        self.update_subtitle_settings()  # Initialize with default values
        
        # Initialize base path and directories
        self.base_path = Path.cwd()
        logging.info(f"Base path initialized: {self.base_path}")
        
        # Initialize directories
        self.raw_dir = self.base_path / 'raw'
        self.cut_dir = self.base_path / 'cut'
        self.used_dir = self.base_path / 'used'
        self.temp_dir = self.base_path / 'temp'
        self.final_dir = self.base_path / 'final'
        
        # Log directory paths
        logging.info(f"Raw directory: {self.raw_dir}")
        logging.info(f"Cut directory: {self.cut_dir}")
        logging.info(f"Used directory: {self.used_dir}")
        logging.info(f"Temp directory: {self.temp_dir}")
        logging.info(f"Final directory: {self.final_dir}")
        
        # Create directories if they don't exist
        for dir_path in [self.raw_dir, self.cut_dir, self.used_dir, self.temp_dir, self.final_dir]:
            dir_path.mkdir(exist_ok=True)
        
        # Setup UI first
        self.setup_ui()
        
        # Then initialize settings manager and load presets
        self.init_settings_manager()
        
        # Finally bind preset selection
        self.preset_combo.bind('<<ComboboxSelected>>', self.load_selected_preset)
        
        # Initialize file manager
        self.file_manager = FileManager(
            base_path=self.base_path,
            raw_dir=self.raw_dir,
            cut_dir=self.cut_dir
        )
        
        # Initialize processors with optimized settings for hook videos
        self.video_processor = HookVideoProcessor(self.base_path)
        
    def setup_ui(self):
        """Setup main UI"""
        # Tạo notebook để chứa các tab
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(expand=True, fill='both')
        
        # Tạo tab chính
        self.main_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.main_tab, text="Single Video")
        
        # Thiết lập tab chính như cũ
        # Set window title
        self.root.title("Hook Maker")
        
        # Create main frame
        main_frame = ttk.Frame(self.main_tab, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # File selection frame
        file_frame = ttk.LabelFrame(main_frame, text="File Selection", padding="5")
        file_frame.grid(row=0, column=0, columnspan=2, padx=5, pady=5, sticky="nsew")
        
        # Hook audio selection
        ttk.Label(file_frame, text="Hook Audio:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        ttk.Entry(file_frame, textvariable=self.hook_path_var).grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        ttk.Button(file_frame, text="Browse", command=lambda: self.browse_file(self.hook_path_var, [("Audio files", "*.mp3;*.wav")])).grid(row=0, column=2, padx=5, pady=5)
        
        # Audio selection
        ttk.Label(file_frame, text="Audio File:").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        ttk.Entry(file_frame, textvariable=self.audio_path_var).grid(row=1, column=1, padx=5, pady=5, sticky="ew")
        ttk.Button(file_frame, text="Browse", command=lambda: self.browse_file(self.audio_path_var, [("Audio files", "*.mp3;*.wav")])).grid(row=1, column=2, padx=5, pady=5)
        
        # Subtitle selection
        ttk.Label(file_frame, text="Subtitle File:").grid(row=2, column=0, padx=5, pady=5, sticky="w")
        self.subtitle_path = tk.StringVar()
        ttk.Entry(file_frame, textvariable=self.subtitle_path).grid(row=2, column=1, padx=5, pady=5, sticky="ew")
        ttk.Button(file_frame, text="Browse", command=lambda: self.browse_file(self.subtitle_path, [("SRT files", "*.srt")])).grid(row=2, column=2, padx=5, pady=5)
        
        # Thumbnail selection
        ttk.Label(file_frame, text="Thumbnail:").grid(row=3, column=0, padx=5, pady=5, sticky="w")
        self.thumbnail_path = tk.StringVar()
        ttk.Entry(file_frame, textvariable=self.thumbnail_path).grid(row=3, column=1, padx=5, pady=5, sticky="ew")
        ttk.Button(file_frame, text="Browse", command=lambda: self.browse_file(self.thumbnail_path, [("PNG files", "*.png")])).grid(row=3, column=2, padx=5, pady=5)
        
        # Preset frame
        preset_frame = ttk.LabelFrame(main_frame, text="Preset Settings", padding="5")
        preset_frame.grid(row=1, column=0, columnspan=2, padx=5, pady=5, sticky="nsew")
        
        # Preset combobox
        ttk.Label(preset_frame, text="Load Preset:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.preset_combo = ttk.Combobox(preset_frame, textvariable=self.preset_var)
        self.preset_combo.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        
        # New preset name
        ttk.Label(preset_frame, text="New Preset Name:").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        preset_name_entry = ttk.Entry(preset_frame, textvariable=self.new_preset_var)
        preset_name_entry.grid(row=1, column=1, padx=5, pady=5, sticky="ew")
        
        # Buttons for preset
        ttk.Button(preset_frame, text="Save Preset", command=self.save_preset).grid(row=2, column=0, padx=5, pady=5, sticky="ew")
        ttk.Button(preset_frame, text="Delete Preset", command=self.delete_preset).grid(row=2, column=1, padx=5, pady=5, sticky="ew")
        
        # Process button
        ttk.Button(main_frame, text="Process Video", command=self.process_video).grid(row=3, column=0, columnspan=2, padx=5, pady=10, sticky="ew")
        
        # Subtitle settings frame
        subtitle_frame = ttk.LabelFrame(main_frame, text="Subtitle Settings", padding="5")
        subtitle_frame.grid(row=4, column=0, columnspan=2, padx=5, pady=5, sticky="nsew")
        
        self.setup_subtitle_frame(subtitle_frame)
        
        # Thêm tab batch processing
        self.setup_batch_processing_tab(self.notebook)
        
    def setup_batch_processing_tab(self, notebook):
        """Setup batch processing tab"""
        # Tạo tab mới
        self.batch_tab = ttk.Frame(notebook)
        notebook.add(self.batch_tab, text="Batch Processing")

        # Frame chọn thư mục input
        input_frame = ttk.LabelFrame(self.batch_tab, text="Input Folder")
        input_frame.pack(padx=10, pady=10, fill='x')

        # Biến lưu đường dẫn thư mục input
        self.batch_input_dir = tk.StringVar()
        
        # Ô nhập và nút browse thư mục input
        input_entry = ttk.Entry(input_frame, textvariable=self.batch_input_dir, width=50)
        input_entry.pack(side='left', padx=5, pady=5, expand=True, fill='x')
        
        input_browse_btn = ttk.Button(
            input_frame, 
            text="Browse", 
            command=lambda: self.browse_folder(self.batch_input_dir)
        )
        input_browse_btn.pack(side='right', padx=5, pady=5)

        # Frame chọn thư mục output
        output_frame = ttk.LabelFrame(self.batch_tab, text="Output Folder")
        output_frame.pack(padx=10, pady=10, fill='x')

        # Biến lưu đường dẫn thư mục output
        self.batch_output_dir = tk.StringVar(value=str(Path.cwd() / 'final'))
        
        # Ô nhập và nút browse thư mục output
        output_entry = ttk.Entry(output_frame, textvariable=self.batch_output_dir, width=50)
        output_entry.pack(side='left', padx=5, pady=5, expand=True, fill='x')
        
        output_browse_btn = ttk.Button(
            output_frame, 
            text="Browse", 
            command=lambda: self.browse_folder(self.batch_output_dir)
        )
        output_browse_btn.pack(side='right', padx=5, pady=5)

        # Frame tiến trình và nút xử lý
        process_frame = ttk.Frame(self.batch_tab)
        process_frame.pack(padx=10, pady=10, fill='x')

        # Nút bắt đầu xử lý batch
        process_btn = ttk.Button(
            process_frame, 
            text="Start Batch Processing", 
            command=self.start_batch_processing
        )
        process_btn.pack(expand=True, fill='x')

        # Thanh tiến trình
        self.batch_progress = ttk.Progressbar(
            process_frame, 
            orient='horizontal', 
            length=100, 
            mode='determinate'
        )
        self.batch_progress.pack(fill='x', pady=5)

        # Text widget để hiển thị log
        self.batch_log = tk.Text(self.batch_tab, height=10, state='disabled')
        self.batch_log.pack(padx=10, pady=10, expand=True, fill='both')

    def browse_folder(self, var):
        """Browse and select folder"""
        folder_selected = filedialog.askdirectory()
        if folder_selected:
            var.set(folder_selected)

    def start_batch_processing(self):
        """Bắt đầu xử lý batch"""
        try:
            # Lấy thư mục input và output
            input_dir = Path(self.batch_input_dir.get())
            output_dir = Path(self.batch_output_dir.get())

            # Kiểm tra thư mục input
            if not input_dir.is_dir():
                messagebox.showerror("Error", "Invalid input directory")
                return

            # Tìm các file phù hợp
            matching_files = self.find_matching_batch_files(input_dir)

            # Kiểm tra có file để xử lý không
            if not matching_files:
                messagebox.showinfo("Info", "No matching files found in the input directory")
                return

            # Chuẩn bị xử lý
            self.batch_progress['maximum'] = len(matching_files)
            self.batch_progress['value'] = 0
            self.clear_batch_log()

            # Xử lý từng nhóm file
            for file_group in matching_files:
                try:
                    # Tạo tên file output
                    output_filename = f"{file_group['thumbnail'].stem.replace('_hook', '')}_{int(time.time())}.mp4"
                    output_path = output_dir / output_filename

                    # Xử lý video
                    self.video_processor.process_hook_video(
                        hook_audio=file_group['hook_audio'],
                        audio_path=file_group['main_audio'],
                        thumbnail_path=file_group['thumbnail'],
                        subtitle_path=file_group['subtitle'],
                        output_path=output_path,
                        subtitle_settings=self.subtitle_settings
                    )

                    # Cập nhật log và progress
                    self.update_batch_log(f"Processed: {output_filename}")
                    self.batch_progress['value'] += 1
                    self.root.update_idletasks()

                except Exception as e:
                    self.update_batch_log(f"Error processing {file_group['thumbnail'].name}: {str(e)}")

            # Hoàn thành
            messagebox.showinfo("Batch Processing", "Batch processing completed!")

        except Exception as e:
            messagebox.showerror("Error", f"Batch processing failed: {str(e)}")

    def find_matching_batch_files(self, folder_path: Path) -> List[Dict[str, Path]]:
        """
        Tìm các file khớp nhau trong thư mục
        
        Args:
            folder_path (Path): Đường dẫn thư mục
        
        Returns:
            List[Dict[str, Path]]: Danh sách các nhóm file khớp
        """
        # Chuyển đổi tất cả các file về lowercase để so sánh
        all_files = [f for f in folder_path.iterdir() if f.is_file()]
        
        # Nhóm file theo tên gốc
        file_groups = {}
        
        for file in all_files:
            # Tách tên file và phần mở rộng
            stem = file.stem.lower()
            
            # Loại bỏ các hậu tố đặc biệt để lấy tên gốc
            for suffix in ['_hook', '_audio']:
                if stem.endswith(suffix):
                    stem = stem[:-len(suffix)]
            
            # Tạo nhóm nếu chưa tồn tại
            if stem not in file_groups:
                file_groups[stem] = {}
            
            # Phân loại file
            if '_hook.png' in file.name.lower():
                file_groups[stem]['thumbnail'] = file
            elif '_hook.wav' in file.name.lower() or '_hook.mp3' in file.name.lower():
                file_groups[stem]['hook_audio'] = file
            elif '_audio.wav' in file.name.lower() or '_audio.mp3' in file.name.lower():
                file_groups[stem]['main_audio'] = file
            elif file.suffix.lower() in ['.srt', '.ass']:
                file_groups[stem]['subtitle'] = file
        
        # Lọc các bộ file đầy đủ
        complete_groups = []
        for name, group in file_groups.items():
            # Kiểm tra xem nhóm có đủ các file cần thiết không
            if len(group) >= 4:  # thumbnail, hook_audio, main_audio, subtitle
                complete_groups.append(group)
        
        return complete_groups

    def update_batch_log(self, message):
        """Cập nhật log trong batch processing"""
        self.batch_log.configure(state='normal')
        self.batch_log.insert(tk.END, message + "\n")
        self.batch_log.see(tk.END)
        self.batch_log.configure(state='disabled')

    def clear_batch_log(self):
        """Xóa sạch log"""
        self.batch_log.configure(state='normal')
        self.batch_log.delete('1.0', tk.END)
        self.batch_log.configure(state='disabled')

    def get_system_fonts(self):
        """Get list of installed fonts"""
        try:
            # Danh sách font mặc định
            default_fonts = ["Arial", "Times New Roman", "Calibri", "Verdana", "Tahoma"]

            # Đường dẫn registry chứa font
            font_paths = [
                (winreg.HKEY_LOCAL_MACHINE, r'SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts'),
                (winreg.HKEY_LOCAL_MACHINE, r'SOFTWARE\Microsoft\Windows\CurrentVersion\Fonts'),
                (winreg.HKEY_CURRENT_USER, r'SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts'),
                (winreg.HKEY_CURRENT_USER, r'SOFTWARE\Microsoft\Windows\CurrentVersion\Fonts')
            ]

            installed_fonts = set()

            for hkey, path in font_paths:
                try:
                    # Mở registry key
                    key = winreg.OpenKey(hkey, path)
                    
                    # Đếm số lượng giá trị trong key
                    num_values = winreg.QueryInfoKey(key)[1]
                    
                    # Lặp qua các giá trị
                    for i in range(num_values):
                        try:
                            name, data, _ = winreg.EnumValue(key, i)
                            # Loại bỏ phần mở rộng và (TrueType)
                            clean_name = name.replace(' (TrueType)', '').replace(' (OpenType)', '').replace(' (Italic)', '')
                            installed_fonts.add(clean_name)
                        except Exception as e:
                            logging.debug(f"Error reading font registry value: {e}")
                    
                    winreg.CloseKey(key)
                except FileNotFoundError:
                    logging.debug(f"Font registry path not found: {path}")
                except PermissionError:
                    logging.debug(f"Permission denied for registry path: {path}")
                except Exception as e:
                    logging.debug(f"Error accessing font registry path {path}: {e}")

            # Thêm một số font phổ biến khác
            additional_fonts = [
                "Segoe UI", "Microsoft Sans Serif", "Consolas", 
                "Courier New", "Georgia", "Palatino Linotype"
            ]
            
            # Kết hợp font mặc định, font từ hệ thống và font bổ sung
            all_fonts = list(set(default_fonts + list(installed_fonts) + additional_fonts))
            
            return sorted(all_fonts)

        except Exception as e:
            logging.error(f"Unexpected error getting system fonts: {e}")
            return default_fonts

    def setup_subtitle_frame(self, subtitle_frame):
        """Setup subtitle settings frame"""
        # Font settings
        font_frame = ttk.Frame(subtitle_frame)
        font_frame.pack(fill="x", padx=5, pady=5)
        
        ttk.Label(font_frame, text="Font:").pack(side="left")
        font_combo = ttk.Combobox(font_frame, textvariable=self.font_var)
        font_combo['values'] = self.get_system_fonts()
        font_combo.pack(side="left", padx=5)
        
        ttk.Label(font_frame, text="Size:").pack(side="left", padx=(10,0))
        ttk.Entry(font_frame, textvariable=self.font_size_var, width=5).pack(side="left", padx=5)

        # Color settings
        color_frame = ttk.Frame(subtitle_frame)
        color_frame.pack(fill="x", padx=5, pady=5)
        
        # Text color
        text_color_frame = ttk.Frame(color_frame)
        text_color_frame.pack(side="left", padx=5)
        ttk.Label(text_color_frame, text="Text:").pack(side="left")
        text_color_entry = ttk.Entry(text_color_frame, textvariable=self.primary_color_var, width=10)
        text_color_entry.pack(side="left", padx=2)
        ttk.Button(text_color_frame, text="Pick", 
                  command=lambda: self.pick_color(self.primary_color_var)).pack(side="left")
        
        # Outline color
        outline_color_frame = ttk.Frame(color_frame)
        outline_color_frame.pack(side="left", padx=5)
        ttk.Label(outline_color_frame, text="Outline:").pack(side="left")
        outline_color_entry = ttk.Entry(outline_color_frame, textvariable=self.outline_color_var, width=10)
        outline_color_entry.pack(side="left", padx=2)
        ttk.Button(outline_color_frame, text="Pick", 
                  command=lambda: self.pick_color(self.outline_color_var)).pack(side="left")
        
        # Background color
        back_color_frame = ttk.Frame(color_frame)
        back_color_frame.pack(side="left", padx=5)
        ttk.Label(back_color_frame, text="Background:").pack(side="left")
        back_color_entry = ttk.Entry(back_color_frame, textvariable=self.back_color_var, width=10)
        back_color_entry.pack(side="left", padx=2)
        ttk.Button(back_color_frame, text="Pick", 
                  command=lambda: self.pick_color(self.back_color_var)).pack(side="left")

        # Style settings
        style_frame = ttk.Frame(subtitle_frame)
        style_frame.pack(fill="x", padx=5, pady=5)
        
        ttk.Label(style_frame, text="Outline:").pack(side="left")
        ttk.Entry(style_frame, textvariable=self.outline_var, width=5).pack(side="left", padx=5)
        
        ttk.Label(style_frame, text="Shadow:").pack(side="left", padx=(10,0))
        ttk.Entry(style_frame, textvariable=self.shadow_var, width=5).pack(side="left", padx=5)

        # Margin settings
        margin_frame = ttk.Frame(subtitle_frame)
        margin_frame.pack(fill="x", padx=5, pady=5)
        
        ttk.Label(margin_frame, text="V-Margin:").pack(side="left")
        ttk.Entry(margin_frame, textvariable=self.margin_v_var, width=5).pack(side="left", padx=5)
        
        ttk.Label(margin_frame, text="H-Margin:").pack(side="left", padx=(10,0))
        ttk.Entry(margin_frame, textvariable=self.margin_h_var, width=5).pack(side="left", padx=5)

        # Alignment and max chars
        align_frame = ttk.Frame(subtitle_frame)
        align_frame.pack(fill="x", padx=5, pady=5)
        
        ttk.Label(align_frame, text="Alignment:").pack(side="left")
        align_combo = ttk.Combobox(align_frame, textvariable=self.alignment_var, width=5)
        align_combo['values'] = list(range(1, 10))
        align_combo.pack(side="left", padx=5)
        
        ttk.Label(align_frame, text="Max chars:").pack(side="left", padx=(10,0))
        ttk.Entry(align_frame, textvariable=self.max_chars_var, width=5).pack(side="left", padx=5)
    
    def browse_file(self, var, filetypes):
        """Open file browser and update the variable with selected path"""
        if 'hook' in str(var):
            filetypes = [('Audio files', '*.mp3;*.wav')]
        elif 'audio' in str(var):
            filetypes = [('Audio files', '*.mp3;*.wav')]
        elif 'subtitle' in str(var):
            filetypes = [('Subtitle files', '*.srt')]
        elif 'thumbnail' in str(var):
            filetypes = [('Image files', '*.png')]
            
        filename = filedialog.askopenfilename(filetypes=filetypes)
        if filename:
            var.set(filename)
    
    def pick_color(self, color_var):
        """Open color picker and update color variable"""
        try:
            # Get current color
            current = self.hex_to_rgb(color_var.get())
            
            # Open color picker
            color = colorchooser.askcolor(color=current)
            if color[1]:  # color is ((r,g,b), hex)
                # Convert RGB to ASS format
                ass_color = self.rgb_to_ass(color[0])
                color_var.set(ass_color)
                logging.debug(f"Selected color: {ass_color}")
        except Exception as e:
            logging.error(f"Error picking color: {e}")
            messagebox.showerror("Error", f"Failed to pick color: {e}")

    def hex_to_rgb(self, ass_color):
        """Convert ASS color format to RGB"""
        try:
            # Remove &H and & from ASS color
            hex_color = ass_color.replace('&H', '').replace('&', '')
            # Convert BGR to RGB
            b = int(hex_color[0:2], 16)
            g = int(hex_color[2:4], 16)
            r = int(hex_color[4:6], 16)
            return (r, g, b)
        except:
            return (255, 255, 255)  # Default to white on error

    def rgb_to_ass(self, rgb):
        """Convert RGB to ASS color format"""
        r, g, b = [int(x) for x in rgb]
        return f"&H{b:02X}{g:02X}{r:02X}&"

    def init_settings_manager(self):
        """Initialize settings manager and load presets"""
        self.settings_manager = SettingsManager(self.base_path)
        self.update_preset_list()

    def update_preset_list(self):
        """Update preset list in combobox"""
        presets = self.settings_manager.get_preset_names()
        self.preset_combo['values'] = presets

    def save_preset(self):
        """Save current settings as new preset"""
        name = self.new_preset_var.get().strip()
        if not name:
            messagebox.showerror("Error", "Please enter a preset name")
            return
            
        # Get current settings
        settings = {
            'font_name': self.font_var.get(),
            'font_size': self.font_size_var.get(),
            'primary_color': self.primary_color_var.get(),
            'outline_color': self.outline_color_var.get(),
            'back_color': self.back_color_var.get(),
            'outline': self.outline_var.get(),
            'shadow': self.shadow_var.get(),
            'margin_v': self.margin_v_var.get(),
            'margin_h': self.margin_h_var.get(),
            'alignment': self.alignment_var.get(),
            'max_chars': self.max_chars_var.get()
        }
        
        try:
            self.settings_manager.save_preset(name, settings)
            self.update_preset_list()
            self.preset_var.set(name)  # Select the new preset
            messagebox.showinfo("Success", f"Preset '{name}' saved successfully")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save preset: {str(e)}")

    def load_selected_preset(self, event=None):
        """Load selected preset settings"""
        name = self.preset_var.get()
        if not name:
            return
            
        try:
            settings = self.settings_manager.load_preset(name)
            # Update GUI with preset settings
            self.font_var.set(settings.get('font_name', 'Arial'))
            self.font_size_var.set(str(settings.get('font_size', '48')))
            self.primary_color_var.set(settings.get('primary_color', '&HFFFFFF&'))
            self.outline_color_var.set(settings.get('outline_color', '&H000000&'))
            self.back_color_var.set(settings.get('back_color', '&H000000&'))
            self.outline_var.set(str(settings.get('outline', '2')))
            self.shadow_var.set(str(settings.get('shadow', '0')))
            self.margin_v_var.set(str(settings.get('margin_v', '20')))
            self.margin_h_var.set(str(settings.get('margin_h', '20')))
            self.alignment_var.set(str(settings.get('alignment', '2')))
            self.max_chars_var.set(str(settings.get('max_chars', '40')))
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load preset: {str(e)}")

    def delete_preset(self):
        """Delete selected preset"""
        name = self.preset_var.get()
        if not name:
            messagebox.showerror("Error", "Please select a preset to delete")
            return
            
        if messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete preset '{name}'?"):
            try:
                self.settings_manager.delete_preset(name)
                self.update_preset_list()
                self.preset_var.set('')  # Clear selection
                messagebox.showinfo("Success", f"Preset '{name}' deleted successfully")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to delete preset: {str(e)}")
    
    def update_subtitle_settings(self):
        """Update subtitle settings from UI values"""
        self.subtitle_settings = {
            'font_name': self.font_var.get(),
            'font_size': int(self.font_size_var.get() or 48),
            'primary_color': self.primary_color_var.get(),
            'outline_color': self.outline_color_var.get(),
            'back_color': self.back_color_var.get(),
            'outline': int(self.outline_var.get() or 2),
            'shadow': int(self.shadow_var.get() or 0),
            'margin_v': int(self.margin_v_var.get() or 20),
            'margin_h': int(self.margin_h_var.get() or 20),
            'alignment': int(self.alignment_var.get() or 2),
            'max_chars': int(self.max_chars_var.get() or 40)
        }
        logging.info(f"Updated subtitle settings: {self.subtitle_settings}")
        return self.subtitle_settings

    def process_video(self):
        """Process video with current settings"""
        try:
            # Validate inputs
            if not all([self.hook_path_var.get(), self.audio_path_var.get(), 
                       self.subtitle_path.get(), self.thumbnail_path.get()]):
                messagebox.showerror("Error", "Please select all required files")
                return
            
            # Update subtitle settings
            self.update_subtitle_settings()
            
            # Get audio filename without extension for output
            audio_path = Path(self.audio_path_var.get())
            output_filename = f"{audio_path.stem}_{int(time.time())}.mp4"
            output_path = self.final_dir / output_filename
            
            self.video_processor.process_hook_video(
                hook_audio=Path(self.hook_path_var.get()),
                audio_path=Path(self.audio_path_var.get()),
                thumbnail_path=Path(self.thumbnail_path.get()),
                subtitle_path=Path(self.subtitle_path.get()),
                output_path=output_path,
                subtitle_settings=self.subtitle_settings
            )
            
            messagebox.showinfo("Success", f"Video processing completed!\nOutput: {output_filename}")
            
        except Exception as e:
            logging.error(f"Error processing video: {str(e)}")
            messagebox.showerror("Error", f"Failed to process video: {str(e)}")

if __name__ == '__main__':
    # Setup logging
    logging.basicConfig(level=logging.DEBUG,
                       format='%(asctime)s - %(levelname)s - %(message)s')
    
    # Create and run GUI
    root = tk.Tk()
    app = HookMakerGUI(root)
    root.mainloop()
