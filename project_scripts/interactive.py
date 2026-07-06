"""Modo interativo do gerenciador — mesmas operações do CLI, guiadas por menu."""

from pathlib import Path

from project_scripts.core.analyzer import (
    AnalyzerError,
    find_model,
    list_models,
    list_projects,
    project_info,
)
from project_scripts.core.editor import (
    EditorError,
    add_field,
    create_schema,
    remove_field,
    remove_schema,
)
from project_scripts.core.fields import (
    TYPE_MAP,
    FieldSpecError,
    ModelSpec,
    parse_field_spec,
    validate_model_name,
)
from project_scripts.core.mermaid import MermaidError, apply_mermaid
from project_scripts.core.migrations import MigrationError, run_migrate
from project_scripts.core.project import ProjectError, create_project
from project_scripts.core.superuser import SuperuserError, create_superuser

KNOWN_ERRORS = (
    AnalyzerError,
    EditorError,
    FieldSpecError,
    MermaidError,
    MigrationError,
    ProjectError,
    SuperuserError,
)

FIELD_HELP = f"""
Formato do campo: nome:tipo[:flags]
  tipos:  {", ".join(TYPE_MAP)}
  flags:  nullable, pk, unique, index, no-create, no-update, no-read, default=VALOR
  exemplos: nome:str | preco:float:nullable | estoque:int:default=0 | sku:str:unique
"""


def _ask(prompt: str, default: str | None = None) -> str:
    suffix = f" [{default}]" if default is not None else ""
    answer = input(f"{prompt}{suffix}: ").strip()
    return answer or (default or "")


def _ask_bool(prompt: str, default: bool = True) -> bool:
    answer = _ask(f"{prompt} (s/n)", "s" if default else "n").lower()
    return answer in {"s", "sim", "y", "1"}


def _choose_project(src_dir: Path) -> Path | None:
    projects = list_projects(src_dir)
    if not projects:
        print("Nenhum projeto encontrado em src/. Crie um primeiro.")
        return None
    print("\nProjetos:")
    for i, name in enumerate(projects, 1):
        print(f"  {i}. {name}")
    escolha = _ask("Número do projeto")
    try:
        return src_dir / projects[int(escolha) - 1]
    except (ValueError, IndexError):
        print("Opção inválida.")
        return None


def _choose_model(pdir: Path) -> str | None:
    models = list_models(pdir)
    if not models:
        print("Nenhum modelo nesse projeto.")
        return None
    print("\nModelos:")
    for i, m in enumerate(models, 1):
        campos = ", ".join(f.name for f in m.spec.fields)
        print(f"  {i}. {m.spec.name} ({campos})")
    escolha = _ask("Número do modelo")
    try:
        return models[int(escolha) - 1].spec.name
    except (ValueError, IndexError):
        print("Opção inválida.")
        return None


def _print_model(pdir: Path, model_name: str) -> None:
    parsed = find_model(pdir, model_name)
    print(f"\nModelo {parsed.spec.name} ({parsed.path})")
    for f in parsed.spec.fields:
        flags = []
        if f.pk:
            flags.append("pk")
        if f.nullable:
            flags.append("nullable")
        if f.unique:
            flags.append("unique")
        if f.index:
            flags.append("index")
        if not f.creatable:
            flags.append("no-create")
        if not f.updatable:
            flags.append("no-update")
        if not f.readable:
            flags.append("no-read")
        if f.default is not None:
            flags.append(f"default={f.default}")
        if f.auto:
            flags.append("(automático)")
        print(f"  - {f.name}: {f.py_type} {' '.join(flags)}")


def _menu_criar_projeto(base_dir: Path) -> None:
    nome = _ask("Nome do projeto")
    if not nome:
        return
    admin = _ask_bool("Incluir painel admin?", True)
    rbac = _ask_bool("Incluir sistema RBAC (permissões por rota)?", True)
    init_uv = _ask_bool("Rodar uv init + uv add das dependências?", False)
    result = create_project(base_dir, nome, admin=admin, rbac=rbac, init_uv=init_uv)
    print(f"\nProjeto '{result['project']}' criado em {result['path']}")
    print("Próximos passos:")
    for step in result["next_steps"]:
        print(f"  - {step}")


