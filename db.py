"""Acceso a la base de datos SQLite del sistema ETITC.

La migración es no destructiva: conserva las filas históricas, añade columnas
nuevas y marca los registros de prueba con ``origen='prueba'``. Nunca borra
información automáticamente.
"""

from __future__ import annotations

import datetime
import hashlib
import hmac
import json
import logging
import os
import re
import sqlite3
import unicodedata
from contextlib import contextmanager
from pathlib import Path

import config

logger = logging.getLogger(__name__)

DB_PATH = config.DB_PATH

SCHEMA_VERSION = 2

ESTADOS_VALIDOS = {"Autorizado", "Denegado"}
ORIGENES_VALIDOS = {"real", "prueba"}

# Tipos de persona que se pueden registrar en el sistema.
TIPOS_PERSONA = ("estudiante", "administrativo", "personal de aseo")

# Etiquetas que, por el contenido y las fechas de la base actual, parecen
# provenir de pruebas o demostraciones. Se conservan, pero se ocultan de los
# reportes por defecto. Se pueden cambiar con clasificar_registros.py.
ETIQUETAS_PRUEBA = {
    "Estudiante Autorizado",
    "Z",
    "A",
    "E",
    "mimi",
    "qwert",
}
# Personas que aparecen con varios nombres en la base actual. Solo se usa
# durante la migración de registros históricos.
ALIAS_PERSONAS = {
    "ANDRES": "Andres Carrillo",
    "Andres_Julian_Carrillo_Restrepo": "Andres Carrillo",
}



ETIQUETAS_DESCONOCIDO = {
    "Desconocido",
    "Desconocido / Alerta",
    "Desconocido_Alerta",
    "Desconocido/Alerta",
}


# ---------------------------------------------------------------------------
# Utilidades de nombres
# ---------------------------------------------------------------------------
def normalizar_nombre(nombre: str) -> str:
  """Devuelve una clave comparable: sin acentos, minúsculas y sin signos."""
  texto = unicodedata.normalize("NFKD", (nombre or "").strip())
  texto = "".join(c for c in texto if not unicodedata.combining(c))
  texto = re.sub(r"[^a-z0-9]+", " ", texto.lower())
  return texto.strip()


def nombre_visible(etiqueta: str) -> str:
  etiqueta = (etiqueta or "").strip()
  return ALIAS_PERSONAS.get(etiqueta, etiqueta.replace("_", " ").strip())


def _carpeta_para(nombre: str) -> str:
  """Busca la carpeta real del dataset cuyo nombre coincide con la persona."""
  objetivo = normalizar_nombre(nombre)
  if objetivo and config.DATASET_DIR.exists():
    try:
      for carpeta in config.DATASET_DIR.iterdir():
        if not carpeta.is_dir() or carpeta.name.startswith("."):
          continue
        if normalizar_nombre(carpeta.name.replace("_", " ")) == objetivo:
          return carpeta.name
    except OSError:
      pass
  limpio = re.sub(r"[^A-Za-z0-9_-]+", "_", nombre or "").strip("_")
  return re.sub(r"_+", "_", limpio)[:60]


def _limpiar_opcional(valor: str | None) -> str | None:
  texto = (valor or "").strip()
  return texto or None


def _fecha_ahora() -> str:
  return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _parsear_fecha(valor: str | None) -> datetime.datetime | None:
  if not valor:
    return None
  try:
    return datetime.datetime.strptime(str(valor), "%Y-%m-%d %H:%M:%S")
  except ValueError:
    return None


# ---------------------------------------------------------------------------
# Conexión y versiones
# ---------------------------------------------------------------------------
@contextmanager
def conexion():
  """Abre una conexión con filas tipo ``sqlite3.Row`` y cierre garantizado."""
  DB_PATH.parent.mkdir(parents=True, exist_ok=True)
  conn = sqlite3.connect(str(DB_PATH), timeout=15)
  conn.row_factory = sqlite3.Row
  conn.execute("PRAGMA foreign_keys = ON")
  conn.execute("PRAGMA busy_timeout = 5000")
  try:
    yield conn
    conn.commit()
  except Exception:
    conn.rollback()
    raise
  finally:
    conn.close()


