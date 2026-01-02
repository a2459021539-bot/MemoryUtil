import sys
import os
import psutil
import winreg

def check_startup_status():
    """检查注册表确认是否已设置开机启动"""
    if sys.platform != 'win32': return False
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_READ)
        # 获取当前程序路径
        app_path = sys.executable if getattr(sys, 'frozen', False) else os.path.abspath(sys.argv[0])
        # 检查是否匹配带参数的命令
        cmd = f'"{app_path}" --minimized'
        value, _ = winreg.QueryValueEx(key, "MemorySpaceExplorer")
        winreg.CloseKey(key)
        return value == cmd
    except:
        return False

def update_startup_registry(auto_startup):
    """根据设置更新注册表"""
    if sys.platform != 'win32': return
    
    app_name = "MemorySpaceExplorer"
    # 如果是打包后的环境，sys.executable 就是 exe 路径
    if getattr(sys, 'frozen', False):
        app_path = sys.executable
    else:
        app_path = os.path.abspath(sys.argv[0])

    # 启动命令带上 --minimized 参数，这样开机启动时会自动隐藏到托盘
    cmd = f'"{app_path}" --minimized'

    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_WRITE)
        if auto_startup:
            winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, cmd)
        else:
            try:
                winreg.DeleteValue(key, app_name)
            except FileNotFoundError:
                pass
        winreg.CloseKey(key)
    except Exception as e:
        print(f"Startup Registry Error: {e}")

def set_process_priority():
    """设置本进程优先级为“低于标准”，确保游戏优先"""
    try:
        p = psutil.Process(os.getpid())
        if sys.platform == 'win32':
            p.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
        else:
            p.nice(10)
    except: pass

