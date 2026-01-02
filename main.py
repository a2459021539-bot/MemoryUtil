import sys
import psutil
import subprocess
import json
import os
import ctypes
import time
import winreg
import re
import random
import traceback
import xml.etree.ElementTree as ET
try:
    import pynvml
    PYNVML_AVAILABLE = True
except ImportError:
    PYNVML_AVAILABLE = False
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QFrame, QPushButton, QDialog,
                             QCheckBox, QRadioButton, QButtonGroup, QGridLayout,
                             QTableWidget, QTableWidgetItem, QHeaderView, QMenu,
                             QComboBox, QDoubleSpinBox, QSystemTrayIcon, QColorDialog, QScrollArea)
from PyQt6.QtCore import Qt, QTimer, QRectF, QPointF, pyqtSignal, QObject, QThread
from PyQt6.QtGui import (QPainter, QColor, QPen, QBrush, QFont, QLinearGradient, 
                         QGradient, QFontMetrics, QAction, QIcon, QPixmap)

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
        'kill_confirm': "确定要结束进程 {name} (PID: {pid}) 吗？"
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
        'kill_confirm': "Are you sure to kill {name} (PID: {pid})?"
    }
}

# ---------------------------------------------------------
# 核心逻辑：Treemap 算法
# ---------------------------------------------------------
class TreeMapItem:
    def __init__(self, name, value, item_type="process", data=None):
        self.name = name
        self.value = value
        self.type = item_type
        self.data = data or {}
        self.rect = QRectF(0, 0, 0, 0)
        self.children = [] # 如果有子节点，则它是分组

    def formatted_size(self):
        val = self.value
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if val < 1024.0:
                return f"{val:.2f} {unit}"
            val /= 1024.0
        return f"{val:.2f} PB"

def squarify_layout(items, x, y, width, height):
    """
    对一组 items 进行 squarify 布局计算。
    """
    # 过滤掉 value 为 0 的项，避免后续计算出现除以零错误
    valid_items = [i for i in items if i.value > 0]
    
    if not valid_items or width <= 0 or height <= 0:
        return []

    total_value = sum(item.value for item in valid_items)
    if total_value == 0: return []

    # 归一化：将 value 映射到面积
    total_area = width * height
    for item in valid_items:
        item.area = (item.value / total_value) * total_area

    result_items = []
    _squarify_recursive(sorted(valid_items, key=lambda x: x.area, reverse=True), [], x, y, width, height, result_items)
    return result_items

def _squarify_recursive(children, row, x, y, width, height, result):
    if not children:
        _layout_row(row, x, y, width, height, result)
        return

    child = children[0]
    side = min(width, height)
    
    if not row:
        _squarify_recursive(children[1:], [child], x, y, width, height, result)
    else:
        current_worst = _worst(row, side)
        next_worst = _worst(row + [child], side)
        
        if current_worst >= next_worst:
            _squarify_recursive(children[1:], row + [child], x, y, width, height, result)
        else:
            _layout_row(row, x, y, width, height, result)
            row_area = sum(n.area for n in row)
            if width < height:
                # 垂直剩余
                h_used = row_area / width
                _squarify_recursive(children, [], x, y + h_used, width, height - h_used, result)
            else:
                # 水平剩余
                w_used = row_area / height
                _squarify_recursive(children, [], x + w_used, y, width - w_used, height, result)

def _worst(row, side):
    if not row or side == 0: return float('inf')
    row_area = sum(n.area for n in row)
    if row_area == 0: return float('inf')
    
    max_area = max(n.area for n in row)
    min_area = min(n.area for n in row)
    
    if min_area == 0: return float('inf')
    
    return max((side**2 * max_area) / (row_area**2), (row_area**2) / (side**2 * min_area))

def _layout_row(row, x, y, width, height, result):
    if not row: return
    row_area = sum(n.area for n in row)
    if width < height:
        row_height = row_area / width if width > 0 else 0
        curr_x = x
        for node in row:
            w = node.area / row_height if row_height > 0 else 0
            node.rect = QRectF(curr_x, y, w, row_height)
            curr_x += w
            result.append(node)
    else:
        row_width = row_area / height if height > 0 else 0
        curr_y = y
        for node in row:
            h = node.area / row_width if row_width > 0 else 0
            node.rect = QRectF(x, curr_y, row_width, h)
            curr_y += h
            result.append(node)