def _version_en_conexion(conn: sqlite3.Connection) -> int:
  tabla = conn.execute(
      "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_version'"
  ).fetchone()
  if not tabla:
    return 0
  fila = conn.execute("SELECT MAX(version) FROM schema_version").fetchone()
  return int(fila[0] or 0)


def _version_actual(ruta: Path | None = None) -> int:
  ruta = Path(ruta) if ruta is not None else DB_PATH
  if not ruta.exists() or ruta.stat().st_size == 0:
    return 0
  try:
    conn = sqlite3.connect(str(ruta), timeout=5)
    conn.row_factory = sqlite3.Row
    try:
      return _version_en_conexion(conn)
    finally:
      conn.close()
  except sqlite3.DatabaseError:
    logger.exception("No se pudo leer la versión de la base de datos")
    return 0


def hacer_backup() -> Path | None:
  """Copia la BD a .backups y devuelve la ruta del respaldo.

  Se usa la API de respaldo de SQLite para obtener una copia consistente
  incluso si la base tiene escrituras recientes o un diario pendiente.
  """
  if not DB_PATH.exists():
    return None
  config.BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
  sello = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
  destino = config.BACKUPS_DIR / f"accesos-{sello}.db"
  contador = 1
  while destino.exists():
    destino = config.BACKUPS_DIR / f"accesos-{sello}-{contador}.db"
    contador += 1

  origen = None
  copia = None
  try:
    origen = sqlite3.connect(str(DB_PATH))
    copia = sqlite3.connect(str(destino))
    origen.backup(copia)
  except Exception:
    logger.exception("No se pudo crear el respaldo de la base de datos")
    if destino.exists():
      try:
        destino.unlink()
      except OSError:
        pass
    return None
  finally:
    if copia is not None:
      copia.close()
    if origen is not None:
      origen.close()
  return destino


# ---------------------------------------------------------------------------
# Esquema y migraciones
# ---------------------------------------------------------------------------
def _crear_tablas(conn: sqlite3.Connection) -> None:
  conn.execute(
      """
      CREATE TABLE IF NOT EXISTS schema_version (
          version INTEGER PRIMARY KEY,
          aplicada_en TEXT NOT NULL
      )
      """
  )
  conn.execute(
      """
      CREATE TABLE IF NOT EXISTS personas (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          nombre TEXT NOT NULL,
          nombre_normalizado TEXT NOT NULL UNIQUE,
          dataset_folder TEXT UNIQUE,
          activo INTEGER NOT NULL DEFAULT 1,
          creado_en TEXT NOT NULL,
          tipo_persona TEXT,
          facultad TEXT,
          carrera TEXT,
          cargo TEXT,
          documento TEXT
      )
      """
  )
  conn.execute(
      """
      CREATE TABLE IF NOT EXISTS registros_acceso (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          usuario TEXT NOT NULL,
          estado TEXT NOT NULL,
          confianza REAL NOT NULL,
          fecha_hora TEXT NOT NULL,
          persona_id INTEGER REFERENCES personas(id),
          etiqueta_original TEXT,
          origen TEXT NOT NULL DEFAULT 'real',
          estado_normalizado TEXT,
          motivo TEXT,
          distancia REAL,
          umbral REAL,
          modelo TEXT,
          evento TEXT DEFAULT 'registro',
          track_id TEXT
      )
      """
  )
  conn.execute(
      """
      CREATE TABLE IF NOT EXISTS operadores (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          usuario TEXT NOT NULL UNIQUE,
          password_hash TEXT NOT NULL,
          salt TEXT NOT NULL,
          rol TEXT NOT NULL DEFAULT 'operador',
          activo INTEGER NOT NULL DEFAULT 1,
          intentos_fallidos INTEGER NOT NULL DEFAULT 0,
          bloqueado_hasta TEXT,
          creado_en TEXT NOT NULL,
          actualizado_en TEXT NOT NULL
      )
      """
  )
  conn.execute(
      """
      CREATE TABLE IF NOT EXISTS auditoria_operador (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          usuario TEXT NOT NULL,
          accion TEXT NOT NULL,
          detalle TEXT,
          fecha_hora TEXT NOT NULL
      )
      """
  )


