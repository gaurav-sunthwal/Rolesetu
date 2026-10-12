import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from backend.modules.profiles import repository
from backend.modules.profiles.models import Profile
from backend.modules.profiles.schemas import ProfileRead, ProfileWrite

_DOCUMENT_FIELDS = ("links", "skills", "experience", "projects", "education")
_SCALAR_FIELDS = ("full_name", "headline", "location", "phone")


def completeness_of(profile: ProfileWrite) -> int:
    """How much of the profile the matcher has to work with, 0-100."""
    score = 0
    if profile.full_name:
        score += 10
    if profile.headline:
        score += 10
    if len(profile.skills) >= 5:
        score += 20
    elif profile.skills:
        score += 10
    if profile.experience:
        score += 25
    if profile.projects:
        score += 15
    if profile.education:
        score += 10
    if any((profile.links.linkedin, profile.links.github, profile.links.portfolio)):
        score += 10
    return score


def to_read(profile: Profile | None) -> ProfileRead:
    if profile is None:
        empty = ProfileWrite()
        return ProfileRead(**empty.model_dump(), version=0, completeness=0, updated_at=None)
    data = ProfileWrite.model_validate(
        {field: getattr(profile, field) for field in (*_SCALAR_FIELDS, *_DOCUMENT_FIELDS)}
    )
    return ProfileRead(
        **data.model_dump(),
        version=profile.version,
        completeness=completeness_of(data),
        updated_at=profile.updated_at,
    )


async def get_profile(db: AsyncSession, *, user_id: uuid.UUID) -> ProfileRead:
    return to_read(await repository.get_by_user(db, user_id))


async def save_profile(
    db: AsyncSession, *, user_id: uuid.UUID, payload: ProfileWrite
) -> ProfileRead:
    incoming = payload.model_dump(mode="json")
    profile = await repository.get_for_update(db, user_id)

    if profile is None:
        profile = Profile(user_id=user_id, version=1, **incoming)
        repository.add(db, profile)
    else:
        changed = any(getattr(profile, field) != value for field, value in incoming.items())
        if changed:
            for field, value in incoming.items():
                setattr(profile, field, value)
            profile.version += 1

    await db.flush()
    await db.refresh(profile)
    return to_read(profile)