# ---------------------------------------------------------
# UI 组件：TreeMapWidget (高密度云图渲染)
# ---------------------------------------------------------
class TreeMapWidget(QWidget):
    # 定义双击信号，传递被双击的项目
    itemDoubleClicked = pyqtSignal(object)
    # 定义右键信号
    itemRightClicked = pyqtSignal(object, QPointF)

    def __init__(self):
        super().__init__()
        self.root_items = []
        self.lang = 'zh' # 默认语言
        self.is_game_mode = False
        self.setMouseTracking(True)
        self.hovered_item = None
        
        # 配色方案 (初始默认值，稍后会由 MainWindow 同步)
        self.colors = {
            'system': QColor(45, 125, 220),  # 蓝色
            'free': QColor(70, 150, 70),    # 绿色
            'gpu': QColor(156, 39, 176),    # 亮紫色
            'gpu_free': QColor(74, 20, 140), # 深紫色
            'vmem': QColor(255, 140, 0),    # 琥珀橙
            'shared': QColor(220, 150, 40), # 橙色
            'header': QColor(60, 60, 65),   # 头部条背景
            'bg': QColor(25, 25, 28),       # 总背景
            'border': QColor(0, 0, 0, 100)  # 边框
        }

    def set_colors(self, color_map):
        """由 MainWindow 调用，更新自定义颜色"""
        for key, hex_val in color_map.items():
            if key in self.colors:
                self.colors[key] = QColor(hex_val)
        self.update()

    def set_data(self, root_items, lang='zh'):
        self.root_items = root_items
        self.lang = lang
        self.recalculate_layout()

    def recalculate_layout(self):
        if not self.root_items:
            self.update()
            return
            
        w, h = self.width(), self.height()
        if w <= 0 or h <= 0: return

        # 1. 第一级：拆分系统和 GPU
        sys_items = [i for i in self.root_items if not i.type.startswith('gpu')]
        gpu_items = [i for i in self.root_items if i.type.startswith('gpu')]
        
        # 计算系统总值和 GPU 总值
        total_val = sum(i.value for i in self.root_items)
        sys_val = sum(i.value for i in sys_items)
        gpu_val = sum(i.value for i in gpu_items)

        if gpu_items and sys_items:
            gpu_ratio = max(0.15, min(0.5, gpu_val / (sys_val + gpu_val) if (sys_val + gpu_val) > 0 else 0.3))
            sys_w = w * (1 - gpu_ratio)
            gpu_w = w - sys_w
        else:
            sys_w, gpu_w = (w, 0) if sys_items else (0, w)

        # 2. 第二级：系统区域内部拆分 (占用 vs 空闲) - 左右布局
        if sys_w > 0:
            sys_used = [i for i in sys_items if i.type == 'system']
            sys_free = [i for i in sys_items if i.type == 'free']
            total_sys = sum(i.value for i in sys_items)
            
            if sys_used and sys_free:
                free_ratio = sum(i.value for i in sys_free) / total_sys
                # 限制空闲区域比例
                free_ratio = max(0.1, min(0.8, free_ratio))
                used_w = sys_w * (1 - free_ratio)
                squarify_layout(sys_used, 0, 0, used_w, h)
                squarify_layout(sys_free, used_w, 0, sys_w - used_w, h)
            else:
                squarify_layout(sys_items, 0, 0, sys_w, h)

        # 3. 第二级：GPU 区域内部拆分 (占用 vs 空闲) - 上下布局
        if gpu_w > 0:
            gpu_used = [i for i in gpu_items if i.type == 'gpu']
            gpu_free = [i for i in gpu_items if i.type == 'gpu_free']
            total_gpu = sum(i.value for i in gpu_items)

            if gpu_used and gpu_free:
                free_ratio = sum(i.value for i in gpu_free) / total_gpu
                # 限制空闲高度比例
                free_ratio = max(0.1, min(0.8, free_ratio))
                free_h = h * free_ratio
                used_h = h - free_h
                squarify_layout(gpu_used, sys_w, 0, gpu_w, used_h)
                squarify_layout(gpu_free, sys_w, used_h, gpu_w, free_h)
            else:
                squarify_layout(gpu_items, sys_w, 0, gpu_w, h)
        
        # 4. 第三级布局：每个分组内部的进程
        for group in self.root_items:
            if group.children:
                # 为分组头部留出一点空间
                header_h = 20 if group.rect.height() > 40 else 0
                padding = 2
                inner_rect = group.rect.adjusted(padding, header_h + padding, -padding, -padding)
                
                if inner_rect.width() > 5 and inner_rect.height() > 5:
                    squarify_layout(group.children, inner_rect.x(), inner_rect.y(), 
                                   inner_rect.width(), inner_rect.height())

        self.update()

    def resizeEvent(self, event):
        self.recalculate_layout()
        super().resizeEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), self.colors['bg'])

        for group in self.root_items:
            self._draw_item(painter, group, is_group=True)
            if group.children:
                for child in group.children:
                    self._draw_item(painter, child, is_group=False)

        # 绘制游戏模式标识
        if self.is_game_mode:
            self._draw_game_icon(painter)

    def _draw_game_icon(self, painter):
        """在右下角绘制游戏图标标识"""
        margin = 10
        icon_size = 32
        rect = QRectF(self.width() - icon_size - margin, 
                      self.height() - icon_size - margin, 
                      icon_size, icon_size)
        
        # 绘制背景圆圈
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(QColor(0, 0, 0, 150)))
        painter.drawEllipse(rect)
        
        # 绘制 🎮 图标
        font = QFont()
        font.setPointSize(16)
        painter.setFont(font)
        painter.setPen(QColor(255, 255, 255))
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "🎮")

    def _draw_item(self, painter, item, is_group=False):
        rect = item.rect
        if rect.width() < 1 or rect.height() < 1: return

        # 1. 基础颜色获取
        base_color = self.colors.get(item.type, Qt.GlobalColor.gray)
        draw_rect = rect.adjusted(0.5, 0.5, -0.5, -0.5)

        if is_group:
            # --- 顶级分组绘制 (系统内存、GPU等) ---
            painter.setPen(QPen(self.colors['border'], 1))
            painter.setBrush(QBrush(base_color.darker(150)))
            painter.drawRect(rect)
            
            header_h = 20 if rect.height() > 30 else 0
            if header_h > 0:
                header_rect = QRectF(rect.x(), rect.y(), rect.width(), header_h)
                painter.fillRect(header_rect, self.colors['header'])
                painter.setPen(Qt.GlobalColor.white)
                font = painter.font()
                font.setBold(True); font.setPointSize(9)
                painter.setFont(font)
                metrics = QFontMetrics(font)
                title = f"{item.name} ({item.formatted_size()})"
                elided_title = metrics.elidedText(title, Qt.TextElideMode.ElideRight, int(rect.width() - 10))
                painter.drawText(header_rect.adjusted(5, 0, -5, 0), Qt.AlignmentFlag.AlignVCenter, elided_title)
        else:
            # --- 进程/程序块绘制 ---
            vmem = item.data.get('vmem', 0)
            rss = item.data.get('rss', item.value - vmem)
            
            # 如果该项有虚拟内存，且空间足够，执行“内部切发布局”
            if vmem > 0 and item.type == 'system' and draw_rect.height() > 35 and draw_rect.width() > 35:
                # 绘制总外框
                painter.setPen(QPen(self.colors['border'], 1))
                painter.setBrush(QBrush(base_color.darker(120)))
                painter.drawRect(draw_rect)
                
                # 绘制小标题 (程序名)
                header_h = 16
                header_rect = QRectF(draw_rect.x(), draw_rect.y(), draw_rect.width(), header_h)
                painter.fillRect(header_rect, self.colors['header'].lighter(130))
                painter.setPen(Qt.GlobalColor.white)
                font = painter.font(); font.setPointSize(8); font.setBold(True); painter.setFont(font)
                name_text = QFontMetrics(font).elidedText(item.name, Qt.TextElideMode.ElideRight, int(draw_rect.width() - 5))
                painter.drawText(header_rect.adjusted(4, 0, -4, 0), Qt.AlignmentFlag.AlignVCenter, name_text)
                
                # 计算内部切分
                body_rect = draw_rect.adjusted(1, header_h + 1, -1, -1)
                v_ratio = vmem / item.value
                
                if body_rect.width() > body_rect.height():
                    # 横向切: [物理 | 虚拟] - 保持主界面左右布局逻辑 (物理在前/左，虚拟在后/右)
                    r_w = body_rect.width() * (1 - v_ratio)
                    r_rect = QRectF(body_rect.x(), body_rect.y(), r_w, body_rect.height())
                    v_rect = QRectF(body_rect.x() + r_w, body_rect.y(), body_rect.width() - r_w, body_rect.height())
                else:
                    # 纵向切: [物理 / 虚拟] - 修正顺序：物理在上，虚拟在下 (对齐主界面上下布局逻辑)
                    r_h = body_rect.height() * (1 - v_ratio)
                    r_rect = QRectF(body_rect.x(), body_rect.y(), body_rect.width(), r_h)
                    v_rect = QRectF(body_rect.x(), body_rect.y() + r_h, body_rect.width(), body_rect.height() - r_h)
                
                # 绘制两个子区域
                for r, c, label, val in [(r_rect, self.colors['system'], "物理", rss), (v_rect, self.colors['vmem'], "虚拟", vmem)]:
                    if r.width() < 1 or r.height() < 1: continue
                    # 子块渐变
                    grad = QLinearGradient(r.topLeft(), r.bottomRight())
                    sub_color = c
                    if item == self.hovered_item:
                        sub_color = sub_color.lighter(130)
                    
                    grad.setColorAt(0, sub_color.lighter(110))
                    grad.setColorAt(1, sub_color.darker(110))
                    
                    # 关键修复：使用 painter.setBrush 确保填充颜色
                    painter.setBrush(QBrush(grad))
                    painter.setPen(QPen(self.colors['border'], 0.5))
                    painter.drawRect(r)
                    
                    # 子块标注
                    if r.width() > 30 and r.height() > 15:
                        painter.setPen(Qt.GlobalColor.white)
                        font.setBold(False); font.setPointSize(7); painter.setFont(font)
                        t_label = label if self.lang == 'zh' else ("Phys" if label == "物理" else "Virt")
                        painter.drawText(r, Qt.AlignmentFlag.AlignCenter, f"{t_label}\n{self._fmt_mini(val)}")
            else:
                # 普通绘制 (无虚拟内存或空间太小)
                color = base_color.lighter(130) if item == self.hovered_item else base_color
                gradient = QLinearGradient(draw_rect.topLeft(), draw_rect.bottomRight())
                gradient.setColorAt(0, color.lighter(110)); gradient.setColorAt(1, color.darker(110))
                
                painter.setBrush(QBrush(gradient))
                painter.setPen(QPen(self.colors['border'], 0.5))
                painter.drawRect(draw_rect)
                
                if draw_rect.width() > 30 and draw_rect.height() > 20:
                    painter.setPen(Qt.GlobalColor.white)
                    font = painter.font(); font.setBold(False)
                    font.setPointSize(min(10, max(6, int(draw_rect.height() / 4))))
                    painter.setFont(font)
                    metrics = QFontMetrics(font)
                    
                    name_rect = draw_rect.adjusted(2, 2, -2, -draw_rect.height()/2)
                    painter.drawText(name_rect, Qt.AlignmentFlag.AlignCenter, metrics.elidedText(item.name, Qt.TextElideMode.ElideRight, int(draw_rect.width())))
                    
                    if draw_rect.height() > 30:
                        size_rect = draw_rect.adjusted(2, draw_rect.height()/2, -2, -2)
                        painter.drawText(size_rect, Qt.AlignmentFlag.AlignCenter, item.formatted_size())

    def _fmt_mini(self, val):
        for unit in ['B', 'K', 'M', 'G']:
            if val < 1024.0: return f"{val:.1f}{unit}"
            val /= 1024.0
        return f"{val:.1f}T"

    def contextMenuEvent(self, event):
        """改用标准的右键菜单事件，这是解决右键不触发的最稳定方式"""
        pos = QPointF(event.pos())
        clicked_item = self._find_item_at(pos)
        if clicked_item:
            self.itemRightClicked.emit(clicked_item, QPointF(event.globalPos()))

    def mousePressEvent(self, event):
        super().mousePressEvent(event)

    def _find_item_at(self, pos):
        for group in self.root_items:
            for child in group.children:
                if child.rect.contains(pos):
                    return child
            if group.rect.contains(pos):
                return group
        return None

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            pos = QPointF(event.pos())
            clicked_item = self._find_item_at(pos)
            if clicked_item:
                self.itemDoubleClicked.emit(clicked_item)

    def mouseMoveEvent(self, event):
        pos = QPointF(event.pos())
        self.hovered_item = None
        
        for group in self.root_items:
            for child in group.children:
                if child.rect.contains(pos):
                    self.hovered_item = child
                    break
            if self.hovered_item: break
            
        self.update()
        if self.hovered_item:
            t = I18N[self.lang]
            total_label = "总占用" if self.lang == 'zh' else "Total"
            phys_label = "物理内存" if self.lang == 'zh' else "Physical"
            virt_label = "虚拟内存" if self.lang == 'zh' else "Virtual"
            
            tooltip = f"{self.hovered_item.name}\n{total_label}: {self.hovered_item.formatted_size()}"
            if 'rss' in self.hovered_item.data:
                rss = self.hovered_item.data['rss']
                vmem = self.hovered_item.data.get('vmem', 0)
                
                def fmt(val):
                    for unit in ['B', 'KB', 'MB', 'GB']:
                        if val < 1024.0: return f"{val:.2f} {unit}"
                        val /= 1024.0
                    return f"{val:.2f} TB"
                
                tooltip += f"\n{phys_label}: {fmt(rss)}"
                if vmem > 0:
                    tooltip += f"\n{virt_label}: {fmt(vmem)}"
            self.setToolTip(tooltip)
        else:
            self.setToolTip("")

