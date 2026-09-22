"""Abrir IAs em terminais locais ou apps nativos.

Detecção por caminhos conhecidos (nada de hardcode da máquina de ninguém).
Receitas de abertura verificadas só para Terminal.app e iTerm2; o resto é
convenção `-e` e só aparece quando detectado. Apps nativos só no macOS.
Quem chama valida os allowlists (ferramenta, alvo) e resolve o cwd.
"""

from __future__ import annotations

import os
import plistlib
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

DARWIN_APPS = [
    Path("/Applications"),
    Path.home() / "Applications",
    Path("/System/Applications"),
    Path("/Applications/Utilities"),
    Path("/System/Applications/Utilities"),
]

def _run_in(binary: str, cwd: str) -> list[str]:
    """Roda o binário da IA no cwd, mantido pelo shell da máquina."""
    return [default_shell(), "-c", _terminal_script(binary, cwd)]


def _open_app(app: str, extra: list[str]) -> list[str]:
    return ["open", "-a", app, "--args", *extra]


def _darwin_app(name: str) -> Path | None:
    for base in DARWIN_APPS:
        candidate = base / name
        if candidate.is_dir():
            return candidate
    return None


def _which(names: list[str]) -> str | None:
    for name in names:
        found = shutil.which(name)
        if found:
            return found
    return None


def default_shell() -> str:
    shell = os.environ.get("SHELL")
    if shell and Path(shell).is_file():
        return shell
    return "/bin/zsh" if sys.platform == "darwin" else "/bin/bash"


def _applescript(argv: list[str]) -> list[str]:
    return ["osascript", *argv]


def _terminal_script(binary: str, cwd: str) -> str:
    return f"cd {shlex.quote(cwd)} && {binary}"


TERMINALS: list[dict] = [
    {
        "id": "iterm2",
        "label": "iTerm2",
        "platforms": ("darwin",),
        "detect": lambda: _darwin_app("iTerm.app") is not None,
        "argv": lambda binary, cwd: _applescript([
            "-e", 'tell application "iTerm" to activate',
            "-e", 'tell application "iTerm" to create window with default profile',
            "-e", f'tell application "iTerm" to tell current session of current window '
                   f'to write text "{_terminal_script(binary, cwd)}"',
        ]),
    },
    {
        "id": "terminal",
        "label": "Terminal",
        "platforms": ("darwin",),
        "detect": lambda: _darwin_app("Terminal.app") is not None,
        "argv": lambda binary, cwd: _applescript([
            "-e", 'tell application "Terminal" to activate',
            "-e", f'tell application "Terminal" to do script "{_terminal_script(binary, cwd)}"',
        ]),
    },
    {
        "id": "ghostty",
        "label": "Ghostty",
        "platforms": ("darwin",),
        "detect": lambda: _darwin_app("Ghostty.app") is not None or _which(["ghostty"]) is not None,
        "argv": lambda binary, cwd: _open_app("Ghostty", ["-e", *_run_in(binary, cwd)]),
    },
    {
        "id": "alacritty",
        "label": "Alacritty",
        "platforms": ("darwin", "linux"),
        "detect": lambda: _darwin_app("Alacritty.app") is not None or _which(["alacritty"]) is not None,
        "argv": lambda binary, cwd: _open_app("Alacritty", ["-e", *_run_in(binary, cwd)])
        if sys.platform == "darwin"
        else ["alacritty", "--working-directory", cwd, "-e", *_run_in(binary, cwd)],
    },
    {
        "id": "kitty",
        "label": "kitty",
        "platforms": ("darwin", "linux"),
        "detect": lambda: _darwin_app("kitty.app") is not None or _which(["kitty"]) is not None,
        "argv": lambda binary, cwd: _open_app("kitty", ["-e", *_run_in(binary, cwd)])
        if sys.platform == "darwin"
        else ["kitty", "--directory", cwd, *_run_in(binary, cwd)],
    },
    {
        "id": "wezterm",
        "label": "WezTerm",
        "platforms": ("darwin", "linux"),
        "detect": lambda: _darwin_app("WezTerm.app") is not None or _which(["wezterm"]) is not None,
        "argv": lambda binary, cwd: _open_app("WezTerm", ["start", "--cwd", cwd, "--", *_run_in(binary, cwd)])
        if sys.platform == "darwin"
        else ["wezterm", "start", "--cwd", cwd, "--", *_run_in(binary, cwd)],
    },
    {
        "id": "gnome-terminal",
        "label": "Terminal do GNOME",
        "platforms": ("linux",),
        "detect": lambda: _which(["gnome-terminal"]) is not None,
        "argv": lambda binary, cwd: ["gnome-terminal", f"--working-directory={cwd}", "--", *_run_in(binary, cwd)],
    },
    {
        "id": "konsole",
        "label": "Konsole",
        "platforms": ("linux",),
        "detect": lambda: _which(["konsole"]) is not None,
        "argv": lambda binary, cwd: ["konsole", "--workdir", cwd, "-e", *_run_in(binary, cwd)],
    },
    {
        "id": "xfce4-terminal",
        "label": "Terminal do Xfce",
        "platforms": ("linux",),
        "detect": lambda: _which(["xfce4-terminal"]) is not None,
        "argv": lambda binary, cwd: [
            "xfce4-terminal",
            f"--working-directory={cwd}",
            "-e",
            f"{default_shell()} -c {_terminal_script(binary, cwd)}",
        ],
    },
    {
        "id": "x-terminal-emulator",
        "label": "Terminal padrão",
        "platforms": ("linux",),
        "detect": lambda: _which(["x-terminal-emulator"]) is not None,
        "argv": lambda binary, cwd: ["x-terminal-emulator", "-e", *_run_in(binary, cwd)],
    },
    {
        "id": "wt",
        "label": "Windows Terminal",
        "platforms": ("win32",),
        "detect": lambda: _which(["wt.exe", "wt"]) is not None,
        "argv": lambda binary, cwd: ["wt.exe", "-d", cwd, binary],
    },
    {
        "id": "cmd",
        "label": "Prompt de Comando",
        "platforms": ("win32",),
        "detect": lambda: sys.platform == "win32",
        "argv": lambda binary, cwd: ["cmd.exe", "/k", f"cd /d {cwd} && {binary}"],
    },
]

