import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import cv2
import mediapipe as mp
import numpy as np
import json
import os
import threading
import time
from datetime import datetime
from PIL import Image, ImageTk

# --- Shared Constants & Helper Functions (from other scripts, slightly adapted for GUI) ---
RECORDINGS_DIR = "hand_recordings"
os.makedirs(RECORDINGS_DIR, exist_ok=True)

mp_hands = mp.solutions.hands
mp_drawing = mp.solutions.drawing_utils # For live feed standard drawing
hands_detector = mp_hands.Hands(max_num_hands=1, min_detection_confidence=0.7, min_tracking_confidence=0.7)

# Hand Styling Parameters (same as others)
COLOR_WRIST = (0, 255, 255)
COLOR_THUMB_TIP = (0, 255, 0)
COLOR_FINGERTIPS = (255, 0, 0)
COLOR_JOINTS = (192, 192, 192)
COLOR_BONES = (220, 220, 220)
PALM_COLOR = (80, 80, 80)
WRIST_IDX, THUMB_TIP_IDX, FINGERTIP_INDICES, PALM_INDICES = 0, 4, [4, 8, 12, 16, 20], [0, 1, 5, 9, 13, 17]

def draw_enhanced_landmarks_gui(image, normalized_landmarks_frame, image_width, image_height):
    if not normalized_landmarks_frame:
        return image # Return original image if no landmarks

    # Create a mutable copy if image is read-only (e.g. from PIL)
    if not image.flags.writeable:
        image = image.copy()

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

    # Draw Palm
    palm_points_cv = []
    for idx in PALM_INDICES:
        if idx < len(pixel_landmarks):
             palm_points_cv.append([pixel_landmarks[idx][0], pixel_landmarks[idx][1]]) # Note: [x,y] for cv2.drawContours
    if len(palm_points_cv) > 2:
        cv2.drawContours(image, [np.array(palm_points_cv)], 0, PALM_COLOR, -1)
    
    # Draw Bones
    for connection in mp_hands.HAND_CONNECTIONS:
        start_idx, end_idx = connection
        if start_idx < len(pixel_landmarks) and end_idx < len(pixel_landmarks):
            p1 = pixel_landmarks[start_idx]
            p2 = pixel_landmarks[end_idx]
            avg_depth_scale = (p1[3] + p2[3]) / 2.0
            thickness = 1 + int(avg_depth_scale * 5)
            cv2.line(image, (p1[0], p1[1]), (p2[0], p2[1]), COLOR_BONES, thickness)

    # Draw Joints
    for idx, (x, y, z_val, depth_scale) in enumerate(pixel_landmarks):
        radius = 3 + int(depth_scale * 7)
        color = COLOR_JOINTS
        if idx == WRIST_IDX: color = COLOR_WRIST
        elif idx == THUMB_TIP_IDX: color = COLOR_THUMB_TIP
        elif idx in FINGERTIP_INDICES: color = COLOR_FINGERTIPS
        cv2.circle(image, (x, y), radius, color, -1)
        cv2.circle(image, (x, y), radius, (50,50,50), 1)
    return image


