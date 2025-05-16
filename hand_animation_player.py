import cv2
import numpy as np
import json
import time
import os



mp_hands = mp.solutions.hands 


RECORDINGS_DIR = "hand_recordings" 


COLOR_WRIST = (0, 255, 255)  
COLOR_THUMB_TIP = (0, 255, 0) 
COLOR_FINGERTIPS = (255, 0, 0) 
COLOR_JOINTS = (192, 192, 192) 
COLOR_BONES = (220, 220, 220) 
PALM_COLOR = (80, 80, 80) 

WRIST_IDX = 0
THUMB_TIP_IDX = 4
INDEX_FINGER_TIP_IDX = 8
MIDDLE_FINGER_TIP_IDX = 12
RING_FINGER_TIP_IDX = 16
PINKY_TIP_IDX = 20
FINGERTIP_INDICES = [THUMB_TIP_IDX, INDEX_FINGER_TIP_IDX, MIDDLE_FINGER_TIP_IDX, RING_FINGER_TIP_IDX, PINKY_TIP_IDX]
PALM_INDICES = [0, 1, 5, 9, 13, 17]



def draw_enhanced_landmarks_replay(image, normalized_landmarks_frame, image_width, image_height):
    """
    Draws enhanced hand landmarks on the image from normalized data.
    Args:
        image: The image to draw on.
        normalized_landmarks_frame: A list of landmark dicts {'x', 'y', 'z', 'visibility'} for a single frame.
        image_width: Width of the image.
        image_height: Height of the image.
    """
    if not normalized_landmarks_frame:
        return

    min_z = float('inf')
    max_z = float('-inf')
    for lm in normalized_landmarks_frame:
        min_z = min(min_z, lm['z'])
        max_z = max(max_z, lm['z'])
    
    z_range = max_z - min_z if max_z > min_z else 1.0

    pixel_landmarks = []
    for lm in normalized_landmarks_frame:
        px = int(lm['x'] * image_width)
        py = int(lm['y'] * image_height)
        depth_scale = (max_z - lm['z']) / z_range if z_range != 0 else 0.5
        pixel_landmarks.append((px, py, lm['z'], depth_scale))

    
    palm_points = []
    for idx in PALM_INDICES:
        if idx < len(pixel_landmarks):
             palm_points.append((pixel_landmarks[idx][0], pixel_landmarks[idx][1]))
    if len(palm_points) > 2:
        cv2.drawContours(image, [np.array(palm_points)], 0, PALM_COLOR, -1)

    
    for connection in mp_hands.HAND_CONNECTIONS:
        start_idx, end_idx = connection
        if start_idx < len(pixel_landmarks) and end_idx < len(pixel_landmarks):
            p1 = pixel_landmarks[start_idx]
            p2 = pixel_landmarks[end_idx]
            avg_depth_scale = (p1[3] + p2[3]) / 2.0
            thickness = 1 + int(avg_depth_scale * 5)
            cv2.line(image, (p1[0], p1[1]), (p2[0], p2[1]), COLOR_BONES, thickness)

    
    for idx, (x, y, z_val, depth_scale) in enumerate(pixel_landmarks):
        radius = 3 + int(depth_scale * 7)
        color = COLOR_JOINTS
        if idx == WRIST_IDX: color = COLOR_WRIST
        elif idx == THUMB_TIP_IDX: color = COLOR_THUMB_TIP
        elif idx in FINGERTIP_INDICES: color = COLOR_FINGERTIPS
        cv2.circle(image, (x, y), radius, color, -1)
        cv2.circle(image, (x, y), radius, (50,50,50), 1)


def replay_animation(filepath, window_width=640, window_height=480):
    """
    Loads and replays a recorded hand animation.
    Args:
        filepath: Path to the JSON recording file.
        window_width: Width of the replay window.
        window_height: Height of the replay window.
    """
    try:
        with open(filepath, 'r') as f:
            recording_data = json.load(f)
    except FileNotFoundError:
        print(f"Error: Recording file not found at {filepath}")
        return
    except json.JSONDecodeError:
        print(f"Error: Could not decode JSON from {filepath}")
        return

    frames_data = recording_data.get("frames", [])
    fps = recording_data.get("fps", 30.0)
    action_name = recording_data.get("actionName", "Unknown Action")

    if not frames_data:
        print("No frames found in the recording.")
        return

    delay_between_frames = int(1000 / fps)  

    print(f"Replaying action: {action_name} at {fps:.2f} FPS. Press 'Q' to quit.")

    for frame_idx, landmarks_normalized in enumerate(frames_data):
        
        replay_image = np.zeros((window_height, window_width, 3), dtype=np.uint8)
        
        draw_enhanced_landmarks_replay(replay_image, landmarks_normalized, window_width, window_height)
        
        
        cv2.putText(replay_image, f"Frame: {frame_idx + 1}/{len(frames_data)}", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 1, cv2.LINE_AA)
        cv2.putText(replay_image, f"Action: {action_name}", (10, 60),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 1, cv2.LINE_AA)


        cv2.imshow("Hand Animation Replay", replay_image)

        if cv2.waitKey(delay_between_frames) & 0xFF == ord('q'):
            break
    
    cv2.destroyAllWindows()


if __name__ == '__main__':
    
    if not os.path.exists(RECORDINGS_DIR) or not os.listdir(RECORDINGS_DIR):
        print(f"No recordings found in '{RECORDINGS_DIR}'. Please run the tracker first to create recordings.")
    else:
        print("Available recordings:")
        recording_files = [f for f in os.listdir(RECORDINGS_DIR) if f.endswith(".json")]
        for i, filename in enumerate(recording_files):
            print(f"{i + 1}. {filename}")
        
        if not recording_files:
            print(f"No .json recordings found in '{RECORDINGS_DIR}'.")
        else:
            while True:
                try:
                    choice = int(input(f"Enter the number of the recording to play (1-{len(recording_files)}): "))
                    if 1 <= choice <= len(recording_files):
                        selected_file = os.path.join(RECORDINGS_DIR, recording_files[choice - 1])
                        replay_animation(selected_file)
                        break
                    else:
                        print("Invalid choice. Please enter a number from the list.")
                except ValueError:
                    print("Invalid input. Please enter a number.")

