"""Importação de diagramas Mermaid ER (erDiagram) para gerar schemas completos.

Sintaxe suportada:

    erDiagram
        CLIENTE ||--o{ PEDIDO : faz
        PEDIDO ||--|{ ITEM_PEDIDO : contem
        PRODUTO }o--o{ PEDIDO : "aparece em"

        CLIENTE {
            string nome
            string email UK
            string telefone "nullable"
        }
        PEDIDO {
            float total "default=0"
            string status
            date data_pedido "nullable"
        }

Regras:
- Cada entidade vira um modelo completo (Create/Update/Table/Read) com CRUD.
- Nomes de entidade viram CamelCase (ITEM_PEDIDO -> ItemPedido).
- Atributos: `tipo nome [PK|UK|FK] ["flags"]`. O comentário entre aspas aceita
  as mesmas flags da CLI (nullable, unique, index, no-create, no-update,
  no-read, default=VALOR), separadas por vírgula. Comentários que não são
  flags são ignorados.
- `id`, `created_at`, `updated_at`, `deleted_at` são automáticos (declarações
  explícitas de `id` são ignoradas).
- Relacionamentos:
    1:N  -> FK uuid no lado N (ex: cliente_id) + Relationship nos dois lados
    1:1  -> FK uuid única no lado direito + Relationship nos dois lados
    N:N  -> tabela de ligação <A><B>Link gerada automaticamente (sem rota)
  Cardinalidade com `o` no lado "1" torna a FK nullable.
"""

import keyword
import re
from dataclasses import dataclass, field
from pathlib import Path

from project_scripts.core.editor import create_schema
from project_scripts.core.fields import FieldSpec, ModelSpec

MERMAID_TYPE_MAP = {
    "string": "str",
    "str": "str",
    "text": "str",
    "varchar": "str",
    "char": "str",
    "int": "int",
    "integer": "int",
    "bigint": "int",
    "smallint": "int",
    "float": "float",
    "double": "float",
    "decimal": "float",
    "numeric": "float",
    "real": "float",
    "bool": "bool",
    "boolean": "bool",
    "date": "date",
    "datetime": "datetime",
    "timestamp": "datetime",
    "uuid": "uuid",
}

FLAG_COMMENT_RE = re.compile(
    r"^(nullable|unique|index|no-create|no-update|no-read|default=.+?)"
    r"(,(nullable|unique|index|no-create|no-update|no-read|default=.+?))*$"
)

ENTITY_OPEN_RE = re.compile(r"^\s*([A-Za-z_][\w-]*)\s*\{\s*$")
ATTR_RE = re.compile(
    r"^\s*([\w()\[\]]+)\s+(\w+)"  # tipo nome
    r"(?:\s+((?:PK|FK|UK)(?:\s*,\s*(?:PK|FK|UK))*))?"  # chaves
    r'(?:\s+"([^"]*)")?\s*$'  # comentário
)
REL_RE = re.compile(
    r"^\s*([A-Za-z_][\w-]*)\s+"
    r"([|}o][|{}o]?)\s*(?:--|\.\.)\s*([|{o][|{}o]?)\s+"
    r"([A-Za-z_][\w-]*)\s*:\s*(.*)$"
)


class MermaidError(ValueError):
    """Erro de parsing/aplicação do diagrama, com mensagem amigável."""


@dataclass
class Relation:
    left: str  # nome do modelo (CamelCase)
    right: str
    left_many: bool
    right_many: bool
    left_optional: bool
    right_optional: bool
    label: str = ""

    @property
    def kind(self) -> str:
        if self.left_many and self.right_many:
            return "n:n"
        if self.left_many or self.right_many:
            return "1:n"
        return "1:1"


@dataclass
class MermaidER:
    models: dict[str, ModelSpec] = field(default_factory=dict)
    relations: list[Relation] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def entity_to_model_name(raw: str) -> str:
    parts = [p for p in re.split(r"[_\-]", raw) if p]
    return "".join(p[0].upper() + p[1:].lower() for p in parts)


