"""Lista o cambia la clasificación real/prueba de los registros históricos."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import db


def listar() -> None:
  print(f"{'ETIQUETA':40} {'ORIGEN':10} TOTAL")
  for fila in db.resumen_etiquetas():
    print(f"{fila['etiqueta'][:39]:40} {fila['origen']:10} {fila['total']:5}")


def main() -> int:
  parser = argparse.ArgumentParser(
      description="Marca etiquetas históricas como reales o de prueba."
  )
  parser.add_argument(
      "--listar",
      action="store_true",
      help="Solo muestra las etiquetas y su clasificación actual.",
  )
  parser.add_argument(
      "--prueba",
      nargs="+",
      metavar="ETIQUETA",
      help="Etiquetas que deben marcarse como prueba.",
  )
  parser.add_argument(
      "--real",
      nargs="+",
      metavar="ETIQUETA",
      help="Etiquetas que deben marcarse como reales.",
  )
  args = parser.parse_args()

  db.inicializar_base_datos()

  if args.prueba:
    total = db.marcar_origen(args.prueba, "prueba")
    print(f"Marcados como prueba: {total} registros.")
  if args.real:
    total = db.marcar_origen(args.real, "real")
    print(f"Marcados como reales: {total} registros.")

  if args.listar or (not args.prueba and not args.real):
    print()
    listar()
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
