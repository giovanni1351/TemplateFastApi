# FastAPI Template

Template completo para APIs com FastAPI, incluindo sistema de autenticação, painel administrativo personalizado e banco de dados com SQLModel.

## Stack Tecnológica

- **Framework**: FastAPI + Starlette + Pydantic
- **ORM**: SQLModel (SQLAlchemy + Pydantic)
- **Admin**: SQLAdmin com tema Tailwind CSS customizado
- **Banco de Dados**: PostgreSQL (produção) / SQLite (desenvolvimento)
- **Migrações**: Alembic
- **Gerenciador de Pacotes**: UV
- **Linters**: Ruff + Pyright
- **Servidor**: Uvicorn

## Como Rodar

### 1. Instale o UV

**Windows (PowerShell):**
```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

**Linux/macOS:**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 2. Clone e instale as dependências

```bash
git clone <repositorio>
cd FastAPITemplate
uv sync
```

O UV cria automaticamente o ambiente virtual `.venv` e instala todas as dependências definidas no `pyproject.toml`.

### 3. Configure as variáveis de ambiente

Copie `.env.example` para `.env` e ajuste os valores:

```bash
cp .env.example .env
```

**Variáveis principais:**

| Variável | Descrição | Padrão |
|----------|-----------|--------|
| `SQLITE_DEV` | Use `1` para SQLite local, `0` para PostgreSQL | `0` |
| `SECRET_KEY` | Chave para JWT | - |
| `ALGORITHM` | Algoritmo JWT | `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Expiração do token | `2500` |
| `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_DATABASE` | Configurações PostgreSQL | - |

### 4. Execute as migrações

```bash
uv run alembic upgrade head
```

### 5. Inicie o servidor

```bash
uv run python src/projeto/app.py
```

Acesse:
- **API**: http://localhost:8000/docs
- **Admin**: http://localhost:8000/admin
- **Health**: http://localhost:8000/heath

## Estrutura do Projeto

```
src/projeto/
├── admin.py              # Views do painel admin (ModelViews)
├── admin_config.py       # Configurações visuais do admin
├── app.py                # Aplicação FastAPI principal
├── auth.py               # Autenticação e JWT
├── database.py           # Conexão com banco de dados
├── settings.py           # Configurações via .env
├── middleware/
│   └── csp.py            # Middleware Content Security Policy
├── migrations/           # Migrações Alembic
├── routes/               # Rotas da API
├── schemas/              # Modelos SQLModel
├── static/               # Arquivos estáticos (ícones, imagens)
│   └── icons/
├── templates/
│   └── sqladmin/         # Templates customizados do admin
│       ├── base.html
│       ├── layout.html
│       ├── login.html
│       ├── index.html
│       ├── list.html
│       ├── create.html
│       ├── edit.html
│       ├── details.html
│       ├── error.html
│       ├── _macros.html
│       └── modals/
└── utils/
```

## Painel Administrativo

O admin é construído com **SQLAdmin** e totalmente personalizado com **Tailwind CSS** via CDN.

### Configurações Visuais

Edite `src/projeto/admin_config.py` para personalizar:

```python
from dataclasses import dataclass

@dataclass
class AdminConfig:
    nome_sistema: str = "Administração"      # Nome exibido na sidebar
    nome_empresa: str = "Empresa LTDA"       # Subtítulo na sidebar
    logo_url: str | None = None              # URL ou caminho da logo
    cor_primaria: str = "#3b82f6"            # Azul (botões, links)
    cor_secundaria: str = "#64748b"          # Cinza
    cor_sidebar: str = "#1e293b"             # Fundo da sidebar
    cor_destaque: str = "#10b981"            # Verde (edição)
    cor_fundo: str = "#f8fafc"               # Fundo da página
    tailwind_cdn: str = "https://cdn.tailwindcss.com"

ADMIN_CONFIG = AdminConfig()
```

**Exemplo com logo local:**
```python
ADMIN_CONFIG = AdminConfig(
    nome_sistema="Meu Sistema",
    nome_empresa="Minha Empresa",
    logo_url="/static/logo.png",  # Coloque em src/projeto/static/
    cor_primaria="#8b5cf6",       # Roxo
)
```

### Criando Views do Admin

Edite `src/projeto/admin.py` para adicionar modelos ao painel:

```python
from sqladmin import ModelView
from schemas.meu_modelo import MeuModelo

class MeuModeloAdmin(ModelView, model=MeuModelo):
    column_list = [MeuModelo.nome, MeuModelo.descricao]
    can_create = True
    card_style = True                    # Exibe como cards (False = tabela)
    icon = "fa-solid fa-box"            # Ícone na sidebar
```

Depois registre em `app.py`:
```python
from admin import MeuModeloAdmin
admin.add_view(MeuModeloAdmin)
```

### Ícones Customizáveis

O atributo `icon` aceita múltiplos formatos:

```python
class ExemploAdmin(ModelView, model=Exemplo):
    # Font Awesome (já incluído no SQLAdmin)
    icon = "fa-solid fa-users"

    # Emoji
    icon = "📦"

    # Arquivo local (coloque em src/projeto/static/icons/)
    icon = "/static/icons/book.svg"

    # URL externa
    icon = "https://example.com/icon.png"

    # Sem ícone (usa placeholder padrão)
    icon = None
```

### Modo Card vs Tabela

Use `card_style = True` para exibir registros como cards:

```python
class ProdutoAdmin(ModelView, model=Produto):
    column_list = [Produto.nome, Produto.preco]
    card_style = True   # Cards (grid responsivo)

class LogAdmin(ModelView, model=Log):
    column_list = [Log.data, Log.mensagem]
    card_style = False  # Tabela (padrão)
```

