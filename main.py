import numpy as np
from PIL import Image, ImageTk
import requests
from io import BytesIO
import os
import json
import glob
import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext
import threading
import time
import cv2
from pathlib import Path
import platform
import subprocess

class VideoStreamProcessor:
    def __init__(self, converter_core):
        self.converter = converter_core
        self.cap = None
        self.processing = False
        self.current_frame = 0
        self.total_frames = 0
        self.frame_cache = {}
        self.current_settings_hash = ""
        
    def open_video(self, video_path):
        if self.cap:
            self.cap.release()
            
        self.cap = cv2.VideoCapture(video_path)
        if not self.cap.isOpened():
            return False
            
        self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.current_frame = 0
        self.frame_cache = {}
        return True
    
    def _get_settings_hash(self, settings):
        return str(sorted(settings.items()))
    
    def get_frame(self, frame_num, settings):
        settings_hash = self._get_settings_hash(settings)
        
        cache_key = f"{frame_num}_{settings_hash}"
        if cache_key in self.frame_cache:
            return self.frame_cache[cache_key]
        
        if not self.cap:
            return None
            
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, frame_num)
        ret, frame = self.cap.read()
        
        if not ret:
            return None
        
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        pil_image = Image.fromarray(frame_rgb)
        
        self.converter.set_config(**settings)
        result = self.converter._process_pil_image(pil_image)
        
        self.frame_cache[cache_key] = result
        if len(self.frame_cache) > 100:
            self.frame_cache.pop(next(iter(self.frame_cache)))
        
        return result
    
    def close(self):
        if self.cap:
            self.cap.release()
            self.cap = None

class CrossPlatformCamera:
    @staticmethod
    def detect_cameras():
        system = platform.system().lower()
        
        if system == "linux":
            return CrossPlatformCamera._detect_linux_cameras()
        elif system == "windows":
            return CrossPlatformCamera._detect_windows_cameras()
        elif system == "darwin":
            return CrossPlatformCamera._detect_macos_cameras()
        else:
            return CrossPlatformCamera._detect_fallback_cameras()
    
    @staticmethod
    def _detect_linux_cameras():
        cameras = []
        
        try:
            result = subprocess.run(['v4l2-ctl', '--list-devices'], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                lines = result.stdout.split('\n')
                for i, line in enumerate(lines):
                    if '/dev/video' in line:
                        cam_path = line.strip()
                        if os.path.exists(cam_path):
                            cap = cv2.VideoCapture(cam_path)
                            if cap.isOpened():
                                ret, frame = cap.read()
                                if ret:
                                    cameras.append(cam_path)
                                cap.release()
        except:
            pass
        
        if not cameras:
            cameras = CrossPlatformCamera._detect_fallback_cameras()
            
        return cameras
    
    @staticmethod
    def _detect_windows_cameras():
        cameras = []
        for i in range(10):
            try:
                cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
                if cap.isOpened():
                    ret, frame = cap.read()
                    if ret:
                        cameras.append(i)
                    cap.release()
            except:
                continue
        return cameras if cameras else [0]
    
    @staticmethod
    def _detect_macos_cameras():
        cameras = []
        for i in range(10):
            try:
                cap = cv2.VideoCapture(i)
                if cap.isOpened():
                    ret, frame = cap.read()
                    if ret:
                        cameras.append(i)
                    cap.release()
            except:
                continue
        return cameras if cameras else [0]
    
    @staticmethod
    def _detect_fallback_cameras():
        cameras = []
        for i in range(5):
            try:
                cap = cv2.VideoCapture(i)
                if cap.isOpened():
                    ret, frame = cap.read()
                    if ret:
                        cameras.append(i)
                    cap.release()
            except:
                continue
        return cameras if cameras else [0]

class ConverterCore:
    def __init__(self, config_file=None):
        if config_file is None:
            config_file = self.get_default_config_path()
        
        self.config_file = config_file
        self.default_config = {
            'width': 100,
            'height': None,
            'charset': " .,-=+*#%@",
            'charset_slot1': " .,-=+*#%@",
            'charset_slot2': " .:-=+*#%@",
            'charset_slot3': " ░▒▓█",
            'active_slot': 1,
            'invert': False,
            'brightness': 1.0,
            'contrast': 1.0,
            'line_spacing': 0.55,
            'last_image': None,
            'image_width': 80,
            'image_brightness': 1.0,
            'image_contrast': 1.0,
            'image_invert': False,
            'image_spacing': 0.55,
            'video_width': 80,
            'video_sampling': 1,
            'video_brightness': 1.0,
            'video_contrast': 1.0,
            'video_invert': False,
            'video_spacing': 0.55,
            'video_max_frames': 0,
            'webcam_width': 80,
            'webcam_frame_skip': 2,
            'webcam_brightness': 1.0,
            'webcam_contrast': 1.0,
            'webcam_invert': False,
            'webcam_spacing': 0.55,
            'webcam_mirror': True
        }
        self.config = self.load_config()
        self.video_result = None
        self.video_processor = VideoStreamProcessor(self)
    
    def get_default_config_path(self):
        system = platform.system().lower()
        
        if system == "windows":
            config_dir = os.path.join(os.environ['APPDATA'], 'ascii-convert')
        elif system == "darwin":
            config_dir = os.path.expanduser('~/Library/Application Support/ascii-convert')
        else:
            config_dir = os.path.expanduser('~/.config/ascii-convert')
        
        os.makedirs(config_dir, exist_ok=True)
        return os.path.join(config_dir, "config.json")
    
    def load_config(self):
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    for key, value in self.default_config.items():
                        if key not in config:
                            config[key] = value
                    return config
            return self.default_config.copy()
        except Exception as e:
            return self.default_config.copy()
    
    def save_config(self):
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=4, ensure_ascii=False)
        except Exception:
            pass
    
    def set_config(self, **kwargs):
        for key, value in kwargs.items():
            if key in self.config:
                self.config[key] = value
        self.save_config()
    
    def load_image(self, image_path):
        try:
            if image_path.startswith(('http://', 'https://')):
                response = requests.get(image_path)
                self.image = Image.open(BytesIO(response.content))
            else:
                self.image = Image.open(image_path)
                self.config['last_image'] = image_path
                self.save_config()
            return True
        except Exception:
            return False
    
    def preprocess_image(self):
        if not hasattr(self, 'image'):
            raise ValueError("No image loaded")
        
        grayscale = self.image.convert('L')
        orig_w, orig_h = grayscale.size
        
        if self.config['height'] is None:
            aspect = orig_h / orig_w
            height = int(self.config['width'] * aspect * self.config['line_spacing'])
        else:
            height = self.config['height']
        
        self.processed_image = grayscale.resize((self.config['width'], height))
        return self.processed_image
    
    def apply_adjustments(self, pixels):
        pixels = np.clip(pixels * self.config['brightness'], 0, 255)
        mean = np.mean(pixels)
        pixels = np.clip((pixels - mean) * self.config['contrast'] + mean, 0, 255)
        if self.config['invert']:
            pixels = 255 - pixels
        return pixels
    
    def convert_to_text(self):
        if not hasattr(self, 'processed_image'):
            raise ValueError("Image not processed")
        
        pixels = np.array(self.processed_image)
        pixels = self.apply_adjustments(pixels)
        charset_len = len(self.config['charset'])
        normalized = np.clip((pixels / 255.0 * (charset_len - 1)), 0, charset_len - 1).astype(int)
        
        result = []
        for row in normalized:
            text_row = ''.join(self.config['charset'][pixel] for pixel in row)
            result.append(text_row)
        
        self.text_result = '\n'.join(result)
        return self.text_result
    
    def save_text(self, filename=None):
        if not hasattr(self, 'text_result'):
            raise ValueError("No text to save")
        
        if filename is None:
            base = "output"
            counter = 1
            filename = f"{base}.txt"
            while os.path.exists(filename):
                filename = f"{base}_{counter}.txt"
                counter += 1
        
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(self.text_result)
        return filename
    
    def process(self, image_path=None):
        if image_path is None:
            return None
        
        if not self.load_image(image_path):
            return None
        
        self.preprocess_image()
        return self.convert_to_text()

    def process_video(self, video_path, frame_sampling=1, max_frames=0, progress_callback=None):
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise ValueError("Cannot open video")
        
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if max_frames > 0:
            total_frames = min(total_frames, max_frames * frame_sampling)
        
        frames = []
        processed = 0
        target = total_frames // frame_sampling
        
        for frame_num in range(0, total_frames, frame_sampling):
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_num)
            ret, frame = cap.read()
            
            if not ret:
                break
            
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            pil_image = Image.fromarray(frame_rgb)
            
            text_frame = self._process_pil_image(pil_image)
            frames.append(text_frame)
            processed += 1
            
            if progress_callback:
                progress_callback(processed, target)
        
        cap.release()
        
        self.video_result = "\n\n".join(frames)
        
        return {
            'frames': frames,
            'processed': processed,
            'total': total_frames
        }
    
    def _process_pil_image(self, pil_image):
        self.image = pil_image
        self.preprocess_image()
        return self.convert_to_text()
    
    def save_video_text(self, filename=None):
        if not self.video_result:
            raise ValueError("No video text to save")
        
        if filename is None:
            base = "video_output"
            counter = 1
            filename = f"{base}.txt"
            while os.path.exists(filename):
                filename = f"{base}_{counter}.txt"
                counter += 1
        
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(self.video_result)
        return filename

