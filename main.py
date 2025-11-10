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

class ImageToASCIIGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("ASCII Art Converter v2.0")
        self.root.geometry("1200x800")
        
        self.converter = ImageToASCII()
        
        self.image_path = tk.StringVar()
        self.preview_image = None
        self.ascii_text = None
        self.conversion_timer = None
        self.last_conversion_time = 0
        
        self.setup_gui()
        
    def setup_gui(self):
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill='both', expand=True, padx=10, pady=10)
        
        self.convert_frame = ttk.Frame(notebook)
        notebook.add(self.convert_frame, text='🎨 Control')
        
        self.settings_frame = ttk.Frame(notebook)
        notebook.add(self.settings_frame, text='⚙️ Settings + Result')
        
        self.setup_convert_tab()
        self.setup_settings_tab()
        
    def setup_convert_tab(self):
        main_frame = ttk.Frame(self.convert_frame)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        current_frame = ttk.LabelFrame(main_frame, text="Current Image")
        current_frame.pack(fill='x', padx=5, pady=5)
        
        path_frame = ttk.Frame(current_frame)
        path_frame.pack(fill='x', padx=10, pady=5)
        
        ttk.Label(path_frame, text="Path:").pack(side='left')
        ttk.Entry(path_frame, textvariable=self.image_path, width=60).pack(side='left', fill='x', expand=True, padx=5)
        ttk.Button(path_frame, text="📷", command=self.load_last_image, width=3).pack(side='left', padx=2)
        
        preview_info_frame = ttk.Frame(current_frame)
        preview_info_frame.pack(fill='x', padx=10, pady=10)
        
        preview_frame = ttk.LabelFrame(preview_info_frame, text="Preview")
        preview_frame.pack(side='left', fill='both', expand=True, padx=5)
        
        self.preview_label = ttk.Label(preview_frame, text="Select image from gallery")
        self.preview_label.pack(pady=20, padx=20)
        
        info_frame = ttk.LabelFrame(preview_info_frame, text="Information")
        info_frame.pack(side='right', fill='both', padx=5)
        
        self.info_text = tk.Text(info_frame, height=8, width=30, bg='#f0f0f0', font=('Arial', 9))
        self.info_text.pack(fill='both', expand=True, padx=5, pady=5)
        
        button_frame = ttk.Frame(current_frame)
        button_frame.pack(fill='x', padx=10, pady=10)
        
        ttk.Button(button_frame, text="💾 Save to .txt", command=self.save_ascii).pack(side='left', padx=5)
        ttk.Button(button_frame, text="🔄 Reset", command=self.reset_all).pack(side='left', padx=5)
        
        gallery_frame = ttk.LabelFrame(main_frame, text="Image Gallery")
        gallery_frame.pack(fill='both', expand=True, padx=5, pady=5)
        
        gallery_controls = ttk.Frame(gallery_frame)
        gallery_controls.pack(fill='x', padx=10, pady=5)
        
        ttk.Button(gallery_controls, text="🔄 Refresh", command=self.refresh_gallery).pack(side='left', padx=5)
        ttk.Button(gallery_controls, text="Select Folder", command=self.select_folder).pack(side='left', padx=5)
        
        self.folder_path = tk.StringVar(value=os.getcwd())
        ttk.Label(gallery_controls, textvariable=self.folder_path).pack(side='left', padx=10, fill='x', expand=True)
        
        gallery_list_frame = ttk.Frame(gallery_frame)
        gallery_list_frame.pack(fill='both', expand=True, padx=10, pady=5)
        
        columns = ('name', 'size', 'path')
        self.gallery_tree = ttk.Treeview(gallery_list_frame, columns=columns, show='headings', height=15)
        
        self.gallery_tree.heading('name', text='File Name')
        self.gallery_tree.heading('size', text='Size (KB)')
        self.gallery_tree.heading('path', text='Path')
        
        self.gallery_tree.column('name', width=300)
        self.gallery_tree.column('size', width=100)
        self.gallery_tree.column('path', width=400)
        
        scrollbar = ttk.Scrollbar(gallery_list_frame, orient='vertical', command=self.gallery_tree.yview)
        self.gallery_tree.configure(yscrollcommand=scrollbar.set)
        
        self.gallery_tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        
        self.gallery_tree.bind('<Double-1>', self.on_gallery_select)
        
        self.refresh_gallery()
        
    def setup_settings_tab(self):
        main_paned = ttk.PanedWindow(self.settings_frame, orient='horizontal')
        main_paned.pack(fill='both', expand=True, padx=5, pady=5)
        
        left_frame = ttk.LabelFrame(main_paned, text="Conversion Settings")
        left_frame.pack(side='left', fill='both', padx=5, pady=5)
        
        canvas = tk.Canvas(left_frame)
        scrollbar = ttk.Scrollbar(left_frame, orient="vertical", command=canvas.yview)
        self.scrollable_frame = ttk.Frame(canvas)
        
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        size_frame = ttk.LabelFrame(self.scrollable_frame, text="Art Size")
        size_frame.pack(fill='x', padx=10, pady=5)
        
        ttk.Label(size_frame, text="Width:").grid(row=0, column=0, padx=5, pady=5, sticky='w')
        self.width_var = tk.IntVar(value=self.converter.config['width'])
        width_spinbox = ttk.Spinbox(size_frame, from_=10, to=500, textvariable=self.width_var, width=10,
                                   command=self.schedule_conversion)
        width_spinbox.grid(row=0, column=1, padx=5, pady=5)
        width_spinbox.bind('<KeyRelease>', lambda e: self.schedule_conversion())
        
        ttk.Label(size_frame, text="Height (auto for auto):").grid(row=1, column=0, padx=5, pady=5, sticky='w')
        self.height_var = tk.StringVar(value=str(self.converter.config['height']) if self.converter.config['height'] else 'auto')
        height_entry = ttk.Entry(size_frame, textvariable=self.height_var, width=10)
        height_entry.grid(row=1, column=1, padx=5, pady=5)
        height_entry.bind('<KeyRelease>', lambda e: self.schedule_conversion())
        
        chars_frame = ttk.LabelFrame(self.scrollable_frame, text="Character Sets")
        chars_frame.pack(fill='x', padx=10, pady=5)
        
        slot1_frame = ttk.Frame(chars_frame)
        slot1_frame.pack(fill='x', padx=5, pady=2)
        ttk.Label(slot1_frame, text="Slot 1:").pack(side='left')
        self.charset_slot1 = tk.StringVar(value=self.converter.config.get('charset_slot1', '@%#*+=-,.'))
        slot1_entry = ttk.Entry(slot1_frame, textvariable=self.charset_slot1, width=40)
        slot1_entry.pack(side='left', fill='x', expand=True, padx=5)
        slot1_entry.bind('<KeyRelease>', lambda e: self.schedule_conversion())
        
        slot2_frame = ttk.Frame(chars_frame)
        slot2_frame.pack(fill='x', padx=5, pady=2)
        ttk.Label(slot2_frame, text="Slot 2:").pack(side='left')
        self.charset_slot2 = tk.StringVar(value=self.converter.config.get('charset_slot2', '@%#*+=-.: '))
        slot2_entry = ttk.Entry(slot2_frame, textvariable=self.charset_slot2, width=40)
        slot2_entry.pack(side='left', fill='x', expand=True, padx=5)
        slot2_entry.bind('<KeyRelease>', lambda e: self.schedule_conversion())
        
        slot3_frame = ttk.Frame(chars_frame)
        slot3_frame.pack(fill='x', padx=5, pady=2)
        ttk.Label(slot3_frame, text="Slot 3:").pack(side='left')
        self.charset_slot3 = tk.StringVar(value=self.converter.config.get('charset_slot3', '█▓▒░ '))
        slot3_entry = ttk.Entry(slot3_frame, textvariable=self.charset_slot3, width=40)
        slot3_entry.pack(side='left', fill='x', expand=True, padx=5)
        slot3_entry.bind('<KeyRelease>', lambda e: self.schedule_conversion())
        
        slot_select_frame = ttk.Frame(chars_frame)
        slot_select_frame.pack(fill='x', padx=5, pady=5)
        
        self.active_slot = tk.IntVar(value=self.converter.config.get('active_slot', 1))
        ttk.Radiobutton(slot_select_frame, text="Slot 1", variable=self.active_slot, value=1, 
                       command=self.on_slot_change).pack(side='left', padx=10)
        ttk.Radiobutton(slot_select_frame, text="Slot 2", variable=self.active_slot, value=2,
                       command=self.on_slot_change).pack(side='left', padx=10)
        ttk.Radiobutton(slot_select_frame, text="Slot 3", variable=self.active_slot, value=3,
                       command=self.on_slot_change).pack(side='left', padx=10)
        
        adjust_frame = ttk.LabelFrame(self.scrollable_frame, text="Image Adjustment")
        adjust_frame.pack(fill='x', padx=10, pady=5)
        
        brightness_frame = ttk.Frame(adjust_frame)
        brightness_frame.pack(fill='x', padx=5, pady=2)
        
        ttk.Label(brightness_frame, text="Brightness:").pack(side='left')
        self.brightness_var = tk.DoubleVar(value=self.converter.config['brightness'])
        brightness_spinbox = ttk.Spinbox(brightness_frame, from_=0.1, to=3.0, increment=0.1, 
                                        textvariable=self.brightness_var, width=8,
                                        command=self.schedule_conversion)
        brightness_spinbox.pack(side='left', padx=5)
        brightness_spinbox.bind('<KeyRelease>', lambda e: self.schedule_conversion())
        
        contrast_frame = ttk.Frame(adjust_frame)
        contrast_frame.pack(fill='x', padx=5, pady=2)
        
        ttk.Label(contrast_frame, text="Contrast:").pack(side='left')
        self.contrast_var = tk.DoubleVar(value=self.converter.config['contrast'])
        contrast_spinbox = ttk.Spinbox(contrast_frame, from_=0.1, to=3.0, increment=0.1,
                                      textvariable=self.contrast_var, width=8,
                                      command=self.schedule_conversion)
        contrast_spinbox.pack(side='left', padx=5)
        contrast_spinbox.bind('<KeyRelease>', lambda e: self.schedule_conversion())
        
        advanced_frame = ttk.LabelFrame(self.scrollable_frame, text="Advanced Settings")
        advanced_frame.pack(fill='x', padx=10, pady=5)
        
        self.invert_var = tk.BooleanVar(value=self.converter.config['invert'])
        invert_cb = ttk.Checkbutton(advanced_frame, text="Invert colors", variable=self.invert_var,
                                   command=self.schedule_conversion)
        invert_cb.grid(row=0, column=0, padx=5, pady=5, sticky='w')
        
        spacing_frame = ttk.Frame(advanced_frame)
        spacing_frame.grid(row=1, column=0, sticky='w', padx=5, pady=2)
        
        ttk.Label(spacing_frame, text="Line spacing:").pack(side='left')
        self.spacing_var = tk.DoubleVar(value=self.converter.config['line_spacing'])
        spacing_spinbox = ttk.Spinbox(spacing_frame, from_=0.1, to=2.0, increment=0.05,
                                     textvariable=self.spacing_var, width=8,
                                     command=self.schedule_conversion)
        spacing_spinbox.pack(side='left', padx=5)
        spacing_spinbox.bind('<KeyRelease>', lambda e: self.schedule_conversion())
        
        buttons_frame = ttk.Frame(self.scrollable_frame)
        buttons_frame.pack(fill='x', padx=10, pady=10)
        
        ttk.Button(buttons_frame, text="🔄 Reset to Default", command=self.reset_settings).pack(side='left', padx=5)
        
        right_frame = ttk.LabelFrame(main_paned, text="Result")
        right_frame.pack(side='right', fill='both', expand=True, padx=5, pady=5)
        
        result_controls = ttk.Frame(right_frame)
        result_controls.pack(fill='x', pady=5)
        
        ttk.Label(result_controls, text="Font size:").pack(side='left')
        self.font_size = tk.IntVar(value=6)
        ttk.Spinbox(result_controls, from_=4, to=20, textvariable=self.font_size, 
                   width=5, command=self.update_ascii_display).pack(side='left', padx=5)
        
        ttk.Button(result_controls, text="Copy", command=self.copy_ascii).pack(side='right', padx=5)
        ttk.Button(result_controls, text="Clear", command=self.clear_ascii).pack(side='right', padx=5)
        
        self.ascii_text = scrolledtext.ScrolledText(right_frame, 
                                                   font=('Courier New', self.font_size.get()),
                                                   bg='black', fg='white',
                                                   wrap='none',
                                                   width=80,
                                                   height=35)
        self.ascii_text.pack(fill='both', expand=True, padx=5, pady=5)
        
        self.progress = ttk.Progressbar(right_frame, mode='indeterminate')
        self.progress.pack(fill='x', pady=5)
        
        self.status_var = tk.StringVar(value="Ready")
        status_bar = ttk.Label(right_frame, textvariable=self.status_var)
        status_bar.pack(fill='x', pady=5)
        
        main_paned.add(left_frame, weight=1)
        main_paned.add(right_frame, weight=2)
        
    def on_slot_change(self):
        active_charset = self.get_active_charset()
        self.converter.config['charset'] = active_charset
        self.schedule_conversion()
        
    def get_active_charset(self):
        slot = self.active_slot.get()
        if slot == 1:
            return self.charset_slot1.get()
        elif slot == 2:
            return self.charset_slot2.get()
        else:
            return self.charset_slot3.get()
        
    def schedule_conversion(self):
        current_time = time.time()
        if current_time - self.last_conversion_time < 0.5:
            return
            
        if self.conversion_timer:
            self.root.after_cancel(self.conversion_timer)
            
        self.conversion_timer = self.root.after(500, self.start_auto_conversion)
        
    def start_auto_conversion(self):
        if not self.image_path.get() or not os.path.exists(self.image_path.get()):
            return
            
        self.last_conversion_time = time.time()
        self.apply_settings()
        self.start_conversion()
        
    def load_last_image(self):
        if self.converter.config['last_image'] and os.path.exists(self.converter.config['last_image']):
            self.image_path.set(self.converter.config['last_image'])
            self.load_image_preview(self.converter.config['last_image'])
            self.root.after(100, self.start_conversion)
        else:
            print("⚠️ Last image not found")
            
    def load_image_preview(self, image_path):
        try:
            image = Image.open(image_path)
            image.thumbnail((300, 300))
            self.preview_image = ImageTk.PhotoImage(image)
            self.preview_label.configure(image=self.preview_image)
            
            info_text = f"File: {os.path.basename(image_path)}\n"
            info_text += f"Size: {image.size}\n"
            info_text += f"Format: {image.format}\n"
            info_text += f"Mode: {image.mode}"
            
            self.info_text.delete(1.0, tk.END)
            self.info_text.insert(1.0, info_text)
            
        except Exception as e:
            print(f"❌ Failed to load image: {e}")
            
    def start_conversion(self):
        if not self.image_path.get():
            print("⚠️ Select image first")
            return
            
        self.progress.start()
        self.status_var.set("Converting...")
        
        thread = threading.Thread(target=self.convert_image)
        thread.daemon = True
        thread.start()
        
    def convert_image(self):
        try:
            ascii_art = self.converter.convert(
                image_path=self.image_path.get(),
                show_config=False,
                display=False,
                save=False
            )
            
            self.root.after(0, self.conversion_complete, ascii_art)
            
        except Exception as e:
            self.root.after(0, self.conversion_error, str(e))
            
    def conversion_complete(self, ascii_art):
        self.progress.stop()
        self.ascii_text.delete(1.0, tk.END)
        self.ascii_text.insert(tk.END, ascii_art)
        self.status_var.set("Conversion complete!")
        print("✅ Conversion complete!")
        
    def conversion_error(self, error_msg):
        self.progress.stop()
        self.ascii_text.delete(1.0, tk.END)
        self.ascii_text.insert(tk.END, f"Error: {error_msg}")
        self.status_var.set(f"Error: {error_msg}")
        print(f"❌ Conversion error: {error_msg}")
        
    def update_ascii_display(self):
        if self.ascii_text:
            self.ascii_text.configure(font=('Courier New', self.font_size.get()))
            
    def copy_ascii(self):
        if self.ascii_text.get(1.0, tk.END).strip():
            self.root.clipboard_clear()
            self.root.clipboard_append(self.ascii_text.get(1.0, tk.END))
            print("✅ ASCII art copied to clipboard")
            
    def clear_ascii(self):
        self.ascii_text.delete(1.0, tk.END)
        
    def save_ascii(self):
        if not self.ascii_text.get(1.0, tk.END).strip():
            print("⚠️ No ASCII art to save")
            return
            
        filename = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=(("Text files", "*.txt"), ("All files", "*.*"))
        )
        if filename:
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(self.ascii_text.get(1.0, tk.END))
                print(f"✅ File saved: {filename}")
            except Exception as e:
                print(f"❌ Save error: {e}")
                
    def apply_settings(self):
        try:
            height = None if self.height_var.get().lower() == 'auto' else int(self.height_var.get())
            
            self.converter.set_config(
                width=int(self.width_var.get()),
                height=height,
                charset=self.get_active_charset(),
                charset_slot1=self.charset_slot1.get(),
                charset_slot2=self.charset_slot2.get(),
                charset_slot3=self.charset_slot3.get(),
                active_slot=self.active_slot.get(),
                invert=self.invert_var.get(),
                brightness=float(self.brightness_var.get()),
                contrast=float(self.contrast_var.get()),
                line_spacing=float(self.spacing_var.get())
            )
        except Exception as e:
            print(f"❌ Settings error: {e}")
            
    def reset_settings(self):
        self.width_var.set(self.converter.default_config['width'])
        self.height_var.set('auto')
        self.charset_slot1.set(self.converter.default_config['charset_slot1'])
        self.charset_slot2.set(self.converter.default_config['charset_slot2'])
        self.charset_slot3.set(self.converter.default_config['charset_slot3'])
        self.active_slot.set(self.converter.default_config['active_slot'])
        self.invert_var.set(self.converter.default_config['invert'])
        self.brightness_var.set(self.converter.default_config['brightness'])
        self.contrast_var.set(self.converter.default_config['contrast'])
        self.spacing_var.set(self.converter.default_config['line_spacing'])
        self.schedule_conversion()
        
    def update_settings_gui(self):
        self.width_var.set(self.converter.config['width'])
        self.height_var.set(str(self.converter.config['height']) if self.converter.config['height'] else 'auto')
        self.charset_slot1.set(self.converter.config.get('charset_slot1', '@%#*+=-,.'))
        self.charset_slot2.set(self.converter.config.get('charset_slot2', '@%#*+=-.: '))
        self.charset_slot3.set(self.converter.config.get('charset_slot3', '█▓▒░ '))
        self.active_slot.set(self.converter.config.get('active_slot', 1))
        self.invert_var.set(self.converter.config['invert'])
        self.brightness_var.set(self.converter.config['brightness'])
        self.contrast_var.set(self.converter.config['contrast'])
        self.spacing_var.set(self.converter.config['line_spacing'])
        
    def refresh_gallery(self):
        for item in self.gallery_tree.get_children():
            self.gallery_tree.delete(item)
            
        images = self.converter.get_images_in_folder(self.folder_path.get())
        
        for image_path in images:
            filename = os.path.basename(image_path)
            size = os.path.getsize(image_path) // 1024
            self.gallery_tree.insert('', 'end', values=(filename, f"{size} KB", image_path))
            
    def select_folder(self):
        folder = filedialog.askdirectory(title="Select image folder")
        if folder:
            self.folder_path.set(folder)
            self.refresh_gallery()
            
    def on_gallery_select(self, event):
        selection = self.gallery_tree.selection()
        if selection:
            item = self.gallery_tree.item(selection[0])
            image_path = item['values'][2]
            self.image_path.set(image_path)
            self.load_image_preview(image_path)
            self.root.after(100, self.start_conversion)
        
    def reset_all(self):
        self.image_path.set("")
        self.preview_label.configure(image='', text="Select image from gallery")
        self.info_text.delete(1.0, tk.END)
        self.ascii_text.delete(1.0, tk.END)
        self.status_var.set("Ready")

