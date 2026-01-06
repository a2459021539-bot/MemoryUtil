import sys
import os
import psutil
import subprocess
import time
import re
import xml.etree.ElementTree as ET
import traceback
from utils.treemap_logic import TreeMapItem
from config import I18N

try:
    import warnings
    # 抑制 pynvml 模块抛出的 FutureWarning
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=FutureWarning)
        import pynvml
    PYNVML_AVAILABLE = True
except ImportError:
    PYNVML_AVAILABLE = False

class GPUMonitor:
    """GPU显存监控类，支持NVIDIA和AMD显卡"""
    _nvml_initialized = False
    
    @staticmethod
    def init_nvml():
        """初始化NVIDIA Management Library"""
        if not PYNVML_AVAILABLE:
            return False
        if GPUMonitor._nvml_initialized:
            return True
        try:
            pynvml.nvmlInit()
            GPUMonitor._nvml_initialized = True
            return True
        except:
            return False
    
    _gpu_counter_cache = {}
    _last_gpu_counter_time = 0

    @staticmethod
    def get_gpu_process_memory_windows(is_silent=False):
        """使用 PowerShell 获取 Windows 进程显存占用 (识别 LUID 并匹配)"""
        if is_silent:
            return GPUMonitor._gpu_counter_cache

        current_time = time.time()
        # 强制 15 秒刷新一次 (之前是 30 秒，太长了)
        if GPUMonitor._gpu_counter_cache and (current_time - GPUMonitor._last_gpu_counter_time < 15):
            return GPUMonitor._gpu_counter_cache

        proc_mem_by_luid = {}
        try:
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE
            creation_flags = subprocess.CREATE_NO_WINDOW | 0x00004000 

            # 获取所有进程的 Local Usage (专用显存)
            # 优化：通过 Format-List 强制获取完整 Path 和 CookedValue，防止被截断
            cmd = "powershell -WindowStyle Hidden -Command \"Get-Counter '\\GPU Process Memory(*)\\Local Usage' -ErrorAction SilentlyContinue | Select-Object -ExpandProperty CounterSamples | ForEach-Object { $_.Path + ' : ' + $_.CookedValue }\""
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.DEVNULL, timeout=8, startupinfo=startupinfo, creationflags=creation_flags).decode('utf-8', errors='ignore')
            
            # 匹配格式: ...\gpu process memory(pid_14188_luid_0x00000000_0x000122ec_phys_0)\local usage : 47484928
            pattern = re.compile(r'pid_(\d+)_luid_(0x[0-9a-fA-F_]+).*?\s*:\s*(\d+)')
            
            for line in output.splitlines():
                line = line.strip()
                if not line: continue
                match = pattern.search(line)
                if match:
                    pid = int(match.group(1))
                    luid = match.group(2).lower()
                    mem = int(match.group(3))
                    if mem > 0:
                        if luid not in proc_mem_by_luid: proc_mem_by_luid[luid] = {}
                        proc_mem_by_luid[luid][pid] = proc_mem_by_luid[luid].get(pid, 0) + mem
            
            GPUMonitor._gpu_counter_cache = proc_mem_by_luid
            GPUMonitor._last_gpu_counter_time = current_time
        except Exception as e:
            print(f"PowerShell GPU Counter Error: {e}")
        return proc_mem_by_luid

    @staticmethod
    def get_gpu_info_xml(is_silent=False):
        """使用 nvidia-smi -q -x 获取GPU信息，并智能匹配 PowerShell LUID 数据"""
        gpu_list = []
        try:
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE

            # 获取 Windows 性能计数器 (按 LUID 分组)
            windows_proc_mem_by_luid = GPUMonitor.get_gpu_process_memory_windows(is_silent) if sys.platform == 'win32' else {}

            cmd = "nvidia-smi -q -x"
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.DEVNULL, timeout=5, startupinfo=startupinfo)
            root = ET.fromstring(output)

            # 预先计算每个 LUID 的总占用，用于后续匹配
            luid_totals = {luid: sum(procs.values()) for luid, procs in windows_proc_mem_by_luid.items()}

            for i, gpu in enumerate(root.findall('gpu')):
                try:
                    name_elem = gpu.find('product_name')
                    name = name_elem.text if name_elem is not None else f"GPU {i}"
                    
                    mem = gpu.find('fb_memory_usage')
                    if mem is None: continue
                    
                    total = int(mem.find('total').text.split()[0]) * 1024 * 1024
                    used = int(mem.find('used').text.split()[0]) * 1024 * 1024
                    free = int(mem.find('free').text.split()[0]) * 1024 * 1024
                    
                    # 尝试寻找匹配的 LUID
                    best_luid = None
                    min_diff = float('inf')
                    for luid, l_total in luid_totals.items():
                        diff = abs(l_total - used)
                        if diff < min_diff:
                            min_diff = diff
                            best_luid = luid
                    
                    # 如果差异太大 (例如超过 500MB)，可能没匹配对
                    if min_diff > 500 * 1024 * 1024:
                        if len(root.findall('gpu')) == 1 and len(luid_totals) >= 1:
                            best_luid = max(luid_totals.items(), key=lambda x: x[1])[0] if luid_totals else None
                    
                    matched_win_procs = windows_proc_mem_by_luid.get(best_luid, {}) if best_luid else {}

                    # 解析进程列表
                    proc_map = {}
                    procs_node = gpu.find('processes')
                    if procs_node is not None:
                        for proc in procs_node.findall('process_info'):
                            try:
                                pid_elem = proc.find('pid')
                                p_name_elem = proc.find('process_name')
                                mem_elem = proc.find('used_memory')
                                if pid_elem is not None:
                                    pid = int(pid_elem.text)
                                    p_name = p_name_elem.text if p_name_elem is not None else None
                                    
                                    mem_val = 0
                                    if mem_elem is not None and mem_elem.text != 'N/A':
                                        mem_val = int(mem_elem.text.split()[0]) * 1024 * 1024
                                    elif pid in matched_win_procs:
                                        mem_val = matched_win_procs[pid]
                                    
                                    if pid not in proc_map:
                                        proc_map[pid] = {'mem': 0, 'name': p_name}
                                    proc_map[pid]['mem'] += mem_val
                            except: continue

                    # 补充 nvidia-smi 漏掉但 PowerShell 抓到的进程
                    for pid, mem_val in matched_win_procs.items():
                        if pid not in proc_map and mem_val > 1024 * 1024:
                            proc_map[pid] = {'mem': mem_val, 'name': None}
                    
                    gpu_list.append({
                        'index': i,
                        'name': name,
                        'total': total,
                        'used': used,
                        'free': free,
                        'processes': proc_map,
                        'method': f'xml (luid:{best_luid or "none"})'
                    })
                except Exception as e:
                    print(f"Error parsing GPU {i}: {e}")
        except Exception as e:
            print(f"XML query error: {e}")
        
        return gpu_list

    @staticmethod
    def get_nvidia_gpu_info():
        """使用pynvml获取NVIDIA GPU信息 (增加 LUID 智能匹配)"""
        try:
            if not GPUMonitor.init_nvml(): return []
        except: return []
        
        gpu_list = []
        try:
            # 获取 PowerShell 显存统计 (按 LUID 分组)
            windows_proc_mem_by_luid = GPUMonitor.get_gpu_process_memory_windows() if sys.platform == 'win32' else {}
            luid_totals = {luid: sum(procs.values()) for luid, procs in windows_proc_mem_by_luid.items()}
            
            device_count = pynvml.nvmlDeviceGetCount()

            for i in range(device_count):
                try:
                    handle = pynvml.nvmlDeviceGetHandleByIndex(i)
                    name = pynvml.nvmlDeviceGetName(handle)
                    if isinstance(name, bytes): name = name.decode('utf-8', errors='ignore')
                    mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
                    used_bytes = mem_info.used

                    # 匹配 LUID
                    best_luid = None
                    min_diff = float('inf')
                    for luid, l_total in luid_totals.items():
                        diff = abs(l_total - used_bytes)
                        if diff < min_diff:
                            min_diff = diff
                            best_luid = luid
                    
                    if min_diff > 500 * 1024 * 1024 and device_count == 1 and luid_totals:
                        best_luid = max(luid_totals.items(), key=lambda x: x[1])[0]
                    
                    matched_win_procs = windows_proc_mem_by_luid.get(best_luid, {}) if best_luid else {}

                    # 获取进程信息
                    proc_map = {}
                    for fetch_func in [pynvml.nvmlDeviceGetComputeRunningProcesses, 
                                     pynvml.nvmlDeviceGetGraphicsRunningProcesses]:
                        try:
                            for proc in fetch_func(handle):
                                mem_val = proc.usedGpuMemory
                                if (not mem_val) and proc.pid in matched_win_procs:
                                    mem_val = matched_win_procs[proc.pid]
                                if mem_val:
                                    proc_map[proc.pid] = proc_map.get(proc.pid, 0) + mem_val
                        except: pass
                    
                    # 补充 PowerShell 发现的进程
                    for pid, mem_val in matched_win_procs.items():
                        if pid not in proc_map and mem_val > 1024 * 1024:
                            proc_map[pid] = mem_val

                    gpu_list.append({
                        'index': i,
                        'name': name,
                        'total': mem_info.total,
                        'used': used_bytes,
                        'free': mem_info.free,
                        'processes': proc_map,
                        'method': f'pynvml (luid:{best_luid or "none"})'
                    })
                except: continue
        except Exception as e:
            print(f"NVML Error: {e}")
        return gpu_list

    @staticmethod
    def get_nvidia_gpu_info_fallback():
        """使用nvidia-smi CSV格式作为备用方法 (增加 LUID 智能匹配)"""
        gpu_list = []
        try:
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE

            # 1. 先获取 GPU 列表和基础占用
            cmd_gpu = "nvidia-smi --query-gpu=index,name,memory.total,memory.used --format=csv,noheader,nounits"
            output_gpu = subprocess.check_output(cmd_gpu, shell=True, stderr=subprocess.DEVNULL, timeout=5, startupinfo=startupinfo).decode('utf-8', errors='ignore')
            
            if not output_gpu.strip(): return []
            
            windows_proc_mem_by_luid = GPUMonitor.get_gpu_process_memory_windows() if sys.platform == 'win32' else {}
            luid_totals = {luid: sum(procs.values()) for luid, procs in windows_proc_mem_by_luid.items()}
            
            gpu_procs_map = {}
            def collect_procs(cmd):
                try:
                    out = subprocess.check_output(cmd, shell=True, stderr=subprocess.DEVNULL, timeout=5, startupinfo=startupinfo).decode('utf-8', errors='ignore')
                    for line in out.strip().split('\n'):
                        if not line or ',' not in line: continue
                        parts = [p.strip() for p in line.split(',')]
                        if len(parts) >= 4:
                            try:
                                g_idx = int(parts[0])
                                pid = int(parts[1])
                                mem_str = parts[-1].lower().replace('mib', '').replace('mb', '').strip()
                                mem_val = int(mem_str) * 1024 * 1024
                                if g_idx not in gpu_procs_map: gpu_procs_map[g_idx] = {}
                                gpu_procs_map[g_idx][pid] = gpu_procs_map[g_idx].get(pid, 0) + mem_val
                            except: continue
                except: pass

            collect_procs("nvidia-smi --query-compute-apps=gpu_index,pid,process_name,used_memory --format=csv,noheader")
            collect_procs("nvidia-smi --query-graphics-apps=gpu_index,pid,process_name,used_memory --format=csv,noheader")

            gpu_lines = output_gpu.strip().split('\n')
            for line in gpu_lines:
                ps = [p.strip() for p in line.split(',')]
                if len(ps) < 4: continue
                g_idx = int(ps[0])
                used_bytes = int(ps[3]) * 1024 * 1024
                
                # 匹配 LUID
                best_luid = None
                min_diff = float('inf')
                for luid, l_total in luid_totals.items():
                    diff = abs(l_total - used_bytes)
                    if diff < min_diff:
                        min_diff = diff
                        best_luid = luid
                
                if min_diff > 500 * 1024 * 1024 and len(gpu_lines) == 1 and luid_totals:
                    best_luid = max(luid_totals.items(), key=lambda x: x[1])[0]

                procs = gpu_procs_map.get(g_idx, {})
                matched_win_procs = windows_proc_mem_by_luid.get(best_luid, {}) if best_luid else {}
                
                for pid, mem_val in matched_win_procs.items():
                    if pid not in procs and mem_val > 1024 * 1024:
                        procs[pid] = mem_val

                gpu_list.append({
                    'index': g_idx,
                    'name': ps[1],
                    'total': int(ps[2]) * 1024 * 1024,
                    'used': used_bytes,
                    'free': (int(ps[2]) - int(ps[3])) * 1024 * 1024,
                    'processes': procs,
                    'method': f'nvidia-smi-csv (luid:{best_luid or "none"})'
                })
        except: pass
        return gpu_list
    
    @staticmethod
    def get_generic_gpu_info():
        """使用 WMI 获取所有显卡（含核显）的基础信息"""
        gpu_list = []
        if sys.platform != 'win32': return []
        
        try:
            # 1. 通过 WMI 获取显卡列表
            cmd = "wmic path Win32_VideoController get Name, AdapterRAM /format:csv"
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.DEVNULL, timeout=5).decode('utf-8', errors='ignore')
            
            # 2. 获取 LUID 数据（通用，含核显）
            windows_proc_mem_by_luid = GPUMonitor.get_gpu_process_memory_windows()
            luid_totals = {luid: sum(procs.values()) for luid, procs in windows_proc_mem_by_luid.items()}
            
            # 记录已经通过 NVIDIA SMI 识别出的 LUID (后续可以传入或者根据已用量排除)
            # 这里暂时使用简单的过滤逻辑
            
            lines = [l.strip() for l in output.splitlines() if l.strip()]
            for line in lines[1:]: # 跳过标题
                parts = line.split(',')
                if len(parts) < 3: continue
                name = parts[2].strip()
                
                # 排除显而易见的独显或已经支持的
                if "NVIDIA" in name.upper(): continue
                
                # AdapterRAM 处理
                try:
                    # 某些核显会返回 4GB-1 (4294967295)，这其实是无效值
                    ram_val = int(parts[1])
                    if ram_val >= 4294967295 or ram_val < 0:
                        total_bytes = psutil.virtual_memory().total // 2 # 兜底方案：取系统内存一半作为共享上限
                    else:
                        total_bytes = ram_val
                except:
                    total_bytes = psutil.virtual_memory().total // 2
                
                # 匹配 LUID
                # 启发式匹配：寻找一个未被 NVIDIA 占用的、且有数值的 LUID
                best_luid = None
                used_bytes = 0
                if luid_totals:
                    # 这里的匹配逻辑可以进一步优化
                    # 目前简单取所有 LUID 中的最大值（如果只有一个核显）
                    for luid, val in luid_totals.items():
                        if val > used_bytes:
                            used_bytes = val
                            best_luid = luid
                
                gpu_list.append({
                    'index': 100 + len(gpu_list),
                    'name': name,
                    'total': total_bytes,
                    'used': used_bytes,
                    'free': max(0, total_bytes - used_bytes),
                    'processes': windows_proc_mem_by_luid.get(best_luid, {}) if best_luid else {},
                    'method': f'wmi-igpu (luid:{best_luid or "none"})'
                })
        except:
            pass
        return gpu_list

    @staticmethod
    def get_gpu_info(is_silent=False):
        """
        获取所有GPU信息，支持 NVIDIA 独显、Intel/AMD 核显等。
        优先级：
        1. NVIDIA 独显专用方案 (nvidia-smi / pynvml)
        2. Windows WMI + 性能计数器方案 (适配核显)
        """
        all_gpus = []
        try:
            # 1. 尝试获取 NVIDIA 独显信息
            nvidia_gpus = []
            try:
                nvidia_gpus = GPUMonitor.get_gpu_info_xml(is_silent)
                if not nvidia_gpus:
                    nvidia_gpus = GPUMonitor.get_nvidia_gpu_info()
            except: 
                pass
            
            all_gpus.extend(nvidia_gpus)
            
            # 2. 尝试获取核显或其他显卡信息
            generic_gpus = GPUMonitor.get_generic_gpu_info()
            for g in generic_gpus:
                # 修正去重逻辑：检查当前显卡名是否已在 all_gpus 中
                is_duplicate = any(g['name'].lower() == eg['name'].lower() for eg in all_gpus)
                is_nvidia = "NVIDIA" in g['name'].upper()
                
                if not is_duplicate and not is_nvidia:
                    all_gpus.append(g)
                    
        except Exception as e:
            print(f"GPU Discovery Error: {e}")
            
        return all_gpus

