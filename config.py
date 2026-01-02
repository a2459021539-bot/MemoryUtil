import os
import json
from PyQt6.QtGui import QColor

# ---------------------------------------------------------
# 多语言支持
# ---------------------------------------------------------
I18N = {
    'zh': {
        'title': "Memory Space Explorer - 内存云图分析",
        'status_init': "正在获取实时内存数据...",
        'settings_btn': "⚙ 设置",
        'settings_title': "设置中心",
        'detail_title': "内存占用详情",
        'lang_label': "🌐 界面语言",
        'refresh_label': "🔄 刷新频率 (秒)",
        'display_label': "📊 显示内容",
        'show_free': "显示可用内存",
        'show_gpu_free': "显示可用 GPU 显存",
        'show_gpu_used': "显示占用 GPU 显存",
        'auto_startup': "开机自动启动",
        'tray_show': "显示界面",
        'tray_exit': "退出程序",
        'view_mode_label': "🔍 查看模式",
        'view_program': "按程序聚合",
        'view_process': "按进程独立",
        'auto_optimize_label': "🚀 自动释放空闲内存",
        'opt_interval_label': "⏱ 内存释放间隔 (秒)",
        'close_behavior_label': "🚪 关闭行为",
        'close_to_tray': "最小化到托盘",
        'close_quit': "直接退出程序",
        'color_label': "🎨 颜色自定义",
        'color_system': "物理内存 (已用)",
        'color_free': "物理内存 (空闲)",
        'color_gpu': "GPU 显存 (已用)",
        'color_gpu_free': "GPU 显存 (空闲)",
        'color_vmem': "虚拟内存 (Swap)",
        'lang_en': "English",
        'lang_zh': "简体中文",
        'free_mem': "可用内存",
        'sys_mem': "系统内存",
        'gpu_mem': "GPU 显存",
        'gpu_used': "GPU 已用",
        'gpu_free': "GPU 空闲",
        'gpu_others': "显存常驻/其他",
        'status_format': "物理: {used:.1f}G/{total:.1f}G ({percent}%) | 缓存(磁盘): {sw_used:.1f}G/{sw_total:.1f}G ({sw_percent}%) | 提交: {v_used:.1f}G/{v_total:.1f}G ({v_percent}%) | 进程: {pids}",
        'menu_open_path': "📂 打开文件所在位置",
        'menu_kill': "❌ 结束进程",
        'menu_chain': "🔗 查看进程调用链",
        'menu_properties': "📄 属性",
        'menu_affinity': "🎯 设置相关性 (核心绑定)",
        'chain_title': "进程调用链分析",
        'affinity_title': "设置 CPU 相关性 - {name}",
        'affinity_all': "所有处理器",
        'kill_confirm': "确定要结束进程 {name} (PID: {pid}) 吗？",
        'invert': "反选",
        'save_config': "保存此配置",
        'phys_label': "物理",
        'virt_label': "虚拟",
        'total_label': "总占用",
        'physical_memory': "物理内存",
        'virtual_memory': "虚拟内存",
        'ancestry_chain': "父级调用链：\n",
        'children': "\n直接子进程：\n",
        'sys_cache_kernel': "系统内核/共享/缓存"
    },
    'en': {
        'title': "Memory Space Explorer",
        'status_init': "Fetching real-time data...",
        'settings_btn': "⚙ Settings",
        'settings_title': "Settings",
        'detail_title': "Memory Details",
        'lang_label': "🌐 Language",
        'refresh_label': "🔄 Refresh Interval (s)",
        'display_label': "📊 Display Types",
        'show_free': "Show Free Memory",
        'show_gpu_free': "Show Free GPU Memory",
        'show_gpu_used': "Show Used GPU Memory",
        'auto_startup': "Run at Startup",
        'tray_show': "Show Window",
        'tray_exit': "Exit",
        'view_mode_label': "🔍 View Mode",
        'view_program': "Aggregate by Program",
        'view_process': "Individual Processes",
        'auto_optimize_label': "🚀 Auto Free Idle Memory",
        'opt_interval_label': "⏱ Optimize Interval (s)",
        'close_behavior_label': "🚪 Close Behavior",
        'close_to_tray': "Minimize to Tray",
        'close_quit': "Quit Directly",
        'color_label': "🎨 Custom Colors",
        'color_system': "RAM (Used)",
        'color_free': "RAM (Free)",
        'color_gpu': "GPU (Used)",
        'color_gpu_free': "GPU (Free)",
        'color_vmem': "Swap (Virtual)",
        'lang_en': "English",
        'lang_zh': "Chinese",
        'free_mem': "Free Memory",
        'sys_mem': "System Memory",
        'gpu_mem': "GPU Memory",
        'gpu_used': "GPU Used",
        'gpu_free': "GPU Free",
        'gpu_others': "GPU Others",
        'status_format': "RAM: {used:.1f}G/{total:.1f}G ({percent}%) | Cache(Disk): {sw_used:.1f}G/{sw_total:.1f}G ({sw_percent}%) | Commit: {v_used:.1f}G/{v_total:.1f}G ({v_percent}%) | Procs: {pids}",
        'menu_open_path': "📂 Open File Location",
        'menu_kill': "❌ Terminate Process",
        'menu_chain': "🔗 Show Process Chain",
        'menu_properties': "📄 Properties",
        'menu_affinity': "🎯 Set CPU Affinity",
        'chain_title': "Process Chain Analysis",
        'affinity_title': "Set CPU Affinity - {name}",
        'affinity_all': "All Processors",
        'kill_confirm': "Are you sure to kill {name} (PID: {pid})?",
        'invert': "Invert",
        'save_config': "Save this configuration",
        'phys_label': "Phys",
        'virt_label': "Virt",
        'total_label': "Total",
        'physical_memory': "Physical",
        'virtual_memory': "Virtual",
        'ancestry_chain': "Ancestry Chain:\n",
        'children': "\nChildren:\n",
        'sys_cache_kernel': "System Cache/Kernel"
    }
}

