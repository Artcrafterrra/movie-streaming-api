from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from database import get_db, UserModel
from database.models import UserProfileModel
from routes.accounts import get_current_user
from schemas.profiles import UserProfileResponseSchema, UserProfileRequestSchema

router = APIRouter(prefix="/users", tags=["Profiles"])


@router.get("/profile/", response_model=UserProfileResponseSchema)
async def get_profile(user: UserModel = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(UserProfileModel).where(UserProfileModel.user_id == user.id))
    user_profile = result.scalar_one_or_none()
    if not user_profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User profile not found."
        )

    return UserProfileResponseSchema(
        id=user_profile.id,
        first_name=user_profile.first_name,
        last_name=user_profile.last_name,
        avatar=user_profile.avatar,
        gender=user_profile.gender,
        date_of_birth=user_profile.date_of_birth,
        info=user_profile.info,
        user_id=user_profile.user_id
    )


@router.patch("/profile/{user_id}/", response_model=UserProfileResponseSchema)
async def patch_profile(
    user_id: int,
    profile_data: UserProfileRequestSchema,
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    if current_user.id !=user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can't change others profiles."
        )

    result = await db.execute(select(UserProfileModel).where(UserProfileModel.user_id == user_id))
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found."
        )

    for field, value in profile_data.model_dump(exclude_unset=True).items():
        setattr(profile, field, value)

    db.add(profile)
    await db.commit()
    await db.refresh(profile)

    return UserProfileResponseSchema.model_validate(profile)
