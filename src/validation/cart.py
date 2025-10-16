from database.models.cart import Cart, CartItem
from fastapi.exceptions import RequestValidationError
from database.models.accounts import UserModel, UserProfileModel
from database.models.movies import Movie
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends, HTTPException
from database import get_db
from datetime import date


def cart_movie_validator(cart: Cart, cart_item: CartItem):
    if cart_item in cart.items:
        raise RequestValidationError("Movie in already in cart")


async def check_purchased_movies(cart: Cart, cart_item: CartItem, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(UserModel).where(UserModel.id == cart.user_id))
    user = result.scalars().first()
    for movie in user.bought_movies:
        if cart_item.movie == movie:
            raise HTTPException(status_code=400, detail="Movie is already purchased")


def check_empty_cart(cart: Cart):
    if not cart.items:
        raise HTTPException(status_code=404, detail="Cart is empty")


async def check_movie_certification(cart: Cart, cart_item: CartItem, db: AsyncSession = Depends(get_db)):
    restrictions = {"G": 0, "PG": 10, "PG-13": 13, "R": 17, "NC-17": 18}
    movie_query = await db.execute(select(Movie).where(Movie.id == cart_item.movie_id))
    certification = movie_query.scalars().first().certification.value
    user_query =await db.execute(select(UserModel).where(UserModel.id == cart.user_id))
    user = user_query.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user_profile_query = await db.execute(select(UserProfileModel).where(UserProfileModel.user_id == user.id))
    user_profile = user_profile_query.scalars().first()
    user_age = date.today().year - user_profile.date_of_birth.year
    if user_age < restrictions[certification]:
        raise HTTPException(status_code=403, detail="User's age is not suitable for watching current movie")
