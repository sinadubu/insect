// static/js/analysis.js

document.addEventListener('DOMContentLoaded', () => {
    // 1. 영상 ID 확인
    // HTML의 body 태그에 있는 data-video-id 속성에서 ID를 가져옵니다.
    const videoId = document.body.dataset.videoId;
    if (!videoId) {
        console.error('페이지에서 비디오 ID를 찾을 수 없습니다.');
        return;
    }

    // 2. 주요 DOM 요소 참조
    const backButton = document.getElementById('back-button');
    const deleteButton = document.getElementById('delete-button');

    const filenameEl = document.getElementById('video-filename');
    const videoIdEl = document.getElementById('video-id');
    const farmIdEl = document.getElementById('farm-id');
    const statusBadge = document.getElementById('video-status-badge');
    const statusText = document.getElementById('video-status-text');
    const keyframesContainer = document.getElementById('keyframes-container');

    // 업로드 시각 및 영상 길이 표시 요소
    const createdAtEl = document.getElementById('video-created-at');
    const durationEl = document.getElementById('video-duration');

    // 3. 버튼 이벤트 핸들러 설정

    // 뒤로 가기 버튼: 브라우저 히스토리가 있으면 뒤로, 없으면 대시보드로 이동
    if (backButton) {
        backButton.addEventListener('click', () => {
            if (window.history.length > 1) {
                window.history.back();
            } else {
                window.location.href = '/dashboard';
            }
        });
    }

    // 분석 결과 삭제 버튼
    if (deleteButton) {
        deleteButton.addEventListener('click', async () => {
            const ok = window.confirm(
                '정말로 이 분석 결과를 삭제하시겠습니까?\n삭제 후에는 복구할 수 없습니다.'
            );
            if (!ok) return;

            try {
                // 삭제 API 요청 전송
                const res = await fetch(`/api/videos/${videoId}`, {
                    method: 'DELETE',
                });

                if (!res.ok) {
                    let msg = '삭제 중 오류가 발생했습니다.';
                    try {
                        const data = await res.json();
                        if (data && data.error) msg = data.error;
                    } catch (_) { }
                    alert(msg);
                    return;
                }

                alert('분석 결과가 삭제되었습니다.');
                window.location.href = '/dashboard';
            } catch (err) {
                console.error(err);
                alert('서버와 통신 중 오류가 발생했습니다.');
            }
        });
    }

    // 4. UI 업데이트 함수들

    // 분석 상태에 따라 상단 뱃지와 설명 텍스트 업데이트
    function applyStatus(video) {
        if (!statusBadge || !statusText) return;

        let statusColorClass = 'bg-gray-500/20 text-gray-400';
        let statusLabel = video.status || '알 수 없음';
        let statusDesc = '상태 확인 중...';

        if (video.status === 'done') {
            if (video.final === 'normal') {
                statusColorClass = 'bg-green-500/20 text-green-400';
                statusLabel = '정상';
                statusDesc = '분석이 완료되었습니다.';
            } else if (video.final === 'abnormal') {
                statusColorClass = 'bg-red-500/20 text-red-400';
                statusLabel = '비정상';
                statusDesc = '비정상 객체가 발견되었습니다.';
            } else {
                statusColorClass = 'bg-blue-500/20 text-blue-400';
                statusLabel = '완료';
                statusDesc = '분석이 완료되었습니다.';
            }
        } else if (video.status === 'uploaded') {
            statusColorClass = 'bg-purple-500/20 text-purple-400';
            statusLabel = '대기 중';
            statusDesc = '분석 대기 중입니다.';
        } else if (video.status === 'processing') {
            statusColorClass = 'bg-yellow-500/20 text-yellow-500';
            statusLabel = '분석 중';
            statusDesc = '분석이 진행 중입니다.';
        }

        statusBadge.className =
            'inline-flex items-center justify-center rounded-full px-3 py-1 text-xs font-medium ' +
            statusColorClass;
        statusBadge.textContent = statusLabel;
        statusText.textContent = statusDesc;
    }

    // 키프레임 슬라이더 생성 및 렌더링
    function renderKeyframes(video) {
        if (!keyframesContainer) return;

        keyframesContainer.innerHTML = '';

        const keyframes = Array.isArray(video.keyframes) ? video.keyframes : [];

        // 키프레임 데이터가 없을 경우 안내 메시지 표시
        if (keyframes.length === 0) {
            const msg = document.createElement('div');
            msg.className =
                'rounded-xl bg-slate-100 p-8 text-center text-sm text-slate-500 dark:bg-slate-800/30 dark:text-slate-300';
            msg.textContent =
                video.status === 'done'
                    ? '키프레임 데이터가 없습니다.'
                    : '분석이 진행 중입니다. 잠시 후 다시 확인해주세요.';
            keyframesContainer.appendChild(msg);
            return;
        }

        // 슬라이더 UI (이미지, 상태 뱃지, 네비게이션 버튼 등) 구성
        keyframesContainer.innerHTML = `
      <div class="rounded-xl border border-slate-200 bg-white/90 p-4 dark:border-slate-700 dark:bg-slate-900/90">
        <div class="flex items-center justify-between gap-3">
          <!-- 좌측 정보: 시간 및 상태 -->
          <div class="flex items-center gap-3">
            <div class="flex items-center gap-1 text-slate-600 dark:text-slate-300 text-sm">
              <span class="material-symbols-outlined text-base">schedule</span>
              <span id="kf-time">0s</span>
            </div>
            <span id="kf-status-badge"
                  class="inline-flex items-center justify-center rounded-full px-3 py-1 text-xs font-medium bg-slate-500/10 text-slate-600 dark:text-slate-300">
              상태
            </span>
          </div>

          <!-- 우측 컨트롤: 이전/다음 버튼 및 현재 위치 -->
          <div class="flex items-center gap-2 text-xs text-slate-500 dark:text-slate-400">
            <button id="kf-prev"
                    class="rounded-full border border-slate-300 px-3 py-1 text-xs font-medium hover:bg-slate-100 disabled:opacity-40 dark:border-slate-600 dark:hover:bg-slate-800">
              이전
            </button>
            <span id="kf-index" class="min-w-[60px] text-center">
              1 / ${keyframes.length}
            </span>
            <button id="kf-next"
                    class="rounded-full border border-slate-300 px-3 py-1 text-xs font-medium hover:bg-slate-100 disabled:opacity-40 dark:border-slate-600 dark:hover:bg-slate-800">
              다음
            </button>
          </div>
        </div>

        <!-- 키프레임 이미지 표시 영역 -->
        <div class="mt-4 flex justify-center">
          <div class="overflow-hidden rounded-xl border border-slate-200 bg-black/80 dark:border-slate-700">
            <img id="kf-image"
                 src=""
                 alt="keyframe"
                 class="w-full max-h-[420px] object-contain" />
          </div>
        </div>
      </div>
    `;

        const timeEl = document.getElementById('kf-time');
        const statusBadgeEl = document.getElementById('kf-status-badge');
        const imgEl = document.getElementById('kf-image');
        const indexEl = document.getElementById('kf-index');
        const prevBtn = document.getElementById('kf-prev');
        const nextBtn = document.getElementById('kf-next');

        let currentIndex = 0;

        // 현재 인덱스에 맞춰 슬라이더 뷰 업데이트
        function updateView() {
            const kf = keyframes[currentIndex];

            // 1. 시간 업데이트
            const t = kf.time ?? '-';
            timeEl.textContent = `${t}s`;

            // 2. 상태 뱃지 업데이트 (정상/비정상 색상 구분)
            let label = '';
            let cls =
                'inline-flex items-center justify-center rounded-full px-3 py-1 text-xs font-medium ';

            if (kf.status === 'abnormal') {
                label = '비정상';
                cls += 'bg-red-500/10 text-red-500 dark:text-red-300';
            } else if (kf.status === 'normal') {
                label = '정상';
                cls += 'bg-green-500/10 text-green-600 dark:text-green-300';
            } else if (kf.status) {
                label = kf.status;
                cls += 'bg-slate-500/10 text-slate-600 dark:text-slate-300';
            } else {
                label = '상태 미정';
                cls += 'bg-slate-500/10 text-slate-600 dark:text-slate-300';
            }

            statusBadgeEl.className = cls;
            statusBadgeEl.textContent = label;

            // 3. 이미지 업데이트
            if (kf.frame_image_url) {
                imgEl.src = kf.frame_image_url;
                imgEl.classList.remove('hidden');
            } else {
                imgEl.src = '';
                imgEl.classList.add('hidden');
            }

            // 4. 인덱스 텍스트 업데이트
            indexEl.textContent = `${currentIndex + 1} / ${keyframes.length}`;

            // 5. 버튼 활성화 상태 업데이트
            prevBtn.disabled = currentIndex === 0;
            nextBtn.disabled = currentIndex === keyframes.length - 1;
        }

        // 이전/다음 버튼 이벤트 연결
        prevBtn.addEventListener('click', () => {
            if (currentIndex > 0) {
                currentIndex -= 1;
                updateView();
            }
        });

        nextBtn.addEventListener('click', () => {
            if (currentIndex < keyframes.length - 1) {
                currentIndex += 1;
                updateView();
            }
        });

        // 초기 뷰 렌더링
        updateView();
    }

    // 5. 서버에서 영상 상세 정보 가져오기
    fetch(`/api/videos/${videoId}`)
        .then((response) => {
            if (!response.ok) throw new Error('Video not found');
            return response.json();
        })
        .then((video) => {
            // 파일명 표시
            if (filenameEl) {
                const displayName =
                    video.original_filename || video.filename || '(파일명 없음)';
                filenameEl.textContent = displayName;
            }

            // 메타데이터 표시 (ID, 농장 ID)
            if (videoIdEl) videoIdEl.textContent = video._id || videoId;
            if (farmIdEl) farmIdEl.textContent = video.farm_id || '-';

            // 업로드 일시 표시
            if (createdAtEl) {
                const c = video.created_at;
                let dateObj = null;

                if (c && typeof c === 'object' && c['$date']) {
                    dateObj = new Date(c['$date']);
                } else if (typeof c === 'string') {
                    dateObj = new Date(c);
                }

                if (dateObj && !Number.isNaN(dateObj.getTime())) {
                    createdAtEl.textContent = dateObj.toLocaleString();
                } else {
                    createdAtEl.textContent = '-';
                }
            }

            // 영상 길이 표시
            if (durationEl) {
                if (video.duration != null) {
                    durationEl.textContent = `${video.duration}s`;
                } else {
                    durationEl.textContent = '-';
                }
            }

            // 상태 뱃지 및 키프레임 슬라이더 업데이트
            applyStatus(video);
            renderKeyframes(video);
        })
        .catch((error) => {
            console.error('Error:', error);

            if (filenameEl) filenameEl.textContent = '오류 발생';
            if (statusText)
                statusText.textContent =
                    '영상을 불러올 수 없습니다. 잠시 후 다시 시도해 주세요.';

            if (keyframesContainer) {
                keyframesContainer.innerHTML = '';
                const msg = document.createElement('div');
                msg.className =
                    'rounded-xl bg-red-500/10 p-8 text-center text-sm text-red-500 dark:bg-red-500/10 dark:text-red-400';
                msg.textContent = '영상 정보를 불러오는 중 오류가 발생했습니다.';
                keyframesContainer.appendChild(msg);
            }
        });
});
