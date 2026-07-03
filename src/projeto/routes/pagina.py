from database import get_async_session
from fastcrud import crud_router  # type: ignore
from schemas.pagina import Pagina, PaginaCreate, PaginaRead, PaginaUpdate
from utils.rbac_router import verify_rbac

router = crud_router(
    session=get_async_session,
    model=Pagina,
    create_schema=PaginaCreate,
    update_schema=PaginaUpdate,
    select_schema=PaginaRead,
    include_relationships=["livro"],  # Optional: automatically include related data
    path="/pagina",
    tags=["Pagina"],
    create_deps=[verify_rbac],
    read_deps=[verify_rbac],
    read_multi_deps=[verify_rbac],
    update_deps=[verify_rbac],
    delete_deps=[verify_rbac],
)
