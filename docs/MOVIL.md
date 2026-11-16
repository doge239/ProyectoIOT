# Android con Angular y Capacitor

Angular es responsive y ya funciona desde el navegador del celular.
Capacitor 8 está instalado y configurado en `frontend/capacitor.config.ts` para
reutilizar la misma interfaz. Se genera un APK de prueba firmado con la clave
debug del equipo; no hay publicación en tiendas ni APK release de distribución.

## Compilar e instalar el APK de prueba

Desde la raíz en PowerShell, con Java 21 y el SDK de Android instalados:

```powershell
.\compilar-apk.ps1
```

El resultado queda en `apk/Parquea-Admin-1.0-debug.apk`, excluido de Git. El
script compila Angular, sincroniza Capacitor y ejecuta `assembleDebug`. Usa
el backend Railway desplegado; puedes cambiarlo con `-BackendUrl https://...`.
No se incluyen contraseñas ni claves de sensores en el APK.

Copia el APK a tu teléfono Android (Android 7.0 o superior), ábrelo y permite
la instalación desde la aplicación con la que lo abriste cuando Android lo
solicite. Inicia sesión con las credenciales de producción de
`.local/railway-credenciales.txt`. La aplicación requiere Internet para
consultar Railway. Para distribuir en una tienda necesitas generar un build
release y gestionar una clave de firma propia.

La APK generada fue verificada con `apksigner` e instalada en un emulador
Android. Se comprobaron login contra Railway, carga de los cuatro puestos,
apertura del editor y cierre de sesión. La configuración incluida usa HTTPS
y no contiene la contraseña del administrador ni claves de sensores.

Después de desplegar el backend por HTTPS, desde `frontend/`:

```powershell
node scripts/mobile-config.mjs https://TU-BACKEND.up.railway.app
npx cap add android
npm run mobile:sync
npm run mobile:open
```

`cap add android` se ejecuta una sola vez.
En este equipo `frontend/android/` ya fue generado y sincronizado como prueba:
omite `npx cap add android` si esa carpeta existe. Aún debes configurar la URL
real del backend y volver a sincronizar antes de compilar el APK.

`mobile:sync` compila Angular y copia
la web al proyecto nativo. `mobile:open` abre Android Studio, donde puedes
ejecutar en un dispositivo o generar el APK. Necesitas Android Studio, su SDK
y el JDK compatible con Capacitor 8; consulta los
[requisitos oficiales](https://capacitorjs.com/docs/getting-started/environment-setup).

`public/config.json` es generado e ignorado por Git. Incluye solo la URL de la
API; nunca pongas allí claves de sensor o contraseña de administrador. Para
cambiar la API del APK vuelve a generar esa configuración y sincroniza.
El frontend web de Railway toma su configuración de `API_BASE_URL` en runtime.

Añade `https://localhost` a `CORS_ORIGINS` del backend para Android. Para iOS,
el origen es `capacitor://localhost` y se requiere macOS/Xcode y añadir la
plataforma correspondiente. La aplicación requiere conexión para conocer el
estado actual: si se pierde, evita mostrar una disponibilidad antigua como
si fuera vigente.

Antes de subir el proyecto Android a Git, revisa su configuración de firma;
no publiques keystores ni claves de firma. Los directorios nativos generados
se ignoran inicialmente en este repositorio y puedes versionarlos cuando los
uses, conservando sus exclusiones de archivos de compilación y credenciales.