def get_process_name_extended(pid):
    """更强大的进程名获取，处理权限受限的情况"""
    try:
        p = psutil.Process(pid)
        return p.name()
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        try:
            # 尝试通过 ctypes 调用 Windows API
            import ctypes
            from ctypes import wintypes
            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            h = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
            if h:
                buffer = ctypes.create_unicode_buffer(1024)
                size = wintypes.DWORD(1024)
                if ctypes.windll.kernel32.QueryFullProcessImageNameW(h, 0, buffer, ctypes.byref(size)):
                    name = os.path.basename(buffer.value)
                    ctypes.windll.kernel32.CloseHandle(h)
                    return name
                ctypes.windll.kernel32.CloseHandle(h)
        except:
            pass
    return f"PID {pid}"

def get_memory_data(show_free=True, show_gpu_free=True, show_gpu_used=True, lang='zh', view_mode='process', is_silent=False):
    vm = psutil.virtual_memory()
    t = I18N[lang]
    root_items = []
    
    total_used_bytes = vm.total - vm.available
    
    if show_free:
        free_group = TreeMapItem(t['free_mem'], vm.available, "free")
        root_items.append(free_group)
    
    sys_group = TreeMapItem(t['sys_mem'], total_used_bytes, "system")
    procs = []
    total_proc_private = 0
    
    for p in psutil.process_iter(['pid', 'name', 'memory_info']):
        # 优化：在遍历大列表时强制让出 CPU 毫秒级时间片
        # 静默模式下稍微加长 sleep 时间，更彻底地释放 CPU
        time.sleep(0.002 if is_silent else 0.001)
        try:
            m_info = p.info['memory_info']
            if not m_info: continue
            
            # 采集物理内存(rss)和私有总占用(private)
            m_rss = m_info.rss
            m_private = getattr(m_info, 'private', m_rss)
            m_vmem = max(0, m_private - m_rss)
            
            # 使用总占用作为色块大小
            m_total = m_private
            
            if m_total > 2 * 1024 * 1024:
                p_name = p.info['name']
                if not p_name:
                    p_name = get_process_name_extended(p.info['pid'])
                procs.append(TreeMapItem(p_name, m_total, "system", data={'pid': p.info['pid'], 'rss': m_rss, 'vmem': m_vmem}))
                total_proc_private += m_private
        except: continue
            
    if view_mode == 'program':
        aggregated = {}
        for p in procs:
            if p.name not in aggregated:
                aggregated[p.name] = TreeMapItem(p.name, 0, "system", data={'is_group': True, 'rss': 0, 'vmem': 0})
            aggregated[p.name].value += p.value
            aggregated[p.name].data['rss'] += p.data['rss']
            aggregated[p.name].data['vmem'] += p.data['vmem']
            aggregated[p.name].children.append(p)
        final_procs = list(aggregated.values())
    else:
        final_procs = procs

    final_procs.sort(key=lambda x: x.value, reverse=True)
    top_procs = final_procs[:150] 
    
    # 此时总占用统计 (基于物理内存 rss 计算 gap)
    total_rss_allocated = sum(p.data.get('rss', 0) for p in procs)
    other_gap = total_used_bytes - total_rss_allocated
    
    if other_gap > 0:
        gap_name = t.get('sys_cache_kernel', "系统内核/共享/缓存")
        gap_item = TreeMapItem(gap_name, other_gap, "system", data={'rss': other_gap, 'vmem': 0})
        top_procs.append(gap_item)
        
    sys_group.children = top_procs
    sys_group.value = sum(p.value for p in top_procs)
    sys_group.data['rss'] = sum(p.data.get('rss', 0) for p in top_procs)
    sys_group.data['vmem'] = sum(p.data.get('vmem', 0) for p in top_procs)
    root_items.append(sys_group)

    # 获取 GPU 数据
    total_gpu_total = 0
    total_gpu_used_corrected = 0
    
    if show_gpu_free or show_gpu_used:
        try:
            # 传入静默模式标志
            gpu_list = GPUMonitor.get_gpu_info(is_silent)
            
            if gpu_list:
                for gpu_info in gpu_list:
                    g_idx = gpu_info['index']
                    g_name = gpu_info['name']
                    total_bytes = gpu_info['total']
                    used_bytes = gpu_info['used']
                    free_bytes = gpu_info.get('free', total_bytes - used_bytes)
                    proc_map = gpu_info.get('processes', {})
                
                    # 状态栏统计累加
                    total_gpu_total += total_bytes
                    # 这里的修正只用于计算状态栏百分比，确保与 TreeMap 的“视觉占用”一致
                    current_proc_sum = sum(p['mem'] for p in proc_map.values()) if isinstance(proc_map, dict) and any(isinstance(v, dict) for v in proc_map.values()) else sum(v for v in proc_map.values() if isinstance(v, (int, float)))
                    display_used_bytes = max(used_bytes, current_proc_sum)
                    total_gpu_used_corrected += display_used_bytes

                    # 1. GPU 可用部分 (顶级块，模仿内存分析)
                    if show_gpu_free and free_bytes > 0:
                        g_free_name = f"{g_name} - {t['gpu_free']}" if len(gpu_list) > 1 else t['gpu_free']
                        root_items.append(TreeMapItem(g_free_name, free_bytes, "gpu_free"))
                    
                    # 2. GPU 使用部分 (顶级块)
                    if show_gpu_used:
                        g_used_name = f"{g_name} - {t['gpu_used']}" if len(gpu_list) > 1 else t['gpu_used']
                        # TreeMap 绘图依然使用 display_used_bytes (保持原样)
                        gpu_used_group = TreeMapItem(g_used_name, display_used_bytes, "gpu")
                        
                        # 构建进程列表
                        current_gpu_procs = []
                        for pid, data in proc_map.items():
                            used_mem = data['mem'] if isinstance(data, dict) else data
                            proc_name = None
                            if isinstance(data, dict) and data.get('name'):
                                proc_name = os.path.basename(data['name'])
                            if not proc_name:
                                proc_name = get_process_name_extended(pid)
                            current_gpu_procs.append(TreeMapItem(proc_name, used_mem, "gpu", data={'pid': pid}))
                        
                        if view_mode == 'program':
                            agg_gpu = {}
                            for p in current_gpu_procs:
                                agg_key = p.name.lower()
                                if agg_key not in agg_gpu:
                                    agg_gpu[agg_key] = TreeMapItem(p.name, 0, "gpu", data={'is_group': True})
                                agg_gpu[agg_key].value += p.value
                                agg_gpu[agg_key].children.append(p)
                            final_gpu_procs = list(agg_gpu.values())
                        else:
                            final_gpu_procs = current_gpu_procs
                            
                        allocated_gpu = sum(p.value for p in final_gpu_procs)
                        if allocated_gpu > display_used_bytes and display_used_bytes > 0:
                            scale = display_used_bytes / allocated_gpu
                            for p in final_gpu_procs:
                                p.value *= scale
                            allocated_gpu = display_used_bytes

                        if display_used_bytes > allocated_gpu:
                            others_mem = display_used_bytes - allocated_gpu
                            final_gpu_procs.append(TreeMapItem(
                                t.get('gpu_others', "显存常驻/其他"), 
                                others_mem, 
                                "gpu"
                            ))
                        
                        gpu_used_group.children = sorted(final_gpu_procs, key=lambda x: x.value, reverse=True)
                        if gpu_used_group.value > 0:
                            root_items.append(gpu_used_group)
        except Exception as e:
            print(f"GPU Data Error: {e}")
            traceback.print_exc()

    # 计算最终要给状态栏显示的百分比
    final_gpu_percent = (total_gpu_used_corrected / total_gpu_total * 100) if total_gpu_total > 0 else 0
    return root_items, final_gpu_percent

