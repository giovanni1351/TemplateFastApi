from fastapi import APIRouter
from routes import token, user

router = APIRouter()


router.include_router(user.router)
router.include_router(token.router)
