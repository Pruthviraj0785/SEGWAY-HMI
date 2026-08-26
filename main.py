import sys
import re
import serial
import pynmea2
import time
from pathlib import Path
from datetime import datetime

import os
os.environ["PYQTGRAPH_QT_LIB"] = "PySide6"

import cv2

from PySide6.QtWidgets import (
    QSizePolicy,
    QApplication,
    QWidget,
    QFrame,
    QLabel,
    QPushButton, QStyle,
    QLineEdit,
    QMessageBox,
    QVBoxLayout,
    QHBoxLayout,
    QDialog,
    QListWidget,
    QListWidgetItem
)

from PySide6.QtGui import (
    QPixmap,
    QImage,
    QFont,
    QColor,
    QCursor,
    QPalette,
    QDesktopServices
)

from PySide6.QtCore import (
    QObject,
    QEvent,
    Qt,
    QTimer,
    QDateTime,
    QUrl,
    QSize,
    QFile
)

from PySide6.QtUiTools import QUiLoader

import pyqtgraph as pg
from pyqtgraph import PlotWidget


# ============================
# Backend Modules
# ============================

from backend.uart import UART
from backend.battery import Battery
from backend.motor import Motor
from backend.camera import Camera
from backend.graph import Graph
from backend.diagnostics import Diagnostics
from backend.settings import Settings
from backend.password_manager import PasswordManager


class ThreeTapScreenshotFilter(QObject):
    def __init__(self, hmi):
        super().__init__()
        self.hmi = hmi
        self.taps = 0
        self.last_tap = 0.0

    def eventFilter(self, obj, event):
        if event.type() in (
            QEvent.Type.MouseButtonPress,
            QEvent.Type.TouchBegin,
        ):
            import time
            now = time.monotonic()

            if now - self.last_tap > 2.0:
                self.taps = 0

            self.last_tap = now
            self.taps += 1

            print(f"SCREENSHOT TAP {self.taps}/3")

            if self.taps == 3:
                self.hmi.save_temporary_screenshot()
                self.taps = 0

        return False


