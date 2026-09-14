# tests/test_medplum_retry.py — Milestone: EHR reliability (retry/backoff §15.1)
import httpx
import pytest

from src.database import medplum_client as mc


@pytest.fixture(autouse=True)
def fast_backoff(monkeypatch):
    monkeypatch.setattr(mc, "_RETRY_BASE_DELAY", 0.001)


class _Resp:
    def __init__(self, status): self.status_code = status
    def json(self): return {"ok": True}
    @property
    def text(self): return "{}"


async def test_retries_then_succeeds(monkeypatch):
    calls = {"n": 0}

    async def flaky(self, method, url, **kw):
        calls["n"] += 1
        if calls["n"] < 3:
            raise httpx.ConnectError("boom")
        return _Resp(200)

    monkeypatch.setattr(httpx.AsyncClient, "request", flaky)
    client = mc.MedplumClient("https://x", "id", "secret")
    resp = await client._send("GET", "https://x/fhir/R4/Patient", headers={})
    assert resp.status_code == 200
    assert calls["n"] == 3


async def test_raises_after_exhausting_retries(monkeypatch):
    calls = {"n": 0}

    async def always_fail(self, method, url, **kw):
        calls["n"] += 1
        raise httpx.ConnectTimeout("nope")

    monkeypatch.setattr(httpx.AsyncClient, "request", always_fail)
    client = mc.MedplumClient("https://x", "id", "secret")
    with pytest.raises(httpx.ConnectTimeout):
        await client._send("GET", "https://x/fhir/R4/Patient", headers={})
    assert calls["n"] == mc._MAX_RETRIES


async def test_retries_on_5xx(monkeypatch):
    calls = {"n": 0}

    async def five_then_ok(self, method, url, **kw):
        calls["n"] += 1
        return _Resp(503) if calls["n"] < 2 else _Resp(200)

    monkeypatch.setattr(httpx.AsyncClient, "request", five_then_ok)
    client = mc.MedplumClient("https://x", "id", "secret")
    resp = await client._send("GET", "https://x/fhir/R4/Slot", headers={})
    assert resp.status_code == 200 and calls["n"] == 2
