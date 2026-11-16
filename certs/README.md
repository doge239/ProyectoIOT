# Certificados HTTPS del ESP32

`x509_crt_bundle.bin` contiene nombres y claves públicas de las autoridades raíz
Mozilla incluidas en certifi. No contiene secretos. Se incorpora al firmware
con `board_build.embed_files` y se verifica el certificado del servidor, sin
desactivar TLS. El ESP32 sincroniza la hora por NTP antes de enviar por HTTPS.

Para actualizar las CA desde la raíz del proyecto:

```powershell
.\.venv\Scripts\python.exe -m pip install -r tools/requirements-firmware.txt
.\.venv\Scripts\python.exe tools/update_cert_bundle.py
```

Después recompila el firmware. Fuente y formato:
[Espressif ESP-IDF 4.4](https://github.com/espressif/esp-idf/tree/v4.4.7/components/mbedtls/esp_crt_bundle).
Certificados Mozilla distribuidos por [certifi, licencia MPL-2.0](https://github.com/certifi/python-certifi).
