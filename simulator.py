import random


class Simulator:

    def __init__(self):
        self.speed = 0.0
        self.battery = 100

        self.direction = 1

    def get_data(self):

        # Speed Simulation
        self.speed += 2 * self.direction

        if self.speed >= 25:
            self.direction = -1

        if self.speed <= 0:
            self.direction = 1

        # Battery Simulation
        self.battery -= 0.05

        if self.battery <= 20:
            self.battery = 100

        voltage = 46 + (self.battery / 100) * 2.2

        current = 1 + (self.speed / 25) * 8

        rpm = int(self.speed * 60)

        leftRPM = rpm + random.randint(-8, 8)
        rightRPM = rpm + random.randint(-8, 8)

        temperature = 30 + current * 0.8

        pitch = random.uniform(-2, 2)

        roll = random.uniform(-1.5, 1.5)

        yaw = random.uniform(178, 182)

        if self.speed == 0:
            mode = "IDLE"

        elif self.speed < 5:
            mode = "START"

        elif self.speed < 20:
            mode = "BALANCE"

        else:
            mode = "CRUISE"

        if self.battery > 70:
            status = "🟢 READY"

        elif self.battery > 40:
            status = "🟡 NORMAL"

        else:
            status = "🔴 LOW BATTERY"

        return {

            "speed": self.speed,

            "battery": self.battery,

            "voltage": voltage,

            "current": current,

            "leftRPM": leftRPM,

            "rightRPM": rightRPM,

            "temperature": temperature,

            "pitch": pitch,

            "roll": roll,

            "yaw": yaw,

            "mode": mode,

            "status": status

        }