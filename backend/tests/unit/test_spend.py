import json
import sqlite3
from datetime import UTC, datetime, timedelta

import spend


def test_custo_anthropic_separa_cache_e_dedup_fica_com_o_ultimo_chunk(tmp_path):
    root = tmp_path / "projects" / "demo"
    root.mkdir(parents=True)
    now = datetime.now(UTC).replace(microsecond=0)
    lines = [
        {
            "type": "assistant",
            "timestamp": now.isoformat(),
            "sessionId": "s1",
            "cwd": "/tmp/Projetos/demo",
            "isSidechain": False,
            "requestId": "r1",
            "message": {
                "id": "m1",
                "model": "claude-haiku-4-5",
                "usage": {"input_tokens": 100, "output_tokens": 1},
            },
        },
        {
            "type": "assistant",
            "timestamp": (now + timedelta(seconds=1)).isoformat(),
            "sessionId": "s1",
            "cwd": "/tmp/Projetos/demo",
            "requestId": "r1",
            "message": {
                "id": "m1",
                "model": "claude-haiku-4-5-20251001",
                "usage": {
                    "input_tokens": 100,
                    "output_tokens": 50,
                    "cache_read_input_tokens": 1000,
                    "cache_creation": {"ephemeral_5m_input_tokens": 200},
                },
            },
        },
    ]
    (root / "sess.jsonl").write_text("\n".join(json.dumps(line) for line in lines))
    payload = spend.build(days=2, tool="claude", roots={"claude": tmp_path / "projects"})
    tool = payload["tools"]["claude"]
    assert tool["total"]["requests"] == 1
    assert tool["total"]["output_tokens"] == 50
    assert tool["dupes"] == 1
    # 100*1 + 50*5 + 200*1.25 + 1000*0.1 = 700, por 1M
    assert tool["total"]["cost"] == 0.0007
    assert tool["by_model"][0]["model"] == "claude-haiku-4-5"
    assert tool["unknown_models"] == []


def test_custo_dos_modelos_novos_bate_com_a_tabela():
    # Opus 5.5: input 4, output 20, cache read 0.2 (5% do input); fast 8/40.
    assert spend.anthropic_cost("claude-opus-5-5", None, 1_000_000, 0, 0, 0, 0) == 4.0
    assert spend.anthropic_cost("claude-opus-5-5", None, 0, 0, 0, 0, 1_000_000) == 0.2
    assert spend.anthropic_cost("claude-opus-5-5", "fast", 1_000_000, 0, 0, 0, 0) == 8.0
    # GPT-6 Sol 2/10 e Luna 0.1/0.5.
    assert spend.openai_cost("gpt-6-sol", 1_000_000, 0, 0, 0) == 2.0
    assert spend.openai_cost("gpt-6-luna", 0, 1_000_000, 0, 0) == 0.5


def test_custo_dos_modelos_codex_e_fable_bate_com_a_tabela():
    # gpt-5.3-codex: 1.75/14, cache read a 10% do input.
    assert spend.openai_cost("gpt-5.3-codex", 1_000_000, 0, 0, 0) == 1.75
    assert spend.openai_cost("gpt-5.3-codex", 0, 0, 1_000_000, 0) == 0.175
    assert spend.openai_cost("gpt-5-codex", 0, 1_000_000, 0, 0) == 10.0
    # Fable 5.1: cache read a 2.5% do input.
    assert spend.anthropic_cost("claude-fable-5-1", None, 0, 0, 0, 0, 1_000_000) == 0.25


def test_codex_desconta_cache_do_input_e_ignora_turno_acumulado(tmp_path):
    day = datetime.now().astimezone()
    folder = tmp_path / "sessions" / f"{day.year}" / f"{day.month:02d}" / f"{day.day:02d}"
    folder.mkdir(parents=True)
    ts = day.replace(microsecond=0).isoformat()
    rows = [
        {"type": "session_meta", "timestamp": ts, "payload": {"cwd": "/tmp/repo", "session_id": "sid"}},
        {"type": "turn_context", "timestamp": ts, "payload": {"model": "gpt-5.6-luna"}},
        {
            "type": "token_usage_record",
            "timestamp": ts,
            "payload": {
                "session_id": "sid",
                "response_id": "resp1",
                "usage": {
                    "input_tokens": 1000,
                    "cached_input_tokens": 800,
                    "output_tokens": 20,
                    "reasoning_output_tokens": 5,
                },
                "turn_token_usage": {"input_tokens": 999999},
            },
        },
        {
            "type": "token_usage_record",
            "timestamp": ts,
            "payload": {
                "session_id": "sid",
                "response_id": "resp1",
                "usage": {"input_tokens": 1000, "cached_input_tokens": 800, "output_tokens": 40},
            },
        },
    ]
    (folder / "rollout.jsonl").write_text("\n".join(json.dumps(row) for row in rows))
    tool = spend.build(days=2, tool="codex", roots={"codex": tmp_path / "sessions"})["tools"]["codex"]
    assert tool["total"]["requests"] == 1
    assert tool["total"]["input_tokens"] == 200
    assert tool["total"]["cache_read_tokens"] == 800
    assert tool["total"]["output_tokens"] == 40
    # 200*0.20 + 800*0.02 + 40*1.20 = 104, por 1M
    assert tool["total"]["cost"] == 0.000104


