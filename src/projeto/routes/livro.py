from auth import UserByRole
from database import get_async_session
from fastcrud import crud_router  # type: ignore
from schemas.livro import Livro, LivroCreate, LivroRead, LivroUpdate

router = crud_router(
    session=get_async_session,
    model=Livro,
    create_schema=LivroCreate,
    update_schema=LivroUpdate,
    select_schema=LivroRead,
    include_relationships=["paginas"],  # Optional: automatically include related data
    path="/livro",
    tags=["Livro"],
    create_deps=[UserByRole([])],
    read_deps=[UserByRole([])],
    read_multi_deps=[UserByRole([])],
    update_deps=[UserByRole([])],
    delete_deps=[UserByRole([])],
)