def _agregar_columnas(conn: sqlite3.Connection) -> None:
  columnas = {
      fila["name"] for fila in conn.execute("PRAGMA table_info(registros_acceso)")
  }
  nuevas = {
      "persona_id": "INTEGER REFERENCES personas(id)",
      "etiqueta_original": "TEXT",
      "origen": "TEXT NOT NULL DEFAULT 'real'",
      "estado_normalizado": "TEXT",
      "motivo": "TEXT",
      "distancia": "REAL",
      "umbral": "REAL",
      "modelo": "TEXT",
      "evento": "TEXT DEFAULT 'registro'",
      "track_id": "TEXT",
  }
  for nombre, definicion in nuevas.items():
    if nombre not in columnas:
      conn.execute(f"ALTER TABLE registros_acceso ADD COLUMN {nombre} {definicion}")


def _agregar_columnas_personas(conn: sqlite3.Connection) -> None:
  columnas = {fila["name"] for fila in conn.execute("PRAGMA table_info(personas)")}
  nuevas = {
      "tipo_persona": "TEXT",
      "facultad": "TEXT",
      "carrera": "TEXT",
      "cargo": "TEXT",
      "documento": "TEXT",
  }
  for nombre, definicion in nuevas.items():
    if nombre not in columnas:
      conn.execute(f"ALTER TABLE personas ADD COLUMN {nombre} {definicion}")


def _crear_indices(conn: sqlite3.Connection) -> None:
  conn.execute(
      "CREATE INDEX IF NOT EXISTS idx_registros_fecha "
      "ON registros_acceso(fecha_hora)"
  )
  conn.execute(
      "CREATE INDEX IF NOT EXISTS idx_registros_usuario "
      "ON registros_acceso(usuario)"
  )
  conn.execute(
      "CREATE INDEX IF NOT EXISTS idx_registros_persona "
      "ON registros_acceso(persona_id)"
  )
  conn.execute(
      "CREATE INDEX IF NOT EXISTS idx_personas_tipo "
      "ON personas(tipo_persona)"
  )
  conn.execute(
      "CREATE INDEX IF NOT EXISTS idx_auditoria_fecha "
      "ON auditoria_operador(fecha_hora)"
  )


def _migrar_v1(conn: sqlite3.Connection) -> None:
  """Clasifica los registros históricos sin borrar nada."""
  filas = conn.execute(
      "SELECT id, usuario, estado, confianza FROM registros_acceso"
  ).fetchall()

  for fila in filas:
    etiqueta = (fila["usuario"] or "").strip()
    estado_original = (fila["estado"] or "").strip()
    es_prueba = etiqueta in ETIQUETAS_PRUEBA
    origen = "prueba" if es_prueba else "real"
    estado_normalizado = "Autorizado" if estado_original == "Autorizado" else "Denegado"

    if estado_normalizado == "Autorizado":
      motivo = None
    elif estado_original == "Desconocido / Alerta":
      motivo = "historico"
    else:
      motivo = "sin_coincidencia"

    persona_id = None
    if not es_prueba and etiqueta not in ETIQUETAS_DESCONOCIDO:
      persona = nombre_visible(etiqueta)
      persona_id = _obtener_o_crear_persona(
          conn, persona, _carpeta_para(persona)
      )

    conn.execute(
        """
        UPDATE registros_acceso
        SET etiqueta_original = COALESCE(etiqueta_original, ?),
            origen = ?,
            estado_normalizado = ?,
            motivo = ?,
            persona_id = COALESCE(persona_id, ?)
        WHERE id = ?
        """,
        (
            etiqueta,
            origen,
            estado_normalizado,
            motivo,
            persona_id,
            fila["id"],
        ),
    )


