from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import app
import sessions


def test_higienizacao_titulo_e_preview():
    # Remove tags <USER_REQUEST> e HTML
    raw = "<USER_REQUEST>Criar testes unitários para o sistema</USER_REQUEST>"
    assert sessions.clean_title(raw) == "Criar testes unitários para o sistema"

    raw_html = "<div>Título <b>com</b> formatação</div>"
    assert sessions.clean_title(raw_html) == "Título com formatação"

    # Truncamento com reticências
    long_title = "A" * 150
    cleaned = sessions.clean_title(long_title, max_len=50)
    assert len(cleaned) == 51  # 50 chars + "…"
    assert cleaned.endswith("…")

    # Preview com ANSI escapes
    ansi_text = "\x1b[32mSucesso na execução\x1b[0m do comando"
    assert sessions.clean_preview(ansi_text) == "Sucesso na execução do comando"


def test_sanitizacao_skills():
    raw_skills = ["tgrep", "linear-mcp", "a", "invalid skill with space", "true", "tgrep"]
    sanitized = sessions.sanitize_skills(raw_skills)
    assert sanitized == ["linear-mcp", "tgrep"]


def test_rotulo_projeto():
    assert sessions.project_label("/Users/dev/Projetos/Activesoft/sigaweb") == "Activesoft/sigaweb"
    assert sessions.project_label("/Users/dev/repo") == "dev/repo"
    assert sessions.project_label(None) == "global"


def test_comando_reabertura_por_ia():
    assert sessions.resume_command("claude", "claude", "sess-123") == "claude --resume sess-123"
    assert sessions.resume_command("codex", "codex", "sess-456") == "codex resume sess-456"
    assert sessions.resume_command("opencode", "opencode", "sess-789") == "opencode session sess-789"
    assert sessions.resume_command("copilot", "copilot", "sess-abc") == "copilot --resume sess-abc"
    assert "resume sess-xyz" in sessions.resume_command("gemini", "gemini", "sess-xyz")


def test_metodo_instalacao_cli(monkeypatch):
    import shutil

    # Simula binário no Homebrew Cask
    monkeypatch.setattr(shutil, "which", lambda b: "/opt/homebrew/Caskroom/codex/0.157.1/bin/codex")
    assert app.cli_install_method("codex") == "brew (cask)"

    # Simula binário no Homebrew Cellar
    monkeypatch.setattr(shutil, "which", lambda b: "/opt/homebrew/Cellar/opencode/1.18.32/bin/opencode")
    assert app.cli_install_method("opencode") == "brew"

    # Simula binário via npm / fnm
    monkeypatch.setattr(
        shutil, "which", lambda b: "/Users/dev/.local/share/fnm/node-versions/v24/lib/node_modules/copilot"
    )
    assert app.cli_install_method("copilot") == "npm"

    # Simula binário via script install.sh (.local/share/claude)
    monkeypatch.setattr(shutil, "which", lambda b: "/Users/dev/.local/share/claude/versions/2.1.283")
    assert app.cli_install_method("claude") == "install.sh"

    # Simula binário ausente
    monkeypatch.setattr(shutil, "which", lambda b: None)
    assert app.cli_install_method("inexistente") is None


def test_scan_sessoes_claude(tmp_path: Path):
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir(parents=True)
    history_file = claude_dir / "history.jsonl"
    projects_dir = claude_dir / "projects" / "p1"
    projects_dir.mkdir(parents=True)

    # Escreve entrada no history
    history_file.write_text(
        json.dumps({
            "sessionId": "session-claude-1",
            "display": "Refatoração de serviço de cobrança",
            "project": "/Users/dev/Projetos/sigaweb",
            "timestamp": 1727400000000,
        })
        + "\n"
    )

    # Escreve transcript no projects
    transcript_file = projects_dir / "session-claude-1.jsonl"
    lines = [
        json.dumps({
            "type": "user",
            "timestamp": "2026-09-27T10:00:00Z",
            "message": {"content": "Como refatorar o boleto?"},
        }),
        json.dumps({
            "type": "assistant",
            "timestamp": "2026-09-27T10:01:00Z",
            "message": {
                "content": [
                    {"type": "tool_use", "name": "Skill", "input": {"skill": "tgrep"}},
                    {"type": "text", "text": "Aqui está a proposta de refatoração."},
                ],
                "usage": {"input_tokens": 100, "output_tokens": 50, "cache_read_input_tokens": 20},
            },
        }),
    ]
    transcript_file.write_text("\n".join(lines) + "\n")

    res = sessions.scan_claude_sessions(home=tmp_path)
    assert len(res) == 1
    s = res[0]
    assert s["id"] == "session-claude-1"
    assert s["title"] == "Refatoração de serviço de cobrança"
    assert s["skills"] == ["tgrep"]
    assert s["tokens"] == 170
    assert s["resume_cmd"] == "claude --resume session-claude-1"


