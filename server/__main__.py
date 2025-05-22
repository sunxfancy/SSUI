import argparse
import uvicorn
import os
from server.server import app

def main():
    os.environ["HF_HUB_ENABLE_HF_TRANSFER"] = "1"

    # parser = argparse.ArgumentParser()
    # parser.add_argument("--dev", action="store_true", help="Enable development mode with auto-reload")
    # args = parser.parse_args()
    uvicorn.run(app, host="localhost", port=7422, reload=False)

if __name__ == "__main__":
    main()