def _plural(module: str) -> str:
    plural = module + "s"
    if keyword.iskeyword(plural):
        plural += "_"
    return plural


def _apply_comment_flags(fspec: FieldSpec, comment: str, warnings: list[str]) -> None:
    """Aplica flags declaradas no comentário do atributo (se forem flags)."""
    compact = comment.strip().replace(" ", "")
    if not compact or not FLAG_COMMENT_RE.match(compact):
        return  # comentário livre, não são flags
    from project_scripts.core.fields import _parse_default

    for flag in compact.split(","):
        if flag == "nullable":
            fspec.nullable = True
        elif flag == "unique":
            fspec.unique = True
        elif flag == "index":
            fspec.index = True
        elif flag == "no-create":
            fspec.creatable = False
        elif flag == "no-update":
            fspec.updatable = False
        elif flag == "no-read":
            fspec.readable = False
        elif flag.startswith("default="):
            try:
                fspec.default = _parse_default(flag.split("=", 1)[1], fspec.type)
            except ValueError as e:
                warnings.append(f"{fspec.name}: {e} — default ignorado")


def parse_mermaid(text: str) -> MermaidER:
    lines = text.splitlines()
    if not any("erDiagram" in line for line in lines):
        raise MermaidError(
            "o arquivo não contém um bloco 'erDiagram' do Mermaid"
        )

    er = MermaidER()
    current: ModelSpec | None = None

    for lineno, raw_line in enumerate(lines, 1):
        line = raw_line.strip()
        if (
            not line
            or line.startswith("%%")
            or line in {"```", "```mermaid"}
            or line == "erDiagram"
        ):
            continue

        if current is not None:
            if line == "}":
                current = None
                continue
            m_attr = ATTR_RE.match(line)
            if not m_attr:
                raise MermaidError(
                    f"linha {lineno}: atributo inválido '{line}'. "
                    f"Formato: tipo nome [PK|UK|FK] [\"flags\"]"
                )
            raw_type, name, keys, comment = m_attr.groups()
            name = name.lower()
            if name in {"id", "created_at", "updated_at", "deleted_at"}:
                er.warnings.append(
                    f"{current.name}.{name} ignorado (campo automático do template)"
                )
                continue
            tipo = MERMAID_TYPE_MAP.get(raw_type.lower())
            if tipo is None:
                er.warnings.append(
                    f"{current.name}.{name}: tipo '{raw_type}' desconhecido, usando str"
                )
                tipo = "str"
            fspec = FieldSpec(name=name, type=tipo)
            key_set = {k.strip().upper() for k in (keys or "").split(",") if k.strip()}
            if "PK" in key_set:
                fspec.pk = True
                fspec.creatable = False
                fspec.updatable = False
            if "UK" in key_set:
                fspec.unique = True
            # FK declarada no atributo: resolvida depois pelos relacionamentos
            if comment:
                _apply_comment_flags(fspec, comment, er.warnings)
            current.fields.append(fspec)
            continue

        m_entity = ENTITY_OPEN_RE.match(line)
        if m_entity:
            model_name = entity_to_model_name(m_entity.group(1))
            if model_name not in er.models:
                er.models[model_name] = ModelSpec(name=model_name)
            current = er.models[model_name]
            continue

        m_rel = REL_RE.match(line)
        if m_rel:
            left_raw, left_card, right_card, right_raw, label = m_rel.groups()
            left = entity_to_model_name(left_raw)
            right = entity_to_model_name(right_raw)
            for name in (left, right):
                er.models.setdefault(name, ModelSpec(name=name))
            er.relations.append(
                Relation(
                    left=left,
                    right=right,
                    left_many="}" in left_card,
                    right_many="{" in right_card,
                    left_optional="o" in left_card,
                    right_optional="o" in right_card,
                    label=label.strip().strip('"'),
                )
            )
            continue

        raise MermaidError(
            f"linha {lineno}: não entendi '{line}'. "
            f"Esperado entidade, atributo ou relacionamento erDiagram."
        )

    if not er.models:
        raise MermaidError("nenhuma entidade encontrada no diagrama")
    return er


