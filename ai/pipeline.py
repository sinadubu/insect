import os
import time
from typing import List, Dict, Any

import cv2
import torch
import torch.nn as nn
from torchvision import models, transforms
from PIL import Image
from ultralytics import YOLO

from db.mongo import get_db


# ==============================
# 0. 전역 설정 및 경로 정의
# ==============================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))  # ai/ 폴더 절대 경로
PROJECT_ROOT = os.path.dirname(BASE_DIR)               # 프로젝트 최상위 경로

# 모델 가중치 파일 경로 설정
YOLO_WEIGHTS = os.path.join(PROJECT_ROOT, "yolo.pt")  
RESNET_WEIGHTS = os.path.join(PROJECT_ROOT, "best_resnet50_mealworm.pth")

# GPU 사용 가능 여부 확인 및 디바이스 설정
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(f"[AI] 분석에 사용할 장치: {DEVICE}")

# ==============================
# 1. ResNet 분류기 모델 로드
# ==============================

# 모델 출력 인덱스와 실제 레이블 매핑
# 학습 시 사용된 ImageFolder의 클래스 순서에 맞춰야 합니다.
IDX_TO_LABEL = {
    0: "abnormal",  # 비정상 (질병, 폐사 등)
    1: "normal",    # 정상
}

# ResNet50 모델 구조 불러오기 (사전 학습된 가중치는 사용하지 않음)
resnet_model = models.resnet50(weights=None)
num_ftrs = resnet_model.fc.in_features
# 마지막 완전 연결 계층(FC)을 우리 데이터셋의 클래스 개수(2개)에 맞게 수정
resnet_model.fc = nn.Linear(num_ftrs, len(IDX_TO_LABEL))

# 학습된 ResNet 가중치 파일 로드
if not os.path.exists(RESNET_WEIGHTS):
    print(f"[경고] ResNet 가중치 파일을 찾을 수 없습니다: {RESNET_WEIGHTS}")
else:
    state = torch.load(RESNET_WEIGHTS, map_location=DEVICE)
    resnet_model.load_state_dict(state)
    print(f"[AI] ResNet 모델 가중치를 성공적으로 불러왔습니다: {RESNET_WEIGHTS}")

# 모델을 설정된 디바이스(GPU/CPU)로 이동하고 평가(Inference) 모드로 전환
resnet_model.to(DEVICE)
resnet_model.eval()

# ResNet 입력 이미지를 위한 전처리 파이프라인
# 이미지 크기 변경, 텐서 변환, 정규화 수행
RESNET_TRANSFORM = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406],
                         std=[0.229, 0.224, 0.225]),
])

# ==============================
# 2. YOLO 모델 로드
# ==============================

# YOLO 객체 감지 모델 가중치 로드
if not os.path.exists(YOLO_WEIGHTS):
    print(f"[경고] YOLO 가중치 파일을 찾을 수 없습니다: {YOLO_WEIGHTS}")
yolo_model = YOLO(YOLO_WEIGHTS)
print(f"[AI] YOLO 모델을 성공적으로 불러왔습니다: {YOLO_WEIGHTS}")


# ==============================
# 3. 유틸리티 함수: 이미지 크롭 분류
# ==============================

def classify_crop_bgr(crop_bgr) -> Dict[str, Any]:
    """
    OpenCV 형태(BGR)의 크롭된 이미지를 입력받아 ResNet으로 정상/비정상 여부를 분류합니다.

    Args:
        crop_bgr (numpy.ndarray): OpenCV로 읽은 BGR 이미지 배열

    Returns:
        dict: 예측 인덱스(pred_idx), 레이블(label), 신뢰도(confidence)를 포함한 딕셔너리
    """
    # OpenCV(BGR) 이미지를 PIL(RGB) 이미지로 변환
    crop_rgb = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2RGB)
    pil_img = Image.fromarray(crop_rgb)

    # 전처리 및 배치 차원 추가 (H,W,C) -> (1,C,H,W)
    tensor = RESNET_TRANSFORM(pil_img).unsqueeze(0).to(DEVICE)

    with torch.no_grad():
        # 모델 추론
        logits = resnet_model(tensor)
        probs = torch.softmax(logits, dim=1)[0]
        
        # 가장 높은 확률을 가진 클래스 선택
        pred_idx = int(torch.argmax(probs))
        pred_label = IDX_TO_LABEL.get(pred_idx, str(pred_idx))
        confidence = float(probs[pred_idx])

    return {
        "pred_idx": pred_idx,
        "label": pred_label,
        "confidence": confidence,
    }


