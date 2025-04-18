import argparse
import uvicorn
from server.server import app

def main():
    # parser = argparse.ArgumentParser()
    # parser.add_argument("--dev", action="store_true", help="Enable development mode with auto-reload")
    # args = parser.parse_args()
    uvicorn.run(app, host="127.0.0.1", port=7422, reload=False)

if __name__ == "__main__":
    main()
