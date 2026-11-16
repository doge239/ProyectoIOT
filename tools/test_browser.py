"""Prueba funcional contra el servidor local, con credenciales de backend/.env.

Uso: .venv/Scripts/python.exe tools/test_browser.py http://127.0.0.1:8081
Restaura los metadatos editados al terminar. Envía lecturas de prueba que vencen
según el tiempo sin datos configurado; no ejecutar contra producción.
"""
import json
from pathlib import Path
import re
import sys

from dotenv import dotenv_values
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8081"
if not BASE.startswith(("http://127.0.0.1:", "http://localhost:")):
    raise SystemExit("Esta prueba está limitada al servidor local.")
credentials = (ROOT / '.local/credenciales.txt').read_text(encoding='utf-8')
password = re.search(r'Contraseña: (.+)', credentials)[1]
device_key = next(iter(json.loads(dotenv_values(ROOT / 'backend/.env')['DEVICE_KEYS'])))
out = ROOT / '.local/screenshots'
out.mkdir(parents=True, exist_ok=True)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 1100})
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.goto(BASE)
    page.wait_for_load_state('networkidle')
    expect(page.get_by_role('heading', name='Bienvenido de vuelta')).to_be_visible()
    page.screenshot(path=str(out / 'login-desktop.png'), full_page=True)
    page.get_by_label('Contraseña', exact=True).fill(password)
    page.get_by_role('button', name='Ingresar al panel').click()
    expect(page.get_by_role('heading', name='Vista general', exact=True)).to_be_visible()
    expect(page.locator('.parking-slot')).to_have_count(4)
    token = page.evaluate("sessionStorage.getItem('parking-session')")
    admin = {"Authorization": "Bearer " + token}
    original = page.request.get(BASE + '/api/puestos', headers=admin).json()
    try:
        readings = {f'A{i}': {"ocupado": i in (1, 3), "adc": 3000 if i in (1, 3) else 500} for i in range(1, 5)}
        assert page.request.post(BASE + '/api/telemetria', data=readings, headers={"X-Device-Key": device_key}).status == 204
        expect(page.locator('.parking-slot[data-state="ocupado"]')).to_have_count(2)
        expect(page.locator('.parking-slot[data-state="libre"]')).to_have_count(2)
        page.screenshot(path=str(out / 'dashboard-desktop.png'), full_page=True)

        page.get_by_role('button', name='Editar A2, Libre', exact=True).click()
        page.get_by_label('Nombre visible').fill('Acceso de servicio')
        page.get_by_label('Puesto habilitado').uncheck()
        page.get_by_label('Motivo de desactivación').fill('Mantenimiento de prueba')
        page.get_by_role('button', name='Guardar cambios', exact=True).click()
        expect(page.get_by_role('dialog')).to_have_count(0)
        assert page.request.post(BASE + '/api/telemetria', data={"A2": {"ocupado": False, "adc": 200}}, headers={"X-Device-Key": device_key}).status == 204
        expect(page.get_by_role('button', name='Editar Acceso de servicio, Deshabilitado')).to_be_visible()
        page.reload()
        expect(page.get_by_role('button', name='Editar Acceso de servicio, Deshabilitado')).to_be_visible()

        page.get_by_role('button', name='Puestos', exact=True).click()
        page.get_by_role('textbox', name='Buscar puesto').fill('Acceso de servicio')
        expect(page.locator('.management-card')).to_have_count(1)
        page.get_by_role('combobox', name='Filtrar por estado').select_option('libre')
        expect(page.get_by_role('heading', name='No hay coincidencias')).to_be_visible()
        page.get_by_role('combobox', name='Filtrar por estado').select_option('todos')
        page.get_by_role('textbox', name='Buscar puesto').fill('')
        page.set_viewport_size({"width": 390, "height": 844})
        page.screenshot(path=str(out / 'puestos-mobile.png'), full_page=True)
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), 'Desbordamiento móvil'
        page.get_by_role('button', name='Editar A2', exact=True).click()
        expect(page.get_by_role('dialog')).to_be_visible()
        page.get_by_label('Puesto habilitado').check()
        page.get_by_role('button', name='Guardar cambios', exact=True).click()
        expect(page.get_by_role('dialog')).to_have_count(0)

        page.get_by_role('button', name='Configuración', exact=True).click()
        page.get_by_label('Nombre del estacionamiento').fill('Campus de prueba')
        page.get_by_label('Tiempo para marcar').fill('7')
        page.get_by_role('button', name='Guardar configuración', exact=True).click()
        expect(page.locator('.topbar')).to_contain_text('Campus de prueba')
        expect(page.locator('.alert.success')).to_contain_text('Configuración guardada.')
        page.get_by_role('button', name='Vista general', exact=True).click()
        page.screenshot(path=str(out / 'dashboard-mobile.png'), full_page=True)
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), 'Desbordamiento móvil'

        page.route('**/api/puestos**', lambda route: route.abort())
        page.evaluate("document.dispatchEvent(new Event('visibilitychange'))")
        expect(page.get_by_text('Reconectando…', exact=True)).to_be_visible(timeout=15000)
        expect(page.locator('.parking-slot[data-state="libre"]')).to_have_count(0)
        page.unroute('**/api/puestos**')
        expect(page.get_by_text('Servidor conectado', exact=True)).to_be_visible(timeout=15000)
    finally:
        for slot_id, slot in original['puestos'].items():
            body = {key: slot[key] for key in ['nombre', 'sector', 'notas', 'habilitado', 'motivo_desactivacion']}
            assert page.request.put(BASE + '/api/puestos/' + slot_id, data=body, headers=admin).status == 200
        assert page.request.put(BASE + '/api/configuracion', data=original['configuracion'], headers=admin).status == 200
    page.get_by_role('button', name='Cerrar sesión').click()
    expect(page.get_by_role('heading', name='Bienvenido de vuelta')).to_be_visible()
    assert page.request.get(BASE + '/api/puestos', headers=admin).status == 401
    page.screenshot(path=str(out / 'login-mobile.png'), full_page=True)
    browser.close()
    assert not errors, errors
print('OK: login, lecturas, edición, desactivación, persistencia, filtros, configuración, móvil, desconexión y logout.')
