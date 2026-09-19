import json

import pytest

import app

OPENCODE_JSONC = """{
  // comentário com "mcp" e chaves { } para confundir
  "mcp": {
    "context7": {
      "type": "remote",
      "url": "https://mcp.context7.com/mcp",
      "enabled": true,
    },
    "linear": {
      /* bloco */
      "type": "remote",
    },
  },
  "plugin": ["@dietrichgebert/ponytail"],
}
"""

CODEX_TOML = """model = "gpt-5"

[mcp_servers.context7]
url = "https://mcp.context7.com/mcp"
enabled = true

[mcp_servers.linear]
command = "npx"
args = ["-y", "mcp-remote"]

[profiles.default]
model = "gpt-5"
"""


def test_toggle_opencode_mcp_desliga_preservando_comentarios():
    updated = app.toggle_opencode_mcp_enabled(OPENCODE_JSONC, "context7", False)
    assert updated is not None
    assert '"enabled": false' in updated
    assert "// comentário com \"mcp\" e chaves { } para confundir" in updated
    assert "/* bloco */" in updated
    assert json.loads(app.strip_jsonc(updated))["mcp"]["context7"]["url"] == "https://mcp.context7.com/mcp"


def test_toggle_opencode_mcp_insere_enabled_quando_ausente():
    updated = app.toggle_opencode_mcp_enabled(OPENCODE_JSONC, "linear", False)
    assert updated is not None
    linear_start = updated.index('"linear"')
    assert '"enabled": false' in updated[linear_start:]
    assert app.toggle_opencode_mcp_enabled(OPENCODE_JSONC, "nao-existe", True) is None


def test_toggle_opencode_mcp_religa():
    desligado = app.toggle_opencode_mcp_enabled(OPENCODE_JSONC, "context7", False)
    assert desligado is not None
    ligado = app.toggle_opencode_mcp_enabled(desligado, "context7", True)
    assert ligado is not None
    assert '"enabled": true' in ligado


def test_toggle_codex_mcp_desliga_na_secao():
    updated = app.toggle_codex_mcp_enabled(CODEX_TOML, "context7", False)
    assert updated is not None
    assert "enabled = false" in updated
    assert '[profiles.default]\nmodel = "gpt-5"' in updated


def test_toggle_codex_mcp_insere_enabled_quando_ausente():
    updated = app.toggle_codex_mcp_enabled(CODEX_TOML, "linear", False)
    assert updated is not None
    linear = updated.split("[mcp_servers.linear]")[1].split("[profiles")[0]
    assert "enabled = false" in linear
    assert app.toggle_codex_mcp_enabled(CODEX_TOML, "nao-existe", True) is None


def test_collect_mcps_inclui_arquivo_de_origem(tmp_path, monkeypatch):
    opencode_dir = tmp_path / "opencode"
    opencode_dir.mkdir()
    (opencode_dir / "opencode.jsonc").write_text(
        '{"mcp": {"linear": {"type": "remote", "url": "https://mcp.linear.app/mcp"}}}'
    )
    monkeypatch.setitem(
        app.SOURCE_BY_ID,
        "opencode",
        {
            "id": "opencode", "label": "opencode", "root": str(opencode_dir),
            "exclude_dirs": set(), "exclude_files": set(),
        },
    )
    monkeypatch.setattr(app, "MCP_GLOBAL_FILES", (("opencode", "opencode.jsonc"),))
    monkeypatch.setattr(app, "HOME", tmp_path)

    mcps = app.collect_mcps()
    assert mcps[0]["name"] == "linear"
    assert mcps[0]["file"] == {"s": "opencode", "r": "opencode.jsonc"}


def test_run_mcp_action_rejeita_desconhecido(monkeypatch):
    monkeypatch.setattr(app, "collect_mcps", lambda: [{"name": "context7", "source": "opencode"}])
    with pytest.raises(app.ApiError):
        app.run_mcp_action("opencode", "nao-existe", "enable")
    with pytest.raises(app.ApiError):
        app.run_mcp_action("copilot", "context7", "enable")


def test_run_mcp_action_usa_cli_quando_suportado(monkeypatch):
    monkeypatch.setattr(app, "collect_mcps", lambda: [{"name": "context7", "source": "gemini"}])
    monkeypatch.setattr(app.shutil, "which", lambda name: f"/usr/local/bin/{name}")
    captured: dict[str, list[str]] = {}

    class Proc:
        returncode = 0
        stdout = "ok"
        stderr = ""

    def fake_run(command, **kwargs):
        captured["command"] = command
        return Proc()

    monkeypatch.setattr(app.subprocess, "run", fake_run)
    result = app.run_mcp_action("gemini", "context7", "disable")
    assert result["ok"] is True
    assert captured["command"] == ["/usr/local/bin/gemini", "mcp", "disable", "context7"]

    with pytest.raises(app.ApiError):
        app.run_mcp_action("gemini", "context7", "login")


def test_run_mcp_action_edita_config_do_opencode(tmp_path, monkeypatch):
    root = tmp_path / "opencode"
    root.mkdir()
    (root / "opencode.jsonc").write_text(OPENCODE_JSONC)
    monkeypatch.setitem(
        app.SOURCE_BY_ID,
        "opencode",
        {
            "id": "opencode", "label": "opencode", "root": str(root),
            "exclude_dirs": set(), "exclude_files": set(),
        },
    )
    monkeypatch.setattr(app, "collect_mcps", lambda: [{"name": "context7", "source": "opencode"}])

    result = app.run_mcp_action("opencode", "context7", "disable")
    assert result["ok"] is True
    assert '"enabled": false' in (root / "opencode.jsonc").read_text()
    assert result["backup"]