def _obtener_o_crear_persona(
    conn: sqlite3.Connection,
    nombre: str,
    dataset_folder: str | None = None,
) -> int | None:
  nombre = (nombre or "").strip()
  normalizado = normalizar_nombre(nombre)
  if not normalizado:
    return None

  fila = conn.execute(
      "SELECT id, dataset_folder FROM personas WHERE nombre_normalizado = ?",
      (normalizado,),
  ).fetchone()
  if fila:
    if dataset_folder and not fila["dataset_folder"]:
      conn.execute(
          "UPDATE personas SET dataset_folder = ? WHERE id = ?",
          (dataset_folder, fila["id"]),
      )
    return int(fila["id"])

  try:
    cursor = conn.execute(
        """
        INSERT INTO personas (nombre, nombre_normalizado, dataset_folder, creado_en)
        VALUES (?, ?, ?, ?)
        """,
        (
            nombre,
            normalizado,
            _limpiar_opcional(dataset_folder),
            _fecha_ahora(),
        ),
    )
    return int(cursor.lastrowid)
  except sqlite3.IntegrityError:
    fila = conn.execute(
        "SELECT id FROM personas WHERE nombre_normalizado = ?",
        (normalizado,),
    ).fetchone()
    if fila:
      return int(fila["id"])
    if dataset_folder:
      fila = conn.execute(
          "SELECT id FROM personas WHERE dataset_folder = ?",
          (dataset_folder,),
      ).fetchone()
      if fila:
        conn.execute(
            "UPDATE personas SET nombre = ?, nombre_normalizado = ? WHERE id = ?",
            (nombre, normalizado, fila["id"]),
        )
        return int(fila["id"])
    logger.warning("No se pudo registrar la persona %s", nombre)
    return None


def _aplicar_metadata_persona(
    conn: sqlite3.Connection, persona_id: int, carpeta: Path
) -> None:
  """Recupera tipo y datos desde ``metadata.json`` si el archivo existe.

  Sirve cuando se copia solo el dataset a otro equipo: la base nueva puede
  reconstruir el tipo de persona sin pedirle al operador que lo vuelva a escribir.
  """
  ruta = carpeta / "metadata.json"
  if not ruta.exists():
    return
  try:
    datos = json.loads(ruta.read_text(encoding="utf-8"))
  except (OSError, ValueError):
    logger.warning("metadata.json inválido en la carpeta %s", carpeta.name)
    return
  if not isinstance(datos, dict):
    return

  tipo = str(datos.get("tipo_persona") or "").strip().lower()
  if tipo not in TIPOS_PERSONA:
    return

  facultad = (
      str(datos.get("facultad") or "").strip() or None
      if tipo == "estudiante"
      else None
  )
  carrera = (
      str(datos.get("carrera") or "").strip() or None
      if tipo == "estudiante"
      else None
  )
  cargo = (
      str(datos.get("cargo") or "").strip() or None
      if tipo == "administrativo"
      else None
  )
  documento = (
      str(datos.get("documento") or "").strip() or None
      if tipo == "personal de aseo"
      else None
  )
  if tipo == "estudiante" and not (facultad and carrera):
    return
  if tipo == "administrativo" and not cargo:
    return
  if tipo == "personal de aseo" and not documento:
    return

  conn.execute(
      """
      UPDATE personas
      SET tipo_persona = ?, facultad = ?, carrera = ?, cargo = ?, documento = ?
      WHERE id = ?
      """,
      (tipo, facultad, carrera, cargo, documento, persona_id),
  )


def inicializar_base_datos(hacer_respaldo: bool = True) -> dict:
  """Crea o migra la base de datos de forma idempotente."""
  version_antes = _version_actual()
  respaldo = None
  if (
      version_antes < SCHEMA_VERSION
      and hacer_respaldo
      and DB_PATH.exists()
      and DB_PATH.stat().st_size > 0
  ):
    respaldo = hacer_backup()

  with conexion() as conn:
    _crear_tablas(conn)
    _agregar_columnas(conn)
    _agregar_columnas_personas(conn)
    _crear_indices(conn)

    version = _version_en_conexion(conn)
    if version < 1:
      _migrar_v1(conn)
      conn.execute(
          "INSERT INTO schema_version (version, aplicada_en) VALUES (1, ?)",
          (_fecha_ahora(),),
      )
      version = 1
      logger.info("Base de datos migrada a la versión 1")
    if version < 2:
      conn.execute(
          "INSERT INTO schema_version (version, aplicada_en) VALUES (2, ?)",
          (_fecha_ahora(),),
      )
      version = 2
      logger.info(
          "Base de datos migrada a la versión 2 (tipo y datos de personas)"
      )
    elif version > SCHEMA_VERSION:
      logger.warning(
          "La base de datos tiene una versión más nueva (%s) que este programa (%s)",
          version,
          SCHEMA_VERSION,
      )

  return {"version": max(version, 1), "backup": respaldo}


