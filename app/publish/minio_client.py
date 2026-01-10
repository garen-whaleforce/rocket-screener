"""MinIO storage client for article archiving.

Stores articles to MinIO before publishing to Ghost.
Uses S3-compatible API via boto3.
"""

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


@dataclass
class MinIOConfig:
    """MinIO connection configuration."""

    endpoint_url: str
    access_key: str
    secret_key: str
    bucket: str = "rocket-screener"
    verify_ssl: bool = True

    @classmethod
    def from_env(cls) -> "MinIOConfig":
        """Load config from environment variables."""
        import os

        # Use external endpoint that has valid SSL cert
        endpoint = os.environ.get(
            "MINIO_ENDPOINT", "https://minio.api.whaleforce.dev"
        )
        access_key = os.environ.get("MINIO_ACCESS_KEY", "whaleforce")
        secret_key = os.environ.get("MINIO_SECRET_KEY", "whaleforce.ai")
        bucket = os.environ.get("MINIO_BUCKET", "rocket-screener")
        verify_ssl = os.environ.get("MINIO_VERIFY_SSL", "true").lower() == "true"

        return cls(
            endpoint_url=endpoint,
            access_key=access_key,
            secret_key=secret_key,
            bucket=bucket,
            verify_ssl=verify_ssl,
        )


class MinIOClient:
    """Client for storing articles to MinIO."""

    def __init__(self, config: Optional[MinIOConfig] = None):
        self.config = config or MinIOConfig.from_env()
        self._client = None

    @property
    def client(self):
        """Lazy initialization of S3 client."""
        if self._client is None:
            self._client = boto3.client(
                "s3",
                endpoint_url=self.config.endpoint_url,
                aws_access_key_id=self.config.access_key,
                aws_secret_access_key=self.config.secret_key,
                config=Config(signature_version="s3v4"),
                verify=self.config.verify_ssl,
            )
        return self._client

    def ensure_bucket_exists(self) -> bool:
        """Ensure the bucket exists, create if not.

        Returns:
            True if bucket exists or was created
        """
        try:
            self.client.head_bucket(Bucket=self.config.bucket)
            return True
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code")
            if error_code == "404":
                try:
                    self.client.create_bucket(Bucket=self.config.bucket)
                    logger.info(f"Created bucket: {self.config.bucket}")
                    return True
                except ClientError as create_error:
                    logger.error(f"Failed to create bucket: {create_error}")
                    return False
            else:
                logger.error(f"Error checking bucket: {e}")
                return False

    def store_article(
        self,
        article_num: int,
        date_str: str,
        content: str,
        metadata: Optional[dict] = None,
    ) -> Optional[str]:
        """Store article content to MinIO.

        Args:
            article_num: Article number (1, 2, or 3)
            date_str: Date string (YYYY-MM-DD)
            content: Article markdown content
            metadata: Optional metadata dict

        Returns:
            Object key if successful, None otherwise
        """
        # Build object key: articles/{date}/article{num}.md
        key = f"articles/{date_str}/article{article_num}.md"

        try:
            self.ensure_bucket_exists()

            # Store article content
            self.client.put_object(
                Bucket=self.config.bucket,
                Key=key,
                Body=content.encode("utf-8"),
                ContentType="text/markdown; charset=utf-8",
                Metadata={
                    "article-num": str(article_num),
                    "date": date_str,
                    "created-at": datetime.now().isoformat(),
                    **(metadata or {}),
                },
            )
            logger.info(f"Stored article to MinIO: {key}")
            return key

        except ClientError as e:
            logger.error(f"Failed to store article {article_num} to MinIO: {e}")
            return None

    def store_evidence_pack(
        self,
        article_num: int,
        date_str: str,
        evidence_pack: dict,
    ) -> Optional[str]:
        """Store evidence pack to MinIO for reproducibility.

        Args:
            article_num: Article number (1, 2, or 3)
            date_str: Date string (YYYY-MM-DD)
            evidence_pack: Evidence pack dict

        Returns:
            Object key if successful, None otherwise
        """
        key = f"evidence/{date_str}/article{article_num}_evidence.json"

        try:
            self.ensure_bucket_exists()

            content = json.dumps(evidence_pack, ensure_ascii=False, indent=2, default=str)
            self.client.put_object(
                Bucket=self.config.bucket,
                Key=key,
                Body=content.encode("utf-8"),
                ContentType="application/json; charset=utf-8",
            )
            logger.info(f"Stored evidence pack to MinIO: {key}")
            return key

        except ClientError as e:
            logger.error(f"Failed to store evidence pack {article_num} to MinIO: {e}")
            return None

    def store_run_manifest(
        self,
        date_str: str,
        manifest: dict,
    ) -> Optional[str]:
        """Store run manifest with all article keys and metadata.

        Args:
            date_str: Date string (YYYY-MM-DD)
            manifest: Run manifest dict

        Returns:
            Object key if successful, None otherwise
        """
        key = f"manifests/{date_str}/run_manifest.json"

        try:
            self.ensure_bucket_exists()

            content = json.dumps(manifest, ensure_ascii=False, indent=2, default=str)
            self.client.put_object(
                Bucket=self.config.bucket,
                Key=key,
                Body=content.encode("utf-8"),
                ContentType="application/json; charset=utf-8",
            )
            logger.info(f"Stored run manifest to MinIO: {key}")
            return key

        except ClientError as e:
            logger.error(f"Failed to store run manifest to MinIO: {e}")
            return None

    def get_article(self, article_num: int, date_str: str) -> Optional[str]:
        """Retrieve article content from MinIO.

        Args:
            article_num: Article number (1, 2, or 3)
            date_str: Date string (YYYY-MM-DD)

        Returns:
            Article content if found, None otherwise
        """
        key = f"articles/{date_str}/article{article_num}.md"

        try:
            response = self.client.get_object(
                Bucket=self.config.bucket,
                Key=key,
            )
            content = response["Body"].read().decode("utf-8")
            return content

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code")
            if error_code == "NoSuchKey":
                logger.warning(f"Article not found: {key}")
            else:
                logger.error(f"Failed to get article: {e}")
            return None

    def list_articles(self, date_str: str) -> list[str]:
        """List all articles for a given date.

        Args:
            date_str: Date string (YYYY-MM-DD)

        Returns:
            List of object keys
        """
        prefix = f"articles/{date_str}/"

        try:
            response = self.client.list_objects_v2(
                Bucket=self.config.bucket,
                Prefix=prefix,
            )
            return [obj["Key"] for obj in response.get("Contents", [])]

        except ClientError as e:
            logger.error(f"Failed to list articles: {e}")
            return []


