from celery import shared_task
from datetime import datetime, timezone
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError

from config.settings import base_app_settings as settings
from database.models.accounts import (
    ActivationTokenModel,
    PasswordResetTokenModel,
)

import asyncio


engine = create_async_engine(settings.DATABASE_URL, echo=False)

AsyncSessionLocal: sessionmaker[AsyncSession] = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)

print("✅ OK AsyncSessionLocal!!!!!!!!", AsyncSessionLocal)


@shared_task
def delete_expired_tokens():
    async def _delete():
        now = datetime.now(timezone.utc)
        print(
            f"[Celery] 🧹 Starting expired token cleanup at {now.isoformat()}"
        )

        async with AsyncSessionLocal() as session:
            try:
                result_activation = await session.execute(
                    delete(ActivationTokenModel).where(
                        ActivationTokenModel.expires_at < now
                    )
                )

                result_reset = await session.execute(
                    delete(PasswordResetTokenModel).where(
                        PasswordResetTokenModel.expires_at < now
                    )
                )

                await session.commit()

                print(
                    f"[Celery] ✅ Cleanup complete at {now.isoformat()} | "
                    f"Deleted: {result_activation.rowcount or 0} activation tokens, "
                    f"{result_reset.rowcount or 0} reset tokens."
                )

            except SQLAlchemyError as db_error:
                await session.rollback()
                print(
                    f"[Celery] ❌ Database error during cleanup: {type(db_error).__name__} - {db_error}"
                )

            except Exception as e:
                await session.rollback()
                print(f"[Celery] ⚠️ Unexpected error: {type(e).__name__} - {e}")

            finally:
                await session.close()
                print("[Celery] 🔒 Database session closed after cleanup.")

    asyncio.run(_delete())
