import os
import shutil
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from fastapi import UploadFile

from app.config import settings

logger = logging.getLogger("meetora.storage")

class BaseStorageService(ABC):
    @abstractmethod
    def save_file(self, file: UploadFile, meeting_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Saves file to storage provider.
        Returns: {
            "storage_type": str,
            "file_path": str,
            "url": str,
            "file_size": int,
            "filename": str
        }
        """
        pass

    @abstractmethod
    def delete_file(self, file_path: str) -> bool:
        """Deletes file from storage."""
        pass

    @abstractmethod
    def get_file_url(self, file_path: str) -> str:
        """Returns direct or presigned URL for playback / download."""
        pass


class LocalStorageService(BaseStorageService):
    """
    Local disk storage for meeting audio/video files.
    """
    def __init__(self, upload_dir: str = settings.UPLOAD_DIR):
        self.upload_dir = upload_dir
        os.makedirs(self.upload_dir, exist_ok=True)

    def save_file(self, file: UploadFile, meeting_id: Optional[int] = None) -> Dict[str, Any]:
        prefix = f"m_{meeting_id}_" if meeting_id else ""
        safe_filename = f"{prefix}{int(os.times().elapsed * 1000)}_{file.filename or 'recording.wav'}"
        dest_path = os.path.join(self.upload_dir, safe_filename)

        with open(dest_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        size = os.path.getsize(dest_path)
        logger.info(f"Saved recording locally: {dest_path} ({size} bytes)")

        return {
            "storage_type": "local",
            "file_path": dest_path,
            "url": f"/uploads/{safe_filename}",
            "file_size": size,
            "filename": safe_filename,
        }

    def delete_file(self, file_path: str) -> bool:
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                return True
        except Exception as e:
            logger.error(f"Failed to delete local file {file_path}: {e}")
        return False

    def get_file_url(self, file_path: str) -> str:
        filename = os.path.basename(file_path)
        return f"/uploads/{filename}"


class S3StorageService(BaseStorageService):
    """
    AWS S3 / MinIO storage for meeting audio/video files.
    """
    def __init__(self):
        self.bucket = settings.AWS_S3_BUCKET
        self.region = settings.AWS_REGION
        self.endpoint_url = settings.AWS_S3_ENDPOINT_URL or None

    def _get_client(self):
        try:
            import boto3
            client_kwargs = {
                "service_name": "s3",
                "region_name": self.region,
            }
            if settings.AWS_ACCESS_KEY_ID and settings.AWS_SECRET_ACCESS_KEY:
                client_kwargs["aws_access_key_id"] = settings.AWS_ACCESS_KEY_ID
                client_kwargs["aws_secret_access_key"] = settings.AWS_SECRET_ACCESS_KEY
            if self.endpoint_url:
                client_kwargs["endpoint_url"] = self.endpoint_url
            return boto3.client(**client_kwargs)
        except ImportError:
            logger.warning("boto3 package not installed. S3 storage falling back to local simulation.")
            return None

    def save_file(self, file: UploadFile, meeting_id: Optional[int] = None) -> Dict[str, Any]:
        client = self._get_client()
        s3_key = f"meetings/{meeting_id or 'general'}/{int(os.times().elapsed * 1000)}_{file.filename or 'audio.wav'}"

        if not client:
            # Fallback to local disk if boto3 not available
            local = LocalStorageService()
            res = local.save_file(file, meeting_id)
            res["storage_type"] = "s3_simulated_local"
            return res

        # Upload file stream to S3
        file.file.seek(0, 2)
        size = file.file.tell()
        file.file.seek(0)

        client.upload_fileobj(
            file.file,
            self.bucket,
            s3_key,
            ExtraArgs={"ContentType": file.content_type or "audio/wav"}
        )

        url = client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket, "Key": s3_key},
            ExpiresIn=3600 * 24
        )

        return {
            "storage_type": "s3",
            "file_path": s3_key,
            "url": url,
            "file_size": size,
            "filename": os.path.basename(s3_key),
        }

    def delete_file(self, file_path: str) -> bool:
        client = self._get_client()
        if not client:
            return False
        try:
            client.delete_object(Bucket=self.bucket, Key=file_path)
            return True
        except Exception as e:
            logger.error(f"Failed to delete S3 object {file_path}: {e}")
            return False

    def get_file_url(self, file_path: str) -> str:
        client = self._get_client()
        if not client:
            return f"/uploads/{os.path.basename(file_path)}"
        try:
            return client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket, "Key": file_path},
                ExpiresIn=3600 * 24
            )
        except Exception:
            return f"https://{self.bucket}.s3.{self.region}.amazonaws.com/{file_path}"


class CloudinaryStorageService(BaseStorageService):
    """
    Cloudinary storage for meeting audio/video files.
    """
    def __init__(self):
        self._init_cloudinary()

    def _init_cloudinary(self):
        try:
            import cloudinary
            import cloudinary.uploader
            if settings.CLOUDINARY_URL:
                cloudinary.config(cloudinary_url=settings.CLOUDINARY_URL)
            elif settings.CLOUDINARY_CLOUD_NAME:
                cloudinary.config(
                    cloud_name=settings.CLOUDINARY_CLOUD_NAME,
                    api_key=settings.CLOUDINARY_API_KEY,
                    api_secret=settings.CLOUDINARY_API_SECRET,
                    secure=True
                )
            return True
        except ImportError:
            logger.warning("cloudinary package not installed. Cloudinary storage falling back to local.")
            return False

    def save_file(self, file: UploadFile, meeting_id: Optional[int] = None) -> Dict[str, Any]:
        try:
            import cloudinary
            import cloudinary.uploader

            file.file.seek(0, 2)
            size = file.file.tell()
            file.file.seek(0)

            folder = f"meetora/meetings/{meeting_id or 'general'}"
            res = cloudinary.uploader.upload(
                file.file,
                resource_type="auto",
                folder=folder,
                use_filename=True,
                unique_filename=True,
            )

            return {
                "storage_type": "cloudinary",
                "file_path": res.get("public_id", ""),
                "url": res.get("secure_url", res.get("url", "")),
                "file_size": size,
                "filename": os.path.basename(res.get("secure_url", file.filename)),
            }
        except Exception as e:
            logger.warning(f"Cloudinary upload failed ({e}), falling back to local disk storage.")
            local = LocalStorageService()
            res = local.save_file(file, meeting_id)
            res["storage_type"] = "cloudinary_fallback_local"
            return res

    def delete_file(self, file_path: str) -> bool:
        try:
            import cloudinary.uploader
            cloudinary.uploader.destroy(file_path, resource_type="video")
            return True
        except Exception as e:
            logger.error(f"Failed to delete Cloudinary asset {file_path}: {e}")
            return False

    def get_file_url(self, file_path: str) -> str:
        if file_path.startswith("http"):
            return file_path
        return f"https://res.cloudinary.com/{settings.CLOUDINARY_CLOUD_NAME}/video/upload/{file_path}"


def get_storage() -> BaseStorageService:
    provider = settings.STORAGE_PROVIDER.lower().strip()
    if provider == "s3":
        return S3StorageService()
    elif provider == "cloudinary":
        return CloudinaryStorageService()
    return LocalStorageService()

