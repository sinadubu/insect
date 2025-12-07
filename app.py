from flask import (
    Flask,
    render_template,
    request,
    jsonify,
    redirect,
    url_for,
    session,
    flash,
)
from functools import wraps
from db.mongo import get_db
from ai.pipeline import run_analysis
from werkzeug.security import generate_password_hash, check_password_hash
from bson import json_util, ObjectId
from datetime import datetime
import uuid
import os

# Flask 애플리케이션 초기화
app = Flask(__name__)

# 업로드된 파일이 저장될 경로 설정
app.config["UPLOAD_FOLDER"] = "static/uploads"

# 보안 키 설정: 실제 운영 배포 시에는 환경 변수 등을 통해 관리하는 것이 안전합니다.
app.secret_key = "CHANGE_ME_TO_RANDOM_SECRET_KEY"


# =========================
# 유저 관련 헬퍼 함수
# =========================

def create_user(email: str, password: str, name: str, role: str = "user") -> str:
    """
    새 운 사용자를 생성합니다.
    이메일이 이미 존재하면 ValueError를 발생시킵니다.
    """
    db = get_db()
    existing = db.users.find_one({"email": email})
    if existing:
        raise ValueError("이미 사용 중인 이메일입니다.")

    # 사용자 정보  문서 생성
    doc = {
        "email": email,
        "password_hash": generate_password_hash(password), # 비밀번호는 해시 처리하여 저장
        "name": name,
        "role": role,  # 권한: "user" 또는 "admin"
        "created_at": datetime.utcnow(),
    }
    result = db.users.insert_one(doc)
    return str(result.inserted_id)


def find_user_by_email(email: str):
    """이메일로 사용자를 검색합니다."""
    return get_db().users.find_one({"email": email})


def find_user_by_id(user_id: str):
    """MongoDB ObjectId로 사용자를 검색합니다."""
    try:
        oid = ObjectId(user_id)
    except Exception:
        return None
    return get_db().users.find_one({"_id": oid})


def list_all_users():
    """모든 사용자를 최신 가입순으로 조회합니다."""
    return list(get_db().users.find({}).sort("created_at", -1))


# =========================
# 인증 / 권한 관련 데코레이터 & 컨텍스트
# =========================

def get_current_user():
    """현재 세션에 로그인된 사용자 정보를 가져옵니다."""
    if "user_id" not in session:
        return None
    return find_user_by_id(session["user_id"])


@app.context_processor
def inject_current_user():
    """
    모든 템플릿(HTML)에서 `current_user` 변수를 사용할 수 있도록 주입합니다.
    로그인 상태에 따라 UI를 다르게 보여줄 때 유용합니다.
    """
    return {"current_user": get_current_user()}


def login_required(view_func):
    """로그인이 필요한 라우트에 적용하는 데코레이터입니다."""
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            # 로그인이 안 되어 있다면 로그인 페이지로 리다이렉트
            return redirect(url_for("login", next=request.path))
        return view_func(*args, **kwargs)

    return wrapper


def admin_required(view_func):
    """관리자 권한이 필요한 라우트에 적용하는 데코레이터입니다."""
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login", next=request.path))
        user = get_current_user()
        # 관리자가 아니면 403 Forbidden 에러 반환
        if not user or user.get("role") != "admin":
            return "접근 권한이 없습니다.", 403
        return view_func(*args, **kwargs)

    return wrapper


# =========================
# HTML 페이지 라우트
# =========================

@app.route("/")
def home():
    """메인 페이지: 기본적으로 대시보드로 이동합니다."""
    return redirect(url_for("dashboard_page"))


@app.route("/upload")
@login_required
def upload_page():
    """영상 업로드 페이지를 렌더링합니다."""
    return render_template("upload.html")


@app.route("/dashboard")
@login_required
def dashboard_page():
    """대시보드 페이지를 렌더링합니다."""
    return render_template("dashboard.html")


@app.route("/analysis/<video_id>")
@login_required
def analysis_page(video_id):
    """분석 결과 상세 페이지를 렌더링합니다."""
    return render_template("analysis.html", video_id=video_id)


