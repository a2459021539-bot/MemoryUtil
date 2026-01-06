import sys
import os
import traceback

# 1. 基础环境检查 (必须在所有业务导入之前)
try:
    import psutil
    import ctypes
    from PyQt6.QtWidgets import QApplication, QMessageBox
    from PyQt6.QtGui import QIcon, QPixmap
except ImportError as e:
    print(f"Critical System Import Error: {e}")
    sys.exit(1)

def exception_hook(exctype, value, tb):
    """全局未捕获异常句柄"""
    err_msg = "".join(traceback.format_exception(exctype, value, tb))
    print(err_msg)
    try:
        if QApplication.instance():
            QMessageBox.critical(None, "程序运行异常 / Critical Error", f"发生未捕获的错误：\n\n{err_msg}")
    except:
        pass
    sys.exit(1)

sys.excepthook = exception_hook

# 2. 延迟导入业务模块
try:
    import random
    import subprocess
    import json
    from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, 
                                 QHBoxLayout, QLabel, QPushButton, QMenu, QSystemTrayIcon)
    from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QThread, QPointF
    from PyQt6.QtGui import QPainter, QColor, QBrush, QAction, QFont

    from config import I18N, load_settings, save_settings
    from utils.treemap_logic import TreeMapItem
    from utils.data_provider import GPUMonitor
    from utils.worker import DataWorker
    from utils.system_utils import check_startup_status, update_startup_registry, set_process_priority
    from ui.treemap_widget import TreeMapWidget
    from ui.dialogs import SettingsDialog, DetailWindow, ProcessChainWindow, AffinityDialog
except Exception as e:
    # 捕获导入阶段的错误（如 ModuleNotFoundError）
    app = QApplication(sys.argv)
    QMessageBox.critical(None, "模块加载失败 / Module Load Error", f"导入组件时出错，这通常是由于打包配置不正确导致的：\n\n{str(e)}\n\n{traceback.format_exc()}")
    sys.exit(1)

