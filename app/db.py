import time
from sqlalchemy import select, create_engine, event, ForeignKey, String, Text, JSON, Float, Integer, Boolean, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from . import config

config.initialize_data()
engine = create_engine(config.DATABASE_URL, connect_args={'check_same_thread': False, 'timeout': 30} if config.DATABASE_URL.startswith('sqlite:') else {}, pool_pre_ping=True)
if config.DATABASE_URL.startswith('sqlite:'):
    @event.listens_for(engine, 'connect')
    def pragmas(connection, _):
        connection.execute('PRAGMA foreign_keys=ON')
        connection.execute('PRAGMA journal_mode=WAL')
Session = sessionmaker(engine, expire_on_commit=False)

class Base(DeclarativeBase): pass

class User(Base):
    __tablename__ = 'users'
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True)
    password: Mapped[str] = mapped_column(Text, default='')
    settings: Mapped[dict] = mapped_column(JSON, default=dict)
    month: Mapped[str] = mapped_column(String(7), default='')
    spend: Mapped[float] = mapped_column(Float, default=0)

class CriteriaRecord(Base):
    __tablename__ = 'criteria'
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    name: Mapped[str] = mapped_column(String(200))
    data: Mapped[dict] = mapped_column(JSON)

class Job(Base):
    __tablename__ = 'jobs'
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    kind: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), default='queued')
    payload: Mapped[dict] = mapped_column(JSON)
    progress: Mapped[dict] = mapped_column(JSON, default=dict)
    cursor: Mapped[int] = mapped_column(default=0)
    attempts: Mapped[int] = mapped_column(default=0)
    lease: Mapped[float] = mapped_column(Float, default=0)
    created: Mapped[float] = mapped_column(Float, default=time.time)
    cancel: Mapped[bool] = mapped_column(Boolean, default=False)
    error: Mapped[str | None] = mapped_column(Text)
    spent: Mapped[float] = mapped_column(Float, default=0)
    budget: Mapped[float] = mapped_column(Float, default=0)
    idempotency_key: Mapped[str] = mapped_column(String(64))
    __table_args__ = (UniqueConstraint('user_id', 'idempotency_key'),)

class Target(Base):
    __tablename__ = 'targets'
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    job_id: Mapped[int] = mapped_column(ForeignKey('jobs.id'))
    category: Mapped[str] = mapped_column(String(20))
    identity: Mapped[str] = mapped_column(String(500))
    data: Mapped[dict] = mapped_column(JSON)
    screening: Mapped[dict] = mapped_column(JSON)
    __table_args__ = (UniqueConstraint('job_id', 'category', 'identity'),)

class Opportunity(Base):
    __tablename__ = 'opportunities'
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    target_id: Mapped[int | None] = mapped_column(ForeignKey('targets.id'))
    name: Mapped[str] = mapped_column(String(200))
    category: Mapped[str] = mapped_column(String(20))
    notes: Mapped[str] = mapped_column(Text, default='')
    financials: Mapped[list] = mapped_column(JSON, default=list)
    criteria: Mapped[dict] = mapped_column(JSON, default=dict)

class Document(Base):
    __tablename__ = 'documents'
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    opportunity_id: Mapped[int] = mapped_column(ForeignKey('opportunities.id'))
    filename: Mapped[str] = mapped_column(String(200))
    storage: Mapped[str] = mapped_column(String(64))
    size: Mapped[int] = mapped_column(Integer)
    digest: Mapped[str] = mapped_column(String(64))

class Evaluation(Base):
    __tablename__ = 'evaluations'
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    opportunity_id: Mapped[int] = mapped_column(ForeignKey('opportunities.id'))
    job_id: Mapped[int] = mapped_column(ForeignKey('jobs.id'), unique=True)
    created: Mapped[float] = mapped_column(Float, default=time.time)
    report: Mapped[dict] = mapped_column(JSON)

class Usage(Base):
    __tablename__ = 'usage'
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    job_id: Mapped[int] = mapped_column(ForeignKey('jobs.id'))
    category: Mapped[str] = mapped_column(String(30))
    provider: Mapped[str] = mapped_column(String(50))
    estimated_cost: Mapped[float] = mapped_column(Float)
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    created: Mapped[float] = mapped_column(Float, default=time.time)

class Cache(Base):
    __tablename__ = 'provider_cache'
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    created: Mapped[float] = mapped_column(Float, default=time.time)
    data: Mapped[dict] = mapped_column(JSON)

def init_db(): Base.metadata.create_all(engine)

def local_user(db):
    """Single local operator; no sign-in. Reuses the first account from older databases."""
    user = db.scalar(select(User).order_by(User.id).limit(1))
    if not user:
        user = User(email='local', settings=dict(config.DEFAULT_SETTINGS)); db.add(user); db.commit()
    return user


class ProviderRate(Base):
    __tablename__ = 'provider_rates'
    key: Mapped[str] = mapped_column(String(64),primary_key=True)
    next_allowed: Mapped[float] = mapped_column(Float,default=0)
    window_start: Mapped[float] = mapped_column(Float,default=time.time)
    calls: Mapped[int] = mapped_column(default=0)
