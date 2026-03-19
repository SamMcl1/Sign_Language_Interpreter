"""
Real-time sign language interpreter using the MediaPipe Gesture Recognizer.

Controls:
    Space - Start/Stop recording
    Q - Quit
    C - Clear the current word
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
SIGN_CONFIRM_FRAMES = 3
SEND_COOLDOWN = 1.0

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
    try:
        arduino = serial.Serial(ARDUINO_PORT, BAUD_RATE, timeout=1)
        time.sleep(2)
        print(f'Arduino connected on {ARDUINO_PORT}')
        return arduino
    except serial.SerialException:
        print(f'Arduino not found on {ARDUINO_PORT}, running without it')
        return None


def send_to_arduino(arduino, text):
    if arduino:
        arduino.write(f'{text}\n'.encode())


def main():
    cap = cv2.VideoCapture(0)
    arduino = connect_arduino()

    base_options = mp_python.BaseOptions(model_asset_path=MODEL_PATH)
    options = vision.GestureRecognizerOptions(base_options=base_options)
    recognizer = vision.GestureRecognizer.create_from_options(options)

    word = ''
    last_sign = ''
    sign_frame_count = 0
    recording = False
    last_send_time = 0
    fullscreen = False

    cv2.namedWindow('Sign Language Interpreter', cv2.WINDOW_NORMAL)

    while True:
        _, img = cap.read()
        img = cv2.flip(img, 1)
        key = cv2.waitKey(1) & 0xFF

        if key == ord(' '):
            recording = not recording
            word = ''
            sign_frame_count = 0
            send_to_arduino(arduino, 'START' if recording else 'STOP')

        if recording:
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
            result = recognizer.recognize(mp_image)

            if result.hand_landmarks:
                h, w, _ = img.shape
                lms = result.hand_landmarks[0]
                x_coords = [int(lm.x * w) for lm in lms]
                y_coords = [int(lm.y * h) for lm in lms]
                x1 = max(0, min(x_coords) - 25)
                y1 = max(0, min(y_coords) - 25)
                x2 = min(w, max(x_coords) + 25)
                y2 = min(h, max(y_coords) + 25)
                cv2.rectangle(img, (x1, y1), (x2, y2), (255, 255, 255), 3)

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

                        now = time.time()
                        if sign_frame_count == SIGN_CONFIRM_FRAMES and (now - last_send_time) >= SEND_COOLDOWN:
                            word += sign + ' '
                            print(word.strip())
                            send_to_arduino(arduino, sign)
                            last_send_time = now
                            sign_frame_count = 0
            else:
                sign_frame_count = 0

        status = 'RECORDING' if recording else 'PRESS SPACE TO START'
        color = (0, 0, 255) if recording else (0, 255, 0)
        cv2.putText(img, status, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
        cv2.putText(img, word.strip(), (10, 70), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        cv2.imshow('Sign Language Interpreter', img)

        if key == ord('q'):
            break
        if key == ord('c'):
            word = ''
        if key == ord('f'):
            fullscreen = not fullscreen
            if fullscreen:
                cv2.setWindowProperty('Sign Language Interpreter', cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
            else:
                cv2.setWindowProperty('Sign Language Interpreter', cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_NORMAL)

    cap.release()
    cv2.destroyAllWindows()
    if arduino:
        arduino.close()


if __name__ == '__main__':
    main()