def store_articles_to_minio(
    articles: list[tuple[int, str, dict]],
    date_str: str,
    dry_run: bool = False,
) -> dict:
    """Store all articles to MinIO before publishing.

    Args:
        articles: List of (article_num, content, evidence_pack) tuples
        date_str: Date string (YYYY-MM-DD)
        dry_run: If True, skip actual storage

    Returns:
        Dict with storage results
    """
    if dry_run:
        logger.info("[DRY RUN] Would store articles to MinIO")
        return {
            "success": True,
            "dry_run": True,
            "articles": [num for num, _, _ in articles],
        }

    client = MinIOClient()
    results = {
        "success": True,
        "articles": [],
        "evidence": [],
        "errors": [],
    }

    for article_num, content, evidence_pack in articles:
        # Store article
        article_key = client.store_article(article_num, date_str, content)
        if article_key:
            results["articles"].append(article_key)
        else:
            results["success"] = False
            results["errors"].append(f"Failed to store article {article_num}")

        # Store evidence pack
        if evidence_pack:
            evidence_key = client.store_evidence_pack(
                article_num, date_str, evidence_pack
            )
            if evidence_key:
                results["evidence"].append(evidence_key)

    # Store run manifest
    manifest = {
        "date": date_str,
        "created_at": datetime.now().isoformat(),
        "articles": results["articles"],
        "evidence_packs": results["evidence"],
        "success": results["success"],
    }
    manifest_key = client.store_run_manifest(date_str, manifest)
    if manifest_key:
        results["manifest"] = manifest_key

    return results
