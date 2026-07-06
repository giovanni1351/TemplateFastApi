"""Análise de projetos existentes: features, schemas e campos.

Usa AST para mapear os modelos SQLModel de cada projeto, derivando as
flags de cada campo pela presença nas classes Create/Update/Read.
"""

import ast
from dataclasses import dataclass, field
from pathlib import Path

from project_scripts.core.fields import (
    ANNOTATION_MAP,
    AUTO_FIELDS,
    FieldSpec,
    ModelSpec,
)

# schemas de infraestrutura do template ficam fora do mapeamento/edição
SKIP_SCHEMA_FILES = {"__init__.py", "rbac.py", "password_reset.py", "token.py"}


class AnalyzerError(ValueError):
    """Erro de análise com mensagem amigável."""


@dataclass
class ParsedModel:
    """Resultado da análise de um arquivo de schema."""

    spec: ModelSpec
    path: Path
    # trecho [início, fim) em linhas (0-based) ocupado pelas classes do modelo
    block_start: int = 0
    block_end: int = 0
    # linhas verbatim preservadas dentro da classe table (métodos, relationships)
    table_extras: list[str] = field(default_factory=list)
    # classes do arquivo fora do bloco do modelo (ex: enums) ficam intactas
    warnings: list[str] = field(default_factory=list)


def list_projects(src_dir: Path) -> list[str]:
    if not src_dir.is_dir():
        return []
    return sorted(
        p.name
        for p in src_dir.iterdir()
        if p.is_dir() and (p / "app.py").is_file()
    )


def project_dir(src_dir: Path, name: str) -> Path:
    pdir = src_dir / name
    if not (pdir / "app.py").is_file():
        disponiveis = ", ".join(list_projects(src_dir)) or "(nenhum)"
        raise AnalyzerError(
            f"projeto '{name}' não encontrado em {src_dir}. "
            f"Projetos disponíveis: {disponiveis}"
        )
    return pdir


def project_features(pdir: Path) -> dict:
    return {
        "admin": (pdir / "admin").is_dir(),
        "rbac": (pdir / "utils" / "rbac_router.py").is_file(),
    }


def project_info(pdir: Path) -> dict:
    schemas = list_models(pdir)
    routes_dir = pdir / "routes"
    routes = (
        sorted(p.stem for p in routes_dir.glob("*.py") if p.stem != "__init__")
        if routes_dir.is_dir()
        else []
    )
    return {
        "project": pdir.name,
        "path": str(pdir),
        "features": project_features(pdir),
        "models": [m.spec.name for m in schemas],
        "routes": routes,
    }


def _annotation_info(annotation: ast.expr) -> tuple[str, bool]:
    """Retorna (anotação sem o None, nullable)."""
    text = ast.unparse(annotation)
    nullable = False
    compact = text.replace(" ", "")
    if compact.endswith("|None"):
        nullable = True
        text = compact.removesuffix("|None")
    if text.startswith("Optional[") and text.endswith("]"):
        nullable = True
        text = text[len("Optional[") : -1]
    return text, nullable


def _simple_fields(classdef: ast.ClassDef) -> tuple[dict[str, dict], list[ast.stmt]]:
    """Extrai campos simples (AnnAssign) e devolve os statements extras."""
    fields: dict[str, dict] = {}
    extras: list[ast.stmt] = []
    for stmt in classdef.body:
        if (
            isinstance(stmt, ast.AnnAssign)
            and isinstance(stmt.target, ast.Name)
        ):
            value = stmt.value
            # Relationship(...) é preservado verbatim, não é um campo simples
            if (
                isinstance(value, ast.Call)
                and isinstance(value.func, ast.Name)
                and value.func.id == "Relationship"
            ):
                extras.append(stmt)
                continue
            annotation, nullable = _annotation_info(stmt.annotation)
            info: dict = {
                "annotation": annotation,
                "nullable": nullable,
                "default": None,
                "pk": False,
                "unique": False,
                "index": False,
                "default_factory": None,
                "foreign_key": None,
            }
            if isinstance(value, ast.Call) and isinstance(value.func, ast.Name) and value.func.id == "Field":
                for kw in value.keywords:
                    if kw.arg == "primary_key":
                        info["pk"] = ast.unparse(kw.value) == "True"
                    elif kw.arg == "unique":
                        info["unique"] = ast.unparse(kw.value) == "True"
                    elif kw.arg == "index":
                        info["index"] = ast.unparse(kw.value) == "True"
                    elif kw.arg == "default":
                        text = ast.unparse(kw.value)
                        info["default"] = None if text == "None" else text
                    elif kw.arg == "default_factory":
                        info["default_factory"] = ast.unparse(kw.value)
                    elif kw.arg == "foreign_key" and isinstance(kw.value, ast.Constant):
                        info["foreign_key"] = kw.value.value
            elif value is not None:
                text = ast.unparse(value)
                info["default"] = None if text == "None" else text
            fields[stmt.target.id] = info
        elif isinstance(stmt, ast.Pass):
            continue
        elif (
            isinstance(stmt, ast.Expr)
            and isinstance(stmt.value, ast.Constant)
            and isinstance(stmt.value.value, str)
        ):
            continue  # docstring
        else:
            extras.append(stmt)
    return fields, extras


