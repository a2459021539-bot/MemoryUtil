import os
import json
import psutil
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
                             QCheckBox, QGridLayout, QTableWidget, QTableWidgetItem, 
                             QHeaderView, QComboBox, QDoubleSpinBox, QScrollArea, 
                             QWidget, QFrame, QColorDialog, QMessageBox)
from PyQt6.QtCore import Qt, pyqtSignal, QPointF, QTimer
from PyQt6.QtGui import QColor, QFontMetrics
from ui.components import SwitchButton
from config import I18N, save_settings, DOCS_CONFIG_FILE

class ProcessChainWindow(QDialog):
    def __init__(self, parent, pid, lang='zh'):
        super().__init__(parent)
        t = I18N[lang]
        self.setWindowTitle(t['chain_title'])
        self.resize(500, 400)
        self.setStyleSheet("background-color: #1E1E1E; color: #EEE;")
        
        layout = QVBoxLayout(self)
        self.text_area = QLabel()
        self.text_area.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.text_area.setStyleSheet("font-family: Consolas; font-size: 12px; border: 1px solid #333; padding: 10px;")
        layout.addWidget(self.text_area)
        
        chain_text = self.get_process_chain(pid, lang)
        self.text_area.setText(chain_text)

    def get_process_chain(self, pid, lang):
        try:
            p = psutil.Process(pid)
            chain = []
            curr = p
            while curr:
                chain.insert(0, f"[{curr.pid}] {curr.name()}")
                curr = curr.parent()
            
            t = I18N[lang]
            result = t['ancestry_chain']
            for i, name in enumerate(chain):
                result += "  " * i + ("└─ " if i > 0 else "") + name + "\n"
            
            children = p.children()
            if children:
                result += t['children']
                for child in children:
                    result += f"  └─ [{child.pid}] {child.name()}\n"
            
            return result
        except:
            return "Process info unavailable (Access Denied or Terminated)."

