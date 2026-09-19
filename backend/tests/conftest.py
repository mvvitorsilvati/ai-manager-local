import pytest

import app


@pytest.fixture
def fonte(tmp_path, monkeypatch):
    """Registra a fonte 'teste' apontando para um diretório temporário."""
    monkeypatch.setitem(
        app.SOURCE_BY_ID,
        "teste",
        {"id": "teste", "label": "t", "root": str(tmp_path), "exclude_dirs": set(), "exclude_files": set()},
    )
    return tmp_path


@pytest.fixture
def fonte_projeto(tmp_path):
    """Fonte do tipo projeto, com os mesmos excludes reais."""
    return {
        "id": "proj:teste",
        "label": "teste",
        "root": str(tmp_path),
        "project": True,
        "exclude_dirs": app.PROJECT_EXCLUDE_DIRS,
        "exclude_files": set(),
    }
