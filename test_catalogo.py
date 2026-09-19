import json
import os
import pwd
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import app


class StripJsoncTest(unittest.TestCase):
    def test_remove_comentarios_e_virgulas_finais(self):
        src = '{\n // linha\n "a": 1, /* bloco */ "b": [1, 2,],\n}'
        self.assertEqual(json.loads(app.strip_jsonc(src)), {"a": 1, "b": [1, 2]})

    def test_preserva_strings_com_barras_e_virgula_chave(self):
        src = '{"url": "https://x//y", "p": "a, }"}'
        self.assertEqual(json.loads(app.strip_jsonc(src)), {"url": "https://x//y", "p": "a, }"})

    def test_preserva_aspas_escapadas(self):
        src = '{"q": "diz \\"oi\\" // nada"}'
        self.assertEqual(json.loads(app.strip_jsonc(src))["q"], 'diz "oi" // nada')


class CategorizeTest(unittest.TestCase):
    def test_skill(self):
        self.assertEqual(app.categorize("agents", "foo/SKILL.md", "SKILL.md"), "skill")

    def test_contexto(self):
        self.assertEqual(app.categorize("codex", "AGENTS.md", "AGENTS.md"), "context")

    def test_config(self):
        self.assertEqual(app.categorize("opencode", "opencode.jsonc", "opencode.jsonc"), "config")

    def test_agente(self):
        self.assertEqual(app.categorize("opencode", "agent/coder.md", "coder.md"), "agent")

    def test_comando_codex(self):
        self.assertEqual(app.categorize("codex", "prompts/cr.md", "cr.md"), "command")


