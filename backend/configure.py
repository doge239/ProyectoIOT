"""Prepara credenciales locales sin guardar secretos en Git."""
import json
from pathlib import Path
import secrets
from pwdlib import PasswordHash

ROOT = Path(__file__).resolve().parents[1]


def main():
    env = ROOT / "backend" / ".env"
    if env.exists():
        raise SystemExit("backend/.env ya existe; se conserva su configuración.")
    password, device_key = secrets.token_urlsafe(15), secrets.token_urlsafe(36)
    password_hash = PasswordHash.recommended().hash(password)
    env.write_text(
        f"ADMIN_USERNAME=admin\nADMIN_PASSWORD_HASH='{password_hash}'\n"
        f"DEVICE_KEYS='{json.dumps({device_key: ['A1', 'A2', 'A3', 'A4']})}'\n"
        "ALLOW_ANONYMOUS_TELEMETRY=false\nENVIRONMENT=development\n"
        "CORS_ORIGINS=http://localhost:4200,http://127.0.0.1:4200,https://localhost,capacitor://localhost\n",
        encoding="utf-8",
    )
    local = ROOT / ".local"
    local.mkdir(exist_ok=True)
    (local / "credenciales.txt").write_text(
        "SOLO PARA DESARROLLO LOCAL. No compartir ni subir a Git.\n"
        f"Usuario: admin\nContraseña: {password}\n\n"
        "Backend: backend/.env\nClave del sensor: include/config.local.h\n", encoding="utf-8",
    )
    include = ROOT / "include"
    include.mkdir(exist_ok=True)
    firmware_config = include / "config.local.h"
    if not firmware_config.exists():
        firmware_config.write_text(
            '#pragma once\n#define IOT_TELEMETRY_URL "http://host.wokwi.internal:8080/api/telemetria"\n'
            f'#define IOT_DEVICE_KEY "{device_key}"\n', encoding="utf-8",
        )
    print("Configuración creada. Consulta .local/credenciales.txt para entrar al panel.")
    print("Compila el firmware para incorporar la clave del sensor.")


if __name__ == "__main__":
    main()
