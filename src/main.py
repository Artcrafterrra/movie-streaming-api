from fastapi import FastAPI


app = FastAPI(
    title="Movies Api",
    description="Description of project"
)

api_version_prefix = "/api/v1"
