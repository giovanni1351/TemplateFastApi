import os
import shutil
from pathlib import Path
from subprocess import run


class CreateProject:
    def __init__(self) -> None:
        self.diretorios = ["admin", "routes", "schemas", "utils"]
        self.base_dir: Path = Path(__file__).parent.parent

    @staticmethod
    def create_admin(dir_module: str) -> None:
        base_dir: Path = Path(__file__).parent.parent
        shutil.copytree(
            os.path.join(base_dir, "project_scripts", "python_default", "admin"),
            os.path.join(dir_module, "admin"),
            dirs_exist_ok=True,
        )

    @staticmethod
    def create_utils(dir_module: str) -> None:
        base_dir: Path = Path(__file__).parent.parent
        shutil.copytree(
            os.path.join(base_dir, "project_scripts", "python_default", "utils"),
            os.path.join(dir_module, "utils"),
            dirs_exist_ok=True,
        )

    @staticmethod
    def create_schemas(dir_module: str) -> None:
        base_dir: Path = Path(__file__).parent.parent
        shutil.copytree(
            os.path.join(base_dir, "project_scripts", "python_default", "schemas"),
            os.path.join(dir_module, "schemas"),
            dirs_exist_ok=True,
        )

    @staticmethod
    def create_routes(dir_module: str) -> None:
        base_dir: Path = Path(__file__).parent.parent
        shutil.copytree(
            os.path.join(base_dir, "project_scripts", "python_default", "routes"),
            os.path.join(dir_module, "routes"),
            dirs_exist_ok=True,
        )

    def create_dir_content(self, module_name: str, dir: str):
        fromto = {
            "admin": CreateProject.create_admin,
            "utils": CreateProject.create_utils,
            "schemas": CreateProject.create_schemas,
            "routes": CreateProject.create_routes,
        }
        fromto[module_name](dir)

    def run(self) -> str:
        print("Criando projeto")
        print("Iniciando o uv")
        iniciar_uv = input("Deseja iniciar o projeto uv? 1. sim 2. não")
        iniciar_uv = iniciar_uv == "1"
        if iniciar_uv:
            run("uv init", cwd=Path(__file__).parent.parent)
            run(
                "uv add alembic asyncpg bcrypt "
                "fastapi fastcrud itsdangerous minio "
                "passlib pwdlib pydantic pydantic-settings pyjwt pylogkit "
                "sqladmin sqlmodel tzdata uvicorn python-multipart",
                cwd=Path(__file__).parent.parent,
            )
        nome_projeto = input("Digite o nome do projeto: ").replace(" ", "_").lower()
        project_dir = os.path.join(self.base_dir, "src", nome_projeto)
        os.makedirs(project_dir, exist_ok=True)
        for diretorio in self.diretorios:
            dir_module = os.path.join(project_dir, diretorio)
            os.makedirs(dir_module, exist_ok=True)
            self.create_dir_content(diretorio, os.path.join(project_dir))

        shutil.copy(
            os.path.join(
                self.base_dir, "project_scripts", "python_default", "router.py"
            ),
            os.path.join(project_dir, "router.py"),
        )
        shutil.copy(
            os.path.join(self.base_dir, "project_scripts", "python_default", "app.py"),
            os.path.join(project_dir, "app.py"),
        )
        shutil.copy(
            os.path.join(self.base_dir, "project_scripts", "python_default", "auth.py"),
            os.path.join(project_dir, "auth.py"),
        )
        shutil.copy(
            os.path.join(
                self.base_dir, "project_scripts", "python_default", "database.py"
            ),
            os.path.join(project_dir, "database.py"),
        )
        shutil.copy(
            os.path.join(
                self.base_dir, "project_scripts", "python_default", "settings.py"
            ),
            os.path.join(project_dir, "settings.py"),
        )
        shutil.copytree(
            os.path.join(self.base_dir, "project_scripts", "admin_template"),
            os.path.join(project_dir, "templates"),
            dirs_exist_ok=True,
        )

        return nome_projeto
