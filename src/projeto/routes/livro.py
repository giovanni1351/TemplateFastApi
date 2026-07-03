from database import get_async_session
from fastcrud import crud_router  # type: ignore
from schemas.livro import Livro, LivroCreate, LivroRead, LivroUpdate
from utils.rbac_router import verify_rbac

router = crud_router(
    session=get_async_session,
    model=Livro,
    create_schema=LivroCreate,
    update_schema=LivroUpdate,
    select_schema=LivroRead,
    include_relationships=["paginas"],  # Optional: automatically include related data
    path="/livro",
    tags=["Livro"],
    create_deps=[verify_rbac],
    read_deps=[verify_rbac],
    read_multi_deps=[verify_rbac],
    update_deps=[verify_rbac],
    delete_deps=[verify_rbac],
)
