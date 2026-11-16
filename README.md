# Parquea · Estacionamiento IoT

Panel de administración Angular 22, API FastAPI y ESP32/Wokwi para cuatro
puestos. Frontend responsive, preparación para Capacitor 8 y despliegue en
Railway con PostgreSQL. Funciona localmente con SQLite sin instalar una base.

## Qué hace

- Un único administrador inicia sesión; no hay registro de usuarios ni reservas.
- El sensor informa libre/ocupado y ADC. No tiene permisos de administración.
- El administrador edita nombre, sector y notas de los puestos A1–A4.
- Puede desactivar un puesto con un motivo y volver a habilitarlo.
- Los reportes del sensor no pueden reactivar un puesto deshabilitado.
- Sin lecturas recientes, el estado pasa a Sin datos. El tiempo es configurable.
- Cambios, última lectura y sesiones persisten en la base de datos.
- Las claves de los sensores se validan por puesto y se envían en `X-Device-Key`.

## Ejecutar en este equipo

El entorno `.venv`, las dependencias, la configuración local y la compilación
Angular ya están preparados. Desde la raíz del proyecto en PowerShell:

```powershell
.\iniciar.ps1 -NoBuild
```

Abre http://127.0.0.1:8080. El usuario y contraseña locales están en
[.local/credenciales.txt](.local/credenciales.txt), excluido de Git.
Deja la terminal abierta. Si editaste Angular usa `./iniciar.ps1` para recompilar.
Si PowerShell bloquea scripts, puedes iniciar directamente:

```powershell
.\.venv\Scripts\python.exe servidor.py
```

Compila con **PlatformIO: Build** y luego inicia **F1 → Wokwi: Start Simulator**.
El firmware debe incluir la clave de `include/config.local.h`. Al iniciar la
simulación A1 y A3 estarán ocupados, A2 y A4 libres. Consulta
[las pruebas y el circuito](docs/SIMULACION.md).

## Instalación desde una copia nueva

Necesitas Python oficial 3.11 o superior, Node 24.15 o superior de la rama 24,
y las extensiones PlatformIO IDE y Wokwi Simulator para simular.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
.\.venv\Scripts\python.exe -m backend.configure
cd frontend
npm ci
npm run build
cd ..
.\.venv\Scripts\python.exe servidor.py
```

En este equipo `python` apunta a MSYS2. El entorno `.venv` fue creado con el
Python de PlatformIO para usar las dependencias nativas de Windows. Si necesitas
recrearlo aquí sin instalar otro Python:

```powershell
& "$env:USERPROFILE\.platformio\penv\Scripts\python.exe" -m venv .venv
```

`backend.configure` genera una contraseña aleatoria, un hash Argon2 y una clave
de sensor. Los archivos privados son `backend/.env`, `include/config.local.h`
y `.local/credenciales.txt`. Si `.env` ya existe, no se reemplaza.
No subas esos archivos ni firmware con credenciales a repositorios públicos.

## Desarrollo con recarga

Terminal 1, desde la raíz:

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.main:create_app --factory --reload --port 8080
```

Terminal 2:

```powershell
cd frontend
npm start
```

Abre http://localhost:4200. Angular redirige `/api/**` y `/config.json` al backend.
Para servir una compilación nueva con `servidor.py`, compila Angular y reinicia
el servidor, especialmente si la carpeta `dist` no existía al arrancar.

## Railway y móvil

- [Guía Railway: PostgreSQL, variables y dos servicios o servicio conjunto](docs/RAILWAY.md).
- [Angular + Capacitor para Android](docs/MOVIL.md).
- [Simulación Wokwi y generación de nodos](docs/SIMULACION.md).
- [Actualizar certificados HTTPS del firmware](certs/README.md).

Los Dockerfiles usan la raíz del repositorio como contexto. La guía detalla el
Config File Path para cada servicio. El despliegue, los dominios y las variables
de producción quedan pendientes de configurar en tu cuenta Railway.

## Estructura

| Ruta | Función |
| --- | --- |
| `frontend/` | Angular, estilos responsive, cliente API y Capacitor |
| `backend/` | API, autenticación, validación, SQLAlchemy y configuración |
| `src/main.cpp` | Lecturas y envío HTTP local / HTTPS con verificación de CA |
| `include/config.example.h` | Ejemplo de configuración del ESP32 |
| `certs/` | Bundle de CA públicas para TLS |
| `servidor.py`, `iniciar.ps1` | Arranque local |
| `Dockerfile`, `railway.json` | Despliegue conjunto |
| `frontend/Dockerfile`, `backend/Dockerfile` | Despliegue separado |
| `dashboard/index.html` | Dashboard original conservado como referencia |

## Validación

```powershell
.\.venv\Scripts\python.exe -m pip install -r backend/requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest backend/tests -q
cd frontend
npm run build
cd ..
```

La API tiene pruebas de permisos, validación, desactivación, vencimiento,
persistencia, configuración, CORS, logout y límite de login. Para repetirlas
también contra PostgreSQL, configura `TEST_DATABASE_URL` con una base **local**
llamada `parking_iot_test`; se crean y eliminan esquemas aislados de prueba.

Para comprobar la UI con un backend local activo:

```powershell
.\.venv\Scripts\python.exe -m playwright install chromium
.\.venv\Scripts\python.exe tools/test_browser.py http://127.0.0.1:8080
```

La prueba de navegador usa las credenciales locales, envía lecturas de prueba
y restaura los metadatos al terminar. Capturas en `.local/screenshots/`.
La base guarda solo la lectura más reciente, sin historial de ocupación.
El despliegue real Railway y el recorrido HTTPS desde Wokwi hacia ese dominio
se verifican una vez que tengas los servicios levantados.
