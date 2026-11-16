import { readFileSync, writeFileSync } from 'node:fs';

const code = Number(process.argv[2]);
const name = process.argv[3];
if (!Number.isInteger(code) || code < 1 || !/^\d+\.\d+(\.\d+)?$/.test(name || ''))
  throw new Error('Uso: node scripts/android-version.mjs <código entero> <versión, por ejemplo 1.1>');
const path = 'android/app/build.gradle';
const source = readFileSync(path, 'utf8');
if (!/versionCode\s+\d+/.test(source) || !/versionName\s+"[^"]+"/.test(source))
  throw new Error('No se encontró la configuración de versión Android.');
writeFileSync(path, source.replace(/versionCode\s+\d+/, `versionCode ${code}`)
  .replace(/versionName\s+"[^"]+"/, `versionName "${name}"`));
