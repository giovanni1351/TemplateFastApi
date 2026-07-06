# Gerado pelo gerenciador do template. Edite via `python gerenciar.py` ou manualmente.
from utils.rbac_router import verify_rbac
from database import get_async_session
from fastcrud import crud_router  # type: ignore
from schemas.produto import Produto, ProdutoCreate, ProdutoRead, ProdutoUpdate

router = crud_router(
    session=get_async_session,
    model=Produto,
    create_schema=ProdutoCreate,
    update_schema=ProdutoUpdate,
    select_schema=ProdutoRead,
    path="/produto",
    tags=["Produto"],
    create_deps=[verify_rbac],
    read_deps=[verify_rbac],
    read_multi_deps=[verify_rbac],
    update_deps=[verify_rbac],
    delete_deps=[verify_rbac],
)
