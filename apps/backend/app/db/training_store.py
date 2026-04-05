import os
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, String, Text, create_engine, func, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker


class Base(DeclarativeBase):
    pass


class DatasetSampleModel(Base):
    __tablename__ = "training_dataset_samples"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class TrainingLogModel(Base):
    __tablename__ = "training_logs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    level: Mapped[str] = mapped_column(String(32), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)


class TrainingRuntimeSnapshotModel(Base):
    __tablename__ = "training_runtime_snapshot"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class QuasiStaticScenarioModel(Base):
    __tablename__ = "quasi_static_scenarios"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    request_payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class QuasiStaticRunModel(Base):
    __tablename__ = "quasi_static_runs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    scenario_id: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    result_payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class QuasiStaticRunArtifactModel(Base):
    __tablename__ = "quasi_static_run_artifacts"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(64), nullable=False)
    artifact_type: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


def _db_url() -> str:
    # Training storage prefers dedicated TRAINING_DB_URL, then DATABASE_URL.
    # SQLAlchemy sync engine requires sync postgres driver, so asyncpg URL is normalized.
    raw = (
        os.getenv("TRAINING_DB_URL") or os.getenv("DATABASE_URL") or "sqlite:///./data/training.db"
    )
    if raw.startswith("postgresql+asyncpg://"):
        return raw.replace("postgresql+asyncpg://", "postgresql+psycopg://", 1)
    return raw


engine = create_engine(_db_url(), future=True)
SessionLocal = sessionmaker(
    bind=engine, autoflush=False, autocommit=False, expire_on_commit=False, class_=Session
)


def _iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def init_training_db() -> None:
    Base.metadata.create_all(bind=engine)


def list_dataset() -> list[dict]:
    with SessionLocal() as session:
        items = session.scalars(
            select(DatasetSampleModel).order_by(DatasetSampleModel.created_at.desc())
        ).all()
        return [
            {
                "id": item.id,
                "name": item.name,
                "payload": item.payload,
                "label": item.label,
                "note": item.note,
                "created_at": _iso(item.created_at),
            }
            for item in items
        ]


def add_dataset_sample(item: dict) -> dict:
    with SessionLocal() as session:
        model = DatasetSampleModel(
            id=item["id"],
            name=item["name"],
            payload=item["payload"],
            label=item.get("label"),
            note=item.get("note"),
            created_at=datetime.now(timezone.utc),
        )
        session.add(model)
        session.commit()
        session.refresh(model)
        return {
            "id": model.id,
            "name": model.name,
            "payload": model.payload,
            "label": model.label,
            "note": model.note,
            "created_at": _iso(model.created_at),
        }


def update_dataset_sample(sample_id: str, payload: dict) -> dict | None:
    with SessionLocal() as session:
        model = session.get(DatasetSampleModel, sample_id)
        if model is None:
            return None
        model.name = payload["name"]
        model.payload = payload["payload"]
        model.label = payload.get("label")
        model.note = payload.get("note")
        session.commit()
        session.refresh(model)
        return {
            "id": model.id,
            "name": model.name,
            "payload": model.payload,
            "label": model.label,
            "note": model.note,
            "created_at": _iso(model.created_at),
        }


def delete_dataset_sample(sample_id: str) -> bool:
    with SessionLocal() as session:
        model = session.get(DatasetSampleModel, sample_id)
        if model is None:
            return False
        session.delete(model)
        session.commit()
        return True


def add_training_log(log_id: str, level: str, message: str) -> None:
    with SessionLocal() as session:
        row = TrainingLogModel(
            id=log_id, ts=datetime.now(timezone.utc), level=level, message=message
        )
        session.add(row)
        session.commit()


def list_training_logs(limit: int = 200) -> list[dict]:
    safe_limit = max(1, min(limit, 1000))
    with SessionLocal() as session:
        rows = session.scalars(
            select(TrainingLogModel).order_by(TrainingLogModel.ts.desc()).limit(safe_limit)
        ).all()
        return [
            {"ts": _iso(row.ts), "level": row.level, "message": row.message} for row in rows[::-1]
        ]


def load_runtime_snapshot() -> dict | None:
    with SessionLocal() as session:
        row = session.get(TrainingRuntimeSnapshotModel, "runtime")
        if row is None:
            return None
        return row.payload


def save_runtime_snapshot(payload: dict) -> None:
    with SessionLocal() as session:
        row = session.get(TrainingRuntimeSnapshotModel, "runtime")
        if row is None:
            row = TrainingRuntimeSnapshotModel(
                key="runtime",
                payload=payload,
                updated_at=datetime.now(timezone.utc),
            )
            session.add(row)
        else:
            row.payload = payload
            row.updated_at = datetime.now(timezone.utc)
        session.commit()


def list_quasi_static_scenarios() -> list[dict]:
    init_training_db()
    with SessionLocal() as session:
        rows = session.scalars(
            select(QuasiStaticScenarioModel).order_by(QuasiStaticScenarioModel.created_at.desc())
        ).all()
        return [
            {
                "id": row.id,
                "name": row.name,
                "description": row.description,
                "request_payload": row.request_payload,
                "created_at": _iso(row.created_at),
                "updated_at": _iso(row.updated_at),
            }
            for row in rows
        ]


def get_quasi_static_scenario(scenario_id: str) -> dict | None:
    init_training_db()
    with SessionLocal() as session:
        row = session.get(QuasiStaticScenarioModel, scenario_id)
        if row is None:
            return None
        return {
            "id": row.id,
            "name": row.name,
            "description": row.description,
            "request_payload": row.request_payload,
            "created_at": _iso(row.created_at),
            "updated_at": _iso(row.updated_at),
        }


