import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.ai.llm_client import verify_api_key
from backend.core.encryption import decrypt_text, encrypt_text
from backend.modules.llm_keys.models import UserLlmKey


async def set_user_llm_key(db: AsyncSession, *, user_id: uuid.UUID, api_key: str) -> UserLlmKey:
    """Test the key against Gemini, then store it. A key that fails is never saved,
    so an existing working key is not replaced by a broken one.
    """
    await verify_api_key(api_key)

    result = await db.execute(select(UserLlmKey).where(UserLlmKey.user_id == user_id))
    row = result.scalar_one_or_none()
    encrypted = encrypt_text(api_key)

    if row is None:
        row = UserLlmKey(user_id=user_id, encrypted_key=encrypted)
        db.add(row)
    else:
        row.encrypted_key = encrypted

    await db.flush()
    return row


async def get_user_llm_key(db: AsyncSession, *, user_id: uuid.UUID) -> UserLlmKey | None:
    result = await db.execute(select(UserLlmKey).where(UserLlmKey.user_id == user_id))
    return result.scalar_one_or_none()


async def get_decrypted_user_llm_key(db: AsyncSession, *, user_id: uuid.UUID) -> str | None:
    row = await get_user_llm_key(db, user_id=user_id)
    return decrypt_text(row.encrypted_key) if row else None


async def delete_user_llm_key(db: AsyncSession, *, user_id: uuid.UUID) -> None:
    row = await get_user_llm_key(db, user_id=user_id)
    if row is not None:
        await db.delete(row)