# ---------------------------------------------------------------------------
# Personas
# ---------------------------------------------------------------------------
def guardar_persona(
    nombre: str,
    tipo_persona: str,
    *,
    facultad: str | None = None,
    carrera: str | None = None,
    cargo: str | None = None,
    documento: str | None = None,
    dataset_folder: str | None = None,
) -> int:
  """Crea o actualiza una persona con su tipo y datos específicos.

  El tipo se guarda en minúsculas y debe ser uno de ``TIPOS_PERSONA``. Los
  campos que no aplican al tipo se guardan como ``NULL`` para no mezclar datos
  de estudiantes con los de administrativos o personal de aseo.
  """
  nombre = (nombre or "").strip()
  normalizado = normalizar_nombre(nombre)
  if not nombre or not normalizado:
    raise ValueError("El nombre de la persona no puede estar vacío.")

  tipo_persona = (tipo_persona or "").strip().lower()
  if tipo_persona not in TIPOS_PERSONA:
    raise ValueError(
        "Tipo de persona inválido. Use: " + ", ".join(TIPOS_PERSONA) + "."
    )

  facultad = _limpiar_opcional(facultad) if tipo_persona == "estudiante" else None
  carrera = _limpiar_opcional(carrera) if tipo_persona == "estudiante" else None
  cargo = _limpiar_opcional(cargo) if tipo_persona == "administrativo" else None
  documento = (
      _limpiar_opcional(documento) if tipo_persona == "personal de aseo" else None
  )

  requeridos = {
      "estudiante": (("facultad", facultad), ("carrera", carrera)),
      "administrativo": (("cargo", cargo),),
      "personal de aseo": (("documento", documento),),
  }[tipo_persona]
  faltantes = [campo for campo, valor in requeridos if not valor]
  if faltantes:
    raise ValueError(
        "Faltan datos obligatorios para el tipo "
        f"'{tipo_persona}': " + ", ".join(faltantes) + "."
    )

  with conexion() as conn:
    persona_id = _obtener_o_crear_persona(conn, nombre, dataset_folder)
    if not persona_id:
      raise ValueError("No se pudo crear la persona en la base de datos.")

    conn.execute(
        """
        UPDATE personas
        SET nombre = ?,
            tipo_persona = ?,
            facultad = ?,
            carrera = ?,
            cargo = ?,
            documento = ?,
            dataset_folder = COALESCE(?, dataset_folder),
            activo = 1
        WHERE id = ?
        """,
        (
            nombre,
            tipo_persona,
            facultad,
            carrera,
            cargo,
            documento,
            _limpiar_opcional(dataset_folder),
            persona_id,
        ),
    )
    _auditar(
        conn,
        "sistema",
        "persona_datos_guardados",
        f"{nombre} ({tipo_persona})",
    )
    return persona_id


def listar_personas() -> list[sqlite3.Row]:
  """Devuelve las personas registradas con sus datos y total de accesos."""
  with conexion() as conn:
    return list(
        conn.execute(
            """
            SELECT
                p.id,
                p.nombre,
                COALESCE(p.tipo_persona, '') AS tipo_persona,
                COALESCE(p.facultad, '') AS facultad,
                COALESCE(p.carrera, '') AS carrera,
                COALESCE(p.cargo, '') AS cargo,
                COALESCE(p.documento, '') AS documento,
                COALESCE(p.dataset_folder, '') AS dataset_folder,
                p.activo,
                p.creado_en,
                (
                    SELECT COUNT(*)
                    FROM registros_acceso r
                    WHERE r.persona_id = p.id
                ) AS total_registros
            FROM personas p
            ORDER BY p.nombre COLLATE NOCASE
            """
        ).fetchall()
    )


