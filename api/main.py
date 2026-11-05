import uvicorn

from src.app import app
from src.core.config import settings

if __name__ == "__main__":
    # log_config=None keeps Uvicorn from replacing the loggin set up in src/app.py.
    uvicorn.run(app, host=settings.api_host, port=settings.api_port, log_config=None)
