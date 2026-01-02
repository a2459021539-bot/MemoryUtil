from PyQt6.QtWidgets import QWidget, QMenu
from PyQt6.QtCore import Qt, QRectF, QPointF, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QFont, QLinearGradient, QFontMetrics, QAction
from utils.treemap_logic import squarify_layout
from config import I18N

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
        painter.setPen(Qt.PenStyle.NoPen)
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
                        
                        lang = self.lang if self.lang in I18N else 'zh'
                        t = I18N[lang]
                        t_label = t.get('phys_label', "Phys") if label == "物理" else t.get('virt_label', "Virt")
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
        pos = QPointF(event.pos())
        item = self._get_item_at(pos)
        if item:
            self.itemRightClicked.emit(item, QPointF(event.globalPos()))

    def mouseDoubleClickEvent(self, event):
        pos = QPointF(event.pos())
        item = self._get_item_at(pos)
        if item:
            self.itemDoubleClicked.emit(item)

    def mouseMoveEvent(self, event):
        pos = QPointF(event.pos())
        item = self._get_item_at(pos)
        if item != self.hovered_item:
            self.hovered_item = item
            self.update()
        
        if item and not item.children:
            self.setToolTip(f"{item.name}\n{item.formatted_size()}")
        else:
            self.setToolTip("")

    def _get_item_at(self, pos):
        # 确保 pos 是 QPointF 类型，以匹配 QRectF.contains
        if not isinstance(pos, QPointF):
            pos = QPointF(pos)
            
        # 优先检测子节点（进程）
        for group in self.root_items:
            if group.children:
                for child in group.children:
                    if child.rect.contains(pos):
                        return child
        # 其次检测顶级分组
        for group in self.root_items:
            if group.rect.contains(pos):
                return group
        return None