class AffinityDialog(QDialog):
    def __init__(self, parent, pid, process_name, lang='zh'):
        super().__init__(parent)
        self.pid = pid
        self.lang = lang
        self.process_name = process_name
        self.process_path = None
        t = I18N[lang]
        self.setWindowTitle(t['affinity_title'].format(name=process_name))
        self.resize(400, 350)
        self.setStyleSheet("""
            QDialog { background-color: #1E1E1E; color: #EEE; }
            QPushButton {
                background-color: #007ACC;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-size: 13px;
            }
            QPushButton:hover { background-color: #0098FF; }
            QPushButton:pressed { background-color: #005A9E; }
            QCheckBox { color: #EEE; font-size: 13px; }
        """)
        
        layout = QVBoxLayout(self)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("border: 1px solid #333;")
        container = QWidget()
        self.grid = QGridLayout(container)
        scroll.setWidget(container)
        layout.addWidget(scroll)

        try:
            self.p = psutil.Process(pid)
            all_cpus = list(range(psutil.cpu_count()))
            current_affinity = set(self.p.cpu_affinity())
            try:
                self.process_path = self.p.exe()
            except:
                self.process_path = None
        except Exception as e:
            layout.addWidget(QLabel(f"Error: {e}"))
            return

        saved_affinity = None
        if self.process_path:
            saved_affinity = self.load_saved_affinity()
        
        affinity_to_use = saved_affinity if saved_affinity else current_affinity

        self.checkboxes = []
        cols = 4
        for i in all_cpus:
            cb = QCheckBox(f"CPU {i}")
            cb.setChecked(i in affinity_to_use)
            self.grid.addWidget(cb, i // cols, i % cols)
            self.checkboxes.append(cb)

        btn_layout = QHBoxLayout()
        btn_all = QPushButton(t['affinity_all'])
        btn_all.clicked.connect(self.select_all)
        btn_invert = QPushButton(t['invert'])
        btn_invert.clicked.connect(self.invert_selection)
        btn_layout.addWidget(btn_all)
        btn_layout.addWidget(btn_invert)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        self.chk_save = QCheckBox(t['save_config'])
        self.chk_save.setChecked(True)
        layout.addWidget(self.chk_save)

        btns = QHBoxLayout()
        ok_btn = QPushButton("OK")
        ok_btn.clicked.connect(self.accept_affinity)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btns.addStretch()
        btns.addWidget(ok_btn)
        btns.addWidget(cancel_btn)
        layout.addLayout(btns)

    def select_all(self):
        for cb in self.checkboxes:
            cb.setChecked(True)

    def invert_selection(self):
        for cb in self.checkboxes:
            cb.setChecked(not cb.isChecked())

    def accept_affinity(self):
        selected_cpus = [i for i, cb in enumerate(self.checkboxes) if cb.isChecked()]
        if not selected_cpus:
            return
        try:
            self.p.cpu_affinity(selected_cpus)
            if self.chk_save.isChecked() and self.process_path:
                self.save_affinity_config(selected_cpus)
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to set affinity: {e}")

    def load_saved_affinity(self):
        try:
            if not self.process_path:
                return None
            if not os.path.exists(DOCS_CONFIG_FILE):
                return None
            with open(DOCS_CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)
            cpu_configs = config.get('cpu_affinity', {})
            if self.process_path in cpu_configs:
                cpus = cpu_configs[self.process_path].get('cpus', [])
                return set(cpus) if cpus else None
            return None
        except:
            return None

    def save_affinity_config(self, cpus):
        try:
            if not self.process_path:
                return
            
            # 加载现有配置
            config = {}
            if os.path.exists(DOCS_CONFIG_FILE):
                with open(DOCS_CONFIG_FILE, 'r', encoding='utf-8') as f:
                    config = json.load(f)
            
            if 'cpu_affinity' not in config:
                config['cpu_affinity'] = {}
                
            config['cpu_affinity'][self.process_path] = {
                'name': self.process_name,
                'cpus': cpus
            }
            
            # 传递更新后的 cpu_affinity
            save_settings({'cpu_affinity': config['cpu_affinity']})
        except:
            pass

class DetailWindow(QDialog):
    def __init__(self, parent, item, lang='zh'):
        super().__init__(parent)
        self.item = item
        t = I18N[lang]
        self.setWindowTitle(f"{item.name} - {t['detail_title']}")
        self.resize(600, 500)
        self.setStyleSheet("""
            QDialog { background-color: #1E1E1E; color: white; }
            QTableWidget { 
                background-color: #252526; 
                color: #EEE; 
                gridline-color: #333; 
                border: 1px solid #333;
                selection-background-color: #094771;
            }
            QHeaderView::section { 
                background-color: #333; 
                color: white; 
                padding: 5px; 
                border: 1px solid #444;
            }
        """)
        
        layout = QVBoxLayout(self)
        header = QLabel(f"{item.name} | {t['display_label']}: {item.formatted_size()}")
        header.setStyleSheet("font-size: 16px; font-weight: bold; color: #00FF00; margin-bottom: 10px;")
        layout.addWidget(header)
        
        self.table = QTableWidget()
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(["名称 / Name", "占用 / Memory"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(1, 150)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_context_menu)
        
        display_list = item.children if item.children else [item]
        display_list = sorted(display_list, key=lambda x: x.value, reverse=True)
        self.display_list = display_list
        
        self.table.setRowCount(len(display_list))
        for i, node in enumerate(display_list):
            name_item = QTableWidgetItem(node.name)
            name_item.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
            self.table.setItem(i, 0, name_item)
            size_item = QTableWidgetItem(node.formatted_size())
            size_item.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
            size_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.table.setItem(i, 1, size_item)
        layout.addWidget(self.table)
        
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        close_btn.setStyleSheet("""
            QPushButton { background-color: #3E3E42; color: white; padding: 10px; border: none; }
            QPushButton:hover { background-color: #505050; }
        """)
        layout.addWidget(close_btn)

    def show_context_menu(self, pos):
        row = self.table.currentRow()
        if row >= 0 and row < len(self.display_list):
            item = self.display_list[row]
            if self.parent():
                self.parent().on_context_menu(item, QPointF(self.table.mapToGlobal(pos)))

class SettingsDialog(QDialog):
    settingsChanged = pyqtSignal()

    def __init__(self, parent, current_settings):
        super().__init__(parent)
        self.settings = current_settings
        self.resize(420, 720)
        self.setStyleSheet("""
            QDialog { background-color: #1E1E1E; color: #EEE; }
            QLabel { background-color: transparent; color: #BBB; font-size: 13px; }
            QLabel#GroupTitle { color: #00FFCC; font-size: 14px; font-weight: bold; margin-bottom: 8px; }
            QFrame#SectionPanel {
                background-color: #252526;
                border: 1px solid #333;
                border-radius: 10px;
            }
            QComboBox, QDoubleSpinBox { 
                background-color: #1E1E1E; color: white; border: 1px solid #444; 
                border-radius: 4px; padding: 5px; min-width: 110px;
            }
            QComboBox:hover, QDoubleSpinBox:hover { border: 1px solid #00FFCC; }
            QCheckBox { background-color: transparent; color: #EEE; font-size: 13px; }
            QCheckBox::indicator { width: 18px; height: 18px; }
            QScrollArea { border: none; background-color: transparent; }
            QWidget#ScrollContent { background-color: #1E1E1E; }
        """)
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_content = QWidget()
        scroll_content.setObjectName("ScrollContent")
        self.container = QVBoxLayout(scroll_content)
        self.container.setSpacing(20)
        self.container.setContentsMargins(10, 10, 15, 10)
        
        layout_base = self._add_section("🌐 基础设置")
        self.lbl_lang = QLabel()
        self.combo_lang = QComboBox()
        self.combo_lang.addItem("简体中文", 'zh'); self.combo_lang.addItem("English", 'en')
        self.combo_lang.setCurrentIndex(self.combo_lang.findData(self.settings.get('lang', 'zh')))
        self._add_row(layout_base, self.lbl_lang, self.combo_lang)
        self.lbl_refresh = QLabel()
        self.spin_refresh = QDoubleSpinBox(); self.spin_refresh.setRange(0.1, 60.0)
        self.spin_refresh.setValue(self.settings.get('refresh_rate', 2000) / 1000.0)
        self._add_row(layout_base, self.lbl_refresh, self.spin_refresh)

        layout_disp = self._add_section("📊 监控显示")
        self.lbl_view_mode = QLabel()
        mode_container = QWidget(); mode_container.setStyleSheet("background-color: transparent;")
        mode_h = QHBoxLayout(mode_container); mode_h.setContentsMargins(0,0,0,0)
        self.btn_view_mode = SwitchButton(); self.btn_view_mode.setChecked(self.settings.get('view_mode') == 'program')
        self.lbl_mode_text = QLabel(); self.lbl_mode_text.setStyleSheet("background-color: transparent; color: #EEE;")
        mode_h.addStretch(); mode_h.addWidget(self.lbl_mode_text); mode_h.addWidget(self.btn_view_mode)
        self._add_row(layout_disp, self.lbl_view_mode, mode_container)
        
        self.lbl_free = QLabel()
        free_container = QWidget(); free_container.setStyleSheet("background-color: transparent;")
        free_h = QHBoxLayout(free_container); free_h.setContentsMargins(0,0,0,0)
        self.btn_free = SwitchButton(); self.btn_free.setChecked(self.settings.get('show_free', True))
        self.lbl_free_text = QLabel(); self.lbl_free_text.setStyleSheet("background-color: transparent; color: #EEE;")
        free_h.addStretch(); free_h.addWidget(self.lbl_free_text); free_h.addWidget(self.btn_free)
        self._add_row(layout_disp, self.lbl_free, free_container)
        
        self.lbl_gpu_free = QLabel()
        gpu_free_container = QWidget(); gpu_free_container.setStyleSheet("background-color: transparent;")
        gpu_free_h = QHBoxLayout(gpu_free_container); gpu_free_h.setContentsMargins(0,0,0,0)
        self.btn_gpu_free = SwitchButton(); self.btn_gpu_free.setChecked(self.settings.get('show_gpu_free', True))
        self.lbl_gpu_free_text = QLabel(); self.lbl_gpu_free_text.setStyleSheet("background-color: transparent; color: #EEE;")
        gpu_free_h.addStretch(); gpu_free_h.addWidget(self.lbl_gpu_free_text); gpu_free_h.addWidget(self.btn_gpu_free)
        self._add_row(layout_disp, self.lbl_gpu_free, gpu_free_container)
        
        self.lbl_gpu_used = QLabel()
        gpu_used_container = QWidget(); gpu_used_container.setStyleSheet("background-color: transparent;")
        gpu_used_h = QHBoxLayout(gpu_used_container); gpu_used_h.setContentsMargins(0,0,0,0)
        self.btn_gpu_used = SwitchButton(); self.btn_gpu_used.setChecked(self.settings.get('show_gpu_used', True))
        self.lbl_gpu_used_text = QLabel(); self.lbl_gpu_used_text.setStyleSheet("background-color: transparent; color: #EEE;")
        gpu_used_h.addStretch(); gpu_used_h.addWidget(self.lbl_gpu_used_text); gpu_used_h.addWidget(self.btn_gpu_used)
        self._add_row(layout_disp, self.lbl_gpu_used, gpu_used_container)
        
        self.lbl_startup = QLabel()
        startup_container = QWidget(); startup_container.setStyleSheet("background-color: transparent;")
        startup_h = QHBoxLayout(startup_container); startup_h.setContentsMargins(0,0,0,0)
        self.btn_startup = SwitchButton(); self.btn_startup.setChecked(self.settings.get('auto_startup', False))
        self.lbl_startup_text = QLabel(); self.lbl_startup_text.setStyleSheet("background-color: transparent; color: #EEE;")
        startup_h.addStretch(); startup_h.addWidget(self.lbl_startup_text); startup_h.addWidget(self.btn_startup)
        self._add_row(layout_disp, self.lbl_startup, startup_container)

        layout_opt = self._add_section("🚀 内存优化")
        self.lbl_auto_opt = QLabel()
        auto_opt_container = QWidget(); auto_opt_container.setStyleSheet("background-color: transparent;")
        auto_opt_h = QHBoxLayout(auto_opt_container); auto_opt_h.setContentsMargins(0,0,0,0)
        self.btn_auto_opt = SwitchButton(); self.btn_auto_opt.setChecked(self.settings.get('auto_optimize', False))
        self.lbl_auto_opt_text = QLabel(); self.lbl_auto_opt_text.setStyleSheet("background-color: transparent; color: #EEE;")
        auto_opt_h.addStretch(); auto_opt_h.addWidget(self.lbl_auto_opt_text); auto_opt_h.addWidget(self.btn_auto_opt)
        self._add_row(layout_opt, self.lbl_auto_opt, auto_opt_container)
        self.lbl_opt_interval = QLabel()
        self.spin_opt_interval = QDoubleSpinBox(); self.spin_opt_interval.setRange(1.0, 3600.0)
        self.spin_opt_interval.setValue(self.settings.get('optimize_interval', 30000) / 1000.0)
        self._add_row(layout_opt, self.lbl_opt_interval, self.spin_opt_interval)

        layout_close = self._add_section("🚪 退出行为")
        self.lbl_close_behavior = QLabel()
        close_container = QWidget(); close_container.setStyleSheet("background-color: transparent;")
        close_h = QHBoxLayout(close_container); close_h.setContentsMargins(0,0,0,0)
        self.btn_close_behavior = SwitchButton(); self.btn_close_behavior.setChecked(self.settings.get('close_to_tray', True))
        self.lbl_close_text = QLabel(); self.lbl_close_text.setStyleSheet("background-color: transparent; color: #EEE;")
        close_h.addStretch(); close_h.addWidget(self.lbl_close_text); close_h.addWidget(self.btn_close_behavior)
        self._add_row(layout_close, self.lbl_close_behavior, close_container)

        layout_color = self._add_section("🎨 视觉颜色")
        self.color_buttons = {}
        color_types = [('system', 'color_system'), ('free', 'color_free'), ('gpu', 'color_gpu'), ('gpu_free', 'color_gpu_free'), ('vmem', 'color_vmem')]
        colors = self.settings.get('colors', {})
        for key, label_key in color_types:
            lbl = QLabel(); btn = QPushButton(); btn.setFixedSize(45, 22); btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setAutoDefault(False); btn.setDefault(False); btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            c_val = colors.get(key, "#888888")
            btn.setStyleSheet(f"background-color: {c_val}; border: 1px solid #555; border-radius: 4px;")
            btn.clicked.connect(lambda checked, k=key: self.pick_color(k))
            self._add_row(layout_color, lbl, btn)
            self.color_buttons[key] = (lbl, btn)

        layout_cpu = self._add_section("⚙️ CPU 配置管理")
        self.lbl_cpu_configs = QLabel()
        lang = self.settings.get('lang', 'zh')
        self.lbl_cpu_configs.setText("已保存的 CPU 配置" if lang == 'zh' else "Saved CPU Configurations")
        layout_cpu.addWidget(self.lbl_cpu_configs)
        self.cpu_config_list = QTableWidget()
        self.cpu_config_list.setColumnCount(3)
        self.cpu_config_list.setHorizontalHeaderLabels(["程序名称", "路径", "CPU 核心"] if lang == 'zh' else ["Program", "Path", "CPU Cores"])
        self.cpu_config_list.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.cpu_config_list.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.cpu_config_list.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self.cpu_config_list.setColumnWidth(2, 200)
        self.cpu_config_list.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.cpu_config_list.setStyleSheet("""
            QTableWidget { background-color: #252526; color: #EEE; gridline-color: #333; border: 1px solid #333; }
            QHeaderView::section { background-color: #333; color: white; padding: 5px; border: 1px solid #444; }
        """)
        self.cpu_config_list.setMaximumHeight(200)
        layout_cpu.addWidget(self.cpu_config_list)
        cpu_btn_layout = QHBoxLayout()
        self.btn_refresh_cpu = QPushButton("刷新" if lang == 'zh' else "Refresh")
        self.btn_refresh_cpu.clicked.connect(self.refresh_cpu_configs)
        self.btn_delete_cpu = QPushButton("删除选中" if lang == 'zh' else "Delete Selected")
        self.btn_delete_cpu.clicked.connect(self.delete_cpu_config)
        cpu_btn_layout.addWidget(self.btn_refresh_cpu)
        cpu_btn_layout.addWidget(self.btn_delete_cpu)
        cpu_btn_layout.addStretch()
        layout_cpu.addLayout(cpu_btn_layout)
        self.lbl_auto_apply_cpu = QLabel()
        auto_apply_container = QWidget(); auto_apply_container.setStyleSheet("background-color: transparent;")
        auto_apply_h = QHBoxLayout(auto_apply_container); auto_apply_h.setContentsMargins(0,0,0,0)
        self.btn_auto_apply_cpu = SwitchButton(); self.btn_auto_apply_cpu.setChecked(self.settings.get('auto_apply_cpu_affinity', False))
        self.lbl_auto_apply_cpu_text = QLabel(); self.lbl_auto_apply_cpu_text.setStyleSheet("background-color: transparent; color: #EEE;")
        auto_apply_h.addStretch(); auto_apply_h.addWidget(self.lbl_auto_apply_cpu_text); auto_apply_h.addWidget(self.btn_auto_apply_cpu)
        self._add_row(layout_cpu, self.lbl_auto_apply_cpu, auto_apply_container)
        
        self.container.addStretch()
        scroll.setWidget(scroll_content)
        main_layout.addWidget(scroll)

        btn_layout = QHBoxLayout()
        self.btn_done = QPushButton("完成")
        self.btn_done.setFixedSize(120, 35)
        self.btn_done.setCursor(Qt.CursorShape.PointingHandCursor); self.btn_done.setDefault(True)
        self.btn_done.setStyleSheet("""
            QPushButton { background-color: #007ACC; color: white; border-radius: 6px; font-weight: bold; font-size: 13px; border: none; }
            QPushButton:hover { background-color: #0098FF; }
            QPushButton:pressed { background-color: #005A9E; }
        """)
        self.btn_done.clicked.connect(self.accept)
        btn_layout.addStretch(); btn_layout.addWidget(self.btn_done); btn_layout.addStretch()
        main_layout.addLayout(btn_layout)
        
        self.combo_lang.currentIndexChanged.connect(self.on_lang_changed)
        self.spin_refresh.valueChanged.connect(self.sync_settings)
        self.btn_view_mode.clicked.connect(self.sync_settings)
        self.btn_close_behavior.clicked.connect(self.sync_settings)
        self.btn_auto_opt.clicked.connect(self.sync_settings)
        self.spin_opt_interval.valueChanged.connect(self.sync_settings)
        self.btn_free.clicked.connect(self.sync_settings)
        self.btn_gpu_free.clicked.connect(self.sync_settings)
        self.btn_gpu_used.clicked.connect(self.sync_settings)
        self.btn_startup.clicked.connect(self.sync_settings)
        self.btn_auto_apply_cpu.clicked.connect(self.sync_settings)

        self.retranslate_ui()
        self.refresh_cpu_configs()

    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(100, lambda: self.btn_done.setFocus() if hasattr(self, 'btn_done') else None)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Return or event.key() == Qt.Key.Key_Enter:
            focused_widget = self.focusWidget()
            if focused_widget and isinstance(focused_widget, QPushButton):
                for key, (lbl, btn) in self.color_buttons.items():
                    if focused_widget == btn:
                        event.ignore()
                        return
            if hasattr(self, 'btn_done'):
                self.btn_done.click()
                return
        super().keyPressEvent(event)

    def _add_section(self, title_text):
        panel = QFrame(); panel.setObjectName("SectionPanel")
        panel_layout = QVBoxLayout(panel); panel_layout.setContentsMargins(15, 12, 15, 15); panel_layout.setSpacing(0)
        
        class ClickableTitle(QWidget):
            def __init__(self, text, content_widget, arrow_label):
                super().__init__()
                self.content_widget = content_widget; self.arrow_label = arrow_label
                self.setStyleSheet("QWidget { background-color: transparent; border: none; } QWidget:hover { background-color: rgba(0, 255, 204, 0.1); }")
                self.setCursor(Qt.CursorShape.PointingHandCursor); self.setFixedHeight(32)
                layout = QHBoxLayout(self); layout.setContentsMargins(0, 0, 0, 0); layout.setSpacing(8); layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)
                arrow_label.setAlignment(Qt.AlignmentFlag.AlignCenter); arrow_label.setFixedSize(16, 16)
                arrow_label.setStyleSheet("QLabel { color: #00FFCC; font-size: 11px; font-weight: bold; background-color: transparent; padding: 0px; }")
                layout.addWidget(arrow_label, alignment=Qt.AlignmentFlag.AlignVCenter)
                title = QLabel(text); title.setObjectName("GroupTitle")
                title.setStyleSheet("color: #00FFCC; font-size: 14px; font-weight: bold; background-color: transparent; padding: 0px; margin: 0px; line-height: 1.0;")
                title.setCursor(Qt.CursorShape.PointingHandCursor); title.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter); title.setMinimumHeight(16)
                layout.addWidget(title, alignment=Qt.AlignmentFlag.AlignVCenter); layout.addStretch()
            def mousePressEvent(self, event):
                if event.button() == Qt.MouseButton.LeftButton:
                    is_expanded = self.content_widget.isVisible(); self.content_widget.setVisible(not is_expanded)
                    self.arrow_label.setText("▼" if not is_expanded else "▶")
        
        content_widget = QWidget(); content_widget.setObjectName("SectionContent")
        content_layout = QVBoxLayout(content_widget); content_layout.setContentsMargins(0, 8, 0, 0); content_layout.setSpacing(10); content_widget.setVisible(True)
        arrow_label = QLabel("▼"); clickable_title = ClickableTitle(title_text, content_widget, arrow_label)
        panel_layout.addWidget(clickable_title); panel_layout.addWidget(content_widget)
        self.container.addWidget(panel)
        return content_layout

    def _add_row(self, parent_layout, label_widget, control_widget):
        row = QHBoxLayout()
        if label_widget: row.addWidget(label_widget)
        row.addStretch(); row.addWidget(control_widget); parent_layout.addLayout(row)

    def on_lang_changed(self):
        self.settings['lang'] = self.combo_lang.currentData()
        self.retranslate_ui()
        self.settingsChanged.emit()

    def pick_color(self, key):
        current_color = self.settings.get('colors', {}).get(key, "#888888")
        c = QColorDialog.getColor(QColor(current_color), self, "Select Color")
        if c.isValid():
            hex_c = c.name().upper()
            if 'colors' not in self.settings: self.settings['colors'] = {}
            self.settings['colors'][key] = hex_c
            self.color_buttons[key][1].setStyleSheet(f"background-color: {hex_c}; border: 1px solid #666; border-radius: 3px;")
            self.settingsChanged.emit()

    def retranslate_ui(self):
        lang = self.settings.get('lang', 'zh')
        if lang not in I18N: lang = 'zh'
        t = I18N[lang]
        self.setWindowTitle(t['settings_title'])
        self.lbl_lang.setText(t['lang_label']); self.lbl_refresh.setText(t['refresh_label'])
        self.spin_refresh.setSuffix(" s"); self.lbl_view_mode.setText(t['view_mode_label'])
        self.lbl_auto_opt.setText(t.get('auto_optimize_label', 'Auto Optimize'))
        self.lbl_opt_interval.setText(t.get('opt_interval_label', 'Interval'))
        self.spin_opt_interval.setSuffix(" s")
        self.lbl_free.setText(t['show_free']); self.lbl_gpu_free.setText(t['show_gpu_free'])
        self.lbl_gpu_used.setText(t['show_gpu_used']); self.lbl_startup.setText(t['auto_startup'])
        self.lbl_close_behavior.setText(t['close_behavior_label'])
        if hasattr(self, 'lbl_cpu_configs'):
            lang = self.settings.get('lang', 'zh')
            self.lbl_cpu_configs.setText("已保存的 CPU 配置" if lang == 'zh' else "Saved CPU Configurations")
            self.cpu_config_list.setHorizontalHeaderLabels(["程序名称", "路径", "CPU 核心"] if lang == 'zh' else ["Program", "Path", "CPU Cores"])
            self.btn_refresh_cpu.setText("刷新" if lang == 'zh' else "Refresh")
            self.btn_delete_cpu.setText("删除选中" if lang == 'zh' else "Delete Selected")
            self.lbl_auto_apply_cpu.setText("开机自动应用 CPU 配置" if lang == 'zh' else "Auto Apply CPU Affinity on Startup")
        for key, label_key in [('system', 'color_system'), ('free', 'color_free'), ('gpu', 'color_gpu'), ('gpu_free', 'color_gpu_free'), ('vmem', 'color_vmem')]:
            if key in self.color_buttons: self.color_buttons[key][0].setText(t[label_key])
        self.combo_lang.blockSignals(True)
        self.combo_lang.setItemText(0, t['lang_zh']); self.combo_lang.setItemText(1, t['lang_en'])
        self.combo_lang.blockSignals(False)
        self.update_toggle_text()

    def update_toggle_text(self):
        lang = self.settings.get('lang', 'zh')
        if lang not in I18N: lang = 'zh'
        t = I18N[lang]
        if hasattr(self, 'lbl_mode_text'): self.lbl_mode_text.setText(t['view_program'] if self.btn_view_mode.isChecked() else t['view_process'])
        if hasattr(self, 'lbl_close_text'): self.lbl_close_text.setText(t['close_to_tray'] if self.btn_close_behavior.isChecked() else t['close_quit'])
        
        # 修正：直接检查属性是否存在并设置文本
        toggles = [
            (getattr(self, 'lbl_free_text', None), self.btn_free),
            (getattr(self, 'lbl_gpu_free_text', None), self.btn_gpu_free),
            (getattr(self, 'lbl_gpu_used_text', None), self.btn_gpu_used),
            (getattr(self, 'lbl_startup_text', None), self.btn_startup),
            (getattr(self, 'lbl_auto_apply_cpu_text', None), self.btn_auto_apply_cpu)
        ]
        
        for lbl, btn in toggles:
            if lbl:
                lbl.setText(("开启" if btn.isChecked() else "关闭") if lang == 'zh' else ("ON" if btn.isChecked() else "OFF"))

    def sync_settings(self):
        self.settings['refresh_rate'] = int(self.spin_refresh.value() * 1000)
        self.settings['view_mode'] = 'program' if self.btn_view_mode.isChecked() else 'process'
        self.settings['close_to_tray'] = self.btn_close_behavior.isChecked()
        self.settings['auto_optimize'] = self.btn_auto_opt.isChecked()
        self.settings['optimize_interval'] = int(self.spin_opt_interval.value() * 1000)
        self.settings['show_free'] = self.btn_free.isChecked()
        self.settings['show_gpu_free'] = self.btn_gpu_free.isChecked()
        self.settings['show_gpu_used'] = self.btn_gpu_used.isChecked()
        self.settings['auto_startup'] = self.btn_startup.isChecked()
        self.settings['auto_apply_cpu_affinity'] = self.btn_auto_apply_cpu.isChecked()
        self.update_toggle_text(); self.settingsChanged.emit()

    def refresh_cpu_configs(self):
        try:
            if not os.path.exists(DOCS_CONFIG_FILE): return
            with open(DOCS_CONFIG_FILE, 'r', encoding='utf-8') as f: config = json.load(f)
            cpu_configs = config.get('cpu_affinity', {})
            self.cpu_config_list.setRowCount(len(cpu_configs))
            for row, (path, cfg) in enumerate(cpu_configs.items()):
                name = cfg.get('name', os.path.basename(path))
                cpus = cfg.get('cpus', [])
                cpus_str = ', '.join(map(str, sorted(cpus))) if cpus else ("无" if self.settings.get('lang', 'zh') == 'zh' else "None")
                for col, text in enumerate([name, path, cpus_str]):
                    it = QTableWidgetItem(text); it.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
                    self.cpu_config_list.setItem(row, col, it)
        except: pass

    def delete_cpu_config(self):
        try:
            row = self.cpu_config_list.currentRow()
            if row < 0: return
            path = self.cpu_config_list.item(row, 1).text()
            
            # 使用 save_settings 的合并功能，只传递需要修改的部分
            # 但 cpu_affinity 是嵌套的，所以我们需要先加载
            if not os.path.exists(DOCS_CONFIG_FILE): return
            with open(DOCS_CONFIG_FILE, 'r', encoding='utf-8') as f: config = json.load(f)
            
            if 'cpu_affinity' in config and path in config['cpu_affinity']:
                del config['cpu_affinity'][path]
                save_settings({'cpu_affinity': config['cpu_affinity']})
                self.refresh_cpu_configs()
        except: pass

