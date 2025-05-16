import cv2
import numpy as np

class InteractiveSphere:
    def __init__(self, initial_pos_normalized, radius_pixels,
                 color_default, color_collided, interaction_landmark_idx):
        self.pos_normalized = list(initial_pos_normalized)  
        self.radius_pixels = radius_pixels
        self.color_default = color_default
        self.color_collided = color_collided
        self.interaction_landmark_idx = interaction_landmark_idx
        self.is_currently_collided = False

    def update_state(self, hand_landmarks_normalized, image_width, image_height):
        """
        Updates the sphere's position and collision state based on hand landmarks.
        Returns True if interaction occurred, False otherwise.
        """
        self.is_currently_collided = False  
        interaction_occurred = False

        if hand_landmarks_normalized and len(hand_landmarks_normalized) > self.interaction_landmark_idx:
            landmark_for_interaction = hand_landmarks_normalized[self.interaction_landmark_idx]
            
            
            sphere_pixel_x = int(self.pos_normalized[0] * image_width)
            sphere_pixel_y = int(self.pos_normalized[1] * image_height)

            
            lm_pixel_x = int(landmark_for_interaction['x'] * image_width)
            lm_pixel_y = int(landmark_for_interaction['y'] * image_height)

            
            dist_sq = (sphere_pixel_x - lm_pixel_x)**2 + (sphere_pixel_y - lm_pixel_y)**2
            
            
            collision_threshold_sq = (self.radius_pixels * 1.2)**2 

            if dist_sq < collision_threshold_sq:
                self.is_currently_collided = True
                interaction_occurred = True
                
                self.pos_normalized[0] = landmark_for_interaction['x']
                self.pos_normalized[1] = landmark_for_interaction['y']
        
        return interaction_occurred

    def draw(self, image):
        """
        Draws the sphere on the provided image.
        Assumes image_width and image_height are attributes of the image (image.shape).
        """
        image_height, image_width = image.shape[:2] 
        
        sphere_pixel_x = int(self.pos_normalized[0] * image_width)
        sphere_pixel_y = int(self.pos_normalized[1] * image_height)
        
        current_color = self.color_collided if self.is_currently_collided else self.color_default
        
        cv2.circle(image, (sphere_pixel_x, sphere_pixel_y), self.radius_pixels, current_color, -1)
        
        cv2.circle(image, (sphere_pixel_x, sphere_pixel_y), self.radius_pixels, (30,30,30), 2)