class MainApplication:
    def __init__(self, root):
        self.root = root
        self.root.title("Art Converter Pro")
        self.root.geometry("1400x900")
        
        self.converter = ConverterCore()
        
        self.image_path = tk.StringVar()
        self.video_path = tk.StringVar()
        self.text_display = None
        self.current_video_frames = []
        self.current_frame_index = 0
        self.video_playing = False
        self.video_fps = 30
        self.playback_delay = 33
        
        self.cap = None
        self.webcam_running = False
        self.current_frame = None
        self.live_output = None
        
        self.conversion_timer = None
        self.last_conversion_time = 0
        self.video_conversion_timer = None
        self.last_video_conversion_time = 0
        
        self.charset_slot1 = tk.StringVar(value=self.converter.config['charset_slot1'])
        self.charset_slot2 = tk.StringVar(value=self.converter.config['charset_slot2'])
        self.charset_slot3 = tk.StringVar(value=self.converter.config['charset_slot3'])
        self.active_slot = tk.IntVar(value=self.converter.config['active_slot'])
        
        self.video_stream_active = False
        
        self.setup_gui()
        self.update_active_charset()
        self.load_settings_from_config()
        
    def setup_gui(self):
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill='both', expand=True, padx=10, pady=10)
        
        self.image_frame = ttk.Frame(self.notebook)
        self.video_frame = ttk.Frame(self.notebook)
        self.webcam_frame = ttk.Frame(self.notebook)
        
        self.notebook.add(self.image_frame, text='🖼️ Images')
        self.notebook.add(self.video_frame, text='🎥 Videos') 
        self.notebook.add(self.webcam_frame, text='📹 Webcam')
        
        self.setup_image_tab()
        self.setup_video_tab()
        self.setup_webcam_tab()
        
    def setup_image_tab(self):
        main_paned = ttk.PanedWindow(self.image_frame, orient='horizontal')
        main_paned.pack(fill='both', expand=True, padx=5, pady=5)
        
        left_frame = ttk.Frame(main_paned)
        right_frame = ttk.Frame(main_paned)
        
        self.setup_image_controls(left_frame)
        self.setup_image_output(right_frame)
        
        main_paned.add(left_frame, weight=1)
        main_paned.add(right_frame, weight=2)
    
    def setup_image_controls(self, parent):
        file_frame = ttk.LabelFrame(parent, text="Image File")
        file_frame.pack(fill='x', padx=5, pady=5)
        
        path_frame = ttk.Frame(file_frame)
        path_frame.pack(fill='x', padx=10, pady=5)
        
        ttk.Label(path_frame, text="Path:").pack(side='left')
        ttk.Entry(path_frame, textvariable=self.image_path, width=50).pack(side='left', fill='x', expand=True, padx=5)
        ttk.Button(path_frame, text="📷", command=self.load_last_image, width=3).pack(side='left', padx=2)
        ttk.Button(path_frame, text="Browse", command=self.browse_image).pack(side='left', padx=5)
        
        settings_frame = ttk.LabelFrame(parent, text="Image Settings")
        settings_frame.pack(fill='both', expand=True, padx=5, pady=5)
        
        self.setup_character_slots(settings_frame)
        
        size_frame = ttk.Frame(settings_frame)
        size_frame.pack(fill='x', padx=10, pady=5)
        
        ttk.Label(size_frame, text="Width:").pack(side='left')
        self.image_width = tk.IntVar(value=80)
        width_spinbox = ttk.Spinbox(size_frame, from_=10, to=500, textvariable=self.image_width, width=8)
        width_spinbox.pack(side='left', padx=5)
        width_spinbox.bind('<<Increment>>', lambda e: self.schedule_image_conversion())
        width_spinbox.bind('<<Decrement>>', lambda e: self.schedule_image_conversion())
        width_spinbox.bind('<KeyRelease>', lambda e: self.schedule_image_conversion())
        
        ttk.Label(size_frame, text="Line spacing:").pack(side='left', padx=(20,0))
        self.image_spacing = tk.DoubleVar(value=0.55)
        spacing_spinbox = ttk.Spinbox(size_frame, from_=0.1, to=2.0, increment=0.05, textvariable=self.image_spacing, width=6)
        spacing_spinbox.pack(side='left', padx=5)
        spacing_spinbox.bind('<<Increment>>', lambda e: self.schedule_image_conversion())
        spacing_spinbox.bind('<<Decrement>>', lambda e: self.schedule_image_conversion())
        spacing_spinbox.bind('<KeyRelease>', lambda e: self.schedule_image_conversion())
        
        adjust_frame = ttk.Frame(settings_frame)
        adjust_frame.pack(fill='x', padx=10, pady=5)
        
        ttk.Label(adjust_frame, text="Brightness:").pack(side='left')
        self.image_brightness = tk.DoubleVar(value=1.0)
        brightness_spinbox = ttk.Spinbox(adjust_frame, from_=0.1, to=3.0, increment=0.1, 
                   textvariable=self.image_brightness, width=6)
        brightness_spinbox.pack(side='left', padx=5)
        brightness_spinbox.bind('<<Increment>>', lambda e: self.schedule_image_conversion())
        brightness_spinbox.bind('<<Decrement>>', lambda e: self.schedule_image_conversion())
        brightness_spinbox.bind('<KeyRelease>', lambda e: self.schedule_image_conversion())
        
        ttk.Label(adjust_frame, text="Contrast:").pack(side='left')
        self.image_contrast = tk.DoubleVar(value=1.0)
        contrast_spinbox = ttk.Spinbox(adjust_frame, from_=0.1, to=3.0, increment=0.1,
                   textvariable=self.image_contrast, width=6)
        contrast_spinbox.pack(side='left', padx=5)
        contrast_spinbox.bind('<<Increment>>', lambda e: self.schedule_image_conversion())
        contrast_spinbox.bind('<<Decrement>>', lambda e: self.schedule_image_conversion())
        contrast_spinbox.bind('<KeyRelease>', lambda e: self.schedule_image_conversion())
        
        self.image_invert = tk.BooleanVar(value=False)
        invert_cb = ttk.Checkbutton(settings_frame, text="Invert colors", variable=self.image_invert,
                                  command=self.schedule_image_conversion)
        invert_cb.pack(anchor='w', padx=10, pady=2)
        
        button_frame = ttk.Frame(settings_frame)
        button_frame.pack(fill='x', padx=10, pady=10)
        
        ttk.Button(button_frame, text="🎬 Convert", command=self.start_image_conversion).pack(side='left', padx=5)
        ttk.Button(button_frame, text="🔄 Reset", command=self.reset_image_settings).pack(side='left', padx=5)
    
    def setup_character_slots(self, parent):
        charset_frame = ttk.LabelFrame(parent, text="Character Slots")
        charset_frame.pack(fill='x', padx=10, pady=5)
        
        slot1_frame = ttk.Frame(charset_frame)
        slot1_frame.pack(fill='x', padx=5, pady=2)
        ttk.Label(slot1_frame, text="Slot 1:").pack(side='left')
        slot1_entry = ttk.Entry(slot1_frame, textvariable=self.charset_slot1, width=40)
        slot1_entry.pack(side='left', fill='x', expand=True, padx=5)
        slot1_entry.bind('<KeyRelease>', lambda e: self.on_charset_change())
        
        slot2_frame = ttk.Frame(charset_frame)
        slot2_frame.pack(fill='x', padx=5, pady=2)
        ttk.Label(slot2_frame, text="Slot 2:").pack(side='left')
        slot2_entry = ttk.Entry(slot2_frame, textvariable=self.charset_slot2, width=40)
        slot2_entry.pack(side='left', fill='x', expand=True, padx=5)
        slot2_entry.bind('<KeyRelease>', lambda e: self.on_charset_change())
        
        slot3_frame = ttk.Frame(charset_frame)
        slot3_frame.pack(fill='x', padx=5, pady=2)
        ttk.Label(slot3_frame, text="Slot 3:").pack(side='left')
        slot3_entry = ttk.Entry(slot3_frame, textvariable=self.charset_slot3, width=40)
        slot3_entry.pack(side='left', fill='x', expand=True, padx=5)
        slot3_entry.bind('<KeyRelease>', lambda e: self.on_charset_change())
        
        slot_select_frame = ttk.Frame(charset_frame)
        slot_select_frame.pack(fill='x', padx=5, pady=5)
        
        ttk.Radiobutton(slot_select_frame, text="Slot 1", variable=self.active_slot, value=1, 
                       command=self.on_slot_change).pack(side='left', padx=5)
        ttk.Radiobutton(slot_select_frame, text="Slot 2", variable=self.active_slot, value=2,
                       command=self.on_slot_change).pack(side='left', padx=5)
        ttk.Radiobutton(slot_select_frame, text="Slot 3", variable=self.active_slot, value=3,
                       command=self.on_slot_change).pack(side='left', padx=5)
    
    def setup_image_output(self, parent):
        result_frame = ttk.LabelFrame(parent, text="Output")
        result_frame.pack(fill='both', expand=True, padx=5, pady=5)
        
        result_controls = ttk.Frame(result_frame)
        result_controls.pack(fill='x', pady=5)
        
        ttk.Button(result_controls, text="Copy", command=self.copy_image_text).pack(side='right', padx=5)
        ttk.Button(result_controls, text="Clear", command=self.clear_image_text).pack(side='right', padx=5)
        ttk.Button(result_controls, text="💾 Save", command=self.save_image_text).pack(side='right', padx=5)
        
        self.image_output = scrolledtext.ScrolledText(
            result_frame, 
            font=('Courier New', 8),
            bg='black', 
            fg='white',
            wrap='none'
        )
        self.image_output.pack(fill='both', expand=True, padx=5, pady=5)
        
        self.image_progress = ttk.Progressbar(result_frame, mode='indeterminate')
        self.image_progress.pack(fill='x', pady=5)
        
        self.image_status = tk.StringVar(value="Ready")
        status_bar = ttk.Label(result_frame, textvariable=self.image_status)
        status_bar.pack(fill='x', pady=5)
        
        self.image_output.bind('<Configure>', self.on_image_output_resize)
    
    def setup_video_tab(self):
        main_paned = ttk.PanedWindow(self.video_frame, orient='horizontal')
        main_paned.pack(fill='both', expand=True, padx=5, pady=5)
        
        left_frame = ttk.Frame(main_paned)
        right_frame = ttk.Frame(main_paned)
        
        self.setup_video_controls(left_frame)
        self.setup_video_preview(right_frame)
        
        main_paned.add(left_frame, weight=1)
        main_paned.add(right_frame, weight=2)
    
    def setup_video_controls(self, parent):
        file_frame = ttk.LabelFrame(parent, text="Video File")
        file_frame.pack(fill='x', padx=5, pady=5)
        
        ttk.Label(file_frame, text="Video Path:").pack(side='left')
        ttk.Entry(file_frame, textvariable=self.video_path, width=40).pack(side='left', fill='x', expand=True, padx=5)
        ttk.Button(file_frame, text="Browse", command=self.browse_video).pack(side='left', padx=5)
        
        settings_frame = ttk.LabelFrame(parent, text="Video Settings")
        settings_frame.pack(fill='both', expand=True, padx=5, pady=5)
        
        self.setup_character_slots(settings_frame)
        
        sampling_frame = ttk.Frame(settings_frame)
        sampling_frame.pack(fill='x', padx=10, pady=5)
        
        ttk.Label(sampling_frame, text="Frame sampling:").pack(side='left')
        self.video_sampling = tk.IntVar(value=1)
        sampling_spinbox = ttk.Spinbox(sampling_frame, from_=1, to=60, textvariable=self.video_sampling, width=5)
        sampling_spinbox.pack(side='left', padx=5)
        sampling_spinbox.bind('<<Increment>>', lambda e: self.schedule_video_preview())
        sampling_spinbox.bind('<<Decrement>>', lambda e: self.schedule_video_preview())
        
        ttk.Label(sampling_frame, text="Output FPS:").pack(side='left', padx=(20,0))
        self.video_output_fps = tk.StringVar(value="30.0")
        ttk.Label(sampling_frame, textvariable=self.video_output_fps).pack(side='left', padx=5)
        
        video_settings_frame = ttk.Frame(settings_frame)
        video_settings_frame.pack(fill='x', padx=10, pady=5)
        
        ttk.Label(video_settings_frame, text="Width:").pack(side='left')
        self.video_width = tk.IntVar(value=80)
        video_width_spinbox = ttk.Spinbox(video_settings_frame, from_=10, to=200, textvariable=self.video_width, width=6)
        video_width_spinbox.pack(side='left', padx=5)
        video_width_spinbox.bind('<<Increment>>', lambda e: self.schedule_video_preview())
        video_width_spinbox.bind('<<Decrement>>', lambda e: self.schedule_video_preview())
        
        ttk.Label(video_settings_frame, text="Line spacing:").pack(side='left', padx=(20,0))
        self.video_spacing = tk.DoubleVar(value=0.55)
        video_spacing_spinbox = ttk.Spinbox(video_settings_frame, from_=0.1, to=2.0, increment=0.05, textvariable=self.video_spacing, width=6)
        video_spacing_spinbox.pack(side='left', padx=5)
        video_spacing_spinbox.bind('<<Increment>>', lambda e: self.schedule_video_preview())
        video_spacing_spinbox.bind('<<Decrement>>', lambda e: self.schedule_video_preview())
        
        adjust_frame = ttk.Frame(settings_frame)
        adjust_frame.pack(fill='x', padx=10, pady=5)
        
        ttk.Label(adjust_frame, text="Brightness:").pack(side='left')
        self.video_brightness = tk.DoubleVar(value=1.0)
        video_brightness_spinbox = ttk.Spinbox(adjust_frame, from_=0.1, to=3.0, increment=0.1, 
                   textvariable=self.video_brightness, width=6)
        video_brightness_spinbox.pack(side='left', padx=5)
        video_brightness_spinbox.bind('<<Increment>>', lambda e: self.schedule_video_preview())
        video_brightness_spinbox.bind('<<Decrement>>', lambda e: self.schedule_video_preview())
        
        ttk.Label(adjust_frame, text="Contrast:").pack(side='left')
        self.video_contrast = tk.DoubleVar(value=1.0)
        video_contrast_spinbox = ttk.Spinbox(adjust_frame, from_=0.1, to=3.0, increment=0.1,
                   textvariable=self.video_contrast, width=6)
        video_contrast_spinbox.pack(side='left', padx=5)
        video_contrast_spinbox.bind('<<Increment>>', lambda e: self.schedule_video_preview())
        video_contrast_spinbox.bind('<<Decrement>>', lambda e: self.schedule_video_preview())
        
        self.video_invert = tk.BooleanVar(value=False)
        video_invert_cb = ttk.Checkbutton(settings_frame, text="Invert colors", variable=self.video_invert,
                                        command=self.schedule_video_preview)
        video_invert_cb.pack(anchor='w', padx=10, pady=2)
        
        max_frames_frame = ttk.Frame(settings_frame)
        max_frames_frame.pack(fill='x', padx=10, pady=5)
        
        ttk.Label(max_frames_frame, text="Max frames (0 for all):").pack(side='left')
        self.video_max_frames = tk.IntVar(value=0)
        max_frames_spinbox = ttk.Spinbox(max_frames_frame, from_=0, to=10000, textvariable=self.video_max_frames, width=8)
        max_frames_spinbox.pack(side='left', padx=5)
        max_frames_spinbox.bind('<<Increment>>', lambda e: self.schedule_video_preview())
        max_frames_spinbox.bind('<<Decrement>>', lambda e: self.schedule_video_preview())
        
        progress_frame = ttk.Frame(settings_frame)
        progress_frame.pack(fill='x', padx=10, pady=5)
        
        self.video_progress = ttk.Progressbar(progress_frame, mode='determinate')
        self.video_progress.pack(fill='x', padx=5, pady=5)
        
        self.video_status = tk.StringVar(value="Select a video file")
        ttk.Label(progress_frame, textvariable=self.video_status).pack(fill='x', padx=5)
        
        button_frame = ttk.Frame(settings_frame)
        button_frame.pack(fill='x', padx=10, pady=10)
        
        ttk.Button(button_frame, text="🎬 Convert Video", command=self.start_video_conversion).pack(side='left', padx=5)
        ttk.Button(button_frame, text="💾 Save Video", command=self.save_video_text).pack(side='left', padx=5)
    
    def setup_video_preview(self, parent):
        preview_frame = ttk.LabelFrame(parent, text="Video Preview")
        preview_frame.pack(fill='both', expand=True, padx=5, pady=5)
        
        preview_controls = ttk.Frame(preview_frame)
        preview_controls.pack(fill='x', padx=10, pady=5)
        
        ttk.Button(preview_controls, text="⏮️", command=self.prev_frame, width=4).pack(side='left', padx=2)
        ttk.Button(preview_controls, text="⏯️", command=self.toggle_video_playback, width=4).pack(side='left', padx=2)
        ttk.Button(preview_controls, text="⏭️", command=self.next_frame, width=4).pack(side='left', padx=2)
        ttk.Button(preview_controls, text="⏹️", command=self.stop_video_playback, width=4).pack(side='left', padx=2)
        
        self.video_frame_label = ttk.Label(preview_controls, text="Frame: 0/0 | FPS: 0")
        self.video_frame_label.pack(side='right', padx=10)
        
        self.video_preview = scrolledtext.ScrolledText(
            preview_frame,
            font=('Courier New', 6),
            bg='black', 
            fg='white',
            wrap='none'
        )
        self.video_preview.pack(fill='both', expand=True, padx=5, pady=5)
        
        self.video_preview.bind('<Configure>', self.on_video_preview_resize)
    
    def setup_webcam_tab(self):
        main_paned = ttk.PanedWindow(self.webcam_frame, orient='horizontal')
        main_paned.pack(fill='both', expand=True, padx=5, pady=5)
        
        left_frame = ttk.Frame(main_paned)
        right_frame = ttk.Frame(main_paned)
        
        self.setup_webcam_controls(left_frame)
        self.setup_webcam_output(right_frame)
        
        main_paned.add(left_frame, weight=1)
        main_paned.add(right_frame, weight=2)
    
    def setup_webcam_controls(self, parent):
        controls_frame = ttk.LabelFrame(parent, text="Webcam Controls")
        controls_frame.pack(fill='x', padx=5, pady=5)
        
        self.available_cameras = CrossPlatformCamera.detect_cameras()
        
        cam_frame = ttk.Frame(controls_frame)
        cam_frame.pack(fill='x', padx=10, pady=5)
        
        ttk.Label(cam_frame, text="Camera:").pack(side='left')
        
        camera_values = [f"Camera {i}" for i in range(len(self.available_cameras))]
        if not camera_values:
            camera_values = ["Camera 0"]
        
        self.camera_combo = ttk.Combobox(cam_frame, values=camera_values, state="readonly", width=15)
        if camera_values:
            self.camera_combo.set(camera_values[0])
        self.camera_combo.pack(side='left', padx=5)
        
        ttk.Button(cam_frame, text="🔄 Rescan", command=self.rescan_cameras).pack(side='left', padx=5)
        
        settings_frame = ttk.LabelFrame(parent, text="Webcam Settings")
        settings_frame.pack(fill='both', expand=True, padx=5, pady=5)
        
        self.setup_character_slots(settings_frame)
        
        skip_frame = ttk.Frame(settings_frame)
        skip_frame.pack(fill='x', padx=10, pady=5)
        
        ttk.Label(skip_frame, text="Process every N frames:").pack(side='left')
        self.webcam_frame_skip = tk.IntVar(value=2)
        ttk.Spinbox(skip_frame, from_=1, to=10, textvariable=self.webcam_frame_skip, width=5).pack(side='left', padx=5)
        
        webcam_settings_frame = ttk.Frame(settings_frame)
        webcam_settings_frame.pack(fill='x', padx=10, pady=5)
        
        ttk.Label(webcam_settings_frame, text="Width:").pack(side='left')
        self.webcam_width = tk.IntVar(value=80)
        ttk.Spinbox(webcam_settings_frame, from_=20, to=200, textvariable=self.webcam_width, width=6).pack(side='left', padx=5)
        
        ttk.Label(webcam_settings_frame, text="Line spacing:").pack(side='left', padx=(20,0))
        self.webcam_spacing = tk.DoubleVar(value=0.55)
        ttk.Spinbox(webcam_settings_frame, from_=0.1, to=2.0, increment=0.05, textvariable=self.webcam_spacing, width=6).pack(side='left', padx=5)
        
        adjust_frame = ttk.Frame(settings_frame)
        adjust_frame.pack(fill='x', padx=10, pady=5)
        
        ttk.Label(adjust_frame, text="Brightness:").pack(side='left')
        self.webcam_brightness = tk.DoubleVar(value=1.0)
        ttk.Spinbox(adjust_frame, from_=0.1, to=3.0, increment=0.1, 
                   textvariable=self.webcam_brightness, width=6).pack(side='left', padx=5)
        
        ttk.Label(adjust_frame, text="Contrast:").pack(side='left')
        self.webcam_contrast = tk.DoubleVar(value=1.0)
        ttk.Spinbox(adjust_frame, from_=0.1, to=3.0, increment=0.1,
                   textvariable=self.webcam_contrast, width=6).pack(side='left', padx=5)
        
        self.webcam_invert = tk.BooleanVar(value=False)
        ttk.Checkbutton(settings_frame, text="Invert colors", variable=self.webcam_invert).pack(anchor='w', padx=10, pady=2)
        
        self.webcam_mirror = tk.BooleanVar(value=True)
        ttk.Checkbutton(settings_frame, text="Mirror image", variable=self.webcam_mirror).pack(anchor='w', padx=10, pady=2)
        
        button_frame = ttk.Frame(settings_frame)
        button_frame.pack(fill='x', padx=10, pady=10)
        
        self.webcam_start_button = ttk.Button(button_frame, text="🎬 Start Webcam", command=self.start_webcam)
        self.webcam_start_button.pack(side='left', padx=5)
        
        self.webcam_stop_button = ttk.Button(button_frame, text="⏹️ Stop", command=self.stop_webcam, state='disabled')
        self.webcam_stop_button.pack(side='left', padx=5)
        
        ttk.Button(button_frame, text="📸 Capture Frame", command=self.capture_webcam_frame).pack(side='left', padx=5)
        
        self.webcam_status = tk.StringVar(value=f"Found {len(self.available_cameras)} cameras. Ready to start.")
        status_bar = ttk.Label(parent, textvariable=self.webcam_status, relief='sunken')
        status_bar.pack(fill='x', padx=5, pady=5)
    
    def setup_webcam_output(self, parent):
        output_controls = ttk.LabelFrame(parent, text="Webcam Output")
        output_controls.pack(fill='x', padx=5, pady=5)
        
        control_frame = ttk.Frame(output_controls)
        control_frame.pack(fill='x', padx=10, pady=5)
        
        ttk.Button(control_frame, text="📋 Copy", command=self.copy_webcam_text).pack(side='right', padx=5)
        ttk.Button(control_frame, text="💾 Save", command=self.save_webcam_text).pack(side='right', padx=5)
        
        output_frame = ttk.LabelFrame(parent, text="Live Output")
        output_frame.pack(fill='both', expand=True, padx=5, pady=5)
        
        self.webcam_output = scrolledtext.ScrolledText(
            output_frame, 
            font=('Courier New', 8),
            bg='black', 
            fg='white',
            wrap='none'
        )
        self.webcam_output.pack(fill='both', expand=True, padx=5, pady=5)
        
        self.webcam_performance = tk.StringVar(value="FPS: 0 | Frame time: 0ms")
        performance_label = ttk.Label(parent, textvariable=self.webcam_performance, relief='sunken')
        performance_label.pack(fill='x', padx=5, pady=5)
        
        self.webcam_output.bind('<Configure>', self.on_webcam_output_resize)

    def calculate_optimal_font_size(self, text_widget, text_content):
        if not text_content:
            return 8
        
        lines = text_content.split('\n')
        if not lines:
            return 8
        
        max_line_length = max(len(line) for line in lines)
        num_lines = len(lines)
        
        widget_width = text_widget.winfo_width() - 20
        widget_height = text_widget.winfo_height() - 20
        
        if widget_width <= 0 or widget_height <= 0:
            return 8
        
        font_width_ratio = 0.6
        font_height_ratio = 1.8
        
        width_based_size = int(widget_width / (max_line_length * font_width_ratio))
        height_based_size = int(widget_height / (num_lines * font_height_ratio))
        
        optimal_size = min(width_based_size, height_based_size)
        
        return max(3, optimal_size)

    def apply_optimal_font_size(self, text_widget, text_content):
        font_size = self.calculate_optimal_font_size(text_widget, text_content)
        text_widget.configure(font=('Courier New', font_size))

    def on_image_output_resize(self, event):
        current_text = self.image_output.get(1.0, tk.END).strip()
        if current_text:
            self.apply_optimal_font_size(self.image_output, current_text)

    def on_video_preview_resize(self, event):
        current_text = self.video_preview.get(1.0, tk.END).strip()
        if current_text:
            self.apply_optimal_font_size(self.video_preview, current_text)

    def on_webcam_output_resize(self, event):
        current_text = self.webcam_output.get(1.0, tk.END).strip()
        if current_text:
            self.apply_optimal_font_size(self.webcam_output, current_text)

    def schedule_image_conversion(self):
        current_time = time.time()
        if current_time - self.last_conversion_time < 0.5:
            return
            
        if self.conversion_timer:
            self.root.after_cancel(self.conversion_timer)
            
        self.conversion_timer = self.root.after(500, self.start_image_conversion)
        
    def schedule_video_preview(self):
        if not self.video_path.get():
            return
            
        current_time = time.time()
        if current_time - self.last_video_conversion_time < 0.3:
            return
            
        if self.video_conversion_timer:
            self.root.after_cancel(self.video_conversion_timer)
            
        self.video_conversion_timer = self.root.after(300, self.update_video_preview_frame)
        
    def on_slot_change(self):
        self.update_active_charset()
        self.save_settings_to_config()
        if self.image_path.get():
            self.schedule_image_conversion()
        if self.video_path.get():
            self.schedule_video_preview()

    def on_charset_change(self):
        self.update_active_charset()
        self.save_settings_to_config()
        if self.image_path.get():
            self.schedule_image_conversion()
        if self.video_path.get():
            self.schedule_video_preview()

    def update_active_charset(self):
        slot = self.active_slot.get()
        if slot == 1:
            charset = self.charset_slot1.get()
        elif slot == 2:
            charset = self.charset_slot2.get()
        else:
            charset = self.charset_slot3.get()
        
        self.converter.set_config(charset=charset)

    def load_settings_from_config(self):
        self.image_width.set(self.converter.config['image_width'])
        self.image_brightness.set(self.converter.config['image_brightness'])
        self.image_contrast.set(self.converter.config['image_contrast'])
        self.image_invert.set(self.converter.config['image_invert'])
        self.image_spacing.set(self.converter.config['image_spacing'])
        
        self.video_width.set(self.converter.config['video_width'])
        self.video_sampling.set(self.converter.config['video_sampling'])
        self.video_brightness.set(self.converter.config['video_brightness'])
        self.video_contrast.set(self.converter.config['video_contrast'])
        self.video_invert.set(self.converter.config['video_invert'])
        self.video_spacing.set(self.converter.config['video_spacing'])
        self.video_max_frames.set(self.converter.config['video_max_frames'])
        
        self.webcam_width.set(self.converter.config['webcam_width'])
        self.webcam_frame_skip.set(self.converter.config['webcam_frame_skip'])
        self.webcam_brightness.set(self.converter.config['webcam_brightness'])
        self.webcam_contrast.set(self.converter.config['webcam_contrast'])
        self.webcam_invert.set(self.converter.config['webcam_invert'])
        self.webcam_spacing.set(self.converter.config['webcam_spacing'])
        self.webcam_mirror.set(self.converter.config['webcam_mirror'])
        
        self.charset_slot1.set(self.converter.config['charset_slot1'])
        self.charset_slot2.set(self.converter.config['charset_slot2'])
        self.charset_slot3.set(self.converter.config['charset_slot3'])
        self.active_slot.set(self.converter.config['active_slot'])

    def save_settings_to_config(self):
        self.converter.set_config(
            image_width=self.image_width.get(),
            image_brightness=float(self.image_brightness.get()),
            image_contrast=float(self.image_contrast.get()),
            image_invert=self.image_invert.get(),
            image_spacing=float(self.image_spacing.get()),
            
            video_width=self.video_width.get(),
            video_sampling=self.video_sampling.get(),
            video_brightness=float(self.video_brightness.get()),
            video_contrast=float(self.video_contrast.get()),
            video_invert=self.video_invert.get(),
            video_spacing=float(self.video_spacing.get()),
            video_max_frames=self.video_max_frames.get(),
            
            webcam_width=self.webcam_width.get(),
            webcam_frame_skip=self.webcam_frame_skip.get(),
            webcam_brightness=float(self.webcam_brightness.get()),
            webcam_contrast=float(self.webcam_contrast.get()),
            webcam_invert=self.webcam_invert.get(),
            webcam_spacing=float(self.webcam_spacing.get()),
            webcam_mirror=self.webcam_mirror.get(),
            
            charset_slot1=self.charset_slot1.get(),
            charset_slot2=self.charset_slot2.get(),
            charset_slot3=self.charset_slot3.get(),
            active_slot=self.active_slot.get()
        )

    def rescan_cameras(self):
        self.available_cameras = CrossPlatformCamera.detect_cameras()
        camera_values = [f"Camera {i}" for i in range(len(self.available_cameras))]
        self.camera_combo['values'] = camera_values
        if camera_values:
            self.camera_combo.set(camera_values[0])
        self.webcam_status.set(f"Found {len(self.available_cameras)} cameras")

    def start_webcam(self):
        try:
            selected_camera_index = self.camera_combo.current()
            if selected_camera_index < 0:
                selected_camera_index = 0
            
            camera_id = self.available_cameras[selected_camera_index]
            
            self.cap = cv2.VideoCapture(camera_id)
            
            if not self.cap.isOpened():
                self.webcam_status.set(f"Cannot access camera {camera_id}")
                return
            
            self.webcam_running = True
            self.webcam_start_button.config(state='disabled')
            self.webcam_stop_button.config(state='normal')
            self.webcam_status.set(f"Camera {camera_id} started")
            
            self.webcam_thread = threading.Thread(target=self.webcam_loop, daemon=True)
            self.webcam_thread.start()
            
        except Exception as e:
            self.webcam_status.set(f"Error: {str(e)}")

    def stop_webcam(self):
        self.webcam_running = False
        if self.cap:
            self.cap.release()
            self.cap = None
        self.webcam_start_button.config(state='normal')
        self.webcam_stop_button.config(state='disabled')
        self.webcam_status.set("Webcam stopped")

    def webcam_loop(self):
        frame_count = 0
        start_time = time.time()
        
        while self.webcam_running and self.cap:
            try:
                ret, frame = self.cap.read()
                if not ret:
                    break
                
                if self.webcam_mirror.get():
                    frame = cv2.flip(frame, 1)
                
                frame_count += 1
                if frame_count % self.webcam_frame_skip.get() != 0:
                    continue
                
                process_start = time.time()
                text_output = self.convert_webcam_frame(frame)
                process_time = (time.time() - process_start) * 1000
                
                self.root.after(0, self.update_webcam_output, text_output)
                
                current_time = time.time()
                elapsed = current_time - start_time
                if elapsed >= 1.0:
                    fps = frame_count / elapsed
                    self.root.after(0, self.update_webcam_performance, fps, process_time)
                    frame_count = 0
                    start_time = current_time
                
                time.sleep(0.01)
                
            except Exception:
                break

    def convert_webcam_frame(self, frame):
        try:
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            pil_image = Image.fromarray(frame_rgb)
            
            self.converter.set_config(
                width=self.webcam_width.get(),
                height=None,
                charset=self.get_active_charset(),
                invert=self.webcam_invert.get(),
                brightness=float(self.webcam_brightness.get()),
                contrast=float(self.webcam_contrast.get()),
                line_spacing=float(self.webcam_spacing.get())
            )
            
            return self.converter._process_pil_image(pil_image)
        except Exception as e:
            return f"Error: {str(e)}"

    def get_active_charset(self):
        slot = self.active_slot.get()
        if slot == 1:
            return self.charset_slot1.get()
        elif slot == 2:
            return self.charset_slot2.get()
        else:
            return self.charset_slot3.get()

    def update_webcam_output(self, text_output):
        if self.webcam_output:
            self.webcam_output.delete(1.0, tk.END)
            self.webcam_output.insert(tk.END, text_output)
            self.live_output = text_output
            self.apply_optimal_font_size(self.webcam_output, text_output)

    def update_webcam_performance(self, fps, frame_time):
        self.webcam_performance.set(f"FPS: {fps:.1f} | Frame time: {frame_time:.1f}ms")

    def copy_webcam_text(self):
        if self.live_output:
            self.root.clipboard_clear()
            self.root.clipboard_append(self.live_output)
            self.webcam_status.set("Text copied")

    def save_webcam_text(self):
        if self.live_output:
            filename = filedialog.asksaveasfilename(
                defaultextension=".txt",
                filetypes=(("Text files", "*.txt"), ("All files", "*.*"))
            )
            if filename:
                try:
                    with open(filename, 'w', encoding='utf-8') as f:
                        f.write(self.live_output)
                    self.webcam_status.set(f"Saved: {os.path.basename(filename)}")
                except Exception:
                    self.webcam_status.set("Save error")

    def capture_webcam_frame(self):
        self.save_webcam_text()

    def browse_image(self):
        filename = filedialog.askopenfilename(
            title="Select image file",
            filetypes=(
                ("Image files", "*.jpg *.jpeg *.png *.bmp *.gif *.tiff *.webp"),
                ("All files", "*.*")
            )
        )
        if filename:
            self.image_path.set(filename)
            self.schedule_image_conversion()

    def browse_video(self):
        filename = filedialog.askopenfilename(
            title="Select video file",
            filetypes=(
                ("Video files", "*.mp4 *.avi *.mov *.mkv *.wmv"),
                ("All files", "*.*")
            )
        )
        if filename:
            self.video_path.set(filename)
            self.load_video_info()
            self.start_video_stream()

    def load_last_image(self):
        if self.converter.config['last_image'] and os.path.exists(self.converter.config['last_image']):
            self.image_path.set(self.converter.config['last_image'])
            self.schedule_image_conversion()

    def start_image_conversion(self):
        if not self.image_path.get():
            return
            
        self.last_conversion_time = time.time()
        self.save_settings_to_config()
        self.image_progress.start()
        self.image_status.set("Converting...")
        
        thread = threading.Thread(target=self.convert_image)
        thread.daemon = True
        thread.start()

    def convert_image(self):
        try:
            self.converter.set_config(
                width=self.image_width.get(),
                height=None,
                charset=self.get_active_charset(),
                invert=self.image_invert.get(),
                brightness=float(self.image_brightness.get()),
                contrast=float(self.image_contrast.get()),
                line_spacing=float(self.image_spacing.get())
            )
            result = self.converter.process(image_path=self.image_path.get())
            self.root.after(0, self.image_conversion_complete, result)
        except Exception as e:
            self.root.after(0, self.image_conversion_error, str(e))

    def image_conversion_complete(self, result):
        self.image_progress.stop()
        self.image_output.delete(1.0, tk.END)
        self.image_output.insert(tk.END, result)
        self.image_status.set("Conversion complete!")
        self.apply_optimal_font_size(self.image_output, result)

    def image_conversion_error(self, error_msg):
        self.image_progress.stop()
        self.image_output.delete(1.0, tk.END)
        self.image_output.insert(tk.END, f"Error: {error_msg}")
        self.image_status.set(f"Error: {error_msg}")

    def copy_image_text(self):
        if self.image_output.get(1.0, tk.END).strip():
            self.root.clipboard_clear()
            self.root.clipboard_append(self.image_output.get(1.0, tk.END))
            self.image_status.set("Text copied")

    def clear_image_text(self):
        self.image_output.delete(1.0, tk.END)

    def save_image_text(self):
        if not self.image_output.get(1.0, tk.END).strip():
            return
            
        filename = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=(("Text files", "*.txt"), ("All files", "*.*"))
        )
        if filename:
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(self.image_output.get(1.0, tk.END))
                self.image_status.set(f"Saved: {os.path.basename(filename)}")
            except Exception:
                self.image_status.set("Save error")

    def load_video_info(self):
        if not self.video_path.get() or not os.path.exists(self.video_path.get()):
            return
        
        try:
            cap = cv2.VideoCapture(self.video_path.get())
            if not cap.isOpened():
                self.video_status.set("Cannot open video file")
                return
            
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            self.video_fps = cap.get(cv2.CAP_PROP_FPS)
            self.update_video_fps()
            
            cap.release()
            self.video_status.set("Video loaded")
            
        except Exception as e:
            self.video_status.set(f"Error: {str(e)}")

    def update_video_fps(self, event=None):
        try:
            source_fps = self.video_fps
            sampling = self.video_sampling.get()
            output_fps = source_fps / sampling
            self.video_output_fps.set(f"{output_fps:.1f}")
            self.playback_delay = int(1000 / output_fps) if output_fps > 0 else 33
        except Exception:
            pass

    def start_video_stream(self):
        try:
            if not self.converter.video_processor.open_video(self.video_path.get()):
                self.video_status.set("Cannot open video file")
                return
                
            self.video_stream_active = True
            self.video_status.set("Video preview ready")
            self.current_frame_index = 0
            self.update_video_preview_frame()
            
        except Exception as e:
            self.video_status.set(f"Error: {str(e)}")

    def stop_video_stream(self):
        self.video_stream_active = False
        self.converter.video_processor.close()
        self.video_status.set("Video preview stopped")

    def update_video_preview_frame(self):
        if not self.video_stream_active or not self.video_path.get():
            return
            
        try:
            settings = {
                'width': self.video_width.get(),
                'height': None,
                'charset': self.get_active_charset(),
                'invert': self.video_invert.get(),
                'brightness': float(self.video_brightness.get()),
                'contrast': float(self.video_contrast.get()),
                'line_spacing': float(self.video_spacing.get())
            }
            
            frame_text = self.converter.video_processor.get_frame(self.current_frame_index, settings)
            
            if frame_text:
                self.video_preview.delete(1.0, tk.END)
                self.video_preview.insert(tk.END, frame_text)
                self.apply_optimal_font_size(self.video_preview, frame_text)
                
                self.video_frame_label.config(
                    text=f"Frame: {self.current_frame_index + 1}/{self.converter.video_processor.total_frames} | FPS: {self.video_output_fps.get()}"
                )
            
            self.last_video_conversion_time = time.time()
            
        except Exception as e:
            self.video_status.set(f"Preview error: {str(e)}")

    def start_video_conversion(self):
        if not self.video_path.get():
            self.video_status.set("Select a video file first")
            return
        
        self.last_video_conversion_time = time.time()
        self.save_settings_to_config()
        self.video_progress.config(value=0)
        self.video_playing = False
        
        thread = threading.Thread(target=self.convert_video)
        thread.daemon = True
        thread.start()

    def convert_video(self):
        try:
            self.video_status.set("Starting conversion...")
            
            self.converter.set_config(
                width=self.video_width.get(),
                height=None,
                charset=self.get_active_charset(),
                invert=self.video_invert.get(),
                brightness=float(self.video_brightness.get()),
                contrast=float(self.video_contrast.get()),
                line_spacing=float(self.video_spacing.get())
            )
            
            result = self.converter.process_video(
                self.video_path.get(),
                frame_sampling=self.video_sampling.get(),
                max_frames=self.video_max_frames.get(),
                progress_callback=self.update_video_progress
            )
            
            self.root.after(0, self.video_conversion_complete, result)
            
        except Exception as e:
            self.root.after(0, self.video_conversion_error, str(e))

    def update_video_progress(self, current, total):
        progress = (current / total) * 100
        self.root.after(0, self.video_progress.config, {'value': progress})
        self.root.after(0, self.video_status.set, f"Processing frame {current}/{total}")

    def video_conversion_complete(self, result):
        self.video_progress.config(value=100)
        self.video_status.set(f"Complete! {result['processed']} frames")
        
        self.current_video_frames = result['frames']
        self.current_frame_index = 0
        
        if self.current_video_frames:
            self.show_current_frame()
            self.start_auto_playback()

    def start_auto_playback(self):
        self.video_playing = True
        self.play_video()

    def video_conversion_error(self, error_msg):
        self.video_progress.config(value=0)
        self.video_status.set(f"Error: {error_msg}")

    def show_current_frame(self):
        if not self.current_video_frames:
            return
        
        frame_text = self.current_video_frames[self.current_frame_index]
        self.video_preview.delete(1.0, tk.END)
        self.video_preview.insert(tk.END, frame_text)
        self.apply_optimal_font_size(self.video_preview, frame_text)
        
        self.video_frame_label.config(text=f"Frame: {self.current_frame_index + 1}/{len(self.current_video_frames)} | FPS: {self.video_output_fps.get()}")

    def next_frame(self):
        if not self.current_video_frames and not self.video_stream_active:
            return
        
        if self.video_stream_active:
            self.current_frame_index = (self.current_frame_index + 1) % self.converter.video_processor.total_frames
            self.update_video_preview_frame()
        else:
            self.current_frame_index = (self.current_frame_index + 1) % len(self.current_video_frames)
            self.show_current_frame()

    def prev_frame(self):
        if not self.current_video_frames and not self.video_stream_active:
            return
        
        if self.video_stream_active:
            self.current_frame_index = (self.current_frame_index - 1) % self.converter.video_processor.total_frames
            self.update_video_preview_frame()
        else:
            self.current_frame_index = (self.current_frame_index - 1) % len(self.current_video_frames)
            self.show_current_frame()

    def toggle_video_playback(self):
        if not self.current_video_frames and not self.video_stream_active:
            return
        
        self.video_playing = not self.video_playing
        if self.video_playing:
            self.play_video()

    def stop_video_playback(self):
        self.video_playing = False

    def play_video(self):
        if not self.video_playing:
            return
        
        self.next_frame()
        self.root.after(self.playback_delay, self.play_video)

    def save_video_text(self):
        if not hasattr(self.converter, 'video_result') or not self.converter.video_result:
            return
        
        filename = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=(("Text files", "*.txt"), ("All files", "*.*"))
        )
        if filename:
            try:
                self.converter.save_video_text(filename)
                self.video_status.set(f"Saved: {os.path.basename(filename)}")
            except Exception:
                self.video_status.set("Save error")

    def reset_image_settings(self):
        self.image_width.set(80)
        self.image_brightness.set(1.0)
        self.image_contrast.set(1.0)
        self.image_invert.set(False)
        self.image_spacing.set(0.55)
        self.schedule_image_conversion()

def main():
    root = tk.Tk()
    app = MainApplication(root)
    
    def on_closing():
        app.stop_webcam()
        if hasattr(app, 'video_stream_active') and app.video_stream_active:
            app.stop_video_stream()
        root.destroy()
    
    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()

if __name__ == "__main__":
    main()
