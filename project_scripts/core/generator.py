"""Geração de código a partir de ModelSpec.

Gera o arquivo de schema (Create/Update/Table/Read), a rota fastcrud,
a view do admin e as linhas de registro (router.py, schemas/__init__.py,
admin_setup.py).
"""

from project_scripts.core.fields import FieldSpec, ModelSpec

GENERATED_HEADER = "# Gerado pelo gerenciador do template. Edite via `python gerenciar.py` ou manualmente."


def _field_kwargs(f: FieldSpec, in_table: bool) -> list[str]:
    kwargs: list[str] = []
    if f.pk and in_table:
        kwargs.append("primary_key=True")
    if f.default is not None:
        kwargs.append(f"default={f.default}")
    elif f.nullable:
        kwargs.append("default=None")
    if f.foreign_key:
        kwargs.append(f'foreign_key="{f.foreign_key}"')
    if f.unique:
        kwargs.append("unique=True")
    if f.index:
        kwargs.append("index=True")
    return kwargs


def _render_field_line(f: FieldSpec, in_table: bool) -> str:
    annotation = f.py_type + (" | None" if f.nullable else "")
    kwargs = _field_kwargs(f, in_table)
    needs_field = f.unique or f.index or bool(f.foreign_key) or (f.pk and in_table)
    if needs_field or (in_table and kwargs):
        return f"    {f.name}: {annotation} = Field({', '.join(kwargs)})"
    if f.default is not None:
        return f"    {f.name}: {annotation} = {f.default}"
    if f.nullable:
        return f"    {f.name}: {annotation} = None"
    return f"    {f.name}: {annotation}"


def render_create_class(spec: ModelSpec) -> str:
    lines = [f"class {spec.name}Create(SQLModel):"]
    creatable = [f for f in spec.custom_fields if f.creatable]
    if not creatable:
        lines.append("    pass")
    for f in creatable:
        lines.append(_render_field_line(f, in_table=False))
    return "\n".join(lines)


def render_update_class(spec: ModelSpec) -> str:
    lines = [f"class {spec.name}Update(SQLModel):"]
    updatable = [f for f in spec.custom_fields if f.updatable]
    if not updatable:
        lines.append("    pass")
    for f in updatable:
        lines.append(f"    {f.name}: {f.py_type} | None = None")
    return "\n".join(lines)


def render_table_class(spec: ModelSpec, extras: list[str] | None = None) -> str:
    creatable = [f for f in spec.custom_fields if f.creatable]
    base = f"{spec.name}Create" if creatable else "SQLModel"
    lines = [f"class {spec.name}({base}, table=True):"]

    if not spec.has_custom_pk:
        lines.append("    id: UUID = Field(primary_key=True, default_factory=uuid4)")
    for f in spec.custom_fields:
        if f.creatable:
            continue  # herdado do Create
        lines.append(_render_field_line(f, in_table=True))
    if spec.timestamps:
        lines.append("    created_at: datetime = Field(default_factory=datetime.now)")
        lines.append("    updated_at: datetime | None = Field(default=None)")
        lines.append("    deleted_at: datetime | None = Field(default=None)")

    if extras:
        lines.append("")
        lines.extend(extras)
    elif len(lines) == 1:
        lines.append("    pass")
    return "\n".join(lines)


def render_read_class(spec: ModelSpec) -> str:
    lines = [f"class {spec.name}Read(SQLModel):"]
    if not spec.has_custom_pk:
        lines.append("    id: UUID")
    for f in spec.custom_fields:
        if not f.readable:
            continue
        annotation = f.py_type + (" | None" if f.nullable else "")
        lines.append(f"    {f.name}: {annotation}")
    if spec.timestamps:
        lines.append("    created_at: datetime")
        lines.append("    updated_at: datetime | None")
        lines.append("    deleted_at: datetime | None")
    if len(lines) == 1:
        lines.append("    pass")
    return "\n".join(lines)


