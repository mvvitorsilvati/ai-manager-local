from pathlib import Path

import pytest

import app
import scan_home


def test_sem_aim_home_usa_o_home_do_processo(monkeypatch):
    monkeypatch.delenv("AIM_HOME", raising=False)
    assert scan_home.scan_home() == Path.home()


def test_aim_home_sobrepoe_o_home_escaneado(monkeypatch, tmp_path):
    monkeypatch.setenv("AIM_HOME", str(tmp_path))
    assert scan_home.scan_home() == tmp_path


@pytest.mark.parametrize(
    ("entrada", "esperado"),
    [("~", ""), ("~/Projetos", "Projetos"), ("~/.claude/skills", ".claude/skills")],
)
def test_scan_path_expande_o_til_contra_o_home_escaneado(monkeypatch, tmp_path, entrada, esperado):
    monkeypatch.setenv("AIM_HOME", str(tmp_path))
    assert scan_home.scan_path(entrada) == tmp_path / esperado


def test_scan_path_mantem_caminho_absoluto(monkeypatch, tmp_path):
    monkeypatch.setenv("AIM_HOME", str(tmp_path / "outro"))
    assert scan_home.scan_path("/etc/hosts") == Path("/etc/hosts")


def test_fonte_com_til_segue_o_aim_home(monkeypatch, tmp_path):
    monkeypatch.setenv("AIM_HOME", str(tmp_path))
    monkeypatch.setitem(
        app.SOURCE_BY_ID,
        "aim-home-teste",
        {"id": "aim-home-teste", "label": "t", "root": "~/.claude", "exclude_dirs": set(), "exclude_files": set()},
    )
    monkeypatch.setattr(app, "SOURCES", [*app.SOURCES, app.SOURCE_BY_ID["aim-home-teste"]])
    assert app.scan_home.scan_path(app.SOURCE_BY_ID["aim-home-teste"]["root"]) == tmp_path / ".claude"
