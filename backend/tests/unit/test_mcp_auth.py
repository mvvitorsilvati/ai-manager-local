import json

import app


def test_codex_authenticated_mcps_le_arquivo_json(tmp_path, monkeypatch):
    codex_dir = tmp_path / ".codex"
    codex_dir.mkdir()
    cred_file = codex_dir / ".credentials.json"
    cred_file.write_text(json.dumps({"linear|abc123": {"token": "secret"}, "context7": {"token": "secret"}}))

    monkeypatch.setattr(app, "HOME", tmp_path)
    monkeypatch.setattr(app.sys, "platform", "linux")

    authed = app.codex_authenticated_mcps()
    assert authed == {"linear", "context7"}


def test_codex_authenticated_mcps_le_keychain(monkeypatch):
    keychain_output = """keychain: "/Users/test/Library/Keychains/login.keychain-db"
version: 512
class: "genp"
attributes:
    0x00000007 <blob>="Codex MCP Credentials"
    "acct"<blob>="linear|638130d5ab3558f4"
    "svce"<blob>="Codex MCP Credentials"
keychain: "/Users/test/Library/Keychains/login.keychain-db"
version: 512
class: "genp"
attributes:
    0x00000007 <blob>="Codex MCP Credentials"
    "acct"<blob>="custom_service|99999"
    "svce"<blob>="Codex MCP Credentials"
"""

    class Proc:
        returncode = 0
        stdout = keychain_output
        stderr = ""

    monkeypatch.setattr(app.sys, "platform", "darwin")
    monkeypatch.setattr(app.subprocess, "run", lambda *args, **kwargs: Proc())
    monkeypatch.setattr(app.Path, "is_file", lambda self: False)

    authed = app.codex_authenticated_mcps()
    assert authed == {"linear", "custom_service"}


def test_opencode_authenticated_mcps(tmp_path, monkeypatch):
    share_dir = tmp_path / "opencode"
    share_dir.mkdir(parents=True)
    auth_file = share_dir / "mcp-auth.json"
    auth_file.write_text(json.dumps({"linear": {"tokens": {}}}))

    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))

    authed = app.opencode_authenticated_mcps()
    assert authed == {"linear"}


def test_fetch_codex_mcp_list_interpreta_tabela(monkeypatch):
    output = (
        "Name       Url                                  Bearer Token Env Var                Status    Auth\n"
        "atlassian  https://mcp.atlassian.com/v1/mcp     -                                   disabled  Unsupported\n"
        "context7   https://mcp.context7.com/mcp         -                                   enabled   Not logged in\n"
        "github     https://api.githubcopilot.com/mcp/   CODEX_GITHUB_PERSONAL_ACCESS_TOKEN  disabled  Unsupported\n"
        "linear     https://mcp.linear.app/mcp           -                                   enabled   OAuth\n"
        "microsoft  https://learn.microsoft.com/api/mcp  -                                   enabled   Unsupported\n"
    )

    class Proc:
        returncode = 0
        stdout = output
        stderr = ""

    monkeypatch.setattr(app.shutil, "which", lambda cmd: "/usr/local/bin/codex")
    monkeypatch.setattr(app.subprocess, "run", lambda *args, **kwargs: Proc())

    result = app.fetch_codex_mcp_list()
    assert result["linear"] == {"has_auth": True, "authenticated": True}
    assert result["context7"] == {"has_auth": True, "authenticated": False}
    assert result["microsoft"] == {"has_auth": False, "authenticated": False}
    assert result["atlassian"] == {"has_auth": False, "authenticated": False}
    assert result["github"] == {"has_auth": False, "authenticated": False}


def test_mcp_auth_status_mcp_local_nunca_tem_auth():
    has_auth, authed = app.mcp_auth_status("codex", "playwright", "local", "npx -y @playwright/mcp@latest")
    assert has_auth is False
    assert authed is False

    has_auth, authed = app.mcp_auth_status("opencode", "context7", "local", "npx -y @upstash/context7-mcp")
    assert has_auth is False
    assert authed is False


def test_mcp_auth_status_opencode_remoto(monkeypatch):
    monkeypatch.setattr(app, "opencode_authenticated_mcps", lambda: {"linear"})

    has_auth, authed = app.mcp_auth_status("opencode", "linear", "remote", "https://mcp.linear.app/mcp")
    assert has_auth is True
    assert authed is True

    has_auth, authed = app.mcp_auth_status("opencode", "outro", "remote", "https://outro.com/mcp")
    assert has_auth is True
    assert authed is False


def test_mcp_auth_status_codex_remoto(monkeypatch):
    monkeypatch.setattr(
        app,
        "get_codex_mcp_auth_map",
        lambda force=False: {
            "linear": {"has_auth": True, "authenticated": True},
            "context7": {"has_auth": True, "authenticated": False},
            "microsoft": {"has_auth": False, "authenticated": False},
        },
    )

    assert app.mcp_auth_status("codex", "linear", "remote", "https://mcp.linear.app/mcp") == (True, True)
    assert app.mcp_auth_status("codex", "context7", "remote", "https://mcp.context7.com/mcp") == (True, False)
    assert app.mcp_auth_status("codex", "microsoft", "remote", "https://learn.microsoft.com/api/mcp") == (
        False,
        False,
    )


def test_collect_mcps_propaga_has_auth_e_authenticated(tmp_path, monkeypatch):
    opencode_dir = tmp_path / "opencode"
    opencode_dir.mkdir()
    (opencode_dir / "opencode.jsonc").write_text(
        '{"mcp": {'
        '  "linear": {"type": "remote", "url": "https://mcp.linear.app/mcp"},'
        '  "local_tool": {"type": "local", "command": ["echo", "1"]}'
        "}}"
    )
    monkeypatch.setattr(
        app,
        "all_tools",
        lambda: [{
            "id": "opencode",
            "label": "opencode",
            "root": str(opencode_dir),
            "mcp": {"rel": "opencode.jsonc", "container": "mcp", "kind": "json"},
            "mcp_login": ["opencode", "mcp", "auth"],
            "mcp_logout": ["opencode", "mcp", "logout"],
        }],
    )
    monkeypatch.setattr(app, "HOME", tmp_path)
    monkeypatch.setattr(app, "opencode_authenticated_mcps", lambda: {"linear"})

    mcps = app.collect_mcps()
    linear = next(m for m in mcps if m["name"] == "linear")
    local_tool = next(m for m in mcps if m["name"] == "local_tool")

    assert linear["has_auth"] is True
    assert linear["authenticated"] is True
    assert local_tool["has_auth"] is False
    assert local_tool["authenticated"] is False


def test_clear_mcp_auth_cache(monkeypatch):
    monkeypatch.setattr(app, "_codex_mcp_cache", (123.0, {"dummy": {"has_auth": True, "authenticated": True}}))
    called = []
    monkeypatch.setattr(app, "update_codex_mcp_cache_bg", lambda: called.append(True))

    app.clear_mcp_auth_cache()
    assert app._codex_mcp_cache == (0.0, {})
    assert called == [True]
