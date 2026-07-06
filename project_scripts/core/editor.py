"""Operações de escrita em projetos: criar schema, adicionar/remover campos,
remover schemas, com registro automático em router/admin/schemas.__init__.
"""

import re
from pathlib import Path

from project_scripts.core.analyzer import (
    AnalyzerError,
    ParsedModel,
    find_model,
    list_models,
    project_features,
)
from project_scripts.core.fields import FieldSpec, ModelSpec
from project_scripts.core.generator import (
    render_admin_setup,
    render_admin_view,
    render_model_classes,
    render_route_file,
    render_router_registration,
    render_schema_file,
    render_schemas_init_line,
    required_imports,
)


class EditorError(ValueError):
    """Erro de edição com mensagem amigável."""


def _ensure_imports(source: str, needed: list[str]) -> str:
    """Garante que as linhas de import existam no início do arquivo."""
    lines = source.splitlines()
    existing = {line.strip() for line in lines if line.strip().startswith(("from ", "import "))}
    missing = [imp for imp in needed if imp not in existing]
    if not missing:
        return source
    # insere após a última linha de import do topo
    insert_at = 0
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith(("from ", "import ", "#")) or not stripped:
            insert_at = i + 1
        else:
            break
    for imp in reversed(missing):
        lines.insert(insert_at, imp)
    return "\n".join(lines) + ("\n" if source.endswith("\n") else "")


def _rewrite_model_block(parsed: ParsedModel, spec: ModelSpec) -> None:
    """Regenera as classes do modelo dentro do arquivo, preservando o resto."""
    source = parsed.path.read_text(encoding="utf-8")
    lines = source.splitlines()
    new_block = render_model_classes(spec, table_extras=parsed.table_extras or None)
    lines[parsed.block_start : parsed.block_end] = new_block.splitlines()
    new_source = "\n".join(lines) + "\n"
    new_source = _ensure_imports(new_source, required_imports(spec))
    parsed.path.write_text(new_source, encoding="utf-8")


def create_schema(
    pdir: Path,
    spec: ModelSpec,
    *,
    with_route: bool = True,
    with_admin: bool = True,
    table_extras: list[str] | None = None,
    type_checking_imports: list[tuple[str, str]] | None = None,
    runtime_imports: list[str] | None = None,
) -> dict:
    """Cria o arquivo de schema e registra nas partes do projeto."""
    features = project_features(pdir)
    schema_path = pdir / "schemas" / f"{spec.module}.py"
    if schema_path.exists():
        raise EditorError(
            f"o schema '{spec.module}.py' já existe no projeto '{pdir.name}'. "
            f"Use add-field/remove-field para editar ou remove-schema para apagar."
        )
    existing = [m.spec.name.lower() for m in list_models(pdir)]
    if spec.name.lower() in existing:
        raise EditorError(f"já existe um modelo chamado '{spec.name}' no projeto")

    created: list[str] = []
    schema_path.write_text(
        render_schema_file(
            spec,
            table_extras=table_extras,
            type_checking_imports=type_checking_imports,
            runtime_imports=runtime_imports,
        ),
        encoding="utf-8",
    )
    created.append(str(schema_path))

    # registra no schemas/__init__.py (necessário para o alembic enxergar)
    init_path = pdir / "schemas" / "__init__.py"
    if init_path.exists():
        content = init_path.read_text(encoding="utf-8")
        line = render_schemas_init_line(spec)
        if line not in content:
            init_path.write_text(content + line, encoding="utf-8")
            created.append(f"{init_path} (import registrado)")

    if with_route:
        route_path = pdir / "routes" / f"{spec.module}.py"
        route_path.write_text(
            render_route_file(spec, rbac=features["rbac"]), encoding="utf-8"
        )
        created.append(str(route_path))
        _register_route(pdir, spec)
        created.append(f"{pdir / 'router.py'} (rota registrada)")

    if with_admin and features["admin"]:
        view_path = pdir / "admin" / "admin_view.py"
        view_path.write_text(
            view_path.read_text(encoding="utf-8") + render_admin_view(spec),
            encoding="utf-8",
        )
        setup_path = pdir / "admin" / "admin_setup.py"
        setup_path.write_text(
            setup_path.read_text(encoding="utf-8") + render_admin_setup(spec),
            encoding="utf-8",
        )
        created.append(f"{view_path} (view do admin)")
        created.append(f"{setup_path} (view registrada)")

    return {
        "project": pdir.name,
        "model": spec.name,
        "created": created,
        "fields": [f.to_dict() for f in spec.fields],
    }


def _register_route(pdir: Path, spec: ModelSpec) -> None:
    router_path = pdir / "router.py"
    content = router_path.read_text(encoding="utf-8")
    if f"{spec.module}.router" in content:
        return
    # adiciona o módulo à linha "from routes import ..."
    match = re.search(r"^from routes import (.+)$", content, flags=re.MULTILINE)
    if match:
        modules = [m.strip() for m in match.group(1).split(",")]
        if spec.module not in modules:
            modules.append(spec.module)
            new_line = "from routes import " + ", ".join(sorted(modules))
            content = content.replace(match.group(0), new_line, 1)
    else:
        content = f"from routes import {spec.module}\n" + content
    if not content.endswith("\n"):
        content += "\n"
    content += render_router_registration(spec)
    router_path.write_text(content, encoding="utf-8")


