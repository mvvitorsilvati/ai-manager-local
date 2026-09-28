import base64
import json
import os

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
    # 236,7/250 = 94,68% — o percent exato das unidades menores, não o 95 arredondado do payload.
    assert credits["percent"] == 94.7
    assert credits["resets_at"] == "2026-09-30T21:00:00Z"


def test_parse_credits_prefere_extra_usage_e_converte_unidades_menores():
    payload = {
        "extra_usage": {
            "is_enabled": True, "used_credits": 32784.0, "monthly_limit": 55000,
            "utilization": 59.60727272727273, "currency": "BRL", "decimal_places": 2,
        },
        "spend": {
            "used": {"amount_minor": 32784, "currency": "BRL", "exponent": 2},
            "limit": {"amount_minor": 55000, "currency": "BRL", "exponent": 2},
            "percent": 60, "enabled": True, "severity": "warning",
        },
    }
    credits = app.parse_credits(payload)
    assert credits is not None
    # Unidades menores: 55000 = R$ 550,00 (forma real da resposta, como na referência).
    assert (credits["used"], credits["limit"], credits["currency"]) == (327.84, 550.0, "BRL")
    assert credits["percent"] == 59.6
    assert credits["severity"] == "warning"


def test_parse_credits_extra_usage_sem_limite_cai_no_spend():
    payload = {
        "extra_usage": {"is_enabled": True, "used_credits": None, "monthly_limit": None},
        "spend": {
            "used": {"amount_minor": 55134, "currency": "USD", "exponent": 2},
            "limit": {"amount_minor": 57000, "currency": "USD", "exponent": 2},
            "enabled": True,
        },
    }
    credits = app.parse_credits(payload)
    assert credits is not None
    assert (credits["used"], credits["limit"]) == (551.34, 570.0)
    assert credits["percent"] == 96.7


def test_parse_credits_extra_usage_desabilitado_esconde_mesmo_com_spend_ligado():
    payload = {
        "extra_usage": {"is_enabled": False},
        "spend": {
            "enabled": True,
            "used": {"amount_minor": 100, "currency": "USD", "exponent": 2},
            "limit": {"amount_minor": 1000, "currency": "USD", "exponent": 2},
        },
    }
    assert app.parse_credits(payload) is None


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


def test_claude_usage_envia_user_agent_do_claude_code(monkeypatch):
    monkeypatch.setattr(app, "claude_access_token", lambda: "token")
    capturado: dict = {}

    class Resp:
        def raise_for_status(self):
            pass

        def json(self):
            return {}

    def fake_get(url, **kwargs):
        capturado.update(kwargs.get("headers") or {})
        return Resp()

    monkeypatch.setattr(app.httpx, "get", fake_get)
    app.claude_usage()
    # Sem o UA do Claude Code o endpoint responde 429 direto.
    assert capturado["User-Agent"] == "claude-code/1.0.0"
    assert capturado["anthropic-beta"] == "oauth-2025-04-20"


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
    assert usage["credits"]["percent"] == 94.7
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


def test_parse_codex_rate_limits_rotula_pela_duracao_nao_pela_posicao():
    windows = app.parse_codex_rate_limits({
        "primary": {"used_percent": 49.0, "window_minutes": 10080},
        "secondary": {"used_percent": 83.0, "window_minutes": 300},
    })
    assert [w["label"] for w in windows] == ["Semanal (7d)", "Sessão (5h)"]


def test_parse_codex_rate_limits_janela_mensal_e_sem_duracao():
    windows = app.parse_codex_rate_limits({
        "primary": {"used_percent": 10.0, "window_minutes": 40320},
        "secondary": {"used_percent": 20.0},
    })
    assert [w["label"] for w in windows] == ["Mensal (28d)", "Semanal"]


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


def test_codex_usage_usa_rollout_anterior_quando_o_mais_novo_ainda_nao_tem_rate_limits(tmp_path, monkeypatch):
    day = tmp_path / "sessions" / "2026" / "09" / "18"
    day.mkdir(parents=True)
    antigo = day / "rollout-antigo.jsonl"
    rate = {"primary": {"used_percent": 21.0, "window_minutes": 300, "resets_at": 1789743133}, "plan_type": "plus"}
    antigo.write_text(json.dumps({"payload": {"rate_limits": rate}}) + "\n")
    novo = day / "rollout-novo.jsonl"
    novo.write_text('{"payload":{"type":"turn"}}\n')
    os.utime(antigo, (1_700_000_000, 1_700_000_000))
    os.utime(novo, (1_700_000_100, 1_700_000_100))
    monkeypatch.setattr(app, "CODEX_SESSIONS", tmp_path / "sessions")

    usage = app.codex_usage()
    assert usage is not None
    assert usage["windows"][0]["utilization"] == 21.0
    assert usage["updated_at"] == 1_700_000_000


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