def test_codex_legado_usa_ultimo_consumo_e_separa_cache_write(tmp_path):
    day = datetime.now().astimezone()
    folder = tmp_path / "sessions" / f"{day.year}" / f"{day.month:02d}" / f"{day.day:02d}"
    folder.mkdir(parents=True)
    ts = day.isoformat()
    rows = [
        {
            "type": "session_meta",
            "timestamp": ts,
            "payload": {
                "id": "subagent-id",
                "session_id": "root-id",
                "cwd": "/tmp/repo",
                "thread_source": "subagent",
            },
        },
        {"type": "turn_context", "timestamp": ts, "payload": {"model": "gpt-5.6-luna"}},
        {
            "type": "event_msg",
            "timestamp": ts,
            "payload": {
                "type": "token_count",
                "info": {
                    "last_token_usage": {
                        "input_tokens": 1000,
                        "cached_input_tokens": 700,
                        "cache_write_input_tokens": 200,
                        "output_tokens": 10,
                    }
                },
            },
        },
    ]
    (folder / "rollout.jsonl").write_text("\n".join(json.dumps(row) for row in rows))
    tool = spend.build(days=2, tool="codex", roots={"codex": tmp_path / "sessions"})["tools"]["codex"]
    assert tool["total"]["input_tokens"] == 100
    assert tool["total"]["cache_write_tokens"] == 200
    assert tool["total"]["sessions"] == 1
    assert tool["by_origin"][0]["origin"] == "subagent"
    assert tool["sessions"][0]["session"] == "subagent-id"


def test_modelo_sem_preco_zera_custo_e_entra_na_lista(tmp_path):
    root = tmp_path / "projects" / "demo"
    root.mkdir(parents=True)
    rec = {
        "type": "assistant",
        "timestamp": datetime.now(UTC).isoformat(),
        "sessionId": "s",
        "cwd": "/tmp/demo",
        "message": {"id": "m", "model": "claude-futuro", "usage": {"input_tokens": 10, "output_tokens": 10}},
    }
    (root / "a.jsonl").write_text(json.dumps(rec))
    tool = spend.build(days=2, tool="claude", roots={"claude": tmp_path / "projects"})["tools"]["claude"]
    assert tool["total"]["cost"] == 0
    assert tool["unknown_models"] == ["claude-futuro"]


def test_opencode_usa_custo_nativo_e_marca_subagente(tmp_path):
    db = tmp_path / "opencode.db"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE session (id text, directory text, parent_id text, model text)")
    conn.execute("CREATE TABLE message (id text, session_id text, time_created integer, data text)")
    now = int(datetime.now(UTC).timestamp() * 1000)
    conn.execute(
        "INSERT INTO session VALUES (?, ?, ?, ?)",
        ("filho", "/tmp/Projetos/alfa", "pai", '{"variant":"max"}'),
    )
    conn.execute(
        "INSERT INTO message VALUES (?, ?, ?, ?)",
        (
            "m1",
            "filho",
            now,
            json.dumps({
                "role": "assistant",
                "modelID": "deepseek",
                "providerID": "opencode-go",
                "cost": 1.5,
                "tokens": {"input": 10, "output": 4, "reasoning": 1, "cache": {"read": 20, "write": 0}},
            }),
        ),
    )
    conn.commit()
    conn.close()
    tool = spend.build(days=2, tool="opencode", roots={"opencode": db})["tools"]["opencode"]
    assert tool["total"]["cost"] == 1.5
    assert tool["total"]["cache_read_tokens"] == 20
    assert tool["total"]["total_tokens"] == 35
    assert tool["by_origin"][0]["origin"] == "subagent"
    assert "max" in tool["by_model"][0]["model"]


def test_copilot_converte_nano_aiu(tmp_path):
    db = tmp_path / "session-store.db"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE sessions (id text, cwd text, repository text)")
    conn.execute(
        """CREATE TABLE assistant_usage_events (
            model text, input_tokens integer, output_tokens integer, cache_read_tokens integer,
            cache_write_tokens integer, reasoning_tokens integer, total_nano_aiu integer,
            created_at text, session_id text, parent_tool_call_id text
        )"""
    )
    conn.execute("INSERT INTO sessions VALUES ('s', '/tmp/repo', 'org/repo')")
    conn.execute(
        "INSERT INTO assistant_usage_events VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("gpt-5.6-luna", 10, 2, 3, 1, 0, 2_500_000_000, datetime.now(UTC).isoformat(), "s", None),
    )
    conn.commit()
    conn.close()
    tool = spend.build(days=2, tool="copilot", roots={"copilot": db})["tools"]["copilot"]
    assert tool["currency"] == "AIU"
    assert tool["total"]["cost"] == 2.5
    assert tool["total"]["input_tokens"] == 6
    assert tool["total"]["total_tokens"] == 12
    assert tool["by_project"][0]["project"] == "org/repo"


def test_janela_exclui_evento_antigo(tmp_path):
    root = tmp_path / "projects" / "demo"
    root.mkdir(parents=True)
    old = (datetime.now(UTC) - timedelta(days=40)).isoformat()
    rec = {
        "type": "assistant",
        "timestamp": old,
        "sessionId": "s",
        "cwd": "/tmp/demo",
        "message": {"id": "m", "model": "claude-haiku-4-5", "usage": {"input_tokens": 9, "output_tokens": 9}},
    }
    (root / "a.jsonl").write_text(json.dumps(rec))
    tool = spend.build(days=7, tool="claude", roots={"claude": tmp_path / "projects"})["tools"]["claude"]
    assert tool["total"]["requests"] == 0


def test_tempo_ativo_nao_soma_intervalo_sobreposto():
    assert spend.union_seconds([(0, 10), (5, 12), (20, 22)]) == 14


def test_fonte_ausente_nao_quebra(tmp_path):
    tool = spend.build(days=7, tool="claude", roots={"claude": tmp_path / "nao-existe"})["tools"]["claude"]
    assert tool["available"] is False
    assert tool["total"]["requests"] == 0