@app.route("/admin/users")
@admin_required
def admin_users():
    """
    관리자 전용: 사용자 목록 관리 페이지
    각 사용자의 영상 업로드 통계 등의 정보를 함께 보여줍니다.
    """
    db = get_db()
    users = list_all_users()
    for u in users:
        # 템플릿에서 사용하기 쉽도록 ObjectId를 문자열로 변환
        u["_id"] = str(u["_id"])

        # 생성일자 포맷팅
        if u.get("created_at"):
            try:
                u["created_at_str"] = u["created_at"].strftime("%Y-%m-%d %H:%M")
            except Exception:
                u["created_at_str"] = ""
        else:
            u["created_at_str"] = ""

        # 해당 사용자가 업로드한 영상 개수 조회
        try:
            from bson import ObjectId
            video_count = db.videos.count_documents({"user_id": ObjectId(u["_id"])})
        except Exception:
            video_count = 0
        u["video_count"] = video_count

    return render_template("admin_users.html", users=users)

@app.route("/admin/users/<user_id>", methods=["DELETE"])
@admin_required
def admin_delete_user(user_id):
    """
    관리자 기능: 특정 사용자 계정과 그 사용자가 업로드한 모든 영상을 삭제합니다.
    """
    db = get_db()
    target_user = find_user_by_id(user_id)
    if not target_user:
        return jsonify({"error": "user not found"}), 404

    current = get_current_user()
    # 안전장치: 관리자 본인의 계정은 실수로 삭제하지 못하도록 방지
    if str(target_user["_id"]) == str(current["_id"]):
        return jsonify({"error": "본인 계정은 여기서 삭제할 수 없습니다."}), 400

    # 이 사용자가 업로드한 모든 영상 조회
    videos = list(db.videos.find({"user_id": target_user["_id"]}))
    deleted_video_count = 0

    # 실제 영상 파일 삭제
    for v in videos:
        file_path = v.get("path")
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
            except OSError:
                # 파일 삭제에 실패하더라도 DB 삭제 프로세스는 계속 진행
                pass
        deleted_video_count += 1

    # DB에서 영상 정보 삭제
    db.videos.delete_many({"user_id": target_user["_id"]})

    # DB에서 사용자 정보 삭제
    db.users.delete_one({"_id": target_user["_id"]})

    return jsonify({
        "ok": True,
        "deleted_videos": deleted_video_count,
    })


# =========================
# 인증(Auth) 라우트: 로그인 / 회원가입 / 로그아웃
# =========================

@app.route("/login", methods=["GET", "POST"])
def login():
    """로그인 처리"""
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")

        user = find_user_by_email(email)
        # 이메일이 없거나 비밀번호가 일치하지 않는 경우
        if not user or not check_password_hash(user.get("password_hash", ""), password):
            flash("이메일 또는 비밀번호가 올바르지 않습니다.", "error")
            return render_template("login.html")

        # 로그인 성공 시 세션에 정보 저장
        session["user_id"] = str(user["_id"])
        session["role"] = user.get("role", "user")

        # 로그인 후 이동할 페이지가 있다면 그곳으로, 없다면 대시보드로 이동
        next_url = request.args.get("next") or url_for("dashboard_page")
        return redirect(next_url)

    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """회원가입 처리"""
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        password2 = request.form.get("password2", "")

        # 필수 입력값 검증
        if not name or not email or not password:
            flash("이름, 이메일, 비밀번호를 모두 입력해주세요.", "error")
            return render_template("register.html")

        # 비밀번호 일치 여부 확인
        if password != password2:
            flash("비밀번호 확인이 일치하지 않습니다.", "error")
            return render_template("register.html")

        try:
            # 사용자 생성 시도
            user_id = create_user(email=email, password=password, name=name, role="user")
        except ValueError as e:
            flash(str(e), "error")
            return render_template("register.html")

        # 가입 완료 후 자동 로그인 처리
        session["user_id"] = user_id
        session["role"] = "user"
        return redirect(url_for("dashboard_page"))

    return render_template("register.html")


@app.route("/logout")
def logout():
    """로그아웃: 세션을 비우고 로그인 페이지로 이동합니다."""
    session.clear()
    return redirect(url_for("login"))


