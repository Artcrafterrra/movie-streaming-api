from database.models.cart import Cart, CartItem
from fastapi.exceptions import RequestValidationError


def cart_movie_validator(cart: Cart, cart_item: CartItem):
    if cart_item in cart.items:
        raise RequestValidationError("Movie in already in cart")


def check_purchased_movies(cart: Cart, cart_item: CartItem):
    pass


def check_movie_certification(cart: Cart, cart_item: CartItem):
    pass
