import { Component, computed, inject, OnDestroy, OnInit, signal } from '@angular/core';
import { DatePipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Api, ApiError, SiteConfig, Slot, Snapshot, State } from './api';

@Component({
  selector: 'app-root', imports: [FormsModule, DatePipe],
  templateUrl: './app.html', styleUrl: './app.css',
})
export class App implements OnInit, OnDestroy {
  api = inject(Api);
  ready = signal(false);
  authenticated = signal(false);
  busy = signal(false);
  connected = signal(false);
  error = signal('');
  notice = signal('');
  slots = signal<Slot[]>([]);
  config = signal<SiteConfig>({ nombre: 'Estacionamiento IoT', segundos_sin_datos: 5 });
  updated = signal<string | null>(null);
  tab = signal<'overview' | 'slots' | 'settings'>('overview');
  username = 'admin';
  password = '';
  search = signal('');
  filter = signal('todos');
  editing = signal<Slot | null>(null);
  settingsDraft: SiteConfig = { nombre: '', segundos_sin_datos: 5 };
  modalError = signal('');
  readonly labels: Record<State, string> = { libre: 'Libre', ocupado: 'Ocupado', sin_datos: 'Sin datos', deshabilitado: 'Deshabilitado' };
  readonly states: State[] = ['libre', 'ocupado', 'sin_datos', 'deshabilitado'];
  counts = computed(() => {
    const counts = { libre: 0, ocupado: 0, sin_datos: 0, deshabilitado: 0 };
    this.slots().forEach(slot => counts[slot.estado]++);
    return counts;
  });
  enabledCount = computed(() => this.slots().filter(slot => slot.habilitado).length);
  occupation = computed(() => this.enabledCount() ? Math.round(this.counts().ocupado / this.enabledCount() * 100) : 0);
  filtered = computed(() => this.slots().filter(slot =>
    (this.filter() === 'todos' || slot.estado === this.filter()) &&
    `${slot.id} ${slot.nombre} ${slot.sector}`.toLocaleLowerCase().includes(this.search().toLocaleLowerCase())));
  private timer?: ReturnType<typeof setTimeout>;
  private stream?: AbortController;
  private pollingFallback = false;
  private refreshVersion = 0;
  private disposed = false;
  private trigger?: HTMLElement;
  private visibilityHandler = () => {
    if (document.visibilityState === 'visible' && this.authenticated()) void this.refresh();
  };

