import json

import app


def test_collect_plugins_deduplica_e_mescla(tmp_path, monkeypatch):
    claude = tmp_path / ".claude"
    (claude / "plugins").mkdir(parents=True)
    (claude / "settings.json").write_text(json.dumps({
        "enabledPlugins": {"audit@arco-ai-plugins": False, "core@arco-ai-plugins": True},
    }))
    (claude / "plugins" / "installed_plugins.json").write_text(json.dumps({
        "plugins": {"audit@arco-ai-plugins": [{"scope": "user", "version": "0.1.1"}]},
    }))
    opencode = tmp_path / ".config" / "opencode"
    opencode.mkdir(parents=True)
    (opencode / "opencode.jsonc").write_text('{"plugin": ["@dietrichgebert/ponytail"]}')
    monkeypatch.setattr(app, "HOME", tmp_path)
    monkeypatch.setattr(app, "OPENCODE_CONFIG", opencode / "opencode.jsonc")
    monkeypatch.setattr(app, "CLAUDE_SETTINGS", claude / "settings.json")
    monkeypatch.setattr(app, "CLAUDE_INSTALLED_PLUGINS", claude / "plugins" / "installed_plugins.json")

    plugins = app.collect_plugins()
    keys = [(p["source"], p["name"]) for p in plugins]
    assert len(keys) == len(set(keys)), "não deve haver plugin repetido por fonte"

    audit = next(p for p in plugins if p["name"] == "audit@arco-ai-plugins")
    assert audit["enabled"] is False  # settings.json manda no estado
    assert "version=0.1.1" in audit["detail"]  # detalhe do instalado é preservado
    assert next(p for p in plugins if p["name"] == "core@arco-ai-plugins")["enabled"] is True


def test_collect_project_plugins_deduplica_por_projeto(tmp_path):
    (tmp_path / "settings.json").write_text(json.dumps({"enabledPlugins": {"x@mkt": True}}))
    (tmp_path / "config.toml").write_text('[plugins."x@mkt"]\nenabled = true\n')
    proj = {
        "id": "proj:titulo",
        "root": str(tmp_path),
        "files": [
            {"n": "settings.json", "r": "settings.json"},
            {"n": "config.toml", "r": "config.toml"},
        ],
    }

    plugins = app.collect_project_plugins([proj])
    assert [p["name"] for p in plugins] == ["x@mkt"]
    assert plugins[0]["scope"] == "projeto"
