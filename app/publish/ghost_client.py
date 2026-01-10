"""Ghost Admin API client.

Handles authentication, post creation/update, and newsletter sending.
Implements idempotent publishing using slug-based deduplication.
"""

import hashlib
import hmac
import logging
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

import requests

from app.config import GhostConfig

logger = logging.getLogger(__name__)


@dataclass
class Post:
    """Represents a Ghost post."""

    title: str
    slug: str
    html: str
    status: str = "draft"
    feature_image: Optional[str] = None
    tags: Optional[list[str]] = None
    excerpt: Optional[str] = None
    # Ghost post ID (set after creation/fetch)
    id: Optional[str] = None


class GhostClient:
    """Client for Ghost Admin API.

    Implements:
    - JWT authentication
    - Post create/update (idempotent by slug)
    - Newsletter sending (only for specified posts)
    """

    def __init__(self, config: GhostConfig):
        self.config = config
        self.base_url = config.admin_api_url.rstrip("/")
        self._token: Optional[str] = None
        self._token_expires: float = 0

    def _generate_token(self) -> str:
        """Generate JWT token for Ghost Admin API.

        Ghost Admin API key format: {id}:{secret}
        Token is valid for 5 minutes.
        """
        import jwt

        # Split the key into id and secret
        key_parts = self.config.admin_api_key.split(":")
        if len(key_parts) != 2:
            raise ValueError(
                "Invalid Ghost Admin API key format. Expected: {id}:{secret}"
            )

        key_id, secret = key_parts

        # Decode the secret (it's hex-encoded)
        secret_bytes = bytes.fromhex(secret)

        # Create JWT header and payload
        iat = int(time.time())
        exp = iat + 5 * 60  # 5 minutes

        header = {"alg": "HS256", "typ": "JWT", "kid": key_id}
        payload = {"iat": iat, "exp": exp, "aud": "/admin/"}

        token = jwt.encode(payload, secret_bytes, algorithm="HS256", headers=header)
        self._token_expires = exp

        return token

    def _get_token(self) -> str:
        """Get valid JWT token, regenerating if expired."""
        if self._token is None or time.time() >= self._token_expires - 30:
            self._token = self._generate_token()
        return self._token

    def _headers(self) -> dict[str, str]:
        """Get headers for API requests."""
        return {
            "Authorization": f"Ghost {self._get_token()}",
            "Content-Type": "application/json",
        }

    def _api_url(self, endpoint: str) -> str:
        """Build full API URL."""
        return f"{self.base_url}/ghost/api/admin/{endpoint}"

    def get_post_by_slug(self, slug: str) -> Optional[dict[str, Any]]:
        """Fetch a post by its slug.

        Returns None if post doesn't exist.
        """
        url = self._api_url(f"posts/slug/{slug}/")
        try:
            response = requests.get(url, headers=self._headers(), timeout=30)
            if response.status_code == 404:
                return None
            response.raise_for_status()
            data = response.json()
            return data.get("posts", [None])[0]
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                return None
            logger.error(f"Failed to fetch post by slug {slug}: {e}")
            raise

    def create_post(
        self,
        post: Post,
        newsletter_slug: Optional[str] = None,
        email_segment: Optional[str] = None,
    ) -> dict[str, Any]:
        """Create a new post.

        Args:
            post: Post data
            newsletter_slug: If provided, send as newsletter
            email_segment: Email segment filter (e.g., "status:free")

        Returns:
            Created post data from Ghost API
        """
        url = self._api_url("posts/")

        post_data: dict[str, Any] = {
            "title": post.title,
            "slug": post.slug,
            "html": post.html,
            "status": post.status,
        }

        if post.feature_image:
            post_data["feature_image"] = post.feature_image
        if post.tags:
            post_data["tags"] = [{"name": tag} for tag in post.tags]
        if post.excerpt:
            post_data["excerpt"] = post.excerpt

        # Newsletter parameters (only for article 1)
        params = {}
        if newsletter_slug:
            params["newsletter"] = newsletter_slug
            if email_segment:
                params["email_segment"] = email_segment

        logger.info(f"Creating post: {post.title} (slug: {post.slug})")
        if newsletter_slug:
            logger.info(f"  -> Will send newsletter: {newsletter_slug}")

        response = requests.post(
            url,
            headers=self._headers(),
            json={"posts": [post_data]},
            params=params if params else None,
            timeout=60,
        )
        response.raise_for_status()

        created = response.json()["posts"][0]
        logger.info(f"Created post ID: {created['id']}")
        return created

    def update_post(
        self,
        post_id: str,
        post: Post,
        updated_at: str,
        newsletter_slug: Optional[str] = None,
        email_segment: Optional[str] = None,
    ) -> dict[str, Any]:
        """Update an existing post.

        Args:
            post_id: Ghost post ID
            post: Updated post data
            updated_at: Current updated_at value (for optimistic locking)
            newsletter_slug: If provided, send as newsletter
            email_segment: Email segment filter

        Returns:
            Updated post data from Ghost API
        """
        url = self._api_url(f"posts/{post_id}/")

        post_data: dict[str, Any] = {
            "title": post.title,
            "slug": post.slug,
            "html": post.html,
            "status": post.status,
            "updated_at": updated_at,
        }

        if post.feature_image:
            post_data["feature_image"] = post.feature_image
        if post.tags:
            post_data["tags"] = [{"name": tag} for tag in post.tags]
        if post.excerpt:
            post_data["excerpt"] = post.excerpt

        params = {}
        if newsletter_slug:
            params["newsletter"] = newsletter_slug
            if email_segment:
                params["email_segment"] = email_segment

        logger.info(f"Updating post: {post.title} (id: {post_id})")

        response = requests.put(
            url,
            headers=self._headers(),
            json={"posts": [post_data]},
            params=params if params else None,
            timeout=60,
        )
        response.raise_for_status()

        updated = response.json()["posts"][0]
        logger.info(f"Updated post ID: {updated['id']}")
        return updated

    def publish_post_idempotent(
        self,
        post: Post,
        send_newsletter: bool = False,
    ) -> dict[str, Any]:
        """Publish a post idempotently.

        If a post with the same slug exists, update it.
        Otherwise, create a new post.

        Args:
            post: Post to publish
            send_newsletter: If True, send as newsletter (only for article 1)

        Returns:
            Published post data
        """
        newsletter_slug = None
        email_segment = None

        if send_newsletter:
            newsletter_slug = self.config.newsletter_slug
            email_segment = self.config.email_segment

        # Check if post exists
        existing = self.get_post_by_slug(post.slug)

        if existing:
            # Update existing post
            logger.info(f"Post already exists, updating: {post.slug}")

            # Check if already sent as newsletter
            if existing.get("email"):
                logger.warning(
                    f"Post {post.slug} was already sent as newsletter. "
                    "Skipping newsletter to avoid duplicate email."
                )
                newsletter_slug = None
                email_segment = None

            return self.update_post(
                post_id=existing["id"],
                post=post,
                updated_at=existing["updated_at"],
                newsletter_slug=newsletter_slug,
                email_segment=email_segment,
            )
        else:
            # Create new post
            return self.create_post(
                post=post,
                newsletter_slug=newsletter_slug,
                email_segment=email_segment,
            )

    def upload_image(self, image_path: str) -> str:
        """Upload an image to Ghost.

        Args:
            image_path: Local path to image file

        Returns:
            URL of uploaded image
        """
        url = self._api_url("images/upload/")

        with open(image_path, "rb") as f:
            files = {"file": (image_path.split("/")[-1], f, "image/png")}
            # Note: Don't use JSON content-type for file uploads
            headers = {"Authorization": f"Ghost {self._get_token()}"}

            response = requests.post(url, headers=headers, files=files, timeout=60)
            response.raise_for_status()

        result = response.json()
        image_url = result["images"][0]["url"]
        logger.info(f"Uploaded image: {image_url}")
        return image_url
