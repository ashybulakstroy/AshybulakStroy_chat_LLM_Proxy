try:
    import uvicorn
except ModuleNotFoundError as exc:
    raise SystemExit(
        "uvicorn is not installed in the current Python interpreter.\n"
        "Use the project virtual environment:\n"
        "  .\\venv\\Scripts\\python.exe run.py\n"
        "or start with:\n"
        "  .\\start_server.ps1"
    ) from exc

from app.config import settings


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=settings.PORT,
        reload=True,
    )
