from PyQt6.QtWidgets import QCheckBox
from PyQt6.QtCore import Qt, QPropertyAnimation, QEasingCurve, pyqtProperty, QPointF
from PyQt6.QtGui import QPainter, QColor, QPen, QLinearGradient, QBrush

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

