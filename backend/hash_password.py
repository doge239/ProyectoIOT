"""Genera un hash Argon2 para ADMIN_PASSWORD_HASH sin guardar la contraseña."""
from getpass import getpass
from pwdlib import PasswordHash

if __name__ == "__main__":
    password = getpass("Contraseña nueva del administrador (mínimo 12 caracteres): ")
    if len(password) < 12:
        raise SystemExit("Usa al menos 12 caracteres.")
    if password != getpass("Repite la contraseña: "):
        raise SystemExit("Las contraseñas no coinciden.")
    print(PasswordHash.recommended().hash(password))
