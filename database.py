import os

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from models import Base, Member

# Neon 免費方案空間上限約 0.5 GB；剩餘容量低於這個門檻就提醒使用者清理舊資料。
NEON_STORAGE_LIMIT_BYTES = int(0.5 * 1024 * 1024 * 1024)
NEON_STORAGE_WARNING_REMAINING_BYTES = int(0.1 * 1024 * 1024 * 1024)


def _build_engine():
    database_url = os.environ.get("DATABASE_URL")
    if database_url:
        # Render/Neon 給的連線字串可能是 postgres://，SQLAlchemy 2.x 需要 postgresql://
        if database_url.startswith("postgres://"):
            database_url = database_url.replace("postgres://", "postgresql://", 1)
        return create_engine(database_url)

    # 沒有設定 DATABASE_URL 時（本機開發），沿用本機 SQLite 檔案
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "carpool_purchase.db")
    return create_engine(f"sqlite:///{db_path}")


engine = _build_engine()
SessionLocal = sessionmaker(bind=engine)

INITIAL_MEMBERS = [
    ("Hugo", True),
    ("Tina", False),
    ("Blue", False),
    ("Mango", False),
    ("Rennie", False),
]


def init_db() -> None:
    Base.metadata.create_all(engine)
    with SessionLocal() as session:
        if session.query(Member).count() == 0:
            for name, is_owner in INITIAL_MEMBERS:
                session.add(Member(name=name, is_owner=is_owner))
            session.commit()


def get_session() -> Session:
    return SessionLocal()


def get_storage_warning() -> str | None:
    """只在雲端 PostgreSQL 上檢查資料庫容量；本機 SQLite 沒有 Neon 的容量限制，不檢查。
    剩餘容量低於 NEON_STORAGE_WARNING_REMAINING_BYTES 時，回傳提醒文字；否則回傳 None。
    """
    if engine.dialect.name != "postgresql":
        return None
    try:
        with engine.connect() as conn:
            used_bytes = conn.execute(text("SELECT pg_database_size(current_database())")).scalar()
    except Exception:
        return None

    remaining_bytes = NEON_STORAGE_LIMIT_BYTES - used_bytes
    if remaining_bytes > NEON_STORAGE_WARNING_REMAINING_BYTES:
        return None

    remaining_mb = max(remaining_bytes, 0) / (1024 * 1024)
    return f"資料庫容量剩餘不到 0.1GB（約 {remaining_mb:.0f}MB），建議考慮清理較久遠的舊紀錄，避免容量用滿。"
