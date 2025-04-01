import ssui_image

@app.get("/extension/example/version")
async def version():
    return "0.0.1"
