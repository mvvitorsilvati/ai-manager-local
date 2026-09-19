import base64
import json

import httpx
import pytest

import app


@pytest.fixture(autouse=True)
def contas_isoladas(tmp_path, monkeypatch):
    monkeypatch.setattr(app, "CLAUDE_ACCOUNT", tmp_path / "sem-claude.json")
    monkeypatch.setattr(app, "CODEX_AUTH", tmp_path / "sem-auth.json")

PAYLOAD_ENTERPRISE = {
    "five_hour": {"utilization": 12.5, "resets_at": "2026-09-19T18:00:00Z"},
    "seven_day": {"utilization": 42.0, "resets_at": "2026-09-24T00:00:00Z"},
    "limits": [{"label": "Créditos", "percent": 50, "resets_at": "2026-09-30T21:00:00Z"}],
    "spend": {
        "used": {"amount_minor": 23670, "currency": "USD", "exponent": 2},
        "limit": {"amount_minor": 25000, "currency": "USD", "exponent": 2},
        "percent": 95,
        "severity": "critical",
        "enabled": True,
        "cap": {"resets_at": "2026-09-30T21:00:00Z"},
    },
}


def test_claude_account_le_email_do_oauth(tmp_path, monkeypatch):
    path = tmp_path / ".claude.json"
    path.write_text(json.dumps({"oauthAccount": {"emailAddress": "fulano@exemplo.com"}}))
    monkeypatch.setattr(app, "CLAUDE_ACCOUNT", path)
    assert app.claude_account() == "fulano@exemplo.com"


def test_claude_account_sem_arquivo_retorna_none():
    assert app.claude_account() is None


def test_codex_account_decodifica_id_token(tmp_path, monkeypatch):
    claims = base64.urlsafe_b64encode(json.dumps({"email": "fulano@exemplo.com"}).encode()).decode().rstrip("=")
    path = tmp_path / "auth.json"
    path.write_text(json.dumps({"tokens": {"id_token": f"cabecalho.{claims}.assinatura"}}))
    monkeypatch.setattr(app, "CODEX_AUTH", path)
    assert app.codex_account() == "fulano@exemplo.com"


def test_codex_account_com_token_invalido_retorna_none(tmp_path, monkeypatch):
    path = tmp_path / "auth.json"
    path.write_text(json.dumps({"tokens": {"id_token": "nao-e-um-jwt"}}))
    monkeypatch.setattr(app, "CODEX_AUTH", path)
    assert app.codex_account() is None


def test_github_account_prefere_email_e_cai_no_login(monkeypatch):
    class Resp:
        def __init__(self, payload):
            self.payload = payload

        def raise_for_status(self):
            pass

        def json(self):
            return self.payload

    monkeypatch.setattr(app.httpx, "get", lambda *a, **k: Resp({"email": "fulano@exemplo.com", "login": "fulano"}))
    assert app.github_account("token") == "fulano@exemplo.com"

    monkeypatch.setattr(app.httpx, "get", lambda *a, **k: Resp({"email": None, "login": "fulano"}))
    assert app.github_account("token") == "fulano"


def test_github_account_com_erro_http_retorna_none(monkeypatch):
    def boom(*args, **kwargs):
        raise httpx.ConnectError("sem rede")

    monkeypatch.setattr(app.httpx, "get", boom)
    assert app.github_account("token") is None


def test_parse_usage_windows_inclui_five_hour_seven_day_e_limits():
    windows = app.parse_usage_windows(PAYLOAD_ENTERPRISE)
    assert windows[0] == {"label": "Sessão (5h)", "utilization": 12.5, "resets_at": "2026-09-19T18:00:00Z"}
    assert windows[1]["label"] == "Semanal (7d)"
    assert windows[-1]["label"] == "Créditos"


def test_parse_usage_windows_ignora_janelas_nulas():
    assert app.parse_usage_windows({"five_hour": None, "seven_day": None, "limits": []}) == []


def test_parse_credits_converte_valores_e_reset():
    credits = app.parse_credits(PAYLOAD_ENTERPRISE)
    assert credits is not None
    assert (credits["used"], credits["limit"], credits["currency"]) == (236.7, 250.0, "USD")
    assert credits["severity"] == "critical"
    assert credits["resets_at"] == "2026-09-30T21:00:00Z"


def test_parse_credits_usa_extra_usage_como_fallback():
    payload = {
        "extra_usage": {
            "is_enabled": True, "used_credits": 10.0, "monthly_limit": 100.0,
            "currency": "USD", "utilization": 10.0,
        }
    }
    credits = app.parse_credits(payload)
    assert credits is not None
    assert credits["used"] == 10.0
    assert credits["resets_at"] is None


