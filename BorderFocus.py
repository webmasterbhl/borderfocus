from PyQt5.QtCore import QEvent, QObject, pyqtSignal, Qt, QTimer, QPoint
from PyQt5.QtWidgets import QSlider, QPushButton, QWidget, QHBoxLayout, QToolBar, QApplication
from PyQt5.QtGui import QCursor  # Importación adicional para controlar la posición del cursor del ratón
from qgis.core import QgsPointXY
from qgis.gui import QgsRubberBand
import qgis.utils

class CustomToolBar(QToolBar):
    def __init__(self, title, parent=None):
        super().__init__(title, parent)
        self.closeButton = QPushButton('X', self)
        self.closeButton.setObjectName('closeButton')
        self.closeButton.setFixedWidth(20)
        self.closeButton.setFixedHeight(20)
        self.closeButton.setVisible(False)

    def event(self, event):
        if event.type() == QEvent.WindowActivate or event.type() == QEvent.WindowDeactivate:
            self.closeButton.setVisible(self.isFloating())
        return super().event(event)

class MouseClickInterceptor(QObject):
    borderClicked = pyqtSignal(QgsPointXY)

    def __init__(self, canvas, borderControl):
        super().__init__()
        self.canvas = canvas
        self.borderControl = borderControl
        self.borderClicked.connect(self.centerMap)
        self.canvas.viewport().installEventFilter(self)
        self.active = False

    def eventFilter(self, obj, event):
        if not self.active:
            return super().eventFilter(obj, event)

        if event.type() == QEvent.MouseButtonRelease and obj is self.canvas.viewport():
            point = self.canvas.getCoordinateTransform().toMapCoordinates(event.pos().x(), event.pos().y())
            border_zone = self.borderControl.getBorderZone()

            if not border_zone.contains(point):
                QTimer.singleShot(50, lambda: self.borderClicked.emit(point))
                return True
        return super().eventFilter(obj, event)

    def centerMap(self, point):
        self.canvas.setCenter(point)
        self.canvas.refresh()
        
        centerPoint = self.canvas.viewport().rect().center()
        globalCenterPoint = self.canvas.viewport().mapToGlobal(centerPoint)
        QCursor.setPos(globalCenterPoint)

class BorderControl:
    def __init__(self, canvas):
        self.canvas = canvas

        totalWidth = 200

        self.slider = QSlider(Qt.Horizontal)
        sliderWidth = 90
        self.slider.setFixedWidth(sliderWidth)
        self.slider.setMinimum(100)
        self.slider.setMaximum(150)
        self.slider.setValue(125)
        self.slider.valueChanged.connect(self.updateBorder)

        self.toggleButton = QPushButton()
        self.toggleButton.setCheckable(True)
        self.toggleButton.toggled.connect(self.toggle)
        self.toggleButton.setStyleSheet("background-color: red; color: white; border: none; margin-left: 19px;")
        buttonWidth = 38
        self.toggleButton.setFixedWidth(buttonWidth)
        self.toggleButton.setFixedHeight(buttonWidth)
        self.toggleButton.setText("C")

        self.toolbarWidget = QWidget()
        self.toolbarWidget.setFixedWidth(totalWidth)

        layout = QHBoxLayout()
        layout.addWidget(self.slider)
        layout.addWidget(self.toggleButton)
        self.toolbarWidget.setLayout(layout)

        self.toolbar = CustomToolBar("Border Focus")
        self.toolbar.addWidget(self.toolbarWidget)
        self.toolbar.setMovable(True)
        self.toolbar.setFloatable(True)
        self.toolbar.closeButton.clicked.connect(self.closeToolbar)

        layout.addWidget(self.toolbar.closeButton)

        qgis.utils.iface.addToolBar(self.toolbar)

        self.border = QgsRubberBand(self.canvas, False)
        self.border.setColor(Qt.transparent)
        self.border.setWidth(2)
        self.border.setLineStyle(Qt.SolidLine)

        self.canvas.extentsChanged.connect(self.updateBorder)

        self.mouseInterceptor = MouseClickInterceptor(self.canvas, self)

    def updateBorder(self):
        if not self.toggleButton.isChecked():
            self.border.reset()
            return

        self.border.reset()
        extent = self.canvas.extent()
        border_zone = extent.buffered(-min(extent.width(), extent.height()) * (self.slider.value() - 100) / 500)

        self.border.addPoint(QgsPointXY(border_zone.xMinimum(), border_zone.yMinimum()))
        self.border.addPoint(QgsPointXY(border_zone.xMaximum(), border_zone.yMinimum()))
        self.border.addPoint(QgsPointXY(border_zone.xMaximum(), border_zone.yMaximum()))
        self.border.addPoint(QgsPointXY(border_zone.xMinimum(), border_zone.yMaximum()))
        self.border.addPoint(QgsPointXY(border_zone.xMinimum(), border_zone.yMinimum()))

    def getBorderZone(self):
        extent = self.canvas.extent()
        return extent.buffered(-min(extent.width(), extent.height()) * (self.slider.value() - 100) / 500)

    def toggle(self, checked):
        self.mouseInterceptor.active = checked
        color = "green" if checked else "red"
        text = "O" if checked else "C"
        self.toggleButton.setText(text)
        self.toggleButton.setStyleSheet(f"background-color: {color}; color: white; border: none; margin-left: 19px;")
        borderColor = Qt.black if checked else Qt.transparent
        self.border.setColor(borderColor)
        self.border.setLineStyle(Qt.DotLine if checked else Qt.SolidLine)
        self.updateBorder()

        if not checked:
            self.border.reset()

    def closeToolbar(self):
        self.toolbar.hide()
        self.toggleButton.setChecked(False)

class BorderFocus:
    def __init__(self, iface):
        self.iface = iface
        self.borderControl = None

    def initGui(self):
        self.borderControl = BorderControl(self.iface.mapCanvas())

    def unload(self):
        if self.borderControl:
            self.borderControl.closeToolbar()
            self.borderControl = None