class SkillParseTest(unittest.TestCase):
    def test_frontmatter_com_descricao_foldada(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "SKILL.md"
            p.write_text("---\nname: teste-skill\ndescription: >\n  Faz algo\n  util\n---\n# corpo\n")
            name, desc = app.parse_skill(p, "fallback")
            self.assertEqual(name, "teste-skill")
            self.assertEqual(desc, "Faz algo util")

    def test_sem_frontmatter_usa_primeira_linha(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "SKILL.md"
            p.write_text("# Titulo\n\nPrimeira linha util.\n")
            name, desc = app.parse_skill(p, "fallback")
            self.assertEqual(name, "fallback")
            self.assertEqual(desc, "Primeira linha util.")


class ResolveFileTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "ok.md").write_text("oi")
        (self.root / "bin.exe").write_text("x")
        app.SOURCE_BY_ID["teste"] = {"id": "teste", "label": "t", "root": self.tmp.name,
                                     "exclude_dirs": set(), "exclude_files": set()}
        self.addCleanup(lambda: (app.SOURCE_BY_ID.pop("teste", None), self.tmp.cleanup()))

    def test_abre_arquivo_valido(self):
        self.assertEqual(app.resolve_file("teste", "ok.md").name, "ok.md")

    def test_bloqueia_traversal(self):
        with self.assertRaises(ValueError):
            app.resolve_file("teste", "../ok.md")

    def test_bloqueia_extensao(self):
        with self.assertRaises(ValueError):
            app.resolve_file("teste", "bin.exe")

    def test_bloqueia_inexistente(self):
        with self.assertRaises(ValueError):
            app.resolve_file("teste", "nao.md")


class ToolForTest(unittest.TestCase):
    def test_fonte_global_usa_tool_da_fonte(self):
        self.assertEqual(app.tool_for({"tool": "codex"}, "AGENTS.md", "AGENTS.md"), "codex")

    def test_projeto_claude(self):
        self.assertEqual(app.tool_for({"project": True}, ".claude/agents/x.md", "x.md"), "claude")

    def test_projeto_opencode(self):
        self.assertEqual(app.tool_for({"project": True}, "opencode.jsonc", "opencode.jsonc"), "opencode")

    def test_projeto_cursor(self):
        self.assertEqual(app.tool_for({"project": True}, ".cursorrules", ".cursorrules"), "cursor")

    def test_projeto_compartilhado(self):
        self.assertEqual(app.tool_for({"project": True}, "AGENTS.md", "AGENTS.md"), "shared")

    def test_projeto_mcp_json_pertence_ao_claude(self):
        self.assertEqual(app.tool_for({"project": True}, ".mcp.json", ".mcp.json"), "claude")


class ExtensoesTest(unittest.TestCase):
    def test_categoriza_imagem(self):
        self.assertEqual(app.categorize("agents", "skill/assets/logo.png", "logo.png"), "image")

    def test_walk_ignora_binarios_e_inclui_sem_extensao(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "assets").mkdir()
            (root / "assets" / "logo.png").write_text("png")
            (root / "cache.pyc").write_text("x")
            (root / "Makefile").write_text("all:")
            src = {"id": "agents", "root": tmp, "exclude_dirs": set(), "exclude_files": set()}
            rels = {f["r"] for f in app.walk_source(src)}
            self.assertIn("assets/logo.png", rels)
            self.assertIn("Makefile", rels)
            self.assertNotIn("cache.pyc", rels)

    def test_resolve_permite_imagem_e_bloqueia_binario(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "logo.png").write_text("x")
            (Path(tmp) / "pacote.zip").write_text("x")
            app.SOURCE_BY_ID["teste"] = {"id": "teste", "label": "t", "root": tmp,
                                         "exclude_dirs": set(), "exclude_files": set()}
            self.addCleanup(lambda: app.SOURCE_BY_ID.pop("teste", None))
            self.assertEqual(app.resolve_file("teste", "logo.png").name, "logo.png")
            with self.assertRaises(ValueError):
                app.resolve_file("teste", "pacote.zip")


class SaveFileTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "a.md").write_text("original")
        (self.root / "config.json").write_text("{}")
        (self.root / "logo.png").write_text("png")
        self.backups = Path(self.tmp.name + "-backups")
        self.audit = Path(self.tmp.name + "-audit.log")
        self._old = (app.BACKUP_DIR, app.AUDIT_LOG)
        app.BACKUP_DIR, app.AUDIT_LOG = self.backups, self.audit
        app.SOURCE_BY_ID["teste"] = {"id": "teste", "label": "t", "root": self.tmp.name,
                                     "exclude_dirs": set(), "exclude_files": set()}
        self.addCleanup(self._cleanup)

    def _cleanup(self):
        app.BACKUP_DIR, app.AUDIT_LOG = self._old
        app.SOURCE_BY_ID.pop("teste", None)
        shutil.rmtree(self.backups, ignore_errors=True)
        self.audit.unlink(missing_ok=True)
        self.tmp.cleanup()

    def _save(self, rel="a.md", content="novo", **kw):
        path = self.root / rel
        if "expected_mtime" not in kw and path.is_file():
            kw["expected_mtime"] = int(path.stat().st_mtime)
        return app.save_file("teste", rel, content, **kw)

    def test_salva_conteudo_e_cria_backup(self):
        result = self._save()
        self.assertEqual((self.root / "a.md").read_text(), "novo")
        self.assertEqual(result["size"], 4)
        backups = app.list_backups("teste", "a.md")
        self.assertEqual(len(backups), 1)
        self.assertTrue((self.backups).is_dir())
        self.assertIn("save", self.audit.read_text())

    def test_conflito_de_mtime(self):
        with self.assertRaises(app.ConflictError) as ctx:
            self._save(expected_mtime=123)
        self.assertTrue(ctx.exception.info.get("mtime"))
        self.assertEqual((self.root / "a.md").read_text(), "original")

    def test_conflito_no_mesmo_segundo_usa_nanossegundos(self):
        stale_ns = (self.root / "a.md").stat().st_mtime_ns
        self._save(content="primeira")  # sobrescreve dentro do mesmo segundo
        with self.assertRaises(app.ConflictError):
            self._save(content="segunda", expected_mtime=None, expected_mtime_ns=stale_ns)
        self.assertEqual((self.root / "a.md").read_text(), "primeira")

    def test_force_ignora_conflito(self):
        self._save(expected_mtime=123, force=True)
        self.assertEqual((self.root / "a.md").read_text(), "novo")

    def test_json_invalido_retorna_422(self):
        with self.assertRaises(app.ApiError) as ctx:
            self._save(rel="config.json", content="{oops}")
        self.assertEqual(ctx.exception.status, 422)
        self.assertEqual((self.root / "config.json").read_text(), "{}")

    def test_binario_retorna_415(self):
        with self.assertRaises(app.ApiError) as ctx:
            self._save(rel="logo.png", content="x")
        self.assertEqual(ctx.exception.status, 415)

    def test_traversal_bloqueado(self):
        with self.assertRaises(app.ApiError) as ctx:
            self._save(rel="../fora.md", content="x")
        self.assertEqual(ctx.exception.status, 400)

    def test_prune_mantem_dez_versoes(self):
        for i in range(12):
            self._save(content=f"versao {i}")
            (self.root / "a.md").touch()
        self.assertEqual(len(app.list_backups("teste", "a.md")), app.BACKUP_KEEP)

    def test_restaura_backup(self):
        self._save(content="alterado")
        (self.root / "a.md").touch()
        versions = app.list_backups("teste", "a.md")
        self.assertEqual(len(versions), 1)
        result = app.restore_backup("teste", "a.md", versions[0]["name"])
        self.assertTrue(result["ok"])
        self.assertEqual((self.root / "a.md").read_text(), "original")

    def test_restore_bloqueia_nome_invalido(self):
        with self.assertRaises(app.ApiError) as ctx:
            app.restore_backup("teste", "a.md", "../../etc/passwd")
        self.assertEqual(ctx.exception.status, 400)