def _source_segment(source_lines: list[str], node: ast.stmt) -> list[str]:
    return source_lines[node.lineno - 1 : node.end_lineno]


def parse_schema_source(source: str, path: Path) -> ParsedModel | None:
    """Analisa um arquivo de schema. Retorna None se não houver modelo table."""
    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        raise AnalyzerError(f"erro de sintaxe em {path.name}: {e}") from e

    source_lines = source.splitlines()
    classes: dict[str, ast.ClassDef] = {
        node.name: node for node in tree.body if isinstance(node, ast.ClassDef)
    }

    table_class: ast.ClassDef | None = None
    for node in classes.values():
        for kw in node.keywords:
            if kw.arg == "table" and ast.unparse(kw.value) == "True":
                table_class = node
                break
        if table_class:
            break
    if table_class is None:
        return None

    name = table_class.name
    create_cls = classes.get(f"{name}Create")
    update_cls = classes.get(f"{name}Update")
    read_cls = classes.get(f"{name}Read") or classes.get(f"{name}Public")

    warnings: list[str] = []
    table_fields, table_extra_stmts = _simple_fields(table_class)
    create_fields, create_extras = _simple_fields(create_cls) if create_cls else ({}, [])
    update_fields, update_extras = _simple_fields(update_cls) if update_cls else ({}, [])
    read_fields, read_extras = _simple_fields(read_cls) if read_cls else ({}, [])
    if create_extras or update_extras or read_extras:
        warnings.append(
            "as classes Create/Update/Read contêm código além de campos simples; "
            "esse código será perdido em edições via CLI"
        )

    # herda o Create? campos do Create pertencem à tabela
    inherits_create = any(
        isinstance(base, ast.Name) and base.id == f"{name}Create"
        for base in table_class.bases
    )

    spec = ModelSpec(name=name)
    ordered: list[tuple[str, dict, bool]] = []
    if inherits_create:
        ordered.extend((n, i, True) for n, i in create_fields.items())
    ordered.extend(
        (n, i, n in create_fields) for n, i in table_fields.items() if n not in create_fields
    )

    has_timestamps = all(
        ts in table_fields for ts in ("created_at", "updated_at", "deleted_at")
    )
    spec.timestamps = has_timestamps

    for fname, info, creatable in ordered:
        auto = False
        if fname == "id" and info["pk"]:
            auto = True
        elif fname in AUTO_FIELDS and fname != "id" and has_timestamps:
            auto = True
        annotation = info["annotation"]
        canonical = ANNOTATION_MAP.get(annotation)
        fspec = FieldSpec(
            name=fname,
            type=canonical or annotation,
            raw_annotation=None if canonical else annotation,
            nullable=info["nullable"],
            pk=info["pk"],
            unique=info["unique"],
            index=info["index"],
            creatable=creatable,
            updatable=fname in update_fields,
            readable=fname in read_fields,
            default=info["default"],
            auto=auto,
            foreign_key=info["foreign_key"],
        )
        spec.fields.append(fspec)

    # extras da classe table preservados verbatim (ex: __str__, Relationship)
    table_extras: list[str] = []
    for stmt in table_extra_stmts:
        table_extras.extend(_source_segment(source_lines, stmt))

    # calcula o bloco de linhas ocupado pelas classes do modelo
    model_classes = [c for c in (create_cls, update_cls, table_class, read_cls) if c]
    block_start = min(c.lineno for c in model_classes) - 1
    block_end = max(c.end_lineno or c.lineno for c in model_classes)

    # classes de outros tipos entre as classes do modelo impedem edição segura
    for other in classes.values():
        if other in model_classes:
            continue
        start, end = other.lineno - 1, other.end_lineno or other.lineno
        if start >= block_start and end <= block_end:
            warnings.append(
                f"a classe '{other.name}' está no meio do bloco do modelo; "
                "edições via CLI podem removê-la"
            )

    return ParsedModel(
        spec=spec,
        path=path,
        block_start=block_start,
        block_end=block_end,
        table_extras=table_extras,
        warnings=warnings,
    )


def parse_schema_file(path: Path) -> ParsedModel | None:
    return parse_schema_source(path.read_text(encoding="utf-8"), path)


def list_models(pdir: Path) -> list[ParsedModel]:
    schemas_dir = pdir / "schemas"
    if not schemas_dir.is_dir():
        return []
    models: list[ParsedModel] = []
    for path in sorted(schemas_dir.glob("*.py")):
        if path.name in SKIP_SCHEMA_FILES:
            continue
        try:
            parsed = parse_schema_file(path)
        except AnalyzerError:
            continue
        if parsed is not None:
            models.append(parsed)
    return models


def find_model(pdir: Path, model_name: str) -> ParsedModel:
    for parsed in list_models(pdir):
        if parsed.spec.name.lower() == model_name.lower():
            return parsed
    nomes = ", ".join(m.spec.name for m in list_models(pdir)) or "(nenhum)"
    raise AnalyzerError(
        f"modelo '{model_name}' não encontrado no projeto '{pdir.name}'. "
        f"Modelos disponíveis: {nomes}"
    )
