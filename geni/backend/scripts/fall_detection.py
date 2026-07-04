#!/usr/bin/env python3
"""
GENI Fall Detection System
Adapted from your original code with improvements for production
Outputs JSON events to Node.js backend instead of on-screen alerts
"""

import cv2
from ultralytics import YOLO
import time
import os
import sys
import json

# Suppress verbose YOLO output
os.environ['YOLO_VERBOSE'] = 'False'

class FallDetectionSystem:
    def __init__(self, patient_name="Patient", camera_index=0):
        """Initialize fall detection system"""
        self.patient_name = patient_name
        self.model = YOLO('yolov8n-pose.pt')
        
        # Try different backends for camera compatibility
        try:
            self.cap = cv2.VideoCapture(camera_index, cv2.CAP_DSHOW)
        except:
            self.cap = cv2.VideoCapture(camera_index)
        
        if not self.cap.isOpened():
            self.log_event("error", "Failed to open camera", {"camera_index": camera_index})
            sys.exit(1)
        
        # State tracking variables
        self.prev_nose_y = 0
        self.prev_hip_y = 0
        self.fall_primed = False
        self.still_seconds = 0
        self.emergency_triggered = False
        self.last_time = time.time()
        self.alert_sent_time = None
        
        # Configuration
        self.NOSE_VEL_THRESHOLD = 35  # pixels/frame for head drop (desk fall)
        self.HIP_VEL_THRESHOLD = 45   # pixels/frame for body drop (floor fall)
        self.CONFIRMATION_TIME = 3.0  # seconds to confirm before alerting
        self.RECOVERY_HEIGHT = 120    # pixels above hip to reset
        
        self.log_event("info", "Fall detection initialized", {
            "patient": self.patient_name,
            "camera": camera_index,
            "confirmation_time": self.CONFIRMATION_TIME
        })
    
    def log_event(self, level, message, data=None):
        """Output structured JSON events for Node.js to consume"""
        event = {
            "timestamp": time.time(),
            "level": level,
            "message": message,
            "patient": self.patient_name
        }
        if data:
            event["data"] = data
        
        # Print JSON to stdout (Node.js will capture this)
        print(json.dumps(event))
        sys.stdout.flush()
    
    def detect_fall(self, frame):
        """Run YOLO pose detection and analyze for falls"""
        results = self.model(frame, verbose=False)
        person_down = False
        keypoints_detected = False
        
        for r in results:
            if r.keypoints and len(r.keypoints.xy[0]) > 11:
                keypoints_detected = True
                pts = r.keypoints.xy[0]
                
                try:
                    # Extract keypoint positions
                    nose_y = float(pts[0][1])
                    shoulder_y = float((pts[5][1] + pts[6][1]) / 2)
                    hip_y = float(pts[11][1])
                    
                    # 1. VELOCITY TRIGGERS (Erratic Movement Detection)
                    nose_vel = nose_y - self.prev_nose_y
                    hip_vel = hip_y - self.prev_hip_y
                    
                    # Trigger if Head drops fast (Desk) OR Hips drop fast (Floor)
                    if nose_vel > self.NOSE_VEL_THRESHOLD or hip_vel > self.HIP_VEL_THRESHOLD:
                        if not self.fall_primed:
                            self.fall_primed = True
                            self.log_event("warning", "Impact detected", {
                                "nose_velocity": round(nose_vel, 2),
                                "hip_velocity": round(hip_vel, 2),
                                "type": "desk" if nose_vel > hip_vel else "floor"
                            })
                    
                    # 2. POSITION CHECK (Is the body "Down"?)
                    # Scenario A: Head is below shoulders (Desk Slump)
                    # Scenario B: Head is near hip level (Floor Collapse)
                    if (nose_y > shoulder_y + 40) or (abs(nose_y - hip_y) < 65):
                        person_down = True
                    
                    # 3. RECOVERY DETECTION: If you stand back up
                    if nose_y < hip_y - self.RECOVERY_HEIGHT:
                        if self.fall_primed or self.emergency_triggered:
                            self.log_event("info", "Recovery detected - standing up", {
                                "nose_height": round(nose_y, 2),
                                "hip_height": round(hip_y, 2)
                            })
                        
                        self.fall_primed = False
                        self.still_seconds = 0
                        # Don't reset emergency_triggered here - let backend handle
                    
                    # Update previous positions for next frame
                    self.prev_nose_y = nose_y
                    self.prev_hip_y = hip_y
                    
                except Exception as e:
                    self.log_event("error", "Keypoint extraction failed", {"error": str(e)})
                    continue
        
        return person_down, keypoints_detected
    
    def update_state(self, person_down, keypoints_detected):
        """Update fall detection state with delta time"""
        now = time.time()
        dt = now - self.last_time
        self.last_time = now
        
        # Update confirmation timer
        if self.fall_primed and (person_down or not keypoints_detected):
            self.still_seconds += dt
            
            # Log confirmation progress every second
            if int(self.still_seconds) != int(self.still_seconds - dt):
                self.log_event("info", "Confirming fall state", {
                    "elapsed": round(self.still_seconds, 1),
                    "threshold": self.CONFIRMATION_TIME,
                    "person_down": person_down,
                    "keypoints_visible": keypoints_detected
                })
        else:
            if self.still_seconds > 0:
                self.log_event("info", "Confirmation timer reset", {
                    "elapsed": round(self.still_seconds, 1)
                })
            self.still_seconds = 0
        
        # TRIGGER EMERGENCY after confirmation time
        if self.still_seconds >= self.CONFIRMATION_TIME and not self.emergency_triggered:
            self.emergency_triggered = True
            self.alert_sent_time = time.time()
            
            self.log_event("emergency", "FALL DETECTED - CONFIRMED", {
                "confirmation_time": round(self.still_seconds, 1),
                "patient": self.patient_name,
                "person_visible": keypoints_detected,
                "person_down": person_down,
                "response_requested": True
            })
    
    def get_status(self):
        """Get current system status for display"""
        if self.emergency_triggered:
            elapsed = time.time() - self.alert_sent_time if self.alert_sent_time else 0
            return {
                "state": "emergency",
                "message": "EMERGENCY: UNRESPONSIVE",
                "elapsed_since_alert": round(elapsed, 1)
            }
        elif self.still_seconds > 0.1:
            return {
                "state": "confirming",
                "message": f"CONFIRMING STATE: {round(self.still_seconds, 1)}s / {self.CONFIRMATION_TIME}s",
                "progress": self.still_seconds / self.CONFIRMATION_TIME
            }
        else:
            return {
                "state": "monitoring",
                "message": "MONITORING"
            }
    
    def reset_emergency(self):
        """Reset emergency state (called from backend when user confirms OK)"""
        if self.emergency_triggered:
            self.log_event("info", "Emergency reset by user confirmation", {
                "duration": round(time.time() - self.alert_sent_time, 1) if self.alert_sent_time else 0
            })
        
        self.emergency_triggered = False
        self.fall_primed = False
        self.still_seconds = 0
        self.alert_sent_time = None
    
    def run(self, headless=False):
        """Main detection loop"""
        self.log_event("info", "Fall detection started", {"headless": headless})
        
        while True:
            ret, frame = self.cap.read()
            if not ret:
                self.log_event("error", "Failed to read camera frame", {})
                break
            
            # Run detection
            person_down, keypoints_detected = self.detect_fall(frame)
            
            # Update state with timing
            self.update_state(person_down, keypoints_detected)
            
            # Display frame if not headless (for testing)
            if not headless:
                status = self.get_status()
                
                # Draw status overlay
                if status["state"] == "emergency":
                    cv2.rectangle(frame, (0, 0), (640, 65), (0, 0, 255), -1)
                    cv2.putText(frame, status["message"], (130, 42), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
                elif status["state"] == "confirming":
                    cv2.putText(frame, status["message"], (20, 40), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 215, 255), 2)
                else:
                    cv2.putText(frame, f"GENI: {status['message']}", (20, 40), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                
                cv2.imshow("GENI Fall Detection", frame)
                
                # Handle keyboard input
                key = cv2.waitKey(1) & 0xFF
                if key == ord('q'):
                    self.log_event("info", "User stopped detection", {})
                    break
                elif key == ord('r'):
                    # Manual reset for testing
                    self.reset_emergency()
            else:
                # Headless mode - minimal delay
                time.sleep(0.01)
        
        self.cleanup()
    
    def cleanup(self):
        """Clean up resources"""
        self.log_event("info", "Fall detection stopped", {})
        self.cap.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="GENI Fall Detection System")
    parser.add_argument("--patient", default="Patient", help="Patient name")
    parser.add_argument("--camera", type=int, default=0, help="Camera index")
    parser.add_argument("--headless", action="store_true", help="Run without display (production)")
    
    args = parser.parse_args()
    
    detector = FallDetectionSystem(
        patient_name=args.patient,
        camera_index=args.camera
    )
    
    try:
        detector.run(headless=args.headless)
    except KeyboardInterrupt:
        detector.log_event("info", "Interrupted by user", {})
        detector.cleanup()
    except Exception as e:
        detector.log_event("error", "Unexpected error", {"error": str(e)})
        detector.cleanup()
        sys.exit(1)
