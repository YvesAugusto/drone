import cv2

cap = cv2.VideoCapture("http://192.168.0.108:8080/video")
while True:
  ret, frame = cap.read()
  print(frame.shape)