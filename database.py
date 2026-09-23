import os

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from models import Base, Member

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "carpool_purchase.db")
engine = create_engine(f"sqlite:///{DB_PATH}")
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