O primeiro campo do `column_list` aparece em destaque nos cards.

### Criação de Usuários com Hash de Senha

O `UserAdmin` já está configurado para criar usuários com senha hasheada corretamente:

```python
class UserAdmin(ModelView, model=User):
    column_list = [User.nome, User.sobrenome, User.email, User.is_admin]
    column_details_exclude_list = [User.password]  # Oculta senha nos detalhes
    can_create = True
    card_style = True
    icon = "fa-solid fa-users"

    async def insert_model(self, request: Request, data: dict[str, Any]) -> User:
        if "password" in data and data["password"]:
            data["password"] = get_password_hash(data["password"])
        return await super().insert_model(request, data)

    async def update_model(
        self, request: Request, pk: Any, data: dict[str, Any]
    ) -> User:
        if "password" in data:
            if data["password"]:
                data["password"] = get_password_hash(data["password"])
            else:
                data.pop("password")  # Não atualiza se campo vazio
        return await super().update_model(request, pk, data)
```

**Funcionalidades:**
- ✅ Senha hasheada automaticamente ao criar usuário (Argon2)
- ✅ Senha hasheada ao atualizar (apenas se fornecida)
- ✅ Campo de senha oculto na listagem e detalhes
- ✅ Se deixar senha em branco na edição, mantém a senha atual

**Como usar:**
1. Acesse `/admin`
2. Clique em "Usuários"
3. Clique em "+ Novo User"
4. Preencha nome, sobrenome, email e senha
5. Marque "Is admin" se for administrador
6. Clique em "Salvar"

### Responsividade

Todos os templates são responsivos:
- **Mobile**: Sidebar oculta, botão hamburger no header
- **Tablet**: Grid adaptativo
- **Desktop**: Sidebar sempre visível, pode ser minimizada

### Sidebar Colapsável

No desktop, clique no botão de seta dupla (◀◀) na sidebar para minimizar:
- Mostra apenas ícones
- Estado salvo em `localStorage`
- Tooltips aparecem ao passar o mouse

No mobile, o botão hamburger abre/fecha a sidebar com overlay.

### Middleware CSP

O `CSPMiddleware` em `src/projeto/middleware/csp.py` configura headers de segurança para permitir o Tailwind CDN:

```python
Content-Security-Policy:
    default-src 'self';
    script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.tailwindcss.com;
    style-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com;
    img-src 'self' data: https:;
    font-src 'self' data:;
```

## Desenvolvimento

### Adicionando Novas Rotas

1. Crie `src/projeto/routes/minha_rota.py`:
```python
from fastapi import APIRouter
from database import AsyncSessionDep

router = APIRouter(prefix="/minha-rota", tags=["Minha Rota"])

@router.get("/")
async def listar(session: AsyncSessionDep):
    # sua lógica
    pass
```

2. Registre em `app.py`:
```python
from routes import minha_rota
app.include_router(minha_rota.router)
```

### Criando Modelos

Use SQLModel em `src/projeto/schemas/`:

```python
from sqlmodel import SQLModel, Field

class Produto(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    nome: str = Field(max_length=100)
    preco: float
```

### Gerando Migrações

```bash
# Criar migração automática
uv run alembic revision --autogenerate -m "descrição da mudança"

# Aplicar migrações
uv run alembic upgrade head

# Reverter última migração
uv run alembic downgrade -1
```

Veja mais comandos em [COMANDOS_ALEMBIC.md](COMANDOS_ALEMBIC.md).

### Linting e Formatação

```bash
# Verificar erros
uv run ruff check src/

# Corrigir automaticamente
uv run ruff check src/ --fix

# Formatar código
uv run ruff format src/

# Verificar tipos
uv run pyright
```

## SQLModel

SQLModel combina Pydantic + SQLAlchemy em uma única classe:

```python
from sqlmodel import SQLModel, Field, Relationship

class Autor(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    nome: str
    livros: list["Livro"] = Relationship(back_populates="autor")

class Livro(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    titulo: str
    autor_id: int | None = Field(default=None, foreign_key="autor.id")
    autor: Autor | None = Relationship(back_populates="livros")
```

**Vantagens:**
- Validação de dados (Pydantic)
- ORM completo (SQLAlchemy)
- Uma única classe para modelo e schema
- Type hints funcionam com linters

## Autenticação

O sistema usa JWT com autenticação OAuth2:

1. **Login**: `POST /token` com `username` e `password`
2. **Token**: Retorna `access_token` para usar em requests
3. **Uso**: Header `Authorization: Bearer <token>`

O admin usa autenticação separada via sessão, verificando o campo `is_admin` do usuário.

## Dependências Principais

| Pacote | Uso |
|--------|-----|
| `fastapi` | Framework web |
| `sqlmodel` | ORM + validação |
| `sqladmin` | Painel administrativo |
| `alembic` | Migrações de banco |
| `pyjwt` | Tokens JWT |
| `bcrypt` | Hash de senhas |
| `pydantic-settings` | Configurações via .env |
| `uvicorn` | Servidor ASGI |
| `minio` | Storage de arquivos (opcional) |

## Recursos Incluídos

- ✅ Sistema de usuários com autenticação JWT
- ✅ Painel admin personalizado com Tailwind CSS
- ✅ Migrações de banco com Alembic
- ✅ Configuração via variáveis de ambiente
- ✅ Logging estruturado (pylogkit)
- ✅ Suporte a MinIO (storage S3-compatible)
- ✅ SMTP configurável para emails
- ✅ Linting e formatação automáticos
- ✅ Type checking com Pyright
- ✅ Templates responsivos
- ✅ Ícones customizáveis
- ✅ Middleware CSP para segurança