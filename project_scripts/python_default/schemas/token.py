from pydantic import BaseModel


class Token(BaseModel):
    """
    Schema para o token
    """

    access_token: str
    token_type: str


class TokenData(BaseModel):
    email: str | None = None
