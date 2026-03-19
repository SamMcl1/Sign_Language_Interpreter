"""
ASL Model Test — Google PopSign TFLite (250 signs)

Uses MediaPipe FaceLandmarker + PoseLandmarker + HandLandmarker to extract
all 543 landmarks per frame, then feeds them into the pre-trained TFLite model.

Controls:
    Q - Quit
"""

import cv2
import numpy as np
import json
import tensorflow as tf
import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision

# --- Config ---
FACE_MODEL    = 'face_landmarker.task'
POSE_MODEL    = 'pose_landmarker.task'
HAND_MODEL    = 'hand_landmarker.task'
ASL_MODEL     = 'asl_model.tflite'
LABEL_MAP     = 'sign_to_prediction_index_map.json'

NUM_FACE  = 468
NUM_POSE  = 33
NUM_HAND  = 21
NUM_TOTAL = NUM_FACE + NUM_POSE + NUM_HAND * 2  # 543

# --- Load label map ---
with open(LABEL_MAP) as f:
    sign_map = json.load(f)
ORD2SIGN = {v: k for k, v in sign_map.items()}

# --- Load TFLite model ---
interpreter = tf.lite.Interpreter(ASL_MODEL)
interpreter.allocate_tensors()
input_details  = interpreter.get_input_details()
output_details = interpreter.get_output_details()

# --- MediaPipe landmark models (VIDEO mode for smooth tracking) ---
base = mp_python.BaseOptions

face_opts = vision.FaceLandmarkerOptions(
    base_options=base(model_asset_path=FACE_MODEL),
    running_mode=vision.RunningMode.VIDEO,
    num_faces=1,
)
pose_opts = vision.PoseLandmarkerOptions(
    base_options=base(model_asset_path=POSE_MODEL),
    running_mode=vision.RunningMode.VIDEO,
    num_poses=1,
)
hand_opts = vision.HandLandmarkerOptions(
    base_options=base(model_asset_path=HAND_MODEL),
    running_mode=vision.RunningMode.VIDEO,
    num_hands=2,
)

face_detector = vision.FaceLandmarker.create_from_options(face_opts)
pose_detector = vision.PoseLandmarker.create_from_options(pose_opts)
hand_detector  = vision.HandLandmarker.create_from_options(hand_opts)


def extract_landmarks(mp_image, timestamp_ms):
    """Extract and combine all 543 landmarks into a (543, 3) float32 array."""
    lms = np.zeros((NUM_TOTAL, 3), dtype=np.float32)

    # Face (0..467)
    face_result = face_detector.detect_for_video(mp_image, timestamp_ms)
    if face_result.face_landmarks:
        for i, lm in enumerate(face_result.face_landmarks[0][:NUM_FACE]):
            lms[i] = [lm.x, lm.y, lm.z]

    # Pose (468..500)
    pose_result = pose_detector.detect_for_video(mp_image, timestamp_ms)
    if pose_result.pose_landmarks:
        for i, lm in enumerate(pose_result.pose_landmarks[0][:NUM_POSE]):
            lms[NUM_FACE + i] = [lm.x, lm.y, lm.z]

    # Hands (501..521 = left, 522..542 = right)
    hand_result = hand_detector.detect_for_video(mp_image, timestamp_ms)
    left_filled  = False
    right_filled = False
    if hand_result.hand_landmarks:
        for hand_lms, handedness in zip(hand_result.hand_landmarks, hand_result.handedness):
            label = handedness[0].category_name  # 'Left' or 'Right'
            if label == 'Left' and not left_filled:
                offset = NUM_FACE + NUM_POSE
                for i, lm in enumerate(hand_lms):
                    lms[offset + i] = [lm.x, lm.y, lm.z]
                left_filled = True
            elif label == 'Right' and not right_filled:
                offset = NUM_FACE + NUM_POSE + NUM_HAND
                for i, lm in enumerate(hand_lms):
                    lms[offset + i] = [lm.x, lm.y, lm.z]
                right_filled = True

    return lms


def predict(landmarks):
    """Run TFLite inference and return top-3 (sign, confidence) pairs."""
    inp = landmarks[np.newaxis, :, :]  # (1, 543, 3)
    interpreter.set_tensor(input_details[0]['index'], inp)
    interpreter.invoke()
    output = interpreter.get_tensor(output_details[0]['index'])  # (250,)
    probs  = np.exp(output) / np.sum(np.exp(output))             # softmax
    top3   = np.argsort(probs)[-3:][::-1]
    return [(ORD2SIGN[i], float(probs[i])) for i in top3]


# --- Main loop ---
cap = cv2.VideoCapture(0)
print("ASL model loaded. Press Q to quit.")

while True:
    ret, frame = cap.read()
    if not ret:
        break

    timestamp_ms = int(cap.get(cv2.CAP_PROP_POS_MSEC))
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)

    landmarks = extract_landmarks(mp_image, timestamp_ms)
    top3 = predict(landmarks)

    # Display top prediction
    sign, conf = top3[0]
    label = f"{sign}  {conf*100:.1f}%"
    cv2.putText(frame, label, (20, 50),
                cv2.FONT_HERSHEY_SIMPLEX, 1.4, (0, 255, 0), 3)

    # Display top-3
    for rank, (s, c) in enumerate(top3):
        cv2.putText(frame, f"  {rank+1}. {s} {c*100:.1f}%", (20, 100 + rank*35),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (200, 200, 200), 2)

    cv2.imshow('ASL Test', frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
face_detector.close()
pose_detector.close()
hand_detector.close()
