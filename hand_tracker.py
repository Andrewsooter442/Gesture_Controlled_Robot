import cv2
import mediapipe as mp
import numpy as np
import json
import time
import os
from datetime import datetime

# --- Configuration ---
# Create a directory for recordings if it doesn't exist
RECORDINGS_DIR = "hand_recordings"
os.makedirs(RECORDINGS_DIR, exist_ok=True)

# --- MediaPipe Hands Initialization ---
mp_hands = mp.solutions.hands
mp_drawing = mp.solutions.drawing_utils
mp_drawing_styles = mp.solutions.drawing_styles # For more advanced styling if needed

hands = mp_hands.Hands(
    max_num_hands=1,  # Focus on one hand for simplicity
    min_detection_confidence=0.7,
    min_tracking_confidence=0.7)

# --- Global variables for recording ---
is_recording = False
recorded_frames = []
current_action_name = "default_action" # This will be set by GUI later

# --- Hand Styling Parameters ---
# Define colors (BGR format for OpenCV)
COLOR_WRIST = (0, 255, 255)  # Yellow
COLOR_THUMB_TIP = (0, 255, 0) # Green
COLOR_FINGERTIPS = (255, 0, 0) # Blue
COLOR_JOINTS = (192, 192, 192) # Light Gray
COLOR_BONES = (220, 220, 220) # Lighter Gray
PALM_COLOR = (80, 80, 80) # Darker gray for palm

# Define landmark indices for special coloring
WRIST_IDX = 0
THUMB_TIP_IDX = 4
INDEX_FINGER_TIP_IDX = 8
MIDDLE_FINGER_TIP_IDX = 12
RING_FINGER_TIP_IDX = 16
PINKY_TIP_IDX = 20
FINGERTIP_INDICES = [THUMB_TIP_IDX, INDEX_FINGER_TIP_IDX, MIDDLE_FINGER_TIP_IDX, RING_FINGER_TIP_IDX, PINKY_TIP_IDX]
PALM_INDICES = [0, 1, 5, 9, 13, 17] # A selection for palm polygon

# --- Helper function to draw enhanced hand landmarks ---
def draw_enhanced_landmarks(image, hand_landmarks_proto, image_width, image_height):
    """
    Draws enhanced hand landmarks on the image.
    Args:
        image: The image to draw on.
        hand_landmarks_proto: The hand_landmarks protobuf object from MediaPipe.
        image_width: Width of the image.
        image_height: Height of the image.
    """
    if not hand_landmarks_proto:
        return

    # Convert protobuf landmarks to a list of dicts with pixel coordinates
    landmarks = []
    min_z = float('inf')
    max_z = float('-inf')
    for lm in hand_landmarks_proto.landmark:
        x, y, z = lm.x, lm.y, lm.z
        landmarks.append({'x': x, 'y': y, 'z': z, 'visibility': lm.visibility}) # Store normalized
        min_z = min(min_z, z)
        max_z = max(max_z, z)

    # Normalize z for visual effects (closer = larger/brighter)
    # MediaPipe z: smaller is closer to camera.
    # We want a factor `depth_scale` from 0 (farthest) to 1 (closest)
    # Avoid division by zero if all z are same
    z_range = max_z - min_z if max_z > min_z else 1.0 

    pixel_landmarks = []
    for lm in landmarks:
        px = int(lm['x'] * image_width)
        py = int(lm['y'] * image_height)
        
        # Calculate depth scale: 1.0 for closest (min_z), 0.0 for farthest (max_z)
        # If z_range is 0, all points are at same depth, default scale to 0.5
        depth_scale = (max_z - lm['z']) / z_range if z_range != 0 else 0.5
        pixel_landmarks.append((px, py, lm['z'], depth_scale))


    # 1. Draw Palm (optional, simple polygon)
    # You can create a more sophisticated palm drawing if needed
    palm_points = []
    for idx in PALM_INDICES: # e.g., [0, 1, 5, 9, 13, 17] or [0,5,9,13,17,0]
        if idx < len(pixel_landmarks):
             palm_points.append((pixel_landmarks[idx][0], pixel_landmarks[idx][1]))
    if len(palm_points) > 2:
        cv2.drawContours(image, [np.array(palm_points)], 0, PALM_COLOR, -1)


    # 2. Draw Bones (Connections)
    for connection in mp_hands.HAND_CONNECTIONS:
        start_idx, end_idx = connection
        if start_idx < len(pixel_landmarks) and end_idx < len(pixel_landmarks):
            p1 = pixel_landmarks[start_idx]
            p2 = pixel_landmarks[end_idx]
            
            avg_depth_scale = (p1[3] + p2[3]) / 2.0
            thickness = 1 + int(avg_depth_scale * 5) # Thicker if closer, base 1px, max 6px
            
            # Bone color can also be depth-modulated if desired
            # current_bone_color = tuple(int(c * (0.5 + 0.5 * avg_depth_scale)) for c in COLOR_BONES)

            cv2.line(image, (p1[0], p1[1]), (p2[0], p2[1]), COLOR_BONES, thickness)

    # 3. Draw Joints (Landmarks)
    for idx, (x, y, z_val, depth_scale) in enumerate(pixel_landmarks):
        radius = 3 + int(depth_scale * 7) # Larger radius if closer, base 3px, max 10px
        
        color = COLOR_JOINTS
        if idx == WRIST_IDX:
            color = COLOR_WRIST
        elif idx == THUMB_TIP_IDX: # Thumb tip has its own color
             color = COLOR_THUMB_TIP
        elif idx in FINGERTIP_INDICES:
            color = COLOR_FINGERTIPS
        
        # Modulate brightness based on depth (optional)
        # current_joint_color = tuple(int(c * (0.6 + 0.4 * depth_scale)) for c in color)

        cv2.circle(image, (x, y), radius, color, -1)
        # Add a border to circles for better definition
        cv2.circle(image, (x, y), radius, (50,50,50), 1)


