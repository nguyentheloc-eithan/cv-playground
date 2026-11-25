"""Snapshot storage: local folder or any S3-compatible bucket (AWS S3, Cloudflare R2, Backblaze B2, MinIO)."""
from pathlib import Path

from . import settings


class LocalStore:
    def __init__(self, cfg):
        self.root = settings.ROOT / cfg.path
        self.root.mkdir(parents=True, exist_ok=True)

    def put(self, name: str, data: bytes):
        (self.root / Path(name).name).write_bytes(data)

    def get(self, name: str):
        p = self.root / Path(name).name
        return p.read_bytes() if p.exists() else None

    def delete(self, name: str):
        (self.root / Path(name).name).unlink(missing_ok=True)

    def healthy(self):
        return self.root.is_dir()


class S3Store:
    def __init__(self, cfg):
        import boto3                      # installed by requirements-prod.txt
        self.bucket, self.prefix = cfg.bucket, cfg.prefix
        self.s3 = boto3.client("s3", region_name=cfg.region, endpoint_url=cfg.endpoint_url or None,
                               aws_access_key_id=cfg.access_key or None, aws_secret_access_key=cfg.secret_key or None)

    def put(self, name, data):
        self.s3.put_object(Bucket=self.bucket, Key=self.prefix + name, Body=data, ContentType="image/jpeg")

    def get(self, name):
        try:
            return self.s3.get_object(Bucket=self.bucket, Key=self.prefix + name)["Body"].read()
        except Exception:
            return None

    def delete(self, name):
        self.s3.delete_object(Bucket=self.bucket, Key=self.prefix + name)

    def healthy(self):
        self.s3.head_bucket(Bucket=self.bucket)
        return True


_store = None


def store():
    global _store
    if _store is None:
        cfg = settings.get().storage
        _store = LocalStore(cfg.local) if cfg.driver == "local" else S3Store(cfg.s3)
    return _store


def reset():
    global _store
    _store = None