def test_scan_sessoes_gemini(tmp_path: Path):
    gemini_root = tmp_path / ".gemini" / "antigravity-cli"
    gemini_root.mkdir(parents=True)
    history_file = gemini_root / "history.jsonl"
    history_file.write_text(
        json.dumps({
            "conversationId": "gemini-conv-1",
            "display": "Ajuste de statusline e monitoramento",
            "workspace": "/Users/dev/Projetos/ai-manager-local",
            "timestamp": 1727400000000,
        })
        + "\n"
    )

    brain_dir = gemini_root / "brain" / "gemini-conv-1" / ".system_generated" / "logs"
    brain_dir.mkdir(parents=True)
    transcript_file = brain_dir / "transcript.jsonl"
    transcript_file.write_text(
        json.dumps({
            "type": "USER_INPUT",
            "source": "USER_EXPLICIT",
            "content": "<USER_REQUEST>Configurar statusline do agy</USER_REQUEST>",
            "created_at": "2026-09-27T10:00:00Z",
        })
        + "\n"
        + json.dumps({
            "type": "PLANNER_RESPONSE",
            "content": "Statusline configurado com sucesso.",
            "created_at": "2026-09-27T10:02:00Z",
        })
        + "\n"
    )

    cache_dir = gemini_root / "cache"
    cache_dir.mkdir(parents=True)
    usage_file = cache_dir / "session_usage.json"
    usage_file.write_text(
        json.dumps({
            "gemini-conv-1": {
                "total_in": 500,
                "total_out": 200,
                "cache_read": 100,
                "cost_usd": 0.0025,
            }
        })
    )

    res = sessions.scan_gemini_sessions(home=tmp_path)
    assert len(res) == 1
    s = res[0]
    assert s["id"] == "gemini-conv-1"
    assert s["tokens"] == 800
    assert s["cost"] == 0.0025
    assert "resume" in s["resume_cmd"]


def test_scan_sessoes_opencode(tmp_path: Path):
    db_dir = tmp_path / ".local" / "share" / "opencode"
    db_dir.mkdir(parents=True)
    db_file = db_dir / "opencode.db"

    conn = sqlite3.connect(db_file)
    conn.execute("""
        CREATE TABLE session (
            id TEXT PRIMARY KEY,
            title TEXT,
            directory TEXT,
            cost REAL,
            tokens_input INTEGER,
            tokens_output INTEGER,
            tokens_cache_read INTEGER,
            time_created INTEGER,
            time_updated INTEGER
        )
    """)
    conn.execute("""
        CREATE TABLE message (
            id TEXT PRIMARY KEY,
            session_id TEXT,
            data TEXT,
            time_created INTEGER
        )
    """)
    conn.execute("""
        CREATE TABLE part (
            id TEXT PRIMARY KEY,
            session_id TEXT,
            data TEXT
        )
    """)

    conn.execute(
        """
        INSERT INTO session VALUES (
            'ses_1', 'Correção de bug de autenticação', '/tmp/repo',
            0.015, 1000, 500, 200, 1727400000000, 1727401000000
        )
        """
    )
    conn.execute(
        """
        INSERT INTO message VALUES ('msg_1', 'ses_1', '{"content": "Erro ao autenticar"}', 1727400000000)
    """
    )
    conn.execute(
        """
        INSERT INTO part VALUES ('part_1', 'ses_1', '{"tool": "skill", "args": {"name": "github-pr-metrics"}}')
    """
    )
    conn.commit()
    conn.close()

    res = sessions.scan_opencode_sessions(home=tmp_path)
    assert len(res) == 1
    s = res[0]
    assert s["id"] == "ses_1"
    assert s["title"] == "Correção de bug de autenticação"
    assert s["skills"] == ["github-pr-metrics"]
    assert s["tokens"] == 1700
    assert s["cost"] == 0.015
    assert s["resume_cmd"] == "opencode session ses_1"


def test_busca_e_filtro_multi_termo(tmp_path: Path):
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir(parents=True)
    history_file = claude_dir / "history.jsonl"
    history_file.write_text(
        json.dumps({
            "sessionId": "s-1",
            "display": "Refatorar banco de dados PostgreSQL",
            "project": "/Projetos/financeiro",
            "timestamp": 1727400000000,
        })
        + "\n"
        + json.dumps({
            "sessionId": "s-2",
            "display": "Ajustar testes de frontend com vitest",
            "project": "/Projetos/ui",
            "timestamp": 1727401000000,
        })
        + "\n"
    )

    # Busca que casa apenas com a primeira sessão
    res1 = sessions.get_sessions("claude", query="postgres financeiro", home=tmp_path, force_refresh=True)
    assert res1["total"] == 1
    assert res1["sessions"][0]["id"] == "s-1"

    # Busca que casa apenas com a segunda sessão
    res2 = sessions.get_sessions("claude", query="vitest", home=tmp_path, force_refresh=True)
    assert res2["total"] == 1
    assert res2["sessions"][0]["id"] == "s-2"

    # Busca sem correspondência
    res3 = sessions.get_sessions("claude", query="inexistente termo", home=tmp_path, force_refresh=True)
    assert res3["total"] == 0


