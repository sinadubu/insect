# 곤충 자동 사육 비전 AI 프로젝트 (갈색거저리 유충 모니터링 시스템)

갈색거저리 유충(밀웜) 사육장에서 촬영한 동영상을 업로드하면, AI가 이를 자동으로 분석하여 생육 상태를 모니터링해 주는 웹 시스템입니다.

시스템은 다음 과정을 자동으로 처리합니다.
1. 키프레임 추출
2. YOLO 기반 유충 객체 탐지
3. 탐지된 유충 이미지 크롭
4. ResNet-50 분류기로 정상/비정상 개체 분류
5. 결과 및 통계를 웹 대시보드로 시각화

## 데모
- 외부 데모 접속 링크는 Issues의 `Live Demo Link (Cloudflare Tunnel)` 글에서 최신 URL을 확인하세요.

- **시연 영상**: 레포지토리 루트의 `demo.mp4`는 시스템 작동 모습을 녹화한 단순 시연용 영상입니다. 다운로드하여 플레이어로 확인해 보세요.
- **모델 가중치**: 레포지토리 루트의 `yolo.pt`, `best_resnet50_mealworm.pth`가 포함되어 있습니다.
- **테스트용 영상**: `비정상이 있는 영상.mp4`, `정상만 있는 영상.mp4`
  - *`demo.mp4`는 단순 시연용입니다. 직접 업로드할 때는 위 테스트용 영상을 사용해 주세요.*
  - 본 레포는 대용량 파일을 Git LFS로 관리합니다. 클론 후 반드시 `git lfs pull`을 실행하세요.

## 주요 기능

- 유충 모니터링
  - 사육장 번호와 메모를 입력해 동영상을 업로드하면 키프레임 추출 및 분석을 수행합니다.
- 객체 탐지 (YOLO)
  - 동영상 내 유충 위치를 탐지하고, 해당 영역을 크롭하여 분류 입력으로 사용합니다.
- 이상 개체 분류 (ResNet-50)
  - 크롭된 유충 이미지를 정상/비정상으로 분류하고 비정상 개체 수/비율을 계산합니다.
- 대시보드
  - 업로드한 영상 목록/분석 상태/요약 통계/이미지 결과를 확인할 수 있습니다.
- 데이터 관리
  - MongoDB에 영상 메타데이터, 분석 결과, 사용자 정보를 저장합니다.

## 기술 스택

- Backend: Python 3.8+, Flask, PyTorch, Ultralytics YOLO, MongoDB (pymongo)
- Frontend: HTML/CSS/JavaScript, Jinja2 Template
- Infrastructure: Docker, Docker Compose (GPU 환경 지원)

## 프로젝트 구조 (요약)

```bash
project-root/
├─ app.py
├─ ai/
├─ db/
├─ templates/
├─ static/
├─ script/
├─ docker-compose.yml
├─ Dockerfile
├─ requirements.txt
├─ yolo.pt
├─ best_resnet50_mealworm.pth
├─ demo.mp4
├─ 비정상이 있는 영상.mp4
└─ 정상만 있는 영상.mp4
