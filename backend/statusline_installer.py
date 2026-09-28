"""Instalador e gerenciador de statusline para Claude Code e Antigravity (agy).

Suporta instalação de:
- Claude Code: statusline-command.sh, subagent-statusline.sh e helpers em ~/.claude/
- Antigravity: statusline.sh em ~/.gemini/antigravity-cli/
- Ambos ou nenhum (padrão)
"""

from __future__ import annotations

import json
import logging
import os
import shlex
import shutil
import subprocess
import sys
import time
from pathlib import Path

logger = logging.getLogger("statusline")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
STATUSLINE_SRC = PROJECT_ROOT / "statusline"
JQ_DOCS_URL = "https://jqlang.org/download/"


def get_home() -> Path:
    aim_home = os.environ.get("AIM_HOME")
    if aim_home:
        return Path(aim_home).expanduser()
    return Path.home()


def jq_available() -> bool:
    """O statusline usa o jq para ler os transcripts; sem ele os scripts ficam mudos."""
    return shutil.which("jq") is not None


def jq_install_command() -> str | None:
    """Comando para instalar o jq na plataforma atual, quando houver gerenciador conhecido."""
    if sys.platform == "darwin":
        return "brew install jq" if shutil.which("brew") else None
    for manager, command in (
        ("apt-get", "sudo apt-get install -y jq"),
        ("dnf", "sudo dnf install -y jq"),
        ("yum", "sudo yum install -y jq"),
        ("pacman", "sudo pacman -S --noconfirm jq"),
        ("zypper", "sudo zypper install -y jq"),
        ("apk", "sudo apk add jq"),
    ):
        if shutil.which(manager):
            return command
    return None


def install_jq() -> dict:
    """Instala o jq pelo gerenciador de pacotes da plataforma."""
    if jq_available():
        return {"ok": True, "installed": False, "command": None, "message": "O jq já está instalado."}
    command = jq_install_command()
    if command is None:
        return {
            "ok": False,
            "installed": False,
            "command": None,
            "message": (
                "Nenhum gerenciador de pacotes conhecido para instalar o jq. "
                f"Instale manualmente: {JQ_DOCS_URL}"
            ),
        }
    try:
        proc = subprocess.run(shlex.split(command), capture_output=True, text=True, timeout=600)
    except (OSError, subprocess.SubprocessError) as exc:
        return {"ok": False, "installed": False, "command": command, "message": f"Falha ao instalar o jq: {exc}"}
    if proc.returncode != 0:
        lines = (proc.stderr or proc.stdout or "").strip().splitlines()
        hint = lines[-1] if lines else f"código {proc.returncode}"
        return {"ok": False, "installed": False, "command": command, "message": f"Falha ao instalar o jq ({hint})."}
    if not jq_available():
        return {
            "ok": False,
            "installed": False,
            "command": command,
            "message": f"O comando terminou, mas o jq não apareceu no PATH. Instale manualmente: {JQ_DOCS_URL}",
        }
    logger.info(f"jq instalado via '{command}'")
    return {"ok": True, "installed": True, "command": command, "message": "jq instalado com sucesso."}


def check_status(home: Path | None = None) -> dict:
    """Verifica se os statuslines estão instalados e configurados."""
    h = home or get_home()

    # Claude Code
    claude_dir = h / ".claude"
    claude_script = claude_dir / "statusline-command.sh"
    claude_settings = claude_dir / "settings.json"
    claude_installed = claude_script.is_file() and os.access(claude_script, os.X_OK)
    claude_configured = False
    if claude_settings.is_file():
        try:
            data = json.loads(claude_settings.read_text(encoding="utf-8"))
            sl = data.get("statusLine") or {}
            cmd = sl.get("command", "")
            claude_configured = "statusline-command" in cmd
        except (OSError, ValueError):
            pass

    # Antigravity
    agy_dir = h / ".gemini" / "antigravity-cli"
    agy_script = agy_dir / "statusline.sh"
    agy_settings = agy_dir / "settings.json"
    agy_installed = agy_script.is_file() and os.access(agy_script, os.X_OK)
    agy_configured = False
    if agy_settings.is_file():
        try:
            data = json.loads(agy_settings.read_text(encoding="utf-8"))
            sl = data.get("statusLine") or {}
            cmd = sl.get("command", "")
            agy_configured = "statusline.sh" in cmd and sl.get("enabled", True) is not False
        except (OSError, ValueError):
            pass

    return {
        "jq": {
            "available": jq_available(),
            "command": jq_install_command(),
        },
        "claude": {
            "installed": claude_installed,
            "configured": claude_configured,
            "path": str(claude_script),
        },
        "antigravity": {
            "installed": agy_installed,
            "configured": agy_configured,
            "path": str(agy_script),
        },
    }


