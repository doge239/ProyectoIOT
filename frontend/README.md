# Frontend Parquea

Angular 22 standalone, señales y formularios; interfaz responsive para
administrador. La API usa sesiones Bearer revocables y el sensor usa otra clave.

```powershell
npm ci
npm start
```

Desarrollo en http://localhost:4200, con proxy al backend de `localhost:8080`.
Producción: `npm run build`; salida en `dist/frontend/browser`.

La web solicita `/config.json` al arrancar. En desarrollo lo sirve FastAPI;
en Railway separado lo sirve `server.mjs` usando `API_BASE_URL`.
Para ejecutar el servidor estático: `npm run serve:production`.

Consulta [Railway](../docs/RAILWAY.md) y [Capacitor](../docs/MOVIL.md).