@dataclass
class _ModelPlan:
    spec: ModelSpec
    table_extras: list[str] = field(default_factory=list)
    type_checking_imports: list[tuple[str, str]] = field(default_factory=list)
    runtime_imports: list[str] = field(default_factory=list)
    with_route: bool = True
    with_admin: bool = True


def build_plan(er: MermaidER) -> tuple[list[_ModelPlan], list[str]]:
    """Converte o ER em planos de criação (FKs, relationships e link tables)."""
    warnings = list(er.warnings)
    plans: dict[str, _ModelPlan] = {
        name: _ModelPlan(spec=spec) for name, spec in er.models.items()
    }
    link_plans: list[_ModelPlan] = []

    def add_fk(
        owner: _ModelPlan, target: ModelSpec, *, nullable: bool, unique: bool
    ) -> FieldSpec:
        fk_name = f"{target.module}_id"
        existing = owner.spec.get_field(fk_name)
        if existing is not None:
            existing.foreign_key = existing.foreign_key or f"{target.module}.id"
            existing.type = "uuid"
            return existing
        fspec = FieldSpec(
            name=fk_name,
            type="uuid",
            nullable=nullable,
            unique=unique,
            index=not unique,
            foreign_key=f"{target.module}.id",
            updatable=False,
        )
        owner.spec.fields.append(fspec)
        return fspec

    for rel in er.relations:
        left_plan, right_plan = plans[rel.left], plans[rel.right]
        left_spec, right_spec = left_plan.spec, right_plan.spec

        if rel.kind == "n:n":
            link_name = f"{rel.left}{rel.right}Link"
            link_spec = ModelSpec(name=link_name, timestamps=False)
            for target in (left_spec, right_spec):
                link_spec.fields.append(
                    FieldSpec(
                        name=f"{target.module}_id",
                        type="uuid",
                        pk=True,
                        creatable=False,
                        updatable=False,
                        foreign_key=f"{target.module}.id",
                    )
                )
            link_plans.append(
                _ModelPlan(spec=link_spec, with_route=False, with_admin=False)
            )
            import_line = f"from schemas.{link_spec.module} import {link_name}"
            for plan, other in (
                (left_plan, right_spec),
                (right_plan, left_spec),
            ):
                attr = _plural(other.module)
                back = _plural(plan.spec.module)
                plan.table_extras.append(
                    f'    {attr}: list["{other.name}"] = Relationship('
                    f'back_populates="{back}", link_model={link_name})'
                    "  # pyright: ignore[reportUnknownVariableType]"
                )
                plan.type_checking_imports.append((other.module, other.name))
                if import_line not in plan.runtime_imports:
                    plan.runtime_imports.append(import_line)
            warnings.append(
                f"relacionamento N:N {rel.left}<->{rel.right}: tabela de ligação "
                f"{link_name} criada (sem rota própria)"
            )
            continue

        if rel.kind == "1:n":
            # o lado "muitos" carrega a FK
            one_plan, many_plan = (
                (right_plan, left_plan) if rel.left_many else (left_plan, right_plan)
            )
            one_optional = (
                rel.right_optional if rel.left_many else rel.left_optional
            )
            add_fk(many_plan, one_plan.spec, nullable=one_optional, unique=False)
            many_attr = _plural(many_plan.spec.module)
            one_attr = one_plan.spec.module
            one_plan.table_extras.append(
                f'    {many_attr}: list["{many_plan.spec.name}"] = Relationship('
                f'back_populates="{one_attr}")'
                "  # pyright: ignore[reportUnknownVariableType]"
            )
            one_plan.type_checking_imports.append(
                (many_plan.spec.module, many_plan.spec.name)
            )
            annotation = f'"{one_plan.spec.name}"'
            if one_optional:
                annotation = f'Optional[{annotation}]'
            many_plan.table_extras.append(
                f"    {one_attr}: {annotation} = Relationship("
                f'back_populates="{many_attr}")'
                "  # pyright: ignore[reportUnknownVariableType]"
            )
            if one_optional:
                imp = "from typing import Optional"
                if imp not in many_plan.runtime_imports:
                    many_plan.runtime_imports.append(imp)
            many_plan.type_checking_imports.append(
                (one_plan.spec.module, one_plan.spec.name)
            )
            continue

        # 1:1 — FK única no lado direito
        add_fk(right_plan, left_spec, nullable=rel.left_optional, unique=True)
        right_attr = right_spec.module
        left_attr = left_spec.module
        left_plan.table_extras.append(
            f'    {right_attr}: Optional["{right_spec.name}"] = Relationship('
            f'back_populates="{left_attr}")'
            "  # pyright: ignore[reportUnknownVariableType]"
        )
        left_plan.type_checking_imports.append((right_spec.module, right_spec.name))
        imp = "from typing import Optional"
        if imp not in left_plan.runtime_imports:
            left_plan.runtime_imports.append(imp)
        annotation = f'"{left_spec.name}"'
        if rel.left_optional:
            annotation = f"Optional[{annotation}]"
            if imp not in right_plan.runtime_imports:
                right_plan.runtime_imports.append(imp)
        right_plan.table_extras.append(
            f"    {left_attr}: {annotation} = Relationship("
            f'back_populates="{right_attr}")'
            "  # pyright: ignore[reportUnknownVariableType]"
        )
        right_plan.type_checking_imports.append((left_spec.module, left_spec.name))

    ordered = list(plans.values()) + link_plans
    return ordered, warnings


