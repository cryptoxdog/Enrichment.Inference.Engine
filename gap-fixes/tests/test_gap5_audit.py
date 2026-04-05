"""Gap-5 tests: PostgreSQL audit persistence."""
import asyncio, pytest
from unittest.mock import AsyncMock, MagicMock, patch
import shared.audit_persistence as ap


@pytest.fixture(autouse=True)
def reset_pool():
    ap._POOL = None
    yield
    ap._POOL = None


@pytest.mark.asyncio
async def test_flush_without_pool_logs_error_returns_zero():
    entries = [{"tenant_id": "t1", "actor": "sys", "action": "enrich", "detail": "x"}]
    result = await ap.flush_audit_entries(entries)
    assert result == 0


@pytest.mark.asyncio
async def test_flush_empty_returns_zero():
    ap._POOL = MagicMock()  # pool present but no entries
    result = await ap.flush_audit_entries([])
    assert result == 0


@pytest.mark.asyncio
async def test_configure_creates_schema():
    mock_conn = AsyncMock()
    mock_pool = MagicMock()
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    await ap.configure_audit_pool(mock_pool)
    mock_conn.execute.assert_awaited_once()
    assert "audit_log" in mock_conn.execute.call_args[0][0]


@pytest.mark.asyncio
async def test_flush_with_pool_inserts_rows():
    mock_conn = AsyncMock()
    mock_pool = MagicMock()
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    ap._POOL = mock_pool
    entries = [
        {"tenant_id": "t1", "actor": "sys", "action": "enrich", "detail": "d1"},
        {"tenant_id": "t1", "actor": "sys", "action": "infer",  "detail": "d2"},
    ]
    result = await ap.flush_audit_entries(entries)
    assert result == 2
    mock_conn.executemany.assert_awaited_once()
