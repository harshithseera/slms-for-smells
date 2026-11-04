import re


class SignupForm:
    def __init__(self, data):
        self.data = data
        self.errors = []

    def validate_email(self):
        value = self.data.get("email", "").strip()
        if not value:
            self.errors.append("email is required")
            return False
        if len(value) > 254:
            self.errors.append("email is too long")
            return False
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[a-z]+", value):
            self.errors.append("email is invalid")
            return False
        return True

    def validate_username(self):
        value = self.data.get("username", "").strip()
        if not value:
            self.errors.append("username is required")
            return False
        if len(value) > 32:
            self.errors.append("username is too long")
            return False
        if not re.fullmatch(r"[a-z0-9_]+", value):
            self.errors.append("username is invalid")
            return False
        return True
