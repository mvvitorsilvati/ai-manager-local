import json
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

import statusline_installer as statusline


def test_get_home_respeita_aim_home(monkeypatch, tmp_path):
    custom = tmp_path / "custom_home"
    monkeypatch.setenv("AIM_HOME", str(custom))
    assert statusline.get_home() == custom


def test_get_home_padrao(monkeypatch):
    monkeypatch.delenv("AIM_HOME", raising=False)
    assert statusline.get_home() == Path.home()


def test_check_status_diretorio_vazio(tmp_path):
    st = statusline.check_status(home=tmp_path)
    assert st["claude"]["installed"] is False
    assert st["claude"]["configured"] is False
    assert st["antigravity"]["installed"] is False
    assert st["antigravity"]["configured"] is False


def test_check_status_com_claude_instalado_e_configurado(tmp_path):
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir(parents=True)
    script = claude_dir / "statusline-command.sh"
    script.write_text("#!/bin/bash\necho ok\n")
    script.chmod(0o755)

    settings = claude_dir / "settings.json"
    settings.write_text(json.dumps({
        "statusLine": {"type": "command", "command": f"bash {script}"}
    }))

    st = statusline.check_status(home=tmp_path)
    assert st["claude"]["installed"] is True
    assert st["claude"]["configured"] is True
    assert st["antigravity"]["installed"] is False


def test_check_status_com_antigravity_instalado_e_configurado(tmp_path):
    agy_dir = tmp_path / ".gemini" / "antigravity-cli"
    agy_dir.mkdir(parents=True)
    script = agy_dir / "statusline.sh"
    script.write_text("#!/bin/bash\necho ok\n")
    script.chmod(0o755)

    settings = agy_dir / "settings.json"
    settings.write_text(json.dumps({
        "statusLine": {"type": "command", "command": str(script), "enabled": True}
    }))

    st = statusline.check_status(home=tmp_path)
    assert st["antigravity"]["installed"] is True
    assert st["antigravity"]["configured"] is True
    assert st["claude"]["installed"] is False


def test_check_status_com_json_invalido(tmp_path):
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir(parents=True)
    (claude_dir / "settings.json").write_text("{invalido}")

    st = statusline.check_status(home=tmp_path)
    assert st["claude"]["configured"] is False


def test_install_claude_copia_arquivos_e_configura(tmp_path):
    installed = statusline.install_claude(home=tmp_path)
    assert len(installed) > 0

    claude_dir = tmp_path / ".claude"
    script = claude_dir / "statusline-command.sh"
    assert script.is_file()
    assert bool(script.stat().st_mode & stat.S_IXUSR)

    settings_file = claude_dir / "settings.json"
    assert settings_file.is_file()
    data = json.loads(settings_file.read_text())
    assert "statusLine" in data
    assert "subagentStatusLine" in data
    assert "statusline-command.sh" in data["statusLine"]["command"]


def test_install_claude_faz_backup_de_arquivos_existentes(tmp_path):
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir(parents=True)
    script = claude_dir / "statusline-command.sh"
    script.write_text("antigo")
    settings = claude_dir / "settings.json"
    settings.write_text(json.dumps({"permissions": []}))

    statusline.install_claude(home=tmp_path)

    backups = list(claude_dir.glob("*.bak-*"))
    assert len(backups) >= 2
    assert script.read_text() != "antigo"


def test_install_antigravity_copia_script_e_configura(tmp_path):
    installed = statusline.install_antigravity(home=tmp_path)
    assert len(installed) == 1

    agy_dir = tmp_path / ".gemini" / "antigravity-cli"
    script = agy_dir / "statusline.sh"
    assert script.is_file()
    assert bool(script.stat().st_mode & stat.S_IXUSR)

    settings_file = agy_dir / "settings.json"
    assert settings_file.is_file()
    data = json.loads(settings_file.read_text())
    assert data["statusLine"]["enabled"] is True
    assert "statusline.sh" in data["statusLine"]["command"]


