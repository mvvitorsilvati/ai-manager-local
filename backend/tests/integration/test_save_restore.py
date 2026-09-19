import os
import pwd
from types import SimpleNamespace

import pytest

import app


@pytest.fixture
def edicao(tmp_path, monkeypatch):
    """Diretório com arquivos de teste, backups/audit isolados e helper de save."""
    root = tmp_path / "repo"
    root.mkdir()
    (root / "a.md").write_text("original")
    (root / "config.json").write_text("{}")
    (root / "logo.png").write_text("png")
    monkeypatch.setattr(app, "BACKUP_DIR", tmp_path / "backups")
    monkeypatch.setattr(app, "AUDIT_LOG", tmp_path / "audit.log")
    monkeypatch.setitem(
        app.SOURCE_BY_ID,
        "teste",
        {"id": "teste", "label": "t", "root": str(root), "exclude_dirs": set(), "exclude_files": set()},
    )

    def save(rel="a.md", content="novo", **kw):
        path = root / rel
        if "expected_mtime" not in kw and path.is_file():
            kw["expected_mtime"] = int(path.stat().st_mtime)
        return app.save_file("teste", rel, content, **kw)

    return SimpleNamespace(root=root, backups=tmp_path / "backups", audit=tmp_path / "audit.log", save=save)


def test_salva_conteudo_e_cria_backup(edicao):
    result = edicao.save()
    assert (edicao.root / "a.md").read_text() == "novo"
    assert result["size"] == 4
    assert len(app.list_backups("teste", "a.md")) == 1
    assert edicao.backups.is_dir()
    assert "save" in edicao.audit.read_text()


def test_conflito_de_mtime(edicao):
    with pytest.raises(app.ConflictError) as exc:
        edicao.save(expected_mtime=123)
    assert exc.value.info.get("mtime")
    assert (edicao.root / "a.md").read_text() == "original"


def test_conflito_no_mesmo_segundo_usa_nanossegundos(edicao):
    stale_ns = str((edicao.root / "a.md").stat().st_mtime_ns)
    edicao.save(content="primeira")
    with pytest.raises(app.ConflictError):
        edicao.save(content="segunda", expected_mtime=None, expected_mtime_ns=stale_ns)
    assert (edicao.root / "a.md").read_text() == "primeira"


def test_mtime_ns_vai_como_string_no_file_info(edicao):
    assert isinstance(app.file_info(edicao.root / "a.md")["mtime_ns"], str)


def test_force_ignora_conflito(edicao):
    edicao.save(expected_mtime=123, force=True)
    assert (edicao.root / "a.md").read_text() == "novo"


def test_json_invalido_retorna_422(edicao):
    with pytest.raises(app.ApiError) as exc:
        edicao.save(rel="config.json", content="{oops}")
    assert exc.value.status == 422
    assert (edicao.root / "config.json").read_text() == "{}"


def test_binario_retorna_415(edicao):
    with pytest.raises(app.ApiError) as exc:
        edicao.save(rel="logo.png", content="x")
    assert exc.value.status == 415


def test_traversal_bloqueado(edicao):
    with pytest.raises(app.ApiError) as exc:
        edicao.save(rel="../fora.md", content="x")
    assert exc.value.status == 400


def test_prune_mantem_dez_versoes(edicao):
    for i in range(12):
        edicao.save(content=f"versao {i}")
        (edicao.root / "a.md").touch()
    assert len(app.list_backups("teste", "a.md")) == app.BACKUP_KEEP


def test_restaura_backup(edicao):
    edicao.save(content="alterado")
    (edicao.root / "a.md").touch()
    versions = app.list_backups("teste", "a.md")
    assert len(versions) == 1
    assert app.restore_backup("teste", "a.md", versions[0]["name"])["ok"]
    assert (edicao.root / "a.md").read_text() == "original"


def test_restore_bloqueia_nome_invalido(edicao):
    with pytest.raises(app.ApiError) as exc:
        app.restore_backup("teste", "a.md", "../../etc/passwd")
    assert exc.value.status == 400


def test_file_info_traz_dono_criacao_e_tamanho(tmp_path):
    p = tmp_path / "a.md"
    p.write_text("abc")
    info = app.file_info(p)
    assert info["owner"] == pwd.getpwuid(os.getuid()).pw_name
    assert info["created"] > 0
    assert info["size"] == 3
