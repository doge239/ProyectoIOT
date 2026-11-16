# Probar con Wokwi

1. Inicia el backend y el frontend compilado con `./iniciar.ps1` desde PowerShell.
2. Compila el ESP32 con **PlatformIO: Build**. El firmware debe incorporar la
   clave de `include/config.local.h`, creada por `python -m backend.configure`.
3. Presiona **F1 → Wokwi: Start Simulator**.
4. Abre http://127.0.0.1:8080 e ingresa con `.local/credenciales.txt`.

A1 y A3 parten ocupados, A2 y A4 libres. Sube el potenciómetro de A2 al máximo
para verlo ocupado. Mueve el interruptor de A3 a la izquierda: unos cinco
segundos sin reportes después, se verá sin datos. El tiempo se puede ajustar
en Configuración.

En Puestos, edita A2 y desmarca Puesto habilitado. Indica un motivo y guarda.
Aunque muevas su potenciómetro, A2 queda deshabilitado; la ficha sigue mostrando
el estado del sensor por separado. Al habilitarlo vuelve a reflejar la lectura
vigente, o sin datos si ya venció.

| Puesto | Potenciómetro ADC1 | Interruptor pull-up |
| --- | --- | --- |
| A1 | GPIO34 | GPIO25 |
| A2 | GPIO35 | GPIO26 |
| A3 | GPIO32 | GPIO27 |
| A4 | GPIO33 | GPIO14 |

Potenciómetros a 3,3 V y GND. Interruptor central al GPIO; derecho a GND.
ADC >= 2500 significa ocupado, <= 1800 libre; entre ambos se conserva el
último estado. El potenciómetro representa la señal de un magnetómetro para
esta demostración. El magnetómetro físico y la fuente/reguladores de 12 V no
se implementan en esta simulación.

Para crear los nodos individuales, ejecuta:

```powershell
.\.venv\Scripts\python.exe generar_nodos.py
```

Se crean `nodos/A1` a `nodos/A4` con código, circuito y bundle de certificados.
Si existe configuración local, también se copia para que los nodos funcionen
con el servidor actual. Esos archivos contienen la clave del sensor y `nodos/`
está excluido de Git. Para producción asigna claves individuales en cada nodo
y en `DEVICE_KEYS`, como explica la guía Railway. Compila cada nodo antes de
simular. No ejecutes la demo de cuatro canales y los nodos a la vez, porque
reportarían sobre los mismos identificadores.

El firmware usa HTTP solo en el servidor local. Para Railway usa la URL HTTPS
de tu backend. Cambiar el nombre visible de A1 no cambia su identificador físico.