def test_usage_snapshot_com_tool_atualiza_so_a_ia_pedida(monkeypatch):
    chamadas: list[str] = []

    def provider(nome: str, payload: dict):
        def fake():
            chamadas.append(nome)
            return payload

        monkeypatch.setattr(app, f"{nome}_usage", fake)

    provider("claude", {"available": True, "windows": []})
    provider("codex", {"available": True, "plan": "plus", "windows": []})
    provider("copilot", {"available": True, "windows": []})
    provider("gemini", {"available": True, "windows": []})
    monkeypatch.setattr(app, "_usage_cache", (0.0, {}))

    assert set(app.usage_snapshot()) == {"claude", "codex", "copilot", "gemini"}
    chamadas.clear()

    parcial = app.usage_snapshot(force=True, tool="codex")
    assert set(parcial) == {"codex"}
    assert parcial["codex"]["plan"] == "plus"
    assert chamadas == ["codex"]

    chamadas.clear()
    assert set(app.usage_snapshot(tool="claude")) == {"claude"}
    assert chamadas == []
    assert set(app._usage_cache[1]) == {"claude", "codex", "copilot", "gemini"}


def test_parse_gemini_quota_extrai_janelas_de_5h_e_7d():
    quota = {
        "gemini-5h": {
            "remaining_fraction": 0.95,
            "reset_time": "2026-09-27T14:00:00Z",
        },
        "gemini-weekly": {
            "remaining_fraction": 0.40,
            "reset_time": "2026-10-04T09:00:00Z",
        },
        "3p-5h": {
            "remaining_fraction": 1.0,
        },
        "3p-weekly": {
            "remaining_fraction": 0.85,
            "reset_time": "2026-10-04T09:00:00Z",
        },
    }
    windows = app.parse_gemini_quota(quota)
    assert len(windows) == 3
    assert windows[0]["label"] == "Sessão (5h)"
    assert windows[0]["utilization"] == 5.0
    assert windows[0]["resets_at"] == "2026-09-27T14:00:00Z"

    assert windows[1]["label"] == "Semanal (7d)"
    assert windows[1]["utilization"] == 60.0

    # 3p-5h com 0% de uso foi omitido, mas 3p-weekly com 15% aparece
    assert windows[2]["label"] == "3P · Semanal (7d)"
    assert windows[2]["utilization"] == 15.0


def test_parse_gemini_quota_janela_intocada_sem_reset_conhecido():
    windows = app.parse_gemini_quota({
        "gemini-5h": {"remaining_fraction": 1.0, "reset_time": "2026-09-27T14:00:00Z"},
        "gemini-weekly": {"remaining_fraction": 0.5, "reset_time": "2026-10-04T09:00:00Z"},
    })
    # Com a janela intocada o CLI devolve "agora + 7d" como reset, que anda a cada leitura.
    assert windows[0]["utilization"] == 0.0
    assert windows[0]["resets_at"] is None
    assert windows[1]["resets_at"] == "2026-10-04T09:00:00Z"


def test_gemini_usage_retorna_dados_do_payload(tmp_path, monkeypatch):
    payload_file = tmp_path / "latest_status.json"
    payload_file.write_text(
        json.dumps({
            "plan_tier": "Google AI Pro",
            "email": "dev@example.com",
            "quota": {
                "gemini-5h": {"remaining_fraction": 0.90, "reset_time": "2026-09-27T14:00:00Z"},
            },
        }),
        encoding="utf-8",
    )
    monkeypatch.setattr(app, "ANTIGRAVITY_CACHE_STATUS", payload_file)
    monkeypatch.setattr(app, "ANTIGRAVITY_PAYLOAD", tmp_path / "inexistente.json")
    monkeypatch.setattr(app, "gemini_account", lambda: "dev@example.com")

    usage = app.gemini_usage()
    assert usage is not None
    assert usage["available"] is True
    assert usage["plan"] == "Google AI Pro"
    assert usage["account"] == "dev@example.com"
    assert len(usage["windows"]) == 1
    assert usage["windows"][0]["utilization"] == 10.0


def test_gemini_usage_sem_conta_e_sem_payload_retorna_none(tmp_path, monkeypatch):
    monkeypatch.setattr(app, "ANTIGRAVITY_CACHE_STATUS", tmp_path / "inexistente1.json")
    monkeypatch.setattr(app, "ANTIGRAVITY_PAYLOAD", tmp_path / "inexistente2.json")
    monkeypatch.setattr(app, "gemini_account", lambda: None)

    assert app.gemini_usage() is None


def test_gemini_usage_sem_payload_nao_inventa_plano(tmp_path, monkeypatch):
    monkeypatch.setattr(app, "ANTIGRAVITY_CACHE_STATUS", tmp_path / "inexistente1.json")
    monkeypatch.setattr(app, "ANTIGRAVITY_PAYLOAD", tmp_path / "inexistente2.json")
    monkeypatch.setattr(app, "gemini_account", lambda: "dev@example.com")

    usage = app.gemini_usage()
    assert usage is not None
    assert usage["plan"] is None
    assert usage["windows"] == []

