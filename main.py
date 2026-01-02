import sys
import os
import psutil
import ctypes
import random
import subprocess
import traceback
import json
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QPushButton, QMenu, QSystemTrayIcon)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QThread, QPointF
from PyQt6.QtGui import QPainter, QColor, QBrush, QIcon, QPixmap, QAction

from config import I18N, load_settings, save_settings
from utils.treemap_logic import TreeMapItem
from utils.data_provider import GPUMonitor
from utils.worker import DataWorker
from utils.system_utils import check_startup_status, update_startup_registry, set_process_priority
from ui.treemap_widget import TreeMapWidget
from ui.dialogs import SettingsDialog, DetailWindow, ProcessChainWindow, AffinityDialog

class MainWindow(QMainWindow):
    request_data = pyqtSignal(dict)

    def __init__(self):
        super().__init__()
        
        # 优化：设置本进程优先级为“低于标准”，确保游戏优先
        set_process_priority()

        # 加载设置
        self.settings = load_settings()
        # 补全可能缺失的设置
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
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #00FF00; font-family: Consolas; font-size: 13px; padding: 2px;")
        self.status_label.setFixedHeight(25)
        
        self.settings_btn = QPushButton("")
        self.settings_btn.setFixedSize(80, 25)
        self.settings_btn.setStyleSheet("""
            QPushButton { background-color: #3E3E42; color: #CCC; border: none; font-size: 12px; }
            QPushButton:hover { background-color: #505050; color: white; }
        """)
        self.settings_btn.clicked.connect(self.open_settings)
        
        top_bar.addWidget(self.status_label, 1)
        top_bar.addWidget(self.settings_btn)
        layout.addLayout(top_bar)

        self.treemap = TreeMapWidget()
        self.treemap.itemDoubleClicked.connect(self.show_details)
        self.treemap.itemRightClicked.connect(self.on_context_menu)
        layout.addWidget(self.treemap, 1)

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_data)
        self.timer.start(self.settings.get('refresh_rate', 3000))
        
        # 系统托盘
        self.init_tray()
        
        self.apply_i18n()
        self.treemap.set_colors(self.settings.get('colors', {}))
        
        # 如果启用了自动应用 CPU 配置，在启动时应用并设置定期检查
        if self.settings.get('auto_apply_cpu_affinity', False):
            QTimer.singleShot(2000, self.apply_saved_cpu_affinity)  # 延迟2秒，确保系统稳定
            self.cpu_affinity_timer = QTimer()
            self.cpu_affinity_timer.timeout.connect(self.apply_saved_cpu_affinity)
            self.cpu_affinity_timer.start(30000)  # 30秒检查一次
        
        self.update_data()

    def init_tray(self):
        """初始化系统托盘"""
        self.tray_icon = QSystemTrayIcon(self)
        self.update_tray_icon(0, 0) # 初始显示 0%
        
        self.tray_menu = QMenu()
        self.tray_menu.setStyleSheet("""
            QMenu { background-color: #252526; color: white; border: 1px solid #444; }
            QMenu::item { padding: 5px 20px; }
            QMenu::item:selected { background-color: #094771; }
        """)
        
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

    def on_tray_icon_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger: # 单击
            if self.isVisible():
                self.hide()
            else:
                self.show_normal()

    def apply_saved_cpu_affinity(self):
        """应用保存的 CPU 配置到所有匹配的进程"""
        try:
            from config import DOCS_CONFIG_FILE
            if not os.path.exists(DOCS_CONFIG_FILE):
                return
            
            with open(DOCS_CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            cpu_configs = config.get('cpu_affinity', {})
            if not cpu_configs:
                return
            
            applied_count = 0
            for proc_path, cfg in cpu_configs.items():
                if not os.path.exists(proc_path):
                    continue
                
                cpus = cfg.get('cpus', [])
                if not cpus:
                    continue
                
                # 查找所有匹配该路径的进程
                for proc in psutil.process_iter(['pid', 'exe']):
                    try:
                        if proc.info['exe'] and os.path.normpath(proc.info['exe']) == os.path.normpath(proc_path):
                            p = psutil.Process(proc.info['pid'])
                            # 检查当前配置是否已经匹配，避免重复设置
                            current_affinity = set(p.cpu_affinity())
                            target_affinity = set(cpus)
                            if current_affinity != target_affinity:
                                p.cpu_affinity(cpus)
                                applied_count += 1
                    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                        continue
                    except Exception:
                        continue
            
            if applied_count > 0:
                print(f"Applied CPU affinity to {applied_count} process(es)")
        except Exception as e:
            print(f"Apply CPU affinity error: {e}")

    def update_tray_icon(self, ram_percent, gpu_percent, v_percent=0):
        """动态绘制系统托盘图标：柱状图形式展示内存和显存占用"""
        pixmap = QPixmap(32, 32)
        pixmap.fill(Qt.GlobalColor.transparent)
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # 柱状图参数
        bar_count = 4
        spacing = 3
        bar_width = (32 - (bar_count + 1) * spacing) // bar_count
        max_h = 24
        
        has_gpu = gpu_percent > 0 or self.settings.get('show_gpu_used', True)
        
        for i in range(bar_count):
            if has_gpu:
                # 前 2 个内存，后 2 个显存
                is_gpu_bar = (i >= 2)
                percent = gpu_percent if is_gpu_bar else ram_percent
            else:
                # 全部显示内存
                percent = ram_percent
            
            if percent < 60:
                color = QColor(0, 255, 100) # 绿色
            elif percent < 85:
                color = QColor(255, 200, 0) # 黄色
            else:
                color = QColor(255, 50, 50)  # 红色
            
            variation = random.randint(-2, 2) if percent > 0 else 0
            h = int((percent / 100.0) * max_h) + variation
            h = max(2, min(max_h, h))
            
            x = spacing + i * (bar_width + spacing)
            
            # 绘制背景灰色条
            painter.setBrush(QBrush(QColor(60, 60, 60)))
            painter.setPen(Qt.GlobalColor.transparent)
            painter.drawRect(x, 32 - spacing - max_h, bar_width, max_h)
            
            # 绘制占用条
            painter.setBrush(QBrush(color))
            painter.drawRect(x, 32 - spacing - h, bar_width, h)
            
        painter.end()
        self.tray_icon.setIcon(QIcon(pixmap))
        
        t = I18N[self.settings['lang']]
        mem_label = t['sys_mem']
        gpu_label = t['gpu_mem']
        vmem_label = t['virtual_memory']
        
        tooltip = f"{mem_label}: {ram_percent}%"
        if has_gpu:
            tooltip += f" | {gpu_label}: {int(gpu_percent)}%"
        tooltip += f" | {vmem_label}: {int(v_percent)}%"
        
        self.tray_icon.setToolTip(tooltip)

    def show_normal(self):
        self.show()
        self.activateWindow()

    def really_quit(self):
        """真正的退出程序"""
        self.tray_icon.hide()
        QApplication.quit()

    def apply_i18n(self):
        lang = self.settings.get('lang', 'zh')
        if lang not in I18N: lang = 'zh'
        t = I18N[lang]
        self.setWindowTitle(t.get('title', 'Memory Space Explorer'))
        if hasattr(self, 'settings_btn'):
            self.settings_btn.setText(t.get('settings_btn', 'Settings'))
        # 更新托盘菜单文字
        if hasattr(self, 'action_show'):
            self.action_show.setText(t.get('tray_show', 'Show'))
        if hasattr(self, 'action_exit'):
            self.action_exit.setText(t.get('tray_exit', 'Exit'))

    def open_settings(self):
        dialog = SettingsDialog(self, self.settings)
        # 绑定即时生效信号
        dialog.settingsChanged.connect(self.on_settings_changed)
        dialog.exec()

    def on_settings_changed(self):
        """当设置对话框中的任何项修改时立即调用"""
        self.apply_i18n()
        # 保存设置到文件
        save_settings(self.settings)
        # 更新颜色
        if hasattr(self, 'treemap'):
            self.treemap.set_colors(self.settings.get('colors', {}))
        # 更新开机启动状态
        update_startup_registry(self.settings.get('auto_startup', False))
        # 重置刷新计时器
        self.timer.stop()
        self.timer.start(self.settings.get('refresh_rate', 3000))
        
        # 更新 CPU 配置自动应用定时器
        if self.settings.get('auto_apply_cpu_affinity', False):
            if not hasattr(self, 'cpu_affinity_timer'):
                self.cpu_affinity_timer = QTimer()
                self.cpu_affinity_timer.timeout.connect(self.apply_saved_cpu_affinity)
            if not self.cpu_affinity_timer.isActive():
                self.cpu_affinity_timer.start(30000)  # 30秒检查一次
            # 立即应用一次
            QTimer.singleShot(1000, self.apply_saved_cpu_affinity)
        else:
            if hasattr(self, 'cpu_affinity_timer') and self.cpu_affinity_timer.isActive():
                self.cpu_affinity_timer.stop()
        
        # 立即更新一次数据
        self.update_data()

    def show_details(self, item):
        dialog = DetailWindow(self, item, self.settings['lang'])
        dialog.show()

    def on_context_menu(self, item, pos):
        # 获取该项关联的所有 PID
        pids = []
        if item.data.get('is_group') and item.children:
            # 聚合模式：提取所有子进程的 PID
            pids = [c.data.get('pid') for c in item.children if c.data.get('pid')]
        else:
            # 独立模式：提取单个 PID
            pid = item.data.get('pid')
            if pid: pids = [pid]
            
        if not pids: return # 如果没有任何有效 PID，不弹出
        
        main_pid = pids[0] # 取占用最大的进程作为代表进行路径打开或链展示
        t = I18N[self.settings['lang']]
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu { background-color: #252526; color: white; border: 1px solid #444; }
            QMenu::item { padding: 8px 25px; }
            QMenu::item:selected { background-color: #094771; }
        """)
        
        action_path = menu.addAction(t['menu_open_path'])
        action_chain = menu.addAction(t['menu_chain'])
        action_props = menu.addAction(t['menu_properties'])
        
        # 只有系统进程（有PID）才显示相关性设置
        action_affinity = None
        if item.type == 'system':
            action_affinity = menu.addAction(t['menu_affinity'])
            
        menu.addSeparator()
        action_kill = menu.addAction(t['menu_kill'])
        
        selected = menu.exec(pos.toPoint())
        
        if selected == action_path:
            self.open_process_path(main_pid)
        elif selected == action_props:
            self.open_process_properties(main_pid)
        elif selected == action_kill:
            self.kill_process(pids, item.name)
        elif selected == action_chain:
            self.show_process_chain(main_pid)
        elif action_affinity and selected == action_affinity:
            self.show_process_affinity(main_pid, item.name)

    def open_process_path(self, pid):
        try:
            p = psutil.Process(pid)
            exe_path = p.exe()
            subprocess.run(f'explorer /select,"{exe_path}"', shell=True)
        except: pass

    def open_process_properties(self, pid):
        """打开 Windows 文件属性窗口"""
        try:
            p = psutil.Process(pid)
            exe_path = p.exe()
            if not os.path.exists(exe_path): return

            # 使用 ShellExecuteEx 打开属性页
            from ctypes import wintypes
            class SHELLEXECUTEINFO(ctypes.Structure):
                _fields_ = [
                    ("cbSize", wintypes.DWORD),
                    ("fMask", ctypes.c_ulong),
                    ("hwnd", wintypes.HWND),
                    ("lpVerb", wintypes.LPCWSTR),
                    ("lpFile", wintypes.LPCWSTR),
                    ("lpParameters", wintypes.LPCWSTR),
                    ("lpDirectory", wintypes.LPCWSTR),
                    ("nShow", ctypes.c_int),
                    ("hInstApp", wintypes.HINSTANCE),
                    ("lpIDList", ctypes.c_void_p),
                    ("lpClass", wintypes.LPCWSTR),
                    ("hkeyClass", wintypes.HKEY),
                    ("dwHotKey", wintypes.DWORD),
                    ("hIconOrMonitor", wintypes.HANDLE),
                    ("hProcess", wintypes.HANDLE),
                ]

            SEE_MASK_INVOKEIDLIST = 0x0000000c
            info = SHELLEXECUTEINFO()
            info.cbSize = ctypes.sizeof(info)
            info.fMask = SEE_MASK_INVOKEIDLIST
            info.lpVerb = "properties"
            info.lpFile = exe_path
            info.nShow = 5 # SW_SHOW
            ctypes.windll.shell32.ShellExecuteExW(ctypes.byref(info))
        except Exception as e:
            print(f"Properties Error: {e}")

    def kill_process(self, pids, name):
        """支持单个 PID 或 PID 列表批量结束"""
        if isinstance(pids, int):
            pids = [pids]
            
        try:
            for pid in pids:
                try:
                    p = psutil.Process(pid)
                    p.terminate()
                except: continue
            # 延迟一小会儿刷新
            QTimer.singleShot(500, self.update_data)
        except: pass

    def show_process_chain(self, pid):
        dialog = ProcessChainWindow(self, pid, self.settings['lang'])
        dialog.show()

    def show_process_affinity(self, pid, name):
        dialog = AffinityDialog(self, pid, name, self.settings['lang'])
        dialog.exec()

    def update_data(self):
        # 1. 深度检测：全屏或无边框游戏避让模式
        is_game = False
        try:
            fg_hwnd = ctypes.windll.user32.GetForegroundWindow()
            if fg_hwnd:
                # 获取当前屏幕分辨率
                sw = ctypes.windll.user32.GetSystemMetrics(0)
                sh = ctypes.windll.user32.GetSystemMetrics(1)
                
                # 获取前台窗口矩形
                from ctypes import wintypes
                rect = wintypes.RECT()
                ctypes.windll.user32.GetWindowRect(fg_hwnd, ctypes.byref(rect))
                
                # 检测逻辑：如果窗口大小覆盖了整个屏幕且不是本软件自身
                if rect.left <= 0 and rect.top <= 0 and rect.right >= sw and rect.bottom >= sh:
                    my_hwnd = int(self.winId())
                    if fg_hwnd != my_hwnd:
                        is_game = True
        except:
            pass

        # 同步状态到 treemap
        if hasattr(self, 'treemap'):
            if self.treemap.is_game_mode != is_game:
                self.treemap.is_game_mode = is_game
                self.treemap.update()

        if is_game:
            # 进入强制暂停模式：不统计、不释放
            msg = "🎮 检测到全屏/无边框游戏：监控与释放已暂停" if self.settings['lang'] == 'zh' else "🎮 Fullscreen/Borderless Gaming: Monitoring paused"
            self.status_label.setText(msg)
            if self.timer.interval() != 30000: # 避让期间 30秒才看一眼
                self.timer.setInterval(30000)
            return

        # 2. 智能焦点感应：检测当前获得焦点的窗口
        is_focused = False
        try:
            fg_hwnd = ctypes.windll.user32.GetForegroundWindow()
            my_hwnd = int(self.winId())
            if fg_hwnd == my_hwnd:
                is_focused = True
        except:
            pass

        # 降频逻辑：如果窗口不可见（最小化）或者 焦点不在本程序上
        if not self.isVisible() or not is_focused:
            if self.timer.interval() != 10000:
                self.timer.setInterval(10000)
            self.settings['_is_silent_mode'] = True
        else:
            if self.timer.interval() != self.settings.get('refresh_rate', 3000):
                self.timer.setInterval(self.settings.get('refresh_rate', 3000))
            self.settings['_is_silent_mode'] = False
                
        self.request_data.emit(self.settings)

    def on_data_received(self, root_items, vm_info):
        try:
            lang = self.settings.get('lang', 'zh')
            if lang not in I18N: lang = 'zh'
            self.treemap.set_data(root_items, lang)
            t = I18N[lang]
            
            graph_phys_used = 0
            graph_virt_used = 0
            
            sys_group = next((item for item in root_items if item.type == 'system'), None)
            if sys_group and sys_group.children:
                for child in sys_group.children:
                    graph_phys_used += child.data.get('rss', 0)
                    graph_virt_used += child.data.get('vmem', 0)
            
            total_ram = vm_info.get('total', 0)
            v_total = vm_info.get('v_total', 0)
            
            percent = (graph_phys_used / total_ram * 100) if total_ram > 0 else 0
            sw_percent = (graph_virt_used / (v_total - total_ram) * 100) if (v_total - total_ram) > 0 else 0
            
            total_used = graph_phys_used + graph_virt_used
            v_percent = (total_used / v_total * 100) if v_total > 0 else 0

            gpu_percent = vm_info.get('gpu_percent', 0)

            warnings = []
            try:
                is_admin = ctypes.windll.shell32.IsUserAnAdmin()
                if not is_admin:
                    warnings.append(t.get('menu_affinity_warning', "[!] 建议以管理员身份运行以获取完整显存进程列表") if lang == 'zh' else "[!] Run as admin for complete GPU process list")
            except: pass
            
            if self.settings.get('show_gpu_used', True):
                gpu_items = [item for item in root_items if item.type.startswith('gpu')]
                for gpu_item in gpu_items:
                    if gpu_item.type == 'gpu' and gpu_item.children:
                        if len(gpu_item.children) == 1 and ('gpu_others' in gpu_item.children[0].name.lower() or '常驻' in gpu_item.children[0].name or 'other' in gpu_item.children[0].name.lower()):
                            warnings.append(t.get('gpu_list_empty_warning', "[!] 显存进程列表为空，请尝试以管理员身份运行") if lang == 'zh' else "[!] GPU process list empty, try running as admin")
                            break
            
            status_fmt = t.get('status_format', "RAM: {used:.1f}G/{total:.1f}G ({percent}%) | Cache(Disk): {sw_used:.1f}G/{sw_total:.1f}G ({sw_percent}%) | Commit: {v_used:.1f}G/{v_total:.1f}G ({v_percent}%) | Procs: {pids}")
            status = status_fmt.format(
                used=graph_phys_used/(1024**3),
                total=total_ram/(1024**3),
                v_used=total_used/(1024**3),
                v_total=v_total/(1024**3),
                sw_used=graph_virt_used/(1024**3),
                sw_total=(v_total - total_ram)/(1024**3),
                percent=int(percent),
                v_percent=int(v_percent),
                sw_percent=int(sw_percent),
                pids=vm_info.get('pids', 0)
            )
            
            if warnings:
                status += " | " + " | ".join(warnings)
            
            self.status_label.setText(status)
            self.update_tray_icon(int(percent), int(gpu_percent), v_percent)
        except Exception as e:
            print(f"Update UI Error: {e}")
            traceback.print_exc()

    def closeEvent(self, event):
        if self.settings.get('close_to_tray', True):
            if self.tray_icon.isVisible():
                self.hide()
                event.ignore()
                return
        
        self.worker_thread.quit()
        self.worker_thread.wait()
        self.tray_icon.hide()
        super().closeEvent(event)

if __name__ == "__main__":
    # 增加递归深度，防止 Treemap 布局在极端情况下崩溃
    sys.setrecursionlimit(2000)
    
    app = QApplication(sys.argv)
    
    try:
        window = MainWindow()
        if "--minimized" not in sys.argv:
            window.show()
        sys.exit(app.exec())
    except Exception as e:
        from PyQt6.QtWidgets import QMessageBox
        error_msg = f"程序启动失败 / Application Startup Failed:\n\n{str(e)}\n\n{traceback.format_exc()}"
        print(error_msg)
        QMessageBox.critical(None, "Fatal Error", error_msg)
        sys.exit(1)
