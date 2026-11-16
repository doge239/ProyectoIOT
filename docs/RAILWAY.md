# Despliegue en Railway

El repositorio está preparado para dos modalidades. No hay servicios desplegados
ni recursos contratados automáticamente. PostgreSQL almacena configuración,
última lectura por sensor y sesiones. No hay registro público de usuarios.

## Opción A: frontend y backend separados

Crea un proyecto Railway con PostgreSQL y dos servicios desde este repositorio.
En **ambos servicios deja Root Directory en la raíz del repositorio**: los
Dockerfiles usan rutas `frontend/` y `backend/` desde ese contexto.

| Servicio | Config File Path | Dockerfile | Healthcheck |
| --- | --- | --- | --- |
| Backend | `/backend/railway.json` | `backend/Dockerfile` | `/api/health` |
| Frontend | `/frontend/railway.json` | `frontend/Dockerfile` | `/health` |

Selecciona Config File Path en los ajustes del servicio para no utilizar el
`railway.json` de la raíz. Genera un dominio público HTTPS para cada servicio.

### Variables del backend

| Variable | Valor |
| --- | --- |
| `ENVIRONMENT` | `production` |
| `DATABASE_URL` | Referencia a `DATABASE_URL` del servicio PostgreSQL |
| `ADMIN_USERNAME` | Tu nombre de administrador |
| `ADMIN_PASSWORD_HASH` | Hash Argon2 generado con el comando de abajo |
| `DEVICE_KEYS` | JSON con claves de sensores y sus puestos permitidos |
| `ALLOW_ANONYMOUS_TELEMETRY` | `false` |
| `CORS_ORIGINS` | Origen HTTPS del frontend; añadir `https://localhost,capacitor://localhost` para app móvil |
| `SESSION_HOURS` | `8`, opcional; de 1 a 24 |

Railway proporciona `PORT`. El proceso escucha en `0.0.0.0:$PORT`. No copies las
credenciales locales al despliegue; genera otras para producción.

Desde el entorno Python local, genera el hash sin guardar tu contraseña:

```powershell
.\.venv\Scripts\python.exe -m backend.hash_password
```

Copia el resultado completo a `ADMIN_PASSWORD_HASH` en la interfaz de Railway,
sin comillas adicionales. Genera claves aleatorias largas para `DEVICE_KEYS`.
Para un ESP32 que lee los cuatro puestos, el formato es:

```json
{"CLAVE_ALEATORIA_DE_AL_MENOS_24_CARACTERES":["A1","A2","A3","A4"]}
```

Para nodos separados puedes asignar una clave distinta por puesto:

```json
{
  "CLAVE_ALEATORIA_DISTINTA_PARA_A1":["A1"],
  "CLAVE_ALEATORIA_DISTINTA_PARA_A2":["A2"],
  "CLAVE_ALEATORIA_DISTINTA_PARA_A3":["A3"],
  "CLAVE_ALEATORIA_DISTINTA_PARA_A4":["A4"]
}
```

Esos valores son ejemplos de formato: sustitúyelos por secretos aleatorios.
Las claves viven en el firmware y en el backend, nunca en Angular.

La primera ejecución crea las tablas y A1–A4 automáticamente. Los reinicios
conservan nombres, desactivaciones y lecturas; una lectura vencida se muestra
sin datos. Esta versión inicial usa creación de esquema, no migraciones
automáticas de esquemas existentes. Versiona las migraciones si amplías las
tablas antes de actualizar una base en producción.

### Variables del frontend

Define `API_BASE_URL=https://TU-BACKEND.up.railway.app`, **sin `/api` al final**.
El servidor entrega `/config.json` con esa URL en cada arranque. Cambiarla no
requiere recompilar Angular. La dirección de la API es pública y no contiene
credenciales. La contraseña se ingresa en el login; la sesión se conserva por
pestaña en `sessionStorage`, expira y se revoca al cerrar sesión.

En `CORS_ORIGINS` del backend usa exactamente el origen del frontend, sin
barra final ni rutas. No uses `*`. CORS no sustituye la autenticación.

## Opción B: un servicio para Angular y API

Usa `Dockerfile` y `railway.json` de la raíz con PostgreSQL. El Dockerfile
compila Angular y FastAPI sirve los archivos y `/api` bajo el mismo dominio.
Configura las variables de backend de la tabla anterior. `CORS_ORIGINS` puede
quedar vacío para la web del mismo origen; añade los orígenes de Capacitor si
lo usas. No hace falta `API_BASE_URL` en esta modalidad.

## Conectar el ESP32 / Wokwi

Edita `include/config.local.h` (creado para la prueba local y excluido de Git):

```cpp
#pragma once
#define IOT_TELEMETRY_URL "https://TU-BACKEND.up.railway.app/api/telemetria"
#define IOT_DEVICE_KEY "LA_CLAVE_QUE_CONFIGURASTE_EN_DEVICE_KEYS"
```

Recompila con **PlatformIO: Build** y reinicia Wokwi. El ESP32 verifica HTTPS
con las CA Mozilla incluidas y sincroniza su reloj por NTP. No se omite la
verificación del certificado. Permite salida a Internet y NTP en la red del
montaje físico. Ajusta también SSID, contraseña y canal Wi-Fi siguiendo
`include/config.example.h` (canal `0` para selección automática en una red real).

HTTP 204 confirma un reporte aceptado. HTTP 401 indica clave inválida; 403,
que el dispositivo reporta un puesto que su clave no autoriza. La clave de un
sensor no permite iniciar sesión, leer el panel ni editar puestos.

La desactivación es administrativa: no corta la alimentación del dispositivo
y no cambia la lectura física. El puesto queda fuera de los disponibles
hasta que el administrador lo habilite.

## Verificación tras desplegar

1. `GET https://TU-BACKEND/api/health` devuelve `{"status":"ok"}`.
2. El frontend abre y permite iniciar sesión con tu administrador.
3. Wokwi recibe HTTP 204 y aparecen las lecturas.
4. Desactiva A2 con un motivo: permanece deshabilitado aunque el sensor reporte.
5. Reinicia el backend: los cambios persisten en PostgreSQL.
6. Detén Wokwi: los puestos habilitados pasan a sin datos al vencer su reporte.

Solo se guarda la última lectura por puesto; esta versión no incluye histórico
ni reservas. Haz copias de seguridad de PostgreSQL según lo que necesites
conservar. Un administrador puede cambiar los metadatos de los cuatro puestos;
agregar sensores nuevos implica ampliar también sus identificadores y firmware.

Referencias oficiales: [monorepos](https://docs.railway.com/deployments/monorepo),
[configuración como código](https://docs.railway.com/reference/config-as-code) y
[variables](https://docs.railway.com/guides/variables).