def _menu_criar_schema(src_dir: Path) -> None:
    pdir = _choose_project(src_dir)
    if pdir is None:
        return
    nome = validate_model_name(_ask("Nome do modelo (ex: Produto)"))
    print(FIELD_HELP)
    spec = ModelSpec(name=nome)
    while True:
        entrada = _ask("Campo (vazio para terminar)")
        if not entrada:
            break
        try:
            spec.fields.append(parse_field_spec(entrada))
            print(f"  + campo {spec.fields[-1].name} adicionado")
        except FieldSpecError as e:
            print(f"  ! {e}")
    if not spec.fields:
        print("Nenhum campo informado, cancelado.")
        return
    spec.timestamps = _ask_bool("Gerar created_at/updated_at/deleted_at?", True)
    with_route = _ask_bool("Gerar rota fastcrud?", True)
    with_admin = _ask_bool("Registrar no admin?", True)
    result = create_schema(pdir, spec, with_route=with_route, with_admin=with_admin)
    print(f"\nModelo {result['model']} criado:")
    for c in result["created"]:
        print(f"  - {c}")
    print("\nLembre-se de gerar a migration do banco (alembic).")


def _menu_editar_schema(src_dir: Path) -> None:
    pdir = _choose_project(src_dir)
    if pdir is None:
        return
    model = _choose_model(pdir)
    if model is None:
        return
    while True:
        _print_model(pdir, model)
        print("\n  1. Adicionar campo\n  2. Remover campo\n  0. Voltar")
        opcao = _ask("Opção")
        if opcao == "1":
            print(FIELD_HELP)
            entrada = _ask("Campo")
            if entrada:
                result = add_field(pdir, model, parse_field_spec(entrada))
                print(f"Campo {result['field_added']['name']} adicionado.")
                for w in result.get("warnings", []):
                    print(f"  aviso: {w}")
        elif opcao == "2":
            campo = _ask("Nome do campo a remover")
            if campo:
                remove_field(pdir, model, campo)
                print(f"Campo {campo} removido.")
        else:
            return


def _offer_migrate(base_dir: Path, pdir: Path, message: str) -> None:
    if not _ask_bool("Gerar e aplicar a migration agora?", True):
        return
    result = run_migrate(base_dir, pdir, message)
    if result.get("no_changes"):
        print("Nenhuma mudança de schema detectada — nada a migrar.")
    else:
        print(f"Migration gerada e aplicada: {result['revision_file']}")


def _ler_mermaid_colado() -> str:
    print(
        "\nCole o diagrama erDiagram abaixo. Quando terminar, digite 'fim' "
        "em uma linha sozinha (ou Ctrl+Z/Ctrl+D):"
    )
    linhas: list[str] = []
    while True:
        try:
            linha = input()
        except EOFError:
            break
        if linha.strip().lower() == "fim":
            break
        linhas.append(linha)
    return "\n".join(linhas)


def _menu_mermaid(base_dir: Path, src_dir: Path) -> None:
    pdir = _choose_project(src_dir)
    if pdir is None:
        return
    print("\nDe onde vem o diagrama?")
    print("  1. Arquivo (.mmd/.md com bloco erDiagram)")
    print("  2. Colar o diagrama aqui no terminal")
    origem = _ask("Opção", "1")
    if origem == "2":
        texto = _ler_mermaid_colado()
        if not texto.strip():
            print("Nada colado, cancelado.")
            return
    else:
        caminho = _ask("Caminho do arquivo", "exemplo_er.mmd")
        arquivo = Path(caminho.strip().strip('"'))
        if not arquivo.is_absolute():
            arquivo = base_dir / arquivo
        if not arquivo.is_file():
            print(f"Arquivo não encontrado: {arquivo}")
            return
        texto = arquivo.read_text(encoding="utf-8")

    plano = apply_mermaid(pdir, texto, dry_run=True)
    print("\nPlano de criação:")
    for m in plano["models"]:
        campos = ", ".join(f["name"] for f in m["fields"])
        extras = "com rota" if m["route"] else "sem rota"
        print(f"  - {m['model']} ({campos}) [{extras}]")
    for w in plano["warnings"]:
        print(f"  aviso: {w}")
    if not _ask_bool("\nCriar todos esses modelos?", True):
        return
    resultado = apply_mermaid(pdir, texto)
    print(f"\n{len(resultado['created'])} modelos criados:")
    for c in resultado["created"]:
        print(f"  - {c['model']}")
    _offer_migrate(base_dir, pdir, "modelos do diagrama mermaid")