# ---------------------------------------------------------
# 默认配置
# ---------------------------------------------------------
DEFAULT_COLORS = {
    'system': "#2D7DDC",
    'free': "#469646",
    'gpu': "#9C27B0",
    'gpu_free': "#4A148C",
    'vmem': "#FF8C00",
    'shared': "#DC9628",
    'header': "#3C3C3D",
    'bg': "#19191C",
    'border': "#000000"
}

APP_CONFIG = {
    'refresh_interval': 2.0,
    'lang': 'zh',
    'show_free': True,
    'show_gpu_free': True,
    'show_gpu_used': True,
    'auto_startup': False,
    'view_mode': 'program',
    'auto_optimize': False,
    'opt_interval': 300,
    'close_to_tray': True,
    'colors': DEFAULT_COLORS.copy()
}

CONFIG_FILE = "config.json"
DOCS_APP_DIR = os.path.join(os.path.expanduser("~"), "Documents", "MemorySpaceExplorer")
DOCS_CONFIG_FILE = os.path.join(DOCS_APP_DIR, "config.json")

def load_settings():
    settings = APP_CONFIG.copy()
    
    # 优先从文档目录读取配置
    actual_path = None
    if os.path.exists(DOCS_CONFIG_FILE):
        actual_path = DOCS_CONFIG_FILE
    elif os.path.exists(CONFIG_FILE):
        actual_path = CONFIG_FILE
        
    if actual_path:
        try:
            with open(actual_path, 'r', encoding='utf-8') as f:
                loaded = json.load(f)
                if isinstance(loaded, dict):
                    # 深度合并，确保 colors 等嵌套字典被正确合并
                    for k, v in loaded.items():
                        if k == 'colors' and isinstance(v, dict):
                            if 'colors' not in settings: settings['colors'] = {}
                            settings['colors'].update(v)
                        else:
                            settings[k] = v
        except:
            pass
            
    # 最终确保 lang 合法
    if settings.get('lang') not in I18N:
        settings['lang'] = 'zh'
        
    return settings

def save_settings(settings):
    # 确保 settings 是完整的，如果不是，则先加载现有配置进行合并
    full_settings = load_settings()
    full_settings.update(settings)
    
    try:
        # 总是保存到文档目录
        if not os.path.exists(DOCS_APP_DIR):
            os.makedirs(DOCS_APP_DIR)
        with open(DOCS_CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(full_settings, f, indent=4, ensure_ascii=False)
    except:
        pass
    
    try:
        # 同时保存到程序目录（如果权限允许）
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(full_settings, f, indent=4, ensure_ascii=False)
    except:
        pass

def get_text(key, lang='zh'):
    return I18N.get(lang, I18N['zh']).get(key, key)

