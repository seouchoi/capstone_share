import numpy as np
import cv2
from Detection_Model import YoloImageDetector
from typing import Any

class DetectionPipeline:
    def __init__(self, pipe : Any) -> None:
        self.pipe = pipe
        #self.detector = YoloImageDetector() #객체 탐지 클래스를 선언
        pass
    
    def image_preprocessing(self, frame: np.ndarray) -> np.ndarray:
        return cv2.resize(frame, (854, 480), interpolation=cv2.INTER_CUBIC) #이미지를 전처리(리사이징)을 하는 부분.(모델의 훈련 부분이 오직 리사이즈만 시행했기 때문에 이 이상은 전처리 못함.)
    
    
    def detect_objects(self, frame: np.ndarray, source_ip: str) -> None:
        #x, y, ret = self.detector.predict_image(frame, source_ip) #객체 탐지지
        #if ret:
        #    self.pipe.send((str(x),str(y)))
            
            
        cv2.imshow(source_ip, frame)
        cv2.waitKey(1)
    
    def process_frame(self, frame: np.ndarray, source_ip: str) -> None: #이미지 전처리와 객체 탐지를 수행시키는 부분.(Get_Video파일에서 while True로 계속해서 작동됨.)
        frame = self.image_preprocessing(frame) 
        self.detect_objects(frame, source_ip)
