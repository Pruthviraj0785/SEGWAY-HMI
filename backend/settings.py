import json
import os


class Settings:

    def __init__(self, filename="config.json"):

        self.filename = filename

        self.default = {
            "serial_port": "COM3",
            "baudrate": 115200,
            "camera": 0,
            "theme": "Dark",
            "fullscreen": False,
            "language": "English"
        }

        if not os.path.exists(self.filename):
            self.save(self.default)

    # --------------------------------
    # Save Settings
    # --------------------------------
    def save(self, data):

        with open(self.filename, "w") as file:
            json.dump(data, file, indent=4)

    # --------------------------------
    # Load Settings
    # --------------------------------
    def load(self):

        try:

            with open(self.filename, "r") as file:
                return json.load(file)

        except:

            return self.default

    # --------------------------------
    # Get One Setting
    # --------------------------------
    def get(self, key):

        data = self.load()

        return data.get(key)

    # --------------------------------
    # Update One Setting
    # --------------------------------
    def set(self, key, value):

        data = self.load()

        data[key] = value

        self.save(data)

    # --------------------------------
    # Reset
    # --------------------------------
    def reset(self):

        self.save(self.default)