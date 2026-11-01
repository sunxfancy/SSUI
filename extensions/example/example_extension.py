from fastapi import APIRouter

app = APIRouter()

@app.get("/version")
async def version():
    return "0.0.1"
