import base64
import json

import httpx
import pytest

import app


@pytest.fixture(autouse=True)
def arquivos_isolados(tmp_path, monkeypatch):
    monkeypatch.setattr(app, "OPENCODE_AUTH", tmp_path / "sem-auth.json")
    monkeypatch.setattr(app, "OPENCODE_CONFIG", tmp_path / "sem-opencode.jsonc")
    monkeypatch.setattr(app, "OPENCODE_PACKAGES", tmp_path / "sem-packages")
    monkeypatch.setattr(app, "CLAUDE_INSTALLED_PLUGINS", tmp_path / "sem-installed.json")
    monkeypatch.setattr(app, "CLAUDE_MARKETPLACES", tmp_path / "sem-marketplaces.json")
    monkeypatch.setattr(app, "CLAUDE_SETTINGS", tmp_path / "sem-settings.json")


def _jwt(payload: dict) -> str:
    body = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    return f"cabecalho.{body}.assinatura"


def test_has_update_compara_versoes():
    assert app.has_update("1.0.1", "1.0.0") is True
    assert app.has_update("1.0.0", "1.0.0") is False
    assert app.has_update(None, "1.0.0") is None
    assert app.has_update("1.0.0", None) is None


def test_cli_version_extrai_numero_do_output(monkeypatch):
    class Proc:
        stdout = "GitHub Copilot CLI 1.0.86."
        stderr = ""

    monkeypatch.setattr(app.subprocess, "run", lambda *a, **k: Proc())
    assert app.cli_version("copilot") == "1.0.86"


def test_cli_version_sem_binario_retorna_none(monkeypatch):
    def boom(*args, **kwargs):
        raise FileNotFoundError("nao existe")

    monkeypatch.setattr(app.subprocess, "run", boom)
    assert app.cli_version("cursor") is None


def test_npm_latest_le_versao_do_registry(monkeypatch):
    class Resp:
        def raise_for_status(self):
            pass

        def json(self):
            return {"version": "9.9.9"}

    monkeypatch.setattr(app.httpx, "get", lambda *a, **k: Resp())
    assert app.npm_latest("@openai/codex") == "9.9.9"


def test_npm_latest_com_erro_http_retorna_none(monkeypatch):
    def boom(*args, **kwargs):
        raise httpx.ConnectError("sem rede")

    monkeypatch.setattr(app.httpx, "get", boom)
    assert app.npm_latest("opencode-ai") is None


def test_opencode_account_le_email_do_jwt(tmp_path, monkeypatch):
    auth = tmp_path / "auth.json"
    token = _jwt({"https://api.openai.com/profile": {"email": "fulano@exemplo.com"}})
    auth.write_text(json.dumps({"openai": {"access": token}}))
    monkeypatch.setattr(app, "OPENCODE_AUTH", auth)
    assert app.opencode_account() == "fulano@exemplo.com"


def test_opencode_account_sem_jwt_retorna_none(tmp_path, monkeypatch):
    auth = tmp_path / "auth.json"
    auth.write_text(json.dumps({"openrouter": {"key": "chave-de-api"}}))
    monkeypatch.setattr(app, "OPENCODE_AUTH", auth)
    assert app.opencode_account() is None


def test_opencode_plugin_version_le_do_cache(tmp_path, monkeypatch):
    manifest = tmp_path / "@dietrichgebert/ponytail@latest/node_modules/@dietrichgebert/ponytail/package.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(json.dumps({"version": "4.10.0"}))
    monkeypatch.setattr(app, "OPENCODE_PACKAGES", tmp_path)
    assert app.opencode_plugin_version("@dietrichgebert/ponytail") == "4.10.0"


def _escrever_marketplace(base, name: str, plugins: dict[str, str | None], snapshot: str | None) -> str:
    location = base / name
    (location / ".claude-plugin").mkdir(parents=True)
    entries = [{"name": plugin, **({"version": version} if version else {})} for plugin, version in plugins.items()]
    (location / ".claude-plugin" / "marketplace.json").write_text(json.dumps({"plugins": entries}))
    if snapshot:
        (location / ".gcs-sha").write_text(snapshot)
    return str(location)


def test_claude_plugin_updates_compara_versao_declarada(tmp_path, monkeypatch):
    location_oficial = _escrever_marketplace(tmp_path, "claude-plugins-official", {"context7": "2.0.0"}, "abc123")
    location_exemplo = _escrever_marketplace(tmp_path, "exemplo", {"core": "0.62.2"}, None)
    installed = tmp_path / "installed.json"
    installed.write_text(json.dumps({"plugins": {
        "context7@claude-plugins-official": [{"version": "2.0.0"}],
        "core@exemplo": [{"version": "0.61.0"}],
    }}))
    marketplaces = tmp_path / "known.json"
    marketplaces.write_text(json.dumps({
        "claude-plugins-official": {"installLocation": location_oficial},
        "exemplo": {"installLocation": location_exemplo},
    }))
    settings = tmp_path / "settings.json"
    settings.write_text(json.dumps({"extraKnownMarketplaces": {"exemplo": {"autoUpdate": True}}}))
    monkeypatch.setattr(app, "CLAUDE_INSTALLED_PLUGINS", installed)
    monkeypatch.setattr(app, "CLAUDE_MARKETPLACES", marketplaces)
    monkeypatch.setattr(app, "CLAUDE_SETTINGS", settings)

    updates = {u["name"]: u for u in app.claude_plugin_updates()}
    assert updates["context7@claude-plugins-official"]["update"] is False
    assert updates["core@exemplo"]["update"] is True
    assert updates["core@exemplo"]["latest"] == "0.62.2"
    assert updates["core@exemplo"]["auto_update"] is True
    assert updates["context7@claude-plugins-official"]["auto_update"] is True  # oficial: ligado por padrão