# Apps nativos por IA. Abrir o app não aceita cwd nem comando: é `open -a`.
NATIVE_APPS: list[dict] = [
    {"id": "ChatGPT", "app": "ChatGPT.app", "tools": ["codex"]},
    {"id": "GitHub Copilot", "app": "GitHub Copilot.app", "tools": ["copilot"]},
    {"id": "Claude", "app": "Claude.app", "tools": ["claude"]},
    {"id": "OpenCode", "app": "OpenCode.app", "tools": ["opencode"]},
    {"id": "Gemini", "app": "Gemini.app", "tools": ["gemini"]},
    {"id": "Antigravity", "app": "Antigravity.app", "tools": ["gemini"]},
    {"id": "Antigravity IDE", "app": "Antigravity IDE.app", "tools": ["gemini"]},
]


def list_terminals() -> list[dict]:
    return [
        {"id": t["id"], "label": t["label"]}
        for t in TERMINALS
        if sys.platform in t["platforms"] and t["detect"]()
    ]


def apps_for_tool(tool: str) -> list[dict]:
    if sys.platform != "darwin":
        return []
    found = []
    for entry in NATIVE_APPS:
        if tool not in entry["tools"]:
            continue
        if _darwin_app(entry["app"]) is not None:
            found.append({"id": entry["id"], "label": entry["id"]})
    return found


def terminal_by_id(term_id: str) -> dict | None:
    return next((t for t in TERMINALS if t["id"] == term_id), None)


def argv_for_terminal(term_id: str, binary: str, cwd: str) -> list[str]:
    entry = terminal_by_id(term_id)
    if entry is None or sys.platform not in entry["platforms"]:
        raise ValueError(f"terminal desconhecido ou indisponível: {term_id}")
    return entry["argv"](binary, cwd)


def launch(argv: list[str]) -> None:
    """Executa o argv de abertura. osascript roda síncrono (erro vira exceção);
    o resto destaca sem bloquear (e sem herdar os pipes do servidor)."""
    if argv and argv[0] == "osascript":
        proc = subprocess.run(argv, capture_output=True, text=True, timeout=15)
        if proc.returncode != 0:
            raise OSError((proc.stderr or "").strip() or "osascript falhou")
        return
    subprocess.Popen(argv, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)


def app_bundle(app_id: str) -> Path | None:
    entry = next((a for a in NATIVE_APPS if a["id"] == app_id), None)
    if entry is None:
        return None
    return _darwin_app(entry["app"])


def app_icns(app_id: str) -> Path | None:
    """Ícone do bundle: CFBundleIconFile primeiro, senão qualquer .icns."""
    bundle = app_bundle(app_id)
    if bundle is None:
        return None
    resources = bundle / "Contents" / "Resources"
    info = bundle / "Contents" / "Info.plist"
    try:
        with open(info, "rb") as fh:
            icon = plistlib.load(fh).get("CFBundleIconFile")
    except OSError:
        icon = None
    if icon:
        name = str(icon)
        candidate = resources / (name if name.endswith(".icns") else f"{name}.icns")
        if candidate.is_file():
            return candidate
    try:
        found = sorted(resources.glob("*.icns"))
    except OSError:
        found = []
    return found[0] if found else None


def app_icon_png(app_id: str, cache_dir: Path) -> Path | None:
    """PNG 128px do ícone, em cache. Só macOS (conversão via sips)."""
    if sys.platform != "darwin":
        return None
    icns = app_icns(app_id)
    if icns is None:
        return None
    out = cache_dir / f"{app_id}.png"
    if out.is_file():
        return out
    try:
        cache_dir.mkdir(parents=True, exist_ok=True)
        proc = subprocess.run(
            ["sips", "-s", "format", "png", "-Z", "128", str(icns), "--out", str(out)],
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0 or not out.is_file():
        return None
    return out


def argv_for_app(app_id: str) -> list[str]:
    entry = next((a for a in NATIVE_APPS if a["id"] == app_id), None)
    if entry is None:
        raise ValueError(f"app desconhecido: {app_id}")
    path = _darwin_app(entry["app"])
    if path is None:
        raise ValueError(f"app não instalado: {entry['app']}")
    return ["open", "-a", str(path)]
