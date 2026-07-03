import os
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any


class Tipos(Enum):
    int = "int"
    float = "float"
    uuid = "uuid"
    datetime = "datetime"
    str = "str"

    def __str__(self):
        return f"{self.value}"


@dataclass
class Campo:
    nome: str
    tipo: Tipos
    nullable: bool
    creatable: bool
    updatable: bool
    public: bool
    default: Any
    primary_key: bool


class Modelo:
    def __init__(self, nome: str):
        self.nome = nome
        self.campos: list[Campo] = []

    def inserir_campo(self) -> None:
        nome = input("Nome do campo: ").replace(" ", "_")

        creatable_input = input("Ele vai estar no schema de create? 1. sim 2. não: ")
        creatable = creatable_input == "1"

        nullable_input = input("Ele vai poder ser nulo? 1. sim 2. não: ")
        nullable = nullable_input == "1"

        updatable_input = input("Ele vai ser atualizavel? 1. sim 2. não: ")
        updatable = updatable_input == "1"

        public_input = input("Ele vai ser publico? 1. sim 2. não:")
        public: bool = public_input == "1"

        primary_key_input = input("Ele vai ser a primary key? 1. sim 2. não: ")
        primary_key = primary_key_input == "1"

        tipo_input = input("digite o tipo: [int, str, float, uuid, datetime]: ")
        tipo = Tipos(tipo_input)

        default_input = input("Valor do default (vazio para nada): ")
        default = None
        if default_input:
            if tipo == Tipos.float:
                try:
                    default = float(default_input)
                except Exception as e:
                    print(e)
                    print("Valor default n é compativel com o tipo selecionado")
                    print("Tente novamente")
                    return
            if tipo == Tipos.int:
                try:
                    default = int(default_input)
                except Exception as e:
                    print(e)
                    print("Valor default n é compativel com o tipo selecionado")
                    print("Tente novamente")
                    return
            if tipo == Tipos.str:
                default = default_input

        campo = Campo(
            nome=nome,
            creatable=creatable,
            default=default,
            updatable=updatable,
            public=public,
            tipo=tipo,
            primary_key=primary_key,
            nullable=nullable,
        )
        self.campos.append(campo)

    def listar_campos(self) -> None:
        for campo, index in enumerate(self.campos):
            print(index, campo)

    def remover_campo(self, indice: int) -> None:
        self.campos.remove(self.campos[indice])
        print("Campo removido com sucesso")

    def create_create_schema_str(self) -> str:
        string = f"class {self.nome}Create(SQLModel):\n"
        for campo in self.campos:
            string += f"    {campo.nome}: {campo.tipo}"
            if campo.default:
                if campo.tipo == Tipos.str:
                    string += f'= "{campo.default}"'
                else:
                    string += f"= {campo.default}"
            string += "\n"
        return string

    def create_sqlmodel_table_str(self) -> str:
        string = f"class {self.nome}(SQLModel, table = True):\n"
        for campo in self.campos:
            string += f"    {campo.nome}: {campo.tipo}{'| None' if campo.nullable else ''} = Field("
            if campo.default:
                if campo.tipo == Tipos.str:
                    string += f'default= "{campo.default}", '
                else:
                    string += f"default= {campo.default}, "
            if campo.primary_key:
                string += "primary_key= True, "
            string += ")\n"
        return string

    def create_public_schema_str(self) -> str:
        string = f"class {self.nome}Public(SQLModel):\n"
        for campo in self.campos:
            if not campo.public:
                continue
            string += f"    {campo.nome}: {campo.tipo}"
            if campo.default:
                if campo.tipo == Tipos.str:
                    string += f'= "{campo.default}"'
                else:
                    string += f"= {campo.default}"
            string += "\n"
        return string

    def create_update_schema_str(self) -> str:
        string = f"class {self.nome}Update(SQLModel):\n"
        for campo in self.campos:
            if not campo.updatable:
                continue
            string += f"    {campo.nome}: {campo.tipo}"
            if campo.default:
                if campo.tipo == Tipos.str:
                    string += f'= "{campo.default}"'
                else:
                    string += f"= {campo.default}"
            string += "\n"
        return string

    def create_admin_view(self, is_list: bool = True) -> str:
        content = f"from schemas.{self.nome.lower()} import {self.nome}\n\n\n"
        content += (
            f"class {self.nome.capitalize()}Admin(ModelView, model={self.nome}):\n"
        )
        if is_list:
            content += "    card_style = False\n"
        else:
            content += "    card_style = True\n"
        lista_campos = "    column_list= ["
        for campo in self.campos:
            lista_campos += f"{self.nome}.{campo.nome},"
        lista_campos += "]\n\n\n\n"
        content += lista_campos
        return content

    def create_admin_setup(self) -> str:
        content = f"\n    from admin.admin_view import {self.nome}Admin\n\n\n"
        content += f"    admin.add_view({self.nome}Admin)\n"
        return content

    def create_fast_crud(self) -> str:
        content = "from auth import UserByRole\n"
        content += "from database import get_async_session\n"
        content += "from fastcrud import crud_router  # type: ignore\n"
        content += f"from schemas.{self.nome.lower()} import {self.nome}, {self.nome}Create, {self.nome}Public, {self.nome}Update\n"
        content += "\n\n\n"
        content += "router = crud_router(\n"
        content += "session=get_async_session,\n"
        content += f"model={self.nome},\n"
        content += f"create_schema={self.nome}Create,\n"
        content += f"update_schema={self.nome}Update,\n"
        content += f"select_schema={self.nome}Public,\n"
        content += f"path='/{self.nome.lower()}',\n"
        content += f"tags=['{self.nome}'],\n"
        content += "create_deps=[UserByRole([])],\n"
        content += "read_deps=[UserByRole([])],\n"
        content += "read_multi_deps=[UserByRole([])],\n"
        content += "update_deps=[UserByRole([])],\n"
        content += "delete_deps=[UserByRole([])],\n"
        content += ")\n"
        return content

    def register_router(self):
        content = f"from routes import {self.nome.lower()}\n"
        content += f"router.include_router({self.nome.lower()}.router)\n"
        return content


