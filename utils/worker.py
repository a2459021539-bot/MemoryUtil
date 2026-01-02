import sys
import psutil
import time
import ctypes
from PyQt6.QtCore import QObject, pyqtSignal
from .data_provider import get_memory_data, GPUMonitor

class DataWorker(QObject):
    data_ready = pyqtSignal(list, dict) # 发送 (root_items, vm_info)
    finished = pyqtSignal()

    def __init__(self):
        super().__init__()
        self._is_running = True
        self.is_busy = False
        self.last_optimize_time = 0

    def fetch_data(self, settings):
        """执行耗时的 I/O 操作"""
        if self.is_busy:
            return
        
        # 进一步优化：如果开启了全屏游戏，则极大幅度降低采集频率
        # 这里虽然没有自动检测，但我们可以通过 worker 的忙碌状态和 nice 值配合
        self.is_busy = True
        try:
            lang = settings['lang']
            show_free = settings['show_free']
            show_gpu_free = settings.get('show_gpu_free', True)
            show_gpu_used = settings.get('show_gpu_used', True)
            view_mode = settings.get('view_mode', 'process')
            auto_optimize = settings.get('auto_optimize', False)
            opt_interval = settings.get('optimize_interval', 30000) / 1000.0
            is_silent = settings.get('_is_silent_mode', False)
            
            # 如果开启了自动优化，且达到了间隔时间，则执行
            current_time = time.time()
            if auto_optimize and (current_time - self.last_optimize_time >= opt_interval):
                self.optimize_memory()
                self.last_optimize_time = current_time

            root_items = get_memory_data(show_free, show_gpu_free, show_gpu_used, lang, view_mode, is_silent)
            
            # 计算总体的显存占用百分比 (不受显示设置影响)
            gpu_percent = 0
            try:
                gpu_list = GPUMonitor.get_gpu_info(is_silent)
                if gpu_list:
                    total_gpu_mem = sum(g['total'] for g in gpu_list)
                    used_gpu_mem = sum(g['used'] for g in gpu_list)
                    if total_gpu_mem > 0:
                        gpu_percent = (used_gpu_mem / total_gpu_mem) * 100
            except:
                pass

            vm = psutil.virtual_memory()
            swap = psutil.swap_memory()
            vm_info = {
                'used': vm.used,
                'total': vm.total,
                'percent': vm.percent,
                'v_used': swap.used,
                'v_total': swap.total,
                'sw_used': max(0, swap.used - vm.used),
                'sw_total': max(0, swap.total - vm.total),
                'gpu_percent': gpu_percent,
                'pids': len(psutil.pids())
            }
            
            self.data_ready.emit(root_items, vm_info)
        except Exception as e:
            print(f"Worker Error: {e}")
        finally:
            self.is_busy = False
            self.finished.emit()

    def optimize_memory(self):
        """调用 Windows API 释放进程工作集内存"""
        if sys.platform != 'win32': return
        
        # 遍历所有进程并尝试 EmptyWorkingSet
        # 需要管理员权限才能处理所有进程，否则只能处理当前权限下的进程
        for proc in psutil.process_iter(['pid']):
            try:
                handle = ctypes.windll.kernel32.OpenProcess(0x001F0FFF, False, proc.info['pid'])
                if handle:
                    ctypes.windll.psapi.EmptyWorkingSet(handle)
                    ctypes.windll.kernel32.CloseHandle(handle)
            except:
                continue