def test_install_antigravity_faz_backup(tmp_path):
    agy_dir = tmp_path / ".gemini" / "antigravity-cli"
    agy_dir.mkdir(parents=True)
    script = agy_dir / "statusline.sh"
    script.write_text("antigo_agy")

    statusline.install_antigravity(home=tmp_path)
    backups = list(agy_dir.glob("statusline.sh.bak-*"))
    assert len(backups) == 1
    assert backups[0].read_text() == "antigo_agy"


def test_install_target_both(tmp_path, monkeypatch):
    monkeypatch.setattr(statusline, "jq_available", lambda: True)
    res = statusline.install("both", home=tmp_path)
    assert res["ok"] is True
    assert res["target"] == "both"
    assert len(res["installed_files"]) >= 2
    assert res["status"]["claude"]["installed"] is True
    assert res["status"]["antigravity"]["installed"] is True


def test_install_target_claude(tmp_path, monkeypatch):
    monkeypatch.setattr(statusline, "jq_available", lambda: True)
    res = statusline.install("claude", home=tmp_path)
    assert res["ok"] is True
    assert res["target"] == "claude"
    assert res["status"]["claude"]["installed"] is True
    assert res["status"]["antigravity"]["installed"] is False


def test_install_target_antigravity(tmp_path, monkeypatch):
    monkeypatch.setattr(statusline, "jq_available", lambda: True)
    res = statusline.install("antigravity", home=tmp_path)
    assert res["ok"] is True
    assert res["target"] == "antigravity"
    assert res["status"]["antigravity"]["installed"] is True
    assert res["status"]["claude"]["installed"] is False


def test_install_target_none(tmp_path):
    res = statusline.install("none", home=tmp_path)
    assert res["ok"] is True
    assert res["target"] == "none"
    assert res["installed_files"] == []
    assert res["status"]["claude"]["installed"] is False
    assert res["status"]["antigravity"]["installed"] is False


def test_prompt_user_choice_opcoes(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda _: "1")
    assert statusline.prompt_user_choice() == "both"

    monkeypatch.setattr("builtins.input", lambda _: "2")
    assert statusline.prompt_user_choice() == "claude"

    monkeypatch.setattr("builtins.input", lambda _: "3")
    assert statusline.prompt_user_choice() == "antigravity"

    monkeypatch.setattr("builtins.input", lambda _: "4")
    assert statusline.prompt_user_choice() == "none"

    monkeypatch.setattr("builtins.input", lambda _: "")
    assert statusline.prompt_user_choice() == "none"


def test_prompt_user_choice_eof(monkeypatch):
    def raise_eof(_):
        raise EOFError()

    monkeypatch.setattr("builtins.input", raise_eof)
    assert statusline.prompt_user_choice() == "none"


def test_list_backups_vazio(tmp_path):
    backups = statusline.list_backups(home=tmp_path)
    assert backups == []


def test_list_backups_com_arquivos(tmp_path):
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir(parents=True)
    b1 = claude_dir / "statusline-command.sh.bak-20260927-100000"
    b1.write_text("backup claude")

    agy_dir = tmp_path / ".gemini" / "antigravity-cli"
    agy_dir.mkdir(parents=True)
    b2 = agy_dir / "statusline.sh.bak-20260927-100500"
    b2.write_text("backup agy")

    backups = statusline.list_backups(home=tmp_path)
    assert len(backups) == 2
    tools = {b["tool"] for b in backups}
    assert tools == {"claude", "antigravity"}

    claude_only = statusline.list_backups(tool="claude", home=tmp_path)
    assert len(claude_only) == 1
    assert claude_only[0]["tool"] == "claude"
    assert claude_only[0]["original_name"] == "statusline-command.sh"

    agy_only = statusline.list_backups(tool="antigravity", home=tmp_path)
    assert len(agy_only) == 1
    assert agy_only[0]["tool"] == "antigravity"
    assert agy_only[0]["original_name"] == "statusline.sh"


