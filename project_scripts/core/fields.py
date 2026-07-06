"""Especificação de campos e modelos usada pelo gerenciador.

Um campo é descrito por uma string no formato:

    nome:tipo[:flag1,flag2,...]

Tipos suportados: int, float, str, bool, uuid, datetime, date
Flags suportadas:
    nullable      - o campo pode ser nulo
    pk            - primary key (substitui o id automático)
    unique        - índice único
    index         - índice comum
    no-create     - fora do schema de criação (XCreate)
    no-update     - fora do schema de atualização (XUpdate)
    no-read       - fora do schema de leitura (XRead)
    default=VALOR - valor padrão (int/float/bool/str conforme o tipo)
    fk=TABELA     - foreign key para TABELA.id (ou fk=tabela.coluna)

Exemplos:
    "nome:str"
    "preco:float:nullable"
    "sku:str:unique,no-update"
    "estoque:int:default=0"
"""

from dataclasses import dataclass, field

# tipo canônico -> (anotação python, import necessário)
TYPE_MAP: dict[str, tuple[str, str | None]] = {
    "int": ("int", None),
    "float": ("float", None),
    "str": ("str", None),
    "bool": ("bool", None),
    "uuid": ("UUID", "from uuid import UUID"),
    "datetime": ("datetime", "from datetime import datetime"),
    "date": ("date", "from datetime import date"),
}

# anotação python -> tipo canônico (para o analisador)
ANNOTATION_MAP: dict[str, str] = {py: tipo for tipo, (py, _) in TYPE_MAP.items()}

VALID_FLAGS = {
    "nullable",
    "pk",
    "unique",
    "index",
    "no-create",
    "no-update",
    "no-read",
}

AUTO_FIELDS = {"id", "created_at", "updated_at", "deleted_at"}


class FieldSpecError(ValueError):
    """Erro de especificação de campo, com mensagem amigável."""


@dataclass
class FieldSpec:
    name: str
    type: str  # canônico (int, str...) ou anotação crua para tipos não mapeados
    nullable: bool = False
    pk: bool = False
    unique: bool = False
    index: bool = False
    creatable: bool = True
    updatable: bool = True
    readable: bool = True
    default: str | None = None  # literal python pronto para o código gerado
    auto: bool = False  # id/created_at/updated_at/deleted_at gerados pelo template
    raw_annotation: str | None = None  # anotação original quando tipo não mapeado
    foreign_key: str | None = None  # ex: "cliente.id"

    @property
    def py_type(self) -> str:
        if self.type in TYPE_MAP:
            return TYPE_MAP[self.type][0]
        return self.raw_annotation or self.type

    @property
    def import_line(self) -> str | None:
        if self.type in TYPE_MAP:
            return TYPE_MAP[self.type][1]
        return None

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "type": self.type if self.type in TYPE_MAP else self.py_type,
            "nullable": self.nullable,
            "pk": self.pk,
            "unique": self.unique,
            "index": self.index,
            "creatable": self.creatable,
            "updatable": self.updatable,
            "readable": self.readable,
            "default": self.default,
            "auto": self.auto,
            "foreign_key": self.foreign_key,
        }


@dataclass
class ModelSpec:
    name: str  # CamelCase, ex: Produto
    fields: list[FieldSpec] = field(default_factory=list)
    timestamps: bool = True  # created_at/updated_at/deleted_at automáticos

    @property
    def module(self) -> str:
        return self.name.lower()

    @property
    def custom_fields(self) -> list[FieldSpec]:
        return [f for f in self.fields if not f.auto]

    @property
    def has_custom_pk(self) -> bool:
        return any(f.pk for f in self.custom_fields)

    def get_field(self, name: str) -> FieldSpec | None:
        for f in self.fields:
            if f.name == name:
                return f
        return None

    def to_dict(self) -> dict:
        return {
            "model": self.name,
            "module": self.module,
            "timestamps": self.timestamps,
            "fields": [f.to_dict() for f in self.fields],
        }


def _parse_default(raw: str, tipo: str) -> str:
    """Converte o valor default informado em literal python para o código."""
    if tipo == "int":
        try:
            return str(int(raw))
        except ValueError as e:
            raise FieldSpecError(
                f"default '{raw}' não é um int válido"
            ) from e
    if tipo == "float":
        try:
            return str(float(raw))
        except ValueError as e:
            raise FieldSpecError(
                f"default '{raw}' não é um float válido"
            ) from e
    if tipo == "bool":
        lowered = raw.strip().lower()
        if lowered in {"true", "1", "sim"}:
            return "True"
        if lowered in {"false", "0", "nao", "não"}:
            return "False"
        raise FieldSpecError(f"default '{raw}' não é um bool válido (use true/false)")
    if tipo == "str":
        escaped = raw.replace('"', '\\"')
        return f'"{escaped}"'
    raise FieldSpecError(f"tipo '{tipo}' não suporta valor default pela CLI")


def parse_field_spec(spec: str) -> FieldSpec:
    """Converte 'nome:tipo[:flags]' em FieldSpec, com erros descritivos."""
    parts = spec.strip().split(":", 2)
    if len(parts) < 2:
        raise FieldSpecError(
            f"especificação inválida '{spec}'. Formato: nome:tipo[:flags] "
            f"(tipos: {', '.join(TYPE_MAP)})"
        )
    name = parts[0].strip().lower().replace(" ", "_")
    if not name.isidentifier():
        raise FieldSpecError(f"nome de campo inválido: '{parts[0]}'")
    if name in AUTO_FIELDS:
        raise FieldSpecError(
            f"o campo '{name}' é gerado automaticamente (id + timestamps)"
        )

    tipo = parts[1].strip().lower()
    if tipo not in TYPE_MAP:
        raise FieldSpecError(
            f"tipo inválido '{tipo}'. Tipos suportados: {', '.join(TYPE_MAP)}"
        )

    fspec = FieldSpec(name=name, type=tipo)

    if len(parts) == 3 and parts[2].strip():
        for raw_flag in parts[2].split(","):
            flag = raw_flag.strip().lower()
            if not flag:
                continue
            if flag.startswith("default="):
                fspec.default = _parse_default(flag.split("=", 1)[1], tipo)
                continue
            if flag.startswith("fk="):
                target = flag.split("=", 1)[1].strip()
                if not target:
                    raise FieldSpecError("fk= exige o nome da tabela (ex: fk=cliente)")
                fspec.foreign_key = target if "." in target else f"{target}.id"
                continue
            if flag not in VALID_FLAGS:
                raise FieldSpecError(
                    f"flag inválida '{flag}'. Flags: "
                    f"{', '.join(sorted(VALID_FLAGS))}, default=VALOR, fk=TABELA"
                )
            if flag == "nullable":
                fspec.nullable = True
            elif flag == "pk":
                fspec.pk = True
                fspec.creatable = False
                fspec.updatable = False
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
    return fspec


def validate_model_name(name: str) -> str:
    """Normaliza e valida o nome do modelo (CamelCase)."""
    cleaned = name.strip().replace(" ", "")
    if not cleaned.isidentifier():
        raise FieldSpecError(f"nome de modelo inválido: '{name}'")
    return cleaned[0].upper() + cleaned[1:]