def sincronizar_personas_con_dataset() -> int:
  """Registra en personas las carpetas reales del dataset."""
  if not config.DATASET_DIR.exists():
    return 0
  creadas = 0
  with conexion() as conn:
    for carpeta in sorted(
        config.DATASET_DIR.iterdir(), key=lambda p: p.name.lower()
    ):
      if not carpeta.is_dir() or carpeta.name.startswith("."):
        continue
      nombre = carpeta.name.replace("_", " ").strip()
      antes = conn.execute(
          "SELECT id FROM personas WHERE nombre_normalizado = ?",
          (normalizar_nombre(nombre),),
      ).fetchone()
      persona_id = _obtener_o_crear_persona(conn, nombre, carpeta.name)
      if persona_id:
        _aplicar_metadata_persona(conn, persona_id, carpeta)
      if not antes:
        creadas += 1
  return creadas


# ---------------------------------------------------------------------------
# Operadores
# ---------------------------------------------------------------------------
def _hash_password(password: str, salt: bytes) -> bytes:
  # dklen=32 conserva compatibilidad con los hashes ya guardados en accesos.db.
  return hashlib.scrypt(
      password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1, dklen=32
  )


def _verificar_password(password: str, hash_guardado: str, salt: bytes) -> bool:
  try:
    calculado = _hash_password(password, salt)
    return hmac.compare_digest(calculado, bytes.fromhex(hash_guardado))
  except (ValueError, TypeError):
    return False


def _auditar(
    conn: sqlite3.Connection,
    usuario: str,
    accion: str,
    detalle: str = "",
) -> None:
  conn.execute(
      """
      INSERT INTO auditoria_operador (usuario, accion, detalle, fecha_hora)
      VALUES (?, ?, ?, ?)
      """,
      ((usuario or "sistema").strip() or "sistema", accion, detalle, _fecha_ahora()),
  )


def registrar_auditoria(usuario: str, accion: str, detalle: str = "") -> None:
  with conexion() as conn:
    _auditar(conn, usuario, accion, detalle)


def crear_operador(
    usuario: str, password: str, rol: str = "operador"
) -> None:
  usuario = (usuario or "").strip()
  if not usuario:
    raise ValueError("El usuario no puede estar vacío.")
  if len(password or "") < config.MIN_LONGITUD_PASSWORD:
    raise ValueError(
        f"La contraseña debe tener al menos {config.MIN_LONGITUD_PASSWORD} caracteres."
    )

  salt = os.urandom(16)
  hash_password = _hash_password(password, salt)
  ahora = _fecha_ahora()

  with conexion() as conn:
    conn.execute(
        """
        INSERT INTO operadores (
            usuario, password_hash, salt, rol, activo,
            intentos_fallidos, bloqueado_hasta, creado_en, actualizado_en
        ) VALUES (?, ?, ?, ?, 1, 0, NULL, ?, ?)
        ON CONFLICT(usuario) DO UPDATE SET
            password_hash = excluded.password_hash,
            salt = excluded.salt,
            rol = excluded.rol,
            activo = 1,
            intentos_fallidos = 0,
            bloqueado_hasta = NULL,
            actualizado_en = excluded.actualizado_en
        """,
        (
            usuario,
            hash_password.hex(),
            salt.hex(),
            (rol or "operador").strip() or "operador",
            ahora,
            ahora,
        ),
    )
    _auditar(conn, usuario, "operador_creado_actualizado", f"rol={rol}")


