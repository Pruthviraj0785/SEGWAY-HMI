class Battery:

    def __init__(self):
        self.max_voltage = 54.6
        self.min_voltage = 39.0

    def percentage(self, voltage):
        percent = ((voltage - self.min_voltage) /
                   (self.max_voltage - self.min_voltage)) * 100

        percent = max(0, min(100, percent))

        return round(percent, 1)

    def health(self, percent):
        if percent > 80:
            return "Excellent"
        elif percent > 50:
            return "Good"
        elif percent > 20:
            return "Low"
        else:
            return "Critical"

    def status(self, percent):
        if percent > 20:
            return "Normal"
        return "Charge Battery"

    def color(self, percent):
        if percent > 70:
            return "Green"
        elif percent > 30:
            return "Yellow"
        return "Red"