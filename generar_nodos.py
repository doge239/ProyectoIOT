"""Crea cuatro proyectos Wokwi independientes a partir del proyecto central."""

import json
from pathlib import Path
from shutil import copyfile


def main():
    raiz = Path(__file__).resolve().parent
    diagrama = json.loads((raiz / "diagram.json").read_text(encoding="utf-8"))
    configuracion = (raiz / "platformio.ini").read_text(encoding="utf-8")
    salida = raiz / "nodos"

    if salida.exists():
        raise SystemExit("Ya existe nodos/. Muévela o renómbrala antes de generar otra copia.")

    for numero in range(1, 5):
        identificador = f"A{numero}"
        prefijo = identificador.lower() + "_"
        nodo = salida / identificador
        (nodo / "src").mkdir(parents=True)
        (nodo / ".vscode").mkdir()
        (nodo / "include").mkdir()
        (nodo / "certs").mkdir()
        for archivo in ("src/main.cpp", "wokwi.toml", ".vscode/extensions.json"):
            copyfile(raiz / archivo, nodo / archivo)
        copyfile(raiz / "certs/x509_crt_bundle.bin", nodo / "certs/x509_crt_bundle.bin")
        copyfile(raiz / "include/config.example.h", nodo / "include/config.example.h")
        if (raiz / "include/config.local.h").exists():
            copyfile(raiz / "include/config.local.h", nodo / "include/config.local.h")
        (nodo / "platformio.ini").write_text(
            configuracion + f"\nbuild_flags = -D PARKING_SLOT={numero}\n",
            encoding="utf-8",
        )
        partes = []
        for parte in diagrama["parts"]:
            componente = parte.copy()
            if componente["id"] == "esp":
                componente["attrs"] = {"macAddress": f"24:0a:c4:00:01:{16 + numero:02x}"}
            elif componente["id"].startswith(prefijo):
                componente["left"] -= 130 * (numero - 1)
            else:
                continue
            partes.append(componente)
        conexiones = [
            cable for cable in diagrama["connections"]
            if cable[0].startswith((prefijo, "esp:"))
        ]
        (nodo / "diagram.json").write_text(
            json.dumps({**diagrama, "parts": partes, "connections": conexiones},
                       ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"Proyecto creado en nodos/{identificador}")


if __name__ == "__main__":
    main()