# ---------------------------------------------------------
# 后台数据采集线程
# ---------------------------------------------------------
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

# ---------------------------------------------------------
# GPU 监控模块
# ---------------------------------------------------------
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
    def get_gpu_info(is_silent=False):
        """
        获取所有GPU信息，按优先级尝试：
        1. XML格式 (nvidia-smi -q -x) - 最可靠，能获取完整进程列表
        2. pynvml - 如果可用且XML失败
        3. CSV格式 (nvidia-smi --query) - 最后备用
        """
        try:
            # 方案1: 优先使用XML格式（Windows上最可靠）
            gpu_list = GPUMonitor.get_gpu_info_xml(is_silent)
            if gpu_list:
                return gpu_list
            
            # 方案2: 尝试pynvml
            gpu_list = GPUMonitor.get_nvidia_gpu_info()
            if gpu_list:
                return gpu_list
            
            # 方案3: 最后使用CSV格式
            gpu_list = GPUMonitor.get_nvidia_gpu_info_fallback()
            return gpu_list
        except Exception as e:
            print(f"Total GPU Info Error: {e}")
            return []

# ---------------------------------------------------------
# 数据采集
# ---------------------------------------------------------
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
        gap_name = "System Cache/Kernel" if lang == 'en' else "系统内核/共享/缓存"
        gap_item = TreeMapItem(gap_name, other_gap, "system", data={'rss': other_gap, 'vmem': 0})
        top_procs.append(gap_item)
        
    sys_group.children = top_procs
    sys_group.value = sum(p.value for p in top_procs)
    sys_group.data['rss'] = sum(p.data.get('rss', 0) for p in top_procs)
    sys_group.data['vmem'] = sum(p.data.get('vmem', 0) for p in top_procs)
    root_items.append(sys_group)

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
                
                    # 1. GPU 可用部分 (顶级块，模仿内存分析)
                    if show_gpu_free and free_bytes > 0:
                        g_free_name = f"{g_name} - {t['gpu_free']}" if len(gpu_list) > 1 else t['gpu_free']
                        root_items.append(TreeMapItem(g_free_name, free_bytes, "gpu_free"))
                    
                    # 2. GPU 使用部分 (顶级块)
                    if show_gpu_used:
                        g_used_name = f"{g_name} - {t['gpu_used']}" if len(gpu_list) > 1 else t['gpu_mem']
                        gpu_used_group = TreeMapItem(g_used_name, used_bytes, "gpu")
                        
                        # 构建进程列表
                        current_gpu_procs = []
                        for pid, data in proc_map.items():
                            used_mem = data['mem'] if isinstance(data, dict) else data
                            proc_name = None
                            
                            # 1. 优先使用从 XML 获取到的进程名
                            if isinstance(data, dict) and data.get('name'):
                                proc_name = os.path.basename(data['name'])
                                
                            # 2. 备选方案：通过扩展函数获取
                            if not proc_name:
                                proc_name = get_process_name_extended(pid)
                            
                            current_gpu_procs.append(TreeMapItem(proc_name, used_mem, "gpu", data={'pid': pid}))
                        
                        # 按程序聚合或独立显示
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
                            
                        # 归一化处理：如果通过 PowerShell 获取的数据总和超过了 nvidia-smi 报告的总占用
                        # 则按比例缩小，确保可视化比例准确
                        allocated_gpu = sum(p.value for p in final_gpu_procs)
                        if allocated_gpu > used_bytes and used_bytes > 0:
                            scale = used_bytes / allocated_gpu
                            for p in final_gpu_procs:
                                p.value *= scale
                            allocated_gpu = used_bytes

                        # 计算未分配的显存（系统保留或其他）
                        if used_bytes > allocated_gpu:
                            others_mem = used_bytes - allocated_gpu
                            final_gpu_procs.append(TreeMapItem(
                                t.get('gpu_others', "显存常驻/其他"), 
                                others_mem, 
                                "gpu"
                            ))
                        
                        # 按显存占用排序
                        gpu_used_group.children = sorted(final_gpu_procs, key=lambda x: x.value, reverse=True)
                        root_items.append(gpu_used_group)
        except Exception as e:
            print(f"GPU Data Error: {e}")
            traceback.print_exc()
    
    return root_items

# ---------------------------------------------------------
# 进程链窗口
# ---------------------------------------------------------
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
            
            result = "Ancestry Chain:\n" if lang == 'en' else "父级调用链：\n"
            for i, name in enumerate(chain):
                result += "  " * i + ("└─ " if i > 0 else "") + name + "\n"
            
            children = p.children()
            if children:
                result += "\nChildren:\n" if lang == 'en' else "\n直接子进程：\n"
                for child in children:
                    result += f"  └─ [{child.pid}] {child.name()}\n"
            
            return result
        except:
            return "Process info unavailable (Access Denied or Terminated)."

