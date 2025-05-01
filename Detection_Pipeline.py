import numpy as np
import cv2
from Detection_Model import YoloImageDetector

class DetectionPipeline:
    def __init__(self) -> None:
        self.detector = YoloImageDetector()
    
    
    def image_preprocessing(self, frame: np.ndarray) -> np.ndarray:
        return cv2.resize(frame, (854, 480), interpolation=cv2.INTER_CUBIC)
    
    
    def detect_objects(self, frame: np.ndarray, source_ip: str) -> None:
        self.detector.predict_image(frame, source_ip)
    
    
    def process_frame(self, frame: np.ndarray, source_ip: str) -> None:
        frame = self.image_preprocessing(frame)
        self.detect_objects(frame, source_ip)