def _backup_file(path: Path) -> Path | None:
    if not path.is_file():
        return None
    ts = time.strftime("%Y%m%d%H%M%S")
    backup = path.with_name(f"{path.name}.bak-{ts}")
    shutil.copy2(path, backup)
    return backup


def install_claude(home: Path | None = None) -> list[str]:
    """Instala os scripts e atualiza o settings.json do Claude Code."""
    h = home or get_home()
    target_dir = h / ".claude"
    target_dir.mkdir(parents=True, exist_ok=True)
    src_dir = STATUSLINE_SRC / "claude"

    installed = []
    claude_files = [
        "statusline-command.sh",
        "statusline-cost.sh",
        "statusline-subagent-cost.sh",
        "subagent-statusline.sh",
    ]

    for fname in claude_files:
        src = src_dir / fname
        if not src.is_file():
            continue
        dst = target_dir / fname
        if dst.is_file():
            _backup_file(dst)
        shutil.copy2(src, dst)
        dst.chmod(0o755)
        installed.append(str(dst))

    # Atualiza settings.json
    settings_file = target_dir / "settings.json"
    settings_data: dict = {}
    if settings_file.is_file():
        _backup_file(settings_file)
        try:
            settings_data = json.loads(settings_file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            settings_data = {}

    if home is None:
        cmd_main = "bash ~/.claude/statusline-command.sh"
        cmd_sub = "bash ~/.claude/subagent-statusline.sh"
    else:
        cmd_main = f"bash {target_dir / 'statusline-command.sh'}"
        cmd_sub = f"bash {target_dir / 'subagent-statusline.sh'}"
    settings_data["statusLine"] = {"type": "command", "command": cmd_main}
    settings_data["subagentStatusLine"] = {"type": "command", "command": cmd_sub}

    settings_file.write_text(json.dumps(settings_data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    logger.info(f"Claude statusline instalado em {target_dir}")
    return installed


def install_antigravity(home: Path | None = None) -> list[str]:
    """Instala o statusline.sh e atualiza o settings.json do Antigravity."""
    h = home or get_home()
    target_dir = h / ".gemini" / "antigravity-cli"
    target_dir.mkdir(parents=True, exist_ok=True)
    src = STATUSLINE_SRC / "antigravity" / "statusline.sh"

    installed = []
    if not src.is_file():
        return installed

    dst = target_dir / "statusline.sh"
    if dst.is_file():
        _backup_file(dst)
    shutil.copy2(src, dst)
    dst.chmod(0o755)
    installed.append(str(dst))

    # Atualiza settings.json
    settings_file = target_dir / "settings.json"
    settings_data: dict = {}
    if settings_file.is_file():
        _backup_file(settings_file)
        try:
            settings_data = json.loads(settings_file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            settings_data = {}

    cmd_agy = str(dst) if home is not None else "~/.gemini/antigravity-cli/statusline.sh"
    settings_data["statusLine"] = {
        "type": "command",
        "command": cmd_agy,
        "enabled": True,
    }

    settings_file.write_text(json.dumps(settings_data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    logger.info(f"Antigravity statusline instalado em {target_dir}")
    return installed


def resolve_target(target: str) -> str:
    """Normaliza o alvo da instalação para both/claude/antigravity/none."""
    t = target.lower().strip()
    if t in ("both", "ambos", "all", "1"):
        return "both"
    if t in ("claude", "claude-code", "2"):
        return "claude"
    if t in ("antigravity", "agy", "gemini", "3"):
        return "antigravity"
    return "none"


def install(target: str = "none", home: Path | None = None) -> dict:
    """Executa a instalação conforme o alvo selecionado.

    O jq é obrigatório para o statusline: sem ele a instalação é abortada com
    `needs_jq`, para a UI (modal) ou a CLI perguntarem antes de prosseguir.
    """
    resolved = resolve_target(target)

    if resolved != "none" and not jq_available():
        return {
            "ok": False,
            "needs_jq": True,
            "target": resolved,
            "installed_files": [],
            "status": check_status(home),
            "jq_command": jq_install_command(),
            "message": "O jq é uma dependência do statusline e não está instalado. Instale o jq para continuar.",
        }

    if resolved == "both":
        c_files = install_claude(home)
        a_files = install_antigravity(home)
        return {
            "ok": True,
            "target": "both",
            "installed_files": c_files + a_files,
            "status": check_status(home),
            "message": "Statusline instalado com sucesso para Claude Code e Antigravity.",
        }
    elif resolved == "claude":
        c_files = install_claude(home)
        return {
            "ok": True,
            "target": "claude",
            "installed_files": c_files,
            "status": check_status(home),
            "message": "Statusline instalado com sucesso para o Claude Code.",
        }
    elif resolved == "antigravity":
        a_files = install_antigravity(home)
        return {
            "ok": True,
            "target": "antigravity",
            "installed_files": a_files,
            "status": check_status(home),
            "message": "Statusline instalado com sucesso para o Antigravity (agy).",
        }
    else:
        return {
            "ok": True,
            "target": "none",
            "installed_files": [],
            "status": check_status(home),
            "message": "Nenhuma alteração realizada no statusline.",
        }


def list_backups(tool: str | None = None, home: Path | None = None) -> list[dict]:
    """Lista todos os arquivos de backup gerados para Claude Code e/ou Antigravity."""
    h = home or get_home()
    backups = []

    dirs: list[tuple[str, Path]] = []
    t = (tool or "").lower().strip()
    if not t or t in ("claude", "claude-code", "both", "all"):
        dirs.append(("claude", h / ".claude"))
    if not t or t in ("antigravity", "gemini", "agy", "both", "all"):
        dirs.append(("antigravity", h / ".gemini" / "antigravity-cli"))

    for t_name, d_path in dirs:
        if not d_path.is_dir():
            continue
        try:
            items = list(d_path.glob("*.bak-*"))
        except OSError:
            continue
        for item in sorted(items, key=lambda p: p.stat().st_mtime, reverse=True):
            if not item.is_file():
                continue
            orig = item.name.split(".bak-")[0]
            st = item.stat()
            backups.append({
                "tool": t_name,
                "backup_name": item.name,
                "original_name": orig,
                "path": str(item),
                "size": st.st_size,
                "mtime": int(st.st_mtime),
            })
    return backups


def restore_backup(tool: str, backup_name: str, home: Path | None = None) -> dict:
    """Restaura um arquivo de backup para o arquivo original correspondente."""
    h = home or get_home()
    t = tool.lower().strip()
    if t in ("claude", "claude-code"):
        target_dir = h / ".claude"
        tool_id = "claude"
    elif t in ("antigravity", "gemini", "agy"):
        target_dir = h / ".gemini" / "antigravity-cli"
        tool_id = "antigravity"
    else:
        raise ValueError(f"Ferramenta inválida para restauração: {tool}")

    backup_file = target_dir / Path(backup_name).name
    if not backup_file.is_file():
        raise FileNotFoundError(f"Arquivo de backup não encontrado: {backup_name}")

    orig_name = backup_name.split(".bak-")[0]
    target_file = target_dir / orig_name

    # Cria backup de segurança do arquivo atual antes da restauração
    if target_file.is_file():
        _backup_file(target_file)

    shutil.copy2(backup_file, target_file)
    if orig_name.endswith(".sh"):
        target_file.chmod(0o755)

    return {
        "ok": True,
        "tool": tool_id,
        "restored": backup_name,
        "target": str(target_file),
        "status": check_status(home),
        "message": f"Backup {backup_name} restaurado com sucesso para {orig_name}.",
    }


def get_preview(tool: str, home: Path | None = None) -> dict:
    """Gera a visualização prévia da barra de statusline para o terminal."""
    import re
    import subprocess

    h = home or get_home()
    t = tool.lower().strip()

    if t in ("claude", "claude-code"):
        script = h / ".claude" / "statusline-command.sh"
        if not script.is_file():
            script = STATUSLINE_SRC / "claude" / "statusline-command.sh"
        cmd = ["bash", str(script)]
        payload = {
            "model": {"display_name": "Sonnet 5 (🔶 High)"},
            "workspace": {"current_dir": str(PROJECT_ROOT)},
            "output_style": {"name": "Concise"},
            "context_window": {"used_percentage": 15, "context_window_size": 200000},
            "total_input_tokens": 135200,
            "total_output_tokens": 42800,
            "total_cache_read_input_tokens": 115000,
            "rate_limits": {
                "five_hour": {"used_percentage": 0},
                "seven_day": {"used_percentage": 12},
            },
        }
        fallback_lines = [
            (
                "\033[1;36mSonnet 5 (🔶 High)\033[0m | ai-manager-local | "
                "\033[0;90m⎇ main\033[0m | \033[0;37mstyle:Concise\033[0m"
            ),
            (
                "\033[1;32mctx:15% of 200k\033[0m | tok ↑135.2k ↓42.8k | ⚡115.0k cache | "
                "lim 5h:0% 7d:12% | \033[1;32m+24\033[0m/\033[1;31m-8\033[0m"
            ),
            "\033[1;33m▶▶ auto mode on\033[0m \033[0;90m(shift+tab to cycle) · ← for agents\033[0m",
        ]
    else:
        script = h / ".gemini" / "antigravity-cli" / "statusline.sh"
        if not script.is_file():
            script = STATUSLINE_SRC / "antigravity" / "statusline.sh"
        cmd = [sys.executable, str(script)]
        payload = {
            "product": "antigravity",
            "model": {"display_name": "Gemini 3.8 Flash (🔷 High)", "id": "gemini-3.8-flash"},
            "workspace": {"current_dir": str(PROJECT_ROOT)},
            "plan_tier": "Google AI Pro",
            "email": "developer@example.com",
            "conversation_id": "c1a2b3d4-preview",
            "context_window": {
                "total_input_tokens": 128450,
                "total_output_tokens": 42100,
                "context_window_size": 1048576,
                "used_percentage": 16.3,
                "current_usage": {"cache_read_input_tokens": 115200},
            },
            "quota": {
                "gemini-5h": {"used_fraction": 0.04, "reset_in_seconds": 10800},
                "gemini-weekly": {"used_fraction": 0.18, "reset_in_seconds": 259200},
            },
            "rate_limits": {
                "five_hour": {"used_percentage": 4},
                "seven_day": {"used_percentage": 18},
                "5h": {"used_percentage": 4},
                "7d": {"used_percentage": 18},
            },
        }
        fallback_lines = [
            (
                "\033[1;36mGemini 3.8 Flash (🔷 High)\033[0m \033[1;36m|\033[0m ai-manager-local "
                "\033[0;37m📦 v1.0.0\033[0m \033[0;37m🐍 v3.14\033[0m \033[0;90m⎇ main\033[0m"
            ),
            (
                "\033[1;32mctx:16.3% of 1.0M ▰▱▱▱▱\033[0m \033[1;36m|\033[0m tok ↑128.4k ↓42.1k "
                "\033[1;36m|\033[0m ⚡115.2k cache \033[1;36m|\033[0m \033[1;32m+24\033[0m/\033[1;31m-8\033[0m"
            ),
            (
                "\033[1;36mlim\033[0m \033[0;90m5h:\033[0m\033[1;32m4.0%\033[0m "
                "\033[1;36m⏱\033[0m \033[0;90m5h:3h\033[0m \033[1;36m|\033[0m "
                "\033[0;90m7d:\033[0m\033[1;32m18%\033[0m "
                "\033[1;36m⏱\033[0m \033[0;90m7d:3d\033[0m \033[1;36m|\033[0m "
                "\033[1;35mGoogle AI Pro\033[0m \033[0;37mdeveloper\033[0m \033[1;36m|\033[0m "
                "\033[0;90mid:c1a2b3d4\033[0m"
            ),
        ]

    try:
        proc = subprocess.run(
            cmd,
            input=json.dumps(payload),
            text=True,
            capture_output=True,
            timeout=3,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            candidate_lines = [line for line in proc.stdout.splitlines() if line.strip()]
            plain_candidates = [re.sub(r"\x1b\[[0-9;]*[a-zA-Z]", "", line).strip() for line in candidate_lines]
            if not any(plain_candidates):
                raw_lines = fallback_lines
            else:
                raw_lines = candidate_lines
                if t in ("claude", "claude-code") and len(raw_lines) == 2:
                    raw_lines.append(
                        "\033[1;33m▶▶ auto mode on\033[0m \033[0;90m(shift+tab to cycle) · ← for agents\033[0m"
                    )
        else:
            raw_lines = fallback_lines
    except (OSError, subprocess.SubprocessError):
        raw_lines = fallback_lines

    plain_lines = [re.sub(r"\x1b\[[0-9;]*[a-zA-Z]", "", line) for line in raw_lines]

    return {
        "ok": True,
        "tool": "claude" if t in ("claude", "claude-code") else "antigravity",
        "raw_lines": raw_lines,
        "plain_lines": plain_lines,
    }


def prompt_user_choice() -> str:
    """Pergunta interativamente ao usuário com opção padrão 'Não fazer nada'."""
    print("\nDeseja instalar os statusline para o claude-code e ou agy?\n")
    print("  [ ] 1. Ambos")
    print("  [ ] 2. Claude")
    print("  [ ] 3. Antigravity")
    print("  [X] 4. Não fazer nada (padrão)\n")

    try:
        choice = input("Escolha uma opção [1-4] (padrão: 4): ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return "none"

    if choice == "1":
        return "both"
    elif choice == "2":
        return "claude"
    elif choice == "3":
        return "antigravity"
    else:
        return "none"


def prompt_install_jq() -> bool:
    """Pergunta no terminal se o usuário quer instalar o jq agora."""
    command = jq_install_command()
    print("\nO jq é uma dependência do statusline e não foi encontrado no PATH.")
    if command:
        print(f"Comando sugerido: {command}")
    else:
        print(f"Instale manualmente: {JQ_DOCS_URL}")
    try:
        answer = input("Deseja instalar o jq agora? [s/N]: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return False
    if answer not in ("s", "sim", "y", "yes"):
        return False
    print(f"\n{install_jq()['message']}")
    return jq_available()


def ensure_jq() -> bool:
    """Garante o jq antes da instalação; aborta quando o usuário recusa ou não há terminal."""
    if jq_available():
        return True
    if not sys.stdin.isatty():
        print("\nO jq é uma dependência do statusline e não está instalado; instalação abortada.")
        return False
    if prompt_install_jq():
        return True
    print("\nInstalação abortada: o jq é obrigatório para o statusline.")
    return False


def main():
    argv = sys.argv[1:]

    if "--check-jq" in argv:
        if not ensure_jq():
            sys.exit(1)
        print("\njq disponível para o statusline.")
        return

    args = [a for a in argv if not a.startswith("-")]
    if args:
        target = args[0]
    elif sys.stdin.isatty():
        target = prompt_user_choice()
    else:
        target = "none"

    if resolve_target(target) != "none" and not ensure_jq():
        sys.exit(1)

    result = install(target)
    print(f"\n{result['message']}")
    if result.get("installed_files"):
        for f in result["installed_files"]:
            print(f"  ✓ {f}")


if __name__ == "__main__":
    main()
