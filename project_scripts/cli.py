"""CLI do gerenciador — todas as operações via argumentos, sem interação.

Pensado para ser usado por humanos e por LLMs. Documentação completa em
GERENCIADOR_CLI.md na raiz do repositório.
"""

import argparse
import json
import sys
from pathlib import Path

from project_scripts.core.analyzer import (
    AnalyzerError,
    find_model,
    list_models,
    list_projects,
    project_dir,
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


def _maybe_migrate(
    base_dir: Path, pdir: Path, message: str, wanted: bool, result: dict
) -> str:
    """Roda a migration após uma mudança de schema, se --migrate foi passado."""
    if not wanted:
        return ""
    mig = run_migrate(base_dir, pdir, message)
    result["migration"] = mig
    if mig.get("no_changes"):
        return "\nMigration: nenhuma mudança detectada pelo alembic"
    return f"\nMigration gerada e aplicada: {mig['revision_file']}"


def _emit(data: dict | list, as_json: bool, human: str | None = None) -> None:
    if as_json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        print(human if human is not None else json.dumps(data, ensure_ascii=False, indent=2))


def _fail(message: str, as_json: bool) -> int:
    if as_json:
        print(json.dumps({"error": message}, ensure_ascii=False), file=sys.stderr)
    else:
        print(f"Erro: {message}", file=sys.stderr)
    return 1


def _human_fields_table(fields: list[dict]) -> str:
    lines = [
        f"{'campo':<16} {'tipo':<10} {'null':<5} {'pk':<3} {'create':<7} {'update':<7} {'read':<5} default",
        "-" * 70,
    ]
    for f in fields:
        lines.append(
            f"{f['name']:<16} {f['type']:<10} "
            f"{'sim' if f['nullable'] else '-':<5} "
            f"{'sim' if f['pk'] else '-':<3} "
            f"{'sim' if f['creatable'] else '-':<7} "
            f"{'sim' if f['updatable'] else '-':<7} "
            f"{'sim' if f['readable'] else '-':<5} "
            f"{f['default'] if f['default'] is not None else '-'}"
        )
    return "\n".join(lines)


def build_parser(base_dir: Path) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gerenciar.py",
        description=(
            "Gerenciador do FastAPI Template: cria projetos, mapeia e edita schemas. "
            "Sem argumentos abre o modo interativo. Documentação: GERENCIADOR_CLI.md"
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True)

    def add_json(p: argparse.ArgumentParser) -> None:
        p.add_argument("--json", action="store_true", help="saída em JSON (para LLMs/scripts)")

    p = sub.add_parser("list-projects", help="lista os projetos em src/")
    add_json(p)

    p = sub.add_parser("create-project", help="cria um projeto novo a partir do template")
    p.add_argument("name", help="nome do projeto (vira src/<nome>)")
    p.add_argument("--no-admin", action="store_true", help="não incluir o painel admin")
    p.add_argument(
        "--no-rbac",
        action="store_true",
        help="não incluir o sistema RBAC (permissões por rota)",
    )
    p.add_argument("--init-uv", action="store_true", help="roda uv init + uv add das dependências")
    p.add_argument("--force", action="store_true", help="sobrescreve se o projeto já existir")
    add_json(p)

    p = sub.add_parser("inspect", help="mostra features, modelos e rotas de um projeto")
    p.add_argument("project")
    add_json(p)

    p = sub.add_parser("list-schemas", help="lista os modelos (schemas) de um projeto")
    p.add_argument("project")
    add_json(p)

    p = sub.add_parser("show-schema", help="mostra os campos de um modelo")
    p.add_argument("project")
    p.add_argument("model")
    add_json(p)

    p = sub.add_parser(
        "create-schema",
        help="cria um modelo com schemas Create/Update/Read, rota fastcrud e admin",
    )
    p.add_argument("project")
    p.add_argument("model", help="nome do modelo em CamelCase (ex: Produto)")
    p.add_argument(
        "--field",
        action="append",
        default=[],
        metavar="SPEC",
        help="campo no formato nome:tipo[:flags] (repetível). Ex: --field preco:float:nullable",
    )
    p.add_argument(
        "--no-timestamps",
        action="store_true",
        help="não gerar created_at/updated_at/deleted_at",
    )
    p.add_argument("--no-route", action="store_true", help="não gerar a rota fastcrud")
    p.add_argument("--no-admin-view", action="store_true", help="não registrar no admin")
    p.add_argument("--migrate", action="store_true", help="gera e aplica a migration em seguida")
    add_json(p)

    p = sub.add_parser("add-field", help="adiciona campo(s) a um modelo existente")
    p.add_argument("project")
    p.add_argument("model")
    p.add_argument(
        "--field",
        action="append",
        required=True,
        metavar="SPEC",
        help="campo no formato nome:tipo[:flags] (repetível)",
    )
    p.add_argument("--migrate", action="store_true", help="gera e aplica a migration em seguida")
    add_json(p)

    p = sub.add_parser("remove-field", help="remove um campo de um modelo existente")
    p.add_argument("project")
    p.add_argument("model")
    p.add_argument("field", help="nome do campo a remover")
    p.add_argument("--migrate", action="store_true", help="gera e aplica a migration em seguida")
    add_json(p)

    p = sub.add_parser(
        "remove-schema",
        help="remove um modelo: schema, rota, registros no router/admin",
    )
    p.add_argument("project")
    p.add_argument("model")
    p.add_argument("--migrate", action="store_true", help="gera e aplica a migration em seguida")
    add_json(p)

    p = sub.add_parser(
        "from-mermaid",
        help="lê um diagrama Mermaid erDiagram e gera todos os modelos, FKs e rotas",
    )
    p.add_argument("project")
    p.add_argument("file", help="arquivo .mmd/.md com o bloco erDiagram")
    p.add_argument("--no-route", action="store_true", help="não gerar as rotas fastcrud")
    p.add_argument("--no-admin-view", action="store_true", help="não registrar no admin")
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="só mostra o plano (modelos, campos, relações), sem escrever nada",
    )
    p.add_argument("--migrate", action="store_true", help="gera e aplica a migration em seguida")
    add_json(p)

    p = sub.add_parser(
        "migrate",
        help="gera (autogenerate) e aplica a migration do projeto",
    )
    p.add_argument("project")
    p.add_argument("-m", "--message", default="atualizacao de schemas", help="mensagem da migration")
    add_json(p)

    p = sub.add_parser(
        "create-superuser",
        help="cria um superusuário (admin) no banco do projeto (sqlite ou postgres)",
    )
    p.add_argument("project")
    p.add_argument("--nome", required=True)
    p.add_argument("--sobrenome", default="")
    p.add_argument("--email", required=True)
    p.add_argument("--password", required=True)
    add_json(p)

    return parser


