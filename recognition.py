"""Carga de la galería facial, comparación y seguimiento de rostros.

Este módulo no importa ``face_recognition`` ni ``cv2`` al cargarse. Así las
funciones puras (comparación, nombres, seguimiento) se pueden probar sin tener
instaladas las dependencias pesadas.
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import re
import time
import unicodedata
import warnings
from dataclasses import dataclass, field
from pathlib import Path

import config

logger = logging.getLogger(__name__)

# face_recognition_models todavía usa pkg_resources; con setuptools >= 81
# aparece una advertencia de deprecación que no afecta el funcionamiento.
warnings.filterwarnings(
    "ignore",
    message="pkg_resources is deprecated as an API.*",
    category=UserWarning,
)

EXTENSIONES_IMAGEN = {".jpg", ".jpeg", ".png"}
RESERVADOS_WINDOWS = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    "COM1",
    "COM2",
    "COM3",
    "COM4",
    "COM5",
    "COM6",
    "COM7",
    "COM8",
    "COM9",
    "LPT1",
    "LPT2",
    "LPT3",
    "LPT4",
    "LPT5",
    "LPT6",
    "LPT7",
    "LPT8",
    "LPT9",
}


# ---------------------------------------------------------------------------
# Estructuras
# ---------------------------------------------------------------------------
@dataclass
class Galeria:
  nombres: list[str] = field(default_factory=list)
  encodings: list[list[float]] = field(default_factory=list)
  rutas: list[str] = field(default_factory=list)
  carpetas: list[str] = field(default_factory=list)
  descartadas: list[dict] = field(default_factory=list)
  fingerprint: str = ""

  @property
  def personas(self) -> list[str]:
    return sorted(set(self.nombres))

  def __len__(self) -> int:
    return len(self.encodings)


@dataclass
class ResultadoReconocimiento:
  nombre: str
  estado: str
  confianza: float
  distancia: float | None = None
  umbral: float | None = None
  motivo: str | None = None


@dataclass
class RostroSeguido:
  track_id: int
  bbox: tuple[int, int, int, int]
  resultado: ResultadoReconocimiento
  inicio_estado: float
  ultimo_visto: float
  confirmado: bool = False
  evento_emitido: bool = False
  visto_este_frame: bool = False


@dataclass
class EventoAcceso:
  track_id: int
  resultado: ResultadoReconocimiento
  bbox: tuple[int, int, int, int]
  fecha: float


# ---------------------------------------------------------------------------
# Validación de capturas y nombres
# ---------------------------------------------------------------------------
def normalizar_display(nombre: str) -> str:
  return re.sub(r"\s+", " ", (nombre or "").strip())


def sanitizar_nombre(nombre: str) -> str:
  """Convierte un nombre visible en un nombre de carpeta seguro."""
  texto = unicodedata.normalize("NFKD", (nombre or "").strip())
  texto = "".join(c for c in texto if not unicodedata.combining(c))
  texto = re.sub(r"[^A-Za-z0-9_-]+", "_", texto)
  texto = re.sub(r"_+", "_", texto).strip("_")
  if not texto:
    return ""
  if texto.upper() in RESERVADOS_WINDOWS:
    texto = f"persona_{texto}"
  return texto[:60]


def normalizar_clave(nombre: str) -> str:
  """Clave para comparar personas sin distinguir tildes, mayúsculas o guiones."""
  texto = unicodedata.normalize("NFKD", (nombre or "").replace("_", " ").strip())
  texto = "".join(c for c in texto if not unicodedata.combining(c))
  texto = re.sub(r"[^a-z0-9]+", " ", texto.lower())
  return texto.strip()


def validar_captura(frame_bgr) -> tuple[bool, str]:
  """Comprueba que la captura tenga una sola cara, nítida y bien iluminada."""
  try:
    import cv2
    import face_recognition
  except ImportError as exc:  # pragma: no cover - depende del entorno
    raise RuntimeError(
        "Faltan dependencias para validar la captura. "
        "Instale con: pip install -r requirements.txt"
    ) from exc

  if frame_bgr is None:
    return False, "No hay imagen de la cámara."

  rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
  ubicaciones = face_recognition.face_locations(rgb)
  if len(ubicaciones) == 0:
    return False, "No se detectó ningún rostro. Mire de frente a la cámara."
  if len(ubicaciones) > 1:
    return False, "Hay más de una persona en la imagen. Deje solo a la persona a registrar."

  top, right, bottom, left = ubicaciones[0]
  ancho = right - left
  alto = bottom - top
  if ancho < 80 or alto < 80:
    return False, "El rostro es muy pequeño. Acérquese un poco a la cámara."

  gris = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
  varianza = float(cv2.Laplacian(gris, cv2.CV_64F).var())
  if varianza < 50:
    return False, "La imagen está borrosa. Mantenga la cámara quieta e intente de nuevo."
  brillo = float(gris.mean())
  if brillo < 40:
    return False, "La imagen está muy oscura. Mejore la iluminación."
  if brillo > 220:
    return False, "La imagen está sobreexpuesta. Evite la luz directa sobre el rostro."

  return True, ""


# ---------------------------------------------------------------------------
# Galería y caché
# ---------------------------------------------------------------------------
def _iterar_imagenes(dataset_dir: Path):
  if not dataset_dir.exists():
    return
  for carpeta in sorted(dataset_dir.iterdir()):
    if not carpeta.is_dir() or carpeta.name.startswith("."):
      continue
    for archivo in sorted(carpeta.iterdir()):
      if archivo.is_file() and archivo.suffix.lower() in EXTENSIONES_IMAGEN:
        yield carpeta, archivo


def _huella_dataset(dataset_dir: Path) -> str:
  huella = hashlib.sha256()
  huella.update(config.MODELO.encode("utf-8"))
  if not dataset_dir.exists():
    return huella.hexdigest()
  for carpeta, archivo in _iterar_imagenes(dataset_dir):
    try:
      estado = archivo.stat()
    except OSError:
      continue
    ruta_relativa = archivo.relative_to(dataset_dir).as_posix()
    huella.update(
        f"{ruta_relativa}|{estado.st_size}|{estado.st_mtime_ns}".encode("utf-8")
    )
  return huella.hexdigest()


def _leer_cache(cache_path: Path) -> dict | None:
  if not cache_path.exists():
    return None
  try:
    with cache_path.open("r", encoding="utf-8") as archivo:
      datos = json.load(archivo)
    if not isinstance(datos, dict):
      return None
    return datos
  except (OSError, ValueError):
    logger.warning("No se pudo leer la caché de embeddings: %s", cache_path)
    return None


def _guardar_cache(cache_path: Path, datos: dict) -> None:
  try:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    temporal = cache_path.with_suffix(".tmp")
    with temporal.open("w", encoding="utf-8") as archivo:
      json.dump(datos, archivo, ensure_ascii=False)
    temporal.replace(cache_path)
  except OSError:
    logger.warning("No se pudo guardar la caché de embeddings: %s", cache_path)


def _galeria_desde_cache(datos: dict) -> Galeria:
  items = datos.get("items", [])
  return Galeria(
      nombres=[str(item["nombre"]) for item in items],
      encodings=[list(item["encoding"]) for item in items],
      rutas=[str(item.get("ruta", "")) for item in items],
      carpetas=[str(item.get("carpeta", "")) for item in items],
      descartadas=list(datos.get("descartadas", [])),
      fingerprint=str(datos.get("fingerprint", "")),
  )


def cargar_galeria(
    dataset_dir: Path | str | None = None,
    cache_path: Path | str | None = None,
    *,
    force: bool = False,
) -> Galeria:
  """Carga los embeddings del dataset, usando caché si no cambió nada."""
  dataset_dir = Path(dataset_dir or config.DATASET_DIR)
  cache_path = Path(cache_path or config.CACHE_PATH)
  fingerprint = _huella_dataset(dataset_dir)

  if not force:
    datos = _leer_cache(cache_path)
    if (
        datos
        and datos.get("version") == 1
        and datos.get("modelo") == config.MODELO
        and datos.get("fingerprint") == fingerprint
    ):
      galeria = _galeria_desde_cache(datos)
      logger.info(
          "Galería cargada desde caché: %s embeddings, %s personas",
          len(galeria),
          len(galeria.personas),
      )
      return galeria

  imagenes = list(_iterar_imagenes(dataset_dir))
  if not imagenes:
    galeria = Galeria(fingerprint=fingerprint)
    _guardar_cache(
        cache_path,
        {
            "version": 1,
            "modelo": config.MODELO,
            "fingerprint": fingerprint,
            "items": [],
            "descartadas": [],
        },
    )
    logger.info("El dataset está vacío: %s", dataset_dir)
    return galeria

  try:
    import face_recognition
  except ImportError as exc:  # pragma: no cover - depende del entorno
    raise RuntimeError(
        "Falta la librería face_recognition. "
        "Instale las dependencias con: pip install -r requirements.txt"
    ) from exc

  nombres: list[str] = []
  encodings: list[list[float]] = []
  rutas: list[str] = []
  carpetas: list[str] = []
  descartadas: list[dict] = []

  for carpeta, archivo in imagenes:
    ruta_relativa = archivo.relative_to(dataset_dir).as_posix()
    try:
      imagen = face_recognition.load_image_file(str(archivo))
      ubicaciones = face_recognition.face_locations(imagen)
      if not ubicaciones:
        descartadas.append({"ruta": ruta_relativa, "motivo": "sin_rostro"})
        continue
      if len(ubicaciones) > 1:
        descartadas.append({"ruta": ruta_relativa, "motivo": "multiples_rostros"})
        continue
      codificaciones = face_recognition.face_encodings(
          imagen, known_face_locations=ubicaciones, num_jitters=1
      )
      if len(codificaciones) != 1:
        descartadas.append({"ruta": ruta_relativa, "motivo": "embedding_invalido"})
        continue
    except Exception as exc: # una imagen corrupta no debe tumbar el arranque
      logger.warning("No se pudo procesar %s: %s", archivo, exc)
      descartadas.append(
          {"ruta": ruta_relativa, "motivo": f"error: {type(exc).__name__}"}
      )
      continue

    nombre = carpeta.name.replace("_", " ").strip()
    nombres.append(nombre)
    encodings.append([float(valor) for valor in codificaciones[0]])
    rutas.append(ruta_relativa)
    carpetas.append(carpeta.name)

  galeria = Galeria(
      nombres=nombres,
      encodings=encodings,
      rutas=rutas,
      carpetas=carpetas,
      descartadas=descartadas,
      fingerprint=fingerprint,
  )
  _guardar_cache(
      cache_path,
      {
          "version": 1,
          "modelo": config.MODELO,
          "fingerprint": fingerprint,
          "items": [
              {
                  "nombre": nombre,
                  "carpeta": carpeta,
                  "ruta": ruta,
                  "encoding": encoding,
              }
              for nombre, carpeta, ruta, encoding in zip(
                  nombres, carpetas, rutas, encodings
              )
          ],
          "descartadas": descartadas,
      },
  )
  logger.info(
      "Galería cargada: %s embeddings, %s personas, %s imágenes descartadas",
      len(galeria),
      len(galeria.personas),
      len(galeria.descartadas),
  )
  return galeria


# ---------------------------------------------------------------------------
# Comparación
# ---------------------------------------------------------------------------
def distancia_euclidiana(a: list[float], b: list[float]) -> float:
  if len(a) != len(b):
    raise ValueError("Los embeddings tienen dimensiones distintas.")
  return math.sqrt(sum((float(x) - float(y)) ** 2 for x, y in zip(a, b)))


def reconocer_rostro(
    face_encoding: list[float] | None,
    galeria: Galeria,
    umbral: float | None = None,
    margen: float | None = None,
) -> ResultadoReconocimiento:
  umbral = config.UMBRAL if umbral is None else float(umbral)
  margen = config.MARGEN_MINIMO if margen is None else float(margen)

  if face_encoding is None:
    return ResultadoReconocimiento(
        "Desconocido", "Denegado", 0.0, umbral=umbral, motivo="sin_embedding"
    )
  if not galeria.encodings or not galeria.nombres:
    return ResultadoReconocimiento(
        "Desconocido", "Denegado", 0.0, umbral=umbral, motivo="galeria_vacia"
    )

  por_persona: dict[str, float] = {}
  for nombre, encoding in zip(galeria.nombres, galeria.encodings):
    distancia = distancia_euclidiana(face_encoding, encoding)
    if nombre not in por_persona or distancia < por_persona[nombre]:
      por_persona[nombre] = distancia

  ordenados = sorted(por_persona.items(), key=lambda item: item[1])
  mejor_nombre, mejor_distancia = ordenados[0]
  segunda_distancia = ordenados[1][1] if len(ordenados) > 1 else None
  similitud = max(0.0, min(100.0, (1.0 - mejor_distancia) * 100.0))

  if mejor_distancia > umbral:
    return ResultadoReconocimiento(
        "Desconocido",
        "Denegado",
        similitud,
        mejor_distancia,
        umbral,
        "baja_similitud",
    )

  if (
      segunda_distancia is not None
      and (segunda_distancia - mejor_distancia) < margen
  ):
    return ResultadoReconocimiento(
        "Desconocido",
        "Denegado",
        similitud,
        mejor_distancia,
        umbral,
        "ambiguo",
    )

  return ResultadoReconocimiento(
      mejor_nombre,
      "Autorizado",
      similitud,
      mejor_distancia,
      umbral,
      None,
  )


# ---------------------------------------------------------------------------
# Seguimiento y eventos
# ---------------------------------------------------------------------------
def _iou(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> float:
  ax1, ay1, ax2, ay2 = a
  bx1, by1, bx2, by2 = b
  inter_x1 = max(ax1, bx1)
  inter_y1 = max(ay1, by1)
  inter_x2 = min(ax2, bx2)
  inter_y2 = min(ay2, by2)
  ancho = max(0, inter_x2 - inter_x1)
  alto = max(0, inter_y2 - inter_y1)
  interseccion = ancho * alto
  if interseccion <= 0:
    return 0.0
  area_a = max(0, ax2 - ax1) * max(0, ay2 - ay1)
  area_b = max(0, bx2 - bx1) * max(0, ay2 - by1)
  union = area_a + area_b - interseccion
  return interseccion / union if union > 0 else 0.0


class RastreadorRostros:
  """Asigna un track a cada rostro y emite un evento por acceso confirmado."""

  def __init__(
      self,
      *,
      tiempo_confirmacion: float = config.TIEMPO_CONFIRMACION,
      cooldown: int = config.COOLDOWN_EVENTO,
      tiempo_olvido: float = config.TIEMPO_OLVIDO,
      iou_minimo: float = 0.25,
  ) -> None:
    self.tiempo_confirmacion = float(tiempo_confirmacion)
    self.cooldown = float(cooldown)
    self.tiempo_olvido = float(tiempo_olvido)
    self.iou_minimo = float(iou_minimo)
    self.tracks: list[RostroSeguido] = []
    self.ultimo_evento: dict[tuple[str, str], float] = {}
    self._siguiente_id = 0

  def reiniciar(self) -> None:
    self.tracks.clear()
    self.ultimo_evento.clear()
    self._siguiente_id = 0

  def actualizar(
      self,
      detecciones: list[tuple[tuple[int, int, int, int], ResultadoReconocimiento]],
      ahora: float | None = None,
  ) -> tuple[list[RostroSeguido], list[EventoAcceso]]:
    ahora = time.monotonic() if ahora is None else float(ahora)
    for track in self.tracks:
      track.visto_este_frame = False

    usados: set[int] = set()
    for bbox, resultado in detecciones:
      mejor_track: RostroSeguido | None = None
      mejor_iou = 0.0
      for track in self.tracks:
        if track.track_id in usados:
          continue
        coincidencia = _iou(bbox, track.bbox)
        if coincidencia > mejor_iou:
          mejor_iou = coincidencia
          mejor_track = track

      if mejor_track is not None and mejor_iou >= self.iou_minimo:
        if (
            mejor_track.resultado.nombre != resultado.nombre
            or mejor_track.resultado.estado != resultado.estado
        ):
          mejor_track.inicio_estado = ahora
          mejor_track.confirmado = False
          mejor_track.evento_emitido = False
        mejor_track.bbox = bbox
        mejor_track.resultado = resultado
        mejor_track.ultimo_visto = ahora
        mejor_track.visto_este_frame = True
        usados.add(mejor_track.track_id)
      else:
        self._siguiente_id += 1
        nuevo = RostroSeguido(
            track_id=self._siguiente_id,
            bbox=bbox,
            resultado=resultado,
            inicio_estado=ahora,
            ultimo_visto=ahora,
            visto_este_frame=True,
        )
        self.tracks.append(nuevo)
        usados.add(nuevo.track_id)

    self.tracks = [
        track
        for track in self.tracks
        if ahora - track.ultimo_visto <= self.tiempo_olvido
    ]

    eventos: list[EventoAcceso] = []
    for track in self.tracks:
      if track.confirmado:
        continue
      # No confirmar un rostro que ya no está en el frame actual: evita
      # registrar eventos de seguimientos "fantasma" que solo siguen en la
      # lista porque aún no vence su tiempo de olvido.
      if not track.visto_este_frame:
        continue
      if ahora - track.inicio_estado < self.tiempo_confirmacion:
        continue

      track.confirmado = True
      if track.evento_emitido:
        continue
      track.evento_emitido = True

      clave = (track.resultado.nombre, track.resultado.estado)
      ultimo = self.ultimo_evento.get(clave)
      if ultimo is not None and (ahora - ultimo) < self.cooldown:
        continue
      self.ultimo_evento[clave] = ahora
      eventos.append(
          EventoAcceso(
              track_id=track.track_id,
              resultado=track.resultado,
              bbox=track.bbox,
              fecha=ahora,
          )
      )

    seguidos = [track for track in self.tracks if track.visto_este_frame]
    return seguidos, eventos