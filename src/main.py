from video import VideoRender
import cv2

def main():
    reader = VideoRender("./data/input/test_trespass.mp4")

    fps = reader.get_fps()
    skip_frame = int(fps * 5)
    playing = True

    while True:

        if playing:
            ret, frame = reader.read()

            if not ret:
                break

            display_frame = cv2.resize(
                frame, 
                None, 
                fx=0.333, 
                fy=0.333
            )

            cv2.imshow("Frame", display_frame)

        key = cv2.waitKey(30) & 0xFF

        if key == ord(" "): # 스페이스바
            playing = not playing

        elif key == 81: # 방향키 왼쪽
            current = reader.get_current_frame()
            reader.seek_frame(max(0, current - skip_frame))

        elif key == 83: # 방향키 오른쪽
            current = reader.get_current_frame()
            reader.seek_frame(current + skip_frame)

        elif key == ord("q"): # q 키
            break

    reader.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()