class CreateSchema:
    def __init__(self, project_path: str) -> None:
        base_path = Path(__file__)
        print(base_path)
        self.project_path = project_path
        self.dir_schema = os.path.join(project_path, "schemas")
        self.dir_routes = os.path.join(project_path, "routes")
        self.path_file_admin_view = os.path.join(project_path, "admin", "admin_view.py")
        self.path_file_admin_setup = os.path.join(
            project_path, "admin", "admin_setup.py"
        )

    def menu(self) -> None:
        print("Aqui você pode criar schemas de forma facil")
        print("0. Ver menu ")
        print("1. Nome do modelo ")
        print("2. Adicionar um campo")
        print("3. Listar os campos")
        print("4. Remover um campo")
        print("5. Mostrar schemas")
        print("6. Criar modelo")
        print("7. Criar admin")
        print("8. Criar fastcrud")
        print("9. Criar crud automatizado")
        print("Digite sair para sair desse menu")
        print("")

    def run(self) -> None:
        modelo: Modelo | None = None
        while True:
            self.menu()
            entrada = input("O que deseja fazer? ")

            match entrada:
                case "1":
                    nome_modelo = (
                        input("Digite o nome do modelo: ").capitalize().replace(" ", "")
                    )
                    if not modelo:
                        modelo = Modelo(nome_modelo)
                    modelo.nome = nome_modelo
                case "2":
                    if not modelo:
                        print("Diga o nome do modelo")
                        continue
                    modelo.inserir_campo()
                case "3":
                    if not modelo:
                        print("Diga o nome do modelo")
                        continue
                    modelo.listar_campos()
                case "4":
                    if not modelo:
                        print("Diga o nome do modelo")
                        continue
                    indice = input("Digite o indice do campo para remover")
                    modelo.remover_campo(int(indice))
                case "5":
                    if not modelo:
                        print("Diga o nome do modelo")
                        continue
                    print(modelo.create_sqlmodel_table_str())
                    print(modelo.create_public_schema_str())
                    print(modelo.create_update_schema_str())
                case "6":
                    if not modelo:
                        print("Diga o nome do modelo")
                        continue

                    content = "from sqlmodel import Field,Relationship,SQLModel\n\n\n\n"

                    content += modelo.create_sqlmodel_table_str()
                    content += modelo.create_create_schema_str()
                    content += modelo.create_update_schema_str()
                    content += modelo.create_public_schema_str()

                    with open(
                        os.path.join(self.dir_schema, f"{modelo.nome.lower()}.py"), "w"
                    ) as file:
                        file.write(content)
                    with open(
                        os.path.join(self.dir_schema, "__init__.py"), "a"
                    ) as file:
                        file.write(
                            f"from schemas.{modelo.nome.lower()} import {modelo.nome}\n"
                        )

                case "7":
                    if not modelo:
                        print("Diga o nome do modelo")
                        continue

                    list_view = (
                        input("Deseja visualizar esse modelo em lista? 1. sim 2.não: ")
                        == "1"
                    )
                    with open(self.path_file_admin_view, "a") as file:
                        file.write(modelo.create_admin_view(list_view))
                    with open(self.path_file_admin_setup, "a") as file:
                        file.write(modelo.create_admin_setup())
                case "8":
                    if not modelo:
                        print("Diga o nome do modelo")
                        continue

                    with open(
                        os.path.join(self.dir_routes, f"{modelo.nome.lower()}.py"), "w"
                    ) as file:
                        file.write(modelo.create_fast_crud())
                    with open(
                        os.path.join(self.project_path, "router.py"), "a"
                    ) as file:
                        file.write(modelo.register_router())
                case "sair":
                    break
                case _:
                    self.menu()