def test_abertura_sessao_com_diretorio(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(app, "OPENABLE", {"claude": "claude"})
    launched = []
    monkeypatch.setattr(app.open_with, "launch", lambda argv: launched.append(argv))
    monkeypatch.setattr(app.open_with, "list_terminals", lambda: [{"id": "terminal", "label": "Terminal"}])
    monkeypatch.setattr(
        app.open_with,
        "argv_for_terminal",
        lambda ident, cmd, cwd: ["osascript", "-e", f"cd '{cwd}' && {cmd}"],
    )

    proj_dir = tmp_path / "meu_projeto"
    proj_dir.mkdir()

    res = app.run_open(
        tool="claude",
        target="terminal:terminal",
        project=None,
        session_id="ses-12345",
        cwd=str(proj_dir),
    )
    assert res["ok"] is True
    assert len(launched) == 1
    assert f"cd '{proj_dir}' && claude --resume ses-12345" in launched[0][2]


def test_get_sessions_todas_as_ias(tmp_path: Path):
    # Cria uma sessão claude e uma sessão gemini
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir(parents=True)
    hist_claude = claude_dir / "history.jsonl"
    hist_claude.write_text(
        json.dumps({
            "sessionId": "s-c1",
            "display": "Refatoração de API",
            "project": str(tmp_path),
            "timestamp": 1727400000000,
        })
        + "\n"
    )

    agy_root = tmp_path / ".gemini" / "antigravity-cli"
    agy_root.mkdir(parents=True)
    hist_agy = agy_root / "history.jsonl"
    hist_agy.write_text(
        json.dumps({
            "conversationId": "s-g1",
            "display": "Análise arquitetural",
            "workspace": str(tmp_path),
            "timestamp": 1727400005000,
        })
        + "\n"
    )

    res = sessions.get_sessions("all", home=tmp_path, force_refresh=True)
    assert res["ok"] is True
    assert res["tool"] == "all"
    assert res["total"] >= 2
    ids = [s["id"] for s in res["sessions"]]
    assert "s-g1" in ids
    assert "s-c1" in ids

    # Busca cross-tool por termo
    res_search = sessions.get_sessions("all", query="arquitetural", home=tmp_path, force_refresh=True)
    assert res_search["total"] == 1
    assert res_search["sessions"][0]["id"] == "s-g1"


def test_scan_sessoes_windows_caminhos(tmp_path: Path):
    # Simula estrutura do OpenCode no AppData do Windows
    opencode_win = tmp_path / "AppData" / "Local" / "opencode"
    opencode_win.mkdir(parents=True)
    db_file = opencode_win / "opencode.db"
    conn = sqlite3.connect(db_file)
    conn.execute(
        """
        CREATE TABLE session (
            id TEXT, title TEXT, directory TEXT, cost REAL, tokens_input INT,
            tokens_output INT, tokens_cache_read INT, time_created INT, time_updated INT
        )
        """
    )
    conn.execute(
        """
        INSERT INTO session VALUES (
            'win_ses_1', 'Sessão no Windows', 'C:\\Projetos\\sigaweb', 0.05, 100, 200, 50, 1727400000000, 1727400000000
        )
        """
    )
    conn.commit()
    conn.close()

    res = sessions.scan_opencode_sessions(home=tmp_path)
    assert len(res) == 1
    assert res[0]["id"] == "win_ses_1"
    assert res[0]["title"] == "Sessão no Windows"


def test_terminal_powershell_windows(monkeypatch):
    import sys
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(app.open_with, "_which", lambda names: "C:\\Windows\\System32\\powershell.exe")

    terms = app.open_with.list_terminals()
    term_ids = {t["id"] for t in terms}
    assert "powershell" in term_ids

    ps_entry = next(t for t in app.open_with.TERMINALS if t["id"] == "powershell")
    argv = ps_entry["argv"]("claude", "C:\\workspace")
    assert "powershell.exe" in argv[0]
    assert "Set-Location -LiteralPath 'C:\\workspace'; claude" in argv[3]


def test_detalhes_sessao_claude_com_mensagens(tmp_path: Path):
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir(parents=True)
    history_file = claude_dir / "history.jsonl"
    projects_dir = claude_dir / "projects" / "p1"
    projects_dir.mkdir(parents=True)

    history_file.write_text(
        json.dumps({
            "sessionId": "ses-det-claude",
            "display": "Refatorar módulo de pagamentos",
            "project": "/Projetos/pagamentos",
            "timestamp": 1727400000000,
        })
        + "\n"
    )

    transcript_file = projects_dir / "ses-det-claude.jsonl"
    lines = [
        json.dumps({
            "type": "user",
            "timestamp": "2026-09-27T10:00:00Z",
            "message": {"content": "Como implementar o split de pagamentos?"},
        }),
        json.dumps({
            "type": "assistant",
            "timestamp": "2026-09-27T10:01:00Z",
            "message": {
                "content": [
                    {"type": "tool_use", "name": "Skill", "input": {"skill": "payment-splitter"}},
                    {"type": "text", "text": "Segue o desenho arquitetural do split."},
                ],
            },
        }),
    ]
    transcript_file.write_text("\n".join(lines) + "\n")

    res = sessions.get_session_details("claude", "ses-det-claude", home=tmp_path)
    assert res["ok"] is True
    assert res["id"] == "ses-det-claude"
    assert res["title"] == "Refatorar módulo de pagamentos"
    assert "payment-splitter" in res["skills"]
    assert len(res["messages"]) == 2
    assert res["messages"][0]["role"] == "user"
    assert "Como implementar o split" in res["messages"][0]["content"]
    assert res["messages"][1]["role"] == "assistant"
    assert "Segue o desenho arquitetural" in res["messages"][1]["content"]


def test_detalhes_sessao_gemini_com_ferramentas(tmp_path: Path):
    gemini_root = tmp_path / ".gemini" / "antigravity-cli"
    gemini_root.mkdir(parents=True)
    history_file = gemini_root / "history.jsonl"
    history_file.write_text(
        json.dumps({
            "conversationId": "conv-gemini-det",
            "display": "Auditoria de agentes",
            "workspace": "/Projetos/ai-manager-local",
            "timestamp": 1727400000000,
        })
        + "\n"
    )

    brain_dir = gemini_root / "brain" / "conv-gemini-det" / ".system_generated" / "logs"
    brain_dir.mkdir(parents=True)
    transcript_file = brain_dir / "transcript.jsonl"
    lines = [
        json.dumps({
            "type": "USER_INPUT",
            "source": "USER_EXPLICIT",
            "content": "<USER_REQUEST>Auditar o tier do repositório</USER_REQUEST>",
            "created_at": "2026-09-27T10:00:00Z",
        }),
        json.dumps({
            "type": "PLANNER_RESPONSE",
            "content": "Iniciando a auditoria das 10 dimensões.",
            "tool_calls": [{"toolAction": "Checking files", "toolSummary": "Verify configs"}],
            "created_at": "2026-09-27T10:01:00Z",
        }),
    ]
    transcript_file.write_text("\n".join(lines) + "\n")

    res = sessions.get_session_details("gemini", "conv-gemini-det", home=tmp_path)
    assert res["ok"] is True
    assert res["id"] == "conv-gemini-det"
    assert len(res["messages"]) == 2
    assert res["messages"][0]["role"] == "user"
    assert res["messages"][0]["content"] == "Auditar o tier do repositório"
    assert res["messages"][1]["role"] == "assistant"
    assert "Iniciando a auditoria" in res["messages"][1]["content"]
    assert "Checking files" in res["messages"][1]["tool_calls"]


def test_detalhes_sessao_fallback_metadados(tmp_path: Path):
    # Sessão inexistente no transcript retorna fallback estruturado sem erro
    res = sessions.get_session_details("codex", "sess-inexistente", home=tmp_path)
    assert res["ok"] is True
    assert res["id"] == "sess-inexistente"
    assert res["tool"] == "codex"
    assert isinstance(res["messages"], list)


def test_higienizacao_conteudo_markdown_preserva_formatacao():
    raw_markdown = """
| Coluna A | Coluna B |
|---|---|
| Valor 1 | Valor 2 |

```python
def ola():
    print("mundo")
```
"""
    cleaned = sessions.clean_message_content(raw_markdown)
    assert "| Coluna A | Coluna B |" in cleaned
    assert "```python\ndef ola():\n    print(\"mundo\")\n```" in cleaned
    assert "\n" in cleaned

    # Remove metadados internos e tags de envelope
    envelope = (
        "<USER_REQUEST>Quero ajustar o drawer</USER_REQUEST>"
        "<ADDITIONAL_METADATA><debug>info</debug></ADDITIONAL_METADATA>"
    )
    assert sessions.clean_message_content(envelope) == "Quero ajustar o drawer"

    # Remove sequencias ANSI
    ansi = "\x1b[34m# Titulo formatado\x1b[0m\nLinha com texto."
    assert sessions.clean_message_content(ansi) == "# Titulo formatado\nLinha com texto."


def test_agregacao_turnos_assistente_gemini_com_multiplos_passos(tmp_path: Path):
    gemini_root = tmp_path / ".gemini" / "antigravity-cli"
    gemini_root.mkdir(parents=True)
    brain_dir = gemini_root / "brain" / "conv-multi-step" / ".system_generated" / "logs"
    brain_dir.mkdir(parents=True)
    transcript_file = brain_dir / "transcript.jsonl"

    markdown_table = "| Ferramenta | Status |\n|---|---|\n| Pytest | 100% |"
    lines = [
        json.dumps({
            "type": "USER_INPUT",
            "source": "USER_EXPLICIT",
            "content": "<USER_REQUEST>Executar verificações completas</USER_REQUEST>",
            "created_at": "2026-09-27T10:00:00Z",
        }),
        # Passo 1: apenas tool call
        json.dumps({
            "type": "PLANNER_RESPONSE",
            "content": "",
            "tool_calls": [{"toolAction": "Analyzing code", "toolSummary": "Code check"}],
            "created_at": "2026-09-27T10:00:05Z",
        }),
        # Passo 2: outra tool call
        json.dumps({
            "type": "PLANNER_RESPONSE",
            "content": "",
            "tool_calls": [{"toolAction": "Running tests", "toolSummary": "Test execution"}],
            "created_at": "2026-09-27T10:00:10Z",
        }),
        # Passo 3: resposta final com tabela markdown
        json.dumps({
            "type": "PLANNER_RESPONSE",
            "content": f"Verificação concluída:\n\n{markdown_table}",
            "tool_calls": [],
            "created_at": "2026-09-27T10:00:15Z",
        }),
    ]
    transcript_file.write_text("\n".join(lines) + "\n")

    res = sessions.get_session_details("gemini", "conv-multi-step", home=tmp_path)
    assert res["ok"] is True
    # Em vez de 4 mensagens fragmentadas, deve consolidar em 2 mensagens (1 user, 1 assistant)
    assert len(res["messages"]) == 2
    assert res["messages"][0]["role"] == "user"
    assert res["messages"][0]["content"] == "Executar verificações completas"

    assistant_msg = res["messages"][1]
    assert assistant_msg["role"] == "assistant"
    # Conteúdo deve preservar a tabela markdown íntegra com quebras de linha
    assert "| Ferramenta | Status |" in assistant_msg["content"]
    assert "\n" in assistant_msg["content"]
    # As ferramentas de todos os passos intermediários devem estar consolidadas
    assert "Analyzing code" in assistant_msg["tool_calls"]
    assert "Running tests" in assistant_msg["tool_calls"]


def test_agregacao_turnos_assistente_claude_com_multiplos_blocos(tmp_path: Path):
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir(parents=True)
    projects_dir = claude_dir / "projects" / "p1"
    projects_dir.mkdir(parents=True)
    transcript_file = projects_dir / "ses-claude-multi.jsonl"

    lines = [
        json.dumps({
            "type": "user",
            "timestamp": "2026-09-27T10:00:00Z",
            "message": {"content": "Como otimizar a consulta?"},
        }),
        # Bloco 1 do assistente com chamada de tool
        json.dumps({
            "type": "assistant",
            "timestamp": "2026-09-27T10:00:05Z",
            "message": {
                "content": [
                    {"type": "tool_use", "name": "tgrep", "input": {"pattern": "SELECT"}},
                ],
            },
        }),
        # Bloco 2 do assistente com resposta em texto
        json.dumps({
            "type": "assistant",
            "timestamp": "2026-09-27T10:00:10Z",
            "message": {
                "content": [
                    {"type": "text", "text": "Recomendo adicionar um índice composto:\n```sql\nCREATE INDEX idx;\n```"},
                ],
            },
        }),
    ]
    transcript_file.write_text("\n".join(lines) + "\n")

    res = sessions.get_session_details("claude", "ses-claude-multi", home=tmp_path)
    assert res["ok"] is True
    # Consolida em 2 mensagens (1 user, 1 assistant)
    assert len(res["messages"]) == 2
    assert res["messages"][0]["role"] == "user"
    assistant_msg = res["messages"][1]
    assert assistant_msg["role"] == "assistant"
    assert "Grep(SELECT)" in assistant_msg["tool_calls"]
    assert "CREATE INDEX idx;" in assistant_msg["content"]
    assert "\n```sql\n" in assistant_msg["content"]


def test_formatacao_amigavel_chamadas_ferramentas(tmp_path: Path):
    home = tmp_path
    # Bash
    cmd_tool = sessions.format_tool_call("run_command", {"CommandLine": "git status -s"}, home=home)
    assert cmd_tool == "Bash(git status -s)"

    # Read
    file_path = str(home / "backend" / "app.py")
    read_tool = sessions.format_tool_call("view_file", {"AbsolutePath": file_path}, home=home)
    assert read_tool == "Read(~/backend/app.py)"

    # Edit
    edit_tool = sessions.format_tool_call("replace_file_content", {"TargetFile": file_path}, home=home)
    assert edit_tool == "Edit(~/backend/app.py)"

    # Grep
    grep_tool = sessions.format_tool_call("tgrep", {"pattern": "format_tool"}, home=home)
    assert grep_tool == "Grep(format_tool)"

    # MCP
    mcp_tool = sessions.format_tool_call("mcp__linear__get_issue", {"id": "1234"}, home=home)
    assert mcp_tool == "MCP:get_issue(1234)"


def test_extracao_imagens_mensagens_usuario_gemini(tmp_path: Path):
    sid = "conv-gemini-img"
    brain = tmp_path / ".gemini" / "antigravity-cli" / "brain" / sid
    logs = brain / ".system_generated" / "logs"
    logs.mkdir(parents=True)
    tpath = logs / "transcript.jsonl"
    line = json.dumps({
        "type": "USER_INPUT",
        "source": "USER_EXPLICIT",
        "created_at": "2026-09-27T10:00:00Z",
        "content": "veja este print",
        "media": [
            {"mime_type": "image/png", "uri": "/tmp/uploaded_print.png"}
        ],
    })
    tpath.write_text(line + "\n")

    res = sessions.get_session_details("gemini", sid, home=tmp_path)
    assert res["ok"] is True
    assert len(res["messages"]) == 1
    msg = res["messages"][0]
    assert msg["role"] == "user"
    assert msg["content"] == "veja este print"
    assert "images" in msg
    assert len(msg["images"]) == 1
    img = msg["images"][0]
    assert img["name"] == "uploaded_print.png"
    assert img["url"] == f"/api/sessions/media?tool=gemini&id={sid}&name=uploaded_print.png"
    assert img["mime"] == "image/png"


def test_extracao_imagens_mensagens_usuario_claude(tmp_path: Path):
    sid = "ses-claude-img"
    proj_dir = tmp_path / ".claude" / "projects"
    proj_dir.mkdir(parents=True)
    tfile = proj_dir / f"{sid}.jsonl"
    b64_pixel = (
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
    )
    line = json.dumps({
        "type": "user",
        "timestamp": "2026-09-27T10:00:00Z",
        "message": {
            "content": [
                {"type": "text", "text": "veja o screenshot"},
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/png",
                        "data": b64_pixel,
                    },
                },
            ]
        },
    })
    tfile.write_text(line + "\n")

    res = sessions.get_session_details("claude", sid, home=tmp_path)
    assert res["ok"] is True
    assert len(res["messages"]) == 1
    msg = res["messages"][0]
    assert msg["role"] == "user"
    assert msg["content"] == "veja o screenshot"
    assert "images" in msg
    assert len(msg["images"]) == 1
    img = msg["images"][0]
    assert img["url"].startswith("data:image/png;base64,")
    assert img["name"] == "screenshot.png"


