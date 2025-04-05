import serial
import time

arduino = serial.Serial(port='/dev/cu.usbserial-2110', baudrate=9600, timeout=1)
time.sleep(2)

while True:
    try:
        with open("hand_data.txt", "r") as f:
            data = f.read().strip()
        if data:
            arduino.write((data + "\n").encode())
            print("Sent:", data)
        time.sleep(0.05)  # Prevent spamming
    except Exception as e:
        print("Error:", e)

