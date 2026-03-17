"""
Real-time sign language phrase builder using the MediaPipe Gesture Recognizer.

Pipeline:
    Camera -> Gesture Recognizer (hand detection + ROI + CV model)
           -> Sign determination -> Phrase accumulation -> Speech + Arduino serial

Signs are confirmed after appearing consistently for sign_confirm_frames frames
and appended to a phrase. After 3 seconds of no hands detected, the full
phrase is spoken aloud and sent to the Arduino.

Controls:
    Q - Quit
    C - Clear the current phrase
"""

import cv2
import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision
import serial
import time
import warnings

warnings.filterwarnings('ignore')

ARDUINO_PORT = '/dev/ttyACM0'
BAUD_RATE = 9600
MODEL_PATH = 'gesture_recognizer.task'

# Maps MediaPipe gesture names to readable words
SIGN_LABELS = {
    'Closed_Fist': 'stop',
    'Open_Palm': 'hello',
    'Pointing_Up': 'one',
    'Thumb_Down': 'no',
    'Thumb_Up': 'yes',
    'Victory': 'peace',
    'ILoveYou': 'i love you',
}

# Maps (thumb, index, middle, ring, pinky) finger states to signs
# Used as fallback when the gesture recognizer returns nothing
LANDMARK_SIGNS = {
    # Numbers (continuing from built-in one/peace/four/hello)
    (0, 1, 1, 1, 0): 'three',
    (0, 1, 1, 1, 1): 'four',
    (1, 1, 1, 1, 1): 'four',   # thumb ambiguity fallback
    (1, 0, 0, 0, 1): 'six',
    (1, 0, 0, 1, 0): 'seven',
    (1, 0, 1, 0, 0): 'eight',
    (1, 1, 0, 0, 0): 'nine',
    (0, 0, 1, 1, 1): 'ten',
    # Common words
    (0, 1, 0, 0, 1): 'call me',
    (0, 0, 0, 0, 1): 'pinky',
    (1, 1, 1, 0, 0): 'good',
    (0, 0, 0, 1, 1): 'please',
    (0, 1, 0, 1, 0): 'help',
    (0, 0, 1, 1, 0): 'more',
    (1, 1, 1, 1, 0): 'thank you',
}


TIP_IDS = [4, 8, 12, 16, 20]
PIP_IDS = [3, 6, 10, 14, 18]


def get_finger_states(lms, handedness='Right'):
    """
    Returns which fingers are extended from gesture recognizer landmarks.

    Parameters:
        lms (list): NormalizedLandmark list from GestureRecognizer result.
        handedness (str): 'Left' or 'Right'.

    Returns:
        tuple: (thumb, index, middle, ring, pinky) — 1 if extended, 0 if folded.
    """
    states = []
    if handedness == 'Right':
        states.append(1 if lms[TIP_IDS[0]].x > lms[PIP_IDS[0]].x else 0)
    else:
        states.append(1 if lms[TIP_IDS[0]].x < lms[PIP_IDS[0]].x else 0)
    for tip, pip in zip(TIP_IDS[1:], PIP_IDS[1:]):
        states.append(1 if lms[tip].y < lms[pip].y else 0)
    return tuple(states)


def connect_arduino():
    """
    Attempts to open a serial connection to the Arduino.

    Returns:
        serial.Serial: Open serial connection, or None if unavailable.
    """
    try:
        arduino = serial.Serial(ARDUINO_PORT, BAUD_RATE, timeout=1)
        time.sleep(2)
        print(f'Arduino connected on {ARDUINO_PORT}')
        return arduino
    except serial.SerialException:
        print(f'Arduino not found on {ARDUINO_PORT}, running without it')
        return None


def send_to_arduino(arduino, text):
    """
    Sends a newline-terminated string to the Arduino over serial.

    Parameters:
        arduino (serial.Serial): Open serial connection, or None.
        text (str): The text to transmit.
    """
    if arduino:
        arduino.write(f'{text}\n'.encode())


def main():
    """
    Runs the word-level sign language interpreter.

    Captures webcam frames and runs the MediaPipe Gesture Recognizer on each
    frame. Confirmed signs are accumulated into a phrase. When no hands are
    detected for inactivity_threshold seconds, the full phrase is sent to the Arduino.
    """
    cap = cv2.VideoCapture(0)
    arduino = connect_arduino()

    base_options = mp_python.BaseOptions(model_asset_path=MODEL_PATH)
    options = vision.GestureRecognizerOptions(base_options=base_options)
    recognizer = vision.GestureRecognizer.create_from_options(options)

    phrase = ''
    last_sign = ''
    sign_frame_count = 0
    sign_confirm_frames = 20
    inactive_start = time.time()
    inactivity_threshold = 3
    recording = False

    while True:
        _, img = cap.read()
        img = cv2.flip(img, 1)
        key = cv2.waitKey(1) & 0xFF

        # Toggle recording with space bar
        if key == ord(' '):
            recording = not recording
            phrase = ''
            sign_frame_count = 0

        if recording:
            # Step 1: Run quantised CV model on frame
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
            result = recognizer.recognize(mp_image)

            if result.hand_landmarks:
                inactive_start = time.time()
                h, w, _ = img.shape
                lms = result.hand_landmarks[0]

                # Step 2: ROI - compute hand bounding box from landmarks
                x_coords = [int(lm.x * w) for lm in lms]
                y_coords = [int(lm.y * h) for lm in lms]
                x1 = max(0, min(x_coords) - 25)
                y1 = max(0, min(y_coords) - 25)
                x2 = min(w, max(x_coords) + 25)
                y2 = min(h, max(y_coords) + 25)
                cv2.rectangle(img, (x1, y1), (x2, y2), (255, 255, 255), 3)

                # Step 3: Determine the sign
                sign = ''
                if result.gestures:
                    gesture = result.gestures[0][0].category_name
                    sign = SIGN_LABELS.get(gesture, '')

                # Fallback: landmark-based detection for custom signs
                if not sign:
                    handedness = result.handedness[0][0].category_name if result.handedness else 'Right'
                    states = get_finger_states(lms, handedness)
                    sign = LANDMARK_SIGNS.get(states, '')

                if sign:
                    cv2.putText(img, sign, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)

                    if sign == last_sign:
                        sign_frame_count += 1
                    else:
                        last_sign = sign
                        sign_frame_count = 1

                    # Step 4: Confirm sign then add to phrase
                    if sign_frame_count == sign_confirm_frames:
                        phrase += sign + ' '
                        print(phrase.strip())
                        send_to_arduino(arduino, sign)
                        sign_frame_count = 0
            else:
                sign_frame_count = 0

                # Send full phrase after inactivity threshold
                if time.time() - inactive_start >= inactivity_threshold and phrase.strip():
                    send_to_arduino(arduino, phrase.strip())
                    phrase = ''
                    inactive_start = time.time()

        # Status overlay
        status = 'RECORDING' if recording else 'PRESS SPACE TO START'
        color = (0, 255, 0) if recording else (0, 0, 255)
        cv2.putText(img, status, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
        cv2.putText(img, phrase.strip(), (10, 70), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        cv2.imshow('Sign Language Interpreter', img)

        if key == ord('q'):
            break
        if key == ord('c'):
            phrase = ''

    cap.release()
    cv2.destroyAllWindows()
    if arduino:
        arduino.close()


if __name__ == '__main__':
    main()