def add_field(pdir: Path, model_name: str, fspec: FieldSpec) -> dict:
    parsed = find_model(pdir, model_name)
    if parsed.spec.get_field(fspec.name) is not None:
        raise EditorError(
            f"o campo '{fspec.name}' já existe no modelo '{parsed.spec.name}'"
        )
    if fspec.pk and parsed.spec.has_custom_pk:
        raise EditorError(f"o modelo '{parsed.spec.name}' já tem uma primary key")
    parsed.spec.fields.append(fspec)
    _rewrite_model_block(parsed, parsed.spec)
    return {
        "project": pdir.name,
        "model": parsed.spec.name,
        "field_added": fspec.to_dict(),
        "file": str(parsed.path),
        "warnings": parsed.warnings,
    }


def _strip_admin_column(pdir: Path, model_name: str, field_name: str) -> bool:
    """Remove referências <Model>.<campo> do admin_view.py (ex: column_list)."""
    view_path = pdir / "admin" / "admin_view.py"
    if not view_path.exists():
        return False
    content = view_path.read_text(encoding="utf-8")
    new_content = re.sub(rf"\b{model_name}\.{field_name}\b\s*,?\s*", "", content)
    if new_content != content:
        view_path.write_text(new_content, encoding="utf-8")
        return True
    return False


def remove_field(pdir: Path, model_name: str, field_name: str) -> dict:
    parsed = find_model(pdir, model_name)
    fspec = parsed.spec.get_field(field_name)
    if fspec is None:
        nomes = ", ".join(f.name for f in parsed.spec.fields)
        raise EditorError(
            f"campo '{field_name}' não existe no modelo '{parsed.spec.name}'. "
            f"Campos: {nomes}"
        )
    if fspec.auto:
        raise EditorError(
            f"o campo '{field_name}' é automático (id/timestamps) e não pode ser removido"
        )
    parsed.spec.fields.remove(fspec)
    _rewrite_model_block(parsed, parsed.spec)
    warnings = list(parsed.warnings)
    if _strip_admin_column(pdir, parsed.spec.name, field_name):
        warnings.append(
            f"referências a {parsed.spec.name}.{field_name} removidas de admin_view.py"
        )
    return {
        "project": pdir.name,
        "model": parsed.spec.name,
        "field_removed": field_name,
        "file": str(parsed.path),
        "warnings": warnings,
    }


def _remove_admin_view(pdir: Path, model_name: str) -> bool:
    """Remove a classe <Model>Admin e o import do schema em admin_view.py."""
    import ast

    view_path = pdir / "admin" / "admin_view.py"
    if not view_path.exists():
        return False
    source = view_path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return False
    lines = source.splitlines()
    to_remove: list[tuple[int, int]] = []
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == f"{model_name}Admin":
            to_remove.append((node.lineno - 1, node.end_lineno or node.lineno))
        if isinstance(node, ast.ImportFrom) and node.module == f"schemas.{model_name.lower()}":
            to_remove.append((node.lineno - 1, node.end_lineno or node.lineno))
    if not to_remove:
        return False
    for start, end in sorted(to_remove, reverse=True):
        del lines[start:end]
    view_path.write_text("\n".join(lines).rstrip("\n") + "\n", encoding="utf-8")
    return True


def remove_schema(pdir: Path, model_name: str) -> dict:
    parsed = find_model(pdir, model_name)
    spec = parsed.spec
    removed: list[str] = []

    parsed.path.unlink()
    removed.append(str(parsed.path))

    # schemas/__init__.py
    init_path = pdir / "schemas" / "__init__.py"
    if init_path.exists():
        content = init_path.read_text(encoding="utf-8")
        new_content = re.sub(
            rf"^from schemas\.{spec.module} import .*\n?",
            "",
            content,
            flags=re.MULTILINE,
        )
        if new_content != content:
            init_path.write_text(new_content, encoding="utf-8")
            removed.append(f"{init_path} (import removido)")

    # routes/<module>.py + router.py
    route_path = pdir / "routes" / f"{spec.module}.py"
    if route_path.exists():
        route_path.unlink()
        removed.append(str(route_path))
    router_path = pdir / "router.py"
    if router_path.exists():
        content = router_path.read_text(encoding="utf-8")
        new_content = re.sub(
            rf"^router\.include_router\({spec.module}\.router\)\n?",
            "",
            content,
            flags=re.MULTILINE,
        )
        match = re.search(r"^from routes import (.+)$", new_content, flags=re.MULTILINE)
        if match:
            modules = [m.strip() for m in match.group(1).split(",") if m.strip() != spec.module]
            new_line = "from routes import " + ", ".join(modules) if modules else ""
            new_content = new_content.replace(match.group(0), new_line, 1)
        if new_content != content:
            router_path.write_text(new_content, encoding="utf-8")
            removed.append(f"{router_path} (rota removida)")

    # admin
    if _remove_admin_view(pdir, spec.name):
        removed.append(f"{pdir / 'admin' / 'admin_view.py'} (view removida)")
    setup_path = pdir / "admin" / "admin_setup.py"
    if setup_path.exists():
        content = setup_path.read_text(encoding="utf-8")
        new_content = re.sub(
            rf"^    from admin\.admin_view import {spec.name}Admin\n\n"
            rf"    admin\.add_view\({spec.name}Admin\)\n",
            "",
            content,
            flags=re.MULTILINE,
        )
        if new_content != content:
            setup_path.write_text(new_content, encoding="utf-8")
            removed.append(f"{setup_path} (registro removido)")

    return {"project": pdir.name, "model": spec.name, "removed": removed}


__all__ = [
    "AnalyzerError",
    "EditorError",
    "add_field",
    "create_schema",
    "remove_field",
    "remove_schema",
]
