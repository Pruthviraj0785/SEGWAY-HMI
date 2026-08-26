import math


class Motor:

    def __init__(self):
        # Change these values according to your Segway
        self.wheel_diameter = 0.26      # meters (260 mm)
        self.max_rpm = 3000

    # ---------------------------------
    # Wheel Circumference
    # ---------------------------------
    def circumference(self):
        return math.pi * self.wheel_diameter

    # ---------------------------------
    # RPM → Speed (km/h)
    # ---------------------------------
    def rpm_to_speed(self, rpm):

        speed = rpm * self.circumference() * 60 / 1000

        return round(speed, 2)

    # ---------------------------------
    # Speed → RPM
    # ---------------------------------
    def speed_to_rpm(self, speed):

        rpm = speed * 1000 / (60 * self.circumference())

        return round(rpm)

    # ---------------------------------
    # Distance Travelled
    # ---------------------------------
    def distance(self, rpm, seconds):

        revolutions = rpm * seconds / 60

        distance = revolutions * self.circumference()

        return round(distance, 2)

    # ---------------------------------
    # Direction
    # ---------------------------------
    def direction(self, rpm):

        if rpm > 0:
            return "Forward"

        elif rpm < 0:
            return "Reverse"

        return "Stopped"

    # ---------------------------------
    # Motor Status
    # ---------------------------------
    def status(self, rpm):

        if rpm == 0:
            return "Stopped"

        elif abs(rpm) < 500:
            return "Low Speed"

        elif abs(rpm) < 1500:
            return "Normal"

        else:
            return "High Speed"

    # ---------------------------------
    # RPM Percentage
    # ---------------------------------
    def rpm_percentage(self, rpm):

        rpm = abs(rpm)

        if rpm > self.max_rpm:
            rpm = self.max_rpm

        return round((rpm / self.max_rpm) * 100)