def apply_mermaid(
    pdir: Path,
    text: str,
    *,
    with_route: bool = True,
    with_admin: bool = True,
    dry_run: bool = False,
) -> dict:
    """Analisa o diagrama e cria todos os modelos no projeto."""
    er = parse_mermaid(text)
    plans, warnings = build_plan(er)

    # validação prévia: nenhum modelo pode já existir
    from project_scripts.core.analyzer import list_models

    existing = {m.spec.name.lower() for m in list_models(pdir)}
    conflicts = [p.spec.name for p in plans if p.spec.name.lower() in existing]
    if conflicts:
        raise MermaidError(
            f"modelos já existem no projeto '{pdir.name}': {', '.join(conflicts)}. "
            f"Remova-os (remove-schema) ou renomeie as entidades no diagrama."
        )

    plan_summary = [
        {
            "model": p.spec.name,
            "fields": [f.to_dict() for f in p.spec.fields],
            "route": p.with_route and with_route,
            "admin": p.with_admin and with_admin,
            "relationships": len(p.table_extras),
        }
        for p in plans
    ]
    if dry_run:
        return {
            "project": pdir.name,
            "dry_run": True,
            "models": plan_summary,
            "relations": [
                {"left": r.left, "right": r.right, "kind": r.kind, "label": r.label}
                for r in er.relations
            ],
            "warnings": warnings,
        }

    created: list[dict] = []
    for plan in plans:
        result = create_schema(
            pdir,
            plan.spec,
            with_route=plan.with_route and with_route,
            with_admin=plan.with_admin and with_admin,
            table_extras=plan.table_extras or None,
            type_checking_imports=plan.type_checking_imports or None,
            runtime_imports=plan.runtime_imports or None,
        )
        created.append(result)

    return {
        "project": pdir.name,
        "dry_run": False,
        "models": plan_summary,
        "created": created,
        "warnings": warnings,
    }