  async ngOnInit() {
    document.addEventListener('visibilitychange', this.visibilityHandler);
    try {
      await this.api.configure();
      if (this.api.token) {
        await this.api.request('/api/auth/me');
        this.authenticated.set(true);
        await this.refresh();
      }
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) this.api.setToken('');
      else this.error.set(this.message(error));
    } finally { this.ready.set(true); }
  }

  ngOnDestroy() {
    this.disposed = true; clearTimeout(this.timer); this.stream?.abort();
    document.removeEventListener('visibilitychange', this.visibilityHandler);
  }
  message(error: unknown) { return error instanceof Error ? error.message : 'No se pudo completar la operación.'; }

  async login() {
    if (this.busy()) return;
    this.busy.set(true); this.error.set('');
    try {
      await this.api.configure();
      const result = await this.api.request<{ token: string }>('/api/auth/login', 'POST', { username: this.username, password: this.password });
      this.api.setToken(result.token); this.password = '';
      this.authenticated.set(true); this.slots.set([]); this.tab.set('overview');
      await this.refresh();
    } catch (error) { this.error.set(this.message(error)); }
    finally { this.busy.set(false); }
  }

  async logout() {
    if (this.busy()) return;
    this.busy.set(true); this.error.set('');
    try {
      await this.api.request('/api/auth/logout', 'POST');
      this.endSession();
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) this.endSession();
      else this.error.set('No se pudo cerrar la sesión en el servidor. Intenta nuevamente.');
    } finally { this.busy.set(false); }
  }

  endSession() {
    this.api.setToken(''); clearTimeout(this.timer); this.stream?.abort();
    this.authenticated.set(false); this.connected.set(false);
    this.slots.set([]); this.editing.set(null); this.notice.set(''); this.error.set('');
  }

  async refresh() {
    clearTimeout(this.timer);
    this.stream?.abort();
    const version = ++this.refreshVersion;
    const token = this.api.token;
    try {
      const snapshot = await this.api.request<Snapshot>('/api/puestos');
      if (this.disposed || token !== this.api.token || version !== this.refreshVersion) return;
      this.applySnapshot(snapshot);
      if (this.pollingFallback) this.timer = setTimeout(() => void this.refresh(), 500);
      else void this.connectStream(token);
    } catch (error) {
      if (this.disposed || token !== this.api.token || version !== this.refreshVersion) return;
      this.markOffline();
      if (error instanceof ApiError && error.status === 401) {
        this.endSession(); this.error.set('Tu sesión expiró. Vuelve a ingresar.');
      }
    } finally {
      if (!this.disposed && this.authenticated() && token === this.api.token && version === this.refreshVersion && !this.connected())
        this.timer = setTimeout(() => void this.refresh(), 1000);
    }
  }

  private applySnapshot(snapshot: Snapshot) {
    this.slots.set(Object.values(snapshot.puestos)); this.config.set(snapshot.configuracion);
    this.updated.set(snapshot.hora_servidor); this.connected.set(true);
  }

  private markOffline() {
    this.connected.set(false);
    this.slots.update(slots => slots.map(slot => ({ ...slot, adc: null, estado_sensor: 'sin_datos', estado: slot.habilitado ? 'sin_datos' : 'deshabilitado' })));
  }

  private async connectStream(token: string) {
    const controller = new AbortController();
    this.stream = controller;
    try {
      await this.api.watchSlots(snapshot => {
        if (!controller.signal.aborted && token === this.api.token) this.applySnapshot(snapshot);
      }, controller.signal);
    } catch (error) {
      if (controller.signal.aborted || this.disposed || token !== this.api.token) return;
      if (error instanceof ApiError && error.status === 401) {
        this.endSession(); this.error.set('Tu sesión expiró. Vuelve a ingresar.');
        return;
      }
      // Keep the app usable during a rolling backend update or on old servers.
      this.pollingFallback = error instanceof ApiError && [404, 405].includes(error.status);
      if (!this.pollingFallback) this.markOffline();
      this.timer = setTimeout(() => void this.refresh(), this.pollingFallback ? 500 : 1000);
    }
  }

  navigate(tab: 'overview' | 'slots' | 'settings') {
    this.tab.set(tab); this.error.set(''); this.notice.set('');
    window.scrollTo(0, 0);
    if (tab === 'settings') this.settingsDraft = { ...this.config() };
  }

  edit(slot: Slot, event: Event) {
    this.trigger = event.currentTarget as HTMLElement;
    this.editing.set({ ...slot }); this.modalError.set('');
    setTimeout(() => document.getElementById('slot-name')?.focus());
  }

  closeEdit() {
    if (this.busy()) return;
    this.editing.set(null); this.trigger?.focus();
  }

  trapDialog(event: KeyboardEvent) {
    if (event.key !== 'Tab') return;
    const controls = Array.from((event.currentTarget as HTMLElement).querySelectorAll<HTMLElement>('button:not([disabled]), input:not([disabled]), textarea:not([disabled]), select:not([disabled])'));
    const first = controls[0], last = controls[controls.length - 1];
    if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
    else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
  }

  async saveSlot() {
    const slot = this.editing();
    if (!slot || this.busy()) return;
    this.busy.set(true); this.modalError.set('');
    try {
      const updated = await this.api.request<Slot>(`/api/puestos/${slot.id}`, 'PUT', {
        nombre: slot.nombre, sector: slot.sector, notas: slot.notas,
        habilitado: slot.habilitado, motivo_desactivacion: slot.motivo_desactivacion,
      });
      this.slots.update(slots => slots.map(existing => existing.id === updated.id ? updated : existing));
      this.editing.set(null); this.trigger?.focus();
      this.notice.set(`Cambios de ${slot.id} guardados.`);
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) {
        this.endSession(); this.error.set('Tu sesión expiró. Vuelve a ingresar.');
      } else this.modalError.set(this.message(error));
    } finally { this.busy.set(false); }
  }

  async saveSettings() {
    if (this.busy()) return;
    this.busy.set(true); this.error.set(''); this.notice.set('');
    try {
      const config = await this.api.request<SiteConfig>('/api/configuracion', 'PUT', this.settingsDraft);
      this.config.set(config); this.notice.set('Configuración guardada.');
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) {
        this.endSession(); this.error.set('Tu sesión expiró. Vuelve a ingresar.');
      } else this.error.set(this.message(error));
    } finally { this.busy.set(false); }
  }
}
