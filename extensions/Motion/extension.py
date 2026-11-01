from fastapi import APIRouter


app = APIRouter()


@app.get("/version")
async def version():
    return {"name": "Motion", "version": "0.1.0"}
