#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI-Hub 갈색거저리 데이터셋의 주석(JSON)을 YOLO 라벨 형식(.txt)으로 변환하는 스크립트입니다.

기본 동작:
1. JSON 파일에서 이미지 해상도와 바운딩 박스(BOX) 정보를 읽어옵니다.
2. YOLO 형식에 맞게 좌표를 정규화합니다 (x_center, y_center, width, height).
3. POLYGON 등 BOX가 아닌 어노테이션은 제외합니다.
4. 클래스는 단일 클래스(0) 또는 객체 상태(object_status)에 따라 매핑하여 분류할 수 있습니다.

사용 방법:
    # 1. 단일 클래스로 변환 (모든 객체를 Class 0으로 처리)
    python convert_aihub_to_yolo.py \\
        --json-dir ./data/labels_json \\
        --out-labels ./data/labels_yolo \\
        --class-mode single

    # 2. 상태별 클래스 분리 (정상: 0, 이상: 1 등)
    python convert_aihub_to_yolo.py \\
        --json-dir ./data/labels_json \\
        --out-labels ./data/labels_yolo \\
        --class-mode status --status-map "NM:0,AB:1"
"""
import argparse
import json
import sys
from pathlib import Path

def parse_status_map(s: str):
    """
    문자열 형태의 상태 매핑을 딕셔너리로 변환합니다.
    입력 예시: 'NM:0,AB:1,NG:1'
    출력 예시: {'NM': 0, 'AB': 1, 'NG': 1}
    """
    mapping = {}
    if not s:
        return mapping
    for pair in s.split(","):
        pair = pair.strip()
        if not pair:
            continue
        if ":" not in pair:
            raise ValueError(f"잘못된 status-map 형식입니다: {pair}. '상태:ID' 형태로 입력해주세요.")
        k, v = pair.split(":", 1)
        k = k.strip()
        v = v.strip()
        if not v.isdigit():
            raise ValueError(f"status-map의 클래스 ID는 정수여야 합니다: {pair}")
        mapping[k] = int(v)
    return mapping

def ensure_dir(p: Path):
    """디렉토리가 없으면 생성합니다 (상위 디렉토리 포함)."""
    p.mkdir(parents=True, exist_ok=True)

def main():
    # 명령줄 인자 설정
    ap = argparse.ArgumentParser(description="AI-Hub JSON -> YOLO 라벨 변환기 (BOX만 사용)")
    ap.add_argument("--json-dir", type=Path, required=True, help="읽어올 주석 JSON 파일들이 있는 폴더 경로")
    ap.add_argument("--out-labels", type=Path, required=True, help="생성된 YOLO 라벨(.txt) 파일을 저장할 폴더 경로")
    ap.add_argument("--class-mode", choices=["single", "status"], default="single",
                    help="클래스 분류 모드 (single: 단일 클래스(0), status: 상태값 기반 다중 클래스)")
    ap.add_argument("--status-map", type=str, default="NM:0,AB:1",
                    help="class-mode가 'status'일 때 사용할 매핑 정보 (기본값: 'NM:0,AB:1')")
    ap.add_argument("--write-classes", action="store_true",
                    help="선택 시, out-labels 상위 폴더에 classes.txt 파일을 함께 생성합니다")
    args = ap.parse_args()

    json_dir: Path = args.json_dir
    out_labels: Path = args.out_labels
    class_mode: str = args.class_mode
    status_map_str: str = args.status_map

    # 출력 디렉토리 생성
    ensure_dir(out_labels)

    # 상태 기반 매핑 정보 파싱 (다중 클래스 모드일 때만)
    status_to_id = parse_status_map(status_map_str) if class_mode == "status" else {}

    converted = 0
    skipped = 0
    warnings = 0

    # JSON 파일 순회
    for jf in sorted(json_dir.glob("*.json")):
        try:
            with jf.open("r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            print(f"[오류] JSON 파일을 읽을 수 없습니다: {jf} -> {e}", file=sys.stderr)
            skipped += 1
            continue

        # 이미지 메타데이터 파싱 (해상도, 파일명)
        try:
            img_w = float(data["info"]["resolution"]["width"])
            img_h = float(data["info"]["resolution"]["height"])
            img_name = data["info"]["filename"]
        except Exception as e:
            print(f"[오류] 필수 메타데이터 파싱 실패: {jf} -> {e}", file=sys.stderr)
            skipped += 1
            continue

        if img_w <= 0 or img_h <= 0:
            print(f"[경고] 유효하지 않은 이미지 크기입니다: {jf} (w={img_w}, h={img_h})", file=sys.stderr)
            warnings += 1
            skipped += 1
            continue

        # 어노테이션 정보 처리 (BOX 타입만)
        anns = data.get("annotation", [])
        yolo_lines = []
        for ann in anns:
            if ann.get("annotation_type") != "BOX":
                # BOX가 아닌 타입(예: POLYGON)은 건너뜁니다
                continue
            
            # 좌표 정보 추출
            pts = ann.get("points", {})
            try:
                x = float(pts["x"])
                y = float(pts["y"])
                w = float(pts["width"])
                h = float(pts["height"])
            except Exception:
                warnings += 1
                continue

            if w <= 0 or h <= 0:
                warnings += 1
                continue

            # YOLO 형식으로 좌표 정규화 (0~1 사이 값)
            # YOLO 포맷: <class_id> <x_center> <y_center> <width> <height>
            x_center = (x + w / 2.0) / img_w
            y_center = (y + h / 2.0) / img_h
            w_norm = w / img_w
            h_norm = h / img_h

            # 값을 0.0과 1.0 사이로 클리핑하여 오차 방지
            def clip01(v): return max(0.0, min(1.0, v))
            x_center = clip01(x_center)
            y_center = clip01(y_center)
            w_norm = clip01(w_norm)
            h_norm = clip01(h_norm)

            # 클래스 ID 결정
            if class_mode == "single":
                class_id = 0
            else:
                status = (ann.get("object_status") or "").strip()
                if status not in status_to_id:
                    # 매핑 정보에 없는 상태값은 무시
                    warnings += 1
                    continue
                class_id = status_to_id[status]

            yolo_lines.append(f"{class_id} {x_center:.6f} {y_center:.6f} {w_norm:.6f} {h_norm:.6f}")

        # 변환된 라벨 파일 저장 (.txt)
        stem = Path(img_name).stem
        out_file = out_labels / f"{stem}.txt"
        
        # 유효한 라벨이 있는 경우에만 파일 생성
        if yolo_lines:
            out_file.write_text("\n".join(yolo_lines), encoding="utf-8")
            converted += 1
        else:
            # 라벨이 하나도 없는 빈 파일은 생성하지 않음
            warnings += 1

    print(f"[완료] 총 변환됨: {converted}개, 건너뜀: {skipped}개, 경고: {warnings}건")

    # (선택 사항) classes.txt 파일 생성
    if args.write_classes:
        cls_path = out_labels.parent / "classes.txt"
        if class_mode == "single":
            cls_path.write_text("갈색거저리\n", encoding="utf-8")
        else:
            # 상태 매핑 정보(ID 순서)대로 클래스 이름 기록
            inv = {v: k for k, v in status_to_id.items()}
            max_id = max(inv.keys()) if inv else -1
            lines = []
            for i in range(max_id + 1):
                label = inv.get(i, f"cls_{i}")
                lines.append(label)
            cls_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"[정보] classes.txt 파일이 작성되었습니다: {cls_path}")

if __name__ == "__main__":
    main()