class HandMotionApp:
    def __init__(self, root_window):
        self.root = root_window
        self.root.title("Hand Motion Recorder & Player")
        self.root.geometry("1000x700") # Adjusted size

        self.is_recording = False
        self.recorded_frames_data = []
        self.current_action_name_var = tk.StringVar(value="my_action")
        self.video_capture = None
        self.camera_active = False
        self.replay_active = False
        self.replay_paused = False
        self.current_replay_frame_idx = 0
        self.loaded_replay_data = None
        
        self.last_frame_time = time.time()
        self.frame_count_for_fps = 0
        self.estimated_fps_recording = 30.0

        # --- Main Layout ---
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(expand=True, fill=tk.BOTH)

        # Left Panel: Controls
        controls_frame = ttk.LabelFrame(main_frame, text="Controls", padding="10")
        controls_frame.pack(side=tk.LEFT, fill=tk.Y, padx=10, pady=10)

        # Right Panel: Video Display
        self.video_panel = ttk.LabelFrame(main_frame, text="Live Feed / Replay", padding="10")
        self.video_panel.pack(side=tk.RIGHT, expand=True, fill=tk.BOTH, padx=10, pady=10)
        self.video_label = ttk.Label(self.video_panel)
        self.video_label.pack(expand=True, fill=tk.BOTH)
        # Placeholder for video label dimensions
        self.video_label_width = 640 
        self.video_label_height = 480


        # --- Controls Widgets ---
        # Action Name
        ttk.Label(controls_frame, text="Action Name:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.action_name_entry = ttk.Entry(controls_frame, textvariable=self.current_action_name_var, width=30)
        self.action_name_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")

        # Recording Buttons
        self.record_button = ttk.Button(controls_frame, text="Start Recording", command=self.toggle_recording)
        self.record_button.grid(row=1, column=0, columnspan=2, padx=5, pady=10, sticky="ew")

        # Recordings List
        ttk.Label(controls_frame, text="Saved Recordings:").grid(row=2, column=0, columnspan=2, padx=5, pady=5, sticky="w")
        self.recordings_listbox = tk.Listbox(controls_frame, height=10, exportselection=False)
        self.recordings_listbox.grid(row=3, column=0, columnspan=2, padx=5, pady=5, sticky="nsew")
        self.populate_recordings_list()

        # Playback Buttons
        self.play_button = ttk.Button(controls_frame, text="Play Selected", command=self.play_selected_recording)
        self.play_button.grid(row=4, column=0, padx=5, pady=5, sticky="ew")
        
        self.pause_resume_button = ttk.Button(controls_frame, text="Pause Replay", command=self.toggle_pause_replay, state=tk.DISABLED)
        self.pause_resume_button.grid(row=4, column=1, padx=5, pady=5, sticky="ew")

        self.stop_replay_button = ttk.Button(controls_frame, text="Stop Replay", command=self.stop_replay, state=tk.DISABLED)
        self.stop_replay_button.grid(row=5, column=0, columnspan=2, padx=5, pady=5, sticky="ew")
        
        self.delete_button = ttk.Button(controls_frame, text="Delete Selected", command=self.delete_selected_recording)
        self.delete_button.grid(row=6, column=0, columnspan=2, padx=5, pady=10, sticky="ew")


        # Status Bar
        self.status_var = tk.StringVar(value="Ready")
        status_bar = ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        # Configure grid weights for resizing
        controls_frame.columnconfigure(1, weight=1)
        controls_frame.rowconfigure(3, weight=1) # Listbox expands

        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.init_camera()


    def init_camera(self):
        if not self.camera_active:
            self.video_capture = cv2.VideoCapture(0) # Use camera 0
            if not self.video_capture.isOpened():
                messagebox.showerror("Camera Error", "Could not open webcam.")
                self.status_var.set("Error: Camera not found.")
                return
            self.camera_active = True
            self.status_var.set("Camera activated. Ready.")
            # Get actual frame dimensions from camera
            ret, frame = self.video_capture.read()
            if ret:
                self.video_label_height, self.video_label_width, _ = frame.shape
            self.update_video_feed() # Start the video loop

    def update_video_feed(self):
        if self.replay_active and not self.replay_paused:
            self.update_replay_frame()
            self.root.after(int(1000 / self.loaded_replay_data.get("fps", 30)), self.update_video_feed)
            return # Don't process camera if replaying

        if not self.camera_active or not self.video_capture or not self.video_capture.isOpened():
            # Display a black screen or placeholder if camera is off
            black_frame_ui = np.zeros((self.video_label_height, self.video_label_width, 3), dtype=np.uint8)
            self.display_cv2_image(black_frame_ui, "Camera off or replay active")
            return

        ret, frame = self.video_capture.read()
        if ret:
            frame = cv2.flip(frame, 1)
            
            # Create a black image for skeletal hand visualization
            # Use the actual frame dimensions for the black_image
            current_height, current_width, _ = frame.shape
            skeletal_image = np.zeros((current_height, current_width, 3), dtype=np.uint8)

            image_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = hands_detector.process(image_rgb)
            
            current_frame_landmarks_normalized = []

            if results.multi_hand_landmarks:
                hand_landmarks_proto = results.multi_hand_landmarks[0]
                
                # Draw standard landmarks on live feed (optional)
                # mp_drawing.draw_landmarks(frame, hand_landmarks_proto, mp_hands.HAND_CONNECTIONS)

                # Prepare normalized data for drawing and recording
                for lm in hand_landmarks_proto.landmark:
                    current_frame_landmarks_normalized.append({
                        "x": lm.x, "y": lm.y, "z": lm.z,
                        "visibility": lm.visibility if hasattr(lm, 'visibility') else 0.0
                    })
                
                # Draw enhanced landmarks on the skeletal_image
                skeletal_image = draw_enhanced_landmarks_gui(skeletal_image, current_frame_landmarks_normalized, current_width, current_height)

            if self.is_recording:
                if current_frame_landmarks_normalized:
                    self.recorded_frames_data.append(current_frame_landmarks_normalized)
                # Display REC indicator on skeletal_image
                cv2.putText(skeletal_image, "REC", (current_width - 70, 30), 
                            cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2, cv2.LINE_AA)

            self.display_cv2_image(skeletal_image, "Live Skeletal Hand") # Display the skeletal view
        
        self.root.after(15, self.update_video_feed) # Approx 66 FPS target for UI updates

    def display_cv2_image(self, cv2_image, title_text=""):
        # Resize cv2_image to fit video_label while maintaining aspect ratio
        img_h, img_w = cv2_image.shape[:2]
        label_w, label_h = self.video_panel.winfo_width() - 20, self.video_panel.winfo_height() - 40 # Approx padding
        
        if label_w <=0 or label_h <=0 : # Panel not yet sized
            label_w, label_h = self.video_label_width, self.video_label_height


        scale_w = label_w / img_w
        scale_h = label_h / img_h
        scale = min(scale_w, scale_h)

        if scale > 0 and scale != 1.0: # Avoid resizing if not needed or if scale is invalid
            new_w, new_h = int(img_w * scale), int(img_h * scale)
            resized_image = cv2.resize(cv2_image, (new_w, new_h), interpolation=cv2.INTER_AREA)
        else:
            resized_image = cv2_image

        # Convert to PIL Image
        img_rgb = cv2.cvtColor(resized_image, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(img_rgb)
        imgtk = ImageTk.PhotoImage(image=pil_img)
        
        self.video_label.imgtk = imgtk # Keep a reference!
        self.video_label.configure(image=imgtk)
        self.video_panel.config(text=title_text)


    def toggle_recording(self):
        if self.replay_active:
            messagebox.showwarning("Recording Blocked", "Please stop the current replay before recording.")
            return

        if not self.camera_active:
            self.init_camera() # Try to start camera if not active
            if not self.camera_active: return # if still not active, exit

        if self.is_recording: # Stop recording
            self.is_recording = False
            self.record_button.config(text="Start Recording")
            self.status_var.set("Recording stopped.")
            self.save_current_recording()
            self.action_name_entry.config(state=tk.NORMAL)
        else: # Start recording
            action_name = self.current_action_name_var.get().strip()
            if not action_name:
                messagebox.showerror("Input Error", "Please enter an action name.")
                return
            self.is_recording = True
            self.recorded_frames_data = []
            self.record_button.config(text="Stop Recording")
            self.status_var.set(f"Recording action: {action_name}...")
            self.action_name_entry.config(state=tk.DISABLED)
            
            # Reset FPS calculation for this recording session
            self.last_frame_time = time.time()
            self.frame_count_for_fps = 0


    def save_current_recording(self):
        if not self.recorded_frames_data:
            self.status_var.set("No frames recorded to save.")
            return

        action_name = self.current_action_name_var.get().strip()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = os.path.join(RECORDINGS_DIR, f"{action_name}_{timestamp}.json")
        
        # Calculate FPS based on actual recording time and frames
        # This is a rough estimate as GUI updates might affect precise timing
        # For more accuracy, timestamp each frame during recording.
        # Here, we'll use a simpler approach or a default.
        # Let's assume the update_video_feed rate is somewhat consistent.
        # A better way would be to count frames and time in the recording loop itself.

        recording_data = {
            "actionName": action_name,
            "fps": self.estimated_fps_recording, # Use a fixed or estimated FPS
            "frameCount": len(self.recorded_frames_data),
            "frames": self.recorded_frames_data
        }
        try:
            with open(filename, 'w') as f:
                json.dump(recording_data, f, indent=4)
            self.status_var.set(f"Recording saved: {os.path.basename(filename)}")
            self.populate_recordings_list()
        except IOError as e:
            messagebox.showerror("Save Error", f"Could not save recording: {e}")
            self.status_var.set("Error saving recording.")
        self.recorded_frames_data = []

    def populate_recordings_list(self):
        self.recordings_listbox.delete(0, tk.END)
        try:
            files = [f for f in os.listdir(RECORDINGS_DIR) if f.endswith(".json")]
            # Sort by modification time, newest first
            files.sort(key=lambda name: os.path.getmtime(os.path.join(RECORDINGS_DIR, name)), reverse=True)
            for f_name in files:
                self.recordings_listbox.insert(tk.END, f_name)
        except FileNotFoundError:
            self.status_var.set(f"Recordings directory '{RECORDINGS_DIR}' not found.")


    def play_selected_recording(self):
        selected_indices = self.recordings_listbox.curselection()
        if not selected_indices:
            messagebox.showinfo("Selection", "Please select a recording to play.")
            return
        
        if self.is_recording:
            messagebox.showwarning("Playback Blocked", "Please stop recording before playing an animation.")
            return

        filename = self.recordings_listbox.get(selected_indices[0])
        filepath = os.path.join(RECORDINGS_DIR, filename)

        try:
            with open(filepath, 'r') as f:
                self.loaded_replay_data = json.load(f)
        except Exception as e:
            messagebox.showerror("Load Error", f"Could not load or parse recording: {e}")
            self.loaded_replay_data = None
            return

        if not self.loaded_replay_data or "frames" not in self.loaded_replay_data or not self.loaded_replay_data["frames"]:
            messagebox.showerror("Playback Error", "Recording is empty or invalid.")
            return
        
        self.replay_active = True
        self.replay_paused = False
        self.current_replay_frame_idx = 0
        self.status_var.set(f"Playing: {self.loaded_replay_data.get('actionName', 'Unknown')}")
        
        self.record_button.config(state=tk.DISABLED)
        self.play_button.config(state=tk.DISABLED)
        self.delete_button.config(state=tk.DISABLED)
        self.pause_resume_button.config(text="Pause Replay", state=tk.NORMAL)
        self.stop_replay_button.config(state=tk.NORMAL)
        
        if self.camera_active and self.video_capture: # Release camera if active
            self.video_capture.release()
            self.camera_active = False
            
        # The update_video_feed loop will now handle replay frames
        # No need to call update_replay_frame directly here, loop will pick it up.


    def update_replay_frame(self):
        if not self.replay_active or not self.loaded_replay_data or self.replay_paused:
            return

        frames = self.loaded_replay_data["frames"]
        if self.current_replay_frame_idx < len(frames):
            normalized_landmarks = frames[self.current_replay_frame_idx]
            
            # Use a fixed size for replay canvas or adapt from loaded data if available
            replay_canvas_width = self.video_label_width 
            replay_canvas_height = self.video_label_height
            
            replay_image = np.zeros((replay_canvas_height, replay_canvas_width, 3), dtype=np.uint8)
            replay_image = draw_enhanced_landmarks_gui(replay_image, normalized_landmarks, replay_canvas_width, replay_canvas_height)
            
            action_name = self.loaded_replay_data.get('actionName', 'Replay')
            frame_text = f"Frame: {self.current_replay_frame_idx + 1}/{len(frames)}"
            cv2.putText(replay_image, frame_text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 1)
            
            self.display_cv2_image(replay_image, f"Replaying: {action_name}")
            self.current_replay_frame_idx += 1
        else:
            self.stop_replay() # Reached end of animation

    def toggle_pause_replay(self):
        if not self.replay_active: return
        self.replay_paused = not self.replay_paused
        if self.replay_paused:
            self.pause_resume_button.config(text="Resume Replay")
            self.status_var.set(f"Paused: {self.loaded_replay_data.get('actionName', 'Unknown')}")
        else:
            self.pause_resume_button.config(text="Pause Replay")
            self.status_var.set(f"Resumed: {self.loaded_replay_data.get('actionName', 'Unknown')}")
            # self.update_replay_frame() # Kickstart if paused

    def stop_replay(self):
        self.replay_active = False
        self.replay_paused = False
        self.loaded_replay_data = None
        self.current_replay_frame_idx = 0
        
        self.status_var.set("Replay stopped. Camera reactivated.")
        self.record_button.config(state=tk.NORMAL)
        self.play_button.config(state=tk.NORMAL)
        self.delete_button.config(state=tk.NORMAL)
        self.pause_resume_button.config(text="Pause Replay", state=tk.DISABLED)
        self.stop_replay_button.config(state=tk.DISABLED)
        
        self.init_camera() # Re-initialize camera for live feed


    def delete_selected_recording(self):
        selected_indices = self.recordings_listbox.curselection()
        if not selected_indices:
            messagebox.showinfo("Selection", "Please select a recording to delete.")
            return

        filename = self.recordings_listbox.get(selected_indices[0])
        filepath = os.path.join(RECORDINGS_DIR, filename)

        if messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete '{filename}'?"):
            try:
                os.remove(filepath)
                self.status_var.set(f"Deleted: {filename}")
                self.populate_recordings_list()
            except OSError as e:
                messagebox.showerror("Delete Error", f"Could not delete file: {e}")
                self.status_var.set(f"Error deleting {filename}.")

    def on_closing(self):
        if self.is_recording:
            if messagebox.askyesno("Recording in Progress", "You are currently recording. Do you want to save it before quitting?"):
                self.save_current_recording()
            else: # Discard
                self.is_recording = False # ensure it doesn't try to save again if save_current_recording was skipped

        if self.video_capture:
            self.video_capture.release()
        self.camera_active = False
        self.replay_active = False # Ensure loops stop
        self.root.destroy()


if __name__ == '__main__':
    root = tk.Tk()
    app = HandMotionApp(root)
    root.mainloop()

