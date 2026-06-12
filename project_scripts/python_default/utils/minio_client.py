import uuid
from datetime import timedelta
from typing import cast
from urllib.parse import urlparse

import urllib3
from fastapi import UploadFile
from minio import Minio
from minio.credentials.providers import Provider
from settings import SETTINGS

BUCKET_NAME = "oliveiracarvalho"
# Validade da presigned URL gerada on-demand (24 horas)
PRESIGNED_URL_EXPIRY = timedelta(hours=24)


class MinioClient(Minio):
    def __init__(
        self,
        session_token: str | None = None,
        region: str | None = None,
        http_client: urllib3.PoolManager | None = None,
        credentials: Provider | None = None,
        cert_check: bool = True,  # noqa: FBT001, FBT002
    ) -> None:
        super().__init__(
            SETTINGS.MINIO_URL or "localhost:9000",
            SETTINGS.MINIO_USER,
            SETTINGS.MINIO_PASSWORD,
            session_token,
            bool(
                SETTINGS.MINIO_SECURE
                and "localhost" not in (SETTINGS.MINIO_URL or "localhost:9000")
            ),
            region,
            http_client,
            credentials,
            cert_check,
        )

    def _garantir_bucket(self) -> None:
        """Garante que o bucket padrão existe."""
        if not self.bucket_exists(BUCKET_NAME):
            self.make_bucket(BUCKET_NAME)

    def fazer_upload(self, image: UploadFile) -> str:
        """
        Faz upload de uma imagem para o bucket e retorna o object_name (permanente).

        O object_name deve ser armazenado no banco de dados para permitir
        a geração de URLs on-demand via `gerar_url`.
        """
        self._garantir_bucket()

        # Gera nome único com extensão normalizada para lowercase
        filename = image.filename or "arquivo"
        raw_ext = filename.rsplit(".", 1)[-1] if "." in filename else "bin"
        extension = raw_ext.split("?")[0].lower()  # remove query strings e normaliza
        object_name = f"{uuid.uuid4()}.{extension}"

        # Calcula tamanho do arquivo para o MinIO
        image.file.seek(0, 2)
        file_size = image.file.tell()
        image.file.seek(0)

        self.put_object(
            bucket_name=BUCKET_NAME,
            object_name=object_name,
            data=image.file,
            length=file_size,
            content_type=image.content_type or "application/octet-stream",
        )

        return object_name

    def gerar_url(self, object_name: str) -> str:
        """
        Gera uma presigned URL de acesso temporário para um object_name existente.

        Validade: PRESIGNED_URL_EXPIRY (padrão 24 horas).
        Chame este método sempre que precisar exibir a imagem — nunca armazene a URL.
        Se MINIO_PUBLIC_URL estiver definido, o host da URL é trocado para que o app
        (em outro dispositivo) consiga carregar imagens e áudios.
        """
        url = self.get_presigned_url(
            "GET",
            BUCKET_NAME,
            object_name,
            expires=PRESIGNED_URL_EXPIRY,
        )
        public_url = getattr(SETTINGS, "MINIO_PUBLIC_URL", None)
        if public_url and public_url.strip():
            parsed = urlparse(url)
            pub = urlparse(public_url.strip().rstrip("/"))
            url = f"{cast('str', pub.scheme)}://{cast('str', pub.netloc)}{parsed.path}?{parsed.query}"
        return url

    def registrar_image(self, image: UploadFile) -> tuple[str, str]:
        """
        Compatibilidade retroativa: faz upload e retorna (object_name, url).

        Prefira usar `fazer_upload` + `gerar_url` separadamente.
        A URL retornada expira em PRESIGNED_URL_EXPIRY (24 horas).
        """
        object_name = self.fazer_upload(image)
        url = self.gerar_url(object_name)

        return object_name, url

    def gerar_url_fresca(self, stored_url: str) -> str:
        """
        Se stored_url for uma URL presigned, extrai bucket/object_name e gera nova URL.
        Se for apenas object_name (ex.: uuid.jpg), gera presigned com gerar_url.
        """
        try:
            parsed = urlparse(stored_url)
            path_parts = parsed.path.lstrip("/").split("/", 1)
            if len(path_parts) == 2:
                bucket, obj_name = path_parts
                url = self.get_presigned_url(
                    "GET", bucket, obj_name, expires=timedelta(hours=12)
                )
            else:
                return self.gerar_url(stored_url)

            public_url = getattr(SETTINGS, "MINIO_PUBLIC_URL", None)
            if public_url and public_url.strip():
                p = urlparse(url)
                pub = urlparse(public_url.strip().rstrip("/"))
                url = f"{cast('str', pub.scheme)}://{cast('str', pub.netloc)}{p.path}?{p.query}"
            return url
        except Exception:  # noqa: BLE001
            return stored_url
