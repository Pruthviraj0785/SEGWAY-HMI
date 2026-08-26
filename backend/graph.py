from collections import deque


class Graph:

    def __init__(self, max_points=100):

        self.max_points = max_points

        self.time = deque(maxlen=max_points)

        self.voltage = deque(maxlen=max_points)
        self.current = deque(maxlen=max_points)
        self.speed = deque(maxlen=max_points)
        self.rpm = deque(maxlen=max_points)
        self.pitch = deque(maxlen=max_points)
        self.roll = deque(maxlen=max_points)
        self.yaw = deque(maxlen=max_points)

    # -----------------------------------
    # Add New Data
    # -----------------------------------
    def add_data(
        self,
        t,
        voltage,
        current,
        speed,
        rpm,
        pitch,
        roll,
        yaw
    ):

        self.time.append(t)

        self.voltage.append(voltage)
        self.current.append(current)
        self.speed.append(speed)
        self.rpm.append(rpm)
        self.pitch.append(pitch)
        self.roll.append(roll)
        self.yaw.append(yaw)

    # -----------------------------------
    # Get Data
    # -----------------------------------
    def get_voltage(self):
        return list(self.time), list(self.voltage)

    def get_current(self):
        return list(self.time), list(self.current)

    def get_speed(self):
        return list(self.time), list(self.speed)

    def get_rpm(self):
        return list(self.time), list(self.rpm)

    def get_pitch(self):
        return list(self.time), list(self.pitch)

    def get_roll(self):
        return list(self.time), list(self.roll)

    def get_yaw(self):
        return list(self.time), list(self.yaw)

    # -----------------------------------
    # Clear Graph
    # -----------------------------------
    def clear(self):

        self.time.clear()

        self.voltage.clear()
        self.current.clear()
        self.speed.clear()
        self.rpm.clear()
        self.pitch.clear()
        self.roll.clear()
        self.yaw.clear()

    # -----------------------------------
    # Number of Samples
    # -----------------------------------
    def samples(self):
        return len(self.time)