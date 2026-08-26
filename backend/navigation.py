from PySide6.QtCore import QFile
from PySide6.QtUiTools import QUiLoader


class NavigationManager:

    def __init__(self):
        self.loader = QUiLoader()
        self.current_window = None

    def load_ui(self, filename):

        if self.current_window:
            self.current_window.close()

        ui_file = QFile(f"ui/{filename}")

        ui_file.open(QFile.ReadOnly)

        self.current_window = self.loader.load(ui_file)

        ui_file.close()

        self.current_window.show()

    def show_main_menu(self):

        self.load_ui("main_menu.ui")

        self.current_window.btnHome.clicked.connect(self.show_home)

    def show_home(self):

        self.load_ui("home.ui")