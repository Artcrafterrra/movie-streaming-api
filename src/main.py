from fastapi import FastAPI

from routes import movies, accounts
from routes.orders import router as orders_router

app = FastAPI(title="Movies Api", description="Description of project")

api_version_prefix = "/api/v1"

app.include_router(movies.router, prefix=api_version_prefix)
app.include_router(accounts.router, prefix=api_version_prefix)
app.include_router(orders_router)
