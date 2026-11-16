import { Injectable } from '@angular/core';

export type State = 'libre' | 'ocupado' | 'sin_datos' | 'deshabilitado';
export interface Slot {
  id: string; nombre: string; sector: string; notas: string; habilitado: boolean;
  motivo_desactivacion: string; estado: State; estado_sensor: State;
  adc: number | null; ultimo_reporte: string | null;
}
export interface SiteConfig { nombre: string; segundos_sin_datos: number; }
export interface Snapshot { puestos: Record<string, Slot>; configuracion: SiteConfig; hora_servidor: string; }
export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message); }
}

@Injectable({ providedIn: 'root' })
export class Api {
  token = sessionStorage.getItem('parking-session') || '';
  base = '';

  async configure() {
    const response = await fetch('/config.json', { cache: 'no-store', signal: AbortSignal.timeout(8000) });
    if (!response.ok) throw new Error('No se pudo cargar la configuración de conexión.');
    const config = await response.json();
    if (typeof config.apiBaseUrl !== 'string') throw new Error('Configuración de conexión inválida.');
    this.base = config.apiBaseUrl.replace(/\/$/, '');
  }

  setToken(token: string) {
    this.token = token;
    if (token) sessionStorage.setItem('parking-session', token);
    else sessionStorage.removeItem('parking-session');
  }

  async request<T>(path: string, method = 'GET', body?: unknown): Promise<T> {
    const headers: Record<string, string> = {};
    if (this.token) headers['Authorization'] = `Bearer ${this.token}`;
    if (body !== undefined) headers['Content-Type'] = 'application/json';
    let response: Response;
    try {
      response = await fetch(this.base + path, {
        method, headers, body: body === undefined ? undefined : JSON.stringify(body),
        cache: 'no-store', signal: AbortSignal.timeout(8000),
      });
    } catch {
      throw new ApiError(0, 'No hay conexión con el servidor. Revisa tu conexión e intenta nuevamente.');
    }
    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new ApiError(response.status, typeof error.detail === 'string' ? error.detail : 'No se pudo completar la operación. Revisa los datos.');
    }
    return response.status === 204 ? undefined as T : response.json();
  }
}