class MainWindow(QMainWindow):
    request_data = pyqtSignal(dict)

    def __init__(self):
        super().__init__()
        # 1. 加载配置
        from config import load_settings
        self.settings = load_settings()
        # 2. 状态锁初始化 (从配置读取)
        self._last_is_game = self.settings.get('game_mode_manual', False)
        
        # 3. 预渲染游戏模式图标，确保切换时绝对成功
        self._game_icon_pixmap = QPixmap(32, 32)
        self._render_game_icon_static()
        
        self._current_game_name = ""
        self._current_game_path = ""
        
        set_process_priority()
        if 'auto_startup' not in self.settings:
            self.settings['auto_startup'] = check_startup_status()
        
        self.worker_thread = QThread()
        self.worker = DataWorker()
        self.worker.moveToThread(self.worker_thread)
        self.request_data.connect(self.worker.fetch_data)
        self.worker.data_ready.connect(self.on_data_received)
        self.worker_thread.start()

        self.resize(1200, 800)
        self.setStyleSheet("background-color: #1e1e1e;")

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(0)

        top_bar = QHBoxLayout()
        top_bar.setContentsMargins(5, 2, 5, 2)
        top_bar.setSpacing(10) # 增加组件间的间距
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #00FF00; font-family: Consolas; font-size: 13px; padding: 2px;")
        self.status_label.setFixedHeight(25)
        
        # 手动游戏模式开关容器
        game_mode_container = QWidget()
        game_mode_layout = QHBoxLayout(game_mode_container)
        game_mode_layout.setContentsMargins(0, 0, 0, 0)
        game_mode_layout.setSpacing(8) # 文本和开关之间的距离
        
        self.game_mode_lbl = QLabel("")
        self.game_mode_lbl.setStyleSheet("color: #BBB; font-size: 12px;")
        from ui.components import SwitchButton
        self.game_mode_switch = SwitchButton()
        self.game_mode_switch.setFixedSize(46, 22) # 修正：宽度改为偶数，高度保持
        self.game_mode_switch.setChecked(self.settings.get('game_mode_manual', False))
        self.game_mode_switch.clicked.connect(self.toggle_manual_game_mode)
        
        # 忽略按钮 (初始隐藏)
        self.ignore_game_btn = QPushButton("")
        self.ignore_game_btn.setFixedSize(100, 25)
        self.ignore_game_btn.setStyleSheet("""
            QPushButton { background-color: #A33; color: white; border: none; font-size: 11px; border-radius: 3px; }
            QPushButton:hover { background-color: #C44; }
        """)
        self.ignore_game_btn.setVisible(False)
        self.ignore_game_btn.clicked.connect(self.ignore_current_game)

        game_mode_layout.addWidget(self.game_mode_lbl)
        game_mode_layout.addWidget(self.game_mode_switch, 0, Qt.AlignmentFlag.AlignVCenter)
        game_mode_layout.addWidget(self.ignore_game_btn)

        self.settings_btn = QPushButton("")
        self.settings_btn.setFixedSize(80, 25)
        self.settings_btn.setStyleSheet("""
            QPushButton { background-color: #3E3E42; color: #CCC; border: none; font-size: 12px; border-radius: 3px; }
            QPushButton:hover { background-color: #505050; color: white; }
        """)
        self.settings_btn.clicked.connect(self.open_settings)
        
        top_bar.addWidget(self.status_label, 1)
        top_bar.addWidget(game_mode_container)
        top_bar.addWidget(self.settings_btn)
        layout.addLayout(top_bar)

        self.treemap = TreeMapWidget()
        self.treemap.itemDoubleClicked.connect(self.show_details)
        self.treemap.itemRightClicked.connect(self.on_context_menu)
        layout.addWidget(self.treemap, 1)

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_data)
        self.timer.start(self.settings.get('refresh_rate', 2000))
        
        self.init_tray()
        self.apply_i18n()
        self.treemap.set_colors(self.settings.get('colors', {}))
        
        if self.settings.get('auto_apply_cpu_affinity', False):
            QTimer.singleShot(2000, self.apply_saved_cpu_affinity)
            self.cpu_affinity_timer = QTimer()
            self.cpu_affinity_timer.timeout.connect(self.apply_saved_cpu_affinity)
            self.cpu_affinity_timer.start(30000)
        
        self.update_data()

    def init_tray(self):
        try:
            self.tray_icon = QSystemTrayIcon(self)
            self.update_tray_icon(0, 0, 0)
            self.tray_menu = QMenu()
            self.tray_menu.setStyleSheet("QMenu { background-color: #252526; color: white; border: 1px solid #444; } QMenu::item { padding: 5px 20px; } QMenu::item:selected { background-color: #094771; }")
            self.action_show = QAction("", self)
            self.action_show.triggered.connect(self.show_normal)
            self.action_exit = QAction("", self)
            self.action_exit.triggered.connect(self.really_quit)
            self.tray_menu.addAction(self.action_show)
            self.tray_menu.addSeparator()
            self.tray_menu.addAction(self.action_exit)
            self.tray_icon.setContextMenu(self.tray_menu)
            self.tray_icon.activated.connect(self.on_tray_icon_activated)
            self.tray_icon.show()
        except:
            print("Tray icon initialization failed.")

    def on_tray_icon_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            if self.isVisible(): self.hide()
            else: self.show_normal()

    def toggle_manual_game_mode(self):
        """手动切换游戏模式"""
        enabled = self.game_mode_switch.isChecked()
        self.settings['game_mode_manual'] = enabled
        self._last_is_game = enabled # 立即强制同步状态锁
        save_settings(self.settings)
        self.update_data()
        self.update_tray_icon(0, 0, 0) # 立即触发重绘

    def _render_game_icon_static(self):
        """预渲染游戏图标到缓存"""
        self._game_icon_pixmap.fill(Qt.GlobalColor.transparent)
        with QPainter(self._game_icon_pixmap) as painter:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            # 紫色背景
            painter.setBrush(QBrush(QColor(156, 39, 176)))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(self._game_icon_pixmap.rect().adjusted(2, 2, -2, -2), 6, 6)
            # 手柄
            font = QFont("Segoe UI Emoji")
            font.setPixelSize(22)
            painter.setFont(font)
            painter.setPen(QColor(255, 255, 255))
            painter.drawText(self._game_icon_pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "🎮")

    def apply_saved_cpu_affinity(self):
        try:
            from config import DOCS_CONFIG_FILE
            if not os.path.exists(DOCS_CONFIG_FILE): return
            with open(DOCS_CONFIG_FILE, 'r', encoding='utf-8') as f: config = json.load(f)
            cpu_configs = config.get('cpu_affinity', {})
            if not cpu_configs: return
            applied_count = 0
            for proc_path, cfg in cpu_configs.items():
                if not os.path.exists(proc_path): continue
                cpus = cfg.get('cpus', [])
                if not cpus: continue
                for proc in psutil.process_iter(['pid', 'exe']):
                    try:
                        if proc.info['exe'] and os.path.normpath(proc.info['exe']) == os.path.normpath(proc_path):
                            p = psutil.Process(proc.info['pid'])
                            if set(p.cpu_affinity()) != set(cpus):
                                p.cpu_affinity(cpus); applied_count += 1
                    except: continue
            if applied_count > 0: print(f"Applied CPU affinity to {applied_count} process(es)")
        except: pass

    def update_tray_icon(self, ram_percent, gpu_percent, v_percent=0):
        try:
            # 双重保险：同时检查配置和状态锁
            is_game = self.settings.get('game_mode_manual', False) or getattr(self, '_last_is_game', False)
            
            if is_game:
                # 【终极拦截】游戏模式下直接输出预制图标，绝不执行绘图逻辑
                game_icon = QIcon(self._game_icon_pixmap)
                self.tray_icon.setIcon(game_icon)
                self.setWindowIcon(game_icon)
                return
            
            # --- 以下仅在非游戏模式运行 ---
            pixmap = QPixmap(32, 32)
            pixmap.fill(Qt.GlobalColor.transparent)
            with QPainter(pixmap) as painter:
                painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                bar_count = 4; spacing = 3; bar_width = (32 - (bar_count + 1) * spacing) // bar_count; max_h = 24
                has_gpu = gpu_percent > 0 or self.settings.get('show_gpu_used', True)
                for i in range(bar_count):
                    percent = gpu_percent if (has_gpu and i >= 2) else ram_percent
                    color = QColor(0, 255, 100) if percent < 60 else (QColor(255, 200, 0) if percent < 85 else QColor(255, 50, 50))
                    h = max(2, min(max_h, int((percent / 100.0) * max_h) + random.randint(-2, 2) if percent > 0 else 0))
                    x = spacing + i * (bar_width + spacing)
                    painter.setBrush(QBrush(QColor(60, 60, 60))); painter.setPen(Qt.GlobalColor.transparent); painter.drawRect(x, 32 - spacing - max_h, bar_width, max_h)
                    painter.setBrush(QBrush(color)); painter.drawRect(x, 32 - spacing - h, bar_width, h)
            
            icon = QIcon(pixmap)
            self.tray_icon.setIcon(icon)
            self.setWindowIcon(icon)
            
            # 更新悬停提示
            lang = self.settings.get('lang', 'zh')
            t = I18N.get(lang, I18N['zh'])
            tooltip = f"{t.get('sys_mem', 'RAM')}: {ram_percent}%"
            if has_gpu: tooltip += f" | {t.get('gpu_mem', 'GPU')}: {int(gpu_percent)}%"
            tooltip += f" | {t.get('virtual_memory', 'Swap')}: {int(v_percent)}%"
            self.tray_icon.setToolTip(tooltip)
        except Exception as e:
            print(f"Tray Icon Update Error: {e}")

    def show_normal(self):
        self.show(); self.activateWindow()

    def really_quit(self):
        self.tray_icon.hide(); QApplication.quit()

    def apply_i18n(self):
        lang = self.settings.get('lang', 'zh')
        if lang not in I18N: lang = 'zh'
        t = I18N[lang]
        self.setWindowTitle(t.get('title', 'Memory Space Explorer'))
        if hasattr(self, 'settings_btn'): self.settings_btn.setText(t.get('settings_btn', 'Settings'))
        if hasattr(self, 'action_show'): self.action_show.setText(t.get('tray_show', 'Show'))
        if hasattr(self, 'action_exit'): self.action_exit.setText(t.get('tray_exit', 'Exit'))
        if hasattr(self, 'game_mode_lbl'): self.game_mode_lbl.setText(t.get('game_mode_manual', 'Game Mode'))
        if hasattr(self, 'ignore_game_btn'): self.ignore_game_btn.setText(t.get('game_mode_ignore', 'Ignore'))

    def _show_ignore_button(self, show):
        if hasattr(self, 'ignore_game_btn'):
            if self.ignore_game_btn.isVisible() != show:
                self.ignore_game_btn.setVisible(show)

    def ignore_current_game(self):
        """将当前触发游戏模式的程序加入忽略列表"""
        if self._current_game_path:
            if 'ignored_games' not in self.settings:
                self.settings['ignored_games'] = []
            
            if self._current_game_path not in self.settings['ignored_games']:
                self.settings['ignored_games'].append(self._current_game_path)
                save_settings(self.settings)
                # 立即刷新，退出游戏模式
                self.update_data()

    def open_settings(self):
        dialog = SettingsDialog(self, self.settings)
        dialog.settingsChanged.connect(self.on_settings_changed)
        dialog.exec()

    def on_settings_changed(self):
        self.apply_i18n(); save_settings(self.settings)
        if hasattr(self, 'game_mode_switch'):
            self.game_mode_switch.blockSignals(True)
            self.game_mode_switch.setChecked(self.settings.get('game_mode_manual', False))
            self.game_mode_switch.blockSignals(False)
        if hasattr(self, 'treemap'): self.treemap.set_colors(self.settings.get('colors', {}))
        update_startup_registry(self.settings.get('auto_startup', False))
        self.timer.stop(); self.timer.start(self.settings.get('refresh_rate', 2000))
        if self.settings.get('auto_apply_cpu_affinity', False):
            if not hasattr(self, 'cpu_affinity_timer'):
                self.cpu_affinity_timer = QTimer()
                self.cpu_affinity_timer.timeout.connect(self.apply_saved_cpu_affinity)
            if not self.cpu_affinity_timer.isActive(): self.cpu_affinity_timer.start(30000)
            QTimer.singleShot(1000, self.apply_saved_cpu_affinity)
        elif hasattr(self, 'cpu_affinity_timer') and self.cpu_affinity_timer.isActive():
            self.cpu_affinity_timer.stop()
        self.update_data()

    def show_details(self, item):
        dialog = DetailWindow(self, item, self.settings.get('lang', 'zh'))
        dialog.show()

    def on_context_menu(self, item, pos):
        pids = []
        if item.data.get('is_group') and item.children: pids = [c.data.get('pid') for c in item.children if c.data.get('pid')]
        else:
            pid = item.data.get('pid')
            if pid: pids = [pid]
        if not pids: return
        main_pid = pids[0]
        lang = self.settings.get('lang', 'zh'); t = I18N.get(lang, I18N['zh'])
        menu = QMenu(self)
        menu.setStyleSheet("QMenu { background-color: #252526; color: white; border: 1px solid #444; } QMenu::item { padding: 8px 25px; } QMenu::item:selected { background-color: #094771; }")
        action_path = menu.addAction(t.get('menu_open_path', 'Path'))
        action_chain = menu.addAction(t.get('menu_chain', 'Chain'))
        action_props = menu.addAction(t.get('menu_properties', 'Props'))
        action_affinity = menu.addAction(t.get('menu_affinity', 'Affinity')) if item.type == 'system' else None
        menu.addSeparator()
        action_kill = menu.addAction(t.get('menu_kill', 'Kill'))
        selected = menu.exec(pos.toPoint())
        if selected == action_path: self.open_process_path(main_pid)
        elif selected == action_props: self.open_process_properties(main_pid)
        elif selected == action_kill: self.kill_process(pids, item.name)
        elif selected == action_chain: self.show_process_chain(main_pid)
        elif action_affinity and selected == action_affinity: self.show_process_affinity(main_pid, item.name)

    def open_process_path(self, pid):
        try:
            p = psutil.Process(pid); exe_path = p.exe()
            subprocess.run(f'explorer /select,"{exe_path}"', shell=True)
        except: pass

    def open_process_properties(self, pid):
        try:
            p = psutil.Process(pid); exe_path = p.exe()
            if not os.path.exists(exe_path): return
            from ctypes import wintypes
            class SHELLEXECUTEINFO(ctypes.Structure):
                _fields_ = [("cbSize", wintypes.DWORD), ("fMask", ctypes.c_ulong), ("hwnd", wintypes.HWND), ("lpVerb", wintypes.LPCWSTR), ("lpFile", wintypes.LPCWSTR), ("lpParameters", wintypes.LPCWSTR), ("lpDirectory", wintypes.LPCWSTR), ("nShow", ctypes.c_int), ("hInstApp", wintypes.HINSTANCE), ("lpIDList", ctypes.c_void_p), ("lpClass", wintypes.LPCWSTR), ("hkeyClass", wintypes.HKEY), ("dwHotKey", wintypes.DWORD), ("hIconOrMonitor", wintypes.HANDLE), ("hProcess", wintypes.HANDLE)]
            info = SHELLEXECUTEINFO(); info.cbSize = ctypes.sizeof(info); info.fMask = 0x0000000c; info.lpVerb = "properties"; info.lpFile = exe_path; info.nShow = 5
            ctypes.windll.shell32.ShellExecuteExW(ctypes.byref(info))
        except: pass

    def kill_process(self, pids, name):
        if isinstance(pids, int): pids = [pids]
        try:
            for pid in pids:
                try: 
                    p = psutil.Process(pid)
                    p.terminate()
                except: continue
            
            # 立即触发数据更新，不再等待 500ms
            # 虽然进程退出可能需要零点几秒，但立即更新能提供更好的交互反馈
            self.update_data()
            
            # 200ms 后再次静默刷新一次，确保进程彻底从列表中消失
            QTimer.singleShot(200, self.update_data)
        except: pass

    def show_process_chain(self, pid):
        dialog = ProcessChainWindow(self, pid, self.settings.get('lang', 'zh'))
        dialog.show()

    def show_process_affinity(self, pid, name):
        dialog = AffinityDialog(self, pid, name, self.settings.get('lang', 'zh'))
        dialog.exec()

    def update_data(self):
        # 1. 优先使用手动设置，否则执行自动检测
        is_game = self.settings.get('game_mode_manual', False)
        trigger_name = ""
        trigger_path = ""
        
        if not is_game:
            try:
                fg_hwnd = ctypes.windll.user32.GetForegroundWindow()
                if fg_hwnd:
                    sw = ctypes.windll.user32.GetSystemMetrics(0); sh = ctypes.windll.user32.GetSystemMetrics(1)
                    from ctypes import wintypes
                    rect = wintypes.RECT(); ctypes.windll.user32.GetWindowRect(fg_hwnd, ctypes.byref(rect))
                    
                    # 判断是否全屏
                    if rect.left <= 0 and rect.top <= 0 and rect.right >= sw and rect.bottom >= sh:
                        if fg_hwnd != int(self.winId()):
                            # 获取进程信息
                            lpdw_pid = wintypes.DWORD()
                            ctypes.windll.user32.GetWindowThreadProcessId(fg_hwnd, ctypes.byref(lpdw_pid))
                            pid = lpdw_pid.value
                            
                            try:
                                p = psutil.Process(pid)
                                exe_path = p.exe()
                                # 检查是否在忽略列表中 (匹配路径或文件名)
                                ignored_list = self.settings.get('ignored_games', [])
                                if exe_path not in ignored_list and p.name() not in ignored_list:
                                    is_game = True
                                    trigger_path = exe_path
                                    # 尝试获取友好名称
                                    from utils.data_provider import get_file_description_windows
                                    trigger_name = get_file_description_windows(exe_path) or p.name()
                            except:
                                # 如果无法获取进程信息，但确实全屏且不是自己，依然进入游戏模式（兜底）
                                is_game = True
                                trigger_name = "Unknown Process"
            except: pass
        
        self._current_game_name = trigger_name
        self._current_game_path = trigger_path
        
        # 保存状态供其他回调检查，防止覆盖图标
        self._last_is_game = is_game
        
        if hasattr(self, 'treemap'):
            if self.treemap.is_game_mode != is_game: self.treemap.is_game_mode = is_game; self.treemap.update()
            
        if is_game:
            lang = self.settings.get('lang', 'zh')
            t = I18N.get(lang, I18N['zh'])
            
            # 显示触发进程名
            status_text = f"🎮 {t.get('game_mode_active', 'Game Mode Active')}"
            if trigger_name:
                status_text += f" | {t.get('game_mode_trigger', 'Trigger')}: {trigger_name}"
                # 如果是自动触发的，显示忽略按钮（通过 status_label 的交互不太方便，我们在 top_bar 加个临时按钮）
                self._show_ignore_button(True)
            else:
                self._show_ignore_button(False)
                
            self.status_label.setText(status_text)
            if self.timer.interval() != 30000: self.timer.setInterval(30000)
            self.update_tray_icon(0, 0, 0)
            return
        
        self._show_ignore_button(False)
        is_focused = False
        try: is_focused = (ctypes.windll.user32.GetForegroundWindow() == int(self.winId()))
        except: pass
        if not self.isVisible() or not is_focused:
            if self.timer.interval() != 10000: self.timer.setInterval(10000)
            self.settings['_is_silent_mode'] = True
        else:
            ref_rate = self.settings.get('refresh_rate', 2000)
            if self.timer.interval() != ref_rate: self.timer.setInterval(ref_rate)
            self.settings['_is_silent_mode'] = False
        self.request_data.emit(self.settings)

    def on_data_received(self, root_items, vm_info):
        try:
            lang = self.settings.get('lang', 'zh')
            if lang not in I18N: lang = 'zh'
            self.treemap.set_data(root_items, lang)
            t = I18N[lang]
            graph_phys_used = 0; graph_virt_used = 0
            sys_group = next((item for item in root_items if item.type == 'system'), None)
            if sys_group and sys_group.children:
                for child in sys_group.children:
                    graph_phys_used += child.data.get('rss', 0); graph_virt_used += child.data.get('vmem', 0)
            
            total_ram = vm_info.get('total', 1); v_total = vm_info.get('v_total', 1)
            # 计算虚拟内存总量 (Disk Swap)
            # 如果 Commit Limit 小于等于物理内存，说明没开分页文件，此时缓存总量记为已用量，避免显示 0.0G
            sw_total_val = max(graph_virt_used, v_total - total_ram)
            
            percent = (graph_phys_used / total_ram * 100)
            # 保护：防止除以 0，且限制最大值为 100%
            if sw_total_val > 0:
                sw_percent = min(100.0, (graph_virt_used / sw_total_val * 100))
            else:
                sw_percent = 100.0 if graph_virt_used > 0 else 0.0
            
            total_used = graph_phys_used + graph_virt_used; v_percent = (total_used / v_total * 100)
            gpu_percent = vm_info.get('gpu_percent', 0)
            
            warnings = []
            try:
                if not ctypes.windll.shell32.IsUserAnAdmin(): warnings.append(t.get('menu_affinity_warning', "[!] Suggest Run as Admin"))
            except: pass
            
            status_fmt = t.get('status_format', "RAM: {used:.1f}G/{total:.1f}G ({percent}%) | Procs: {pids}")
            status = status_fmt.format(
                used=graph_phys_used/(1024**3), 
                total=total_ram/(1024**3), 
                v_used=total_used/(1024**3), 
                v_total=v_total/(1024**3), 
                sw_used=graph_virt_used/(1024**3), 
                sw_total=sw_total_val/(1024**3), 
                percent=int(percent), 
                gpu_percent=int(gpu_percent),
                v_percent=int(v_percent), 
                sw_percent=int(sw_percent), 
                pids=vm_info.get('pids', 0)
            )
            if warnings: status += " | " + " | ".join(warnings)
            self.status_label.setText(status)
            
            # 始终尝试更新，update_tray_icon 内部会根据 _last_is_game 决定内容
            self.update_tray_icon(int(percent), int(gpu_percent), v_percent)
        except Exception as e:
            print(f"UI Update Error: {e}")

    def closeEvent(self, event):
        if self.settings.get('close_to_tray', True) and self.tray_icon.isVisible():
            self.hide(); event.ignore(); return
        self.worker_thread.quit(); self.worker_thread.wait(); self.tray_icon.hide()
        super().closeEvent(event)

if __name__ == "__main__":
    sys.setrecursionlimit(2000)
    app = QApplication(sys.argv)
    
    # --- 单实例检查 ---
    from PyQt6.QtNetwork import QLocalServer, QLocalSocket
    server_name = "MemorySpaceExplorer_SingleInstance_Server"
    
    # 尝试连接现有实例
    socket = QLocalSocket()
    socket.connectToServer(server_name)
    if socket.waitForConnected(500):
        # 如果连接成功，说明已有实例在运行
        print("Another instance is already running. Exiting.")
        sys.exit(0)
    
    # 如果没连接上，创建一个服务器监听，标记自己是第一个实例
    local_server = QLocalServer()
    if not local_server.listen(server_name):
        # 即使没连上但也监听失败（可能是上次非正常退出的残余），清理后再试
        QLocalServer.removeServer(server_name)
        local_server.listen(server_name)
    
    app.setQuitOnLastWindowClosed(False)
    try:
        window = MainWindow()
        if "--minimized" not in sys.argv: window.show()
        sys.exit(app.exec())
    except Exception as e:
        QMessageBox.critical(None, "Fatal Error", f"程序启动失败：\n{str(e)}\n\n{traceback.format_exc()}")
