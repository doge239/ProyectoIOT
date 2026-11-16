# Actualización rápida de puestos

El ESP32 conserva su cliente TCP/TLS y usa HTTP keep-alive. Muestrea cada
40 ms y envía cambios de ocupación sin esperar al siguiente reporte periódico,
con un mínimo de 100 ms entre envíos y un reintento de 1 s si hay errores.
El reporte periódico de 750 ms conserva el dato ADC y la detección de conexión.
La llamada HTTP sigue siendo síncrona: la duración real de la red también
afecta cuánto tarda en detectar un cambio durante una petición pendiente.

La web y APK 1.1 reciben instantáneas mediante una petición autenticada a
`GET /api/puestos/stream`. El servidor notifica después de confirmar cambios
de sensores, puestos o configuración en la base de datos. El token se envía
en Authorization, no en la URL. El canal verifica sesiones y datos vencidos
cada segundo y libera sus conexiones de base entre lecturas.

La app vuelve a conectar si se corta el canal; al regresar de segundo plano
sincroniza de nuevo. Si el backend todavía no tiene el endpoint de streaming,
usa consultas cada 500 ms como compatibilidad. Una interrupción del stream
se detecta por sus heartbeats; no se mantienen puestos libres como vigentes
cuando se pierde la conexión.

Las notificaciones inmediatas operan dentro de cada proceso del backend. La
instancia Railway actual usa un proceso y una réplica. Si se agregan procesos
o réplicas, los cambios de otros procesos se detectan en la comprobación de
un segundo; para conservar notificaciones inmediatas entre réplicas se debe
añadir un bus compartido como PostgreSQL NOTIFY o Redis.

## Medición en Railway

Se realizaron cinco cambios de notas por cliente y se midió desde el inicio
de la petición de edición hasta que el texto apareció en pantalla. Se
restauraron las notas originales y no se modificó la ocupación para medir.

| Cliente | Mediana | Rango |
| --- | --- | --- |
| Web en pantalla móvil | 233 ms | 207–312 ms |
| APK 1.1 en emulador Android | 236 ms | 228–271 ms |

Es una medición del recorrido petición → Railway → interfaz. No incluye el
muestreo ni el envío desde Wokwi y no garantiza una latencia constante en
otras redes o teléfonos. El firmware muestra la duración HTTP por Serial
para verificar ese tramo al reiniciar el simulador.

La compilación del firmware, Angular y APK pasó. Las pruebas de API contra
SQLite y PostgreSQL incluyen permisos del canal, cambios en vivo y cierre de
sesiones. También se comprobaron desconexión/reconexión en el navegador e
instalación de la APK 1.1 sobre la versión anterior en Android.

Para aplicar la mejora: recarga la web, instala `apk/Parquea-Admin-1.1-debug.apk`
y reinicia Wokwi para cargar el firmware recién compilado. El estado Sin datos
sigue usando el tiempo de seguridad configurado (cinco segundos por defecto).
