from fastapi import FastAPI

from routes import movies

app = FastAPI(title="Movies Api", description="Description of project")

api_version_prefix = "/api/v1"

app.include_router(movies.router, prefix=api_version_prefix)
