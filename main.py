import subprocess
import time

# Start the hand tracker
hand_tracker = subprocess.Popen(["python", "hand_tracker.py"])

# Wait briefly to make sure file starts being written
time.sleep(1)

# Start the Arduino sender
arduino_sender = subprocess.Popen(["python", "arduino_sender.py"])

try:
    # Keep the main script running while both subprocesses are alive
    while True:
        if hand_tracker.poll() is not None or arduino_sender.poll() is not None:
            print("One of the subprocesses has exited.")
            break
        time.sleep(0.5)

except KeyboardInterrupt:
    print("\nStopping processes...")
    hand_tracker.terminate()
    arduino_sender.terminate()
    hand_tracker.wait()
    arduino_sender.wait()
    print("All processes stopped.")

