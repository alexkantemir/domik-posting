import json
import logging
from datetime import datetime, timezone

from app.database import SessionLocal
from app.models import ContentItem, GeneratedPost, Publication
from app.services.publishers.registry import get_publisher

logger = logging.getLogger(__name__)


def publish_scheduled_posts() -> None:
    """Called every minute. Publishes approved posts whose scheduled_at has passed."""
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        posts = (
            db.query(GeneratedPost)
            .filter(
                GeneratedPost.status == "approved",
                GeneratedPost.scheduled_at <= now,
            )
            .with_for_update(skip_locked=True)
            .all()
        )

        if not posts:
            return

        logger.info("Scheduler: %d post(s) ready to publish", len(posts))

        for post in posts:
            item: ContentItem = post.content_item
            file_paths = json.loads(item.file_paths or "[]")
            image_path = file_paths[0] if file_paths else None

            publisher = get_publisher(post.platform)
            if not publisher or not publisher.is_configured():
                logger.warning("Scheduler: no publisher for %s, skipping post %d", post.platform, post.id)
                continue

            try:
                result = publisher.publish(post.text or "", image_path=image_path)
                pub = Publication(
                    generated_post_id=post.id,
                    platform=post.platform,
                    published_at=datetime.now(timezone.utc).replace(tzinfo=None) if result.success else None,
                    platform_post_id=result.platform_post_id,
                    post_url=result.post_url,
                    success=result.success,
                    error_message=result.error_message,
                )
                db.add(pub)
                post.status = "published" if result.success else "failed"
                db.commit()
                logger.info(
                    "Scheduler: post %d → %s success=%s url=%s",
                    post.id, post.platform, result.success, result.post_url,
                )
            except Exception:
                logger.exception("Scheduler: unhandled error publishing post %d", post.id)
                post.status = "failed"
                db.commit()
    finally:
        db.close()
