# 곤충 자동 사육 비전 AI 프로젝트 (갈색거저리 유충 모니터링 시스템)

갈색거저리 유충(밀웜) 사육장에서 촬영한 동영상을 업로드하면, AI가 이를 자동으로 분석하여 생육 상태를 모니터링해 주는 웹 시스템입니다.

시스템은 다음과 같은 과정을 자동으로 처리합니다.
1. 키프레임 추출
2. YOLO 기반 유충 객체 탐지
3. 탐지된 유충 이미지 크롭
4. ResNet-50 분류기로 정상/비정상 개체 분류
5. 결과 및 통계를 웹 대시보드로 시각화

## 주요 기능

- 유충 모니터링: 
  사육장 번호와 메모를 입력하여 동영상을 업로드하면, 시스템이 키프레임을 추출하고 분석 진행 상황을 알려줍니다.

- 객체 탐지 (YOLO):
  동영상 내의 유충 위치를 정확하게 찾아내고, 해당 영역을 잘라내어 정밀 분석을 준비합니다.

- 이상 개체 분류 (ResNet-50):
  각 유충이 건강한지, 혹은 질병이나 폐사 등의 이상이 있는지 판단하여 비정상 개체의 수와 비율을 계산합니다.

- 대시보드:
  업로드한 영상 목록과 분석 상태를 한눈에 볼 수 있으며, 분석 결과에 대한 요약 통계와 실제 이미지를 확인할 수 있습니다.

- 데이터 관리:
  MongoDB를 활용하여 영상 정보와 분석 결과, 사용자 데이터를 안전하게 관리합니다.

## 기술 스택

- Backend: Python 3.8+, Flask, PyTorch, YOLO, MongoDB (pymongo)
- Frontend: HTML/CSS/JavaScript, Jinja2 Template
- Infrastructure: Docker, Docker Compose (GPU 환경 지원)

## 프로젝트 구조

실제 폴더 구조가 아래와 다른 경우, 환경에 맞게 수정하여 사용하시면 됩니다.

```bash
project-root/
├─ app.py                 # 서버 핵심 코드
├─ requirements.txt       # 필요한 라이브러리 목록
├─ docker-compose.yml     # Docker 구성 파일
├─ Dockerfile             # 도커 이미지 빌드 설정
├─ ai/
│  ├─ pipeline.py         # AI 분석 파이프라인
│  ├─ models/             # 모델 관련 파일
│  └─ utils/              # 유틸리티 함수
├─ db/
│  └─ mongo.py            # DB 연결 설정
├─ templates/             # 웹 화면 템플릿
│  ├─ dashboard.html
│  ├─ upload.html
│  ├─ analysis.html
│  └─ admin_users.html
├─ static/
│  ├─ uploads/            # 동영상 저장소
│  ├─ frames/             # 키프레임 저장소
│  └─ crops/              # 크롭 이미지 저장소
└─ USAGE.md               # 상세 사용 매뉴얼
```

## 사전 준비 사항

GitHub 용량 제한으로 인해 모델 파일은 포함되어 있지 않습니다. 아래 두 파일을 별도로 준비하여 프로젝트 최상위 폴더(project-root)에 넣어주세요.

- YOLO 가중치 파일: yolo.pt
- ResNet 분류기 가중치 파일: best_resnet50_mealworm.pth

## 설치 및 실행 방법

### 방법 A. 로컬 환경에서 실행하기

1. 가상환경 설정 (권장)
   ```bash
   python -m venv venv
   # Windows
   .\venv\Scripts\activate
   # Mac/Linux
   source venv/bin/activate
   ```

2. 패키지 설치
   ```bash
   pip install -r requirements.txt
   ```

3. 환경 변수 설정
   프로젝트 루트에 .env 파일을 만들고 아래 내용을 작성합니다.
   ```env
   FLASK_ENV=development
   MONGO_URI=mongodb://localhost:27017
   MONGO_DB_NAME=insect_db
   UPLOAD_FOLDER=static/uploads
   DEVICE=cuda  # GPU가 없다면 cpu로 설정
   ```

4. 데이터베이스 실행
   로컬에 설치된 MongoDB를 실행합니다 (기본 포트 27017).

5. 서버 시작
   ```bash
   python app.py
   ```

6. 접속 확인
   브라우저에서 http://localhost:5000 으로 접속합니다.

### 방법 B. Docker로 간편하게 실행하기

1. 환경 변수 설정
   docker-compose.yml이 참조할 수 있도록 .env 파일을 설정합니다.
   ```env
   MONGO_INITDB_ROOT_USERNAME=root
   MONGO_INITDB_ROOT_PASSWORD=example
   MONGO_DB_NAME=insect_db
   DEVICE=cuda  # 또는 cpu
   ```

2. 컨테이너 실행
   ```bash
   docker compose up --build
   ```

3. 접속 확인
   마찬가지로 http://localhost:5000 으로 접속하여 확인합니다.

## 사용 방법

1. 업로드 (/upload): 사육장 정보를 입력하고 동영상을 올립니다.
2. 대시보드 (/dashboard): 분석 진행 상황을 실시간으로 확인합니다.
3. 분석 결과 (/analysis/영상ID): 비정상 개체 수, 위치, 실제 이미지를 상세하게 살펴봅니다.
4. 관리자 (/admin/users): 필요시 사용자나 데이터를 관리합니다.

## 주의 사항

- 데이터 보안: DB 관련 파일이나 대용량 모델 파일은 저장소에 직접 올리지 않도록 주의해 주세요.
- 실행 환경: GPU가 없는 환경에서는 DEVICE 설정을 cpu로 변경해야 오류가 발생하지 않습니다.

## 문의하기

프로젝트 사용 중 궁금한 점이 있으시면 언제든 연락 주세요.

- 개발자: 이도훈
- GitHub: https://github.com/sinadubu
