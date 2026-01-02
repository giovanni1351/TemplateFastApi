# Comandos do Alembic

## Comandos principais para gerenciar migrações:

### Criar uma nova migração

```bash
uv run alembic revision --autogenerate -m "Descrição da migração"
```

### Aplicar migrações

```bash
# Aplicar todas as migrações pendentes
uv run alembic upgrade head

# Aplicar até uma migração específica
uv run alembic upgrade <revision_id>
```

### Reverter migrações

```bash
# Reverter uma migração
uv run alembic downgrade -1

# Reverter até uma migração específica
uv run alembic downgrade <revision_id>

# Reverter tudo (voltar ao estado inicial)
uv run alembic downgrade base
```

### Verificar status

```bash
# Ver migração atual
uv run alembic current

# Ver histórico de migrações
uv run alembic history

# Ver histórico com mais detalhes
uv run alembic history -v

# Verificar se há diferenças entre modelos e banco
uv run alembic check
```

### Criar migração manual (sem autogenerate)

```bash
uv run alembic revision -m "Descrição"
```

### Marcar migração como aplicada (sem executar)

```bash
uv run alembic stamp head
uv run alembic stamp <revision_id>
```

## Fluxo de trabalho recomendado:

1. **Modificar modelos** - Alterar os arquivos em `models/`
2. **Gerar migração** - `uv run alembic revision --autogenerate -m "Descrição"`
3. **Revisar migração** - Verificar o arquivo gerado em `alembic/versions/`
4. **Aplicar migração** - `uv run alembic upgrade head`

## Estrutura de arquivos:

- `alembic.ini` - Configuração do Alembic (URL do banco, etc.)
- `alembic/env.py` - Script de ambiente (configurado para SQLModel)
- `alembic/versions/` - Diretório com as migrações
- `models/__init__.py` - Importa todos os modelos para o Alembic detectar

## Exemplo de uso completo:

```bash
# 1. Adicionar novo campo ao modelo User
# 2. Gerar migração
uv run alembic revision --autogenerate -m "Add email_verified field to User"

# 3. Verificar se a migração foi gerada corretamente
uv run alembic history

# 4. Aplicar a migração
uv run alembic upgrade head

# 5. Verificar se foi aplicada
uv run alembic current
```

## Dicas importantes:

- **Sempre revisar** os arquivos de migração antes de aplicar
- **Fazer backup** do banco antes de aplicar migrações em produção
- **Testar migrações** em ambiente de desenvolvimento primeiro
- **Não editar** migrações já aplicadas, criar uma nova se necessário
- **Para SQLite** o projeto está configurado com `render_as_batch=True` para suportar alterações complexas
