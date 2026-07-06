"""Gerenciador do FastAPI Template.

Sem argumentos: modo interativo (menus).
Com argumentos: CLI completo, pensado para humanos e LLMs.

    python gerenciar.py --help
    python gerenciar.py list-projects --json
    python gerenciar.py create-project loja --no-rbac
    python gerenciar.py create-schema loja Produto --field nome:str --field preco:float

Documentação completa: GERENCIADOR_CLI.md
"""

import sys
from pathlib import Path

BASE_DIR = Path(__file__).parent


def main() -> int:
    if len(sys.argv) > 1:
        from project_scripts.cli import main as cli_main

        return cli_main(BASE_DIR)
    from project_scripts.interactive import run

    run(BASE_DIR)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
