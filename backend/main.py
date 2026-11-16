from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import secrets
import time
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt
from pwdlib import PasswordHash
from sqlalchemy import delete, select, text, update
from sqlalchemy.orm import Session

from .config import ROOT, Settings
from .database import AdminSession, Base, LoginLimit, SiteSettings, Slot, open_database


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def fingerprint(value):
    return hashlib.sha256(value.encode()).hexdigest()


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Login(Input):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=256)
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)


class SlotEdit(Input):
    nombre: str = Field(min_length=1, max_length=60)
    sector: str = Field(min_length=1, max_length=60)
    notas: str = Field(max_length=1000)
    habilitado: StrictBool
    motivo_desactivacion: str = Field(max_length=240)


class SettingsEdit(Input):
    nombre: str = Field(min_length=1, max_length=80)
    segundos_sin_datos: int = Field(strict=True, ge=3, le=300)


class Reading(Input):
    ocupado: StrictBool
    adc: Annotated[StrictInt, Field(ge=0, le=4095)]


def create_app(settings=None):
    config = settings or Settings()
    hasher = PasswordHash.recommended()
    try:
        hasher.verify("configuration-check", config.admin_password_hash)
    except Exception as exc:
        raise RuntimeError("ADMIN_PASSWORD_HASH no es un hash Argon2 válido.") from exc
    engine, sessions = open_database(config.database_url)

    @asynccontextmanager
    async def lifespan(app):
        Base.metadata.create_all(engine)
        with sessions.begin() as db:
            for number in range(1, 5):
                slot_id = f"A{number}"
                if db.get(Slot, slot_id) is None:
                    db.add(Slot(id=slot_id, name=slot_id))
            if db.get(SiteSettings, 1) is None:
                db.add(SiteSettings(id=1))
            if db.get(LoginLimit, "admin") is None:
                db.add(LoginLimit(key="admin", attempts=0, window_start=time.time()))
        yield
        engine.dispose()

    app = FastAPI(title="Estacionamiento IoT", version="1.0.0", lifespan=lifespan,
                  docs_url=None if config.production else "/docs", redoc_url=None)
    app.state.sessions = sessions
    app.add_middleware(CORSMiddleware, allow_origins=config.origins, allow_credentials=False,
                       allow_methods=["GET", "POST", "PUT", "OPTIONS"],
                       allow_headers=["Authorization", "Content-Type", "X-Device-Key"])

    @app.middleware("http")
    async def headers_and_limits(request: Request, call_next):
        length = request.headers.get("content-length")
        if length and (not length.isdigit() or int(length) > 16384):
            return Response(status_code=413)
        if request.method in ("POST", "PUT", "PATCH"):
            body = bytearray()
            async for chunk in request.stream():
                body.extend(chunk)
                if len(body) > 16384:
                    return Response(status_code=413)
            request._body = bytes(body)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["X-Frame-Options"] = "DENY"
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    def database():
        with sessions() as db:
            yield db

    Db = Annotated[Session, Depends(database)]

    def admin(db: Db, authorization: Annotated[str | None, Header()] = None):
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(401, "Inicia sesión como administrador.")
        session = db.get(AdminSession, fingerprint(authorization[7:]))
        if session is None or session.expires_at <= utcnow():
            raise HTTPException(401, "La sesión expiró. Vuelve a ingresar.")
        return session

    Admin = Annotated[AdminSession, Depends(admin)]

    @app.get("/api/health")
    def health(db: Db):
        db.execute(text("SELECT 1"))
        return {"status": "ok"}

    @app.post("/api/auth/login")
    def login(body: Login, db: Db):
        now = time.time()
        db.execute(update(LoginLimit).where(LoginLimit.key == "admin", LoginLimit.window_start <= now - 60)
                   .values(attempts=0, window_start=now))
        changed = db.execute(update(LoginLimit).where(LoginLimit.key == "admin", LoginLimit.attempts < 10)
                             .values(attempts=LoginLimit.attempts + 1)).rowcount
        db.commit()
        if not changed:
            raise HTTPException(429, "Demasiados intentos. Espera un minuto.", headers={"Retry-After": "60"})
        password_ok = hasher.verify(body.password, config.admin_password_hash)
        if not hmac.compare_digest(body.username.encode(), config.admin_username.encode()) or not password_ok:
            raise HTTPException(401, "Usuario o contraseña incorrectos.")
        token = secrets.token_urlsafe(48)
        expiration = utcnow() + timedelta(hours=config.session_hours)
        db.execute(delete(AdminSession).where(AdminSession.expires_at <= utcnow()))
        db.add(AdminSession(token_hash=fingerprint(token), expires_at=expiration))
        db.commit()
        return {"token": token, "usuario": config.admin_username, "expira": expiration.isoformat() + "Z"}

    @app.get("/api/auth/me")
    def me(session: Admin):
        return {"usuario": config.admin_username}

    @app.post("/api/auth/logout", status_code=204)
    def logout(session: Admin, db: Db):
        db.delete(session)
        db.commit()
        return Response(status_code=204)

    def serialized(slot, stale_seconds, now):
        stale = slot.received_at is None or (now - slot.received_at).total_seconds() >= stale_seconds
        sensor_state = "sin_datos" if stale else "ocupado" if slot.occupied else "libre"
        return {"id": slot.id, "nombre": slot.name, "sector": slot.zone, "notas": slot.notes,
                "habilitado": slot.enabled, "motivo_desactivacion": slot.disabled_reason,
                "estado": sensor_state if slot.enabled else "deshabilitado", "estado_sensor": sensor_state,
                "adc": None if stale else slot.adc,
                "ultimo_reporte": slot.received_at.isoformat() + "Z" if slot.received_at else None}

    @app.get("/api/puestos")
    def slots(db: Db, session: Admin):
        site = db.get(SiteSettings, 1)
        now = utcnow()
        entries = {slot.id: serialized(slot, site.stale_seconds, now) for slot in db.scalars(select(Slot).order_by(Slot.id))}
        return {"puestos": entries, "configuracion": {"nombre": site.name, "segundos_sin_datos": site.stale_seconds},
                "hora_servidor": now.isoformat() + "Z"}

    @app.put("/api/puestos/{slot_id}")
    def edit_slot(slot_id: str, body: SlotEdit, db: Db, session: Admin):
        slot = db.get(Slot, slot_id)
        if slot is None:
            raise HTTPException(404, "Puesto no encontrado.")
        if not body.habilitado and not body.motivo_desactivacion:
            raise HTTPException(422, "Indica el motivo para desactivar el puesto.")
        slot.name, slot.zone, slot.notes = body.nombre, body.sector, body.notas
        slot.enabled = body.habilitado
        slot.disabled_reason = "" if body.habilitado else body.motivo_desactivacion
        db.commit()
        return serialized(slot, db.get(SiteSettings, 1).stale_seconds, utcnow())

    @app.put("/api/configuracion")
    def edit_settings(body: SettingsEdit, db: Db, session: Admin):
        site = db.get(SiteSettings, 1)
        site.name, site.stale_seconds = body.nombre, body.segundos_sin_datos
        db.commit()
        return body

    @app.post("/api/telemetria", status_code=204)
    def telemetry(body: dict[str, Reading], db: Db,
                  x_device_key: Annotated[str | None, Header()] = None):
        permitted = None
        if x_device_key:
            for key, assigned in config.device_keys.items():
                if hmac.compare_digest(x_device_key.encode(), key.encode()):
                    permitted = set(assigned)
                    break
        elif config.allow_anonymous and not config.production:
            permitted = {"A1", "A2", "A3", "A4"}
        if permitted is None:
            raise HTTPException(401, "Credencial de sensor inválida.")
        if not body or len(body) > 4 or any(slot_id not in permitted for slot_id in body):
            raise HTTPException(403, "El sensor no tiene permiso para esos puestos.")
        now = utcnow()
        for slot_id, reading in body.items():
            slot = db.get(Slot, slot_id)
            if slot is None:
                raise HTTPException(404, "Puesto no encontrado.")
            slot.occupied, slot.adc, slot.received_at = reading.ocupado, reading.adc, now
        db.commit()
        return Response(status_code=204)

    @app.get("/config.json")
    def frontend_config():
        return {"apiBaseUrl": ""}

    frontend = ROOT / "frontend" / "dist" / "frontend" / "browser"
    if frontend.is_dir():
        app.mount("/", StaticFiles(directory=frontend, html=True), name="frontend")
    else:
        @app.get("/")
        def no_build():
            return {"mensaje": "API lista. Compila frontend/ con npm run build o usa npm start.", "docs": "/docs"}
    return app