# ==============================
# 4. 메인 분석 파이프라인
# ==============================

def run_analysis(video_id: str, file_path: str) -> None:
    """
    업로드된 비디오 파일을 분석하여 결과를 데이터베이스에 저장합니다.
    
    동작 과정:
    1) 비디오에서 일정 간격으로 프레임을 추출합니다.
    2) YOLO 모델을 사용하여 곤충(객체)의 영역(Bounding Box)을 감지합니다.
    3) 감지된 각 영역을 잘라내어(Crop), ResNet 분류기를 통해 정상/비정상을 판별합니다.
    4) 비정상 객체가 발견된 프레임에는 박스를 그려서 '키프레임' 이미지로 저장합니다.
    5) 전체 분석 결과(통계, 상태, 키프레임 정보 등)를 MongoDB에 업데이트합니다.

    Args:
        video_id (str): 데이터베이스 상의 비디오 문서 ID
        file_path (str): 분석할 비디오 파일의 절대 경로
    """
    db = get_db()

    print(f"[AI] 비디오 분석 시작: {video_id} (경로: {file_path})")

    # 분석 시작 상태로 업데이트
    db.videos.update_one(
        {"_id": video_id},
        {"$set": {"status": "processing"}},
    )

    # 파일 존재 확인
    if not os.path.exists(file_path):
        print(f"[오류] 비디오 파일을 찾을 수 없습니다: {file_path}")
        db.videos.update_one(
            {"_id": video_id},
            {"$set": {"status": "error", "analysis_error": "video file not found"}},
        )
        return

    # OpenCV로 비디오 열기
    cap = cv2.VideoCapture(file_path)
    if not cap.isOpened():
        print(f"[오류] 비디오를 열 수 없습니다: {file_path}")
        db.videos.update_one(
            {"_id": video_id},
            {"$set": {"status": "error", "analysis_error": "cannot open video"}},
        )
        return

    # 프레임 속도(FPS) 확인 및 샘플링 간격 설정
    fps = cap.get(cv2.CAP_PROP_FPS)
    if fps <= 0:
        fps = 30.0  # FPS 정보를 읽지 못할 경우 기본값 사용
    
    # 3초마다 한 프레임씩 샘플링하여 분석 (속도 최적화)
    frame_interval = int(fps * 3)

    total_detections = 0
    abnormal_count = 0
    keyframes: List[Dict[str, Any]] = []

    # 키프레임 저장용 디렉토리 생성
    keyframe_dir = os.path.join("static", "keyframes")
    os.makedirs(keyframe_dir, exist_ok=True)

    frame_idx = 0
    sampled_idx = 0

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break  # 비디오 끝 도달

            # 샘플링 간격에 맞지 않는 프레임은 건너뜀
            if frame_interval > 1 and (frame_idx % frame_interval != 0):
                frame_idx += 1
                continue

            # 현재 프레임의 시간(초) 계산
            t_sec = frame_idx / fps

            # 시각화(박스 그리기)용 프레임 복사
            vis_frame = frame.copy()

            # 1단계: YOLO 객체 감지 수행
            results = yolo_model(frame, conf=0.25, verbose=False)
            if not results:
                frame_idx += 1
                continue

            result = results[0]
            boxes = result.boxes
            if boxes is None or len(boxes) == 0:
                frame_idx += 1
                continue

            frame_has_abnormal = False
            detections_for_frame: List[Dict[str, Any]] = []

            # 감지된 각 객체(박스)에 대해 처리
            for box in boxes:
                # 좌표 추출 및 정수 변환
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                x1, y1, x2, y2 = map(int, (x1, y1, x2, y2))

                # 프레임 경계를 벗어나지 않도록 좌표 클리핑
                h, w, _ = frame.shape
                x1 = max(0, min(w - 1, x1))
                x2 = max(0, min(w, x2))
                y1 = max(0, min(h - 1, y1))
                y2 = max(0, min(h, y2))
                
                # 유효하지 않은 박스는 무시
                if x2 <= x1 or y2 <= y1:
                    continue

                # 객체 영역 자르기 (Crop)
                crop = frame[y1:y2, x1:x2]
                if crop.size == 0:
                    continue

                # 2단계: ResNet으로 정상/비정상 분류
                cls_result = classify_crop_bgr(crop)
                total_detections += 1

                det = {
                    "x1": x1,
                    "y1": y1,
                    "x2": x2,
                    "y2": y2,
                    "label": cls_result["label"],
                    "confidence": cls_result["confidence"],
                }
                detections_for_frame.append(det)

                if cls_result["label"] == "abnormal":
                    abnormal_count += 1
                    frame_has_abnormal = True

            # 비정상 객체가 하나라도 발견되면 해당 프레임을 키프레임으로 저장
            if frame_has_abnormal and detections_for_frame:
                sampled_idx += 1
                keyframe_filename = f"{video_id}_kf{sampled_idx}_t{int(t_sec)}.jpg"
                keyframe_path = os.path.join(keyframe_dir, keyframe_filename)

                # 결과 시각화: 감지된 모든 객체에 대해 바운딩 박스와 라벨 그리기
                for det in detections_for_frame:
                    if det["label"] == "abnormal":
                        color = (0, 0, 255)   # 비정상: 빨강 (Red)
                    else:
                        color = (0, 255, 0)   # 정상: 초록 (Green)

                    x1, y1, x2, y2 = det["x1"], det["y1"], det["x2"], det["y2"]
                    cv2.rectangle(vis_frame, (x1, y1), (x2, y2), color, 2)

                    text = f'{det["label"]} {det["confidence"]:.2f}'
                    # 라벨 텍스트 그리기 (박스 위쪽)
                    cv2.putText(
                        vis_frame,
                        text,
                        (x1, max(0, y1 - 5)),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.4,
                        color,
                        1,
                        cv2.LINE_AA,
                    )

                # 시각화된(박스가 그려진) 이미지를 파일로 저장
                cv2.imwrite(keyframe_path, vis_frame)

                # 키프레임 정보를 리스트에 추가
                keyframes.append({
                    "time": round(t_sec, 2),
                    "status": "abnormal",  # 비정상 프레임임을 표시
                    "frame_image_url": f"/static/keyframes/{keyframe_filename}",
                    "detections": detections_for_frame,
                })

            frame_idx += 1

    finally:
        # 비디오 리소스 해제
        cap.release()

    # 최종 통계 계산
    normal_count = max(0, total_detections - abnormal_count)
    # 비정상 개체가 하나라도 있으면 전체 영상을 'abnormal'로 판정
    final_label = "abnormal" if abnormal_count > 0 else "normal"

    summary = {
        "total_count": total_detections,
        "normal_count": normal_count,
        "abnormal_count": abnormal_count,
    }

    # DB에 최종 분석 결과 업데이트
    db.videos.update_one(
        {"_id": video_id},
        {
            "$set": {
                "status": "done",
                "final": final_label,
                "summary": summary,
                "keyframes": keyframes,
            }
        },
    )

    print(f"[AI] 비디오 분석 완료: {video_id}")
    print(f"[AI] 결과 요약: {summary}, 최종 판정: {final_label}, 생성된 키프레임 수: {len(keyframes)}")