class GitInfoTest(unittest.TestCase):
    def test_arquivo_fora_de_repo_nao_tem_commit(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "a.md"
            p.write_text("x")
            self.assertIsNone(app.git_last_commit(p))

    @unittest.skipUnless(shutil.which("git"), "git indisponível")
    def test_ultimo_commit_do_arquivo(self):
        with tempfile.TemporaryDirectory() as tmp:
            subprocess.run(["git", "init", "-q", tmp], check=True, capture_output=True)
            p = Path(tmp) / "a.md"
            p.write_text("x")
            subprocess.run(["git", "-C", tmp, "add", "a.md"], check=True, capture_output=True)
            subprocess.run(["git", "-C", tmp, "-c", "user.name=Teste", "-c", "user.email=t@t",
                            "commit", "-q", "-m", "x"], check=True, capture_output=True)
            info = app.git_last_commit(p)
            self.assertIsNotNone(info)
            assert info is not None
            self.assertEqual(info["author"], "Teste")
            self.assertEqual(info["email"], "t@t")
            self.assertTrue(info["sha"])

    def test_file_info_traz_dono_criacao_e_tamanho(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "a.md"
            p.write_text("abc")
            info = app.file_info(p)
            self.assertEqual(info["owner"], pwd.getpwuid(os.getuid()).pw_name)
            self.assertGreater(info["created"], 0)
            self.assertEqual(info["size"], 3)


class ProjectDiscoveryTest(unittest.TestCase):
    def test_detecta_repo_com_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            repo = base / "repo"
            (repo / ".git").mkdir(parents=True)
            (repo / ".claude").mkdir()
            (repo / "CLAUDE.md").write_text("x")
            found = app.discover_projects(base=tmp)
            self.assertIn(repo, found)

    def test_ignora_pasta_de_docs_sem_git_e_profunda(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            deep = base / "repo2" / "docs" / "deep"
            deep.mkdir(parents=True)
            (deep / "AGENTS.md").write_text("y")
            self.assertNotIn(deep, app.discover_projects(base=tmp))

    def test_ignora_diretorio_sem_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "qualquer").mkdir()
            (base / "qualquer" / "README.md").write_text("z")
            self.assertEqual(app.discover_projects(base=tmp), [])


class ProjectWalkTest(unittest.TestCase):
    def _source(self, tmp):
        return {"id": "proj:teste", "label": "teste", "root": tmp, "project": True,
                "exclude_dirs": app.PROJECT_EXCLUDE_DIRS, "exclude_files": set()}

    def test_inclui_root_files_e_dirs_de_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".git").mkdir()
            (root / ".claude" / "agents").mkdir(parents=True)
            (root / ".claude" / "agents" / "coder.md").write_text("x")
            (root / ".claude" / "settings.json").write_text("{}")
            (root / "CLAUDE.md").write_text("x")
            (root / ".cursorrules").write_text("regras")
            (root / "src").mkdir()
            (root / "src" / "app.py").write_text("x")
            rels = {f["r"] for f in app.walk_source(self._source(tmp))}
            self.assertIn("CLAUDE.md", rels)
            self.assertIn(".cursorrules", rels)
            self.assertIn(".claude/agents/coder.md", rels)
            self.assertIn(".claude/settings.json", rels)
            self.assertNotIn("src/app.py", rels)

    def test_inclui_pasta_docs_do_projeto(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "docs").mkdir()
            (root / "docs" / "guia.md").write_text("x")
            (root / "docs" / "img.png").write_text("x")
            rels = {f["r"] for f in app.walk_source(self._source(tmp))}
            self.assertIn("docs/guia.md", rels)
            self.assertIn("docs/img.png", rels)

    def test_ignora_caches_dentro_de_claude(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".git").mkdir()
            (root / ".claude" / "cache").mkdir(parents=True)
            (root / ".claude" / "cache" / "x.json").write_text("{}")
            (root / ".claude" / "worktrees" / "repo").mkdir(parents=True)
            (root / ".claude" / "worktrees" / "repo" / "AGENTS.md").write_text("x")
            (root / ".claude" / "settings.json").write_text("{}")
            rels = {f["r"] for f in app.walk_source(self._source(tmp))}
            self.assertNotIn(".claude/cache/x.json", rels)
            self.assertNotIn(".claude/worktrees/repo/AGENTS.md", rels)
            self.assertIn(".claude/settings.json", rels)


class ProjectConfigParseTest(unittest.TestCase):
    def test_mcp_json_de_projeto(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / ".mcp.json"
            p.write_text('{"mcpServers": {"linear": {"command": "npx", "args": ["-y", "mcp"]}}}')
            mcps = app.mcps_from_config(p)
            self.assertEqual(mcps[0]["name"], "linear")
            self.assertEqual(mcps[0]["type"], "local")

    def test_plugins_de_opencode_json_com_comentarios(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "opencode.jsonc"
            p.write_text('{\n // plugins\n "plugin": ["foo"],\n}')
            plugins = app.plugins_from_config(p)
            self.assertEqual(plugins, [{"name": "foo", "enabled": True, "detail": ""}])

    def test_projeto_resolve_arquivo_sem_extensao_permitida(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".cursorrules").write_text("x")
            app._project_sources["proj:teste"] = {"id": "proj:teste", "root": tmp, "project": True}
            self.addCleanup(lambda: app._project_sources.pop("proj:teste", None))
            self.assertEqual(app.resolve_file("proj:teste", ".cursorrules").name, ".cursorrules")


if __name__ == "__main__":
    unittest.main()
