from PyQt6.QtWidgets import QCheckBox, QDoubleSpinBox
from PyQt6.QtCore import Qt, QPropertyAnimation, QEasingCurve, pyqtProperty, QPointF
from PyQt6.QtGui import QPainter, QColor, QPen, QLinearGradient, QBrush

class SafeDoubleSpinBox(QDoubleSpinBox):
    """只有在获得焦点（点击）后才响应滚轮事件的数字输入框，防止滚动页面时误触"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def wheelEvent(self, event):
        if self.hasFocus():
            super().wheelEvent(event)
        else:
            # 如果没有焦点，将事件传递给父窗口（即允许页面滚动）
            event.ignore()

class SwitchButton(QCheckBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(55, 28)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._thumb_pos = 0.0 # 初始比例 (0.0 到 1.0)
        self._anim = QPropertyAnimation(self, b"thumb_pos")
        self._anim.setDuration(200)
        self._anim.setEasingCurve(QEasingCurve.Type.InOutQuad)

    @pyqtProperty(float)
    def thumb_pos(self):
        return self._thumb_pos

    @thumb_pos.setter
    def thumb_pos(self, pos):
        self._thumb_pos = pos
        self.update()

    def setChecked(self, checked):
        super().setChecked(checked)
        self._thumb_pos = 1.0 if checked else 0.0
        self.update()

    def hitButton(self, pos):
        return self.contentsRect().contains(pos)

    def nextCheckState(self):
        super().nextCheckState()
        end = 1.0 if self.isChecked() else 0.0
        self._anim.stop()
        self._anim.setStartValue(self._thumb_pos)
        self._anim.setEndValue(end)
        self._anim.start()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        h = self.height()
        w = self.width()
        # 动态计算滑块半径和边距
        margin = 3
        radius = (h - margin * 2) / 2
        # 滑块在 X 轴上的活动范围
        start_x = margin + radius
        end_x = w - margin - radius
        # 当前滑块中心 X 坐标
        curr_x = start_x + (end_x - start_x) * self._thumb_pos
        
        # 1. 绘制背景轨道
        bg_color = QColor(38, 166, 154) if self.isChecked() else QColor(117, 117, 117)
        painter.setBrush(bg_color)
        painter.setPen(QPen(QColor(0, 0, 0, 40), 1))
        painter.drawRoundedRect(0, 0, w, h, h/2, h/2)
        
        # 2. 绘制滑块
        gradient = QLinearGradient(curr_x, margin, curr_x, h - margin)
        gradient.setColorAt(0, QColor(255, 255, 255))
        gradient.setColorAt(1, QColor(230, 230, 230))
        
        painter.setBrush(QBrush(gradient))
        painter.setPen(QPen(QColor(0, 0, 0, 60), 0.5))
        painter.drawEllipse(QPointF(curr_x, h / 2), radius, radius)

