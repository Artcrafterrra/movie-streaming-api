from typing import Union
import mimetypes

import aioboto3
from botocore.exceptions import (
    BotoCoreError,
    NoCredentialsError,
    HTTPClientError,
    ConnectionError,
)

from exceptions import S3ConnectionError, S3FileUploadError
from storages.interfaces import S3StorageInterface


class S3StorageClient(S3StorageInterface):

    def __init__(
        self,
        endpoint_url: str | None,
        access_key: str,
        secret_key: str,
        bucket_name: str,
        region_name: str = "us-east-1",
    ):
        """
        Initialize the asynchronous S3 Storage Client using an aioboto3 Session.

        Args:
            endpoint_url (str | None): S3-compatible storage endpoint. None for AWS S3.
            access_key (str): Access key for authentication.
            secret_key (str): Secret key for authentication.
            bucket_name (str): Name of the bucket where files will be stored.
            region_name (str): AWS region name.
        """
        self._endpoint_url = endpoint_url
        self._access_key = access_key
        self._secret_key = secret_key
        self._bucket_name = bucket_name
        self._region_name = region_name

        self._session = aioboto3.Session(
            aws_access_key_id=self._access_key,
            aws_secret_access_key=self._secret_key,
            region_name=self._region_name,
        )

    async def upload_file(
        self,
        file_name: str,
        file_data: Union[bytes, bytearray],
        content_type: str | None = None,
    ) -> None:
        """
        Asynchronously upload a file to the S3-compatible storage.

        Args:
            file_name (str): The name of the file to be stored.
            file_data (Union[bytes, bytearray]): The file data in bytes.
            content_type (str | None): MIME type of the file. Auto-detected if None.

        Raises:
            S3ConnectionError: If there is a connection error with S3.
            S3FileUploadError: If the file upload fails due to a BotoCore error.
        """
        if not content_type:
            content_type, _ = mimetypes.guess_type(file_name)
            content_type = content_type or "application/octet-stream"

        try:
            client_kwargs = {}
            if self._endpoint_url:
                client_kwargs["endpoint_url"] = self._endpoint_url

            async with self._session.client("s3", **client_kwargs) as client:
                await client.put_object(
                    Bucket=self._bucket_name,
                    Key=file_name,
                    Body=file_data,
                    ContentType=content_type,
                )
        except (ConnectionError, HTTPClientError, NoCredentialsError) as e:
            raise S3ConnectionError(
                f"Failed to connect to S3 storage: {str(e)}"
            ) from e
        except BotoCoreError as e:
            raise S3FileUploadError(
                f"Failed to upload to S3 storage: {str(e)}"
            ) from e

    async def get_file_url(self, file_name: str) -> str:
        """
        Generate a public URL for a file stored in the S3-compatible storage.

        Args:
            file_name (str): The name of the file stored in the bucket.

        Returns:
            str: The full URL to access the file.
        """
        if self._endpoint_url:
            # Custom S3-compatible endpoint (MinIO, etc.)
            return f"{self._endpoint_url}/{self._bucket_name}/{file_name}"
        else:
            # AWS S3 standard URL format
            return f"https://{self._bucket_name}.s3.{self._region_name}.amazonaws.com/{file_name}"