def required_imports(spec: ModelSpec) -> list[str]:
    """Linhas de import necessárias para o schema."""
    imports: set[str] = set()
    if not spec.has_custom_pk:
        imports.add("from uuid import UUID, uuid4")
    if spec.timestamps:
        imports.add("from datetime import datetime")
    for f in spec.custom_fields:
        line = f.import_line
        if line:
            if line == "from uuid import UUID" and "from uuid import UUID, uuid4" in imports:
                continue
            imports.add(line)
    if "from uuid import UUID, uuid4" in imports:
        imports.discard("from uuid import UUID")
    if "from datetime import datetime" in imports and "from datetime import date" in imports:
        imports.discard("from datetime import datetime")
        imports.discard("from datetime import date")
        imports.add("from datetime import date, datetime")
    return sorted(imports)


def render_model_classes(spec: ModelSpec, table_extras: list[str] | None = None) -> str:
    """Renderiza as 4 classes do modelo (sem imports)."""
    return "\n\n\n".join(
        [
            render_create_class(spec),
            render_update_class(spec),
            render_table_class(spec, extras=table_extras),
            render_read_class(spec),
        ]
    )


def render_schema_file(
    spec: ModelSpec,
    table_extras: list[str] | None = None,
    type_checking_imports: list[tuple[str, str]] | None = None,
    runtime_imports: list[str] | None = None,
) -> str:
    """Renderiza o arquivo completo do schema.

    type_checking_imports: [(módulo, Classe)] para relationships (forward refs).
    runtime_imports: linhas de import extras (ex: link models de N:N).
    """
    imports = required_imports(spec)
    header = [GENERATED_HEADER]
    if type_checking_imports:
        header.append("from typing import TYPE_CHECKING")
    header.extend(imports)
    header.append("")
    if runtime_imports:
        header.extend(runtime_imports)
    sqlmodel_names = "Field, Relationship, SQLModel" if table_extras else "Field, SQLModel"
    header.append(
        f"from sqlmodel import {sqlmodel_names}  # pyright: ignore[reportUnknownVariableType]"
    )
    if type_checking_imports:
        header.append("")
        header.append("if TYPE_CHECKING:")
        for module, cls in sorted(set(type_checking_imports)):
            header.append(f"    from schemas.{module} import {cls}")
    return (
        "\n".join(header)
        + "\n\n\n"
        + render_model_classes(spec, table_extras=table_extras)
        + "\n"
    )


def render_route_file(spec: ModelSpec, rbac: bool) -> str:
    name = spec.name
    module = spec.module
    if rbac:
        dep_import = "from utils.rbac_router import verify_rbac"
        dep = "verify_rbac"
    else:
        dep_import = "from auth import UserByRole"
        dep = "UserByRole([])"
    return f"""{GENERATED_HEADER}
{dep_import}
from database import get_async_session
from fastcrud import crud_router  # type: ignore
from schemas.{module} import {name}, {name}Create, {name}Read, {name}Update

router = crud_router(
    session=get_async_session,
    model={name},
    create_schema={name}Create,
    update_schema={name}Update,
    select_schema={name}Read,
    path="/{module}",
    tags=["{name}"],
    create_deps=[{dep}],
    read_deps=[{dep}],
    read_multi_deps=[{dep}],
    update_deps=[{dep}],
    delete_deps=[{dep}],
)
"""


def render_admin_view(spec: ModelSpec) -> str:
    """Snippet anexado ao final de admin/admin_view.py."""
    columns = [f for f in spec.custom_fields if f.readable][:5]
    column_list = ", ".join(f"{spec.name}.{f.name}" for f in columns)
    return f"""

from schemas.{spec.module} import {spec.name}  # noqa: E402


class {spec.name}Admin(ModelView, model={spec.name}):
    column_list = [{column_list}]  # noqa: RUF012
    card_style = False
    icon = None
"""


def render_admin_setup(spec: ModelSpec) -> str:
    """Linhas anexadas ao final de admin/admin_setup.py (dentro de setup_admin)."""
    return (
        f"    from admin.admin_view import {spec.name}Admin\n\n"
        f"    admin.add_view({spec.name}Admin)\n"
    )


def render_router_registration(spec: ModelSpec) -> str:
    return f"router.include_router({spec.module}.router)\n"


def render_schemas_init_line(spec: ModelSpec) -> str:
    return f"from schemas.{spec.module} import {spec.name}  # noqa: F401\n"
