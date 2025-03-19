import serial
import threading
import time

class ComPortHandler:
    def __init__(self, port='COM3', baudrate=9600, timeout=1, callback=None):
        """
        Initializes the COM port handler.
        
        :param port: COM port name (e.g., 'COM3')
        :param baudrate: Baud rate for serial communication
        :param timeout: Read timeout in seconds
        :param callback: Function to call when new data is received
        """
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.callback = callback
        self.ser = None
        self.running = False

    def open(self):
        """Open the serial port and start the reading thread."""
        try:
            self.ser = serial.Serial(self.port, self.baudrate, timeout=self.timeout)
            self.running = True
            threading.Thread(target=self.read_loop, daemon=True).start()
        except Exception as e:
            print("Error opening serial port:", e)

    def close(self):
        """Close the serial port."""
        self.running = False
        if self.ser and self.ser.is_open:
            self.ser.close()

    def send_fan_speed(self, speed):
        if self.ser and self.ser.is_open:
            try:
                command = f"CS{speed:.2f}\n"
                self.ser.write(command.encode('utf-8'))
                print(f"Sent fan speed: {command.strip()}")
            except Exception as e:
                print("Error sending fan speed:", e)
        else:
            print("Serial port is not open. Cannot send data.")

    def read_loop(self):
        """
        Continuously reads the serial port for data.
        If no valid data is received for over 2 seconds, calls the callback with "sensor missing".
        """
        last_received = time.time()
        while self.running:
            try:
                line = self.ser.readline().decode('utf-8').strip()
                if line:
                    last_received = time.time()
                    if self.callback:
                        self.callback(line)
                else:
                    # If no data for more than 2 seconds, signal sensor missing
                    if time.time() - last_received > 2:
                        if self.callback:
                            self.callback("sensor missing")
                    time.sleep(0.1)
            except Exception as e:
                print("Error reading serial:", e)
                time.sleep(0.5)