def main_tracker():
    global is_recording, recorded_frames, current_action_name

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Cannot open camera")
        return

    print("Press 'R' to start/stop recording.")
    print("Press 'Q' to quit.")

    start_time_recording = None
    frame_count_recording = 0

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            print("Can't receive frame (stream end?). Exiting ...")
            break

        frame = cv2.flip(frame, 1)
        image_height, image_width, _ = frame.shape
        
        # Create a black image for skeletal hand visualization
        black_image = np.zeros((image_height, image_width, 3), dtype=np.uint8)

        # Convert the BGR image to RGB.
        image_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # Process the image and find hands.
        results = hands.process(image_rgb)

        current_frame_landmarks_normalized = []

        if results.multi_hand_landmarks:
            # For simplicity, we'll use the first detected hand.
            hand_landmarks_proto = results.multi_hand_landmarks[0]
            
            # Draw landmarks on the original frame (standard drawing)
            mp_drawing.draw_landmarks(
                frame,
                hand_landmarks_proto,
                mp_hands.HAND_CONNECTIONS,
                mp_drawing_styles.get_default_hand_landmarks_style(),
                mp_drawing_styles.get_default_hand_connections_style())

            # Draw enhanced landmarks on the black image
            draw_enhanced_landmarks(black_image, hand_landmarks_proto, image_width, image_height)

            # Store normalized landmarks for recording
            for lm in hand_landmarks_proto.landmark:
                current_frame_landmarks_normalized.append({
                    "x": lm.x, "y": lm.y, "z": lm.z, 
                    "visibility": lm.visibility if hasattr(lm, 'visibility') else 0.0
                })
        
        # Recording logic
        if is_recording:
            if current_frame_landmarks_normalized: # Only record if hand is detected
                recorded_frames.append(current_frame_landmarks_normalized)
                frame_count_recording +=1
            # Display recording status
            cv2.putText(frame, "REC", (image_width - 70, 30), 
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2, cv2.LINE_AA)
            cv2.putText(black_image, "REC", (image_width - 70, 30), 
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2, cv2.LINE_AA)


        cv2.imshow("Webcam Feed", frame)
        cv2.imshow("Enhanced Skeletal Hand", black_image)

        key = cv2.waitKey(5) & 0xFF
        if key == ord('q'):
            if is_recording: # If quitting while recording, save current recording
                print("Recording stopped due to quit. Saving...")
                save_recording()
            break
        elif key == ord('r'):
            if not is_recording:
                is_recording = True
                recorded_frames = []
                frame_count_recording = 0
                start_time_recording = time.time()
                # For standalone tracker, prompt for action name or use default
                action_input = input("Enter action name for this recording (or press Enter for default): ").strip()
                if action_input:
                    current_action_name = action_input
                else:
                    current_action_name = "recorded_action"

                print(f"Started recording: {current_action_name}")
            else:
                is_recording = False
                end_time_recording = time.time()
                duration = end_time_recording - start_time_recording
                fps_estimate = frame_count_recording / duration if duration > 0 else 30.0 # Default to 30 if too short
                print(f"Stopped recording: {current_action_name}. Frames: {frame_count_recording}, Duration: {duration:.2f}s, Estimated FPS: {fps_estimate:.2f}")
                save_recording(fps_estimate)

    cap.release()
    cv2.destroyAllWindows()

def save_recording(fps=30.0):
    global recorded_frames, current_action_name
    if not recorded_frames:
        print("No frames recorded to save.")
        return

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = os.path.join(RECORDINGS_DIR, f"{current_action_name}_{timestamp}.json")
    
    recording_data = {
        "actionName": current_action_name,
        "fps": fps,
        "frameCount": len(recorded_frames),
        "frames": recorded_frames
    }

    try:
        with open(filename, 'w') as f:
            json.dump(recording_data, f, indent=4)
        print(f"Recording saved to {filename}")
    except IOError as e:
        print(f"Error saving recording: {e}")
    
    recorded_frames = [] # Clear for next recording


if __name__ == '__main__':
    main_tracker()

