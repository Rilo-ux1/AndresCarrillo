"""Configuración central del sistema de control de acceso ETITC.

Todas las rutas se calculan a partir de la ubicación de este archivo, no del
directorio desde que se ejecute el programa. Así se evita que se cree una
base de datos o un dataset "fantasma" al abrir la aplicación desde otra carpeta.
"""

from __future__ import annotations

import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Rutas del proyecto
# ---------------------------------------------------------------------------
APP_DIR = Path(__file__).resolve().parent
BASE_DIR = APP_DIR.parent


def _ruta_desde_entorno(nombre: str, predeterminada: Path) -> Path:
  valor = os.getenv(nombre)
  return Path(valor).expanduser() if valor else predeterminada


DB_PATH = _ruta_desde_entorno("ETITC_DB", BASE_DIR / "accesos.db")
DATASET_DIR = _ruta_desde_entorno("ETITC_DATASET", BASE_DIR / "dataset")
LOGO_PATH = BASE_DIR / "etitc_escudo.png"
CACHE_PATH = _ruta_desde_entorno("ETITC_CACHE", BASE_DIR / ".cache" / "embeddings.json")
BACKUPS_DIR = _ruta_desde_entorno("ETITC_BACKUPS", BASE_DIR / ".backups")
LOG_PATH = _ruta_desde_entorno("ETITC_LOG", BASE_DIR / "app.log")


# ---------------------------------------------------------------------------
# Parámetros de reconocimiento
# ---------------------------------------------------------------------------
MODELO = "dlib_face_recognition_resnet_model_v1"

# Distancia euclidiana máxima para considerar que dos rostros son la misma
# persona. Calibrada con el dataset local: con 0.577 se mantiene una tasa de
# falsos positivos (FAR) por debajo del 1 %. Se puede ajustar con ETITC_UMBRAL.
UMBRAL = float(os.getenv("ETITC_UMBRAL", "0.577"))

# Diferencia mínima entre la mejor y la segunda mejor persona. Si las dos están
# demasiado cerca, el resultado es ambiguo y se deniega.
MARGEN_MINIMO = float(os.getenv("ETITC_MARGEN", "0.05"))

# Tiempo que debe mantenerse el mismo estado antes de confirmar un evento.
TIEMPO_CONFIRMACION = float(os.getenv("ETITC_CONFIRMACION", "3.0"))

# Tiempo mínimo entre dos eventos de la misma persona/estado (reducido a 5s para pruebas).
COOLDOWN_EVENTO = int(os.getenv("ETITC_COOLDOWN", "5"))

# Tiempo que se conserva un rostro sin verse antes de descartar su seguimiento.
TIEMPO_OLVIDO = float(os.getenv("ETITC_OLVIDO", "2.0"))

# Cámara y frecuencias de actualización.
CAMARA_INDICE = int(os.getenv("ETITC_CAMARA", "0"))

INTERVALO_UI_MS = int(os.getenv("ETITC_INTERVALO_UI", "30"))

# Límite para no cargar una cantidad excesiva de filas en la ventana de consulta.
MAX_REGISTROS_UI = int(os.getenv("ETITC_MAX_REGISTROS", "2000"))

# Seguridad del operador.
MIN_LONGITUD_PASSWORD = int(os.getenv("ETITC_MIN_PASSWORD", "6"))
MAX_INTENTOS_LOGIN = int(os.getenv("ETITC_MAX_INTENTOS", "5"))
BLOQUEO_LOGIN_SEGUNDOS = int(os.getenv("ETITC_BLOQUEO_SEGUNDOS", "60"))


def verificar_entorno() -> list[str]:
  """Devuelve una lista de advertencias legibles sobre el entorno."""
  avisos: list[str] = []
  if not DATASET_DIR.exists():
    avisos.append(f"No existe la carpeta del dataset: {DATASET_DIR}")
  elif not any(DATASET_DIR.iterdir()):
    avisos.append(f"El dataset está vacío: {DATASET_DIR}")
  if not LOGO_PATH.exists():
    avisos.append(f"No se encontró el escudo: {LOGO_PATH}")
  if not DB_PATH.parent.exists():
    avisos.append(f"No existe la carpeta de la base de datos: {DB_PATH.parent}")
  return avisos


def resumen_rutas() -> str:
  return (
      f"BASE_DIR={BASE_DIR}\n"
      f"DB_PATH={DB_PATH}\n"
      f"DATASET_DIR={DATASET_DIR}\n"
      f"UMBRAL={UMBRAL} MARGEN={MARGEN_MINIMO}"
  )