"""Inicia la API y el dashboard Angular compilado: python servidor.py."""
import os
from pathlib import Path
from dotenv import load_dotenv
import uvicorn

if __name__ == "__main__":
    load_dotenv(Path(__file__).resolve().parent / "backend" / ".env")
    uvicorn.run("backend.main:create_app", factory=True,
                host=os.getenv("HOST", "0.0.0.0" if os.getenv("PORT") else "127.0.0.1"),
                port=int(os.getenv("PORT", "8080")))
