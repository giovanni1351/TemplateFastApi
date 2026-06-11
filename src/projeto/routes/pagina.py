from database import get_async_session
from fastcrud import crud_router  # type: ignore
from schemas.pagina import Pagina, PaginaCreate, PaginaRead, PaginaUpdate

router = crud_router(
    session=get_async_session,
    model=Pagina,
    create_schema=PaginaCreate,
    update_schema=PaginaUpdate,
    select_schema=PaginaRead,
    include_relationships=["livro"],  # Optional: automatically include related data
    path="/pagina",
    tags=["Pagina"],
)