# ---------------------------------------------------------
# CPU 相关性设置窗口
# ---------------------------------------------------------
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
        
        # CPU 核心列表
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
            # 获取进程完整路径用于保存配置
            try:
                self.process_path = self.p.exe()
            except:
                self.process_path = None
        except Exception as e:
            layout.addWidget(QLabel(f"Error: {e}"))
            return

        # 尝试加载已保存的配置
        saved_affinity = None
        if self.process_path:
            saved_affinity = self.load_saved_affinity()
        
        # 如果存在已保存的配置，优先使用；否则使用当前配置
        affinity_to_use = saved_affinity if saved_affinity else current_affinity

        self.checkboxes = []
        cols = 4
        for i in all_cpus:
            cb = QCheckBox(f"CPU {i}")
            cb.setChecked(i in affinity_to_use)
            self.grid.addWidget(cb, i // cols, i % cols)
            self.checkboxes.append(cb)

        # 按钮区域
        btn_layout = QHBoxLayout()
        btn_all = QPushButton(t['affinity_all'])
        btn_all.clicked.connect(self.select_all)
        btn_invert = QPushButton("反选" if lang == 'zh' else "Invert")
        btn_invert.clicked.connect(self.invert_selection)
        btn_layout.addWidget(btn_all)
        btn_layout.addWidget(btn_invert)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        # 保存配置复选框
        self.chk_save = QCheckBox("保存此配置" if lang == 'zh' else "Save this configuration")
        self.chk_save.setChecked(True)
        layout.addWidget(self.chk_save)

        # 确认按钮
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
            return # 至少选择一个核心
        try:
            self.p.cpu_affinity(selected_cpus)
            
            # 如果勾选了保存配置，保存到配置文件
            if self.chk_save.isChecked() and self.process_path:
                self.save_affinity_config(selected_cpus)
            
            self.accept()
        except Exception as e:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(self, "Error", f"Failed to set affinity: {e}")

    def load_saved_affinity(self):
        """加载已保存的 CPU 配置"""
        try:
            if not self.process_path:
                return None
            
            doc_dir = os.path.join(os.path.expanduser("~"), "Documents")
            app_dir = os.path.join(doc_dir, "MemorySpaceExplorer")
            config_path = os.path.join(app_dir, "config.json")
            
            if not os.path.exists(config_path):
                return None
            
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            cpu_configs = config.get('cpu_affinity', {})
            if self.process_path in cpu_configs:
                cpus = cpu_configs[self.process_path].get('cpus', [])
                return set(cpus) if cpus else None
            
            return None
        except Exception as e:
            print(f"Load CPU affinity config error: {e}")
            return None

    def save_affinity_config(self, cpus):
        """保存 CPU 配置到配置文件"""
        try:
            if not self.process_path:
                return
            
            # 获取配置文件路径
            doc_dir = os.path.join(os.path.expanduser("~"), "Documents")
            app_dir = os.path.join(doc_dir, "MemorySpaceExplorer")
            if not os.path.exists(app_dir):
                os.makedirs(app_dir)
            config_path = os.path.join(app_dir, "config.json")
            
            # 读取现有配置
            config = {}
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
            
            # 初始化 CPU 配置字典
            if 'cpu_affinity' not in config:
                config['cpu_affinity'] = {}
            
            # 保存配置（使用进程路径作为键）
            config['cpu_affinity'][self.process_path] = {
                'name': self.process_name,
                'cpus': cpus
            }
            
            # 写回配置文件
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"Save CPU affinity config error: {e}")

# ---------------------------------------------------------
# 详细列表窗口
# ---------------------------------------------------------
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
        self.display_list = display_list # 保存列表用于右键查找
        
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
        """处理列表行的右键菜单"""
        row = self.table.currentRow()
        if row >= 0 and row < len(self.display_list):
            item = self.display_list[row]
            # 调用主窗口的右键菜单逻辑
            if self.parent():
                self.parent().on_context_menu(item, QPointF(self.table.mapToGlobal(pos)))

# ---------------------------------------------------------
# 自定义 UI 组件：滑动开关 (Toggle Switch)
# ---------------------------------------------------------
from PyQt6.QtCore import QPropertyAnimation, QEasingCurve, pyqtProperty