class SegwayHMI:

    def __init__(self):

      
        self.app = QApplication(sys.argv)

        self.loader = QUiLoader()

        self.window = None

        # Backend
        self.uart = UART()
        self.battery = Battery()
        self.motor = Motor()

        # Camera
        self.camera = Camera()
        self.camera_started = False
        self.recording = False
        self.video_writer = None
        self.camera_label = None

        self.camera_timer = QTimer()
        self.camera_timer.timeout.connect(
            self.update_camera_frame
        )

        # Graph
        self.graph = Graph()
        self.plot = None

        # ==========================================================
        # M89 GPS
        # ==========================================================

        self.gps_serial = None
        self.gps_port = "/dev/serial0"
        self.gps_baud = 9600

        self.gps_latitude = None
        self.gps_longitude = None
        self.gps_altitude = None
        self.gps_speed = None
        self.gps_satellites = 0
        self.gps_fix = False

        self.gps_timer = QTimer()
        self.gps_timer.timeout.connect(self.read_gps)
        self.gps_timer.start(200)

        # Diagnostics
        self.diag = Diagnostics()

        # Settings
        self.settings = Settings()

        # Password protection
        self.password_manager = PasswordManager()

        # Demo values
        self.voltage = 48.2
        self.current = 5.1
        self.rpm = 850
        self.speed = 12.5
        self.pitch = 2.4
        self.roll = -1.1
        self.yaw = 180
        self.temperature = 33

        self.max_speed = 25
        self.acceleration = 50
        self.brake_strength = 50
        self.graph_time = 0

        # Dashboard timer
        self.timer = QTimer()
        self.timer.timeout.connect(
            self.update_dashboard
        )

        self.timer.start(500)       

        # Clock
        self.clock_timer = QTimer()
        self.clock_timer.timeout.connect(
            self.update_clock
        )
        self.clock_timer.start(1000)

        self.update_clock()

        # ==========================================================
        # THEME
        # ==========================================================

        self.dark_mode = False

        # Original Qt Designer styles for CURRENT page

    def save_temporary_screenshot(self):
        try:
            folder = Path.home() / "HMI_Screenshots"
            folder.mkdir(parents=True, exist_ok=True)

            filename = folder / (
                "HMI_" +
                datetime.now().strftime("%Y%m%d_%H%M%S") +
                ".png"
            )

            pixmap = self.window.grab()
            ok = pixmap.save(str(filename), "PNG")

            if ok:
                print("========================================")
                print("SCREENSHOT SAVED:")
                print(filename)
                print("========================================")
            else:
                print("ERROR: Screenshot could not be saved")

        except Exception as e:
            print("SCREENSHOT ERROR:", e)

    def apply_theme(self):

        if self.window is None:
            return

        # ==========================================================
        # PAGE BACKGROUND ONLY
        #
        # DO NOT TOUCH CHILD WIDGET STYLES.
        # Qt Designer already contains:
        # - card borders
        # - colours
        # - fonts
        # - radius
        # - padding
        # - button appearance
        # ==========================================================

        if self.dark_mode:

            page_bg = "#1E1E1E"

        else:

            page_bg = "#FFFFFF"

        # ==========================================================
        # ONLY CHANGE THE ROOT PAGE BACKGROUND
        # ==========================================================

        self.window.setStyleSheet(
            f"""
            QWidget#{self.window.objectName()} {{
                background-color: {page_bg};
            }}
            """
        )

        # ==========================================================
        # THEME BUTTON
        # ==========================================================

        if hasattr(self.window, "btnDarkTheme"):

            if self.dark_mode:

                self.window.btnDarkTheme.setText(
                    "LIGHT THEME"
                )

            else:

                self.window.btnDarkTheme.setText(
                    "DARK THEME"
                )

        # ==========================================================
        # GRAPH
        # ==========================================================

        if self.plot is not None:

            self.plot.setBackground(
                page_bg
            )

            axis_text = "#FFFFFF" if self.dark_mode else "#172B4D"

            self.plot.getAxis("left").setPen(
                axis_text
            )

            self.plot.getAxis("bottom").setPen(
                axis_text
            )

            self.plot.getAxis("left").setTextPen(
                axis_text
            )

            self.plot.getAxis("bottom").setTextPen(
                axis_text
            )

        # ==========================================================
        # REFRESH
        # ==========================================================

        self.window.update()
        self.window.repaint()
   
    def toggle_theme(self):

        if self.window is None:
            return

        self.dark_mode = not self.dark_mode

        print("================================")
        print("THEME BUTTON PRESSED")
        print(
            "THEME:",
            "DARK" if self.dark_mode else "LIGHT"
        )
        print("================================")

        self.apply_theme()

    def setup_time_date_labels(self):

        # ==========================================================
        # FINAL COMMON TIME + DATE
        # SAME POSITION ON EVERY HMI PAGE
        # ==========================================================

        if self.window is None:
            return

        # TIME
        if not hasattr(self.window, "timeLabel"):

            self.window.timeLabel = QLabel(
                self.window
            )

            self.window.timeLabel.setObjectName(
                "timeLabel"
            )

        self.window.timeLabel.setGeometry(
            840,
            18,
            160,
            27
        )

        self.window.timeLabel.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        self.window.timeLabel.setFont(
            QFont(
                "Arial",
                14,
                QFont.Weight.Bold
            )
        )

        self.window.timeLabel.setStyleSheet(
            """
            QLabel {
                color: #00FF66;
                background-color: transparent;
                border: none;
            }
            """
        )

        self.window.timeLabel.show()

        # DATE
        if not hasattr(self.window, "dateLabel"):

            self.window.dateLabel = QLabel(
                self.window
            )

            self.window.dateLabel.setObjectName(
                "dateLabel"
            )

        self.window.dateLabel.setGeometry(
            830,
            45,
            170,
            27
        )

        self.window.dateLabel.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        self.window.dateLabel.setFont(
            QFont(
                "Arial",
                14,
                QFont.Weight.Bold
            )
        )

        self.window.dateLabel.setStyleSheet(
            """
            QLabel {
                color: #00FF66;
                background-color: transparent;
                border: none;
            }
            """
        )

        self.window.dateLabel.show()

        self.window.timeLabel.raise_()
        self.window.dateLabel.raise_()

        print(
            "FINAL TIME/DATE POSITION:",
            "TIME = (840,18,160,27)",
            "DATE = (830,45,170,27)"
        )

    def load_page(self, filename):

        # ==========================================================
        # STOP CAMERA
        # ==========================================================

        if self.window is not None:

            if self.camera_started:

                self.camera_timer.stop()
                self.camera.stop()

                self.camera_started = False
                self.camera_label = None

                print("Camera Stopped")

        print(">>>>>>>>>>>>")
        print("Requested:", filename)
        print("<<<<<<<<<<<<")

        # ==========================================================
        # CLOSE OLD PAGE
        # ==========================================================

        if self.window is not None:

            self.plot = None

            self.window.close()
            self.window.deleteLater()

            self.window = None

        # ==========================================================
        # RESET STYLE MEMORY
        # ==========================================================

        #self.original_widget_styles = {}

        # ==========================================================
        # LOAD UI
        # ==========================================================

        file = QFile(
            "ui/" + filename
        )

        if not file.open(
            QFile.ReadOnly
        ):

            QMessageBox.critical(
                None,
                "Error",
                "Cannot open\n" + filename
            )

            return

        self.window = self.loader.load(
            file
        )

        file.close()

        if self.window is None:

            QMessageBox.critical(
                None,
                "Error",
                "Failed Loading " + filename
            )

            return


        # FULLSCREEN LCD DISPLAY
        # ==========================================================

        self.window.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
        )

        self.window.setMinimumSize(
            0,
            0
        )

        self.window.setMaximumSize(
            16777215,
            16777215
        )

        # ==========================================================
        # DEBUG
        # ==========================================================

        print("========================")
        print("Loading :", filename)
        print(
            "Object  :",
            self.window.objectName()
        )
        print("========================")

        # ==========================================================
        # BUTTONS
        # ==========================================================

        self.connect_buttons()

        # ==========================================================
        # PAGE INITIALIZATION
        # ==========================================================

        self.initialize_page(
            filename
        )

        # FIT PAGE TO REAL LCD
        self.fit_page_to_lcd(filename)

        # ==========================================================
        # HOME CARD LAYOUT
        # ==========================================================

        if filename == "home.ui":
            self.arrange_home_layout()

        # ==========================================================
        # FINAL TIME + DATE POSITION
        # ==========================================================

        self.setup_time_date_labels()


        # ==========================================================
        # CLOCK
        # ==========================================================

        self.update_clock()

        # ==========================================================
        # APPLY CURRENT THEME
        # ==========================================================

        #self.apply_theme()
       # ==========================================================
        # SHOW
        # ==========================================================

        # ==========================================================
        # SHOW HMI ON RASPBERRY PI LCD
        # ==========================================================
        # TEMPORARY 3-TAP SCREENSHOT DETECTOR
        self._three_tap_filter = ThreeTapScreenshotFilter(self)

        self.window.installEventFilter(self._three_tap_filter)

        for _widget in self.window.findChildren(QWidget):
            _widget.installEventFilter(self._three_tap_filter)

        self.window.show()
        self.window.update()
        self.window.repaint()

        # Wayland: apply fullscreen after the surface exists.
        self.window.showFullScreen()
        self.window.update()
        self.window.repaint()

    def fit_page_to_lcd(self, filename):
        # ==========================================================
        # OPTION 1 - FIT COMPLETE HMI TO 1024x600 LCD
        # ==========================================================

        if self.window is None:
            return

        original_sizes = {
            # Pages already fitted to the real LCD
            "main_menu.ui": (1024, 600),
            "home.ui": (1024, 600),
            "battery.ui": (800, 600),
            "camera.ui": (1024, 600),
            "graph.ui": (1024, 600),

            # KEEP THESE PAGES UNTOUCHED
            "motor.ui": (800, 741),
            "diagnostics.ui": (800, 741),
            "dignostics.ui": (800, 758),
            "dashboard.ui": (800, 747),
            "settings.ui": (800, 741),
            "main_window.ui": (843, 802),
        }

        original_w, original_h = original_sizes.get(
            filename,
            (800, 741)
        )

        screen = QApplication.primaryScreen()

        if screen is None:
            return

        target_w = 1024
        target_h = 600

        sx = target_w / original_w
        sy = target_h / original_h

        print(
            "LCD FIT:",
            filename,
            original_w,
            "x",
            original_h,
            "->",
            target_w,
            "x",
            target_h,
            "scale:",
            round(sx, 3),
            round(sy, 3)
        )

        for widget in self.window.findChildren(QWidget):

            g = widget.geometry()

            x = int(round(g.x() * sx))
            y = int(round(g.y() * sy))
            w = int(round(g.width() * sx))
            h = int(round(g.height() * sy))

            widget.setGeometry(
                x,
                y,
                w,
                h
            )

            font = widget.font()
            size = font.pointSizeF()

            if size > 0:
                font.setPointSizeF(
                    max(
                        1.0,
                        size * ((sx + sy) / 2.0)
                    )
                )
                widget.setFont(font)

        self.window.resize(
            target_w,
            target_h
        )

        self.window.update()
        self.window.repaint()


    def arrange_real_menu_columns(self):

        if self.window is None:
            return

        from PySide6.QtWidgets import QLabel
        from PySide6.QtCore import Qt

        items = {
            "btnHome":        ("🏠", "HOME",        "Open Live Dashboard"),
            "btnBattery":     ("🔋", "BATTERY",     "Battery Management"),
            "btnMotor":       ("⚙️", "MOTOR",       "Motor Monitoring"),
            "btnCamera":      ("📷", "CAMERA",      "Live Pi Camera"),
            "btnGraphs":      ("📈", "LIVE GRAPHS", "Sensor Analytics"),
            "btnDiagnostics": ("📡", "DIAGNOSTICS", "System Health"),
            "btnSettings":    ("⚙️", "SETTINGS",    "Configuration"),
            "btnAbout":       ("ℹ️", "ABOUT",       "Project Information"),
        }

        for name, (emoji, title, info) in items.items():

            button = getattr(self.window, name, None)

            if button is None:
                continue

            button.setText("")

            for child in button.findChildren(QLabel):
                if child.objectName().startswith("menuColumn_"):
                    child.deleteLater()

            # ==========================================
            # FIXED COLUMNS
            # Extra side breathing room
            # ==========================================

            # LEFT GAP + EMOJI
            icon = QLabel(emoji, button)
            icon.setObjectName("menuColumn_icon")
            icon.setGeometry(25, 0, 45, 50)
            icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
            icon.setAttribute(
                Qt.WidgetAttribute.WA_TransparentForMouseEvents
            )
            icon.setStyleSheet(
                "background:transparent;"
                "color:white;"
                "font-family:'Noto Color Emoji';"
                "font-size:16pt;"
            )

            # TITLE
            title_label = QLabel(title, button)
            title_label.setObjectName("menuColumn_title")
            title_label.setGeometry(75, 0, 155, 50)
            title_label.setAlignment(
                Qt.AlignmentFlag.AlignVCenter |
                Qt.AlignmentFlag.AlignLeft
            )
            title_label.setAttribute(
                Qt.WidgetAttribute.WA_TransparentForMouseEvents
            )
            title_label.setStyleSheet(
                "background:transparent;"
                "color:white;"
                "font-family:'DejaVu Sans';"
                "font-size:14pt;"
                "font-weight:700;"
            )

            # EXPLANATION — MOVED FURTHER RIGHT
            info_label = QLabel(info, button)
            info_label.setObjectName("menuColumn_info")
            info_label.setGeometry(285, 0, 255, 50)
            info_label.setAlignment(
                Qt.AlignmentFlag.AlignVCenter |
                Qt.AlignmentFlag.AlignLeft
            )
            info_label.setAttribute(
                Qt.WidgetAttribute.WA_TransparentForMouseEvents
            )
            info_label.setStyleSheet(
                "background:transparent;"
                "color:white;"
                "font-family:'DejaVu Sans';"
                "font-size:13pt;"
                "font-weight:600;"
            )

            # ARROW — WITH RIGHT GAP
            arrow = QLabel("➜", button)
            arrow.setObjectName("menuColumn_arrow")
            arrow.setGeometry(560, 0, 55, 50)
            arrow.setAlignment(Qt.AlignmentFlag.AlignCenter)
            arrow.setAttribute(
                Qt.WidgetAttribute.WA_TransparentForMouseEvents
            )
            arrow.setStyleSheet(
                "background:transparent;"
                "color:white;"
                "font-family:'DejaVu Sans';"
                "font-size:15pt;"
                "font-weight:700;"
            )

            for label in (
                icon,
                title_label,
                info_label,
                arrow,
            ):
                label.show()
                label.raise_()

            button.raise_()

        print("MENU: SIDE GAPS + RIGHT-SHIFTED EXPLANATION READY")


    def initialize_page(self, filename):

        if filename == "main_menu.ui":
            self.arrange_real_menu_columns()

        if filename == "home.ui":

            self.load_home()

        elif filename == "battery.ui":

            self.load_battery()

        elif filename == "motor.ui":

            self.load_motor()

        elif filename == "camera.ui":

            self.load_camera()

        elif filename == "graph.ui":

            self.plot = PlotWidget()

            if self.dark_mode:

                self.plot.setBackground(
                    "#1E1E1E"
                )

            else:

                self.plot.setBackground(
                    "#FFFFFF"
                )

            self.plot.showGrid(
                x=True,
                y=True,
                alpha=0.25
            )

            # ==========================================
            # GRAPH WIDGET — FILL GRAPH FRAME
            # ==========================================

            frame = self.window.graphFrame

            # Remove any previous layout from this frame
            old_layout = frame.layout()

            if old_layout is not None:
                while old_layout.count():
                    item = old_layout.takeAt(0)
                    widget = item.widget()

                    if widget is not None:
                        widget.deleteLater()

                old_layout.deleteLater()

            layout = QVBoxLayout(frame)

            layout.setContentsMargins(
                3, 3, 3, 3
            )

            layout.setSpacing(0)

            layout.addWidget(
                self.plot,
                1
            )

            self.plot.setSizePolicy(
                QSizePolicy.Policy.Expanding,
                QSizePolicy.Policy.Expanding
            )

            self.load_graph()

        elif filename == "diagnostics.ui":

            self.load_diagnostics()

        elif filename == "settings.ui":

            self.load_settings()

    def save_settings_action(self):
        """Save the current Settings backend configuration."""
        try:
            data = self.settings.load()

            if hasattr(self.window, "brightnessSlider"):
                data["brightness"] = self.window.brightnessSlider.value()

            self.settings.save(data)

            QMessageBox.information(
                self.window,
                "Settings",
                "Settings saved successfully."
            )

            print("SETTINGS SAVED")

        except Exception as e:
            QMessageBox.critical(
                self.window,
                "Settings Error",
                "Unable to save settings.\\n" + str(e)
            )
            print("SETTINGS SAVE ERROR:", e)

    def restore_defaults_action(self):
        """Restore the existing Settings backend defaults."""
        try:
            self.settings.reset()

            self.load_settings()

            QMessageBox.information(
                self.window,
                "Settings",
                "Settings restored to defaults."
            )

            print("SETTINGS RESTORED TO DEFAULTS")

        except Exception as e:
            QMessageBox.critical(
                self.window,
                "Settings Error",
                "Unable to restore defaults.\\n" + str(e)
            )
            print("SETTINGS RESTORE ERROR:", e)

    def load_settings(self):

        # Settings page display values
        self.window.lblbluetoothValue.setText("OFF")
        self.window.lblexposureValue.setText("AUTO")
        self.window.lblBreakstrengthValue.setText("Strong")
        self.window.lbluartValue.setText("115200")
        self.window.lblmaxspeedValue.setText("12 km/h")
        self.window.lblbrightnessValue.setText("80%")
        self.window.lblwifiValue.setText("Connected")
        self.window.lblvolumeValue.setText("60%")
        self.window.lblAccelerationValue.setText("Medium")

        # Brightness slider
        if hasattr(self.window, "brightnessSlider"):
            self.window.brightnessSlider.setValue(80)

        print("SETTINGS PAGE LOADED")
    def arrange_home_layout(self):

        if self.window is None:
            return

        print("ARRANGING HOME - FINAL MOTOR/SETTINGS STYLE")

        # ==========================================================
        # TOP BAR
        # ==========================================================

        if hasattr(self.window, "btnMenu_2"):
            self.window.btnMenu_2.setGeometry(30, 30, 161, 51)
            self.window.btnMenu_2.setText("← MENU")
            self.window.btnMenu_2.raise_()

        if hasattr(self.window, "lblhome"):
            self.window.lblhome.setGeometry(420, 18, 180, 40)
            self.window.lblhome.setAlignment(
                Qt.AlignmentFlag.AlignCenter
            )

        # ==========================================================
        # TIME / DATE
        # ==========================================================

        if hasattr(self.window, "timeLabel"):
            self.window.timeLabel.setGeometry(840, 18, 160, 27)
            self.window.timeLabel.setAlignment(
                Qt.AlignmentFlag.AlignCenter
            )
            self.window.timeLabel.raise_()

        if hasattr(self.window, "dateLabel"):
            self.window.dateLabel.setGeometry(830, 45, 170, 27)
            self.window.dateLabel.setAlignment(
                Qt.AlignmentFlag.AlignCenter
            )
            self.window.dateLabel.raise_()

        # ==========================================================
        # SPEED
        # ==========================================================

        if hasattr(self.window, "speedTitleLabel"):
            self.window.speedTitleLabel.setGeometry(
                365, 70, 290, 35
            )
            self.window.speedTitleLabel.setAlignment(
                Qt.AlignmentFlag.AlignCenter
            )

        if hasattr(self.window, "speedValueLabel"):
            self.window.speedValueLabel.setGeometry(
                335, 105, 350, 65
            )
            self.window.speedValueLabel.setAlignment(
                Qt.AlignmentFlag.AlignCenter
            )

        # ==========================================================
        # THREE COLUMN CARD LAYOUT
        # ==========================================================

        card_w = 205
        card_h = 78

        x1 = 90
        x2 = 410
        x3 = 730

        # Row 1
        y1 = 185

        # Row 2
        y2 = 280

        # Row 3
        y3 = 375

        # ==========================================================
        # VOLTAGE
        # ==========================================================

        if hasattr(self.window, "frameVoltage"):
            self.window.frameVoltage.setGeometry(
                x1, y1, card_w, card_h
            )

        # ==========================================================
        # CURRENT
        # ==========================================================

        if hasattr(self.window, "frameCurrent"):
            self.window.frameCurrent.setGeometry(
                x2, y1, card_w, card_h
            )

        # ==========================================================
        # TEMPERATURE
        # ==========================================================

        if hasattr(self.window, "tempeatuereframe"):
            self.window.tempeatuereframe.setGeometry(
                x3, y1, card_w, card_h
            )

        # ==========================================================
        # LEFT RPM
        # ==========================================================

        if hasattr(self.window, "LefRPMframe"):
            self.window.LefRPMframe.setGeometry(
                x1, y2, card_w, card_h
            )

        # ==========================================================
        # RIGHT RPM
        # ==========================================================

        if hasattr(self.window, "frameRightRPM"):
            self.window.frameRightRPM.setGeometry(
                x2, y2, card_w, card_h
            )

        # ==========================================================
        # YAW
        # ==========================================================

        if hasattr(self.window, "frameYaw"):
            self.window.frameYaw.setGeometry(
                x3, y2, card_w, card_h
            )

        # ==========================================================
        # PITCH
        # ==========================================================

        if hasattr(self.window, "framePitch"):
            self.window.framePitch.setGeometry(
                x1, y3, card_w, card_h
            )

        # ==========================================================
        # ROLL
        # ==========================================================

        if hasattr(self.window, "frameRoll"):
            self.window.frameRoll.setGeometry(
                x2, y3, card_w, card_h
            )

        # ==========================================================
        # MODE
        # ==========================================================

        if hasattr(self.window, "Modeframe"):
            self.window.Modeframe.setGeometry(
                x3, y3, card_w, card_h
            )

        # ==========================================================
        # CENTER ALL CARD CONTENT
        # ==========================================================

        labels = [
            "voltageTitleLabel",
            "voltageValueLabel",
            "currentTitleLabel",
            "currentValueLabel",
            "temperatureTitleLabel",
            "temperatureValueLabel",
            "leftRPMTitleLabel",
            "leftRPMTitleLabel_2",
            "rightRPMTitleLabel",
            "rightRPMValueLabel",
            "yawTitleLabel",
            "yawValueLabel",
            "pitchTitleLabel",
            "pitchValueLabel",
            "rollTitleLabel_2",
            "rollValueLabel_2",
            "modeTitleLabel",
            "modeValueLabel"
        ]

        for name in labels:
            if hasattr(self.window, name):
                getattr(self.window, name).setAlignment(
                    Qt.AlignmentFlag.AlignCenter
                )

        # ==========================================================
        # FINAL HOME CARD TEXT CENTERING
        # ==========================================================
        # Do NOT move the cards.
        # Make each title/value use the full card width.

        _home_labels = [
            "leftRPMTitleLabel",
            "leftRPMTitleLabel_2",
            "rightRPMTitleLabel",
            "rightRPMValueLabel",
            "voltageTitleLabel",
            "voltageValueLabel",
            "pitchTitleLabel",
            "pitchValueLabel",
            "currentTitleLabel",
            "currentValueLabel",
            "rollTitleLabel",
            "rollValueLabel_2",
            "temperatureTitleLabel",
            "temperatureValueLabel",
            "yawTitleLabel",
            "yawValueLabel",
            "modeTitleLabel",
            "modeValueLabel",
        ]

        for _name in _home_labels:
            if hasattr(self.window, _name):
                _label = getattr(self.window, _name)
                _parent = _label.parentWidget()

                if _parent is not None:
                    _g = _label.geometry()

                    # Center inside the actual parent/card.
                    _label.setGeometry(
                        0,
                        _g.y(),
                        _parent.width(),
                        _g.height()
                    )

                _label.setAlignment(
                    Qt.AlignmentFlag.AlignCenter |
                    Qt.AlignmentFlag.AlignVCenter
                )

        # ==========================================================
        # SYSTEM STATUS - FINAL CENTERED LAYOUT
        # ==========================================================

        if hasattr(self.window, "segwayStatusFrame"):

            self.window.segwayStatusFrame.setGeometry(
                150, 475, 724, 90
            )

            self.window.segwayStatusFrame.raise_()

        # These coordinates are RELATIVE to segwayStatusFrame.
        if hasattr(self.window, "segwayStatusTitle"):

            self.window.segwayStatusTitle.setGeometry(
                0, 5, 724, 25
            )

            font = self.window.segwayStatusTitle.font()
            font.setPointSize(13)
            font.setBold(True)
            self.window.segwayStatusTitle.setFont(font)

            self.window.segwayStatusTitle.setAlignment(
                Qt.AlignmentFlag.AlignCenter |
                Qt.AlignmentFlag.AlignVCenter
            )

            self.window.segwayStatusTitle.setStyleSheet(
                "color: #00FFFF;"
                "background: transparent;"
                "border: none;"
            )

        if hasattr(self.window, "segwayStatusValue"):

            self.window.segwayStatusValue.setGeometry(
                0, 32, 724, 50
            )

            font = self.window.segwayStatusValue.font()
            font.setPointSize(22)
            font.setBold(True)
            self.window.segwayStatusValue.setFont(font)

            self.window.segwayStatusValue.setAlignment(
                Qt.AlignmentFlag.AlignCenter |
                Qt.AlignmentFlag.AlignVCenter
            )

            self.window.segwayStatusValue.setStyleSheet(
                "color: #00FF66;"
                "background: transparent;"
                "border: none;"
            )

        # ==========================================================
        # KEEP MENU / TIME / DATE ABOVE OTHER WIDGETS
        # ==========================================================

        if hasattr(self.window, "btnMenu_2"):
            self.window.btnMenu_2.raise_()

        if hasattr(self.window, "timeLabel"):
            self.window.timeLabel.raise_()

        if hasattr(self.window, "dateLabel"):
            self.window.dateLabel.raise_()

        # ==========================================================
        # HOME MENU BUTTON — FINAL LOCK
        # Match MOTOR MENU exactly
        # ==========================================================

        if hasattr(self.window, "btnMenu_2"):
            self.window.btnMenu_2.setGeometry(
                30, 30, 161, 51
            )
            self.window.btnMenu_2.setText("← MENU")
            self.window.btnMenu_2.show()
            self.window.btnMenu_2.raise_()

        print("HOME MENU FINAL LOCK: 30,30,161,51")
        print("HOME MOTOR/SETTINGS STYLE READY")


    def load_home(self):

        self.window.modeValueLabel.setText(
            "BALANCE"
        )

        self.window.speedValueLabel.setText(
            f"{self.speed:.1f} km/h"
        )

        self.window.voltageValueLabel.setText(
            f"{self.voltage:.1f} V"
        )

        self.window.currentValueLabel.setText(
            f"{self.current:.1f} A"
        )

        self.window.temperatureValueLabel.setText(
            f"{self.temperature:.1f} °C"
        )

        self.window.rightRPMValueLabel.setText(
            str(int(self.rpm))
        )

        self.window.pitchValueLabel.setText(
            f"{self.pitch:.1f}°"
        )

        self.window.rollValueLabel_2.setText(
            f"{self.roll:.1f}°"
        )

        self.window.yawValueLabel.setText(
            f"{self.yaw:.1f}°"
        )

        # ============================================
        # SEGWAY HMI SYSTEM STATUS
        # ============================================

        if hasattr(self.window, "segwayStatusValue"):

            # ============================================
            # LIVE SEGWAY STATUS
            # ============================================

            if self.rpm > 0:
                current_status = "SEGWAY RUNNING"
            elif abs(self.speed) > 0.1:
                current_status = "SEGWAY MOVING"
            elif abs(self.current) > 0.5:
                current_status = "SYSTEM ACTIVE"
            elif self.voltage > 0:
                current_status = "SEGWAY READY"
            else:
                current_status = "SEGWAY OFFLINE"

            self.window.segwayStatusValue.setText(
                current_status
            )



    # ============================================
    # MAIN MENU SYSTEM CONTROLS
    # ============================================

    def start_system_control(self):
        self.system_control_state = "RUNNING"
        print("SYSTEM START")

    def pause_system_control(self):
        self.system_control_state = "PAUSED"
        print("SYSTEM PAUSED")

    def stop_system_control(self):
        self.system_control_state = "STOPPED"
        print("SYSTEM STOPPED")

    # ============================================
    # NAVIGATION
    # ============================================
    # ============================================
    # BATTERY PAGE
    # ============================================

    def load_battery(self):

        self.window.voltageValueLabel.setText(
            f"{self.voltage:.1f} V"
        )

        self.window.currentValueLabel.setText(
            f"{self.current:.1f} A"
        )

        # Battery page touch/navigation protection
        if hasattr(self.window, "btnMenu"):
            self.window.btnMenu.setEnabled(True)
            self.window.btnMenu.setAttribute(
                Qt.WidgetAttribute.WA_TransparentForMouseEvents,
                False
            )
            self.window.btnMenu.raise_()

    def show_gps_popup(self):
        """Show M89 GPS location in a popup."""

        dialog = QDialog(self.window)
        dialog.setWindowTitle("SEGWAY GPS LOCATION")
        dialog.setModal(True)
        dialog.resize(520, 380)

        dialog.setStyleSheet("""
            QDialog {
                background-color: #1e1e1e;
                border: 2px solid #00ff66;
            }

            QLabel {
                color: white;
            }

            QPushButton {
                background-color: #1e1e1e;
                color: white;
                border: 2px solid #00ff66;
                border-radius: 10px;
                padding: 12px;
                font-size: 18px;
                font-weight: bold;
            }

            QPushButton:hover {
                background-color: #00ff66;
                color: black;
            }
        """)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(25, 20, 25, 20)
        layout.setSpacing(15)

        title = QLabel("📍  SEGWAY GPS LOCATION")
        title.setStyleSheet(
            "color: #00ff66; font-size: 26px; font-weight: bold;"
        )
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        status = QLabel("GPS: SEARCHING...")
        status.setStyleSheet(
            "color: #00ff66; font-size: 18px; font-weight: bold;"
        )
        status.setAlignment(Qt.AlignmentFlag.AlignCenter)

        location = QLabel(
            "Latitude:  --\n"
            "Longitude: --\n"
            "Altitude:  --\n"
            "Satellites: --"
        )
        location.setStyleSheet(
            "color: white; font-size: 20px;"
        )
        location.setAlignment(Qt.AlignmentFlag.AlignCenter)

        cancel_btn = QPushButton("CANCEL")
        cancel_btn.clicked.connect(dialog.reject)

        layout.addWidget(title)
        layout.addWidget(status)
        layout.addWidget(location)
        layout.addStretch()
        layout.addWidget(cancel_btn)

        try:
            gps = serial.Serial(
                port="/dev/serial0",
                baudrate=9600,
                timeout=1
            )

            start_time = time.time()
            gps_found = False

            while time.time() - start_time < 5:

                line = gps.readline().decode(
                    "ascii",
                    errors="ignore"
                ).strip()

                if not line.startswith("$"):
                    continue

                if (
                    line.startswith("$GPGGA")
                    or line.startswith("$GNGGA")
                ):

                    parts = line.split(",")

                    if len(parts) >= 10:

                        fix = parts[6]

                        if fix and fix != "0":

                            gps_found = True

                            lat_raw = parts[2]
                            lat_dir = parts[3]

                            lon_raw = parts[4]
                            lon_dir = parts[5]

                            satellites = parts[7]
                            altitude = parts[9]

                            def convert_coordinate(
                                value,
                                direction
                            ):
                                if not value:
                                    return "--"

                                try:
                                    if direction in ("N", "S"):
                                        degrees = float(value[:2])
                                        minutes = float(value[2:])
                                    else:
                                        degrees = float(value[:3])
                                        minutes = float(value[3:])

                                    decimal = (
                                        degrees + minutes / 60
                                    )

                                    if direction in ("S", "W"):
                                        decimal = -decimal

                                    return f"{decimal:.6f}°"

                                except Exception:
                                    return "--"

                            latitude = convert_coordinate(
                                lat_raw,
                                lat_dir
                            )

                            longitude = convert_coordinate(
                                lon_raw,
                                lon_dir
                            )

                            status.setText(
                                "GPS: FIX ACTIVE"
                            )

                            location.setText(
                                f"Latitude:  {latitude}\n"
                                f"Longitude: {longitude}\n"
                                f"Altitude:  {altitude} m\n"
                                f"Satellites: {satellites}\n\n"
                                "Source: M89 GPS"
                            )

                            break

            gps.close()

            if not gps_found:

                status.setText("GPS: NO FIX")
                status.setStyleSheet(
                    "color: #ffcc00; "
                    "font-size: 18px; "
                    "font-weight: bold;"
                )

                location.setText(
                    "Latitude:  --\n"
                    "Longitude: --\n"
                    "Altitude:  --\n"
                    "Satellites: --\n\n"
                    "Waiting for GPS satellite fix..."
                )

        except Exception as e:

            status.setText("GPS: ERROR")
            status.setStyleSheet(
                "color: #ff4444; "
                "font-size: 18px; "
                "font-weight: bold;"
            )

            location.setText(
                "Unable to read M89 GPS.\n\n"
                f"Error:\n{e}"
            )

        dialog.exec()


    def connect_buttons(self):

        # MAP / GPS BUTTON
        if hasattr(self.window, "btnMap"):
            try:
                self.window.btnMap.clicked.disconnect()
            except:
                pass

            self.window.btnMap.clicked.connect(
                self.show_gps_popup
            )

            print("MAP BUTTON CONNECTED")


    # ==========================================
    # MAIN MENU NAVIGATION
    # ==========================================

        if self.window.objectName() == "MainMenu":

            if hasattr(self.window, "btnHome"):
                print("HOME BUTTON FOUND - CONNECTING")
                self.window.btnHome.clicked.connect(
                    lambda: self.load_page("home.ui")
                )
    
            # ==========================================================
            # MAIN MENU START / PAUSE / STOP CONTROLS
            # ==========================================================
            if self.window.objectName() == "MainMenu":

                if hasattr(self.window, "btnStartSystem"):
                    try:
                        self.window.btnStartSystem.clicked.disconnect()
                    except:
                        pass
                    self.window.btnStartSystem.clicked.connect(
                        self.start_system_control
                    )

                if hasattr(self.window, "btnPauseSystem"):
                    try:
                        self.window.btnPauseSystem.clicked.disconnect()
                    except:
                        pass
                    self.window.btnPauseSystem.clicked.connect(
                        self.pause_system_control
                    )

                if hasattr(self.window, "btnStopSystem"):
                    try:
                        self.window.btnStopSystem.clicked.disconnect()
                    except:
                        pass
                    self.window.btnStopSystem.clicked.connect(
                        self.stop_system_control
                    )

                print("CONTROL BUTTONS CONNECTED")

            print("HOME BUTTON CONNECTED")

            if hasattr(self.window, "btnMotor"):
                self.window.btnMotor.clicked.connect(
                    lambda: self.load_page("motor.ui")
                )

            if hasattr(self.window, "btnBattery"):
                self.window.btnBattery.clicked.connect(
                    lambda: self.load_page("battery.ui")
                )

            if hasattr(self.window, "btnCamera"):
                self.window.btnCamera.clicked.connect(
                    lambda: self.load_page("camera.ui")
                )

            if hasattr(self.window, "btnGraphs"):
                self.window.btnGraphs.clicked.connect(
                    lambda: self.load_page("graph.ui")
                )

            if hasattr(self.window, "btnDiagnostics"):
                self.window.btnDiagnostics.clicked.connect(
                    lambda: self.load_page("diagnostics.ui")
                )

            if hasattr(self.window, "btnSettings"):
                self.window.btnSettings.clicked.connect(
                    lambda: self.load_page("settings.ui")
                )

    # ==========================================
        # ==========================================
        # ==========================================
        # SETTINGS CONTROLS
        # ==========================================

        # Change Password
        if hasattr(self.window, "btnChangePassword"):
            try:
                self.window.btnChangePassword.clicked.disconnect()
            except:
                pass

            self.window.btnChangePassword.clicked.connect(
                self.change_password_dialog
            )

        # Save Settings
        if hasattr(self.window, "btnSaveSettings"):
            try:
                self.window.btnSaveSettings.clicked.disconnect()
            except:
                pass

            self.window.btnSaveSettings.clicked.connect(
                self.save_settings_action
            )

        # Restore Defaults
        if hasattr(self.window, "btnRestoreDefaults"):
            try:
                self.window.btnRestoreDefaults.clicked.disconnect()
            except:
                pass

            self.window.btnRestoreDefaults.clicked.connect(
                self.restore_defaults_action
            )

    # THEME BUTTON — ALL PAGES
    # ==========================================

        if hasattr(self.window, "btnDarkTheme"):

            if isinstance(
                self.window.btnDarkTheme,
                QPushButton
            ):

                try:
                    self.window.btnDarkTheme.clicked.disconnect()
                except (RuntimeError, TypeError):
                    pass

                self.window.btnDarkTheme.clicked.connect(
                    self.toggle_theme
                )

        # ==========================================
        # BACK / HOME BUTTONS — ALL PAGES
        # ==========================================

        if hasattr(self.window, "btnMenu"):

            if isinstance(self.window.btnMenu, QPushButton):

                try:
                    self.window.btnMenu.clicked.disconnect()
                except:
                    pass

                self.window.btnMenu.clicked.connect(
                    lambda: self.load_page("main_menu.ui")
                )

        if hasattr(self.window, "btnMenu_2"):

            if isinstance(self.window.btnMenu_2, QPushButton):

                try:
                    self.window.btnMenu_2.clicked.disconnect()
                except:
                    pass

                self.window.btnMenu_2.clicked.connect(
                    lambda: self.load_page("main_menu.ui")
                )

        if hasattr(self.window, "btnHome"):

            # Don't reconnect Main Menu's Home button
            # to itself.
            if self.window.objectName() != "MainMenu":

                if isinstance(self.window.btnHome, QPushButton):

                    try:
                        self.window.btnHome.clicked.disconnect()
                    except:
                        pass

                    self.window.btnHome.clicked.connect(
                        lambda: self.load_page("main_menu.ui")
                    )
    # ==========================================================
    # M89 GPS READER
    # ==========================================================

    def start_gps(self):

        if self.gps_serial is not None:
            return

        try:
            self.gps_serial = serial.Serial(
                self.gps_port,
                self.gps_baud,
                timeout=0
            )

            print(
                "M89 GPS CONNECTED:",
                self.gps_port,
                self.gps_baud
            )

        except Exception as e:
            self.gps_serial = None
            print("M89 GPS CONNECTION ERROR:", e)

    def read_gps(self):

        if self.gps_serial is None:
            self.start_gps()

        if self.gps_serial is None:
            return

        try:

            while self.gps_serial.in_waiting:

                line = self.gps_serial.readline().decode(
                    "ascii",
                    errors="ignore"
                ).strip()

                if not line or not line.startswith("$"):
                    continue

                try:
                    msg = pynmea2.parse(line)
                except Exception:
                    continue

                if hasattr(msg, "latitude") and hasattr(msg, "longitude"):

                    if msg.latitude and msg.longitude:
                        self.gps_latitude = float(msg.latitude)
                        self.gps_longitude = float(msg.longitude)
                        self.gps_fix = True

                if hasattr(msg, "altitude"):

                    if msg.altitude not in (None, ""):
                        try:
                            self.gps_altitude = float(msg.altitude)
                        except Exception:
                            pass

                if hasattr(msg, "num_sats"):

                    if msg.num_sats not in (None, ""):
                        try:
                            self.gps_satellites = int(msg.num_sats)
                        except Exception:
                            pass

                if hasattr(msg, "spd_over_grnd"):

                    if msg.spd_over_grnd not in (None, ""):
                        try:
                            self.gps_speed = (
                                float(msg.spd_over_grnd) * 1.852
                            )
                        except Exception:
                            pass

        except Exception as e:
            print("GPS READ ERROR:", e)

    def load_motor(self):

        self.window.lblLeftRPMValue.setText(str(self.rpm))

        self.window.lblRightRPMValue.setText(str(self.rpm))

        self.window.lblDirectionValue.setText(
            self.motor.direction(self.rpm)
        )

        self.window.lblModeValue.setText("BALANCE")

        self.window.lblHallValue_2.setText("OK")

        self.window.lblCurrentValue.setText(
            f"{self.current:.1f} A"
        )

        self.window.lblVoltageValue.setText(
            f"{self.voltage:.1f} V"
        )

        self.window.lblPowerValue.setText(
            f"{self.voltage*self.current:.1f} W"
        )
        self.window.lblPowerValue.setFont(
            QFont("Arial", 20, QFont.Weight.Bold)
        )
        self.window.lblPowerValue.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        self.window.lblPowerValue.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        self.window.lblControllerTempValue.setText(
            f"{self.temperature} °C"
        )

        self.window.lblMotorStatus.setText(
            self.motor.status(self.rpm)
        )
    # ============================================
    # CAMERA PAGE
    # ============================================

    def load_camera(self):

        print("CAMERA PAGE")

        # Camera starts OFF when page opens
        self.camera_started = False
        self.camera_timer.stop()

        # Camera preview
        self.camera_label = self.window.cameraFeedLabel

        self.camera_label.clear()
        self.camera_label.setText("Camera Not Connected")

        # Reset button text
        self.window.btnStartCamera.setText("START CAMERA")
        self.window.btnRecordvideo.setText("RECORD")

        self.window.btnRecordvideo.setFont(
            QFont("Arial", 14, QFont.Weight.Bold)
        )

        # -----------------------------
        # START / STOP CAMERA
        # -----------------------------
        try:
            self.window.btnStartCamera.clicked.disconnect()
        except:
            pass

        self.window.btnStartCamera.clicked.connect(
            self.toggle_camera
        )

        # -----------------------------
        # CAPTURE IMAGE
        # -----------------------------
        try:
            self.window.btnCaptureImage.clicked.disconnect()
        except:
            pass

        self.window.btnCaptureImage.clicked.connect(
            self.capture_image
        )

        # -----------------------------
        # RECORD / STOP RECORDING
        # -----------------------------
        try:
            self.window.btnRecordvideo.clicked.disconnect()
        except:
            pass

        self.window.btnRecordvideo.clicked.connect(
            self.toggle_recording
        )

        print("Camera Controls Ready")

        # ==========================================
        # VIEW GALLERY BUTTON
        # ==========================================

        try:
            self.window.btnGallery.clicked.disconnect()
        except:
            pass

        self.window.btnGallery.clicked.connect(
            self.show_gallery
        )

        print("Gallery Button Connected")

        # ==========================================
        # VIEW GALLERY BUTTON
        # ==========================================

        self.gallery_button = QPushButton(
            "VIEW GALLERY",
            self.window
        )

        # Hide duplicate dynamically-created gallery button.
        # The proper btnGallery from camera.ui is already present.
        self.gallery_button.hide()

        self.gallery_button.setGeometry(
            70,
            595,
            854,
            55
        )

        self.gallery_button.setFont(
            QFont("Arial", 15, QFont.Weight.Bold)
        )

        self.gallery_button.setStyleSheet("""
            QPushButton {
                background-color: #2B2B2B;
                color: #FFFFFF;
                border: 3px solid #9C27B0;
                border-radius: 15px;
            }
            QPushButton:pressed {
                background-color: #3A3A3A;
            }
        """)

        self.gallery_button.clicked.connect(
            self.show_gallery
        )

        self.gallery_button.hide()

        print("Gallery Button Ready")

    def toggle_camera(self):

        # =================================
        # CAMERA OFF → START
        # =================================

        if not self.camera_started:

            if self.camera.start(0):

                self.camera_started = True

                print("Camera Started")

                self.camera_timer.start(33)

                self.window.btnStartCamera.setText(
                    "STOP CAMERA"
                )


                print("Camera Status: LIVE")

                self.update_camera_frame()

            else:

                print("Camera Not Connected")

                self.camera_label.clear()

                self.camera_label.setText(
                    "Camera Not Connected"
                )

        # =================================
        # CAMERA ON → STOP
        # =================================

        else:

            print("Stopping Camera")

            # Stop recording first
            if self.recording:

                print("Stopping Recording First")

                if self.video_writer is not None:

                    self.video_writer.release()

                    self.video_writer = None

                self.recording = False

                self.window.btnRecordvideo.setText(
                    "RECORD"
                )
                self.window.btnRecordvideo.setFont(
                    QFont("Arial", 13, QFont.Weight.Bold)
                )

            # Stop camera timer
            self.camera_timer.stop()

            # Release camera
            self.camera.stop()

            self.camera_started = False

            # Clear preview
            self.camera_label.clear()

            self.camera_label.setText(
                "Camera OFF"
            )

            # Reset button
            self.window.btnStartCamera.setText(
                "START CAMERA"
            )

            print("Camera Status: OFF")

    def update_camera_frame(self):

        if self.window is None:
            return

      

        if not self.camera_started:
            return

        if self.camera_label is None:
            return

        frame = self.camera.read()

        if frame is None:
            return

        # RECORD ORIGINAL FRAME
        if self.recording and self.video_writer is not None:
            self.video_writer.write(frame)

        # BGR → RGB
        frame = cv2.cvtColor(
            frame,
            cv2.COLOR_BGR2RGB
        )

        height, width, channels = frame.shape

        bytes_per_line = channels * width

        image = QImage(
            frame.data,
            width,
            height,
            bytes_per_line,
            QImage.Format.Format_RGB888
        )

        pixmap = QPixmap.fromImage(image)

        # ============================================
        # CAMERA DISPLAY — FULL WIDTH, NO LEFT/RIGHT CROP
        # ============================================

        label_width = self.camera_label.width()
        label_height = self.camera_label.height()

        if label_width > 0 and label_height > 0:

            # Scale using the FULL preview width.
            # 2304x1296 -> 924x520 approximately.
            # This preserves the original 16:9 ratio.
            pixmap = pixmap.scaled(
                label_width,
                int(label_width * pixmap.height() / pixmap.width()),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )

            # The scaled image is taller than the preview.
            # Crop ONLY top/bottom.
            if pixmap.height() > label_height:

                y = (pixmap.height() - label_height) // 2

                pixmap = pixmap.copy(
                    0,
                    y,
                    label_width,
                    label_height
                )

            self.camera_label.setAlignment(
                Qt.AlignmentFlag.AlignCenter
            )

        self.camera_label.setPixmap(pixmap)

    def capture_image(self):

        if not self.camera_started:

            print("Camera is OFF")
            return

        filename = "capture.jpg"

        if self.camera.capture(filename):

            print("Image Captured:", filename)

            # Find latest captured image
            photos = list(
                self.camera.photo_dir.glob("*.jpg")
            )

            if photos:

                latest_photo = max(
                    photos,
                    key=lambda p: p.stat().st_mtime
                )

                self.show_image_popup(
                    latest_photo
                )

        else:

            print("Image Capture Failed")

    def show_image_popup(self, image_path):

        dialog = QDialog(self.window)

        dialog.setWindowTitle(
            "Captured Image"
        )

        dialog.setFixedSize(
            750,
            600
        )

        layout = QVBoxLayout(
            dialog
        )

        image_label = QLabel()

        image_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        pixmap = QPixmap(
            str(image_path)
        )

        if not pixmap.isNull():

            pixmap = pixmap.scaled(
                700,
                500,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )

            image_label.setPixmap(
                pixmap
            )

        else:

            image_label.setText(
                "Unable to load image"
            )

        # ADD IMAGE LABEL
        layout.addWidget(
            image_label
        )

        # IMAGE NAME
        info = QLabel(
            f"Saved: {image_path.name}"
        )

        info.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        layout.addWidget(
            info
        )

        # ==========================================
        # PHOTO ACTION BUTTONS
        # ==========================================

        button_layout = QHBoxLayout()

        # DELETE PHOTO
        delete_button = QPushButton()

        delete_button.setIcon(
            self.window.style().standardIcon(
                QStyle.StandardPixmap.SP_TrashIcon
            )
        )

        delete_button.setIconSize(
            QSize(22, 22)
        )

        delete_button.setFixedSize(
            48,
            42
        )

        delete_button.setToolTip(
            "Delete photo"
        )

        delete_button.setStyleSheet("""
            QPushButton {
                background-color: #2B2B2B;
                border: 2px solid #FF5252;
                border-radius: 8px;
            }

            QPushButton:hover {
                background-color: #3A3A3A;
            }

            QPushButton:pressed {
                background-color: #FF5252;
            }
        """)

        def delete_photo():
            if not image_path.exists():
                dialog.reject()
                return

            reply = QMessageBox.question(
                dialog,
                "Delete Photo",
                f"Delete this photo?\\n\\n{image_path.name}",
                QMessageBox.StandardButton.Yes
                | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )

            if reply == QMessageBox.StandardButton.Yes:
                try:
                    image_path.unlink()

                    print(
                        "PHOTO DELETED:",
                        image_path
                    )

                    dialog.accept()

                except Exception as e:
                    QMessageBox.warning(
                        dialog,
                        "Delete Failed",
                        f"Could not delete photo.\\n\\n{e}"
                    )

        delete_button.clicked.connect(
            delete_photo
        )

        # CLOSE BUTTON
        close_button = QPushButton(
            "CLOSE"
        )

        close_button.clicked.connect(
            dialog.accept
        )

        button_layout.addStretch()

        button_layout.addWidget(
            delete_button
        )

        button_layout.addWidget(
            close_button
        )

        button_layout.addStretch()

        layout.addLayout(
            button_layout
        )

        dialog.exec()

    def show_gallery(self):

        dialog = QDialog(self.window)

        dialog.setWindowTitle(
            "Camera Gallery"
        )

        dialog.setFixedSize(
            750,
            600
        )

        layout = QVBoxLayout(
            dialog
        )

        title = QLabel(
            "CAPTURED MEDIA"
        )

        title.setFont(
            QFont("Arial", 18, QFont.Weight.Bold)
        )

        title.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        layout.addWidget(
            title
        )

                # ==========================================
                # PHOTOS
                # ==========================================

        photos = sorted(
            self.camera.photo_dir.glob("*.jpg"),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )

        photo_list = QListWidget()
        photo_list.setStyleSheet("""
            QListWidget {
                background-color: transparent;
                border: none;
            }

            QListWidget::item {
                color: #00FF66;
                padding: 6px;
                font-size: 13px;
            }

            QListWidget::item:selected {
                background-color: #333333;
                color: #00FF66;
            }
        """)

        photo_list.setMinimumHeight(
            250
        )

        if photos:

            for photo in photos:

                item = QListWidgetItem(
                    "📷 " + photo.name
                )

                item.setData(
                    Qt.ItemDataRole.UserRole,
                    str(photo)
                )

                photo_list.addItem(
                    item
                )

        else:

            photo_list.addItem(
                "No captured images"
            )

        layout.addWidget(
            QLabel("PHOTOS")
        )

        layout.addWidget(
            photo_list
        )

                # ==========================================
                # VIDEOS
                # ==========================================

        videos = sorted(
            self.camera.video_dir.glob("*.mp4"),
            key=lambda p: p.stat().st_mtime,
             reverse=True
            )

        video_list = QListWidget()
        video_list.setStyleSheet("""
            QListWidget {
                background-color: transparent;
                border: none;
            }

            QListWidget::item {
                color: #00FF66;
                padding: 6px;
                font-size: 13px;
            }

            QListWidget::item:selected {
                background-color: #333333;
                color: #00FF66;
            }
        """)

        video_list.setMinimumHeight(
            150
        )

        if videos:

            for video in videos:

                item = QListWidgetItem(
                    "🎥 " + video.name
                )

                item.setData(
                    Qt.ItemDataRole.UserRole,
                    str(video)
                )

                video_list.addItem(
                    item
                )

        else:

            video_list.addItem(
                "No recorded videos"
            )

        layout.addWidget(
            QLabel("VIDEOS")
        )

        layout.addWidget(
            video_list
        )

                # ==========================================
                # PHOTO DOUBLE CLICK
                # ==========================================

        photo_list.itemDoubleClicked.connect(
            lambda item:
            self.gallery_open_photo(
                item,
                dialog
            )
        )
        video_list.itemDoubleClicked.connect(
        self.gallery_open_video
        )

                # ==========================================
                # CLOSE
                # ==========================================

        close_button = QPushButton(
            "CLOSE"
        )

        close_button.clicked.connect(
            dialog.accept
        )

        layout.addWidget(
            close_button
        )

        dialog.exec()

    def gallery_open_photo(
        self,
        item,
        gallery_dialog
    ):

        path = item.data(
            Qt.ItemDataRole.UserRole
        )

        if not path:
            return

        image_path = Path(
            path
        )

        if image_path.exists():

            self.show_image_popup(
                image_path
            )

    def gallery_open_video(self, item):

        path = item.data(
            Qt.ItemDataRole.UserRole
        )

        if not path:
            return

        video_path = Path(path)

        if video_path.exists():

            QDesktopServices.openUrl(
                QUrl.fromLocalFile(
                    str(video_path)
                )
            )

    def toggle_recording(self):

                    # =================================
                    # START RECORDING
                    # =================================

        if not self.recording:

            if not self.camera_started:

                print("Camera is OFF")
                return

            width = int(
                self.camera.cap.get(
                    cv2.CAP_PROP_FRAME_WIDTH
                )
            )

            height = int(
                self.camera.cap.get(
                    cv2.CAP_PROP_FRAME_HEIGHT
                )
            )

            fps = 30

            fourcc = cv2.VideoWriter_fourcc(
                *"mp4v"
            )
            video_file = (
                self.camera.video_dir /
                f"video_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
            )

            self.video_writer = cv2.VideoWriter(
                str(video_file),
                fourcc,
                fps,
                (width, height)
            )
            if not self.video_writer.isOpened():

                print("Recording Failed")

                self.video_writer = None

                return

            self.recording = True

            self.window.btnRecordvideo.setText(
                "STOP RECORDING"
            )
            self.window.btnRecordvideo.setFont(
                QFont("Arial", 13, QFont.Weight.Bold)
            )

            print("Recording Started")

                    # =================================
                    # STOP RECORDING
                    # =================================

        else:

            print("Stopping Recording")

            if self.video_writer is not None:

                self.video_writer.release()

                self.video_writer = None

                self.recording = False

                self.window.btnRecordvideo.setText(
                    "RECORD"
            )
                self.window.btnRecordvideo.setFont(
                    QFont("Arial", 13, QFont.Weight.Bold)
                    )
                print(
                "Recording Saved"
            )
    def load_graph(self):

        self.graph_time += 1

        self.graph.add_data(
            self.graph_time,
            self.voltage,
            self.current,
            self.speed,
            self.rpm,
            self.pitch,
            self.roll,
            self.yaw
        )

        x, y = self.graph.get_speed()

        self.plot.clear()

        self.plot.showGrid(x=True, y=True)

        self.plot.plot(
            x,
            y,
            pen=pg.mkPen("#00FFFF", width=2)
        )