def test_parse_credits_desabilitado_retorna_none():
    assert app.parse_credits({"spend": {"enabled": False}, "extra_usage": {"is_enabled": False}}) is None


def test_claude_usage_sem_token_retorna_none(monkeypatch):
    monkeypatch.setattr(app, "claude_access_token", lambda: None)
    assert app.claude_usage() is None


def test_claude_usage_com_erro_http_retorna_none(monkeypatch):
    monkeypatch.setattr(app, "claude_access_token", lambda: "token")

    def boom(*args, **kwargs):
        raise httpx.ConnectError("sem rede")

    monkeypatch.setattr(app.httpx, "get", boom)
    assert app.claude_usage() is None


def test_claude_usage_parseia_resposta(monkeypatch):
    monkeypatch.setattr(app, "claude_access_token", lambda: "token")

    class Resp:
        def raise_for_status(self):
            pass

        def json(self):
            return PAYLOAD_ENTERPRISE

    monkeypatch.setattr(app.httpx, "get", lambda *a, **k: Resp())
    usage = app.claude_usage()
    assert usage is not None
    assert usage["available"] is True
    assert usage["credits"]["percent"] == 95
    assert len(usage["windows"]) == 3


def test_parse_codex_rate_limits_rotula_janelas():
    windows = app.parse_codex_rate_limits({
        "primary": {"used_percent": 83.0, "window_minutes": 300, "resets_at": 1789743133},
        "secondary": {"used_percent": 49.0, "window_minutes": 10080, "resets_at": 1789837486},
    })
    assert windows[0]["label"] == "Sessão (5h)"
    assert windows[0]["utilization"] == 83.0
    assert windows[0]["resets_at"] == "2026-09-18T14:52:13+00:00"
    assert windows[1]["label"] == "Semanal (7d)"


def test_codex_usage_le_ultimo_rollout(tmp_path, monkeypatch):
    day = tmp_path / "sessions" / "2026" / "09" / "18"
    day.mkdir(parents=True)
    rollout = day / "rollout-teste.jsonl"
    rate = {
        "primary": {"used_percent": 10.0, "window_minutes": 300, "resets_at": 1789743133},
        "plan_type": "plus",
        "credits": {"balance": "0"},
    }
    rollout.write_text('{"payload":{"type":"turn"}}\n' + json.dumps({"payload": {"rate_limits": rate}}) + "\n")
    monkeypatch.setattr(app, "CODEX_SESSIONS", tmp_path / "sessions")
    usage = app.codex_usage()
    assert usage is not None
    assert usage["plan"] == "plus"
    assert usage["windows"][0]["utilization"] == 10.0
    assert usage["updated_at"] > 0


def test_codex_usage_sem_sessoes_retorna_none(tmp_path, monkeypatch):
    monkeypatch.setattr(app, "CODEX_SESSIONS", tmp_path / "nao-existe")
    assert app.codex_usage() is None


def test_parse_copilot_quota_converte_percentual_e_ilimitados():
    payload = {
        "copilot_plan": "individual",
        "quota_reset_date": "2026-10-01",
        "quota_snapshots": {
            "chat": {"unlimited": True, "percent_remaining": 100.0},
            "completions": {"unlimited": True, "percent_remaining": 100.0},
            "premium_interactions": {"unlimited": False, "percent_remaining": 25.0, "entitlement": 200},
        },
    }
    usage = app.parse_copilot_quota(payload)
    assert usage["plan"] == "individual"
    assert usage["windows"] == [
        {"label": "Premium requests", "utilization": 75.0, "resets_at": "2026-10-01T00:00:00+00:00"}
    ]
    assert usage["unlimited"] == ["Chat", "Completions"]


def test_copilot_usage_sem_token_retorna_none(monkeypatch):
    monkeypatch.setattr(app, "github_token", lambda: None)
    assert app.copilot_usage() is None


def test_copilot_usage_com_erro_http_retorna_none(monkeypatch):
    monkeypatch.setattr(app, "github_token", lambda: "token")

    def boom(*args, **kwargs):
        raise httpx.ConnectError("sem rede")

    monkeypatch.setattr(app.httpx, "get", boom)
    assert app.copilot_usage() is None


def test_github_token_prefere_variavel_de_ambiente(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "abc123")
    assert app.github_token() == "abc123"