class SwitchButton(QCheckBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(55, 28)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._thumb_pos = 3.0 # 改为浮点数，滑动更平滑
        self._anim = QPropertyAnimation(self, b"thumb_pos")
        self._anim.setDuration(200)
        self._anim.setEasingCurve(QEasingCurve.Type.InOutQuad)

    @pyqtProperty(float) # 使用 float 类型
    def thumb_pos(self):
        return self._thumb_pos

    @thumb_pos.setter
    def thumb_pos(self, pos):
        self._thumb_pos = pos
        self.update()

    def setChecked(self, checked):
        super().setChecked(checked)
        self._thumb_pos = 30.0 if checked else 3.0
        self.update()

    def hitButton(self, pos):
        return self.contentsRect().contains(pos)

    # 使用 nextCheckState 代替 checkStateSet，这样在状态改变前就能准确捕捉并启动动画
    def nextCheckState(self):
        super().nextCheckState()
        # 点击后状态已经反转了，所以 isChecked() 是切换后的目标状态
        end = 30.0 if self.isChecked() else 3.0
        self._anim.stop()
        self._anim.setStartValue(self._thumb_pos)
        self._anim.setEndValue(end)
        self._anim.start()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # 1. 绘制背景轨道
        bg_color = QColor(38, 166, 154) if self.isChecked() else QColor(117, 117, 117)
        painter.setBrush(bg_color)
        painter.setPen(QPen(QColor(0, 0, 0, 40), 1))
        painter.drawRoundedRect(0, 0, self.width(), self.height(), self.height()/2, self.height()/2)
        
        # 2. 绘制滑块 (带 3D 效果)
        # 使用 self._thumb_pos 确保滑块位置随动画实时更新
        gradient = QLinearGradient(self._thumb_pos, 3, self._thumb_pos, 25)
        gradient.setColorAt(0, QColor(255, 255, 255))
        gradient.setColorAt(1, QColor(230, 230, 230))
        
        painter.setBrush(QBrush(gradient))
        painter.setPen(QPen(QColor(0, 0, 0, 60), 0.5))
        
        # 滑块 X 轴使用浮点数坐标，绘图时会自动处理
        painter.drawEllipse(QPointF(self._thumb_pos + 11, 14), 11, 11)

# ---------------------------------------------------------
# 设置对话框
# ---------------------------------------------------------
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
            
            /* 设置块面板样式 */
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
        
        # --- 1. 基础设置 ---
        layout_base = self._add_section("🌐 基础设置")
        self.lbl_lang = QLabel()
        self.combo_lang = QComboBox()
        self.combo_lang.addItem("简体中文", 'zh'); self.combo_lang.addItem("English", 'en')
        self.combo_lang.setCurrentIndex(self.combo_lang.findData(self.settings['lang']))
        self._add_row(layout_base, self.lbl_lang, self.combo_lang)
        
        self.lbl_refresh = QLabel()
        self.spin_refresh = QDoubleSpinBox(); self.spin_refresh.setRange(0.1, 60.0)
        self.spin_refresh.setValue(self.settings['refresh_rate'] / 1000.0)
        self._add_row(layout_base, self.lbl_refresh, self.spin_refresh)

        # --- 2. 监控显示 ---
        layout_disp = self._add_section("📊 监控显示")
        self.lbl_view_mode = QLabel()
        mode_container = QWidget()
        mode_container.setStyleSheet("background-color: transparent;")
        mode_h = QHBoxLayout(mode_container); mode_h.setContentsMargins(0,0,0,0)
        self.btn_view_mode = SwitchButton(); self.btn_view_mode.setChecked(self.settings.get('view_mode') == 'program')
        self.lbl_mode_text = QLabel(); self.lbl_mode_text.setStyleSheet("background-color: transparent; color: #EEE;")
        mode_h.addStretch(); mode_h.addWidget(self.lbl_mode_text); mode_h.addWidget(self.btn_view_mode)
        self._add_row(layout_disp, self.lbl_view_mode, mode_container)
        
        # 显示可用内存 - 改为开关样式
        self.lbl_free = QLabel()
        free_container = QWidget()
        free_container.setStyleSheet("background-color: transparent;")
        free_h = QHBoxLayout(free_container); free_h.setContentsMargins(0,0,0,0)
        self.btn_free = SwitchButton(); self.btn_free.setChecked(self.settings.get('show_free', True))
        self.lbl_free_text = QLabel(); self.lbl_free_text.setStyleSheet("background-color: transparent; color: #EEE;")
        free_h.addStretch(); free_h.addWidget(self.lbl_free_text); free_h.addWidget(self.btn_free)
        self._add_row(layout_disp, self.lbl_free, free_container)
        
        # 显示可用 GPU 显存 - 改为开关样式
        self.lbl_gpu_free = QLabel()
        gpu_free_container = QWidget()
        gpu_free_container.setStyleSheet("background-color: transparent;")
        gpu_free_h = QHBoxLayout(gpu_free_container); gpu_free_h.setContentsMargins(0,0,0,0)
        self.btn_gpu_free = SwitchButton(); self.btn_gpu_free.setChecked(self.settings.get('show_gpu_free', True))
        self.lbl_gpu_free_text = QLabel(); self.lbl_gpu_free_text.setStyleSheet("background-color: transparent; color: #EEE;")
        gpu_free_h.addStretch(); gpu_free_h.addWidget(self.lbl_gpu_free_text); gpu_free_h.addWidget(self.btn_gpu_free)
        self._add_row(layout_disp, self.lbl_gpu_free, gpu_free_container)
        
        # 显示占用 GPU 显存 - 改为开关样式
        self.lbl_gpu_used = QLabel()
        gpu_used_container = QWidget()
        gpu_used_container.setStyleSheet("background-color: transparent;")
        gpu_used_h = QHBoxLayout(gpu_used_container); gpu_used_h.setContentsMargins(0,0,0,0)
        self.btn_gpu_used = SwitchButton(); self.btn_gpu_used.setChecked(self.settings.get('show_gpu_used', True))
        self.lbl_gpu_used_text = QLabel(); self.lbl_gpu_used_text.setStyleSheet("background-color: transparent; color: #EEE;")
        gpu_used_h.addStretch(); gpu_used_h.addWidget(self.lbl_gpu_used_text); gpu_used_h.addWidget(self.btn_gpu_used)
        self._add_row(layout_disp, self.lbl_gpu_used, gpu_used_container)
        
        # 开机自动启动 - 改为开关样式
        self.lbl_startup = QLabel()
        startup_container = QWidget()
        startup_container.setStyleSheet("background-color: transparent;")
        startup_h = QHBoxLayout(startup_container); startup_h.setContentsMargins(0,0,0,0)
        self.btn_startup = SwitchButton(); self.btn_startup.setChecked(self.settings.get('auto_startup', False))
        self.lbl_startup_text = QLabel(); self.lbl_startup_text.setStyleSheet("background-color: transparent; color: #EEE;")
        startup_h.addStretch(); startup_h.addWidget(self.lbl_startup_text); startup_h.addWidget(self.btn_startup)
        self._add_row(layout_disp, self.lbl_startup, startup_container)

        # --- 3. 内存优化 ---
        layout_opt = self._add_section("🚀 内存优化")
        self.lbl_auto_opt = QLabel()
        auto_opt_container = QWidget()
        auto_opt_container.setStyleSheet("background-color: transparent;")
        auto_opt_h = QHBoxLayout(auto_opt_container); auto_opt_h.setContentsMargins(0,0,0,0)
        self.btn_auto_opt = SwitchButton(); self.btn_auto_opt.setChecked(self.settings.get('auto_optimize', False))
        self.lbl_auto_opt_text = QLabel(); self.lbl_auto_opt_text.setStyleSheet("background-color: transparent; color: #EEE;")
        auto_opt_h.addStretch(); auto_opt_h.addWidget(self.lbl_auto_opt_text); auto_opt_h.addWidget(self.btn_auto_opt)
        self._add_row(layout_opt, self.lbl_auto_opt, auto_opt_container)
        
        self.lbl_opt_interval = QLabel()
        self.spin_opt_interval = QDoubleSpinBox(); self.spin_opt_interval.setRange(1.0, 3600.0)
        self.spin_opt_interval.setValue(self.settings.get('optimize_interval', 30000) / 1000.0)
        self._add_row(layout_opt, self.lbl_opt_interval, self.spin_opt_interval)

        # --- 4. 退出行为 ---
        layout_close = self._add_section("🚪 退出行为")
        self.lbl_close_behavior = QLabel()
        close_container = QWidget()
        close_container.setStyleSheet("background-color: transparent;")
        close_h = QHBoxLayout(close_container); close_h.setContentsMargins(0,0,0,0)
        self.btn_close_behavior = SwitchButton(); self.btn_close_behavior.setChecked(self.settings.get('close_to_tray', True))
        self.lbl_close_text = QLabel(); self.lbl_close_text.setStyleSheet("background-color: transparent; color: #EEE;")
        close_h.addStretch(); close_h.addWidget(self.lbl_close_text); close_h.addWidget(self.btn_close_behavior)
        self._add_row(layout_close, self.lbl_close_behavior, close_container)

        # --- 5. 视觉颜色 ---
        layout_color = self._add_section("🎨 视觉颜色")
        self.color_buttons = {}
        color_types = [('system', 'color_system'), ('free', 'color_free'), ('gpu', 'color_gpu'), ('gpu_free', 'color_gpu_free'), ('vmem', 'color_vmem')]
        for key, label_key in color_types:
            lbl = QLabel(); btn = QPushButton(); btn.setFixedSize(45, 22); btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setAutoDefault(False) # 防止回车键误触发颜色选择
            btn.setDefault(False) # 明确禁用默认按钮行为
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus) # 颜色按钮不接受焦点，避免回车键触发
            btn.setStyleSheet(f"background-color: {self.settings['colors'][key]}; border: 1px solid #555; border-radius: 4px;")
            btn.clicked.connect(lambda checked, k=key: self.pick_color(k))
            self._add_row(layout_color, lbl, btn)
            self.color_buttons[key] = (lbl, btn)

        # --- 6. CPU 配置管理 ---
        layout_cpu = self._add_section("⚙️ CPU 配置管理")
        self.lbl_cpu_configs = QLabel()
        self.lbl_cpu_configs.setText("已保存的 CPU 配置" if self.settings['lang'] == 'zh' else "Saved CPU Configurations")
        layout_cpu.addWidget(self.lbl_cpu_configs)
        
        # CPU 配置列表
        self.cpu_config_list = QTableWidget()
        self.cpu_config_list.setColumnCount(3)
        self.cpu_config_list.setHorizontalHeaderLabels(["程序名称", "路径", "CPU 核心"] if self.settings['lang'] == 'zh' else ["Program", "Path", "CPU Cores"])
        self.cpu_config_list.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.cpu_config_list.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.cpu_config_list.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self.cpu_config_list.setColumnWidth(2, 200)
        self.cpu_config_list.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.cpu_config_list.setStyleSheet("""
            QTableWidget {
                background-color: #252526;
                color: #EEE;
                gridline-color: #333;
                border: 1px solid #333;
            }
            QHeaderView::section {
                background-color: #333;
                color: white;
                padding: 5px;
                border: 1px solid #444;
            }
        """)
        self.cpu_config_list.setMaximumHeight(200)
        layout_cpu.addWidget(self.cpu_config_list)
        
        # 刷新和删除按钮
        cpu_btn_layout = QHBoxLayout()
        self.btn_refresh_cpu = QPushButton("刷新" if self.settings['lang'] == 'zh' else "Refresh")
        self.btn_refresh_cpu.clicked.connect(self.refresh_cpu_configs)
        self.btn_delete_cpu = QPushButton("删除选中" if self.settings['lang'] == 'zh' else "Delete Selected")
        self.btn_delete_cpu.clicked.connect(self.delete_cpu_config)
        cpu_btn_layout.addWidget(self.btn_refresh_cpu)
        cpu_btn_layout.addWidget(self.btn_delete_cpu)
        cpu_btn_layout.addStretch()
        layout_cpu.addLayout(cpu_btn_layout)
        
        # 自动应用配置开关
        self.lbl_auto_apply_cpu = QLabel()
        auto_apply_container = QWidget()
        auto_apply_container.setStyleSheet("background-color: transparent;")
        auto_apply_h = QHBoxLayout(auto_apply_container); auto_apply_h.setContentsMargins(0,0,0,0)
        self.btn_auto_apply_cpu = SwitchButton(); self.btn_auto_apply_cpu.setChecked(self.settings.get('auto_apply_cpu_affinity', False))
        self.lbl_auto_apply_cpu_text = QLabel(); self.lbl_auto_apply_cpu_text.setStyleSheet("background-color: transparent; color: #EEE;")
        auto_apply_h.addStretch(); auto_apply_h.addWidget(self.lbl_auto_apply_cpu_text); auto_apply_h.addWidget(self.btn_auto_apply_cpu)
        self._add_row(layout_cpu, self.lbl_auto_apply_cpu, auto_apply_container)
        
        self.container.addStretch()
        scroll.setWidget(scroll_content)
        main_layout.addWidget(scroll)

        # 添加底部“完成”按钮
        btn_layout = QHBoxLayout()
        self.btn_done = QPushButton("完成")
        self.btn_done.setFixedSize(120, 35)
        self.btn_done.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_done.setDefault(True) # 设置为默认按钮，响应回车
        self.btn_done.setStyleSheet("""
            QPushButton {
                background-color: #007ACC;
                color: white;
                border-radius: 6px;
                font-weight: bold;
                font-size: 13px;
                border: none;
            }
            QPushButton:hover { background-color: #0098FF; }
            QPushButton:pressed { background-color: #005A9E; }
        """)
        self.btn_done.clicked.connect(self.accept)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_done)
        btn_layout.addStretch()
        main_layout.addLayout(btn_layout)
        
        # 绑定事件
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
        self.refresh_cpu_configs()  # 初始化时加载 CPU 配置列表

    def showEvent(self, event):
        """对话框显示时，确保完成按钮获得焦点"""
        super().showEvent(event)
        # 延迟设置焦点，确保所有控件都已初始化
        QTimer.singleShot(100, lambda: self.btn_done.setFocus() if hasattr(self, 'btn_done') else None)

    def keyPressEvent(self, event):
        """重写键盘事件，确保回车键只触发完成按钮"""
        if event.key() == Qt.Key.Key_Return or event.key() == Qt.Key.Key_Enter:
            # 如果焦点在颜色按钮上，忽略回车键
            focused_widget = self.focusWidget()
            if focused_widget and isinstance(focused_widget, QPushButton):
                # 检查是否是颜色按钮
                for key, (lbl, btn) in self.color_buttons.items():
                    if focused_widget == btn:
                        event.ignore()
                        return
            # 否则触发完成按钮
            if hasattr(self, 'btn_done'):
                self.btn_done.click()
                return
        super().keyPressEvent(event)

    def _add_section(self, title_text):
        panel = QFrame()
        panel.setObjectName("SectionPanel")
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(15, 12, 15, 15)
        panel_layout.setSpacing(0)  # 标题和内容之间无间距
        
        # 可点击的标题栏（带折叠箭头）
        class ClickableTitle(QWidget):
            def __init__(self, text, content_widget, arrow_label):
                super().__init__()
                self.content_widget = content_widget
                self.arrow_label = arrow_label
                self.setStyleSheet("""
                    QWidget {
                        background-color: transparent;
                        border: none;
                    }
                    QWidget:hover {
                        background-color: rgba(0, 255, 204, 0.1);
                    }
                """)
                self.setCursor(Qt.CursorShape.PointingHandCursor)
                self.setFixedHeight(32)  # 固定标题栏高度
                layout = QHBoxLayout(self)
                layout.setContentsMargins(0, 0, 0, 0)
                layout.setSpacing(8)  # 箭头和标题之间的间距
                # 确保布局中的所有元素垂直居中对齐
                layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)
                
                # 箭头标签，垂直和水平居中对齐
                arrow_label.setAlignment(Qt.AlignmentFlag.AlignCenter)  # AlignCenter包含水平和垂直居中
                arrow_label.setFixedSize(16, 16)  # 固定箭头大小，确保正方形
                arrow_label.setStyleSheet("""
                    QLabel {
                        color: #00FFCC;
                        font-size: 11px;
                        font-weight: bold;
                        background-color: transparent;
                        padding: 0px;
                    }
                """)
                layout.addWidget(arrow_label, alignment=Qt.AlignmentFlag.AlignVCenter)
                
                # 标题标签
                title = QLabel(text)
                title.setObjectName("GroupTitle")
                title.setStyleSheet("color: #00FFCC; font-size: 14px; font-weight: bold; background-color: transparent; padding: 0px; margin: 0px; line-height: 1.0;")
                title.setCursor(Qt.CursorShape.PointingHandCursor)
                title.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                title.setMinimumHeight(16)  # 设置最小高度，确保与箭头对齐
                layout.addWidget(title, alignment=Qt.AlignmentFlag.AlignVCenter)
                layout.addStretch()
            
            def mousePressEvent(self, event):
                if event.button() == Qt.MouseButton.LeftButton:
                    is_expanded = self.content_widget.isVisible()
                    self.content_widget.setVisible(not is_expanded)
                    # 更新箭头：点击后的新状态，展开时显示▼，折叠时显示▶
                    new_state_expanded = not is_expanded
                    self.arrow_label.setText("▼" if new_state_expanded else "▶")
        
        # 内容容器（可折叠）
        content_widget = QWidget()
        content_widget.setObjectName("SectionContent")
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(0, 8, 0, 0)  # 内容区域顶部留出间距
        content_layout.setSpacing(10)
        content_widget.setVisible(True)  # 默认展开
        
        # 折叠箭头图标（根据内容状态初始化）
        arrow_label = QLabel("▼")  # 默认展开，显示向下箭头
        # 样式在ClickableTitle中设置
        
        # 创建可点击标题
        clickable_title = ClickableTitle(title_text, content_widget, arrow_label)
        panel_layout.addWidget(clickable_title)
        panel_layout.addWidget(content_widget)
        
        self.container.addWidget(panel)
        return content_layout

    def _add_row(self, parent_layout, label_widget, control_widget):
        row = QHBoxLayout()
        if label_widget:
            row.addWidget(label_widget)
        row.addStretch()
        row.addWidget(control_widget)
        parent_layout.addLayout(row)

    def on_lang_changed(self):
        self.settings['lang'] = self.combo_lang.currentData()
        self.retranslate_ui()
        self.settingsChanged.emit()

    def pick_color(self, key):
        c = QColorDialog.getColor(QColor(self.settings['colors'][key]), self, "Select Color")
        if c.isValid():
            hex_c = c.name().upper()
            self.settings['colors'][key] = hex_c
            self.color_buttons[key][1].setStyleSheet(f"background-color: {hex_c}; border: 1px solid #666; border-radius: 3px;")
            self.settingsChanged.emit()

    def retranslate_ui(self):
        t = I18N[self.settings['lang']]
        self.setWindowTitle(t['settings_title'])
        self.lbl_lang.setText(t['lang_label']); self.lbl_refresh.setText(t['refresh_label'])
        self.spin_refresh.setSuffix(" s"); self.lbl_view_mode.setText(t['view_mode_label'])
        self.lbl_auto_opt.setText(t.get('auto_optimize_label', 'Auto Optimize'))
        self.lbl_opt_interval.setText(t.get('opt_interval_label', 'Interval'))
        self.spin_opt_interval.setSuffix(" s")
        self.lbl_free.setText(t['show_free'])
        self.lbl_gpu_free.setText(t['show_gpu_free'])
        self.lbl_gpu_used.setText(t['show_gpu_used'])
        self.lbl_startup.setText(t['auto_startup'])
        self.lbl_close_behavior.setText(t['close_behavior_label'])
        
        # CPU 配置管理
        if hasattr(self, 'lbl_cpu_configs'):
            self.lbl_cpu_configs.setText("已保存的 CPU 配置" if self.settings['lang'] == 'zh' else "Saved CPU Configurations")
            self.cpu_config_list.setHorizontalHeaderLabels(["程序名称", "路径", "CPU 核心"] if self.settings['lang'] == 'zh' else ["Program", "Path", "CPU Cores"])
            self.btn_refresh_cpu.setText("刷新" if self.settings['lang'] == 'zh' else "Refresh")
            self.btn_delete_cpu.setText("删除选中" if self.settings['lang'] == 'zh' else "Delete Selected")
            self.lbl_auto_apply_cpu.setText("开机自动应用 CPU 配置" if self.settings['lang'] == 'zh' else "Auto Apply CPU Affinity on Startup")
        
        color_types = [('system', 'color_system'), ('free', 'color_free'), ('gpu', 'color_gpu'), ('gpu_free', 'color_gpu_free'), ('vmem', 'color_vmem')]
        for key, label_key in color_types:
            if key in self.color_buttons: self.color_buttons[key][0].setText(t[label_key])

        self.combo_lang.blockSignals(True)
        self.combo_lang.setItemText(0, t['lang_zh']); self.combo_lang.setItemText(1, t['lang_en'])
        self.combo_lang.blockSignals(False)
        self.update_toggle_text()

    def update_toggle_text(self):
        t = I18N[self.settings['lang']]
        if hasattr(self, 'lbl_mode_text'):
            self.lbl_mode_text.setText(t['view_program'] if self.btn_view_mode.isChecked() else t['view_process'])
        if hasattr(self, 'lbl_close_text'):
            self.lbl_close_text.setText(t['close_to_tray'] if self.btn_close_behavior.isChecked() else t['close_quit'])
        if hasattr(self, 'lbl_free_text'):
            if self.settings['lang'] == 'zh':
                self.lbl_free_text.setText("开启" if self.btn_free.isChecked() else "关闭")
            else:
                self.lbl_free_text.setText("ON" if self.btn_free.isChecked() else "OFF")
        if hasattr(self, 'lbl_gpu_free_text'):
            if self.settings['lang'] == 'zh':
                self.lbl_gpu_free_text.setText("开启" if self.btn_gpu_free.isChecked() else "关闭")
            else:
                self.lbl_gpu_free_text.setText("ON" if self.btn_gpu_free.isChecked() else "OFF")
        if hasattr(self, 'lbl_gpu_used_text'):
            if self.settings['lang'] == 'zh':
                self.lbl_gpu_used_text.setText("开启" if self.btn_gpu_used.isChecked() else "关闭")
            else:
                self.lbl_gpu_used_text.setText("ON" if self.btn_gpu_used.isChecked() else "OFF")
        if hasattr(self, 'lbl_startup_text'):
            if self.settings['lang'] == 'zh':
                self.lbl_startup_text.setText("开启" if self.btn_startup.isChecked() else "关闭")
            else:
                self.lbl_startup_text.setText("ON" if self.btn_startup.isChecked() else "OFF")
        if hasattr(self, 'lbl_auto_apply_cpu_text'):
            if self.settings['lang'] == 'zh':
                self.lbl_auto_apply_cpu_text.setText("开启" if self.btn_auto_apply_cpu.isChecked() else "关闭")
            else:
                self.lbl_auto_apply_cpu_text.setText("ON" if self.btn_auto_apply_cpu.isChecked() else "OFF")

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
        self.update_toggle_text()
        self.settingsChanged.emit()

    def refresh_cpu_configs(self):
        """刷新 CPU 配置列表"""
        try:
            doc_dir = os.path.join(os.path.expanduser("~"), "Documents")
            app_dir = os.path.join(doc_dir, "MemorySpaceExplorer")
            config_path = os.path.join(app_dir, "config.json")
            
            config = {}
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
            
            cpu_configs = config.get('cpu_affinity', {})
            
            self.cpu_config_list.setRowCount(len(cpu_configs))
            for row, (path, cfg) in enumerate(cpu_configs.items()):
                name = cfg.get('name', os.path.basename(path))
                cpus = cfg.get('cpus', [])
                none_text = "无" if self.settings['lang'] == 'zh' else "None"
                cpus_str = ', '.join(map(str, sorted(cpus))) if cpus else none_text
                
                name_item = QTableWidgetItem(name)
                name_item.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
                self.cpu_config_list.setItem(row, 0, name_item)
                
                path_item = QTableWidgetItem(path)
                path_item.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
                self.cpu_config_list.setItem(row, 1, path_item)
                
                cpus_item = QTableWidgetItem(cpus_str)
                cpus_item.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
                self.cpu_config_list.setItem(row, 2, cpus_item)
        except Exception as e:
            print(f"Refresh CPU configs error: {e}")

    def delete_cpu_config(self):
        """删除选中的 CPU 配置"""
        try:
            row = self.cpu_config_list.currentRow()
            if row < 0:
                return
            
            path_item = self.cpu_config_list.item(row, 1)
            if not path_item:
                return
            
            path = path_item.text()
            
            doc_dir = os.path.join(os.path.expanduser("~"), "Documents")
            app_dir = os.path.join(doc_dir, "MemorySpaceExplorer")
            config_path = os.path.join(app_dir, "config.json")
            
            config = {}
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
            
            if 'cpu_affinity' in config and path in config['cpu_affinity']:
                del config['cpu_affinity'][path]
                
                with open(config_path, 'w', encoding='utf-8') as f:
                    json.dump(config, f, indent=4, ensure_ascii=False)
                
                self.refresh_cpu_configs()
        except Exception as e:
            print(f"Delete CPU config error: {e}")

    def on_lang_changed(self):
        self.settings['lang'] = self.combo_lang.currentData()
        self.retranslate_ui()
        self.settingsChanged.emit()

    def pick_color(self, key):
        c = QColorDialog.getColor(QColor(self.settings['colors'][key]), self, "Select Color")
        if c.isValid():
            hex_c = c.name().upper()
            self.settings['colors'][key] = hex_c
            self.color_buttons[key][1].setStyleSheet(f"background-color: {hex_c}; border: 1px solid #666; border-radius: 3px;")
            self.settingsChanged.emit()

