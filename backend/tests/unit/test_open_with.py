import sys
from pathlib import Path

import pytest

import app
import open_with


@pytest.fixture
def mac(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "platform", "darwin")
    installed = {"iTerm.app", "Claude.app"}
    monkeypatch.setattr(open_with, "_darwin_app", lambda name: tmp_path / name if name in installed else None)
    monkeypatch.setattr(open_with, "_which", lambda names: None)
    return tmp_path


def test_lista_so_o_que_foi_detectado(mac):
    assert open_with.list_terminals() == [{"id": "iterm2", "label": "iTerm2"}]
    assert open_with.apps_for_tool("claude") == [{"id": "Claude", "label": "Claude"}]
    assert open_with.apps_for_tool("codex") == []


def test_sem_nada_detectado_retorna_vazio(monkeypatch):
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setattr(open_with, "_darwin_app", lambda name: None)
    monkeypatch.setattr(open_with, "_which", lambda names: None)
    assert open_with.list_terminals() == []
    assert open_with.apps_for_tool("claude") == []


def test_iterm_abre_shell_no_diretorio_com_espaco(mac):
    argv = open_with.argv_for_terminal("iterm2", "claude", "/tmp/Meu Dir/repo")
    assert argv[0] == "osascript"
    texto = " ".join(argv)
    assert "cd '/tmp/Meu Dir/repo' && claude" in texto


def _fake_bundle(tmp_path, name="Fake.app", icon="fake.icns"):
    resources = tmp_path / name / "Contents" / "Resources"
    resources.mkdir(parents=True)
    import plistlib

    with open(tmp_path / name / "Contents" / "Info.plist", "wb") as fh:
        plistlib.dump({"CFBundleIconFile": icon}, fh)
    (resources / icon).write_bytes(b"icns")
    return tmp_path / name


def test_icone_resolve_pelo_info_plist(tmp_path, monkeypatch):
    bundle = _fake_bundle(tmp_path)
    monkeypatch.setattr(open_with, "_darwin_app", lambda name: bundle if name == "Claude.app" else None)
    assert open_with.app_icns("Claude") == bundle / "Contents" / "Resources" / "fake.icns"
    assert open_with.app_icns("Inexistente") is None
    monkeypatch.setattr(open_with, "_darwin_app", lambda name: None)
    assert open_with.app_icns("Claude") is None


def test_icone_converte_uma_vez_e_reusa_cache(tmp_path, monkeypatch):
    import subprocess

    bundle = _fake_bundle(tmp_path)
    monkeypatch.setattr(open_with, "_darwin_app", lambda name: bundle if name == "Claude.app" else None)
    monkeypatch.setattr(sys, "platform", "darwin")
    chamadas = []

    class Proc:
        returncode = 0

    def fake_run(argv, **kwargs):
        chamadas.append(argv)
        Path(argv[-1]).write_bytes(b"png")
        return Proc()

    monkeypatch.setattr(subprocess, "run", fake_run)
    cache = tmp_path / "icons"
    first = open_with.app_icon_png("Claude", cache)
    second = open_with.app_icon_png("Claude", cache)
    assert first == second == cache / "Claude.png"
    assert len(chamadas) == 1
    assert "sips" in chamadas[0]


def test_icone_falha_de_conversao_retorna_none(tmp_path, monkeypatch):
    import subprocess

    bundle = _fake_bundle(tmp_path)
    monkeypatch.setattr(open_with, "_darwin_app", lambda name: bundle if name == "Claude.app" else None)
    monkeypatch.setattr(sys, "platform", "darwin")

    def boom(argv, **kwargs):
        raise OSError("sem sips")

    monkeypatch.setattr(subprocess, "run", boom)
    assert open_with.app_icon_png("Claude", tmp_path / "icons") is None


def test_terminal_desconhecido_erro(mac):
    with pytest.raises(ValueError):
        open_with.argv_for_terminal("warp", "claude", "/tmp")


def test_app_resolve_caminho_e_ignora_cwd(mac):
    argv = open_with.argv_for_app("Claude")
    assert argv[:2] == ["open", "-a"]
    assert argv[2].endswith("Claude.app")
    with pytest.raises(ValueError):
        open_with.argv_for_app("Inexistente")


def test_run_open_valida_tool_terminal_e_projeto(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setattr(app, "OPENABLE", {"claude": "claude"})
    monkeypatch.setattr(open_with, "list_terminals", lambda: [{"id": "iterm2", "label": "iTerm2"}])
    monkeypatch.setattr(open_with, "apps_for_tool", lambda tool: [])
    chamadas = []
    monkeypatch.setattr(open_with, "launch", lambda argv: chamadas.append(argv))
    monkeypatch.setattr(app, "AUDIT_LOG", tmp_path / "audit.log")

    with pytest.raises(app.ApiError):
        app.run_open("semcli", "terminal:iterm2", None)
    with pytest.raises(app.ApiError):
        app.run_open("claude", "terminal:warp", None)
    with pytest.raises(app.ApiError):
        app.run_open("claude", "coisa-aleatoria", None)

    projeto = tmp_path / "meu proj"
    projeto.mkdir()
    monkeypatch.setitem(app.SOURCE_BY_ID, "proj:x", {"id": "proj:x", "root": str(projeto), "project": True})
    assert app.run_open("claude", "terminal:iterm2", "proj:x") == {"ok": True}
    assert f"cd '{projeto}' && claude" in " ".join(chamadas[0])

    # projeto desconhecido cai no fallback, nunca em caminho cru
    monkeypatch.setattr(app, "HOME", tmp_path)
    base = tmp_path / "Projetos"
    base.mkdir()
    monkeypatch.setattr(app, "project_base", lambda: str(base))
    assert app.resolve_open_cwd("/etc/sombra") == str(base)
    assert app.run_open("claude", "terminal:iterm2", "/etc/sombra") == {"ok": True}
    assert "/etc/sombra" not in " ".join(chamadas[1])


def test_run_open_app_ignora_projeto_e_registra_auditoria(tmp_path, monkeypatch):
    monkeypatch.setattr(app, "OPENABLE", {"claude": "claude"})
    monkeypatch.setattr(open_with, "apps_for_tool", lambda tool: [{"id": "Claude", "label": "Claude"}])
    monkeypatch.setattr(open_with, "argv_for_app", lambda app_id: ["open", "-a", "Claude.app"])
    chamadas = []
    monkeypatch.setattr(open_with, "launch", lambda argv: chamadas.append(argv))
    monkeypatch.setattr(app, "AUDIT_LOG", tmp_path / "audit.log")
    assert app.run_open("claude", "app:Claude", "proj:qualquer") == {"ok": True}
    assert chamadas == [["open", "-a", "Claude.app"]]
    assert "open-app" in (tmp_path / "audit.log").read_text()


def test_run_open_falha_de_lancamento_vira_500(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setattr(app, "OPENABLE", {"claude": "claude"})
    monkeypatch.setattr(open_with, "list_terminals", lambda: [{"id": "iterm2", "label": "iTerm2"}])
    monkeypatch.setattr(app, "HOME", tmp_path)

    def boom(argv):
        raise OSError("sem display")

    monkeypatch.setattr(open_with, "launch", boom)
    with pytest.raises(app.ApiError) as exc:
        app.run_open("claude", "terminal:iterm2", None)
    assert exc.value.status == 500
