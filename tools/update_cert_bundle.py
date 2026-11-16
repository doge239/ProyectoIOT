"""Genera el bundle de CA Mozilla para WiFiClientSecure (formato ESP-IDF 4.4).

Formato documentado por Espressif: cantidad uint16, luego longitud del nombre,
longitud de clave, nombre DER y SubjectPublicKeyInfo DER, ordenados por nombre.
https://github.com/espressif/esp-idf/tree/v4.4.7/components/mbedtls/esp_crt_bundle
Los certificados provienen de certifi (Mozilla), licencia MPL-2.0.
"""
from pathlib import Path
import struct
import certifi
from cryptography import x509
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

ROOT = Path(__file__).resolve().parents[1]


def main():
    certificates = x509.load_pem_x509_certificates(Path(certifi.where()).read_bytes())
    entries = sorted((cert.subject.public_bytes(), cert.public_key().public_bytes(
        Encoding.DER, PublicFormat.SubjectPublicKeyInfo)) for cert in certificates)
    bundle = struct.pack('>H', len(entries)) + b''.join(
        struct.pack('>HH', len(name), len(key)) + name + key for name, key in entries)
    output = ROOT / "certs" / "x509_crt_bundle.bin"
    output.parent.mkdir(exist_ok=True)
    output.write_bytes(bundle)
    print(f"Bundle actualizado: {len(entries)} CA, {len(bundle)} bytes.")


if __name__ == "__main__":
    main()
