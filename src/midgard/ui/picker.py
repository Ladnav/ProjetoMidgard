"""Visual coordinate and color pixel picker dialog."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import QDialog, QLabel, QToolTip, QVBoxLayout, QWidget


class PickerLabel(QLabel):
    """Custom QLabel that handles mouse movement coordinates and click selectors."""

    def __init__(self, pixmap: QPixmap, on_clicked) -> None:
        super().__init__()
        self.setPixmap(pixmap)
        self.on_clicked = on_clicked
        self.setMouseTracking(True)
        # Convert QPixmap to QImage for fast coordinate pixel color access
        self.qimage = pixmap.toImage()

    def mouseMoveEvent(self, event) -> None:
        pos = event.position().toPoint()
        x, y = pos.x(), pos.y()
        if 0 <= x < self.qimage.width() and 0 <= y < self.qimage.height():
            color = QColor(self.qimage.pixel(pos))
            r, g, b = color.red(), color.green(), color.blue()
            QToolTip.showText(
                event.globalPosition().toPoint(),
                f"Position: ({x}, {y})\nRGB Color: ({r}, {g}, {b})",
                self,
            )
        super().mouseMoveEvent(event)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.position().toPoint()
            x, y = pos.x(), pos.y()
            if 0 <= x < self.qimage.width() and 0 <= y < self.qimage.height():
                color = QColor(self.qimage.pixel(pos))
                self.on_clicked(x, y, color.red(), color.green(), color.blue())
        super().mousePressEvent(event)


class PickDialog(QDialog):
    """Dialog showing the game screen capture to select coordinates and colors."""

    def __init__(self, pixmap: QPixmap, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Midgard Picker — Click to select position & color")
        self.setModal(True)

        # Selected metrics
        self.selected_x: int | None = None
        self.selected_y: int | None = None
        self.selected_r: int | None = None
        self.selected_g: int | None = None
        self.selected_b: int | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.picker_label = PickerLabel(pixmap, self._on_clicked)
        layout.addWidget(self.picker_label)

    def _on_clicked(self, x: int, y: int, r: int, g: int, b: int) -> None:
        self.selected_x = x
        self.selected_y = y
        self.selected_r = r
        self.selected_g = g
        self.selected_b = b
        self.accept()


class WindowListDialog(QDialog):
    """List matching windows and allow user to select one for injection."""

    def __init__(self, windows: list[tuple[int, int, str]], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Select Target Client Window")
        self.setMinimumSize(460, 260)
        self.setModal(True)

        self.selected_hwnd: int | None = None
        self.selected_pid: int | None = None
        self.selected_title: str | None = None

        layout = QVBoxLayout(self)

        from PySide6.QtWidgets import QListWidget, QListWidgetItem, QDialogButtonBox
        self.list_widget = QListWidget()
        for hwnd, pid, title in windows:
            # Display clearly matching PID and process window name
            item = QListWidgetItem(f"HWND: {hwnd} | PID: {pid} | Title: {title}")
            item.setData(Qt.ItemDataRole.UserRole, (hwnd, pid, title))
            self.list_widget.addItem(item)

        layout.addWidget(self.list_widget)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._accept_selection)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _accept_selection(self) -> None:
        current_item = self.list_widget.currentItem()
        if current_item:
            data = current_item.data(Qt.ItemDataRole.UserRole)
            if data:
                self.selected_hwnd, self.selected_pid, self.selected_title = data
                self.accept()
                return
        self.reject()
