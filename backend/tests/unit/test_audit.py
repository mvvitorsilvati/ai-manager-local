import json

import app


def test_read_audit_retorna_mais_recente_primeiro(tmp_path, monkeypatch):
    log = tmp_path / "audit.log"
    linhas = [
        {"ts": "2026-09-19T10:00:00", "action": "save", "path": "/a", "size": 1, "backup": None},
        {"ts": "2026-09-19T11:00:00", "action": "restore", "path": "/a", "size": 2, "backup": "/b"},
    ]
    log.write_text("\n".join(json.dumps(linha) for linha in linhas) + "\nlinha invalida\n")
    monkeypatch.setattr(app, "AUDIT_LOG", log)

    entries = app.read_audit()
    assert [entry["action"] for entry in entries] == ["restore", "save"]
    assert entries[0]["backup"] == "/b"


def test_read_audit_respeita_limite(tmp_path, monkeypatch):
    log = tmp_path / "audit.log"
    log.write_text("\n".join(json.dumps({"ts": str(i), "action": "save"}) for i in range(10)))
    monkeypatch.setattr(app, "AUDIT_LOG", log)

    assert len(app.read_audit(3)) == 3
    assert app.read_audit(3)[0]["ts"] == "9"  # mais recente primeiro


def test_read_audit_sem_arquivo(tmp_path, monkeypatch):
    monkeypatch.setattr(app, "AUDIT_LOG", tmp_path / "nao-existe.log")
    assert app.read_audit() == []
