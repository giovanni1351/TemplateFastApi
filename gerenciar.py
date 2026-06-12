import os
from pathlib import Path

from project_scripts.create_project import CreateProject
from project_scripts.create_schema import CreateSchema


class Gerenciar:
    def __init__(self):
        self.root_dir = Path(__file__).parent
        self.projects_dir = self.root_dir / "src"

    def menu(self) -> None:
        print("Seja bem-vindo ao gerenciador do projeto")
        print("O que deseja fazer?")
        print("0. Ver menu ")
        print("1. Criar projeto novo")
        print("2. Listar projetos")
        print("3. Criar schema")

    def run(self) -> None:
        projetos: list[str] = []
        while True:
            self.menu()
            entrada = input("O que deseja fazer? ")

            match entrada:
                case "0":
                    self.menu()
                case "1":
                    create_project = CreateProject()
                    nome_projeto = create_project.run()
                    projetos.append(nome_projeto)
                case "2":
                    print("\n\n")
                    print("Projetos: ")
                    for projeto in os.listdir(self.projects_dir):
                        print(projeto)
                    print("\n\n")
                case "3":
                    print("Selecione o projeto que vc deseja adicionar o schema")
                    print("Projetos: ")
                    projetos = os.listdir(self.projects_dir)
                    for i, projeto in enumerate(projetos):
                        print(i, projeto)
                    print("\n\n")
                    projeto_selecionado = projetos[int(input("Projeto:"))]
                    criar_schema = CreateSchema(
                        os.path.join(self.projects_dir, projeto_selecionado)
                    )
                    criar_schema.run()
                case "sair":
                    break
                case _:
                    self.menu()


if __name__ == "__main__":
    gerenciar = Gerenciar()
    gerenciar.run()
