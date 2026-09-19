import httpx

import app


def test_statuspage_sem_incidentes():
    result = app._statuspage_incident({"status": {"indicator": "none", "description": "All Systems Operational"}})
    assert result == {"ok": True, "indicator": "none", "description": "All Systems Operational"}


def test_statuspage_com_incidente():
    result = app._statuspage_incident({"status": {"indicator": "major", "description": "Partial Outage"}})
    assert result["ok"] is False
    assert result["indicator"] == "major"


def test_statuspage_payload_vazio_nao_quebra():
    result = app._statuspage_incident({})
    assert result["ok"] is False


def test_google_incidentes_encerrados_ficam_ok():
    result = app._google_incident([{"severity": "medium", "end": "2026-09-01T18:52:00+00:00"}])
    assert result["ok"] is True


def test_google_incidente_ativo_usa_pior_severidade():
    result = app._google_incident([
        {"severity": "low", "external_desc": "leve"},
        {"severity": "high", "external_desc": "grave"},
    ])
    assert result["ok"] is False
    assert result["indicator"] == "high"
    assert result["description"] == "grave"


def test_incident_for_com_erro_http_retorna_none(monkeypatch):
    def boom(*args, **kwargs):
        raise httpx.ConnectError("sem rede")

    monkeypatch.setattr(app.httpx, "get", boom)
    monkeypatch.setattr(app, "_status_json", lambda url: None)
    assert app.incident_for("claude") is None


def test_status_json_cai_para_curl_quando_httpx_falha(monkeypatch):
    def boom(*args, **kwargs):
        raise httpx.ConnectError("certificado do proxy")

    class Proc:
        returncode = 0
        stdout = '{"status": {"indicator": "none", "description": "All Systems Operational"}}'

    monkeypatch.setattr(app.httpx, "get", boom)
    monkeypatch.setattr(app.subprocess, "run", lambda *a, **k: Proc())
    payload = app._status_json("https://exemplo.test/status.json")
    assert payload is not None
    assert payload["status"]["indicator"] == "none"


def test_incident_for_desconhecido_retorna_none():
    assert app.incident_for("opencode") is None


def test_incidents_snapshot_monta_por_fonte(monkeypatch):
    monkeypatch.setattr(
        app, "incident_for",
        lambda source: {"ok": source != "codex", "indicator": "major", "description": source},
    )
    snapshot = app.incidents_snapshot(force=True)
    assert snapshot["sources"]["codex"]["ok"] is False
    assert snapshot["sources"]["claude"]["ok"] is True
    app._incidents_cache = (0.0, {})
