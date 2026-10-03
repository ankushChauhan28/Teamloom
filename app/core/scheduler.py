import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.db.base import AsyncSessionLocal
from app.services.auth_service import (
    cleanup_expired_revocations,
    cleanup_unverified_signups,
)

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


async def run_cleanup_expired_tokens() -> int:
    """
    Background job that creates its own independent AsyncSession
    to clean up expired revoked tokens and logs the number of deleted rows.
    """
    try:
        async with AsyncSessionLocal() as db:
            deleted_count = await cleanup_expired_revocations(db)
            logger.info("Revoked tokens cleanup job executed: %d expired tokens deleted", deleted_count)
            return deleted_count
    except Exception as e:
        logger.error("Error during revoked tokens cleanup job: %s", e, exc_info=True)
        return 0


async def run_cleanup_unverified_signups() -> int:
    """
    Background job that creates its own independent AsyncSession
    to delete unverified signups and empty organizations older than 7 days (X1, B8).
    """
    try:
        async with AsyncSessionLocal() as db:
            deleted_count = await cleanup_unverified_signups(db)
            logger.info(
                "Unverified signups cleanup job executed: %d signups/organizations deleted",
                deleted_count,
            )
            return deleted_count
    except Exception as e:
        logger.error("Error during unverified signups cleanup job: %s", e, exc_info=True)
        return 0


def start_scheduler() -> None:
    """Initializes and starts the background job scheduler."""
    if not scheduler.running:
        scheduler.add_job(
            run_cleanup_expired_tokens,
            "interval",
            hours=24,
            id="cleanup_expired_revoked_tokens",
            replace_existing=True,
        )
        scheduler.add_job(
            run_cleanup_unverified_signups,
            "interval",
            hours=24,
            id="cleanup_unverified_signups",
            replace_existing=True,
        )
        scheduler.start()
        logger.info("APScheduler started successfully (token & signup cleanup intervals).")


def shutdown_scheduler() -> None:
    """Cleanly shuts down the background job scheduler."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("APScheduler stopped successfully.")
