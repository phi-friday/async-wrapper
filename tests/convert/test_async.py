from __future__ import annotations

import inspect
import time
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, AsyncGenerator, Generator

import anyio
import pytest
import sqlalchemy as sa
from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.orm import Mapped, registry

from ..base import Timer  # noqa: TID252
from .base import BaseTest

pytestmark = pytest.mark.anyio

metadata = MetaData()
mapper_registry = registry(metadata=metadata)
Base = mapper_registry.generate_base()


class Table(Base):
    __tablename__ = "table"
    id: Mapped[int] = sa.Column(sa.Integer(), primary_key=True, autoincrement=True)  # pyright: ignore[reportAssignmentType]
    name: Mapped[str] = sa.Column(sa.String(255), nullable=False)  # pyright: ignore[reportAssignmentType]
    value: Mapped[float] = sa.Column(sa.Float(), nullable=False)  # pyright: ignore[reportAssignmentType]


def create_new_table(name: str | None = None, value: float | None = None) -> Table:
    return Table(name=name or "test", value=1.0 if value is None else value)


@pytest.fixture(scope="module")
def temp_dir() -> Generator[Path, None, None]:
    with TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


@pytest.fixture(scope="module")
async def engine(
    temp_dir: Path, anyio_backend: tuple[str, dict[str, Any]]
) -> AsyncGenerator[AsyncEngine, None]:
    if anyio_backend[0] == "trio":
        pytest.skip("trio does not support sqlalchemy")

    engine = create_async_engine(f"sqlite+aiosqlite:///{temp_dir / 'test.db'}")
    async with engine.begin() as conn:
        await conn.run_sync(lambda sync_conn: metadata.create_all(sync_conn))

    new = create_new_table()
    async with AsyncSession(engine) as session:
        session.add(new)
        await session.commit()

    try:
        yield engine
    finally:
        await engine.dispose()


@pytest.fixture()
async def session(engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSession(engine) as session:
        yield session


class TestAsync(BaseTest):
    @pytest.mark.parametrize("x", range(1, 4))
    async def test_sync_to_async(self, x: int):
        sample = self.sync_to_async()(sample_sync_func)
        with Timer() as timer:
            await sample(x, self.epsilon)
        assert self.epsilon * x < timer.term < self.epsilon * x + self.epsilon

    @pytest.mark.parametrize("x", range(2, 5))
    async def test_sync_to_async_gather(self, x: int):
        sample = self.sync_to_async()(sample_sync_func)
        with Timer() as timer:
            async with anyio.create_task_group() as task_group:
                for _ in range(x):
                    task_group.start_soon(sample, 1, self.epsilon)
        assert self.epsilon < timer.term < self.epsilon + self.epsilon

    @pytest.mark.parametrize("x", range(2, 5))
    async def test_toggle(self, x: int):
        sample = self.toggle()(sample_sync_func)
        assert inspect.iscoroutinefunction(sample)
        with Timer() as timer:
            await sample(x, self.epsilon)
        assert self.epsilon * x < timer.term < self.epsilon * x + self.epsilon


class TestSqlalchemy(BaseTest):
    async def test_commit(self, session: AsyncSession) -> None:
        new = create_new_table("add", 2.0)
        session.add(new)
        commit = session.commit()
        self.async_to_sync()(commit)()
        await session.rollback()

        await session.refresh(new)
        maybe = await session.get(Table, new.id)
        assert maybe is not None

    async def test_rollback(self, session: AsyncSession) -> None:
        new = create_new_table("rollback", 3.0)
        session.add(new)
        await session.flush()
        await session.refresh(new)
        new_id = int(new.id)
        rollback = session.rollback()
        self.async_to_sync()(rollback)()

        maybe = await session.get(Table, new_id)
        assert maybe is None


def sample_sync_func(x: int, epsilon: float) -> None:
    time.sleep(epsilon * x)
