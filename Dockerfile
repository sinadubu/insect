# Dockerfile (GPU 지원 환경)

# 1. Python 베이스 이미지 선택
#    가볍고 안정적인 3.11-slim 버전을 사용합니다.
FROM python:3.11-slim

# 2. 기본 환경 변수 설정
#    __pycache__ 디렉토리 생성 방지 (컨테이너 내 불필요한 파일 생성 최소화)
ENV PYTHONDONTWRITEBYTECODE=1
#    파이썬 로그가 버퍼링 없이 즉시 출력되도록 설정 (디버깅 용이)
ENV PYTHONUNBUFFERED=1

# 3. 작업 디렉토리 설정
#    컨테이너 내부의 모든 명령어가 실행될 기본 위치입니다.
WORKDIR /app

# 4. 필수 시스템 패키지 설치
#    OpenCV 및 멀티미디어 처리에 필요한 라이브러리(ffmpeg, libgl1 등)를 설치합니다.
#    설치 후 캐시를 삭제하여 이미지 크기를 줄입니다.
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    ffmpeg \
    libgl1 \
    libsm6 \
    libxext6 \
    && rm -rf /var/lib/apt/lists/*

# 5-1. PyTorch (GPU 버전) 우선 설치
#    YOLOv8 등 딥러닝 모델 구동을 위해 CUDA 12.1 지원 버전을 특정하여 설치합니다.
#    --index-url 옵션으로 PyTorch 공식 저장소에서 다운로드 받습니다.
RUN pip install --upgrade pip && \
    pip install --no-cache-dir \
    --index-url https://download.pytorch.org/whl/cu121 \
    torch==2.5.1 torchvision==0.20.1 torchaudio==2.5.1

# 5-2. 프로젝트 의존성 패키지 설치
#    requirements.txt에 명시된 나머지 라이브러리(Flask, pymongo 등)를 설치합니다.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 6. 소스 코드 복사
#    현재 디렉토리의 모든 파일을 컨테이너의 작업 디렉토리(/app)로 복사합니다.
COPY . .

# 7. 정적 파일 저장소 생성
#    영상 업로드 및 키프레임 저장을 위한 폴더를 미리 생성합니다.
RUN mkdir -p static/uploads static/keyframes

# 8. Flask 애플리케이션 환경 변수 설정
ENV FLASK_APP=app.py
ENV FLASK_RUN_HOST=0.0.0.0

# 컨테이너가 5000번 포트를 사용함을 명시
EXPOSE 5000

# 9. 서버 실행 명령어
#    프로덕션 환경에 적합한 Gunicorn WSGI 서버를 사용하여 앱을 구동합니다.
CMD ["gunicorn", "-b", "0.0.0.0:5000", "app:app"]
