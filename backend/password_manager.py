import hashlib
import json
import os


class PasswordManager:

    def __init__(self, filename="password.json"):
        self.filename = filename

        if not os.path.exists(self.filename):
            self.set_password("1234")

    def _hash(self, password):
        return hashlib.sha256(
            password.encode("utf-8")
        ).hexdigest()

    def set_password(self, password):
        data = {
            "password_hash": self._hash(password)
        }

        with open(self.filename, "w") as file:
            json.dump(data, file, indent=4)

        try:
            os.chmod(self.filename, 0o600)
        except Exception:
            pass

    def verify(self, password):
        try:
            with open(self.filename, "r") as file:
                data = json.load(file)

            return data.get("password_hash") == self._hash(password)

        except Exception:
            return False
