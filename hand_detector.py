"""
Utility module providing the handDetector class for detecting and tracking
hands in real-time video using MediaPipe Hands.
"""

import cv2
import mediapipe as mp


class handDetector():
    """
    Detects and tracks hands in real-time video using MediaPipe Hands.

    Attributes:
        mode (bool): Static image mode if True, video mode if False.
        max_hands (int): Maximum number of hands to detect.
        detection_con (float): Minimum detection confidence threshold.
        presence_con (float): Minimum presence confidence threshold.
        track_con (float): Minimum tracking confidence threshold.
    """

    def __init__(self, mode=False, max_hands=2, detection_con=0.5, presence_con=0.5, track_con=0.5):
        """
        Initialises the handDetector with the given confidence thresholds.

        Parameters:
            mode (bool): Static image mode if True, video mode if False.
            max_hands (int): Maximum number of hands to detect.
            detection_con (float): Minimum detection confidence (0.0 - 1.0).
            presence_con (float): Minimum presence confidence (0.0 - 1.0).
            track_con (float): Minimum tracking confidence (0.0 - 1.0).
        """
        self.mode = mode
        self.max_hands = max_hands
        self.detection_con = detection_con
        self.presence_con = presence_con
        self.track_con = track_con

        self.mp_hands = mp.solutions.hands
        self.hands = self.mp_hands.Hands(
            static_image_mode=self.mode,
            max_num_hands=self.max_hands,
            min_detection_confidence=self.detection_con,
            min_tracking_confidence=self.track_con
        )
        self.mp_draw = mp.solutions.drawing_utils

    def find_hands(self, img, draw=True):
        """
        Processes an image to detect hands and optionally draws landmarks.

        Parameters:
            img (ndarray): BGR input image from OpenCV.
            draw (bool): If True, draws hand landmarks onto the image.

        Returns:
            img (ndarray): The input image, with landmarks drawn if draw=True.
        """
        imgRGB = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        self.results = self.hands.process(imgRGB)

        if self.results.multi_hand_landmarks:
            for handLms in self.results.multi_hand_landmarks:
                if draw:
                    self.mp_draw.draw_landmarks(img, handLms, self.mp_hands.HAND_CONNECTIONS)

        return img

    def find_position(self, img, draw=True):
        """
        Returns pixel coordinates of hand landmarks for each detected hand.

        Must be called after find_hands() on the same frame.

        Parameters:
            img (ndarray): BGR input image, used for coordinate scaling.
            draw (bool): If True, draws a circle at each landmark position.

        Returns:
            all_landmarks (list): List of (handedness, landmark_list) tuples.
                handedness (str): 'Left' or 'Right'.
                landmark_list (list): List of [id, x, y] for each of the 21 landmarks.
        """
        all_landmarks = []

        if self.results.multi_hand_landmarks and self.results.multi_handedness:
            for hand_num in range(len(self.results.multi_handedness)):
                hand = self.results.multi_hand_landmarks[hand_num]
                handedness = self.results.multi_handedness[hand_num].classification

                for classification in handedness:
                    landmark_list = []
                    height, width, _ = img.shape

                    for id, landmark in enumerate(hand.landmark):
                        cx, cy = int(landmark.x * width), int(landmark.y * height)
                        landmark_list.append([id, cx, cy])

                        if draw:
                            cv2.circle(img, (cx, cy), 5, (255, 255, 255), cv2.FILLED)

                    all_landmarks.append((classification.label, landmark_list))

        return all_landmarks

    def get_finger_states(self, lmlist, handedness='Right'):
        """
        Returns which fingers are extended as a 5-element list.

        Uses tip vs PIP joint position for fingers 1-4, and lateral tip vs IP
        position for the thumb (accounting for handedness).

        Parameters:
            lmlist (list): Landmark list of [id, x, y] from find_position().
            handedness (str): 'Left' or 'Right' hand classification.

        Returns:
            states (list): [thumb, index, middle, ring, pinky] — 1 if extended, 0 if folded.
        """
        tip_ids = [4, 8, 12, 16, 20]
        pip_ids = [3, 6, 10, 14, 18]
        states = []

        # Thumb: check lateral extension relative to IP joint
        if handedness == 'Right':
            states.append(1 if lmlist[tip_ids[0]][1] > lmlist[pip_ids[0]][1] else 0)
        else:
            states.append(1 if lmlist[tip_ids[0]][1] < lmlist[pip_ids[0]][1] else 0)

        # Fingers: tip y above pip y means extended
        for tip, pip in zip(tip_ids[1:], pip_ids[1:]):
            states.append(1 if lmlist[tip][2] < lmlist[pip][2] else 0)

        return states

    def get_roi(self, img, lmlist):
        """
        Crops the region of interest (hand area) from the image.

        Computes a bounding box around all landmarks with a 25px margin,
        clamped to the image boundaries.

        Parameters:
            img (ndarray): BGR input image.
            lmlist (list): Landmark list of [id, x, y] entries from find_position().

        Returns:
            roi (ndarray): Cropped hand region.
            bounds (tuple): Bounding box as (x1, y1, x2, y2) in pixel coordinates.
        """
        h, w, _ = img.shape
        x_coords = [lm[1] for lm in lmlist]
        y_coords = [lm[2] for lm in lmlist]
        x1 = max(0, min(x_coords) - 25)
        y1 = max(0, min(y_coords) - 25)
        x2 = min(w, max(x_coords) + 25)
        y2 = min(h, max(y_coords) + 25)
        roi = img[y1:y2, x1:x2]
        return roi, (x1, y1, x2, y2)
