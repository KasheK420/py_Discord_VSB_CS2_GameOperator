import uvicorn
from utils.config import settings

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.HTTP_HOST,
        port=settings.HTTP_PORT,
        reload=False,
        log_level=settings.LOG_LEVEL.lower(),
        proxy_headers=True
    )
