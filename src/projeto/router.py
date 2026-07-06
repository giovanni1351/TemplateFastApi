from fastapi import APIRouter
from routes import livro, pagina, produto, token, user

router = APIRouter()


router.include_router(user.router)
router.include_router(token.router)
router.include_router(livro.router)
router.include_router(pagina.router)
router.include_router(produto.router)