# ---------------------------------------------------------
# 主窗口
# ---------------------------------------------------------
class MainWindow(QMainWindow):
    request_data = pyqtSignal(dict)

    def __init__(self):
        super().__init__()
        
        # 优化：设置本进程优先级为“低于标准”，确保游戏优先
        try:
            import psutil
            import os
            p = psutil.Process(os.getpid())
            p.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
        except: pass

        self.settings = {
            'lang': 'zh',
            'refresh_rate': 3000,
            'show_free': True,
            'show_gpu_free': True,
            'show_gpu_used': True,
            'view_mode': 'program',
            'close_to_tray': True,
            'auto_optimize': False,
            'optimize_interval': 30000,
            'auto_startup': self.check_startup_status(),
            'auto_apply_cpu_affinity': False,
            'colors': {
                'system': '#2D7DDC',
                'free': '#469646',
                'gpu': '#8C3CB4',
                'gpu_free': '#643282',
                'vmem': '#FF8C00'
            }
        }
        
        # 从文档文件夹加载已保存的配置
        self.load_settings()
        
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
        self.timer.start(self.settings['refresh_rate'])
        
        # 系统托盘
        self.init_tray()
        
        self.apply_i18n()
        self.treemap.set_colors(self.settings['colors'])
        
        # 如果启用了自动应用 CPU 配置，在启动时应用并设置定期检查
        if self.settings.get('auto_apply_cpu_affinity', False):
            QTimer.singleShot(2000, self.apply_saved_cpu_affinity)  # 延迟2秒，确保系统稳定
            # 设置定时器，每30秒检查一次并应用配置（因为进程可能后启动）
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

    def get_config_path(self):
        """获取配置文件在文档文件夹中的路径"""
        doc_dir = os.path.join(os.path.expanduser("~"), "Documents")
        app_dir = os.path.join(doc_dir, "MemorySpaceExplorer")
        try:
            if not os.path.exists(app_dir):
                os.makedirs(app_dir)
            return os.path.join(app_dir, "config.json")
        except:
            # 如果无法创建目录，回退到当前目录
            return "config.json"

    def load_settings(self):
        """从配置文件加载设置 (包含自动迁移逻辑)"""
        path = self.get_config_path()
        old_path = "config.json"
        
        # 确定读取哪个文件
        actual_path = path if os.path.exists(path) else (old_path if os.path.exists(old_path) else None)
            
        if actual_path:
            try:
                with open(actual_path, 'r', encoding='utf-8') as f:
                    saved_settings = json.load(f)
                    # 处理旧的 show_gpu 配置迁移
                    if 'show_gpu' in saved_settings and 'show_gpu_free' not in saved_settings:
                        old_show_gpu = saved_settings.pop('show_gpu')
                        saved_settings['show_gpu_free'] = old_show_gpu
                        saved_settings['show_gpu_used'] = old_show_gpu
                    
                    # 深度更新：确保新添加的设置项有默认值
                    for k, v in saved_settings.items():
                        if k == 'colors' and isinstance(v, dict):
                            self.settings['colors'].update(v)
                        else:
                            self.settings[k] = v
                
                # 如果是从旧位置加载的，立即保存一份到新位置以完成迁移
                if actual_path == old_path:
                    self.save_settings()
            except Exception as e:
                print(f"Load settings error: {e}")

    def save_settings(self):
        """保存当前设置到配置文件"""
        path = self.get_config_path()
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"Save settings error: {e}")

    def apply_saved_cpu_affinity(self):
        """应用保存的 CPU 配置到所有匹配的进程"""
        try:
            config_path = self.get_config_path()
            if not os.path.exists(config_path):
                return
            
            with open(config_path, 'r', encoding='utf-8') as f:
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
        
        # 检查是否检测到 GPU (如果 gpu_percent 为 0 且没有任何 GPU 项，可能没 GPU)
        # 这里简单判断：如果有 GPU 占用或总容量 > 0 (通过 gpu_percent 传递)
        has_gpu = gpu_percent > 0 or self.settings.get('show_gpu_used', True)
        
        # 绘制 4 个柱子
        for i in range(bar_count):
            if has_gpu:
                # 前 2 个内存，后 2 个显存
                is_gpu_bar = (i >= 2)
                percent = gpu_percent if is_gpu_bar else ram_percent
            else:
                # 全部显示内存
                percent = ram_percent
            
            # 根据各自百分比计算颜色 (绿色 -> 黄色 -> 红色)
            if percent < 60:
                color = QColor(0, 255, 100) # 绿色
            elif percent < 85:
                color = QColor(255, 200, 0) # 黄色
            else:
                color = QColor(255, 50, 50)  # 红色
            
            # 基础高度计算
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
        mem_label = "内存" if self.settings['lang'] == 'zh' else "RAM"
        gpu_label = "显存" if self.settings['lang'] == 'zh' else "GPU"
        vmem_label = "虚拟内存" if self.settings['lang'] == 'zh' else "Swap"
        
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
        t = I18N[self.settings['lang']]
        self.setWindowTitle(t['title'])
        if hasattr(self, 'settings_btn'):
            self.settings_btn.setText(t['settings_btn'])
        # 更新托盘菜单文字
        if hasattr(self, 'action_show'):
            self.action_show.setText(t['tray_show'])
        if hasattr(self, 'action_exit'):
            self.action_exit.setText(t['tray_exit'])

    def open_settings(self):
        dialog = SettingsDialog(self, self.settings)
        # 绑定即时生效信号
        dialog.settingsChanged.connect(self.on_settings_changed)
        dialog.exec()

    def on_settings_changed(self):
        """当设置对话框中的任何项修改时立即调用"""
        self.apply_i18n()
        # 保存设置到文件
        self.save_settings()
        # 更新颜色
        if hasattr(self, 'treemap'):
            self.treemap.set_colors(self.settings['colors'])
        # 更新开机启动状态
        self.update_startup_registry()
        # 重置刷新计时器
        self.timer.stop()
        self.timer.start(self.settings['refresh_rate'])
        
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

    def check_startup_status(self):
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

    def update_startup_registry(self):
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
            if self.settings.get('auto_startup', False):
                winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, cmd)
            else:
                try:
                    winreg.DeleteValue(key, app_name)
                except FileNotFoundError:
                    pass
            winreg.CloseKey(key)
        except Exception as e:
            print(f"Startup Registry Error: {e}")

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
            # 定义必要的结构体
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

            # 调用 ShellExecuteExW (Unicode版本)
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
            if self.timer.interval() != self.settings['refresh_rate']:
                self.timer.setInterval(self.settings['refresh_rate'])
            self.settings['_is_silent_mode'] = False
                
        self.request_data.emit(self.settings)

    def on_data_received(self, root_items, vm_info):
        self.treemap.set_data(root_items, self.settings['lang'])
        t = I18N[self.settings['lang']]
        
        # --- 核心修改：从图形数据中提取统计值，确保对齐 ---
        graph_phys_used = 0
        graph_virt_used = 0
        
        # 寻找“系统内存”分组
        sys_group = next((item for item in root_items if item.type == 'system'), None)
        if sys_group and sys_group.children:
            for child in sys_group.children:
                graph_phys_used += child.data.get('rss', 0)
                graph_virt_used += child.data.get('vmem', 0)
        
        # 重新计算百分比
        percent = (graph_phys_used / vm_info['total'] * 100) if vm_info['total'] > 0 else 0
        sw_percent = (graph_virt_used / (vm_info['v_total'] - vm_info['total']) * 100) if (vm_info['v_total'] - vm_info['total']) > 0 else 0
        
        total_used = graph_phys_used + graph_virt_used
        v_percent = (total_used / vm_info['v_total'] * 100) if vm_info['v_total'] > 0 else 0

        gpu_percent = vm_info.get('gpu_percent', 0)

        # 诊断信息
        warnings = []
        
        # 检查管理员权限
        try:
            is_admin = ctypes.windll.shell32.IsUserAnAdmin()
            if not is_admin:
                warnings.append("[!] 建议以管理员身份运行以获取完整显存进程列表" if self.settings['lang'] == 'zh' else "[!] Run as admin for complete GPU process list")
        except:
            pass
        
        # GPU 监控状态诊断
        if self.settings.get('show_gpu_used', True):
            # 检查是否所有GPU的进程列表都为空（说明可能获取不到进程）
            gpu_items = [item for item in root_items if item.type.startswith('gpu')]
            for gpu_item in gpu_items:
                if gpu_item.type == 'gpu' and gpu_item.children:
                    # 检查是否只有"常驻/其他"这一个子项
                    if len(gpu_item.children) == 1 and ('gpu_others' in gpu_item.children[0].name.lower() or '常驻' in gpu_item.children[0].name or 'other' in gpu_item.children[0].name.lower()):
                        if self.settings['lang'] == 'zh':
                            warnings.append("[!] 显存进程列表为空，请尝试以管理员身份运行")
                        else:
                            warnings.append("[!] GPU process list empty, try running as admin")
                        break
        
        status = t['status_format'].format(
            used=graph_phys_used/(1024**3),
            total=vm_info['total']/(1024**3),
            v_used=total_used/(1024**3),
            v_total=vm_info['v_total']/(1024**3),
            sw_used=graph_virt_used/(1024**3),
            sw_total=(vm_info['v_total'] - vm_info['total'])/(1024**3),
            percent=int(percent),
            v_percent=int(v_percent),
            sw_percent=int(sw_percent),
            pids=vm_info['pids']
        )
        
        if warnings:
            status += " | " + " | ".join(warnings)
        
        self.status_label.setText(status)
        # 更新托盘动态图标
        self.update_tray_icon(int(percent), int(gpu_percent), v_percent)

    def closeEvent(self, event):
        """根据设置决定关闭行为"""
        if self.settings.get('close_to_tray', True):
            if self.tray_icon.isVisible():
                self.hide()
                event.ignore()
                return
        
        # 否则真正退出
        self.worker_thread.quit()
        self.worker_thread.wait()
        self.tray_icon.hide()
        super().closeEvent(event)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    
    # 如果启动参数包含 --minimized，则不调用 show()，程序会直接在托盘运行
    if "--minimized" not in sys.argv:
        window.show()
    
    sys.exit(app.exec())
