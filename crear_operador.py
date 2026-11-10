"""Crea o actualiza un operador del sistema ETITC."""

from __future__ import annotations

import argparse
import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import config
import db


def main() -> int:
  parser = argparse.ArgumentParser(description="Crear o actualizar un operador.")
  parser.add_argument("--usuario", help="Nombre de usuario del operador.")
  parser.add_argument(
      "--rol",
      default="operador",
      choices=("operador", "administrador"),
      help="Rol del operador (por defecto: operador).",
  )
  args = parser.parse_args()

  usuario = args.usuario or input("Usuario: ").strip()
  if not usuario:
    print("El usuario no puede estar vacío.")
    return 1

  password = getpass.getpass("Contraseña: ")
  confirmacion = getpass.getpass("Confirmar contraseña: ")
  if password != confirmacion:
    print("Las contraseñas no coinciden.")
    return 1

  db.inicializar_base_datos()
  try:
    db.crear_operador(usuario, password, args.rol)
  except ValueError as exc:
    print(f"Error: {exc}")
    return 1
  except Exception as exc:
    print(f"No se pudo guardar el operador: {exc}")
    return 1

  print(f"Operador '{usuario}' creado o actualizado correctamente.")
  print(f"Base de datos: {config.DB_PATH}")
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
