import json
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from types import SimpleNamespace

import pytest

import app

H = {"Content-Type": "application/json", "X-Gestor": "1"}


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


def test_catalog_responde_com_fontes(servidor):
    status, body = request(f"{servidor.url}/api/catalog")
    assert status == 200
    assert any(s["id"] == "teste" for s in json.loads(body)["sources"])


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
    app._usage_cache = (0.0, {})
    status, body = request(f"{servidor.url}/api/usage")
    assert status == 200
    assert json.loads(body)["claude"]["available"] is True


def test_authors_fora_de_repo_retorna_vazio(servidor):
    status, body = request(f"{servidor.url}/api/authors", {"files": [{"s": "teste", "r": "a.md"}]})
    assert status == 200
    assert json.loads(body) == []


def test_legacy_serve_o_vanilla(servidor):
    status, body = request(f"{servidor.url}/legacy")
    assert status == 200
    assert "Gestor Local" in body.decode()


def test_raiz_serve_html(servidor):
    status, body = request(f"{servidor.url}/")
    assert status == 200
    assert b"<html" in body.lower()