def test_claude_plugin_updates_usa_snapshot_quando_sem_versao(tmp_path, monkeypatch):
    location = _escrever_marketplace(
        tmp_path, "oficial", {"context7": None}, "c447c3207a425bc4e2a0d068435f64b0477ae981",
    )
    installed = tmp_path / "installed.json"
    installed.write_text(json.dumps({"plugins": {
        "context7@oficial": [{"version": "c447c3207a42"}],
        "code-review@oficial": [{"version": "000000000000"}],
    }}))
    marketplaces = tmp_path / "known.json"
    marketplaces.write_text(json.dumps({"oficial": {"installLocation": location}}))
    monkeypatch.setattr(app, "CLAUDE_INSTALLED_PLUGINS", installed)
    monkeypatch.setattr(app, "CLAUDE_MARKETPLACES", marketplaces)

    updates = {u["name"]: u for u in app.claude_plugin_updates()}
    assert updates["context7@oficial"]["update"] is False
    assert updates["code-review@oficial"]["update"] is True


def test_claude_plugin_updates_sem_marketplace_nao_marca_update(tmp_path, monkeypatch):
    installed = tmp_path / "installed.json"
    installed.write_text(json.dumps({"plugins": {"plugin-sem-marketplace": [{"version": "1.0.0"}]}}))
    monkeypatch.setattr(app, "CLAUDE_INSTALLED_PLUGINS", installed)
    monkeypatch.setattr(app, "CLAUDE_MARKETPLACES", tmp_path / "sem.json")

    updates = app.claude_plugin_updates()
    assert updates[0]["update"] is None
    assert updates[0]["auto_update"] is None


def test_claude_plugin_updates_nao_sinaliza_downgrade(tmp_path, monkeypatch):
    location = tmp_path / "oficial"
    (location / ".claude-plugin").mkdir(parents=True)
    (location / ".claude-plugin" / "marketplace.json").write_text(json.dumps({"plugins": [
        {"name": "seguranca", "version": "2.0.7", "source": "./plugins/seguranca"},
    ]}))
    (location / "plugins" / "seguranca" / ".claude-plugin").mkdir(parents=True)
    (location / "plugins" / "seguranca" / ".claude-plugin" / "plugin.json").write_text(
        json.dumps({"version": "2.0.8"})
    )
    installed = tmp_path / "installed.json"
    installed.write_text(json.dumps({"plugins": {"seguranca@oficial": [{"version": "2.0.8"}]}}))
    marketplaces = tmp_path / "known.json"
    marketplaces.write_text(json.dumps({"oficial": {"installLocation": str(location)}}))
    monkeypatch.setattr(app, "CLAUDE_INSTALLED_PLUGINS", installed)
    monkeypatch.setattr(app, "CLAUDE_MARKETPLACES", marketplaces)

    update = app.claude_plugin_updates()[0]
    assert update["latest"] == "2.0.8"
    assert update["update"] is False


def test_update_command_por_metodo_de_instalacao(monkeypatch):
    monkeypatch.setattr(app.shutil, "which", lambda name: f"/usr/local/bin/{name}")

    monkeypatch.setattr(app.os.path, "realpath", lambda path: "/opt/homebrew/Caskroom/codex/0.154.0/bin/codex")
    assert app.update_command("codex") == ["/usr/local/bin/brew", "upgrade", "--cask", "codex"]

    monkeypatch.setattr(app.os.path, "realpath", lambda path: "/opt/homebrew/Cellar/opencode/1.18.31/bin/opencode")
    assert app.update_command("opencode") == ["/usr/local/bin/brew", "upgrade", "opencode"]

    monkeypatch.setattr(
        app.os.path, "realpath",
        lambda path: "/x/fnm/node-versions/v24/lib/node_modules/@github/copilot/npm-loader.js",
    )
    assert app.update_command("copilot") == ["npm", "install", "-g", "@github/copilot@latest"]

    monkeypatch.setattr(app.os.path, "realpath", lambda path: "/opt/x/bin/gemini")
    assert app.update_command("gemini") is None
    assert app.update_command("cursor") is None


def test_update_command_sem_binario_retorna_none(monkeypatch):
    monkeypatch.setattr(app.shutil, "which", lambda name: None)
    assert app.update_command("claude") is None


