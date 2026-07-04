#!/usr/bin/env python3
"""
GENI Master Sensing Core - YOLOv8 Pose Detection
Detects falls, desk faints, and unresponsive states
Sends HTTP alerts to Node.js backend when emergency detected

Mathematical Thresholds (CALIBRATED - DO NOT CHANGE):
- nose_vel > 35: Head dropping fast
- hip_vel > 45: Hips dropping fast (floor fall)
- abs(nose_y - hip_y) < 65: Head near hip level (collapsed)
- nose_y > shoulder_y + 40: Head below shoulders (desk slump)
- nose_y < hip_y - 120: Standing upright (reset)
- 3.0 seconds: Confirmation timer
"""

import cv2
import time
import os
import sys
import requests
import json
from ultralytics import YOLO

os.environ['YOLO_VERBOSE'] = 'False'

# Backend URL
BACKEND_URL = os.getenv('YOLO_BACKEND_URL', 'http://localhost:5001')
ALERT_ENDPOINT = f'{BACKEND_URL}/api/yolo/emergency'

# Load model
print("[YOLO] Loading YOLOv8 pose model...")
model = YOLO('yolov8n-pose.pt')
print("[YOLO] Model loaded successfully")

# Camera
cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
if not cap.isOpened():
    print("[ERROR] Cannot open camera. Make sure camera is connected.")
    sys.exit(1)

# Detection state
prev_nose_y = 0
prev_hip_y = 0
fall_primed = False
still_seconds = 0
emergency_triggered = False
last_time = time.time()
frame_count = 0

print("[GENI] Master Sensing Active - Monitoring for falls/faints")
print(f"[GENI] Backend: {BACKEND_URL}")

try:
    while True:
        ret, frame = cap.read()
        if not ret:
            print("[ERROR] Frame read failed")
            break

        frame_count += 1
        results = model(frame, verbose=False)
        person_down = False

        for r in results:
            # Plot skeleton only (no boxes, no labels)
            frame = r.plot(labels=False, boxes=False)
            
            if r.keypoints and len(r.keypoints.xy[0]) > 11:
                pts = r.keypoints.xy[0]
                try:
                    nose_y = float(pts[0][1])
                    shoulder_y = (float(pts[5][1]) + float(pts[6][1])) / 2
                    hip_y = float(pts[11][1])

                    # === VELOCITY TRIGGERS ===
                    nose_vel = nose_y - prev_nose_y
                    hip_vel = hip_y - prev_hip_y

                    # Impact detection: Head drops fast OR Hips drop fast
                    if nose_vel > 35 or hip_vel > 45:
                        fall_primed = True
                        print(f"[DETECT] Impact: nose_vel={nose_vel:.1f}, hip_vel={hip_vel:.1f}")

                    # === POSITION CHECK ===
                    # Desk slump: Head below shoulders
                    if nose_y > shoulder_y + 40:
                        person_down = True
                    
                    # Floor collapse: Head near hip level
                    if abs(nose_y - hip_y) < 65:
                        person_down = True

                    # === RESET LOGIC ===
                    # Standing up: Nose well above hips
                    if nose_y < hip_y - 120:
                        if fall_primed or still_seconds > 0:
                            print("[RESET] Person stood up - clearing fall state")
                        fall_primed = False
                        still_seconds = 0
                        emergency_triggered = False

                    prev_nose_y = nose_y
                    prev_hip_y = hip_y

                except Exception as e:
                    print(f"[ERROR] Keypoint processing: {e}")
                    continue

        # === 3-SECOND CONFIRMATION TIMER ===
        now = time.time()
        dt = now - last_time
        last_time = now

        if fall_primed and person_down:
            still_seconds += dt
        elif fall_primed and not person_down:
            # Out-of-sight scenario: Person disappeared after fall
            still_seconds += dt
        else:
            still_seconds = 0

        # === TRIGGER ALERT ===
        if still_seconds > 3.0 and not emergency_triggered:
            print("=" * 60)
            print("🚨 !!! EMERGENCY: DISPATCHING ALERT !!!")
            print("=" * 60)
            emergency_triggered = True

            # Send HTTP alert to backend
            try:
                alert_data = {
                    'type': 'fall' if hip_vel > 45 else 'desk_faint',
                    'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
                    'confidence': 0.95,
                    'detected_at_frame': frame_count,
                    'person_detected': True
                }
                
                print(f"[ALERT] Sending to backend: {ALERT_ENDPOINT}")
                response = requests.post(ALERT_ENDPOINT, json=alert_data, timeout=5)
                
                if response.status_code == 200:
                    print("[ALERT] ✅ Alert sent successfully")
                else:
                    print(f"[ALERT] ⚠️ Alert failed: {response.status_code}")
            except Exception as e:
                print(f"[ALERT] ❌ Error sending alert: {e}")

        # === UI DISPLAY ===
        if emergency_triggered:
            cv2.rectangle(frame, (0, 0), (640, 65), (0, 0, 255), -1)
            cv2.putText(
                frame, 
                "EMERGENCY: UNRESPONSIVE", 
                (130, 42), 
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8, 
                (255, 255, 255), 
                2
            )
        elif still_seconds > 0.1:
            cv2.putText(
                frame,
                f"CONFIRMING: {still_seconds:.1f}s",
                (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 215, 255),
                2
            )
        else:
            cv2.putText(
                frame,
                "GENI: MONITORING",
                (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 255, 0),
                2
            )

        cv2.imshow("GENI Master Sensing - YOLOv8 Pose Detection", frame)
        
        if cv2.waitKey(1) & 0xFF == ord('q'):
            print("[SHUTDOWN] Quit signal received")
            break

except KeyboardInterrupt:
    print("\n[SHUTDOWN] Ctrl+C received")
except Exception as e:
    print(f"[ERROR] Unexpected error: {e}")
finally:
    cap.release()
    cv2.destroyAllWindows()
    print("[SHUTDOWN] Cleanup complete")