# ============================================
    # DIAGNOSTICS PAGE
    # ============================================


  
        
    def load_diagnostics(self):
        # ==========================================================
        # DIAGNOSTICS VALUES
        # ==========================================================

        self.window.lblRaspberryPiValue.setText(
            "CONNECTED"
        )

        self.window.lblSTM32Value.setText(
            "CONNECTED"
        )

        self.window.lblCameraValue.setText(
            "ACTIVE"
        )

        self.window.lblIMUValue.setText(
            "OK"
        )

        self.window.lblHallSensorsValue.setText(
            "OK"
        )

        self.window.lblMotorsValue.setText(
            "RUNNING"
        )

        self.window.lblWiFiValue.setText(
            "CONNECTED"
        )

        self.window.lblUARTValue.setText(
            "CONNECTED"
        )

        self.window.lblCANValue.setText(
            "OK"
        )

        # ==========================================================
        # VALUE LABELS
        # ==========================================================

        value_labels = [
            self.window.lblRaspberryPiValue,
            self.window.lblSTM32Value,
            self.window.lblCameraValue,
            self.window.lblIMUValue,
            self.window.lblHallSensorsValue,
            self.window.lblMotorsValue,
            self.window.lblWiFiValue,
            self.window.lblUARTValue,
            self.window.lblCANValue
        ]

        # ==========================================================
        # VALUE FONT
        # ==========================================================

        for label in value_labels:

            font = label.font()

            # Change this number if required
            font.setPointSize(18)

            label.setFont(font)

            label.setAlignment(
                Qt.AlignmentFlag.AlignCenter
            )

            label.setWordWrap(False)

    def update_dashboard(self):

        if self.window is None:
            return

        # Read telemetry safely
        try:
            telemetry = self.uart.read_telemetry()
        except Exception:
            telemetry = None

        if telemetry:

            self.voltage = telemetry.get("V", self.voltage)
            self.current = telemetry.get("I", self.current)
            self.rpm = telemetry.get("RPM", self.rpm)
            self.speed = telemetry.get("S", self.speed)
            self.pitch = telemetry.get("P", self.pitch)
            self.roll = telemetry.get("R", self.roll)
            self.yaw = telemetry.get("Y", self.yaw)
            self.temperature = telemetry.get(
                "T",
                self.temperature
            )

        # Current page
        page = self.window.objectName()

        # Home page
        if page == "Home":

            # ==========================================
            # LIVE ROTATING SEGWAY STATUS
            # One status at a time
            # ==========================================

            if hasattr(self.window, "segwayStatusValue"):

                # Create the rotating status index once.
                if not hasattr(self, "_status_index"):
                    self._status_index = 0

                # Change displayed status every 2 seconds.
                if not hasattr(self, "_status_last_change"):
                    self._status_last_change = 0

                import time
                now = time.monotonic()

                if now - self._status_last_change >= 2.0:
                    self._status_last_change = now
                    self._status_index += 1

                # Determine REAL current states.
                if telemetry:
                    stm32_status = "STM32 CONNECTED"
                else:
                    stm32_status = "STM32 DISCONNECTED"

                pi_status = "PI CONNECTED"

                if self.rpm > 0:
                    motor_status = "MOTOR ON"
                else:
                    motor_status = "MOTOR OFF"

                if self.camera_started:
                    camera_status = "CAMERA ON"
                else:
                    camera_status = "CAMERA OFF"

                if abs(self.speed) > 0.1:
                    motion_status = "SEGWAY MOVING"
                elif telemetry:
                    motion_status = "SEGWAY READY"
                else:
                    motion_status = "SEGWAY OFFLINE"

                # Statuses shown ONE AT A TIME.
                live_statuses = [
                    "SYSTEM " + getattr(self, "system_control_state", "STOPPED"),
                    pi_status,
                    stm32_status,
                    motor_status,
                    camera_status,
                    motion_status,
                ]

                current_status = live_statuses[
                    self._status_index % len(live_statuses)
                ]

                self.window.segwayStatusValue.setText(
                    current_status
                )

                # Status-specific colour.
                if "DISCONNECTED" in current_status:
                    status_color = "#FF5252"
                elif current_status in (
                    "MOTOR ON",
                    "PI CONNECTED",
                    "STM32 CONNECTED",
                    "CAMERA ON",
                    "SEGWAY READY",
                ):
                    status_color = "#00FF66"
                elif current_status == "SEGWAY MOVING":
                    status_color = "#00E5FF"
                else:
                    status_color = "#FFD700"

                self.window.segwayStatusValue.setStyleSheet(
                    "color: " + status_color + ";"
                    "background: transparent;"
                    "border: none;"
                    "font: bold 22pt Arial;"
                )

            self.window.speedValueLabel.setText(
                f"{self.speed:.1f} km/h"
            )

            self.window.voltageValueLabel.setText(
                f"{self.voltage:.1f} V"
            )

            self.window.currentValueLabel.setText(
                f"{self.current:.1f} A"
            )

            self.window.temperatureValueLabel.setText(
                f"{self.temperature:.1f} °C"
            )

            self.window.rightRPMValueLabel.setText(
                str(int(self.rpm))
            )

            self.window.pitchValueLabel.setText(
                f"{self.pitch:.1f}°"
            )

            self.window.rollValueLabel_2.setText(
                f"{self.roll:.1f}°"
            )

            self.window.yawValueLabel.setText(
                f"{self.yaw:.1f}°"
            )

            self.window.modeValueLabel.setText(
                "BALANCE"
            )

        # Other pages
        elif page == "Battery":
            self.load_battery()

        elif page == "Motor":
            self.load_motor()

        elif page == "Graph":
            self.load_graph()

        elif page == "Diagnostics":
            self.load_diagnostics()

    def update_clock(self):

        if self.window is None:
            return

        current = datetime.now()

        if hasattr(self.window, "timeLabel"):

            self.window.timeLabel.setText(
                current.strftime("%I:%M %p")
            )

        if hasattr(self.window, "dateLabel"):

            self.window.dateLabel.setText(
                current.strftime("%d %B %Y")
            )

    # ==========================================================
    # PASSWORD LOCK SCREEN
    # ==========================================================

    def change_password_dialog(self):
        import subprocess

        dialog = QDialog(self.window)
        dialog.setWindowTitle("🔐 CHANGE PASSWORD")
        dialog.setModal(True)
        dialog.setFixedSize(1024, 600)

        dialog.setStyleSheet("""
            QDialog {
                background-color: #151515;
            }

            QLabel {
                color: white;
                font: bold 16pt "Segoe UI";
            }

            QLineEdit {
                background-color: #252525;
                color: white;
                border: 3px solid #00E5FF;
                border-radius: 12px;
                padding: 8px;
                font: bold 18pt "Segoe UI";
            }

            QLineEdit:focus {
                border: 3px solid #00FF66;
            }

            QPushButton {
                background-color: #252525;
                color: white;
                border: 2px solid #00E5FF;
                border-radius: 12px;
                font: bold 16pt "Segoe UI";
            }

            QPushButton:hover {
                background-color: #00E5FF;
                color: black;
            }
        """)

        title = QLabel("🔐  CHANGE PASSWORD", dialog)
        title.setGeometry(250, 35, 524, 55)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(
            "color:#00E5FF; font:bold 24pt 'Segoe UI';"
        )

        message = QLabel("ENTER OLD PASSWORD", dialog)
        message.setGeometry(250, 95, 524, 40)
        message.setAlignment(Qt.AlignmentFlag.AlignCenter)

        old_password = QLineEdit(dialog)
        old_password.setGeometry(300, 145, 424, 55)
        old_password.setEchoMode(QLineEdit.EchoMode.Password)
        old_password.setPlaceholderText("OLD PASSWORD")
        old_password.setInputMethodHints(
            Qt.InputMethodHint.ImhDigitsOnly |
            Qt.InputMethodHint.ImhPreferNumbers
        )
        old_password.setMaxLength(12)

        new_password = QLineEdit(dialog)
        new_password.setGeometry(300, 225, 424, 55)
        new_password.setEchoMode(QLineEdit.EchoMode.Password)
        new_password.setPlaceholderText("NEW PASSWORD")
        new_password.setInputMethodHints(
            Qt.InputMethodHint.ImhDigitsOnly |
            Qt.InputMethodHint.ImhPreferNumbers
        )
        new_password.setMaxLength(12)

        confirm_password = QLineEdit(dialog)
        confirm_password.setGeometry(300, 305, 424, 55)
        confirm_password.setEchoMode(QLineEdit.EchoMode.Password)
        confirm_password.setPlaceholderText("CONFIRM NEW PASSWORD")
        confirm_password.setInputMethodHints(
            Qt.InputMethodHint.ImhDigitsOnly |
            Qt.InputMethodHint.ImhPreferNumbers
        )
        confirm_password.setMaxLength(12)

        # Force NUMBERS ONLY even if another keyboard sends characters.
        def numbers_only(text):
            sender = dialog.sender()
            if sender is not None:
                clean = "".join(ch for ch in text if ch.isdigit())
                if clean != text:
                    sender.setText(clean)

        old_password.textChanged.connect(numbers_only)
        new_password.textChanged.connect(numbers_only)
        confirm_password.textChanged.connect(numbers_only)

        save_button = QPushButton("SAVE PASSWORD", dialog)
        save_button.setGeometry(300, 395, 205, 60)

        cancel_button = QPushButton("CANCEL", dialog)
        cancel_button.setGeometry(519, 395, 205, 60)

        keyboard = [None]

        def open_keyboard():
            try:
                if keyboard[0] is None or keyboard[0].poll() is not None:
                    keyboard[0] = subprocess.Popen(
                        ["squeekboard"],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL
                    )
            except Exception as e:
                print("KEYBOARD OPEN ERROR:", e)

        def close_keyboard():
            try:
                subprocess.run(
                    ["pkill", "-x", "squeekboard"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
            except Exception:
                pass

            keyboard[0] = None

        # Open keyboard whenever a password field is touched.
        for field in (
            old_password,
            new_password,
            confirm_password
        ):
            original_focus = field.focusInEvent

            def make_focus_handler(widget, original):
                def handler(event):
                    original(event)
                    open_keyboard()
                return handler

            field.focusInEvent = make_focus_handler(
                field,
                original_focus
            )

        def save_password():
            old = old_password.text()
            new = new_password.text()
            confirm = confirm_password.text()

            if not self.password_manager.verify(old):
                message.setText("INCORRECT OLD PASSWORD")
                message.setStyleSheet(
                    "color:#FF5252; font:bold 16pt 'Segoe UI';"
                )
                old_password.clear()
                old_password.setFocus()
                open_keyboard()
                return

            if not new:
                message.setText("NEW PASSWORD CANNOT BE EMPTY")
                message.setStyleSheet(
                    "color:#FF5252; font:bold 16pt 'Segoe UI';"
                )
                new_password.setFocus()
                open_keyboard()
                return

            if not new.isdigit():
                message.setText("NUMBERS ONLY")
                message.setStyleSheet(
                    "color:#FF5252; font:bold 16pt 'Segoe UI';"
                )
                new_password.clear()
                new_password.setFocus()
                open_keyboard()
                return

            if new != confirm:
                message.setText("PASSWORDS DO NOT MATCH")
                message.setStyleSheet(
                    "color:#FF5252; font:bold 16pt 'Segoe UI';"
                )
                confirm_password.clear()
                confirm_password.setFocus()
                open_keyboard()
                return

            close_keyboard()
            self.password_manager.set_password(new)

            QMessageBox.information(
                dialog,
                "Password",
                "Password changed successfully."
            )

            print("PASSWORD CHANGED SUCCESSFULLY")
            dialog.accept()

        save_button.clicked.connect(save_password)

        def cancel():
            close_keyboard()
            dialog.reject()

        cancel_button.clicked.connect(cancel)

        # Clicking blank space closes the keyboard.
        def dialog_mouse_press(event):
            child = dialog.childAt(
                event.position().toPoint()
            )

            if not isinstance(child, QLineEdit):
                close_keyboard()

            QDialog.mousePressEvent(dialog, event)

        dialog.mousePressEvent = dialog_mouse_press

        old_password.setFocus()

        return dialog.exec() == QDialog.DialogCode.Accepted

    def show_password_dialog(self):

        dialog = QDialog(self.window)
        dialog.setWindowTitle("SEGWAY HMI - Password")
        dialog.setModal(True)
        dialog.setFixedSize(1024, 600)

        dialog.setStyleSheet("""
            QDialog {
                background-color: #1E1E1E;
            }
            QLabel {
                color: white;
            }
            QLineEdit {
                background-color: #252525;
                color: white;
                border: 2px solid #00E5FF;
                border-radius: 12px;
                padding: 8px;
                font: bold 26pt Arial;
            }
            QPushButton {
                background-color: #252525;
                color: white;
                border: 2px solid #555555;
                border-radius: 14px;
                font: bold 20pt Arial;
            }
            QPushButton:pressed {
                background-color: #00E5FF;
                color: black;
            }
        """)

        title = QLabel("🔐  SEGWAY HMI", dialog)
        title.setGeometry(300, 55, 424, 55)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(
            "color:#00E5FF; font:bold 26pt Arial;"
        )

        subtitle = QLabel("ENTER PASSWORD", dialog)
        subtitle.setGeometry(300, 115, 424, 40)
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet(
            "color:white; font:bold 16pt Arial;"
        )

        password = QLineEdit(dialog)
        password.setGeometry(362, 165, 300, 58)
        password.setEchoMode(QLineEdit.EchoMode.Password)
        password.setAlignment(Qt.AlignmentFlag.AlignCenter)
        password.setMaxLength(12)

        # ==========================================================
        # TOUCHSCREEN KEYBOARD
        # Squeekboard is already installed on this Raspberry Pi.
        # Focusing the password field requests the on-screen keyboard.
        # ==========================================================
        password.setInputMethodHints(
            Qt.InputMethodHint.ImhDigitsOnly
        )

        password.setFocusPolicy(
            Qt.FocusPolicy.StrongFocus
        )

        message = QLabel("", dialog)
        message.setGeometry(300, 225, 424, 35)
        message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        message.setStyleSheet(
            "color:#FF5252; font:bold 13pt Arial;"
        )

        keys = [
            ("1", 350, 275), ("2", 450, 275), ("3", 550, 275),
            ("4", 350, 345), ("5", 450, 345), ("6", 550, 345),
            ("7", 350, 415), ("8", 450, 415), ("9", 550, 415),
            ("⌫", 350, 485), ("0", 450, 485), ("✓", 550, 485),
        ]

        for text, x, y in keys:

            button = QPushButton(text, dialog)
            button.setGeometry(x, y, 80, 55)

            if text == "⌫":
                button.clicked.connect(
                    lambda: password.setText(
                        password.text()[:-1]
                    )
                )

            elif text == "✓":

                def verify_password():
                    entered = password.text()

                    if self.password_manager.verify(entered):
                        dialog.accept()
                    else:
                        password.clear()
                        message.setText("INCORRECT PASSWORD")

                button.clicked.connect(verify_password)

            else:
                button.clicked.connect(
                    lambda checked=False, value=text:
                    password.setText(
                        password.text() + value
                    )
                )

        password.returnPressed.connect(
            lambda: (
                dialog.accept()
                if self.password_manager.verify(password.text())
                else (
                    password.clear(),
                    message.setText("INCORRECT PASSWORD")
                )
            )
        )

        return dialog.exec() == QDialog.DialogCode.Accepted

    def run(self):

        print("RUN FUNCTION STARTING")

        # ==========================================================
        # HMI PASSWORD PROTECTION
        # ==========================================================

        # Create the initial window behind the password dialog.
        self.load_page("main_menu.ui")

        if not self.show_password_dialog():

            print("PASSWORD NOT VERIFIED - HMI LOCKED")

            self.app.quit()
            return

        print("PASSWORD VERIFIED - HMI UNLOCKED")
        print("MAIN MENU LOADED")
        print("WINDOW:", self.window)
        print("WINDOW SIZE:", self.window.size())
        print("WINDOW VISIBLE:", self.window.isVisible())

        self.app.setOverrideCursor(
            QCursor(Qt.CursorShape.ArrowCursor)
        )

        print("FORCING WINDOW TO STAY OPEN")

        result = self.app.exec()

        print("QT EVENT LOOP ENDED:", result)

        sys.exit(result)

if __name__ == "__main__":

    print("MAIN STARTING")

    app = SegwayHMI()

    print("APP CREATED")

    app.run()
