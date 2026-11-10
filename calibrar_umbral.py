"""Calcula un umbral de distancia recomendado a partir del dataset local."""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import config
import recognition


def _percentil(valores: list[float], p: float) -> float:
  if not valores:
    return float("nan")
  ordenados = sorted(valores)
  indice = min(len(ordenados) - 1, max(0, int(round((len(ordenados) - 1) * p))))
  return ordenados[indice]


def main() -> int:
  parser = argparse.ArgumentParser(
      description="Calibra el umbral de reconocimiento con las fotos del dataset."
  )
  parser.add_argument(
      "--json",
      type=Path,
      help="Guardar el resultado de la calibración en un archivo JSON.",
  )
  args = parser.parse_args()

  print(f"Dataset: {config.DATASET_DIR}")
  galeria = recognition.cargar_galeria(config.DATASET_DIR, config.CACHE_PATH)
  if not galeria.encodings:
    print("No hay embeddings válidos. Registre personas y vuelva a intentar.")
    return 1

  print(
      f"Embeddings: {len(galeria)} | Personas: {len(galeria.personas)}"
  )
  if galeria.descartadas:
    print(f"Imágenes descartadas: {len(galeria.descartadas)}")
    for item in galeria.descartadas:
      print(f"  - {item['ruta']}: {item['motivo']}")

  genuinas: list[float] = []
  impostoras: list[float] = []
  for i in range(len(galeria.encodings)):
    for j in range(i + 1, len(galeria.encodings)):
      distancia = recognition.distancia_euclidiana(
          galeria.encodings[i], galeria.encodings[j]
      )
      if galeria.nombres[i] == galeria.nombres[j]:
        genuinas.append(distancia)
      else:
        impostoras.append(distancia)

  if not genuinas or not impostoras:
    print(
        "Se necesitan al menos dos personas con dos fotos válidas cada una "
        "para calcular distancias genuinas e impostoras."
    )
    return 1

  print(f"\nDistancias genuinas ({len(genuinas)} pares):")
  print(
      f"  mín={min(genuinas):.3f}  mediana={statistics.median(genuinas):.3f}  "
      f"máx={max(genuinas):.3f}"
  )
  print(f"Distancias impostoras ({len(impostoras)} pares):")
  print(
      f"  mín={min(impostoras):.3f}  mediana={statistics.median(impostoras):.3f}  "
      f"máx={max(impostoras):.3f}"
  )

  mejor_eer = None
  mejor_far_1 = None
  for indice in range(200, 801):
    umbral = indice / 1000.0
    far = sum(1 for d in impostoras if d <= umbral) / len(impostoras)
    frr = sum(1 for d in genuinas if d > umbral) / len(genuinas)
    diferencia = abs(far - frr)
    if mejor_eer is None or diferencia < mejor_eer[0]:
      mejor_eer = (diferencia, umbral, far, frr)
    if far <= 0.01 and (mejor_far_1 is None or frr < mejor_far_1[0]):
      mejor_far_1 = (frr, umbral, far)

  print("\nResultados:")
  if mejor_eer:
    _, umbral, far, frr = mejor_eer
    print(
        f"  EER aproximado: umbral={umbral:.3f}  FAR={far * 100:.2f}%  "
        f"FRR={frr * 100:.2f}%"
    )
  recomendado = config.UMBRAL
  if mejor_far_1:
    _, umbral, far = mejor_far_1
    print(
        f"  FAR <= 1%: umbral={umbral:.3f}  FAR={far * 100:.2f}%  "
        f"FRR={mejor_far_1[0] * 100:.2f}%"
    )
    recomendado = umbral
  print(f"  Umbral actual en config.py: {config.UMBRAL:.3f}")
  print(f"  Umbral sugerido para FAR <= 1%: {recomendado:.3f}")

  if args.json:
    datos = {
        "dataset": str(config.DATASET_DIR),
        "embeddings": len(galeria),
        "personas": len(galeria.personas),
        "genuinas": {
            "n": len(genuinas),
            "min": min(genuinas),
            "mediana": statistics.median(genuinas),
            "max": max(genuinas),
            "p95": _percentil(genuinas, 0.95),
        },
        "impostoras": {
            "n": len(impostoras),
            "min": min(impostoras),
            "mediana": statistics.median(impostoras),
            "max": max(impostoras),
            "p05": _percentil(impostoras, 0.05),
        },
        "umbral_actual": config.UMBRAL,
        "umbral_sugerido": recomendado,
    }
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(
        json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"  Resultado guardado en: {args.json}")

  return 0


if __name__ == "__main__":
  raise SystemExit(main())