def test_run_update_rejeita_ferramenta_desconhecida():
    with pytest.raises(app.ApiError):
        app.run_update("cursor")


def test_run_command_captura_saida(monkeypatch):
    class Proc:
        returncode = 1
        stdout = "baixando...\n"
        stderr = "erro qualquer"

    monkeypatch.setattr(app.subprocess, "run", lambda *a, **k: Proc())
    result = app._run_command(["echo", "oi"])
    assert result["ok"] is False
    assert result["command"] == "echo oi"
    assert "erro qualquer" in result["output"]


def test_run_plugin_update_valida_plugin(tmp_path, monkeypatch):
    installed = tmp_path / "installed.json"
    installed.write_text(json.dumps({"plugins": {"audit@plugins-exemplo": [{"version": "0.1.1"}]}}))
    monkeypatch.setattr(app, "CLAUDE_INSTALLED_PLUGINS", installed)

    with pytest.raises(app.ApiError):
        app.run_plugin_update("claude", "nao-existe@x")
    with pytest.raises(app.ApiError):
        app.run_plugin_update("opencode", "@dietrichgebert/ponytail")
    with pytest.raises(app.ApiError):
        app.run_plugin_update("codex", "github@openai-curated")


def test_run_plugin_update_opencode_usa_comando_oficial(tmp_path, monkeypatch):
    config = tmp_path / "opencode.jsonc"
    config.write_text('{"plugin": ["@dietrichgebert/ponytail"]}')
    monkeypatch.setattr(app, "OPENCODE_CONFIG", config)
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
    result = app.run_plugin_update("opencode", "@dietrichgebert/ponytail")
    assert result["ok"] is True
    assert captured["command"] == ["/usr/local/bin/opencode", "plugin", "@dietrichgebert/ponytail", "-g", "--force"]


def test_run_plugin_update_claude_usa_comando_oficial(tmp_path, monkeypatch):
    installed = tmp_path / "installed.json"
    installed.write_text(json.dumps({"plugins": {"audit@plugins-exemplo": [{"version": "0.1.1"}]}}))
    monkeypatch.setattr(app, "CLAUDE_INSTALLED_PLUGINS", installed)
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
    app.run_plugin_update("claude", "audit@plugins-exemplo")
    assert captured["command"] == ["/usr/local/bin/claude", "plugin", "update", "audit@plugins-exemplo", "-y"]


def test_versions_snapshot_inclui_comando_de_update(monkeypatch):
    monkeypatch.setattr(app, "cli_version", lambda binary: "1.0.0")
    monkeypatch.setattr(app, "npm_latest", lambda package: "1.0.0")
    monkeypatch.setattr(app, "update_command", lambda tool: ["brew", "upgrade", tool])
    monkeypatch.setattr(app, "opencode_account", lambda: None)
    monkeypatch.setattr(app, "claude_account", lambda: None)
    monkeypatch.setattr(app, "codex_account", lambda: None)
    monkeypatch.setattr(app, "github_token", lambda: None)
    monkeypatch.setattr(app, "plugin_updates", lambda: [])

    snapshot = app.versions_snapshot(force=True)
    assert snapshot["tools"]["opencode"]["command"] == "brew upgrade opencode"
    assert snapshot["tools"]["opencode"]["update"] is False
    app._versions_cache = (0.0, {})


def test_set_plugin_auto_update_grava_no_settings(tmp_path, monkeypatch):
    claude_dir = tmp_path / "claude"
    claude_dir.mkdir()
    settings = claude_dir / "settings.json"
    settings.write_text(json.dumps({
        "enabledPlugins": {"audit@plugins-exemplo": True},
        "extraKnownMarketplaces": {"plugins-exemplo": {"autoUpdate": False}},
    }))
    monkeypatch.setitem(
        app.SOURCE_BY_ID,
        "claude",
        {
            "id": "claude", "label": "Claude Code", "root": str(claude_dir),
            "exclude_dirs": set(), "exclude_files": set(),
        },
    )
    monkeypatch.setattr(app, "CLAUDE_INSTALLED_PLUGINS", tmp_path / "sem-installed.json")
    monkeypatch.setattr(app, "CLAUDE_SETTINGS", settings)
    marketplaces = tmp_path / "known.json"
    marketplaces.write_text(json.dumps({
        "plugins-exemplo": {"source": {"source": "git", "url": "git@github.com:exemplo/plugins-exemplo.git"}},
    }))
    monkeypatch.setattr(app, "CLAUDE_MARKETPLACES", marketplaces)

    result = app.set_plugin_auto_update("audit@plugins-exemplo", True)
    assert result["ok"] is True
    saved = json.loads(settings.read_text())
    entry = saved["extraKnownMarketplaces"]["plugins-exemplo"]
    assert entry["autoUpdate"] is True
    assert entry["source"]["url"] == "git@github.com:exemplo/plugins-exemplo.git"


def test_set_plugin_auto_update_rejeita_plugin_desconhecido():
    with pytest.raises(app.ApiError):
        app.set_plugin_auto_update("nao-existe@x", True)
