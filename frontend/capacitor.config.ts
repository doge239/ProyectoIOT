import type { CapacitorConfig } from '@capacitor/cli';

const config: CapacitorConfig = {
  appId: 'cl.parquea.admin',
  appName: 'Parquea Admin',
  webDir: 'dist/frontend/browser',
  server: { androidScheme: 'https' },
};
export default config;