def add_quasi_static_scenario(payload: dict) -> dict:
    init_training_db()
    now = datetime.now(timezone.utc)
    with SessionLocal() as session:
        row = QuasiStaticScenarioModel(
            id=payload["id"],
            name=payload["name"],
            description=payload.get("description"),
            request_payload=payload["request_payload"],
            created_at=now,
            updated_at=now,
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        return {
            "id": row.id,
            "name": row.name,
            "description": row.description,
            "request_payload": row.request_payload,
            "created_at": _iso(row.created_at),
            "updated_at": _iso(row.updated_at),
        }


def update_quasi_static_scenario(scenario_id: str, payload: dict) -> dict | None:
    init_training_db()
    with SessionLocal() as session:
        row = session.get(QuasiStaticScenarioModel, scenario_id)
        if row is None:
            return None
        row.name = payload["name"]
        row.description = payload.get("description")
        row.request_payload = payload["request_payload"]
        row.updated_at = datetime.now(timezone.utc)
        session.commit()
        session.refresh(row)
        return {
            "id": row.id,
            "name": row.name,
            "description": row.description,
            "request_payload": row.request_payload,
            "created_at": _iso(row.created_at),
            "updated_at": _iso(row.updated_at),
        }


def delete_quasi_static_scenario(scenario_id: str) -> bool:
    init_training_db()
    with SessionLocal() as session:
        row = session.get(QuasiStaticScenarioModel, scenario_id)
        if row is None:
            return False
        session.delete(row)
        session.commit()
        return True


def add_quasi_static_run(payload: dict) -> dict:
    init_training_db()
    with SessionLocal() as session:
        row = QuasiStaticRunModel(
            id=payload["id"],
            scenario_id=payload["scenario_id"],
            status=payload["status"],
            result_payload=payload["result_payload"],
            created_at=datetime.now(timezone.utc),
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        return {
            "id": row.id,
            "scenario_id": row.scenario_id,
            "status": row.status,
            "result_payload": row.result_payload,
            "created_at": _iso(row.created_at),
        }


def list_quasi_static_runs(scenario_id: str) -> list[dict]:
    init_training_db()
    with SessionLocal() as session:
        rows = session.scalars(
            select(QuasiStaticRunModel)
            .where(QuasiStaticRunModel.scenario_id == scenario_id)
            .order_by(QuasiStaticRunModel.created_at.desc())
        ).all()
        return [
            {
                "id": row.id,
                "scenario_id": row.scenario_id,
                "status": row.status,
                "result_payload": row.result_payload,
                "created_at": _iso(row.created_at),
            }
            for row in rows
        ]


def get_quasi_static_run(run_id: str) -> dict | None:
    init_training_db()
    with SessionLocal() as session:
        row = session.get(QuasiStaticRunModel, run_id)
        if row is None:
            return None
        return {
            "id": row.id,
            "scenario_id": row.scenario_id,
            "status": row.status,
            "result_payload": row.result_payload,
            "created_at": _iso(row.created_at),
        }


def add_quasi_static_run_artifact(payload: dict) -> dict:
    init_training_db()
    with SessionLocal() as session:
        row = QuasiStaticRunArtifactModel(
            id=payload["id"],
            run_id=payload["run_id"],
            artifact_type=payload["artifact_type"],
            payload=payload["payload"],
            created_at=datetime.now(timezone.utc),
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        return {
            "id": row.id,
            "run_id": row.run_id,
            "artifact_type": row.artifact_type,
            "payload": row.payload,
            "created_at": _iso(row.created_at),
        }


def list_quasi_static_run_artifacts(
    run_id: str, limit: int = 20, offset: int = 0, sort: str = "desc"
) -> dict:
    init_training_db()
    safe_limit = max(1, min(limit, 200))
    safe_offset = max(0, offset)
    safe_sort = "asc" if sort == "asc" else "desc"
    with SessionLocal() as session:
        total = (
            session.scalar(
                select(func.count())
                .select_from(QuasiStaticRunArtifactModel)
                .where(QuasiStaticRunArtifactModel.run_id == run_id)
            )
            or 0
        )
        order_created = (
            QuasiStaticRunArtifactModel.created_at.asc()
            if safe_sort == "asc"
            else QuasiStaticRunArtifactModel.created_at.desc()
        )
        order_id = (
            QuasiStaticRunArtifactModel.id.asc()
            if safe_sort == "asc"
            else QuasiStaticRunArtifactModel.id.desc()
        )
        rows = session.scalars(
            select(QuasiStaticRunArtifactModel)
            .where(QuasiStaticRunArtifactModel.run_id == run_id)
            .order_by(order_created, order_id)
            .limit(safe_limit)
            .offset(safe_offset)
        ).all()
        items = [
            {
                "id": row.id,
                "run_id": row.run_id,
                "artifact_type": row.artifact_type,
                "payload": row.payload,
                "created_at": _iso(row.created_at),
            }
            for row in rows
        ]
        return {
            "items": items,
            "total": int(total),
            "limit": safe_limit,
            "offset": safe_offset,
            "sort": safe_sort,
            "has_more": safe_offset + len(items) < int(total),
        }


def get_quasi_static_run_artifact(artifact_id: str) -> dict | None:
    init_training_db()
    with SessionLocal() as session:
        row = session.get(QuasiStaticRunArtifactModel, artifact_id)
        if row is None:
            return None
        return {
            "id": row.id,
            "run_id": row.run_id,
            "artifact_type": row.artifact_type,
            "payload": row.payload,
            "created_at": _iso(row.created_at),
        }


def delete_quasi_static_run_artifact(artifact_id: str) -> bool:
    init_training_db()
    with SessionLocal() as session:
        row = session.get(QuasiStaticRunArtifactModel, artifact_id)
        if row is None:
            return False
        session.delete(row)
        session.commit()
        return True
