from pathlib import Path

import app


class TestInstallableTools:
    def test_get_installable_tools_returns_uninstalled_by_default(self, monkeypatch):
        # Simula que apenas 'claude' está instalado no catálogo
        monkeypatch.setattr(app, "build_catalog", lambda: {"tools": [{"id": "claude"}]})
        # Força binários a não existirem exceto claude
        monkeypatch.setattr(
            app.shutil,
            "which",
            lambda binary: "/usr/local/bin/claude" if binary == "claude" else None,
        )
        # Força pastas de config e apps a não existirem
        monkeypatch.setattr(Path, "exists", lambda self: False)

        data = app.get_installable_tools(include_installed=False)

        assert data["ok"] is True
        assert data["platform"] in ("darwin", "linux", "win32")
        assert "tools" in data

        ids = [t["id"] for t in data["tools"]]
        # Claude não deve estar na lista de não-instaladas
        assert "claude" not in ids
        # Cursor, Kiro, CommandCode devem estar presentes
        assert "cursor" in ids
        assert "kiro" in ids
        assert "commandcode" in ids

        for tool in data["tools"]:
            assert tool["installed"] is False
            assert bool(tool["install_command"])
            assert bool(tool["method"])
            assert bool(tool["docs_url"])

    def test_get_installable_tools_include_all(self, monkeypatch):
        monkeypatch.setattr(app, "build_catalog", lambda: {"tools": [{"id": "claude"}]})
        monkeypatch.setattr(
            app.shutil,
            "which",
            lambda binary: "/usr/local/bin/claude" if binary == "claude" else None,
        )
        monkeypatch.setattr(Path, "exists", lambda self: False)

        data = app.get_installable_tools(include_installed=True)

        assert data["ok"] is True
        ids = [t["id"] for t in data["tools"]]
        assert "claude" in ids
        claude_tool = next(t for t in data["tools"] if t["id"] == "claude")
        assert claude_tool["installed"] is True

    def test_is_tool_installed_detects_binary(self, monkeypatch):
        monkeypatch.setattr(
            app.shutil,
            "which",
            lambda binary: "/usr/bin/cursor" if binary == "cursor" else None,
        )
        monkeypatch.setattr(Path, "exists", lambda self: False)

        cursor_spec = next(t for t in app.INSTALLABLE_TOOLS if t["id"] == "cursor")
        assert app.is_tool_installed(cursor_spec, set()) is True

    def test_is_tool_installed_detects_catalog_presence(self):
        kiro_spec = next(t for t in app.INSTALLABLE_TOOLS if t["id"] == "kiro")
        assert app.is_tool_installed(kiro_spec, {"kiro"}) is True
