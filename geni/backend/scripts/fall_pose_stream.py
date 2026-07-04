#!/usr/bin/env python3
"""
GENI Fall Pose Stream
Consumes base64 JPEG frames from stdin and outputs fall state JSON per frame.
"""

import sys
import json
import time
import base64
import cv2
import numpy as np
from ultralytics import YOLO

class FallPoseStream:
    def __init__(self):
        self.model = YOLO('yolov8n-pose.pt')
        self.prev_nose_y = 0.0
        self.prev_hip_y = 0.0
        self.fall_primed = False
        self.still_seconds = 0.0
        self.emergency_triggered = False
        self.last_time = time.time()
        
        self.NOSE_VEL_THRESHOLD = 35
        self.HIP_VEL_THRESHOLD = 45
        self.CONFIRMATION_TIME = 3.0
        self.RECOVERY_HEIGHT = 120
    
    def decode_image(self, image_b64: str):
        image_b64 = image_b64.replace('data:image/jpeg;base64,', '')
        try:
            img_bytes = base64.b64decode(image_b64)
            img_array = np.frombuffer(img_bytes, np.uint8)
            return cv2.imdecode(img_array, cv2.IMREAD_COLOR)
        except Exception:
            return None
    
    def detect_fall(self, frame):
        results = self.model(frame, verbose=False)
        person_down = False
        keypoints_detected = False
        nose_y = None
        hip_y = None
        shoulder_y = None
        nose_x = None
        hip_x = None
        shoulder_x = None
        nose_vel = None
        hip_vel = None
        frame_h, frame_w = frame.shape[:2]
        
        for r in results:
            if r.keypoints and len(r.keypoints.xy[0]) > 11:
                keypoints_detected = True
                pts = r.keypoints.xy[0]
                
                try:
                    nose_x = float(pts[0][0])
                    nose_y = float(pts[0][1])
                    shoulder_x = float((pts[5][0] + pts[6][0]) / 2)
                    shoulder_y = float((pts[5][1] + pts[6][1]) / 2)
                    hip_x = float(pts[11][0])
                    hip_y = float(pts[11][1])
                    
                    nose_vel = nose_y - self.prev_nose_y
                    hip_vel = hip_y - self.prev_hip_y
                    
                    if nose_vel > self.NOSE_VEL_THRESHOLD or hip_vel > self.HIP_VEL_THRESHOLD:
                        if not self.fall_primed:
                            self.fall_primed = True
                    
                    # Person down heuristics (normalized + relative)
                    nose_hip_close = abs(nose_y - hip_y) < max(65, frame_h * 0.12)
                    shoulders_low = shoulder_y > frame_h * 0.65
                    hips_low = hip_y > frame_h * 0.8
                    if (nose_y > shoulder_y + 40) or nose_hip_close or (shoulders_low and hips_low):
                        person_down = True
                    
                    if nose_y < hip_y - self.RECOVERY_HEIGHT:
                        self.fall_primed = False
                        self.still_seconds = 0.0
                    
                    self.prev_nose_y = nose_y
                    self.prev_hip_y = hip_y
                    
                except Exception:
                    continue
        
        return {
            "keypoints_detected": keypoints_detected,
            "person_down": person_down,
            "nose_x": nose_x,
            "nose_y": nose_y,
            "hip_x": hip_x,
            "hip_y": hip_y,
            "shoulder_x": shoulder_x,
            "shoulder_y": shoulder_y,
            "nose_velocity": nose_vel,
            "hip_velocity": hip_vel,
            "frame_height": frame_h,
            "frame_width": frame_w,
        }
    
    def update_state(self, person_down, keypoints_detected, nose_vel, hip_vel):
        now = time.time()
        dt = now - self.last_time
        self.last_time = now
        
        # Prime on sudden movement
        if nose_vel is not None and abs(nose_vel) >= self.NOSE_VEL_THRESHOLD:
            self.fall_primed = True
        if hip_vel is not None and abs(hip_vel) >= self.HIP_VEL_THRESHOLD:
            self.fall_primed = True
        
        if person_down and not self.fall_primed:
            self.fall_primed = True
        
        if self.fall_primed and (person_down or not keypoints_detected):
            self.still_seconds += dt
        else:
            self.still_seconds = 0.0
        
        if self.still_seconds >= self.CONFIRMATION_TIME and not self.emergency_triggered:
            self.emergency_triggered = True
        
        return {
            "fall_primed": self.fall_primed,
            "still_seconds": round(self.still_seconds, 2),
            "emergency_triggered": self.emergency_triggered,
            "confirmation_time": self.CONFIRMATION_TIME,
        }

def main():
    stream = FallPoseStream()
    
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        
        try:
            payload = json.loads(line)
            image_b64 = payload.get("image")
            req_id = payload.get("id")
            
            frame = stream.decode_image(image_b64)
            if frame is None:
                result = {
                    "id": req_id,
                    "timestamp": time.time(),
                    "keypointsDetected": False,
                    "personDown": False,
                    "fallPrimed": False,
                    "emergencyTriggered": False,
                    "stillSeconds": 0.0,
                    "confirmationTime": stream.CONFIRMATION_TIME,
                    "message": "Failed to decode image"
                }
                print(json.dumps(result))
                sys.stdout.flush()
                continue
            
            detection = stream.detect_fall(frame)
            state = stream.update_state(
                detection["person_down"],
                detection["keypoints_detected"],
                detection["nose_velocity"],
                detection["hip_velocity"]
            )
            
            result = {
                "id": req_id,
                "timestamp": time.time(),
                "keypointsDetected": detection["keypoints_detected"],
                "noseX": detection["nose_x"],
                "noseY": detection["nose_y"],
                "hipX": detection["hip_x"],
                "hipY": detection["hip_y"],
                "shoulderX": detection["shoulder_x"],
                "shoulderY": detection["shoulder_y"],
                "noseVelocity": detection["nose_velocity"],
                "hipVelocity": detection["hip_velocity"],
                "personDown": detection["person_down"],
                "fallPrimed": state["fall_primed"],
                "emergencyTriggered": state["emergency_triggered"],
                "stillSeconds": state["still_seconds"],
                "confirmationTime": state["confirmation_time"],
            }
            
            print(json.dumps(result))
            sys.stdout.flush()
        except Exception as e:
            err = {
                "id": payload.get("id") if "payload" in locals() else "unknown",
                "timestamp": time.time(),
                "keypointsDetected": False,
                "personDown": False,
                "fallPrimed": False,
                "emergencyTriggered": False,
                "stillSeconds": 0.0,
                "confirmationTime": stream.CONFIRMATION_TIME,
                "message": f"Error: {str(e)}",
            }
            print(json.dumps(err))
            sys.stdout.flush()

if __name__ == "__main__":
    main()