# =========================
# API: 영상 업로드 및 분석 요청
# =========================

@app.route("/api/videos", methods=["POST"])
@login_required
def upload_video():
    """
    영상을 업로드하고 분석 작업을 시작하는 API입니다.
    """
    from pprint import pprint  # 디버깅 편의를 위해 사용

    try:
        print("/api/videos called")

        current_user = get_current_user()
        if not current_user:
            return jsonify({"error": "unauthenticated"}), 401

        # 1. 요청에 파일이 포함되어 있는지 확인
        if "video" not in request.files:
            print("request.files 에 'video' 키가 없음")
            return jsonify({"error": "no file field 'video' in form"}), 400

        file = request.files["video"]

        if file.filename == "":
            print("빈 파일 이름")
            return jsonify({"error": "empty filename"}), 400

        # 2. 사육장 번호(ID) 확인
        farm_id = request.form.get("farm_id")
        if not farm_id:
            print("farm_id 누락")
            return jsonify({"error": "farm_id is required"}), 400

        print(f"파일 이름: {file.filename}, 사육장 번호: {farm_id}")

        # 업로드된 원본 파일 이름 (사용자 표시용)
        original_filename = file.filename

        # 3. 서버 내부 저장용 파일 이름 생성 (UUID 사용으로 중복 방지)
        video_id = str(uuid.uuid4())
        ext = os.path.splitext(file.filename)[1] or ".mp4"
        filename = f"{video_id}{ext}"

        upload_dir = app.config["UPLOAD_FOLDER"]
        os.makedirs(upload_dir, exist_ok=True)

        file_path = os.path.join(upload_dir, filename)
        file.save(file_path)
        print(f"파일 저장 완료: {file_path}")

        # 4. 데이터베이스에 영상 정보 저장
        db = get_db()
        doc = {
            "_id": video_id,
            "farm_id": farm_id,
            "filename": filename,                    # 디스크에 저장된 실제 파일명
            "original_filename": original_filename,  # 사용자가 보게 될 파일명
            "path": file_path,
            "status": "uploaded",                    # 초기 상태
            "created_at": datetime.utcnow(),
            "user_id": current_user["_id"],          # 업로드한 사용자 ID 연결
        }
        pprint({"insert_doc": doc})
        db.videos.insert_one(doc)
        print("DB insert 완료")

        # 5. 비동기 분석 파이프라인 호출
        # 여기서 에러가 발생해도 파일 업로드는 성공한 것으로 간주하고, DB 상태만 에러로 업데이트합니다.
        try:
            print("run_analysis 시작")
            run_analysis(video_id, file_path)
            print("run_analysis 정상 종료")
        except Exception as e:
            import traceback
            print("run_analysis 중 예외 발생:")
            traceback.print_exc()
            db.videos.update_one(
                {"_id": video_id},
                {"$set": {"status": "error", "analysis_error": str(e)}},
            )

        # 프론트엔드에서는 video_id를 이용해 분석 결과 페이지로 이동할 수 있습니다.
        return jsonify({"video_id": video_id})

    except Exception as e:
        import traceback
        print("업로드 중 예외 발생 (upload_video 전체 try):")
        traceback.print_exc()
        return jsonify({
            "error": "internal server error",
            "detail": str(e),
        }), 500


# =========================
# API: 영상 목록 조회
# =========================

@app.route("/api/videos/list", methods=["GET"])
@login_required
def list_videos():
    """
    영상 목록을 반환합니다.
    일반 사용자는 본인의 영상만, 관리자는 모든 영상을 볼 수 있습니다.
    """
    db = get_db()
    current_user = get_current_user()

    query = {}
    if not current_user:
        return jsonify({"error": "unauthenticated"}), 401

    # 권한 체크: 관리자가 아니면 본인의 영상만 조회하도록 필터링
    if current_user.get("role") != "admin":
        query["user_id"] = current_user["_id"]

    # 최신순 정렬, 최대 50개 제한
    cursor = db.videos.find(query).sort("created_at", -1).limit(50)

    videos = []
    for doc in cursor:
        videos.append({
            "video_id": doc.get("_id"),
            "farm_id": doc.get("farm_id"),
            "original_filename": doc.get("original_filename"),
            "filename": doc.get("filename"),
            "status": doc.get("status"),
            "final": doc.get("final"),
            "created_at": doc.get("created_at").isoformat() if doc.get("created_at") else None,
        })

    return jsonify({"items": videos})


