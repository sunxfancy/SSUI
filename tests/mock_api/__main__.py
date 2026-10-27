import os

import uvicorn


if __name__ == "__main__":
    uvicorn.run(
        "tests.mock_api.app:app",
        host=os.environ.get("SSUI_MOCK_HOST", "127.0.0.1"),
        port=int(os.environ.get("SSUI_MOCK_PORT", "7422")),
        log_level="info",
    )
