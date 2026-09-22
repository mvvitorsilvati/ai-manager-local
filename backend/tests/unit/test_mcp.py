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
    updated = app.toggle_json_mcp_enabled(OPENCODE_JSONC, "mcp", "context7", False)
    assert updated is not None
    assert '"enabled": false' in updated
    assert "// comentário com \"mcp\" e chaves { } para confundir" in updated
    assert "/* bloco */" in updated
    assert json.loads(app.strip_jsonc(updated))["mcp"]["context7"]["url"] == "https://mcp.context7.com/mcp"


def test_toggle_opencode_mcp_insere_enabled_quando_ausente():
    updated = app.toggle_json_mcp_enabled(OPENCODE_JSONC, "mcp", "linear", False)
    assert updated is not None
    linear_start = updated.index('"linear"')
    assert '"enabled": false' in updated[linear_start:]
    assert app.toggle_json_mcp_enabled(OPENCODE_JSONC, "mcp", "nao-existe", True) is None


def test_toggle_opencode_mcp_religa():
    desligado = app.toggle_json_mcp_enabled(OPENCODE_JSONC, "mcp", "context7", False)
    assert desligado is not None
    ligado = app.toggle_json_mcp_enabled(desligado, "mcp", "context7", True)
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
    monkeypatch.setattr(app, "all_tools", lambda: [{
        "id": "opencode", "label": "opencode", "root": str(opencode_dir),
        "mcp": {"rel": "opencode.jsonc", "container": "mcp", "kind": "json"},
    }])
    monkeypatch.setattr(app, "HOME", tmp_path)

    mcps = app.collect_mcps()
    assert mcps[0]["name"] == "linear"
    assert mcps[0]["file"] == {"s": "opencode", "r": "opencode.jsonc"}


def test_collect_mcps_inclui_os_do_claude_por_projeto(tmp_path, monkeypatch):
    (tmp_path / ".claude.json").write_text(json.dumps({
        "mcpServers": {"global-http": {"url": "https://x"}},
        "projects": {
            "/Users/x/Projetos/meu-projeto": {"mcpServers": {"playwright": {"command": "npx"}}},
        },
    }))
    monkeypatch.setattr(app, "HOME", tmp_path)
    monkeypatch.setattr(app, "all_tools", lambda: [])

    mcps = {m["name"]: m for m in app.collect_mcps()}
    assert mcps["global-http"]["file"] == {"s": "claude-global", "r": ".claude.json"}
    assert mcps["playwright"]["scope"] == "meu-projeto"
    assert mcps["playwright"]["type"] == "local"


def test_discovery_encontra_ia_com_mcp_json(tmp_path, monkeypatch):
    trae = tmp_path / ".trae"
    trae.mkdir()
    (trae / "mcp.json").write_text('{"mcpServers": {"linear": {"url": "https://x"}}}')
    monkeypatch.setattr(app, "HOME", tmp_path)
    monkeypatch.setattr(app, "_discovery_cache", (0.0, []))
    monkeypatch.setattr(app, "_index_cache", (0.0, ({}, {})))

    found = app.discovered_tools()
    assert found[0]["id"] == "trae"
    assert app.tool_for({"project": True}, ".trae/mcp.json", "mcp.json") == "trae"

    mcps = app.collect_mcps()
    trae_mcps = [m for m in mcps if m["source"] == "trae"]
    assert trae_mcps[0]["file"] == {"s": "trae", "r": "mcp.json"}


def test_discovery_encontra_ia_em_application_support(tmp_path, monkeypatch):
    trae = tmp_path / "Library" / "Application Support" / "Trae" / "User"
    trae.mkdir(parents=True)
    (trae / "mcp.json").write_text('{"mcpServers": {"linear": {"url": "https://x"}}}')
    monkeypatch.setattr(app, "HOME", tmp_path)
    monkeypatch.setattr(app, "_discovery_cache", (0.0, []))
    monkeypatch.setattr(app, "_index_cache", (0.0, ({}, {})))

    found = {t["id"]: t for t in app.discovered_tools()}
    assert found["trae"]["mcp"]["rel"] == "User/mcp.json"
    assert app.tool_for({"project": True}, "Trae/mcp.json", "mcp.json") == "trae"


def test_discovery_ignora_dirs_sem_assinatura(tmp_path, monkeypatch):
    (tmp_path / ".qualquercoisa").mkdir()
    (tmp_path / ".outra" / "sub").mkdir(parents=True)
    (tmp_path / ".outra" / "mcp.json").write_text('{"outra": true}')
    monkeypatch.setattr(app, "HOME", tmp_path)
    monkeypatch.setattr(app, "_discovery_cache", (0.0, []))

    assert app.discovered_tools() == []


def test_resolve_file_claude_global_apenas_o_arquivo(tmp_path, monkeypatch):
    arquivo = tmp_path / ".claude.json"
    arquivo.write_text("{}")
    monkeypatch.setattr(app, "CLAUDE_GLOBAL_FILE", arquivo)

    assert app.resolve_file("claude-global", ".claude.json") == arquivo
    with pytest.raises(ValueError):
        app.resolve_file("claude-global", "outro.json")
    with pytest.raises(ValueError):
        app.resolve_file("claude-global", "../.ssh/id_rsa")


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
