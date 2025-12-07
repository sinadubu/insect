// static/js/upload.js

// 1. DOM 요소 참조
const selectFileBtn = document.getElementById("selectFileBtn");
const fileInput = document.getElementById("videoFile");
const fileNameLabel = document.getElementById("selectedFileName");
const dropZone = document.getElementById("dropZone");
const uploadForm = document.getElementById("uploadForm");

// 폼 내부의 submit 버튼 참조 (업로드 중 비활성화를 위함)
const submitButton = uploadForm
  ? uploadForm.querySelector('button[type="submit"]')
  : null;

// 2. 이벤트 리스너 설정

// "파일 선택" 버튼 클릭 시 숨겨진 file input 트리거
if (selectFileBtn && fileInput) {
  selectFileBtn.addEventListener("click", () => {
    fileInput.click();
  });
}

// 파일 선택 변경 시 처리: 파일명/크기 표시 및 드롭존 스타일 업데이트
if (fileInput && fileNameLabel) {
  fileInput.addEventListener("change", () => {
    const file = fileInput.files[0];

    if (!file) {
      fileNameLabel.textContent = "선택된 파일이 없습니다.";

      // 파일 선택 취소 시 드롭존 스타일 초기화
      if (dropZone) {
        dropZone.classList.remove("border-primary", "bg-slate-100");
        dropZone.classList.add("border-slate-300");
      }
      return;
    }

    // 파일 크기(MB) 계산 및 파일명 표시
    const sizeMB = (file.size / (1024 * 1024)).toFixed(1);
    fileNameLabel.textContent = `선택된 파일: ${file.name} (${sizeMB} MB)`;

    // 파일 선택 시 드롭존 강조 스타일 적용
    if (dropZone) {
      dropZone.classList.remove("border-slate-300");
      dropZone.classList.add("border-primary", "bg-slate-100");
    }
  });
}

// 드래그 앤 드롭 기능 설정
if (dropZone && fileInput && fileNameLabel) {
  // 드래그 진입/오버 시 스타일 강조
  ["dragenter", "dragover"].forEach((eventName) => {
    dropZone.addEventListener(eventName, (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropZone.classList.add("border-primary", "bg-slate-100");
    });
  });

  // 드래그 이탈/드롭 시 기본 동작 방지
  ["dragleave", "drop"].forEach((eventName) => {
    dropZone.addEventListener(eventName, (e) => {
      e.preventDefault();
      e.stopPropagation();
      // 파일이 선택되지 않은 상태로 나갈 경우 스타일 복구
      if (fileInput.files.length === 0) {
        dropZone.classList.remove("border-primary", "bg-slate-100");
        dropZone.classList.add("border-slate-300");
      }
    });
  });

  // 파일 드롭 처리
  dropZone.addEventListener("drop", (e) => {
    const files = e.dataTransfer.files;
    if (files && files[0]) {
      // 드롭된 파일을 file input에 할당
      fileInput.files = files;

      const sizeMB = (files[0].size / (1024 * 1024)).toFixed(1);
      fileNameLabel.textContent = `선택된 파일: ${files[0].name} (${sizeMB} MB)`;

      // 드롭 성공 시 스타일 유지 (또는 강조)
      dropZone.classList.remove("border-slate-300");
      dropZone.classList.add("border-primary", "bg-slate-100");
    }
  });
}

// 3. 폼 제출 (업로드) 처리
if (uploadForm) {
  uploadForm.addEventListener("submit", async (e) => {
    e.preventDefault();

    const fileInput = document.getElementById("videoFile");
    const farmInput = document.getElementById("farmId");

    // 유효성 검사
    if (!fileInput.files[0]) {
      alert("먼저 업로드할 영상을 선택해 주세요.");
      return;
    }

    if (!farmInput.value.trim()) {
      alert("사육장 번호를 입력해 주세요.");
      return;
    }

    // 서버 전송을 위한 FormData 객체 생성
    const formData = new FormData();
    formData.append("video", fileInput.files[0]);
    formData.append("farm_id", farmInput.value.trim());

    // 중복 제출 방지: 제출 중에는 버튼 비활성화 및 스타일 변경
    if (submitButton) {
      submitButton.disabled = true;
      submitButton.classList.add("opacity-60", "cursor-not-allowed");
    }

    // 디버깅용 로그 출력
    console.log("업로드 요청 보냄", {
      file: fileInput.files[0].name,
      size: fileInput.files[0].size,
      farm_id: farmInput.value.trim(),
    });

    try {
      // 서버로 업로드 요청 전송 (POST /api/videos)
      const res = await fetch("/api/videos", {
        method: "POST",
        body: formData,
      });

      // 응답 본문 텍스트 읽기 (디버깅용)
      let bodyText = "";
      try {
        bodyText = await res.text();
      } catch (e) {
        console.warn("응답 body 읽기 실패", e);
      }
      console.log("업로드 응답 상태:", res.status, "본문:", bodyText);

      if (!res.ok) {
        alert(`업로드/분석 중 오류가 발생했습니다. (status: ${res.status})`);
        // 에러 발생 시 버튼 활성화 상태 복구
        if (submitButton) {
          submitButton.disabled = false;
          submitButton.classList.remove("opacity-60", "cursor-not-allowed");
        }
        return;
      }

      // 성공 시 분석 결과 페이지로 이동
      const data = JSON.parse(bodyText);
      alert("분석이 시작되었습니다!");
      window.location.href = `/analysis/${data.video_id}`;
    } catch (err) {
      console.error("fetch 통신 에러:", err);
      alert("서버와 통신 중 오류가 발생했습니다.");
      // 네트워크 에러 발생 시 버튼 활성화 상태 복구
      if (submitButton) {
        submitButton.disabled = false;
        submitButton.classList.remove("opacity-60", "cursor-not-allowed");
      }
    }
  });
}
