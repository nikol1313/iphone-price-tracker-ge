from contextlib import asynccontextmanager

import pytest

from app.db import sess


class FakeSession:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0
        self.closed = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        self.closed = True

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.rollbacks += 1


@pytest.mark.asyncio
async def test_get_conn_commits_and_closes_after_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = FakeSession()
    monkeypatch.setattr(sess, "SESSION", lambda: fake)
    dependency = asynccontextmanager(sess.get_conn)

    async with dependency() as yielded:
        assert yielded is fake

    assert fake.commits == 1
    assert fake.rollbacks == 0
    assert fake.closed is True


@pytest.mark.asyncio
async def test_get_conn_rolls_back_and_closes_after_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = FakeSession()
    monkeypatch.setattr(sess, "SESSION", lambda: fake)
    dependency = asynccontextmanager(sess.get_conn)

    with pytest.raises(RuntimeError, match="boom"):
        async with dependency():
            raise RuntimeError("boom")

    assert fake.commits == 0
    assert fake.rollbacks == 1
    assert fake.closed is True


def test_engine_uses_pre_ping() -> None:
    assert sess.engine.pool._pre_ping is True
