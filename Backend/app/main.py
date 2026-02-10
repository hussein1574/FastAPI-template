from fastapi import FastAPI
from app.core.config import get_settings
from app.api.api_v1 import user_router, auth_router
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.core.exceptions import AppException
import logging
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from contextlib import asynccontextmanager
from app.tasks.cleanup_tokens import cleanup_expired_tokens


settings = get_settings()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup code
    logging.info(f"Starting up the {settings.PROJECT_NAME} API...")
    import asyncio
    async def periodic_cleanup():
        while True:
            await asyncio.sleep(86400) # every 24 hours
            await cleanup_expired_tokens()
    task = asyncio.create_task(periodic_cleanup())
    yield
    # Shutdown code
    task.cancel()
    logging.info(f"Shutting down the {settings.PROJECT_NAME} API...")


app = FastAPI(lifespan=lifespan, title=f"{settings.PROJECT_NAME} API", version="1.0.0")

# CORS setup

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.ALLOWED_ORIGINS],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# Rate Limiting setup
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Include API routers
app.include_router(user_router, prefix="/api/v1/users", tags=["Users"])
app.include_router(auth_router, prefix="/api/v1/auth", tags=["Authentication"])

# Global exception handler
@app.exception_handler(AppException)
async def app_exception_handler(request, exc: AppException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail}
    )

# Logger setup
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")



@app.get("/")
def read_root():
    return {"status": "Green", "message": f"The {settings.PROJECT_NAME} Workspace is alive!"}