def test_restore_backup_sucesso(tmp_path):
    agy_dir = tmp_path / ".gemini" / "antigravity-cli"
    agy_dir.mkdir(parents=True)
    target = agy_dir / "statusline.sh"
    target.write_text("versao_atual")

    backup_name = "statusline.sh.bak-20260927-120000"
    backup = agy_dir / backup_name
    backup.write_text("versao_original_antiga")

    res = statusline.restore_backup("antigravity", backup_name, home=tmp_path)
    assert res["ok"] is True
    assert res["tool"] == "antigravity"
    assert target.read_text() == "versao_original_antiga"
    assert bool(target.stat().st_mode & stat.S_IXUSR)

    # Verifica que foi criado um backup de segurança do arquivo atual antes da restauração
    new_backups = [b for b in agy_dir.glob("statusline.sh.bak-*") if b.name != backup_name]
    assert len(new_backups) == 1
    assert new_backups[0].read_text() == "versao_atual"


def test_restore_backup_ferramenta_invalida(tmp_path):
    import pytest

    with pytest.raises(ValueError, match="Ferramenta inválida"):
        statusline.restore_backup("desconhecida", "qualquer.bak", home=tmp_path)


def test_restore_backup_arquivo_inexistente(tmp_path):
    import pytest

    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir(parents=True)

    with pytest.raises(FileNotFoundError, match="não encontrado"):
        statusline.restore_backup("claude", "inexistente.bak-123", home=tmp_path)


def test_get_preview_antigravity(tmp_path):
    preview = statusline.get_preview("antigravity", home=tmp_path)
    assert preview["ok"] is True
    assert preview["tool"] == "antigravity"
    assert len(preview["raw_lines"]) >= 1
    assert len(preview["plain_lines"]) >= 1
    full_text = " ".join(preview["plain_lines"])
    assert "Gemini" in full_text
    assert "5h:" in full_text or "7d:" in full_text
    assert "developer" in full_text
    assert "Google AI Pro" in full_text


def test_get_preview_claude(tmp_path):
    preview = statusline.get_preview("claude", home=tmp_path)
    assert preview["ok"] is True
    assert preview["tool"] == "claude"
    assert len(preview["raw_lines"]) >= 1
    assert len(preview["plain_lines"]) >= 1
    full_text = " ".join(preview["plain_lines"])
    assert "lim 5h:" in full_text or "Sonnet" in full_text


