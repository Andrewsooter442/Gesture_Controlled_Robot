import cv2
import mediapipe as mp
import numpy as np

# Initialize MediaPipe Hands module
mp_hands = mp.solutions.hands
mp_drawing = mp.solutions.drawing_utils
hands = mp_hands.Hands(min_detection_confidence=0.5, min_tracking_confidence=0.5)

# Open webcam
cap = cv2.VideoCapture(0)

while cap.isOpened():
    ret, frame = cap.read()
    if not ret:
        break

    # Flip the frame horizontally for natural view
    frame = cv2.flip(frame, 1)
    
    # Convert frame to RGB for MediaPipe
    image_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    results = hands.process(image_rgb)

    # Create a black image for skeletal hand
    h, w, _ = frame.shape
    black_image = np.zeros((h, w, 3), dtype=np.uint8)

    hand_positions = []  # Store hand landmarks

    if results.multi_hand_landmarks:
        for hand_landmarks in results.multi_hand_landmarks:
            # Draw landmarks on the original frame
            mp_drawing.draw_landmarks(frame, hand_landmarks, mp_hands.HAND_CONNECTIONS)

            # Convert normalized landmark points to pixel coordinates
            points = []
            for lm in hand_landmarks.landmark:
                x, y, z = int(lm.x * w), int(lm.y * h), lm.z  # Include depth (z)
                points.append((x, y, z))
            hand_positions.append(points)  # Store hand positions

            # Define hand connections for skeletal representation
            connections = [(0, 1), (1, 2), (2, 3), (3, 4),  # Thumb
                           (0, 5), (5, 6), (6, 7), (7, 8),  # Index Finger
                           (0, 9), (9, 10), (10, 11), (11, 12),  # Middle Finger
                           (0, 13), (13, 14), (14, 15), (15, 16),  # Ring Finger
                           (0, 17), (17, 18), (18, 19), (19, 20)]  # Pinky

            # Draw skeletal hand on the black image
            for p1, p2 in connections:
                cv2.line(black_image, (points[p1][0], points[p1][1]), (points[p2][0], points[p2][1]), (255, 255, 255), 2)

            for x, y, _ in points:
                cv2.circle(black_image, (x, y), 5, (255, 255, 255), -1)

    # Show both windows
    cv2.imshow("Webcam Feed", frame)
    cv2.imshow("Skeletal Hand", black_image)
    
    # Print hand positions (array of landmarks)
    if hand_positions:
        print(hand_positions)
        hand = hand_positions[0]
        flat_data = ",".join([f"{x},{y},{z:.4f}" for (x, y, z) in hand])
        with open("hand_data.txt", "w") as f:
            f.write(flat_data)


    # Press 'q' to exit
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

# Cleanup
cap.release()
cv2.destroyAllWindows()
