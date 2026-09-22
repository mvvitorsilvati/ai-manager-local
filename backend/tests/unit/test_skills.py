import json
import sqlite3
from datetime import UTC, datetime

import skills


def test_claude_conta_comando_e_mede_skill_md(tmp_path):
    root = tmp_path / "projects" / "demo"
    root.mkdir(parents=True)
    now = datetime.now(UTC).isoformat()
    lines = [
        {
            "type": "user",
            "timestamp": now,
            "sessionId": "s1",
            "message": {"content": "rode <command-name>/minha-skill</command-name> aqui"},
        },
        {
            "type": "user",
            "timestamp": now,
            "sessionId": "s1",
            "message": {"content": "rode <command-name>/minha-skill</command-name> de novo"},
        },
        {
            "type": "user",
            "timestamp": now,
            "sessionId": "s2",
            "message": {"content": "só <command-name>/login</command-name> sem skill"},
        },
    ]
    (root / "sess.jsonl").write_text("\n".join(json.dumps(line) for line in lines))
    skill_dir = tmp_path / "skills" / "minha-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("x" * 400)
    payload = skills.build(
        days=2, tool="claude", roots={"claude": tmp_path / "projects"}, skill_dirs=[tmp_path / "skills"]
    )
    tool = payload["tools"]["claude"]
    assert tool["invocations"] == 2
    assert tool["rows"] == [
        {
            "skill": "minha-skill",
            "invocations": 2,
            "sessions": 1,
            "context_tokens": 200,
            "by_origin": {"user": 2, "model": 0},
            "resolved": True,
        }
    ]


def test_claude_conta_chamada_skill_direta(tmp_path):
    root = tmp_path / "projects" / "demo"
    root.mkdir(parents=True)
    rec = {
        "type": "assistant",
        "timestamp": datetime.now(UTC).isoformat(),
        "sessionId": "s",
        "cwd": "/tmp/demo",
        "message": {
            "id": "m",
            "model": "x",
            "content": [{"type": "tool_use", "name": "Skill", "input": {"skill": "core:outra"}}],
            "usage": {"input_tokens": 1, "output_tokens": 1},
        },
    }
    (root / "a.jsonl").write_text(json.dumps(rec))
    skill_dir = tmp_path / "skills" / "outra"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("y" * 40)
    payload = skills.build(
        days=2, tool="claude", roots={"claude": tmp_path / "projects"}, skill_dirs=[tmp_path / "skills"]
    )
    tool = payload["tools"]["claude"]
    assert tool["rows"][0]["skill"] == "outra"
    assert tool["rows"][0]["context_tokens"] == 10
    assert tool["rows"][0]["by_origin"] == {"user": 0, "model": 1}


def test_opencode_soma_conteudo_injetado(tmp_path):
    db = tmp_path / "opencode.db"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE part (id text, message_id text, session_id text, time_created integer, data text)")
    now = int(datetime.now(UTC).timestamp() * 1000)
    part = {"type": "tool", "tool": "skill", "state": {"input": {"name": "tgrep"}, "output": "z" * 80}}
    conn.execute("INSERT INTO part VALUES (?, ?, ?, ?, ?)", ("p1", "m1", "s1", now, json.dumps(part)))
    conn.execute(
        "INSERT INTO part VALUES (?, ?, ?, ?, ?)",
        ("p2", "m2", "s1", now, json.dumps({"type": "tool", "tool": "bash", "state": {}})),
    )
    conn.commit()
    conn.close()
    tool = skills.build(days=2, tool="opencode", roots={"opencode": db})["tools"]["opencode"]
    assert tool["rows"] == [
        {
            "skill": "tgrep",
            "invocations": 1,
            "sessions": 1,
            "context_tokens": 20,
            "by_origin": {"user": 0, "model": 1},
            "resolved": True,
        }
    ]


def test_opencode_conta_comando_digitado_como_usuario(tmp_path):
    db = tmp_path / "opencode.db"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE part (id text, message_id text, session_id text, time_created integer, data text)")
    now = int(datetime.now(UTC).timestamp() * 1000)
    conn.execute(
        "INSERT INTO part VALUES (?, ?, ?, ?, ?)",
        ("p1", "m1", "s1", now, json.dumps({"type": "text", "text": "/cmd-user faz algo"})),
    )
    conn.execute(
        "INSERT INTO part VALUES (?, ?, ?, ?, ?)",
        ("p2", "m2", "s1", now, json.dumps({"type": "text", "text": "texto comum"})),
    )
    conn.commit()
    conn.close()
    skill_dir = tmp_path / "skills" / "cmd-user"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("z" * 400)
    tool = skills.build(days=2, tool="opencode", roots={"opencode": db}, skill_dirs=[tmp_path / "skills"])[
        "tools"
    ]["opencode"]
    assert tool["rows"][0]["by_origin"] == {"user": 1, "model": 0}
    assert tool["rows"][0]["context_tokens"] == 100


def test_opencode_ignora_skill_embutida(tmp_path):
    db = tmp_path / "opencode.db"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE part (id text, message_id text, session_id text, time_created integer, data text)")
    now = int(datetime.now(UTC).timestamp() * 1000)
    part = {
        "type": "tool",
        "tool": "skill",
        "state": {"input": {"name": "customize-opencode"}, "output": "<!--\n Built-in skill. registered in code."},
    }
    conn.execute("INSERT INTO part VALUES (?, ?, ?, ?, ?)", ("p1", "m1", "s1", now, json.dumps(part)))
    conn.commit()
    conn.close()
    tool = skills.build(days=2, tool="opencode", roots={"opencode": db})["tools"]["opencode"]
    assert tool["rows"] == []
    assert tool["invocations"] == 0


def test_top20_mescla_ferramentas(tmp_path):
    root = tmp_path / "projects" / "demo"
    root.mkdir(parents=True)
    rec = {
        "type": "user",
        "timestamp": datetime.now(UTC).isoformat(),
        "sessionId": "s",
        "message": {"content": "<command-name>/dupla</command-name>"},
    }
    (root / "a.jsonl").write_text(json.dumps(rec))
    skill_dir = tmp_path / "skills" / "dupla"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("w" * 400)
    db = tmp_path / "opencode.db"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE part (id text, message_id text, session_id text, time_created integer, data text)")
    now = int(datetime.now(UTC).timestamp() * 1000)
    part = {"type": "tool", "tool": "skill", "state": {"input": {"name": "dupla"}, "output": "q" * 40}}
    conn.execute("INSERT INTO part VALUES (?, ?, ?, ?, ?)", ("p1", "m1", "s9", now, json.dumps(part)))
    conn.commit()
    conn.close()
    payload = skills.build(
        days=2, roots={"claude": tmp_path / "projects", "opencode": db}, skill_dirs=[tmp_path / "skills"]
    )
    assert payload["top"][0] == {
        "skill": "dupla",
        "invocations": 2,
        "sessions": 2,
        "context_tokens": 110,
        "by_origin": {"user": 1, "model": 1},
        "tools": {"claude": 1, "opencode": 1},
    }
    assert payload["tools"]["codex"]["rows"] == []
    assert "sem marca" in payload["tools"]["codex"]["note"]


def test_fonte_ausente_nao_quebra(tmp_path):
    tool = skills.build(days=7, tool="claude", roots={"claude": tmp_path / "nao-existe"})["tools"]["claude"]
    assert tool["available"] is False
    assert tool["invocations"] == 0
