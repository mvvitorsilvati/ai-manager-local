import pytest

import app

# ---------------------------------------------------------------- walk_source

def test_walk_ignora_wal_shm_e_jsonl(tmp_path):
    for name in ("logs.sqlite-wal", "logs.sqlite-shm", "state.sqlite-journal", "history.jsonl", "ok.md"):
        (tmp_path / name).write_text("x")
    src = {"id": "codex", "root": str(tmp_path), "exclude_dirs": set(), "exclude_files": set()}
    assert {f["r"] for f in app.walk_source(src)} == {"ok.md"}


def test_walk_ignora_binarios_e_inclui_sem_extensao(tmp_path):
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "logo.png").write_text("png")
    (tmp_path / "cache.pyc").write_text("x")
    (tmp_path / "Makefile").write_text("all:")
    src = {"id": "agents", "root": str(tmp_path), "exclude_dirs": set(), "exclude_files": set()}
    rels = {f["r"] for f in app.walk_source(src)}
    assert {"assets/logo.png", "Makefile"} <= rels
    assert "cache.pyc" not in rels


# ---------------------------------------------------------------- resolve_file

def test_resolve_abre_arquivo_valido(fonte):
    (fonte / "ok.md").write_text("oi")
    assert app.resolve_file("teste", "ok.md").name == "ok.md"


def test_resolve_bloqueia_traversal(fonte):
    (fonte / "ok.md").write_text("oi")
    with pytest.raises(ValueError):
        app.resolve_file("teste", "../ok.md")


def test_resolve_bloqueia_extensao_binaria(fonte):
    (fonte / "bin.exe").write_text("x")
    with pytest.raises(ValueError):
        app.resolve_file("teste", "bin.exe")


def test_resolve_bloqueia_inexistente(fonte):
    with pytest.raises(ValueError):
        app.resolve_file("teste", "nao.md")


def test_resolve_permite_imagem(fonte):
    (fonte / "logo.png").write_text("x")
    assert app.resolve_file("teste", "logo.png").name == "logo.png"


def test_resolve_arquivo_sem_extensao_permitida(tmp_path, monkeypatch):
    (tmp_path / ".cursorrules").write_text("x")
    monkeypatch.setitem(
        app._project_sources, "proj:teste", {"id": "proj:teste", "root": str(tmp_path), "project": True}
    )
    assert app.resolve_file("proj:teste", ".cursorrules").name == ".cursorrules"


# ---------------------------------------------------------------- projetos

def test_descobre_repo_com_config(tmp_path):
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    (repo / ".claude").mkdir()
    (repo / "CLAUDE.md").write_text("x")
    assert repo in app.discover_projects(base=str(tmp_path))


def test_ignora_pasta_de_docs_sem_git_e_profunda(tmp_path):
    deep = tmp_path / "repo2" / "docs" / "deep"
    deep.mkdir(parents=True)
    (deep / "AGENTS.md").write_text("y")
    assert deep not in app.discover_projects(base=str(tmp_path))


def test_ignora_diretorio_sem_config(tmp_path):
    (tmp_path / "qualquer").mkdir()
    (tmp_path / "qualquer" / "README.md").write_text("z")
    assert app.discover_projects(base=str(tmp_path)) == []


def test_walk_projeto_inclui_root_files_e_dirs_de_config(tmp_path, fonte_projeto):
    (tmp_path / ".git").mkdir()
    (tmp_path / ".claude" / "agents").mkdir(parents=True)
    (tmp_path / ".claude" / "agents" / "coder.md").write_text("x")
    (tmp_path / ".claude" / "settings.json").write_text("{}")
    (tmp_path / "CLAUDE.md").write_text("x")
    (tmp_path / ".cursorrules").write_text("regras")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("x")
    rels = {f["r"] for f in app.walk_source(fonte_projeto)}
    assert {"CLAUDE.md", ".cursorrules", ".claude/agents/coder.md", ".claude/settings.json"} <= rels
    assert "src/app.py" not in rels


def test_walk_projeto_inclui_pasta_docs(tmp_path, fonte_projeto):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "guia.md").write_text("x")
    (tmp_path / "docs" / "img.png").write_text("x")
    rels = {f["r"] for f in app.walk_source(fonte_projeto)}
    assert {"docs/guia.md", "docs/img.png"} <= rels


def test_walk_projeto_ignora_caches(tmp_path, fonte_projeto):
    (tmp_path / ".git").mkdir()
    (tmp_path / ".claude" / "cache").mkdir(parents=True)
    (tmp_path / ".claude" / "cache" / "x.json").write_text("{}")
    (tmp_path / ".claude" / "worktrees" / "repo").mkdir(parents=True)
    (tmp_path / ".claude" / "worktrees" / "repo" / "AGENTS.md").write_text("x")
    (tmp_path / ".claude" / "settings.json").write_text("{}")
    rels = {f["r"] for f in app.walk_source(fonte_projeto)}
    assert ".claude/cache/x.json" not in rels
    assert ".claude/worktrees/repo/AGENTS.md" not in rels
    assert ".claude/settings.json" in rels