# =========================
# API: 대시보드 통계 데이터
# =========================

@app.route("/api/dashboard")
@login_required
def dashboard_data():
    """
    대시보드에 표시할 통계와 최근 활동 데이터를 반환합니다.
    """
    db = get_db()
    current_user = get_current_user()
    if not current_user:
        return jsonify({"error": "unauthenticated"}), 401

    # 권한에 따른 데이터 필터링 설정
    if current_user.get("role") == "admin":
        filter_query = {}
    else:
        filter_query = {"user_id": current_user["_id"]}

    # 각종 상태별 카운트 집계
    all_videos = db.videos.count_documents(filter_query)
    done = db.videos.count_documents({**filter_query, "status": "done"})
    abnormal = db.videos.count_documents({**filter_query, "final": "abnormal"})
    normal = db.videos.count_documents({**filter_query, "final": "normal"})

    # 최근 업로드된 영상 10개 조회
    recent_cursor = (
        db.videos.find(filter_query, {"_id": 1, "filename": 1, "status": 1, "created_at": 1})
        .sort("created_at", -1)
        .limit(10)
    )
    recent = []
    for doc in recent_cursor:
        recent.append({
            "video_id": doc.get("_id"),
            "filename": doc.get("filename"),
            "status": doc.get("status"),
            "created_at": doc.get("created_at").isoformat() if doc.get("created_at") else None,
        })

    return jsonify({
        "stats": {
            "total": all_videos,
            "done": done,
            "normal": normal,
            "abnormal": abnormal,
        },
        "recent": recent,
    })


# =========================
# API: 단일 영상 상세 조회
# =========================

@app.route("/api/videos/<video_id>", methods=["GET"])
@login_required
def video_detail(video_id):
    """
    특정 영상의 상세 정보를 반환합니다. 소유권 확인 과정을 거칩니다.
    """
    db = get_db()
    current_user = get_current_user()
    if not current_user:
        return jsonify({"error": "unauthenticated"}), 401

    video = db.videos.find_one({"_id": video_id})
    if not video:
        return jsonify({"error": "not found"}), 404

    # 관리자가 아닌 경우, 본인의 영상인지 확인
    if current_user.get("role") != "admin":
        if video.get("user_id") != current_user["_id"]:
            return jsonify({"error": "forbidden"}), 403

    # MongoDB 객체(ObjectId, datetime 등)를 JSON으로 직렬화하여 반환
    return app.response_class(
        json_util.dumps(video),
        mimetype="application/json",
    )


# =========================
# API: 영상 및 분석 결과 삭제
# =========================

@app.route("/api/videos/<video_id>", methods=["DELETE"])
@login_required
def delete_video(video_id):
    """
    특정 영상을 DB와 파일 시스템에서 삭제합니다.
    """
    db = get_db()
    current_user = get_current_user()
    if not current_user:
        return jsonify({"error": "unauthenticated"}), 401

    video = db.videos.find_one({"_id": video_id})
    if not video:
        return jsonify({"error": "not found"}), 404

    # 삭제 권한 확인 (관리자 또는 본인)
    if current_user.get("role") != "admin":
        if video.get("user_id") != current_user["_id"]:
            return jsonify({"error": "forbidden"}), 403

    # 파일 시스템에서 삭제 시도
    file_path = video.get("path")
    if file_path and os.path.exists(file_path):
        try:
            os.remove(file_path)
        except OSError:
            # 파일이 이미 없거나 삭제 실패 시 로그만 남기고 진행 (여기서는 pass)
            pass

    # DB에서 문서 삭제
    db.videos.delete_one({"_id": video_id})

    return jsonify({"ok": True})


# =========================

if __name__ == "__main__":
    app.run(debug=True)
