FROM python:3.13-slim

ENV PROJECT_HOME=/app

# --- FIX 1: Configura o cache do UV para uma pasta temporária (sempre gravável) ---
ENV UV_CACHE_DIR=/tmp/.uv-cache

EXPOSE 8000

RUN apt-get -qq update && apt-get install -y \
    build-essential \
    cmake \
    libgl1 \
    libglib2.0-0 \
    git \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir -p $PROJECT_HOME

WORKDIR $PROJECT_HOME

COPY pyproject.toml uv.lock* ./

# Instala o uv
RUN pip install --upgrade pip --no-cache-dir uv

# --- FIX 2: Garante a instalação das dependências ---
# O --frozen garante que ele use exatamente o que está no lock file
RUN uv sync --frozen --no-cache

COPY . .

# --- FIX 3 (Opcional, mas recomendado): Compilação de bytecode ---
# Isso evita que o Python tente escrever arquivos .pyc na inicialização
ENV UV_COMPILE_BYTECODE=1

# Run the application
# Nota: Como já rodamos o sync, podemos chamar o uvicorn diretamente do venv criado pelo uv
# O uv cria o venv em .venv por padrão.
CMD ["/app/.venv/bin/uvicorn", "src.projeto.app:app", "--host", "0.0.0.0", "--port", "8000","--workers","3"]