import { mkdirSync, writeFileSync } from 'node:fs';

const raw = process.argv[2];
if (!raw) throw new Error('Uso: node scripts/mobile-config.mjs https://tu-backend.up.railway.app');
const url = new URL(raw);
if (url.protocol !== 'https:' || url.username || url.password || url.pathname !== '/' || url.search || url.hash)
  throw new Error('Indica el origen HTTPS del backend, sin rutas ni credenciales.');
mkdirSync('public', { recursive: true });
writeFileSync('public/config.json', JSON.stringify({ apiBaseUrl: url.origin }));
console.log('Configuración móvil creada. Ahora ejecuta npm run mobile:sync.');
