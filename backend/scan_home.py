"""Home onde o painel procura as IAs.

`AIM_HOME` sobrepõe o home do processo para leitura: configurações, credenciais
e logs das IAs saem daqui. Serve para quando as IAs rodam em outro sistema, como
painel no WSL e IAs instaladas no Windows (`/mnt/c/Users/<você>`). Sem
`AIM_HOME`, vale o home do processo — que é o certo em macOS, Linux e no
container montando o `$HOME`.

O estado do painel (backups, audit e log) continua no home real: ver
`STATE_HOME` em `app.py`.
"""

from __future__ import annotations

import os
from pathlib import Path


def scan_home() -> Path:
    return Path(os.path.expanduser(os.environ.get("AIM_HOME") or "~"))


def scan_path(root: str | Path) -> Path:
    """Expande `~` (e `~/algo`) contra o home escaneado, não o do processo."""
    texto = str(root)
    if texto == "~":
        return scan_home()
    if texto.startswith("~/"):
        return scan_home() / texto[2:]
    return Path(os.path.expanduser(texto))
