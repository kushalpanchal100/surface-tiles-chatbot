import sys
from pathlib import Path

# Ensure project root is on sys.path
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import uvicorn
from api.app import app
from config.settings import settings

if __name__ == "__main__":
    print(f"🚀 Starting Surfaces Tiles UK API on http://{settings.host}:{settings.port}")
    print(f"📖 Swagger documentation: http://localhost:{settings.port}/docs")
    uvicorn.run(
        "api.app:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug
    )
