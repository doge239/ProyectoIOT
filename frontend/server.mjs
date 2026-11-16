// Servidor estático sin dependencias para el servicio frontend de Railway.
import { createServer } from 'node:http';
import { readFile, stat } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { resolve, sep, extname } from 'node:path';

const root = fileURLToPath(new URL('./dist/frontend/browser/', import.meta.url));
const base = (process.env.API_BASE_URL || '').replace(/\/$/, '');
if (process.env.NODE_ENV === 'production' && !base) throw new Error('Configura API_BASE_URL con el origen HTTPS del backend.');
if (base && new URL(base).protocol !== 'https:') throw new Error('API_BASE_URL debe usar HTTPS.');
const types = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript', '.css': 'text/css', '.json': 'application/json', '.svg': 'image/svg+xml', '.ico': 'image/x-icon', '.woff2': 'font/woff2' };

createServer(async (req, res) => {
  res.setHeader('X-Content-Type-Options', 'nosniff');
  res.setHeader('X-Frame-Options', 'DENY');
  res.setHeader('Referrer-Policy', 'same-origin');
  if (!['GET', 'HEAD'].includes(req.method)) { res.writeHead(405).end(); return; }
  try {
    const path = decodeURIComponent(new URL(req.url, 'http://localhost').pathname);
    if (path === '/config.json' || path === '/health') {
      res.writeHead(200, { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' });
      res.end(req.method === 'HEAD' ? '' : JSON.stringify(path === '/health' ? { status: 'ok' } : { apiBaseUrl: base }));
      return;
    }
    let file = resolve(root, '.' + (path === '/' ? '/index.html' : path));
    if (!file.startsWith(root.endsWith(sep) ? root : root + sep)) { res.writeHead(403).end(); return; }
    if (path.startsWith('/api/')) { res.writeHead(404).end(); return; }
    try { if (!(await stat(file)).isFile()) throw new Error(); }
    catch { if (extname(path)) { res.writeHead(404).end(); return; } file = resolve(root, 'index.html'); }
    const data = await readFile(file);
    res.writeHead(200, { 'Content-Type': types[extname(file)] || 'application/octet-stream',
      'Cache-Control': file.endsWith('.html') ? 'no-cache' : 'public, max-age=3600' });
    res.end(req.method === 'HEAD' ? undefined : data);
  } catch { res.writeHead(400).end(); }
}).listen(Number(process.env.PORT || 4200), '0.0.0.0', () => console.log(`Frontend listo en puerto ${process.env.PORT || 4200}`));
