# API FastAPI template
Esse template tem o objetivo de ser o padrão inicia
Ela ja contem tudo que é necessário para a criação de uma aplicação com
sistema de usuarios e pacotes ja mapeados para a criação dos modelos

# UV
Esse projeto é criado utilizando o gerenciador de pacotes UV
tudo que é feito aqui em questão de pacotes é adicionado pelo uv
ele substitui o pip e o pyenv, ela pode gerenciar as versões do python e as 
dependencias, tudo em cima de um arquivo chamado [pyproject.toml](pyproject.toml)
nesse arquivo contem as configurações dos linters (ruff e pyright)
Alem de versionar corretamente as dependencias, então não é necessário se preocupar
muito com isso, ela ja vai criar uma arvore de dependencia para instalar em outras
maquinas e ja baixar os modulos corretamente
## Como rodar o projeto
Para rodar o projeto
Clone o repositório
e de um `uv sync`
para isso é necessário instalar o uv

- windows `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex`
- linux e mac `curl -LsSf https://astral.sh/uv/install.sh | sh`

depois de instalar e sincronizar o ambiente com o sync, vc vai ver
que foi gerado um .venv, é o ambiente virtual, onde vai conter todas
as dependencias, assim como o `python -m venv .venv` faz
porem se vc está habituado com esse metodo padrão usando o próprio python
Ele vai criar com base no python que está na sua maquina configurado.
Com o uv, ele vai criar o repositório com oq temos em base no pyproject
caso vc n tenha a versão do python, ele vai instalar para vc e junto disso
vai baixar as dependencias e suas subdependencias tambem, padronizando 
para todo mundo 
que for mecher no projeto

depois de criar o ambiente, vc ja pode rodar a aplicação, tenha em mente
que o fastapi é um framework construido em cima do starlette e pydantic
tendo isso em mente, o servidor é iniciado usando o [uvicorn](https://uvicorn.dev/), ele é quem
realmente vai criar o serviço de api, onde vai disponibilizar a aplicação criada 
pelo starlette

Então no final, o fastapi vai apenas usar as validações de tipo do [pydantic](https://docs.pydantic.dev/latest/) 
que usa o type hints do python, então é interessantes vc ter uma noção
de como funciona a tipagem no python e os typehints, pois o fastapi
é fortemente construido em cima disso

A vantagem de utilizar as tipagens é os linters, onde vai te mostrar os 
possiveis erros que podem acontecer em relação aos tipos.
Então, se vc criar uma função que recebe um inteiro e vc chama passando
uma string, o linter vai te avisar desse erro. Para o desenvolvedor
é muito bom, pois vc consegue ja garantir que esse tipo de erro simples
não acontecerá!

# O que o fastapi faz para você?

Ele é um framework/microframework, e ele te da total liberdade para fazer 
oq vc quiser, ou seja, no final, ele só vai te dar a capacidade de criar
as rotas e especificar a entrada e saida, e tudo que é questão de validação
de tipos e serialização, ele vai cuidadar para voce, utilizando o pydantic

Ok, mas e agora? oq eu faço com isso?
Por isso que criamos esse repositório com esse template/exemplo, onde ja 
criamos para você um padrão, onde temos SQLModel uma ORM (object 
relational mapping) e um sistema de autenticação e criação de usuarios!

# SQLModel

Essa é a orm que escolhemos, por conta das facilidades que ela tras
ela usa o pydantic basemodel, ou seja, ela funciona como um validador de 
dados tambem, e tambem usa o sqlalchemy (ESTADO DA ARTE DE ORM NO Python)

Então, ele funciona assim como o BaseModel do pydantic, mas ele pode 
receber um parametro de table=true, que vai dizer que aquele modelo é uma 
tabela no banco de dados

No final, ela vai traduzir para um modelo do sqlalchemy, então, vc pode 
utilizar as facilidades de criação de consultas usando sqlalchemy no sqlmodel
A vantagem disso, é que tudo fica padronizado, se vc fosse usar o pydantic
e sqlalchemy, vc teria um modelo do sqlalchemy e do pydantic que 
representariam as mesmas inoformações, dessa forma, conseguimos deixar
o código mais limpo e intendivel

# Alembic

Voce provavelmente vai ter que atualizar o modelo do banco de dados em 
alugum momento, o alembic está aqui para isso. Ele vai gerencias as migrações
O alembic por natureza é feito para funcionar diretamente com sqlalchemy
o problema é que estamos usando o sqlmodel, e para funcionar é necessário
fazer algumas mudanças em como o alembic funciona. Mas não se preocupe, 
ja deixamos isso pronto para vc. Vc pode apenas usar os comando do 
arquivo de suporte que deixamos para vc em [COMANDOS_ALEMBIC](COMANDOS_ALEMBIC.md)

As migrações ficam armazenadas na pasta [migrations](src/projeto/migrations/), lá tem um arquivo que
é utilizado para o alembic criar as modificações, seria uma especie de 
template. ja arrumamos para funcionarcom o sqlmodel. o env.py, é o que 
realmente vai fazer a configuração, ja arrumamos tambem, para ela buscar 
da mesma função que gera a conexão com o banco da aplicação, então basta 
configurar no .env, que ela ja vai funcionar para a aplicação e alembic.

# Banco de Dados

Certo, para criar as tabelas do banco de dados, é necessário utilizar o 
alembic, ele será o encarregado de criar todas as tabelas e relações,
que vc descreveu nos modelos que vc criou usando o sqlmodel, por isso
é necessário um conhecimento de como modelar o banco com o sqlmodel.
Te garanto que é tranquilo. Ele está aqui pois é um facilitador

Voce pode acessar a documentação do [sqlmodel](https://sqlmodel.tiangolo.com/), lá vai ter passo a passo 
de como vai funcionar para a criação das tabelas, e relações

Para configurar o banco de dados, é necessário preencher todas as variaveis
de ambiente descritas no 