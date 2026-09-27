import json
import sys
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from types import SimpleNamespace

import pytest

import app
import skills
import spend

H = {"Content-Type": "application/json", "X-AIM": "1"}


@pytest.fixture
def servidor(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    root.mkdir()
    (root / "a.md").write_text("original")
    source = {"id": "teste", "label": "t", "root": str(root), "exclude_dirs": set(), "exclude_files": set()}
    monkeypatch.setitem(app.SOURCE_BY_ID, "teste", source)
    monkeypatch.setattr(app, "SOURCES", [*app.SOURCES, source])
    monkeypatch.setattr(app, "BACKUP_DIR", tmp_path / "backups")
    monkeypatch.setattr(app, "AUDIT_LOG", tmp_path / "audit.log")
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), app.Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield SimpleNamespace(url=f"http://127.0.0.1:{httpd.server_address[1]}", root=root)
    httpd.shutdown()
    httpd.server_close()
    thread.join(timeout=5)


def request(url, payload=None, headers=None):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, headers=headers or (H if data else {}))
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()


def test_spend_devolve_o_snapshot(servidor, monkeypatch):
    monkeypatch.setattr(spend, "snapshot", lambda *args, **kwargs: {"tools": {"claude": {"available": True}}})
    status, body = request(f"{servidor.url}/api/spend?days=7")
    assert status == 200
    assert json.loads(body)["tools"]["claude"]["available"] is True


def test_open_targets_lista_terminais_e_apps(servidor, monkeypatch):
    import open_with

    monkeypatch.setattr(open_with, "list_terminals", lambda: [{"id": "iterm2", "label": "iTerm2"}])
    monkeypatch.setattr(open_with, "apps_for_tool", lambda tool: [{"id": "Claude", "label": "Claude"}])
    status, body = request(f"{servidor.url}/api/open-targets?tool=claude")
    assert status == 200
    assert json.loads(body) == {
        "terminals": [{"id": "iterm2", "label": "iTerm2"}],
        "apps": [{"id": "Claude", "label": "Claude"}],
    }


def test_open_invalido_registra_warning_no_log(servidor):
    from loguru import logger

    registros = []
    hid = logger.add(lambda mensagem: registros.append(mensagem), level="WARNING")
    try:
        status, _ = request(f"{servidor.url}/api/open", {"tool": "x", "target": "y"})
        assert status == 400
        assert any("/api/open" in r for r in registros)
    finally:
        logger.remove(hid)


def test_app_icon_serve_png_e_nega_id_ruim(servidor, tmp_path, monkeypatch):
    import open_with

    png = tmp_path / "x.png"
    png.write_bytes(b"fakepng")
    monkeypatch.setattr(open_with, "app_icon_png", lambda app_id, cache: png if app_id == "Claude" else None)
    status, body = request(f"{servidor.url}/api/app-icon?app=Claude")
    assert status == 200
    assert body == b"fakepng"
    status, _ = request(f"{servidor.url}/api/app-icon?app=../../etc/passwd")
    assert status == 404


def test_open_abre_via_launch_e_rejeita_alvo_ruim(servidor, monkeypatch):
    import open_with

    # argv_for_terminal valida a plataforma: finge macOS como nos testes unitários
    monkeypatch.setattr(sys, "platform", "darwin")
    chamadas = []
    monkeypatch.setattr(open_with, "launch", lambda argv: chamadas.append(argv))
    monkeypatch.setattr(app, "OPENABLE", {"claude": "claude"})
    monkeypatch.setattr(open_with, "list_terminals", lambda: [{"id": "iterm2", "label": "iTerm2"}])
    monkeypatch.setattr(open_with, "apps_for_tool", lambda tool: [])
    monkeypatch.setattr(app, "AUDIT_LOG", servidor.root / "audit.log")

    status, _ = request(f"{servidor.url}/api/open", {"tool": "claude", "target": "rm -rf /"})
    assert status == 400
    status, body = request(f"{servidor.url}/api/open", {"tool": "claude", "target": "terminal:iterm2"})
    assert status == 200
    assert json.loads(body) == {"ok": True}
    assert chamadas and chamadas[0][0] == "osascript"


def test_skill_usage_devolve_o_snapshot(servidor, monkeypatch):
    monkeypatch.setattr(skills, "snapshot", lambda *args, **kwargs: {"top": [{"skill": "demo"}]})
    status, body = request(f"{servidor.url}/api/skill-usage?days=7")
    assert status == 200
    assert json.loads(body)["top"][0]["skill"] == "demo"