def autenticar_operador(usuario: str, password: str) -> tuple[bool, str]:
  """Valida credenciales y devuelve ``(ok, rol_o_mensaje)``."""
  usuario = (usuario or "").strip()
  if not usuario or not password:
    return False, "Ingrese usuario y contraseña."

  with conexion() as conn:
    fila = conn.execute(
        "SELECT * FROM operadores WHERE usuario = ?", (usuario,)
    ).fetchone()
    if not fila:
      _auditar(conn, usuario, "login_fallido", "usuario inexistente")
      return False, "Usuario o contraseña incorrectos."
    if not fila["activo"]:
      _auditar(conn, usuario, "login_fallido", "operador inactivo")
      return False, "El operador está desactivado."

    ahora = datetime.datetime.now()
    bloqueado = _parsear_fecha(fila["bloqueado_hasta"])
    if bloqueado and bloqueado > ahora:
      restante = max(1, int((bloqueado - ahora).total_seconds()) + 1)
      return False, f"Cuenta bloqueada. Intente de nuevo en {restante} s."

    try:
      salt = bytes.fromhex(fila["salt"])
    except (ValueError, TypeError):
      _auditar(conn, usuario, "login_fallido", "salt inválido")
      return False, "El operador tiene datos de seguridad inválidos."
    if not _verificar_password(password, fila["password_hash"], salt):
      intentos = int(fila["intentos_fallidos"] or 0) + 1
      if intentos >= config.MAX_INTENTOS_LOGIN:
        hasta = ahora + datetime.timedelta(
            seconds=config.BLOQUEO_LOGIN_SEGUNDOS
        )
        conn.execute(
            """
            UPDATE operadores
            SET intentos_fallidos = 0, bloqueado_hasta = ?, actualizado_en = ?
            WHERE id = ?
            """,
            (hasta.strftime("%Y-%m-%d %H:%M:%S"), _fecha_ahora(), fila["id"]),
        )
        _auditar(conn, usuario, "login_fallido", "bloqueo temporal")
        return (
            False,
            "Demasiados intentos fallidos. Cuenta bloqueada por "
            f"{config.BLOQUEO_LOGIN_SEGUNDOS} segundos.",
        )
      conn.execute(
          """
          UPDATE operadores
          SET intentos_fallidos = ?, actualizado_en = ?
          WHERE id = ?
          """,
          (intentos, _fecha_ahora(), fila["id"]),
      )
      _auditar(conn, usuario, "login_fallido", "contraseña incorrecta")
      return False, "Usuario o contraseña incorrectos."

    conn.execute(
        """
        UPDATE operadores
        SET intentos_fallidos = 0, bloqueado_hasta = NULL, actualizado_en = ?
        WHERE id = ?
        """,
        (_fecha_ahora(), fila["id"]),
    )
    _auditar(conn, usuario, "login_ok", f"rol={fila['rol']}")
    return True, fila["rol"]


def hay_operadores() -> bool:
  with conexion() as conn:
    fila = conn.execute(
        "SELECT COUNT(*) FROM operadores WHERE activo = 1"
    ).fetchone()
    return bool(fila[0])


def desactivar_operador(usuario: str) -> bool:
  """Desactiva un operador sin borrarlo, conservando su historial."""
  usuario = (usuario or "").strip()
  if not usuario:
    return False
  with conexion() as conn:
    cursor = conn.execute(
        """
        UPDATE operadores
        SET activo = 0, actualizado_en = ?
        WHERE usuario = ?
        """,
        (_fecha_ahora(), usuario),
    )
    if cursor.rowcount:
      _auditar(conn, usuario, "operador_desactivado", "activo=0")
    return bool(cursor.rowcount)


def asegurar_operador_desde_entorno() -> bool:
  """Crea el operador desde el entorno solo si no hay ninguno activo.

  No debe sobrescribir la contraseña de un operador existente en cada arranque.
  """
  usuario = (os.getenv("ETITC_OPERADOR_USUARIO") or "").strip()
  password = os.getenv("ETITC_OPERADOR_PASSWORD") or ""
  if not usuario or not password:
    return False
  if hay_operadores():
    return False
  rol = (os.getenv("ETITC_OPERADOR_ROL") or "operador").strip() or "operador"
  try:
    crear_operador(usuario, password, rol)
    return True
  except Exception:
    logger.exception("No se pudo crear el operador desde el entorno")
    return False


