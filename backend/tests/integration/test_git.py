import os
import shutil
import subprocess
from pathlib import Path

import pytest

import app

skip_sem_git = pytest.mark.skipif(shutil.which("git") is None, reason="git indisponível")


def init_repo(path: Path, name="Teste", email="t@t", message="x"):
    subprocess.run(["git", "init", "-q", str(path)], check=True, capture_output=True)
    (path / "a.md").write_text("x")
    subprocess.run(["git", "-C", str(path), "add", "a.md"], check=True, capture_output=True)
    # identidade explícita no ambiente: imune a GIT_AUTHOR_*/GIT_COMMITTER_* herdados (ex.: hooks)
    identidade = {
        **os.environ,
        "GIT_AUTHOR_NAME": name, "GIT_AUTHOR_EMAIL": email,
        "GIT_COMMITTER_NAME": name, "GIT_COMMITTER_EMAIL": email,
    }
    subprocess.run(
        ["git", "-C", str(path), "commit", "-q", "-m", message],
        check=True, capture_output=True, env=identidade,
    )


def test_arquivo_fora_de_repo_nao_tem_commit(tmp_path):
    p = tmp_path / "a.md"
    p.write_text("x")
    assert app.git_last_commit(p) is None


@skip_sem_git
def test_ultimo_commit_do_arquivo(tmp_path):
    init_repo(tmp_path)
    info = app.git_last_commit(tmp_path / "a.md")
    assert info is not None
    assert (info["author"], info["email"], info["committer"]) == ("Teste", "t@t", "Teste")
    assert info["sha"]


@skip_sem_git
def test_trio_de_autores_inclui_coautor_dos_trailers(tmp_path):
    init_repo(tmp_path, name="Committer", email="c@t",
              message="x\n\nCo-Authored-By: Claude Opus 5 <noreply@anthropic.com>")
    info = app.git_last_commit(tmp_path / "a.md")
    assert info is not None
    assert info["committer"] == "Committer"
    assert info["coauthors"] == ["Claude Opus 5 <noreply@anthropic.com>"]


@skip_sem_git
def test_authors_for_em_lote(tmp_path, monkeypatch):
    init_repo(tmp_path, name="Ana", email="a@t")
    monkeypatch.setitem(
        app.SOURCE_BY_ID,
        "teste",
        {"id": "teste", "label": "t", "root": str(tmp_path), "exclude_dirs": set(), "exclude_files": set()},
    )
    result = app.authors_for([{"s": "teste", "r": "a.md"}, {"s": "teste", "r": "nao.md"}])
    assert len(result) == 1
    assert result[0]["author"] == "Ana"