def test_catalog_responde_com_fontes(servidor):
    status, body = request(f"{servidor.url}/api/catalog")
    assert status == 200
    assert any(s["id"] == "teste" for s in json.loads(body)["sources"])


def test_catalog_diz_o_que_o_sistema_operacional_suporta(servidor):
    status, body = request(f"{servidor.url}/api/catalog")
    assert status == 200
    caps = json.loads(body)["caps"]
    assert caps["reveal"] is (sys.platform == "darwin")


def test_file_le_arquivo_da_fonte(servidor):
    status, body = request(f"{servidor.url}/api/file?s=teste&r=a.md")
    assert status == 200
    data = json.loads(body)
    assert data["content"] == "original"
    assert data["mtime_ns"]


def test_file_bloqueia_traversal(servidor):
    status, _ = request(f"{servidor.url}/api/file?s=teste&r=../fora.md")
    assert status == 400


def test_post_exige_header_de_seguranca(servidor):
    status, _ = request(
        f"{servidor.url}/api/save",
        {"s": "teste", "r": "a.md", "content": "x"},
        headers={"Content-Type": "application/json"},
    )
    assert status == 403


def test_fluxo_salvar_backup_restaurar(servidor):
    _, body = request(f"{servidor.url}/api/file?s=teste&r=a.md")
    mtime_ns = json.loads(body)["mtime_ns"]

    status, body = request(
        f"{servidor.url}/api/save",
        {"s": "teste", "r": "a.md", "content": "editado", "mtime_ns": mtime_ns},
    )
    assert status == 200
    assert (servidor.root / "a.md").read_text() == "editado"

    status, body = request(f"{servidor.url}/api/backups?s=teste&r=a.md")
    assert status == 200
    assert len(json.loads(body)) == 1
    backup = json.loads(body)[0]["name"]

    status, _ = request(f"{servidor.url}/api/restore", {"s": "teste", "r": "a.md", "backup": backup})
    assert status == 200
    assert (servidor.root / "a.md").read_text() == "original"


def test_conflito_de_mtime_retorna_409(servidor):
    status, body = request(
        f"{servidor.url}/api/save",
        {"s": "teste", "r": "a.md", "content": "x", "mtime_ns": "1"},
    )
    assert status == 409
    assert json.loads(body)["conflict"] is True


def test_usage_responde_com_dados_do_claude(servidor, monkeypatch):
    monkeypatch.setattr(app, "claude_usage", lambda: {"available": True, "windows": [], "credits": None})
    monkeypatch.setattr(app, "codex_usage", lambda: None)
    monkeypatch.setattr(app, "copilot_usage", lambda: None)
    monkeypatch.setattr(app, "gemini_usage", lambda: None)
    app._usage_cache = (0.0, {})
    status, body = request(f"{servidor.url}/api/usage")
    assert status == 200
    payload = json.loads(body)
    assert payload["claude"]["available"] is True
    assert "codex" in payload
    assert "copilot" in payload
    assert "gemini" in payload

    status, body = request(f"{servidor.url}/api/usage?refresh=1&tool=codex")
    assert status == 200
    assert set(json.loads(body)) == {"codex"}


def test_authors_fora_de_repo_retorna_vazio(servidor):
    status, body = request(f"{servidor.url}/api/authors", {"files": [{"s": "teste", "r": "a.md"}]})
    assert status == 200
    assert json.loads(body) == []


def test_raiz_serve_html(servidor, tmp_path, monkeypatch):
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_bytes(b"<html><body>build</body></html>")
    monkeypatch.setattr(app, "DIST_DIR", dist)

    status, body = request(f"{servidor.url}/")
    assert status == 200
    assert b"<html" in body.lower()


def test_raiz_sem_build_orienta_a_buildar(servidor, tmp_path, monkeypatch):
    monkeypatch.setattr(app, "DIST_DIR", tmp_path / "sem-dist")

    status, body = request(f"{servidor.url}/")
    assert status == 503
    assert b"just build" in body


def test_serve_arquivo_estatico_do_dist(servidor, tmp_path, monkeypatch):
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_bytes(b"<html>spa</html>")
    (dist / "favicon.svg").write_bytes(b"<svg></svg>")
    monkeypatch.setattr(app, "DIST_DIR", dist)

    status, body = request(f"{servidor.url}/favicon.svg")
    assert status == 200
    assert body == b"<svg></svg>"


def test_rota_do_spa_cai_no_index(servidor, tmp_path, monkeypatch):
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_bytes(b"<html>spa</html>")
    monkeypatch.setattr(app, "DIST_DIR", dist)

    status, body = request(f"{servidor.url}/ia")
    assert status == 200
    assert b"<html>spa</html>" in body