def main(base_dir: Path, argv: list[str] | None = None) -> int:
    parser = build_parser(base_dir)
    args = parser.parse_args(argv)
    src_dir = base_dir / "src"
    as_json = getattr(args, "json", False)

    try:
        if args.command == "list-projects":
            data = [project_info(src_dir / p) for p in list_projects(src_dir)]
            human = "\n".join(
                f"- {info['project']} (admin={'sim' if info['features']['admin'] else 'não'}, "
                f"rbac={'sim' if info['features']['rbac'] else 'não'}, "
                f"modelos: {', '.join(info['models']) or 'nenhum'})"
                for info in data
            ) or "Nenhum projeto em src/"
            _emit(data, as_json, human)
            return 0

        if args.command == "create-project":
            result = create_project(
                base_dir,
                args.name,
                admin=not args.no_admin,
                rbac=not args.no_rbac,
                init_uv=args.init_uv,
                force=args.force,
            )
            human = (
                f"Projeto '{result['project']}' criado em {result['path']}\n"
                f"  admin: {'sim' if result['features']['admin'] else 'não'} | "
                f"rbac: {'sim' if result['features']['rbac'] else 'não'} | "
                f"{result['files']} arquivos\nPróximos passos:\n"
                + "\n".join(f"  - {s}" for s in result["next_steps"])
            )
            _emit(result, as_json, human)
            return 0

        if args.command == "inspect":
            data = project_info(project_dir(src_dir, args.project))
            human = (
                f"Projeto: {data['project']}\n"
                f"  admin: {'sim' if data['features']['admin'] else 'não'}\n"
                f"  rbac:  {'sim' if data['features']['rbac'] else 'não'}\n"
                f"  modelos: {', '.join(data['models']) or 'nenhum'}\n"
                f"  rotas:   {', '.join(data['routes']) or 'nenhuma'}"
            )
            _emit(data, as_json, human)
            return 0

        if args.command == "list-schemas":
            pdir = project_dir(src_dir, args.project)
            data = [m.spec.to_dict() for m in list_models(pdir)]
            human = "\n".join(
                f"- {m['model']} ({len(m['fields'])} campos: "
                + ", ".join(f["name"] for f in m["fields"])
                + ")"
                for m in data
            ) or "Nenhum modelo no projeto"
            _emit(data, as_json, human)
            return 0

        if args.command == "show-schema":
            pdir = project_dir(src_dir, args.project)
            parsed = find_model(pdir, args.model)
            data = parsed.spec.to_dict()
            data["file"] = str(parsed.path)
            data["warnings"] = parsed.warnings
            human = (
                f"Modelo {data['model']} ({data['file']})\n"
                + _human_fields_table(data["fields"])
                + ("\nAvisos:\n" + "\n".join(f"  - {w}" for w in data["warnings"]) if data["warnings"] else "")
            )
            _emit(data, as_json, human)
            return 0

        if args.command == "create-schema":
            pdir = project_dir(src_dir, args.project)
            spec = ModelSpec(
                name=validate_model_name(args.model),
                fields=[parse_field_spec(s) for s in args.field],
                timestamps=not args.no_timestamps,
            )
            if not spec.fields:
                return _fail(
                    "informe ao menos um campo com --field nome:tipo[:flags]", as_json
                )
            result = create_schema(
                pdir,
                spec,
                with_route=not args.no_route,
                with_admin=not args.no_admin_view,
            )
            human = (
                f"Modelo {result['model']} criado no projeto {result['project']}:\n"
                + "\n".join(f"  - {c}" for c in result["created"])
            )
            human += _maybe_migrate(
                base_dir, pdir, f"cria modelo {spec.name}", args.migrate, result
            )
            _emit(result, as_json, human)
            return 0

        if args.command == "add-field":
            pdir = project_dir(src_dir, args.project)
            results = []
            for spec_str in args.field:
                results.append(add_field(pdir, args.model, parse_field_spec(spec_str)))
            data = results[-1] if len(results) == 1 else {"changes": results}
            added = ", ".join(r["field_added"]["name"] for r in results)
            human = f"Campo(s) {added} adicionado(s) ao modelo {results[-1]['model']}"
            warns = [w for r in results for w in r.get("warnings", [])]
            if warns:
                human += "\nAvisos:\n" + "\n".join(f"  - {w}" for w in set(warns))
            human += _maybe_migrate(
                base_dir, pdir, f"adiciona campos em {args.model}", args.migrate, data
            )
            _emit(data, as_json, human)
            return 0

        if args.command == "remove-field":
            pdir = project_dir(src_dir, args.project)
            result = remove_field(pdir, args.model, args.field)
            human = f"Campo {result['field_removed']} removido do modelo {result['model']}"
            human += _maybe_migrate(
                base_dir, pdir, f"remove campo {args.field} de {args.model}",
                args.migrate, result,
            )
            _emit(result, as_json, human)
            return 0

        if args.command == "remove-schema":
            pdir = project_dir(src_dir, args.project)
            result = remove_schema(pdir, args.model)
            human = (
                f"Modelo {result['model']} removido do projeto {result['project']}:\n"
                + "\n".join(f"  - {r}" for r in result["removed"])
            )
            human += _maybe_migrate(
                base_dir, pdir, f"remove modelo {args.model}", args.migrate, result
            )
            _emit(result, as_json, human)
            return 0

        if args.command == "from-mermaid":
            pdir = project_dir(src_dir, args.project)
            mermaid_path = Path(args.file)
            if not mermaid_path.is_file():
                return _fail(f"arquivo não encontrado: {args.file}", as_json)
            result = apply_mermaid(
                pdir,
                mermaid_path.read_text(encoding="utf-8"),
                with_route=not args.no_route,
                with_admin=not args.no_admin_view,
                dry_run=args.dry_run,
            )
            titulo = "Plano (dry-run)" if result["dry_run"] else "Modelos criados"
            linhas = [f"{titulo} no projeto {result['project']}:"]
            for m in result["models"]:
                campos = ", ".join(f["name"] for f in m["fields"])
                extras = []
                if m["relationships"]:
                    extras.append(f"{m['relationships']} relacionamento(s)")
                extras.append("com rota" if m["route"] else "sem rota")
                linhas.append(f"  - {m['model']} ({campos}) [{', '.join(extras)}]")
            for w in result["warnings"]:
                linhas.append(f"  aviso: {w}")
            human = "\n".join(linhas)
            if not result["dry_run"]:
                human += _maybe_migrate(
                    base_dir, pdir, "modelos do diagrama mermaid", args.migrate, result
                )
            _emit(result, as_json, human)
            return 0

        if args.command == "migrate":
            pdir = project_dir(src_dir, args.project)
            result = run_migrate(base_dir, pdir, args.message)
            if result.get("no_changes"):
                human = "Nenhuma mudança de schema detectada — nada a migrar"
            else:
                human = f"Migration gerada e aplicada: {result['revision_file']}"
            _emit(result, as_json, human)
            return 0

        if args.command == "create-superuser":
            pdir = project_dir(src_dir, args.project)
            result = create_superuser(
                base_dir,
                pdir,
                nome=args.nome,
                sobrenome=args.sobrenome,
                email=args.email,
                password=args.password,
            )
            human = (
                f"Superusuário {result['status']} no projeto {result['project']} "
                f"(banco: {result['database']}):\n"
                f"  email: {result['email']}\n  id: {result['id']}"
            )
            _emit(result, as_json, human)
            return 0

    except KNOWN_ERRORS as e:
        return _fail(str(e), as_json)

    return _fail(f"comando desconhecido: {args.command}", as_json)
