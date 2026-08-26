from datetime import datetime


class Diagnostics:

    def __init__(self):

        self.uart = False
        self.camera = False
        self.motor = False
        self.battery = False
        self.imu = False

    # ----------------------------------
    # UART
    # ----------------------------------
    def set_uart(self, status):
        self.uart = status

    # ----------------------------------
    # Camera
    # ----------------------------------
    def set_camera(self, status):
        self.camera = status

    # ----------------------------------
    # Motor
    # ----------------------------------
    def set_motor(self, status):
        self.motor = status

    # ----------------------------------
    # Battery
    # ----------------------------------
    def set_battery(self, status):
        self.battery = status

    # ----------------------------------
    # IMU
    # ----------------------------------
    def set_imu(self, status):
        self.imu = status

    # ----------------------------------
    # Overall Health
    # ----------------------------------
    def overall_status(self):

        if all([
            self.uart,
            self.camera,
            self.motor,
            self.battery,
            self.imu
        ]):
            return "SYSTEM OK"

        return "CHECK SYSTEM"

    # ----------------------------------
    # Fault List
    # ----------------------------------
    def faults(self):

        fault_list = []

        if not self.uart:
            fault_list.append("UART Disconnected")

        if not self.camera:
            fault_list.append("Camera Offline")

        if not self.motor:
            fault_list.append("Motor Fault")

        if not self.battery:
            fault_list.append("Battery Fault")

        if not self.imu:
            fault_list.append("IMU Not Detected")

        return fault_list

    # ----------------------------------
    # Report
    # ----------------------------------
    def report(self):

        return {
            "Time": datetime.now().strftime("%H:%M:%S"),
            "UART": self.uart,
            "Camera": self.camera,
            "Motor": self.motor,
            "Battery": self.battery,
            "IMU": self.imu,
            "Status": self.overall_status(),
            "Faults": self.faults()
        }