def test_statusline_get_retorna_status(servidor, monkeypatch):
    import statusline_installer as statusline

    monkeypatch.setattr(
        statusline,
        "check_status",
        lambda *args, **kwargs: {
            "claude": {"installed": True, "configured": True, "path": "/path/claude"},
            "antigravity": {"installed": False, "configured": False, "path": "/path/agy"},
        },
    )
    status, body = request(f"{servidor.url}/api/statusline")
    assert status == 200
    data = json.loads(body)
    assert data["claude"]["installed"] is True
    assert data["antigravity"]["installed"] is False


def test_statusline_post_instala_alvo(servidor, monkeypatch):
    import statusline_installer as statusline

    chamadas = []
    monkeypatch.setattr(
        statusline,
        "install",
        lambda target, **kwargs: chamadas.append(target) or {"ok": True, "target": target, "message": "sucesso"},
    )
    status, body = request(f"{servidor.url}/api/statusline", payload={"target": "claude"})
    assert status == 200
    data = json.loads(body)
    assert data["ok"] is True
    assert chamadas == ["claude"]


def test_statusline_get_backups(servidor, monkeypatch):
    import statusline_installer as statusline

    monkeypatch.setattr(
        statusline,
        "list_backups",
        lambda tool=None: [
            {"tool": "claude", "backup_name": "statusline-command.sh.bak-1", "size": 100, "mtime": 123456}
        ],
    )
    status, body = request(f"{servidor.url}/api/statusline/backups?tool=claude")
    assert status == 200
    data = json.loads(body)
    assert len(data) == 1
    assert data[0]["tool"] == "claude"


def test_statusline_get_preview(servidor, monkeypatch):
    import statusline_installer as statusline

    monkeypatch.setattr(
        statusline,
        "get_preview",
        lambda tool: {
            "ok": True,
            "tool": tool,
            "raw_lines": ["line 1"],
            "plain_lines": ["line 1"],
        },
    )
    status, body = request(f"{servidor.url}/api/statusline/preview?tool=antigravity")
    assert status == 200
    data = json.loads(body)
    assert data["ok"] is True
    assert data["tool"] == "antigravity"
    assert data["plain_lines"] == ["line 1"]


def test_statusline_post_restore_sucesso(servidor, monkeypatch):
    import statusline_installer as statusline

    monkeypatch.setattr(
        statusline,
        "restore_backup",
        lambda tool, backup: {
            "ok": True,
            "tool": tool,
            "restored": backup,
            "message": "restaurado",
        },
    )
    status, body = request(
        f"{servidor.url}/api/statusline/restore",
        payload={"tool": "antigravity", "backup": "statusline.sh.bak-123"},
    )
    assert status == 200
    data = json.loads(body)
    assert data["ok"] is True
    assert data["restored"] == "statusline.sh.bak-123"


def test_statusline_post_restore_erro_validacao(servidor):
    status, body = request(
        f"{servidor.url}/api/statusline/restore",
        payload={"tool": ""},
    )
    assert status == 400
    assert "obrigatórios" in json.loads(body)["error"]


def test_sessions_media_sucesso_gemini(servidor, tmp_path, monkeypatch):
    sid = "sess-media-123"
    brain = tmp_path / ".gemini" / "antigravity-cli" / "brain" / sid / ".user_uploaded"
    brain.mkdir(parents=True)
    img_file = brain / "screenshot.png"
    fake_png = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
    img_file.write_bytes(fake_png)

    monkeypatch.setattr(app, "HOME", tmp_path)

    status, body = request(f"{servidor.url}/api/sessions/media?tool=gemini&id={sid}&name=screenshot.png")
    assert status == 200
    assert body == fake_png


def test_sessions_media_erro_path_traversal(servidor):
    status, body = request(f"{servidor.url}/api/sessions/media?tool=gemini&id=123&name=../hack.png")
    assert status == 400
    assert "inválido" in json.loads(body)["error"]


def test_sessions_media_nao_encontrada(servidor, tmp_path, monkeypatch):
    monkeypatch.setattr(app, "HOME", tmp_path)
    status, body = request(f"{servidor.url}/api/sessions/media?tool=gemini&id=inexistente&name=naoexiste.png")
    assert status == 404
    assert "não encontrada" in json.loads(body)["error"]


def test_installable_tools_endpoint(servidor):
    status, body = request(f"{servidor.url}/api/installable-tools")
    assert status == 200
    data = json.loads(body)
    assert data["ok"] is True
    assert "platform" in data
    assert "tools" in data
    assert isinstance(data["tools"], list)
