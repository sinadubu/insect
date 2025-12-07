# db/mongo.py
import os
from pymongo import MongoClient

# =========================================================
# MongoDB 데이터베이스 연결 설정
# =========================================================

# MongoDB 접속 URI 설정
# 1. 도커 환경: docker-compose.yml에 명시된 'MONGO_URI' 환경 변수를 사용합니다.
# 2. 로컬 환경: 환경 변수가 없을 경우 기본값으로 'mongodb://localhost:27017/insect_db'를 사용합니다.
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/insect_db")

# MongoDB 클라이언트 인스턴스 생성
_client = MongoClient(MONGO_URI)

# 기본 데이터베이스 가져오기
# URI의 경로 부분(예: /insect_db)에 지정된 데이터베이스를 자동으로 선택합니다.
_db = _client.get_default_database()

def get_db():
    """
    애플리케이션 전역에서 사용할 MongoDB 데이터베이스 객체를 반환합니다.
    이 함수를 통해 DB 인스턴스에 접근하여 CRUD 작업을 수행할 수 있습니다.
    
    Returns:
        Database: pymongo Database 객체
    """
    return _db