def test_custo_do_statusline_distingue_sonnet_5_5_do_sonnet_4(tmp_path, monkeypatch):
    if shutil.which("jq") is None:
        pytest.skip("jq não disponível")
    monkeypatch.setenv("TMPDIR", str(tmp_path))
    script = statusline.STATUSLINE_SRC / "claude" / "statusline-cost.sh"
    transcript = tmp_path / "sessao.jsonl"
    for modelo, sessao, esperado in (
        ("claude-sonnet-5-5", "s55", "2.0000"),
        ("claude-sonnet-4-5", "s45", "3.0000"),
    ):
        transcript.write_text(json.dumps({
            "type": "assistant",
            "message": {"model": modelo, "usage": {"input_tokens": 1_000_000}},
        }) + "\n")
        custo = subprocess.run(
            ["bash", str(script), str(transcript), sessao],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        assert custo == esperado, modelo


def test_subagent_statusline_exibe_sonnet_5_5(tmp_path, monkeypatch):
    if shutil.which("jq") is None:
        pytest.skip("jq não disponível")
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir()
    for nome in ("subagent-statusline.sh", "statusline-subagent-cost.sh"):
        shutil.copy(statusline.STATUSLINE_SRC / "claude" / nome, claude_dir / nome)
    monkeypatch.setenv("HOME", str(tmp_path))
    payload = {
        "session_id": "sessao",
        "transcript_path": "",
        "columns": 100,
        "tasks": [
            {"id": "t1", "name": "explorer", "model": "claude-sonnet-5-5", "status": "completed", "tokenCount": 1500},
            {"id": "t2", "name": "builder", "model": "claude-sonnet-5", "status": "completed", "tokenCount": 900},
        ],
    }
    saida = subprocess.run(
        ["bash", str(claude_dir / "subagent-statusline.sh")],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    conteudos = {}
    for linha in saida.splitlines():
        if linha.strip():
            item = json.loads(linha)
            conteudos[item["id"]] = item["content"]
    assert "Sonnet 5.5" in conteudos["t1"]
    assert "Sonnet 5.5" not in conteudos["t2"]


def test_statusline_exige_jq_na_instalacao(tmp_path, monkeypatch):
    monkeypatch.setattr(statusline, "jq_available", lambda: False)
    res = statusline.install("claude", home=tmp_path)
    assert res["ok"] is False
    assert res["needs_jq"] is True
    assert res["installed_files"] == []
    assert not (tmp_path / ".claude" / "statusline-command.sh").exists()


def test_status_inclui_o_estado_do_jq(tmp_path, monkeypatch):
    monkeypatch.setattr(statusline, "jq_available", lambda: False)
    monkeypatch.setattr(statusline, "jq_install_command", lambda: "brew install jq")
    st = statusline.check_status(home=tmp_path)
    assert st["jq"] == {"available": False, "command": "brew install jq"}


def test_instalacao_do_jq_chama_o_gerenciador_e_confirma(monkeypatch):
    estado = {"instalado": False}
    chamadas = []

    def fake_run(cmd, **kwargs):
        chamadas.append(cmd)
        estado["instalado"] = True
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(statusline, "jq_available", lambda: estado["instalado"])
    monkeypatch.setattr(statusline, "jq_install_command", lambda: "brew install jq")
    monkeypatch.setattr(statusline.subprocess, "run", fake_run)

    res = statusline.install_jq()
    assert res["ok"] is True
    assert res["installed"] is True
    assert chamadas == [["brew", "install", "jq"]]


def test_instalacao_do_jq_reporta_falha_sem_quebrar(monkeypatch):
    monkeypatch.setattr(statusline, "jq_available", lambda: False)
    monkeypatch.setattr(statusline, "jq_install_command", lambda: "brew install jq")
    monkeypatch.setattr(
        statusline.subprocess,
        "run",
        lambda cmd, **kwargs: subprocess.CompletedProcess(cmd, 1, "", "boom: sem rede"),
    )
    res = statusline.install_jq()
    assert res["ok"] is False
    assert res["installed"] is False
    assert "boom: sem rede" in res["message"]


def test_prompt_do_jq_aceita_instalar(monkeypatch):
    monkeypatch.setattr(statusline, "jq_available", lambda: True)
    monkeypatch.setattr(statusline, "jq_install_command", lambda: "brew install jq")
    monkeypatch.setattr(statusline, "install_jq", lambda: {"ok": True, "message": "jq instalado com sucesso."})
    monkeypatch.setattr("builtins.input", lambda _: "s")
    assert statusline.prompt_install_jq() is True


def test_prompt_do_jq_recusa_e_aborta(monkeypatch):
    monkeypatch.setattr(statusline, "jq_available", lambda: False)
    monkeypatch.setattr(statusline, "jq_install_command", lambda: "brew install jq")
    monkeypatch.setattr("builtins.input", lambda _: "n")
    assert statusline.prompt_install_jq() is False


def test_ensure_jq_sem_terminal_aborta(monkeypatch):
    monkeypatch.setattr(statusline, "jq_available", lambda: False)
    monkeypatch.setattr(statusline.sys.stdin, "isatty", lambda: False)
    assert statusline.ensure_jq() is False
