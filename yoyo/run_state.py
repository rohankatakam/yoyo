from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import select, text

from . import db
from .artifacts import digest


class State:
    def __init__(self, inputs, resume=None):
        self.lock = db.engine.connect()
        lock_key = int(digest(inputs)[:15], 16)
        if not self.lock.scalar(
            text("SELECT pg_try_advisory_lock(:key)"), {"key": lock_key}
        ):
            self.lock.close()
            raise RuntimeError("An identical episode operation is already running")
        self.lock_key = lock_key
        self.id = resume or str(uuid4())
        try:
            self.load(inputs, resume)
        except Exception:
            self.close()
            raise

    def load(self, inputs, resume):
        with db.engine.begin() as conn:
            if not resume:
                prior = (
                    conn.execute(
                        select(db.runs)
                        .where(
                            db.runs.c.operation_key == digest(inputs),
                        )
                        .order_by(db.runs.c.created_at.desc())
                    )
                    .mappings()
                    .first()
                )
                if prior:
                    self.id, self.inputs, self.progress, self.result = (
                        prior["id"],
                        inputs,
                        prior["progress"],
                        prior["result"] if prior["status"] == "completed" else None,
                    )
                    return
            if resume:
                row = (
                    conn.execute(select(db.runs).where(db.runs.c.id == resume))
                    .mappings()
                    .one()
                )
                if row["input"] != inputs:
                    raise ValueError("Resume inputs differ from original run")
                self.inputs, self.progress = row["input"], row["progress"]
                self.result = row["result"] if row["status"] == "completed" else None
            else:
                self.inputs, self.progress, self.result = (
                    inputs,
                    {"operations": {}},
                    None,
                )
                conn.execute(
                    db.runs.insert().values(
                        id=self.id,
                        status="running",
                        input=inputs,
                        operation_key=digest(inputs),
                        progress=self.progress,
                        trace_status="pending",
                    )
                )

    def close(self):
        self.lock.execute(
            text("SELECT pg_advisory_unlock(:key)"), {"key": self.lock_key}
        )
        self.lock.close()

    def save(self, **values):
        with db.engine.begin() as conn:
            conn.execute(
                db.runs.update()
                .where(db.runs.c.id == self.id)
                .values(progress=self.progress, **values)
            )


def now():
    return datetime.now(UTC)
