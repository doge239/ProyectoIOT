from datetime import timedelta
from types import SimpleNamespace
import os
import uuid
import asyncio
import json
import httpx

from fastapi.testclient import TestClient
from pwdlib import PasswordHash
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from backend.database import AdminSession, Slot
from backend.main import create_app, fingerprint, utcnow

DEVICE_KEY = "test-device-key-with-at-least-24-chars"
SECOND_KEY = "second-device-key-with-at-least-24-chars"
PASSWORD = "test-password-never-use-in-production"


@pytest.fixture(scope="session")
def password_hash():
    return PasswordHash.recommended().hash(PASSWORD)


@pytest.fixture(params=["sqlite", "postgres"] if os.getenv("TEST_DATABASE_URL") else ["sqlite"])
def setup(tmp_path, password_hash, request):
    url = f"sqlite:///{tmp_path / 'test.db'}"
    engine, schema = None, None
    if request.param == "postgres":
        target = make_url(os.environ['TEST_DATABASE_URL'])
        if target.host not in ('127.0.0.1', 'localhost') or target.database != 'parking_iot_test':
            raise RuntimeError('Las pruebas PostgreSQL requieren la base local parking_iot_test.')
        engine = create_engine(target)
        schema = 'test_' + uuid.uuid4().hex
        with engine.begin() as db:
            db.execute(text(f'CREATE SCHEMA "{schema}"'))
        url = target.update_query_dict({'options': f'-csearch_path={schema}'}).render_as_string(hide_password=False)
    settings = SimpleNamespace(production=False, database_url=url,
                           admin_username="admin", admin_password_hash=password_hash,
                           device_keys={DEVICE_KEY: ["A1", "A2", "A3", "A4"], SECOND_KEY: ["A2"]},
                           allow_anonymous=False, session_hours=8,
                           origins=["https://frontend.example", "https://localhost"])
    yield settings
    if engine:
        with engine.begin() as db:
            db.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        engine.dispose()


@pytest.fixture
def client(setup):
    with TestClient(create_app(setup)) as client:
        yield client


@pytest.fixture
def admin(client):
    response = client.post('/api/auth/login', json={"username": "admin", "password": PASSWORD})
    assert response.status_code == 200
    return {"Authorization": "Bearer " + response.json()["token"]}


def reading(occupied=True):
    return {"A1": {"ocupado": occupied, "adc": 3000 if occupied else 500}}


def slot_edit(**updates):
    return {"nombre": "Acceso principal", "sector": "Sector norte", "notas": "Cerca del acceso",
            "habilitado": False, "motivo_desactivacion": "Mantenimiento", **updates}


def test_admin_and_device_permissions_are_separate(client, admin):
    assert client.get('/api/puestos').status_code == 401
    assert client.post('/api/telemetria', json=reading(), headers=admin).status_code == 401
    assert client.get('/api/puestos', headers={"X-Device-Key": DEVICE_KEY}).status_code == 401
    assert client.put('/api/puestos/A1', json=slot_edit(), headers={"X-Device-Key": DEVICE_KEY}).status_code == 401
    assert client.post('/api/auth/login', json={"username": "otro", "password": PASSWORD}).status_code == 401


def test_disabled_slot_cannot_be_reenabled_by_sensor(client, admin):
    device = {"X-Device-Key": DEVICE_KEY}
    assert client.post('/api/telemetria', json=reading(), headers=device).status_code == 204
    assert client.get('/api/puestos', headers=admin).json()['puestos']['A1']['estado'] == 'ocupado'
    assert client.put('/api/puestos/A1', json=slot_edit(), headers=admin).status_code == 200
    assert client.post('/api/telemetria', json=reading(False), headers=device).status_code == 204
    state = client.get('/api/puestos', headers=admin).json()['puestos']['A1']
    assert state['estado'] == 'deshabilitado'
    assert state['estado_sensor'] == 'libre'
    assert state['nombre'] == 'Acceso principal'
    assert state['motivo_desactivacion'] == 'Mantenimiento'
    assert client.put('/api/puestos/A1', json=slot_edit(habilitado=True), headers=admin).json()['estado'] == 'libre'


def test_stale_sensor_and_expired_session(client, admin):
    client.post('/api/telemetria', json=reading(), headers={"X-Device-Key": DEVICE_KEY})
    with client.app.state.sessions.begin() as db:
        db.get(Slot, 'A1').received_at = utcnow() - timedelta(seconds=6)
    slot = client.get('/api/puestos', headers=admin).json()['puestos']['A1']
    assert slot['estado'] == 'sin_datos' and slot['adc'] is None
    with client.app.state.sessions.begin() as db:
        db.get(AdminSession, fingerprint(admin['Authorization'][7:])).expires_at = utcnow() - timedelta(seconds=1)
    assert client.get('/api/puestos', headers=admin).status_code == 401


