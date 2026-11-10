"""Migra la base de datos existente sin borrar registros históricos."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import config
import db


def main() -> int:
  print(f"Base de datos: {config.DB_PATH}")
  if not config.DB_PATH.exists():
    print("La base de datos no existe; se creará una nueva.")
  try:
    info = db.inicializar_base_datos()
  except Exception as exc:
    print(f"ERROR al migrar la base de datos: {exc}")
    return 1

  print(f"Versión de esquema: {info['version']}")
  if info.get("backup"):
    print(f"Respaldo creado: {info['backup']}")
  else:
    print("No fue necesario crear un respaldo nuevo.")

  creadas = db.sincronizar_personas_con_dataset()
  if creadas:
    print(f"Personas nuevas detectadas en el dataset: {creadas}")

  print("\nClasificación actual de etiquetas:")
  print(f"{'ETIQUETA':38} {'ORIGEN':10} TOTAL")
  for fila in db.resumen_etiquetas():
    print(f"{fila['etiqueta'][:37]:38} {fila['origen']:10} {fila['total']:5}")

  with db.conexion() as conn:
    total = conn.execute("SELECT COUNT(*) AS total FROM registros_acceso").fetchone()[
        "total"
    ]
    personas = conn.execute("SELECT COUNT(*) AS total FROM personas").fetchone()[
        "total"
    ]
  print(f"\nRegistros totales: {total}")
  print(f"Personas registradas: {personas}")
  print(
      "\nSugerencia: use clasificar_registros.py --listar para revisar y "
      "ajustar qué etiquetas son de prueba."
  )
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
