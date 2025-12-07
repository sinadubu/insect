// static/js/dashboard.js

document.addEventListener("DOMContentLoaded", () => {
    // 1. 주요 DOM 요소 참조
    const listContainer = document.getElementById("video-list");

    // 상단 통계 카드 요소들 (총 영상 수, 완료됨, 정상, 비정상)
    const totalEl = document.getElementById("stat-total-videos");
    const doneEl = document.getElementById("stat-done-videos");
    const normalEl = document.getElementById("stat-normal-videos");
    const abnormalEl = document.getElementById("stat-abnormal-videos");

    // 진행률 원형 게이지 요소
    const progressPercentEl = document.getElementById("progress-percent");
    const progressRingEl = document.getElementById("progress-ring");

    // 2. 유틸리티 함수들

    // 분석 상태에 따른 텍스트 및 배지 생상 정보를 반환하는 함수
    function getStatusInfo(status, finalStatus) {
        if (status === "done") {
            if (finalStatus === "normal") {
                return {
                    label: "정상",
                    badgeClass: "bg-normal/90 text-white",
                };
            }
            if (finalStatus === "abnormal") {
                return {
                    label: "비정상",
                    badgeClass: "bg-abnormal/90 text-white",
                };
            }
            return {
                label: "완료",
                badgeClass: "bg-primary/90 text-white",
            };
        }

        if (status === "processing") {
            return {
                label: "분석 중",
                badgeClass: "bg-processing/90 text-white",
            };
        }

        if (status === "uploaded") {
            return {
                label: "대기 중",
                badgeClass: "bg-slate-500/80 text-white",
            };
        }

        return {
            label: status || "알 수 없음",
            badgeClass: "bg-slate-500/70 text-white",
        };
    }

    // 날짜 포맷팅 함수: ISO 문자열을 'YYYY-MM-DD HH:MM' 형식으로 변환
    function formatDate(iso) {
        if (!iso) return "-";
        const d = new Date(iso);
        if (Number.isNaN(d.getTime())) return "-";

        const yyyy = d.getFullYear();
        const mm = String(d.getMonth() + 1).padStart(2, "0");
        const dd = String(d.getDate()).padStart(2, "0");
        const hh = String(d.getHours()).padStart(2, "0");
        const mi = String(d.getMinutes()).padStart(2, "0");

        return `${yyyy}-${mm}-${dd} ${hh}:${mi}`;
    }

    // 3. 데이터 로딩 및 UI 업데이트 함수들

    // 대시보드 상단 통계 및 진행률 데이터 로드
    async function loadDashboardStats() {
        try {
            const res = await fetch("/api/dashboard");
            if (!res.ok) {
                throw new Error("Failed to fetch /api/dashboard");
            }

            const data = await res.json();
            const stats = data.stats || {};
            const total = stats.total ?? 0;
            const done = stats.done ?? 0;
            const normal = stats.normal ?? 0;
            const abnormal = stats.abnormal ?? 0;

            // 통계 숫자 업데이트
            if (totalEl) totalEl.textContent = total;
            if (doneEl) doneEl.textContent = done;
            if (normalEl) normalEl.textContent = normal;
            if (abnormalEl) abnormalEl.textContent = abnormal;

            // 진행률 계산 (전체 영상 중 분석 완료된 비율)
            let percent = 0;
            if (total > 0) {
                percent = Math.round((done / total) * 100);
            }

            // 퍼센트 텍스트 업데이트
            if (progressPercentEl) {
                progressPercentEl.textContent = `${percent}%`;
            }

            // 원형 게이지(SVG stroke-dasharray) 업데이트
            if (progressRingEl) {
                // percent값 범위를 0~100으로 제한
                const p = Math.max(0, Math.min(100, percent));

                // stroke-dasharray 설정: "채워질 길이, 전체 길이"
                // 여기서는 전체 길이를 100으로 가정하고 비율만큼 채움
                progressRingEl.setAttribute("stroke-dasharray", `${p}, 100`);

                // 100%에 근접했을 때 시각적 완성도를 위해 미세 조정
                if (p >= 99) {
                    progressRingEl.setAttribute("stroke-dasharray", "100, 100");
                    progressRingEl.setAttribute("stroke-dashoffset", "0");
                } else {
                    // 시작 지점 조정을 위한 오프셋 (기존 디자인 유지)
                    progressRingEl.setAttribute("stroke-dashoffset", "-17");
                }
            }
        } catch (err) {
            console.error("대시보드 통계 로딩 실패:", err);
        }
    }

    // 최근 영상 목록 로드 및 렌더링
    async function loadVideos() {
        if (!listContainer) return;

        try {
            const res = await fetch("/api/videos/list");
            if (!res.ok) {
                throw new Error("Failed to fetch /api/videos/list");
            }

            const data = await res.json();
            const items = data.items || [];

            listContainer.innerHTML = "";

            // 목록이 비어있는 경우 안내 메시지 표시
            if (items.length === 0) {
                const empty = document.createElement("div");
                empty.className =
                    "flex items-center justify-center p-3 rounded-lg bg-white dark:bg-card-dark text-xs text-slate-600 dark:text-slate-300";
                empty.textContent = "아직 업로드된 영상이 없습니다.";
                listContainer.appendChild(empty);
                return;
            }

            // 영상 아이템 카드 생성 및 추가
            items.forEach((video) => {
                const status = video.status;
                const finalStatus = video.final;
                const { label, badgeClass } = getStatusInfo(status, finalStatus);

                const createdAt = formatDate(video.created_at);

                // 화면에 표시할 파일명 결정 (원본 파일명 우선)
                const displayName =
                    video.original_filename || video.filename || "(이름 없음)";

                const card = document.createElement("div");
                card.className =
                    "flex items-center gap-4 p-3 rounded-lg bg-white dark:bg-card-dark cursor-pointer hover:bg-slate-50 dark:hover:bg-card-dark/80 transition-colors";

                // 카드 클릭 시 해당 영상의 상세 분석 페이지로 이동
                card.addEventListener("click", () => {
                    if (video.video_id) {
                        window.location.href = `/analysis/${video.video_id}`;
                    }
                });

                // 카드 내부 HTML 구조 구성
                card.innerHTML = `
          <div class="flex items-center justify-center w-14 h-14 rounded-md bg-primary/10 text-primary">
            <span class="material-symbols-outlined text-2xl">movie</span>
          </div>

          <div class="flex-1 min-w-0">
            <p class="text-black dark:text-white font-medium truncate">
              ${displayName}
            </p>
            <p class="text-black/60 dark:text-white/60 text-xs mt-0.5">
              사육장: <span class="font-semibold">${video.farm_id || "-"}</span>
            </p>
            <p class="text-black/50 dark:text-white/50 text-[11px] mt-0.5">
              업로드: ${createdAt}
            </p>
          </div>

          <div class="px-3 py-1 text-sm font-medium rounded-full ${badgeClass}">
            <p>${label}</p>
          </div>
        `;

                listContainer.appendChild(card);
            });
        } catch (err) {
            console.error(err);
            listContainer.innerHTML = "";

            // 에러 발생 시 안내 메시지 표시
            const errorBox = document.createElement("div");
            errorBox.className =
                "flex items-center justify-center p-3 rounded-lg bg-red-50 dark:bg-red-900/40 text-xs text-red-600 dark:text-red-300";
            errorBox.textContent =
                "영상 목록을 불러오는 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.";
            listContainer.appendChild(errorBox);
        }
    }

    // 4. 초기 실행
    loadDashboardStats();
    loadVideos();
});
