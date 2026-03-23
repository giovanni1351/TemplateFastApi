from database import get_async_session
from fastcrud import crud_router  # type: ignore
from schemas.pagina import Pagina, PaginaCreate, PaginaUpdate

router = crud_router(
    session=get_async_session,
    model=Pagina,
    create_schema=PaginaCreate,
    update_schema=PaginaUpdate,
    include_relationships=["livro"],  # Optional: automatically include related data
    path="/Pagina",
    tags=["Pagina"],
)
