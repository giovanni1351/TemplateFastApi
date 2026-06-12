from dataclasses import dataclass


@dataclass
class AdminConfig:
    nome_sistema: str = "Administração"
    nome_empresa: str = "Empresa LTDA"
    logo_url: str | None = None
    cor_primaria: str = "#3b82f6"
    cor_secundaria: str = "#64748b"
    cor_sidebar: str = "#1e293b"
    cor_destaque: str = "#10b981"
    cor_fundo: str = "#f8fafc"
    tailwind_cdn: str = "https://cdn.tailwindcss.com"


ADMIN_CONFIG = AdminConfig()