def _menu_migrate(base_dir: Path, src_dir: Path) -> None:
    pdir = _choose_project(src_dir)
    if pdir is None:
        return
    mensagem = _ask("Mensagem da migration", "atualizacao de schemas")
    result = run_migrate(base_dir, pdir, mensagem)
    if result.get("no_changes"):
        print("Nenhuma mudança de schema detectada — nada a migrar.")
    else:
        print(f"Migration gerada e aplicada: {result['revision_file']}")


def _ask_password(prompt: str) -> str:
    import getpass
    import sys

    # getpass lê do console no Windows; com stdin redirecionado usa input()
    if sys.stdin.isatty():
        return getpass.getpass(f"{prompt}: ")
    return input(f"{prompt}: ")


def _menu_superusuario(base_dir: Path, src_dir: Path) -> None:
    pdir = _choose_project(src_dir)
    if pdir is None:
        return
    nome = _ask("Nome")
    sobrenome = _ask("Sobrenome", "")
    email = _ask("Email")
    while True:
        senha = _ask_password("Senha")
        confirma = _ask_password("Confirme a senha")
        if senha == confirma:
            break
        print("As senhas não conferem, tente de novo.")
    result = create_superuser(
        base_dir, pdir, nome=nome, sobrenome=sobrenome, email=email, password=senha
    )
    print(
        f"\nSuperusuário {result['status']} no projeto {result['project']} "
        f"(banco: {result['database']})"
    )
    print(f"  email: {result['email']}\n  id: {result['id']}")
    print("Acesse /admin com esse email e senha.")


def _menu_remover_schema(src_dir: Path) -> None:
    pdir = _choose_project(src_dir)
    if pdir is None:
        return
    model = _choose_model(pdir)
    if model is None:
        return
    if not _ask_bool(f"Remover o modelo {model} e todos os registros dele?", False):
        return
    result = remove_schema(pdir, model)
    print(f"Modelo {result['model']} removido:")
    for r in result["removed"]:
        print(f"  - {r}")


def run(base_dir: Path) -> None:
    src_dir = base_dir / "src"
    print("=== Gerenciador do FastAPI Template ===")
    print("Dica: tudo isso também funciona via argumentos (veja GERENCIADOR_CLI.md)\n")
    while True:
        print(
            "\n1. Criar projeto novo"
            "\n2. Listar projetos"
            "\n3. Inspecionar projeto (schemas e features)"
            "\n4. Criar schema (modelo + rota + admin)"
            "\n5. Editar schema (adicionar/remover campos)"
            "\n6. Remover schema"
            "\n7. Importar diagrama Mermaid (ER) — gera todos os modelos"
            "\n8. Gerar/aplicar migration (alembic)"
            "\n9. Criar superusuário (admin)"
            "\n0. Sair"
        )
        opcao = _ask("O que deseja fazer?")
        try:
            if opcao == "1":
                _menu_criar_projeto(base_dir)
            elif opcao == "2":
                for name in list_projects(src_dir):
                    info = project_info(src_dir / name)
                    print(
                        f"- {name} (admin={'sim' if info['features']['admin'] else 'não'}, "
                        f"rbac={'sim' if info['features']['rbac'] else 'não'}, "
                        f"modelos: {', '.join(info['models']) or 'nenhum'})"
                    )
            elif opcao == "3":
                pdir = _choose_project(src_dir)
                if pdir is not None:
                    info = project_info(pdir)
                    print(f"\nProjeto {info['project']}")
                    print(f"  admin: {'sim' if info['features']['admin'] else 'não'}")
                    print(f"  rbac:  {'sim' if info['features']['rbac'] else 'não'}")
                    for m in list_models(pdir):
                        _print_model(pdir, m.spec.name)
            elif opcao == "4":
                _menu_criar_schema(src_dir)
            elif opcao == "5":
                _menu_editar_schema(src_dir)
            elif opcao == "6":
                _menu_remover_schema(src_dir)
            elif opcao == "7":
                _menu_mermaid(base_dir, src_dir)
            elif opcao == "8":
                _menu_migrate(base_dir, src_dir)
            elif opcao == "9":
                _menu_superusuario(base_dir, src_dir)
            elif opcao in {"0", "sair", "exit", "q"}:
                return
        except KNOWN_ERRORS as e:
            print(f"Erro: {e}")
        except (KeyboardInterrupt, EOFError):
            print()
            return
