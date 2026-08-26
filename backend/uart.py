import serial
import serial.tools.list_ports


class UART:

    def __init__(self):
        self.ser = None

    def available_ports(self):
        return [
            port.device
            for port in serial.tools.list_ports.comports()
        ]

    def connect(self, port="COM3", baudrate=115200):

        try:
            self.ser = serial.Serial(
                port,
                baudrate,
                timeout=1
            )
            return True

        except Exception as e:
            print(e)
            return False

    def disconnect(self):

        if self.ser and self.ser.is_open:
            self.ser.close()

    def is_connected(self):

        return self.ser is not None and self.ser.is_open

    def send(self, text):

        if self.is_connected():
            self.ser.write((text + "\n").encode())

    def receive(self):

        if self.is_connected():

            try:
                return self.ser.readline().decode().strip()

            except:

                return ""

        return ""
    
    def parse_data(self, data):

        values = {}

        try:
            parts = data.split(",")

            for part in parts:
                key, value = part.split("=")

                values[key.strip()] = float(value.strip())

            return values

        except Exception as e:
            print("UART parse error:", e)
            return {}
    def read_telemetry(self):

        data = self.receive()

        if not data:
            return {}

        return self.parse_data(data)
    
if __name__ == "__main__":

    uart = UART()

    test_data = "V=48.2,I=5.1,RPM=880,S=13.7,P=2.4,R=-1.1,Y=180,T=33"

    data = uart.parse_data(test_data)

    print(data)