class ImageToASCII:
    def __init__(self, config_file="ascii_config.json"):
        self.config_file = config_file
        self.default_config = {
            'width': 100,
            'height': None,
            'charset': "@%#*+=-,.",
            'charset_slot1': "@%#*+=-,.",
            'charset_slot2': "@%#*+=-.: ",
            'charset_slot3': "█▓▒░ ",
            'active_slot': 1,
            'invert': False,
            'brightness': 1.0,
            'contrast': 1.0,
            'line_spacing': 0.55,
            'last_image': None
        }
        self.config = self.load_config()
    
    def load_config(self):
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    for key, value in self.default_config.items():
                        if key not in config:
                            config[key] = value
                    return config
            else:
                return self.default_config.copy()
        except Exception as e:
            print(f"❌ Config load error: {e}")
            return self.default_config.copy()
    
    def save_config(self):
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"❌ Config save error: {e}")
    
    def set_config(self, **kwargs):
        for key, value in kwargs.items():
            if key in self.config:
                self.config[key] = value
        self.save_config()
    
    def get_images_in_folder(self, folder="."):
        image_extensions = ['*.jpg', '*.jpeg', '*.png', '*.bmp', '*.gif', '*.tiff', '*.webp']
        images = []
        for extension in image_extensions:
            images.extend(glob.glob(os.path.join(folder, extension)))
            images.extend(glob.glob(os.path.join(folder, extension.upper())))
        return sorted(images)
    
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
        except Exception as e:
            print(f"❌ Image load error: {e}")
            return False
    
    def preprocess_image(self):
        if not hasattr(self, 'image'):
            raise ValueError("Load image first")
        
        grayscale_image = self.image.convert('L')
        original_width, original_height = grayscale_image.size
        
        if self.config['height'] is None:
            aspect_ratio = original_height / original_width
            height = int(self.config['width'] * aspect_ratio * self.config['line_spacing'])
        else:
            height = self.config['height']
        
        self.processed_image = grayscale_image.resize((self.config['width'], height))
        return self.processed_image
    
    def apply_image_adjustments(self, pixels):
        pixels = np.clip(pixels * self.config['brightness'], 0, 255)
        mean = np.mean(pixels)
        pixels = np.clip((pixels - mean) * self.config['contrast'] + mean, 0, 255)
        if self.config['invert']:
            pixels = 255 - pixels
        return pixels
    
    def pixels_to_ascii(self):
        if not hasattr(self, 'processed_image'):
            raise ValueError("Preprocess image first")
        
        pixels = np.array(self.processed_image)
        pixels = self.apply_image_adjustments(pixels)
        charset_length = len(self.config['charset'])
        normalized_pixels = np.clip((pixels / 255.0 * (charset_length - 1)), 0, charset_length - 1).astype(int)
        
        ascii_art = []
        for row in normalized_pixels:
            ascii_row = ''.join(self.config['charset'][pixel] for pixel in row)
            ascii_art.append(ascii_row)
        
        self.ascii_result = '\n'.join(ascii_art)
        return self.ascii_result
    
    def save_ascii(self, filename=None):
        if not hasattr(self, 'ascii_result'):
            raise ValueError("Create ASCII art first")
        
        if filename is None:
            base_name = "ascii_art"
            counter = 1
            filename = f"{base_name}.txt"
            while os.path.exists(filename):
                filename = f"{base_name}_{counter}.txt"
                counter += 1
        
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(self.ascii_result)
        return filename
    
    def convert(self, image_path=None, show_config=True, display=True, save=True):
        if image_path is None:
            return None
        
        if not self.load_image(image_path):
            return None
        
        self.preprocess_image()
        ascii_art = self.pixels_to_ascii()
        return ascii_art

def main():
    root = tk.Tk()
    app = ImageToASCIIGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()