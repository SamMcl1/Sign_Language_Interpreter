"""
Real-time sign language interpreter using the MediaPipe Gesture Recognizer.

Pipeline:
    Camera -> Gesture Recognizer (hand detection + ROI + CV model)
           -> Sign determination -> Speech output + Arduino serial

Controls:
    Q - Quit
    C - Clear the current word
"""

import cv2
import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision
import serial
import time
from gtts import gTTS
import io
import pygame
import warnings

warnings.filterwarnings('ignore')

ARDUINO_PORT = '/dev/ttyACM0'
BAUD_RATE = 9600
MODEL_PATH = 'gesture_recognizer.task'

# Maps MediaPipe gesture names to readable signs
SIGN_LABELS = {
    'Closed_Fist': 'fist',
    'Open_Palm': 'hello',
    'Pointing_Up': 'one',
    'Thumb_Down': 'no',
    'Thumb_Up': 'yes',
    'Victory': 'peace',
    'ILoveYou': 'i love you',
}


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
        text (str): The sign label to transmit.
    """
    if arduino:
        arduino.write(f'{text}\n'.encode())


def speech(text):
    """
    Speaks the given text using gTTS and pygame.

    Blocks until playback is complete.

    Parameters:
        text (str): Text to be spoken aloud.
    """
    tts = gTTS(text=text, lang='en', slow=False)
    mp3_fp = io.BytesIO()
    tts.write_to_fp(mp3_fp)
    mp3_fp.seek(0)
    pygame.mixer.music.load(mp3_fp, 'mp3')
    pygame.mixer.music.play()
    while pygame.mixer.music.get_busy():
        pygame.time.Clock().tick(10)


def main():
    """
    Runs the letter-level sign language interpreter.

    Captures webcam frames, runs the MediaPipe Gesture Recognizer on each
    frame, draws the hand ROI bounding box, and confirms a sign after it
    appears consistently for sign_confirm_frames frames. Confirmed signs
    are appended to a word, spoken aloud, and sent to the Arduino.
    """
    pygame.mixer.init()
    cap = cv2.VideoCapture(0)
    arduino = connect_arduino()

    base_options = mp_python.BaseOptions(model_asset_path=MODEL_PATH)
    options = vision.GestureRecognizerOptions(base_options=base_options)
    recognizer = vision.GestureRecognizer.create_from_options(options)

    word = ''
    last_sign = ''
    sign_frame_count = 0
    sign_confirm_frames = 20
    recording = False

    while True:
        _, img = cap.read()
        img = cv2.flip(img, 1)
        key = cv2.waitKey(1) & 0xFF

        # Toggle recording with space bar
        if key == ord(' '):
            recording = not recording
            word = ''
            sign_frame_count = 0

        if recording:
            # Step 1: Run quantised CV model on frame
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
            result = recognizer.recognize(mp_image)

            if result.hand_landmarks:
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
                if result.gestures:
                    gesture = result.gestures[0][0].category_name
                    sign = SIGN_LABELS.get(gesture, '')

                    if sign:
                        cv2.putText(img, sign, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)

                        if sign == last_sign:
                            sign_frame_count += 1
                        else:
                            last_sign = sign
                            sign_frame_count = 1

                        # Step 4: Confirm sign then output
                        if sign_frame_count == sign_confirm_frames:
                            word += sign + ' '
                            print(word.strip())
                            speech(sign)
                            send_to_arduino(arduino, sign)
                            sign_frame_count = 0
            else:
                sign_frame_count = 0

        # Status overlay
        status = 'RECORDING' if recording else 'PRESS SPACE TO START'
        color = (0, 0, 255) if recording else (0, 255, 0)
        cv2.putText(img, status, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
        cv2.putText(img, word.strip(), (10, 70), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        cv2.imshow('Sign Language Interpreter', img)

        if key == ord('q'):
            break
        if key == ord('c'):
            word = ''

    cap.release()
    cv2.destroyAllWindows()
    if arduino:
        arduino.close()


if __name__ == '__main__':
    main()