def test_claude_exibe_apenas_prompts_e_formata_comando_com_imagem(tmp_path: Path):
    sid = "ses-claude-command"
    proj_dir = tmp_path / ".claude" / "projects" / "p1"
    proj_dir.mkdir(parents=True)
    command = (
        "<command-message>revisar-pr</command-message>\n"
        "<command-name>/revisar-pr</command-name>\n"
        "<command-args>https://example.test/123</command-args>"
    )
    pixel = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
    records = [
        {"type": "user", "message": {"content": command}},
        {
            "type": "user",
            "isMeta": True,
            "message": {"content": [{"type": "text", "text": "Base directory for this skill: /internal"}]},
        },
        {"type": "user", "message": {"content": [{"type": "tool_result", "content": "resultado interno"}]}},
        {"type": "user", "isCompactSummary": True, "message": {"content": "Resumo interno da conversa"}},
        {"type": "user", "message": {"content": [
            {"type": "text", "text": "# Pedido\n\n**Confira** a imagem"},
            {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": pixel}},
        ]}},
        {"type": "assistant", "message": {"content": [{"type": "text", "text": "Imagem recebida."}]}},
    ]
    (proj_dir / f"{sid}.jsonl").write_text("\n".join(json.dumps(record) for record in records) + "\n")

    overview = sessions.scan_claude_sessions(home=tmp_path)[0]
    assert overview["title"] == "/revisar-pr https://example.test/123"
    assert overview["message_count"] == 3

    messages = sessions.get_session_details("claude", sid, home=tmp_path)["messages"]
    assert [(msg["role"], msg["content"]) for msg in messages] == [
        ("user", "/revisar-pr https://example.test/123"),
        ("user", "# Pedido\n\n**Confira** a imagem"),
        ("assistant", "Imagem recebida."),
    ]
    assert messages[1]["images"] == [{
        "url": f"data:image/png;base64,{pixel}",
        "name": "screenshot.png",
        "mime": "image/png",
    }]


def test_claude_remove_notificacoes_internas_e_desembrulha_lembretes(tmp_path: Path):
    sid = "ses-claude-noise"
    proj_dir = tmp_path / ".claude" / "projects" / "p1"
    proj_dir.mkdir(parents=True)
    notification = (
        "<task-notification>\n<task-id>abc</task-id>\n"
        "<tool-use-id>toolu_123</tool-use-id>\n<status>stopped</status>\n"
        "<summary>Comando em background encerrado.</summary>\n</task-notification>"
    )
    caveat = "<local-command-caveat>Caveat: mensagens geradas pelo usuário.</local-command-caveat>"
    reminder = "<system-reminder>\nLembrete interno.\n</system-reminder>"
    records = [
        {"type": "user", "message": {"content": notification}},
        {"type": "user", "message": {"content": caveat}},
        {
            "type": "user",
            "message": {"content": "<command-name>/effort</command-name>\n<command-message>effort</command-message>"},
        },
        {
            "type": "user",
            "message": {"content": [{"type": "text", "text": reminder}]},
        },
        {"type": "user", "message": {"content": "Pedido real"}},
        {"type": "assistant", "message": {"content": [{"type": "text", "text": "Resposta."}]}},
    ]
    (proj_dir / f"{sid}.jsonl").write_text("\n".join(json.dumps(record) for record in records) + "\n")

    overview = sessions.scan_claude_sessions(home=tmp_path)[0]
    assert overview["title"] == "Lembrete interno."

    messages = sessions.get_session_details("claude", sid, home=tmp_path)["messages"]
    assert [(msg["role"], msg["content"]) for msg in messages] == [
        ("user", "/effort"),
        ("user", "Lembrete interno."),
        ("user", "Pedido real"),
        ("assistant", "Resposta."),
    ]


def test_obter_nome_exibicao_usuario(monkeypatch):
    import subprocess
    import sys

    # Simula retorno do Git
    monkeypatch.setattr(
        subprocess, "check_output", lambda *args, **kwargs: "Vitor Silva\n"
    )
    assert sessions.get_user_display_name() == "Vitor Silva"

    # Simula falha do Git e pwd com variável USER
    monkeypatch.setattr(
        subprocess, "check_output", lambda *args, **kwargs: (_ for _ in ()).throw(Exception("git error"))
    )
    monkeypatch.setitem(sys.modules, "pwd", None)
    monkeypatch.setenv("USER", "joao.souza")
    assert sessions.get_user_display_name() == "Joao Souza"


def test_detalhes_de_ferramentas_em_sessao_claude(tmp_path: Path):
    sid = "sess-tool-details-1"
    proj_dir = tmp_path / ".claude" / "projects" / "p1"
    proj_dir.mkdir(parents=True)
    tfile = proj_dir / f"{sid}.jsonl"

    lines = [
        json.dumps({
            "type": "assistant",
            "timestamp": "2026-09-27T10:00:00Z",
            "message": {
                "content": [
                    {"type": "text", "text": "Executando teste"},
                    {
                        "type": "tool_use",
                        "name": "Bash",
                        "input": {"command": "ls -la /tmp/repo"},
                    },
                ]
            },
        })
    ]
    tfile.write_text("\n".join(lines) + "\n")

    res = sessions.get_session_details("claude", sid, home=tmp_path)
    assert res["ok"] is True
    assert len(res["messages"]) == 1
    msg = res["messages"][0]
    assert "tool_calls" in msg
    assert "tool_details" in msg
    assert len(msg["tool_details"]) == 1
    td = msg["tool_details"][0]
    assert td["name"] == "Bash"
    assert "ls -la /tmp/repo" in td["raw"]
    assert "Bash(ls -la /tmp/repo)" in td["display"]


def test_sincronizacao_estrita_tool_calls_e_details_com_comandos_repetidos(tmp_path: Path):
    """Garante correspondência 1:1 exata de índice entre tool_calls e tool_details sem descompasso."""
    brain_dir = tmp_path / ".gemini" / "antigravity-cli" / "brain" / "conv-sync-check"
    log_dir = brain_dir / ".system_generated" / "logs"
    log_dir.mkdir(parents=True)
    tfile = log_dir / "transcript.jsonl"

    # Sequência onde o assistente roda git diff duas vezes e depois git push
    lines = [
        json.dumps({
            "step_index": 0,
            "type": "USER_INPUT",
            "source": "USER_EXPLICIT",
            "content": "<USER_REQUEST>verifique e suba as alteracoes</USER_REQUEST>",
        }),
        json.dumps({
            "step_index": 1,
            "type": "PLANNER_RESPONSE",
            "source": "MODEL",
            "tool_calls": [{"name": "run_command", "args": {"CommandLine": "git diff"}}],
        }),
        json.dumps({
            "step_index": 2,
            "type": "PLANNER_RESPONSE",
            "source": "MODEL",
            "tool_calls": [{"name": "run_command", "args": {"CommandLine": "git diff"}}],
        }),
        json.dumps({
            "step_index": 3,
            "type": "PLANNER_RESPONSE",
            "source": "MODEL",
            "tool_calls": [{"name": "run_command", "args": {"CommandLine": "git push origin main"}}],
        }),
    ]
    tfile.write_text("\n".join(lines) + "\n")

    res = sessions.get_session_details("gemini", "conv-sync-check", home=tmp_path)
    assert res["ok"] is True
    assert len(res["messages"]) == 2
    assistant_msg = res["messages"][1]

    tcs = assistant_msg.get("tool_calls", [])
    tds = assistant_msg.get("tool_details", [])

    # Devem ter o mesmo comprimento exato e correspondência índice por índice
    assert len(tcs) == 3
    assert len(tds) == 3
    for idx in range(3):
        assert tcs[idx] == tds[idx]["display"]

    assert "git push" in tcs[2]
    assert "git push origin main" in tds[2]["raw"]


def test_is_slash_command_detecta_meta_comandos():
    assert sessions.is_slash_command("/model") is True
    assert sessions.is_slash_command("/mcp") is True
    assert sessions.is_slash_command("/effort high") is True
    assert sessions.is_slash_command("/cost") is True
    assert sessions.is_slash_command("/status") is True
    assert sessions.is_slash_command("/help") is True
    # Não deve considerar caminhos absolutos ou prompts normais
    assert sessions.is_slash_command("/Users/vitor.silva/projeto/arquivo.py") is False
    assert sessions.is_slash_command("/home/ubuntu/app") is False
    assert sessions.is_slash_command("Como fazer o deploy no kubernetes?") is False
    assert sessions.is_slash_command("") is False
    assert sessions.is_slash_command(None) is False


def test_pick_meaningful_title_ignora_slash_commands_iniciais():
    candidates = ["/model", "/effort high", "Refatorar autenticação OAuth", "Ajustar testes"]
    title = sessions.pick_meaningful_title(candidates, fallback="sessao-123")
    assert title == "Refatorar autenticação OAuth"

    # Se todos forem slash commands, faz fallback para o primeiro
    only_slash = ["/model", "/mcp"]
    assert sessions.pick_meaningful_title(only_slash, fallback="sessao-123") == "/model"

    # Se lista vazia, usa fallback
    assert sessions.pick_meaningful_title([], fallback="sessao-padrao") == "sessao-padrao"


def test_get_sessions_retorna_top_cost_e_top_tokens(tmp_path: Path):
    # Cria estrutura de mock com sessões de diferentes custos e tokens
    claude_root = tmp_path / ".claude"
    claude_root.mkdir()
    history_file = claude_root / "history.jsonl"
    history_file.write_text(
        json.dumps({"sessionId": "s-baixa", "display": "tarefa barata", "timestamp": 1000}) + "\n"
        + json.dumps({"sessionId": "s-alta", "display": "tarefa cara", "timestamp": 2000}) + "\n"
    )

    proj_dir = claude_root / "projects" / "test"
    proj_dir.mkdir(parents=True)
    (proj_dir / "s-baixa.jsonl").write_text(
        json.dumps({
            "type": "assistant",
            "message": {
                "model": "claude-sonnet-4-5",
                "content": [{"type": "text", "text": "ok"}],
                "usage": {"input_tokens": 100, "output_tokens": 50},
            },
        }) + "\n"
    )
    (proj_dir / "s-alta.jsonl").write_text(
        json.dumps({
            "type": "assistant",
            "message": {
                "model": "claude-sonnet-4-5",
                "content": [{"type": "text", "text": "ok"}],
                "usage": {"input_tokens": 100000, "output_tokens": 50000},
            },
        }) + "\n"
    )

    res = sessions.get_sessions("claude", home=tmp_path, force_refresh=True)
    assert res["ok"] is True
    assert "top_cost" in res
    assert "top_tokens" in res
    assert len(res["top_cost"]) > 0
    assert len(res["top_tokens"]) > 0
    assert res["top_cost"][0]["id"] == "s-alta"
    assert res["top_tokens"][0]["id"] == "s-alta"