def test_telemetry_validation_and_assigned_slots(client):
    device = {"X-Device-Key": DEVICE_KEY}
    for payload in [reading() | {"A5": {"ocupado": True, "adc": 3}}, {}, {"A1": {"ocupado": True, "adc": 3, "habilitado": True}}, {"A1": {"ocupado": 1, "adc": 3}}, {"A1": {"ocupado": False, "adc": 4096}}]:
        assert client.post('/api/telemetria', json=payload, headers=device).status_code in (403, 422)
    assert client.post('/api/telemetria', json=reading(), headers={"X-Device-Key": SECOND_KEY}).status_code == 403
    assert client.post('/api/telemetria', json={"A2": {"ocupado": False, "adc": 10}}, headers={"X-Device-Key": SECOND_KEY}).status_code == 204
    assert client.post('/api/telemetria', content='x' * 17000).status_code == 413


def test_edits_persist_after_restart(setup):
    with TestClient(create_app(setup)) as client:
        token = client.post('/api/auth/login', json={"username": "admin", "password": PASSWORD}).json()['token']
        headers = {"Authorization": "Bearer " + token}
        client.put('/api/puestos/A1', json=slot_edit(), headers=headers)
        client.put('/api/configuracion', json={"nombre": "Campus norte", "segundos_sin_datos": 12}, headers=headers)
    with TestClient(create_app(setup)) as client:
        state = client.get('/api/puestos', headers=headers).json()
        assert state['puestos']['A1']['nombre'] == 'Acceso principal'
        assert state['puestos']['A1']['estado'] == 'deshabilitado'
        assert state['configuracion'] == {"nombre": "Campus norte", "segundos_sin_datos": 12}
        assert client.post('/api/auth/logout', headers=headers).status_code == 204
        assert client.get('/api/puestos', headers=headers).status_code == 401


def test_no_manual_occupancy_override(client, admin):
    assert client.put('/api/puestos/A1', json=slot_edit(ocupado=True), headers=admin).status_code == 422
    assert client.put('/api/puestos/A1', json=slot_edit(motivo_desactivacion=' '), headers=admin).status_code == 422
    assert client.put('/api/puestos/A1', json=slot_edit(nombre=' '), headers=admin).status_code == 422
    assert client.put('/api/configuracion', json={"nombre": "Campus", "segundos_sin_datos": 1}, headers=admin).status_code == 422


def test_cors_and_health(client):
    response = client.options('/api/puestos', headers={"Origin": "https://frontend.example", "Access-Control-Request-Method": "GET", "Access-Control-Request-Headers": "authorization"})
    assert response.status_code == 200
    assert response.headers['access-control-allow-origin'] == 'https://frontend.example'
    assert client.get('/api/health').json() == {"status": "ok"}


def test_login_rate_limit(client):
    for _ in range(10):
        assert client.post('/api/auth/login', json={"username": "admin", "password": "incorrecta"}).status_code == 401
    assert client.post('/api/auth/login', json={"username": "admin", "password": PASSWORD}).status_code == 429


def test_stream_requires_admin(client):
    assert client.get('/api/puestos/stream').status_code == 401
    assert client.get('/api/puestos/stream', headers={"X-Device-Key": DEVICE_KEY}).status_code == 401


def test_stream_pushes_changes_and_revokes_session(setup):
    async def check():
        app = create_app(setup)
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url='http://test') as client:
                token = (await client.post('/api/auth/login', json={"username": "admin", "password": PASSWORD})).json()['token']
                headers = {"Authorization": "Bearer " + token}
                endpoint = next(route.endpoint for route in app.routes if getattr(route, 'path', '') == '/api/puestos/stream')

                async def disconnected():
                    return False

                response = await endpoint(SimpleNamespace(is_disconnected=disconnected), headers['Authorization'])
                iterator = response.body_iterator

                async def next_message():
                    while True:
                        chunk = await anext(iterator)
                        if chunk.strip():
                            return json.loads(chunk)

                try:
                    assert len((await next_message())['puestos']) == 4
                    assert (await client.post('/api/telemetria', json=reading(), headers={"X-Device-Key": DEVICE_KEY})).status_code == 204
                    # The notification must wake the stream before its 1s timer.
                    update = await asyncio.wait_for(next_message(), timeout=0.9)
                    assert update['puestos']['A1']['estado'] == 'ocupado'
                    await client.put('/api/puestos/A1', json=slot_edit(), headers=headers)
                    update = await asyncio.wait_for(next_message(), timeout=0.9)
                    assert update['puestos']['A1']['estado'] == 'deshabilitado'
                    await client.post('/api/auth/logout', headers=headers)
                    assert (await asyncio.wait_for(next_message(), timeout=0.9))['error'] == 'session_expired'
                finally:
                    await iterator.aclose()
    asyncio.run(check())
