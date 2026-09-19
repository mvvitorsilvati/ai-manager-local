from pathlib import Path

import app


def test_load_env_file_le_pares_e_ignora_comentarios(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text('# comentário\nAIM_TESTE_A=1\n\nAIM_TESTE_A=2\nAIM_TESTE_B="com aspas"\n')
    monkeypatch.delenv("AIM_TESTE_A", raising=False)
    monkeypatch.delenv("AIM_TESTE_B", raising=False)
    app.load_env_file(env)
    assert app.os.environ["AIM_TESTE_A"] == "2"  # última ocorrência do arquivo vence
    assert app.os.environ["AIM_TESTE_B"] == "com aspas"  # aspas removidas pelo dotenv


def test_load_env_file_nao_sobrescreve_ambiente(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("AIM_TESTE_C=do_arquivo\n")
    monkeypatch.setenv("AIM_TESTE_C", "do_ambiente")
    app.load_env_file(env)
    assert app.os.environ["AIM_TESTE_C"] == "do_ambiente"


def test_load_env_file_inexistente_nao_quebra(tmp_path):
    app.load_env_file(Path(tmp_path) / "nao-existe.env")


def test_server_address_padrao_e_local(monkeypatch):
    monkeypatch.delenv("AIM_HOST", raising=False)
    monkeypatch.delenv("AIM_PORT", raising=False)
    monkeypatch.setattr(app.sys, "argv", ["app.py"])
    assert app.server_address() == ("127.0.0.1", app.DEFAULT_PORT)


def test_server_address_respeita_env_e_flags(monkeypatch):
    monkeypatch.setenv("AIM_HOST", "0.0.0.0")
    monkeypatch.setenv("AIM_PORT", "5000")
    monkeypatch.setattr(app.sys, "argv", ["app.py", "--host", "127.0.0.1", "--port", "6000"])
    assert app.server_address() == ("127.0.0.1", 6000)


def test_project_base_usa_env_com_fallback(monkeypatch):
    monkeypatch.delenv("AIM_PROJECTS_DIR", raising=False)
    assert app.project_base() == app.DEFAULT_PROJECT_BASE
    monkeypatch.setenv("AIM_PROJECTS_DIR", "~/OutroLugar")
    assert app.project_base() == "~/OutroLugar"
