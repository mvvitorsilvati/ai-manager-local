import json

import pytest

import app

# ---------------------------------------------------------------- strip_jsonc

def test_strip_jsonc_remove_comentarios_e_virgulas_finais():
    src = '{\n // linha\n "a": 1, /* bloco */ "b": [1, 2,],\n}'
    assert json.loads(app.strip_jsonc(src)) == {"a": 1, "b": [1, 2]}


def test_strip_jsonc_preserva_strings_com_barras_e_virgula_chave():
    src = '{"url": "https://x//y", "p": "a, }"}'
    assert json.loads(app.strip_jsonc(src)) == {"url": "https://x//y", "p": "a, }"}


def test_strip_jsonc_preserva_aspas_escapadas():
    src = '{"q": "diz \\"oi\\" // nada"}'
    assert json.loads(app.strip_jsonc(src))["q"] == 'diz "oi" // nada'


# ---------------------------------------------------------------- categorize

@pytest.mark.parametrize(
    ("source_id", "rel", "name", "esperado"),
    [
        ("agents", "foo/SKILL.md", "SKILL.md", "skill"),
        ("codex", "AGENTS.md", "AGENTS.md", "context"),
        ("opencode", "opencode.jsonc", "opencode.jsonc", "config"),
        ("opencode", "agent/coder.md", "coder.md", "agent"),
        ("codex", "prompts/cr.md", "cr.md", "command"),
        ("agents", "skill/assets/logo.png", "logo.png", "image"),
    ],
)
def test_categorize(source_id, rel, name, esperado):
    assert app.categorize(source_id, rel, name) == esperado


# ---------------------------------------------------------------- tool_for

@pytest.mark.parametrize(
    ("source", "rel", "esperado"),
    [
        ({"tool": "codex"}, "AGENTS.md", "codex"),
        ({"project": True}, ".claude/agents/x.md", "claude"),
        ({"project": True}, "opencode.jsonc", "opencode"),
        ({"project": True}, ".cursorrules", "cursor"),
        ({"project": True}, "AGENTS.md", "shared"),
        ({"project": True}, ".mcp.json", "claude"),
    ],
)
def test_tool_for(source, rel, esperado):
    assert app.tool_for(source, rel, rel.split("/")[-1]) == esperado


# ---------------------------------------------------------------- parse_skill

def test_skill_frontmatter_com_descricao_foldada(tmp_path):
    p = tmp_path / "SKILL.md"
    p.write_text("---\nname: teste-skill\ndescription: >\n  Faz algo\n  util\n---\n# corpo\n")
    assert app.parse_skill(p, "fallback") == ("teste-skill", "Faz algo util")


def test_skill_sem_frontmatter_usa_primeira_linha(tmp_path):
    p = tmp_path / "SKILL.md"
    p.write_text("# Titulo\n\nPrimeira linha util.\n")
    assert app.parse_skill(p, "fallback") == ("fallback", "Primeira linha util.")


# ---------------------------------------------------------------- parsers de config

def test_mcp_json_de_projeto(tmp_path):
    p = tmp_path / ".mcp.json"
    p.write_text('{"mcpServers": {"linear": {"command": "npx", "args": ["-y", "mcp"]}}}')
    mcps = app.mcps_from_config(p)
    assert mcps[0]["name"] == "linear"
    assert mcps[0]["type"] == "local"


def test_plugins_de_opencode_json_com_comentarios(tmp_path):
    p = tmp_path / "opencode.jsonc"
    p.write_text('{\n // plugins\n "plugin": ["foo"],\n}')
    assert app.plugins_from_config(p) == [{"name": "foo", "enabled": True, "detail": ""}]
