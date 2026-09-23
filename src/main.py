from video import PersonDetector, ZoneEditor
import cv2

def main():
    WINDOW_NAME = "CCTV"  # 창 이름을 변수로 통일

    person_detector = PersonDetector("yolov8n.pt", classes=[0, 1], conf=0.5)
    zone_editor = ZoneEditor(window_name=WINDOW_NAME)  # 같은 이름으로 넘김
    cap = cv2.VideoCapture("./data/input/test_trespass.mp4")

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        boxes = person_detector.detect(frame)
        person_detector.draw(frame, boxes)
        zone_editor.draw(frame)

        cv2.imshow(WINDOW_NAME, frame)  # editor랑 동일한 이름 사용
        key = cv2.waitKey(1)
        if key == 27:
            break
        zone_editor.handle_key(key)

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()