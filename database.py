import os

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from models import Base, Member


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
