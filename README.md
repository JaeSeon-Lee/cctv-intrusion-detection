# CCTV Intrusion Detection

CCTV 영상에서 사용자가 지정한 위험지역을 침입하는 움직이는 객체를 탐지하고
침입 사건을 자동으로 기록하는 Computer Vision 프로젝트.

## Project Goal

- CCTV 영상 입력
- 사용자가 Polygon 형태의 위험지역 지정
- 움직이는 객체 검출
- 객체와 위험지역의 공간적 겹침 판단
- N프레임 이상 지속 시 침입 확정
- 침입 영상 자동 저장
- 침입 이벤트 로그 저장

## Pipeline

CCTV Video
→ Motion Detection
→ Object Region Detection
→ Danger Zone Intersection
→ Temporal Filtering
→ Intrusion Event
→ Recording / Logging

## Tech Stack

- Python
- OpenCV
- NumPy
- Pandas
- Matplotlib