# ---------------------------------------------------------------------------
# Registros de acceso
# ---------------------------------------------------------------------------
def registrar_evento(
    usuario: str,
    estado: str,
    confianza: float,
    *,
    distancia: float | None = None,
    umbral: float | None = None,
    motivo: str | None = None,
    evento: str = "registro",
    origen: str = "real",
    track_id: str | None = None,
    modelo: str | None = None,
) -> int:
  if estado not in ESTADOS_VALIDOS:
    estado = "Denegado"
  if origen not in ORIGENES_VALIDOS:
    origen = "real"

  usuario = (usuario or "Desconocido").strip() or "Desconocido"
  confianza = max(0.0, min(100.0, float(confianza)))
  estado_normalizado = "Autorizado" if estado == "Autorizado" else "Denegado"

  with conexion() as conn:
    persona_id = None
    if origen == "real" and usuario not in ETIQUETAS_DESCONOCIDO:
      persona_id = _obtener_o_crear_persona(
          conn, usuario, _carpeta_para(usuario)
      )

    cursor = conn.execute(
        """
        INSERT INTO registros_acceso (
            usuario, estado, confianza, fecha_hora, persona_id,
            etiqueta_original, origen, estado_normalizado, motivo,
            distancia, umbral, modelo, evento, track_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            usuario,
            estado,
            confianza,
            _fecha_ahora(),
            persona_id,
            usuario,
            origen,
            estado_normalizado,
            _limpiar_opcional(motivo),
            distancia,
            umbral,
            modelo or config.MODELO,
            evento or "registro",
            str(track_id) if track_id is not None else None,
        ),
    )
    return int(cursor.lastrowid)


def listar_registros(
    incluir_prueba: bool = False,
    texto: str = "",
    estado: str = "",
    limite: int | None = None,
) -> list[sqlite3.Row]:
  """Devuelve el historial filtrado, del más reciente al más antiguo."""
  limite = max(1, int(limite or config.MAX_REGISTROS_UI))
  condiciones: list[str] = []
  parametros: list[object] = []

  if not incluir_prueba:
    condiciones.append("COALESCE(r.origen, 'real') = 'real'")
  if texto and texto.strip():
    like = f"%{texto.strip()}%"
    condiciones.append(
        "(COALESCE(p.nombre, r.usuario) LIKE ? "
        "OR COALESCE(r.etiqueta_original, r.usuario) LIKE ? "
        "OR r.fecha_hora LIKE ?)"
    )
    parametros.extend([like, like, like])
  if estado and estado.strip().lower() != "todos":
    normalizado = (
        "Autorizado"
        if estado.strip().lower() in {"autorizado", "permitido"}
        else "Denegado"
    )
    condiciones.append("COALESCE(r.estado_normalizado, r.estado) = ?")
    parametros.append(normalizado)

  where = ("WHERE " + " AND ".join(condiciones)) if condiciones else ""
  parametros.append(limite)

  with conexion() as conn:
    return list(
        conn.execute(
            f"""
            SELECT
                r.id,
                COALESCE(p.nombre, r.usuario) AS usuario,
                COALESCE(r.estado_normalizado, r.estado) AS estado,
                r.confianza,
                r.fecha_hora,
                r.persona_id,
                COALESCE(r.etiqueta_original, r.usuario) AS etiqueta_original,
                COALESCE(r.origen, 'real') AS origen,
                COALESCE(r.motivo, '') AS motivo,
                r.distancia,
                r.umbral,
                COALESCE(r.modelo, '') AS modelo,
                COALESCE(r.evento, 'registro') AS evento,
                COALESCE(r.track_id, '') AS track_id,
                COALESCE(p.tipo_persona, '') AS tipo_persona
            FROM registros_acceso r
            LEFT JOIN personas p ON p.id = r.persona_id
            {where}
            ORDER BY r.id DESC
            LIMIT ?
            """,
            parametros,
        ).fetchall()
    )


def marcar_origen(etiquetas: list[str], origen: str) -> int:
  """Marca como real/prueba todas las filas de las etiquetas indicadas."""
  if origen not in ORIGENES_VALIDOS:
    raise ValueError("El origen debe ser 'real' o 'prueba'.")
  limpias = [e.strip() for e in etiquetas if (e or "").strip()]
  if not limpias:
    return 0
  marcadores = ", ".join("?" for _ in limpias)
  with conexion() as conn:
    cursor = conn.execute(
        f"""
        UPDATE registros_acceso
        SET origen = ?
        WHERE usuario IN ({marcadores})
           OR etiqueta_original IN ({marcadores})
        """,
        [origen, *limpias, *limpias],
    )
    return int(cursor.rowcount)


def resumen_etiquetas() -> list[sqlite3.Row]:
  """Agrupa el historial por etiqueta original y origen."""
  with conexion() as conn:
    return list(
        conn.execute(
            """
            SELECT
                COALESCE(etiqueta_original, usuario) AS etiqueta,
                COALESCE(origen, 'real') AS origen,
                COUNT(*) AS total
            FROM registros_acceso
            GROUP BY COALESCE(etiqueta_original, usuario), COALESCE(origen, 'real')
            ORDER BY total DESC, etiqueta COLLATE NOCASE
            """
        ).fetchall()
    )
