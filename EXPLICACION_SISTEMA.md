# Explicación completa del sistema ETITC

Esta es la explicación didáctica del proyecto, pensada para alguien que lo ve
por primera vez. Incluye el código, la instalación, los imports, la base de
datos, las pruebas, VS Code y todos los archivos "extra" que se crearon
alrededor del sistema.

La explicación va en este orden:

1. Qué hace el sistema.
2. Qué se instaló y por qué.
3. Estructura del proyecto.
4. **Archivos extra: para qué sirve cada uno.**
5. Código: `config.py`, `recognition.py`, `db.py`, `Main.py`.
6. Flujos completos.
7. Calibración, base de datos y pruebas.
8. VS Code, imports, errores y límites.

> Documentos relacionados:
> - [`README.md`](README.md): referencia general del proyecto.
> - [`GUIA_PUESTA_EN_MARCHA.md`](GUIA_PUESTA_EN_MARCHA.md): pasos operativos
>   para dejar el sistema funcionando en este equipo.
> - [`GUIA_OTRO_EQUIPO.md`](GUIA_OTRO_EQUIPO.md): instalación y ejecución en un
>   computador distinto.

---

# 1. Qué hace el sistema

Es una aplicación de escritorio para control de acceso con reconocimiento
facial.

Flujo general:

```text
Webcam → frame → detector de rostros → embedding de 128 números
       → comparación con la galería → umbral + margen
       → Autorizado / Denegado → registro en SQLite
```

Un **embedding** no es una foto: es un vector de 128 números que representa las
facciones de un rostro. Dos fotos de la misma persona producen vectores
cercanos; dos personas distintas producen vectores lejanos.

La aplicación permite:

- Validar accesos en tiempo real.
- Registrar personas con 6 fotos.
- Consultar y exportar el historial.
- Separar registros reales de registros de prueba.
- Administrar operadores con contraseña.
- Auditar las acciones del operador.

---

# 2. Qué se instaló y por qué

## 2.1 Python y el entorno virtual

Se usa **Python 3.15.2**, instalado en:

```text
C:\Python315\python.exe
```

Dentro del proyecto se creó:

```text
C:\Users\HP\onedrive\Escritorio\PPP\.venv
```

Un **entorno virtual** es una caja de herramientas aislada. Evita que las
librerías de este proyecto se mezclen con las del Python global y permite
borrar/recrear el entorno sin afectar otros programas.

Se creó con:

```powershell
py -3.15 -m venv .venv
```

Y se instala con:

```powershell
.\.venv\Scripts\python.exe -m pip install ...
```

`pip` es el instalador de paquetes de Python.

El `python` del PATH **no** tiene estas librerías. Por eso `run.bat` y VS Code
usan explícitamente `.venv\Scripts\python.exe`.

## 2.2 Paquetes instalados

| Paquete | Versión | Se importa como | Para qué sirve |
| --- | --- | --- | --- |
| `tkinter` | Incluido en Python | `tkinter`, `ttk` | Interfaz gráfica. No se instala con pip. |
| `opencv-python` | 4.14.0.94 | `cv2` | Cámara, frames, redimensionar, dibujar, detectar desenfoque. |
| `Pillow` | 13.0.0 | `PIL` | Convertir imágenes para mostrarlas en Tkinter. |
| `numpy` | 2.5.4 | `numpy` | Arreglos numéricos usados por OpenCV, Pillow y face_recognition. |
| `dlib-bin` | 20.0.1.post1 | `dlib` | dlib ya compilado para Windows. Evita CMake y Visual Studio. |
| `face-recognition` | 1.3.0 | `face_recognition` | Detecta rostros y calcula embeddings. |
| `face-recognition-models` | 0.3.0 | `face_recognition_models` | Modelos preentrenados. |
| `click` | 8.5.0 | `click` | Dependencia de la utilidad de consola de face_recognition. |
| `setuptools` | 80.10.2 | `pkg_resources` | Los modelos todavía usan `pkg_resources`. |
| `debugpy` | 1.8.22 | `debugpy` | Permite ejecutar y depurar con F5 en VS Code. |

## 2.3 Por qué `dlib-bin` y no `dlib`

El `dlib` oficial normalmente se distribuye como código fuente. En Windows eso
obliga a tener:

- CMake.
- Visual Studio Build Tools.
- El componente "Desarrollo para el escritorio con C++".

`dlib-bin` trae dlib **ya compilado** para Windows. Aunque el paquete se llama
`dlib-bin`, el módulo se importa igual:

```python
import dlib
```

Por eso el proyecto funciona sin instalar compiladores.

## 2.4 Por qué `pip install --no-deps`

`face-recognition` declara que necesita `dlib`. Si se instala normalmente, pip
intentaría instalar el `dlib` oficial y podría intentar compilarlo.

Se usa:

```powershell
.\.venv\Scripts\python.exe -m pip install --no-deps -r requirements.txt
```

`--no-deps` significa: instala solo lo que está en la lista, no busques
dependencias automáticamente.

Por eso `requirements.txt` incluye **todo**:

- `dlib-bin`
- `face-recognition`
- `face-recognition-models`
- `numpy`
- `opencv-python`
- `Pillow`
- `click`
- `setuptools<81`
- `debugpy`

El `--no-deps` va en el **comando**, no dentro del archivo; pip no acepta esa
opción como línea de `requirements.txt`.

## 2.5 El problema de `pkg_resources`

`face_recognition_models` usa internamente:

```python
from pkg_resources import resource_filename
```

`pkg_resources` venía con setuptools. A partir de setuptools 81 fue eliminado.
Por eso se instala:

```text
setuptools<81
```

concretamente `80.10.2`.

Si se instala setuptools 84 aparece:

```text
ModuleNotFoundError: No module named 'pkg_resources'
```

En `recognition.py` además se silencia la advertencia de deprecación, porque no
afecta el funcionamiento.

## 2.6 Los modelos

`face-recognition-models` pesa aproximadamente **100 MB** e incluye:

- El detector HOG de dlib.
- El modelo ResNet que genera embeddings de 128 dimensiones.
- Los predictores de puntos faciales.

No se descargan al ejecutar: quedan dentro de
`.venv\Lib\site-packages\face_recognition_models`.

## 2.7 Verificación

```powershell
cd C:\Users\HP\onedrive\Escritorio\PPP
.\.venv\Scripts\python.exe -c "import cv2, numpy, PIL, dlib, face_recognition, debugpy; print('OK')"
```

Resultado esperado: `OK`.

También se comprobó con una foto real del dataset: OpenCV 4.14, dlib 20.0.1, un
rostro detectado y un embedding de 128 dimensiones.

---

# 3. Estructura del proyecto

```text
PPP/
├─ ReconocimientoFacial/
│  ├─ Main.py                 Interfaz, cámara, registro, consultas
│  ├─ config.py               Rutas y parámetros
│  ├─ db.py                   SQLite, migración, operadores, auditoría
│  ├─ recognition.py          Galería, embeddings, comparación, seguimiento
│  ├─ migrar_bd.py            Migración manual
│  ├─ crear_operador.py       Crear/actualizar operador
│  ├─ clasificar_registros.py Clasificar real/prueba
│  └─ calibrar_umbral.py      Calcular el umbral
├─ dataset/<Persona>/variante_1..6.jpg
├─ tests/
│  ├─ __init__.py
│  ├─ test_db.py
│  └─ test_reconocimiento.py
├─ .vscode/                   Configuración de VS Code
├─ .cache/                    Caché de embeddings y calibración
├─ .backups/                  Respaldos de base y fotos
├─ .venv/                     Entorno virtual
├─ accesos.db                 Base de datos
├─ accesos.backup-...db       Respaldo anterior
├─ app.log                    Log de ejecución
├─ requirements.txt
├─ run.bat
├─ README.md
├─ GUIA_PUESTA_EN_MARCHA.md
├─ EXPLICACION_SISTEMA.md     Este documento
└─ .gitignore
```

La separación es intencional:

- `config.py` no depende de nadie.
- `db.py` solo depende de `config`.
- `recognition.py` solo depende de `config` y carga `cv2`/`face_recognition`
  dentro de funciones.
- `Main.py` une todo.
- Los tests pueden ejecutar la lógica sin cámara.

---

# 4. Archivos extra: para qué sirve cada uno

Estos archivos no forman parte del "reconocimiento" en sí, pero hacen que el
proyecto sea mantenible, reproducible y seguro.

## 4.1 La carpeta `.vscode/`

Es una carpeta de configuración para **Visual Studio Code**. Python no la lee;
solo la usa el editor.

Contiene:

### `.vscode/settings.json`

Configura el proyecto dentro de VS Code:

- `python.defaultInterpreterPath`: apunta a `.venv\Scripts\python.exe`.
- `python-envs.defaultEnvManager`: indica que se usa un entorno virtual.
- `python.terminal.activateEnvironment`: activa el entorno en la terminal
  integrada.
- `python.analysis.extraPaths`: añade `ReconocimientoFacial` para que Pylance
  entienda `import config`, `import db`, etc.
- `python.testing.unittestEnabled`: activa la vista de pruebas.
- `python.testing.unittestArgs`: busca pruebas en `tests/`.
- `files.encoding`: UTF-8.
- `terminal.integrated.env.windows`: `PYTHONUTF8=1` y `PYTHONIOENCODING=utf-8`.
- `files.watcherExclude` y `search.exclude`: evitan indexar `.venv`, `.cache`,
  `.backups` y `__pycache__`, que son carpetas grandes o generadas.

Si se borra este archivo, la aplicación sigue funcionando con `run.bat`, pero
VS Code puede usar otro intérprete y perder el autocompletado.

### `.vscode/launch.json`

Define cómo se ejecuta y depura el proyecto con **F5**:

1. `ETITC: Ejecutar aplicación`.
2. `ETITC: Crear operador`.
3. `ETITC: Migrar base de datos`.
4. `ETITC: Calibrar umbral`.
5. `ETITC: Listar clasificación de registros`.
6. `ETITC: Pruebas (unittest)`.

Todas usan:

```json
"python": "${workspaceFolder}/.venv/Scripts/python.exe"
```

Eso garantiza que F5 use el entorno correcto aunque en la barra inferior de VS
Code esté seleccionado otro Python.

También usan:

- `"console": "integratedTerminal"` para ver mensajes y poder escribir
  contraseñas.
- `"cwd": "${workspaceFolder}"`.
- Variables `PYTHONUTF8` y `PYTHONIOENCODING`.

Si se borra, F5 deja de tener estas configuraciones; la app todavía se puede
ejecutar con `run.bat`.

### `.vscode/tasks.json`

Define tareas que se pueden lanzar desde **Terminal > Run Task**:

- `ETITC: instalar dependencias`.
- `ETITC: verificar dependencias`.
- `ETITC: ejecutar pruebas`.
- `ETITC: ejecutar aplicación`.

La tarea de pruebas es la predeterminada del grupo `test`. La de instalación es
la del grupo `build`.

### `.vscode/extensions.json`

Recomienda las extensiones:

- `ms-python.python`
- `ms-python.vscode-pylance`
- `ms-python.debugpy`
- `ms-python.vscode-python-envs`

VS Code puede mostrar un aviso para instalarlas. En este equipo ya están
instaladas.

### ¿Se puede borrar `.vscode/`?

Sí. La aplicación seguirá funcionando con `run.bat`, pero perderás:

- F5 y depuración.
- Tareas.
- Intérprete fijado.
- Vista de pruebas configurada.

No es parte del producto; es comodidad de desarrollo.

---

## 4.2 `.gitignore`

Es un archivo de texto que le dice a **Git** qué archivos no debe subir a un
repositorio.

En este proyecto **todavía no hay un repositorio Git**, así que por ahora está
"inactivo", pero queda preparado para cuando lo haya.

Contenido y significado:

| Línea | Qué ignora | Por qué |
| --- | --- | --- |
| `.venv/`, `venv/` | Entornos virtuales | Son grandes y específicos de cada máquina. |
| `__pycache__/`, `*.py[cod]`, `*.egg-info/`, `.pytest_cache/` | Archivos generados por Python | Se regeneran solos. |
| `.env`, `config.local.json` | Secretos y configuración local | No deben subirse. |
| `accesos.db` | Base de datos real | Contiene historial y datos personales. |
| `accesos.backup-*.db`, `.backups/` | Respaldos | Pueden contener datos sensibles. |
| `*.db-journal`, `*.db-wal`, `*.db-shm` | Archivos temporales de SQLite | Se generan solos. |
| `.cache/` | Caché de embeddings | Se regenera. |
| `app.log`, `*.log` | Logs | Pueden contener información de uso. |
| `dataset/` | Fotos de rostros | Son datos biométricos. |

La última línea es importante: el propio archivo dice que, si el dataset es
solo de demostración, se puede quitar esa línea. Si se suben rostros reales a un
repositorio público, se estarían exponiendo datos biométricos.

`.gitignore` no es un programa: es una lista de patrones para Git.

---

## 4.3 `.venv/`

Es el entorno virtual.

Contiene:

- `Scripts\python.exe`: el Python del proyecto.
- `Scripts\pip.exe`: el instalador.
- `Lib\site-packages`: todas las librerías instaladas.
- Los modelos de face_recognition.

No es código fuente y no se debe editar a mano.

Se puede borrar y recrear con:

```powershell
Remove-Item -Recurse -Force .venv
py -3.15 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install --no-deps -r .\requirements.txt
```

Mientras exista, `run.bat` lo usa automáticamente.

---

## 4.4 `.cache/`

Es una carpeta de caché. No es la base de datos ni un respaldo.

### `.cache/embeddings.json`

Guarda:

- Los 29 embeddings utilizables.
- El nombre y la carpeta de cada persona.
- La ruta de cada foto.
- La lista de imágenes descartadas.
- Una huella del dataset.
- La versión de la caché y el modelo usado.

Sirve para no recalcular los embeddings en cada arranque. Si se borra, el
sistema los vuelve a calcular desde `dataset/`; solo tarda más la primera vez.

Se invalida automáticamente si:

- Cambia una foto.
- Se agrega o elimina una imagen.
- Cambia el modelo.
- Cambia la versión de la caché.

### `.cache/calibracion.json`

Es el informe de la última calibración del umbral. Guarda:

- Ruta del dataset.
- Número de embeddings y personas.
- Estadísticas de distancias genuinas.
- Estadísticas de distancias impostoras.
- Umbral actual y umbral sugerido.

**No se usa al arrancar la aplicación.** Es un registro de evidencia para
consultar o presentar. Se puede borrar sin afectar el reconocimiento; se
regenera ejecutando `calibrar_umbral.py`.

---

## 4.5 `.backups/`

Guarda copias de seguridad.

Actualmente contiene:

```text
.backups/accesos-20261026-132838.db
```

Es la copia de la base **antes de la migración**. Si la migración hubiera
fallado, se podría restaurar.

También se usa para guardar las fotos anteriores cuando se vuelve a registrar
una persona:

```text
.backups/Andres_Carrillo-20261026-143000/
```

No es lo mismo que un respaldo externo. Es una red de seguridad local. Conviene
copiar `.backups/` y `accesos.db` a otro disco o a la nube periódicamente.

---

## 4.6 `accesos.backup-20261026-132109.db`

Es un respaldo anterior de la base, guardado en la raíz del proyecto.

Representa el estado previo a las correcciones. Se conserva para poder volver
atrás si algo sale mal.

No se usa durante la ejecución normal.

---

## 4.7 `ReconocimientoFacial/Main.backup-20261026-132109.py`

Es una copia del `Main.py` original, antes de separar el código en módulos.

Se guardó para:

- Comparar el comportamiento anterior.
- Poder volver al código monolítico si fuera necesario.
- Tener evidencia del cambio.

No se importa ni se ejecuta. Python solo ejecuta `Main.py`.

Cuando el sistema esté validado definitivamente, se puede archivar o eliminar;
por ahora es útil conservarlo.

---

## 4.8 `app.log`

Es el registro de ejecución.

Se escribe desde `main()` con `logging`:

- Consola.
- Archivo `app.log` en UTF-8.

Contiene:

- Inicio del sistema.
- Rutas y configuración.
- Versión de la base.
- Carga de la galería.
- Imágenes descartadas.
- Eventos registrados.
- Errores de cámara o base de datos.

Es la primera cosa que hay que revisar si algo falla.

Se abre en modo **append**: no se borra al cerrar; va creciendo. No tiene
rotación automática. Si se vuelve muy grande, se puede archivar o borrar con la
aplicación cerrada; se crea de nuevo.

---

## 4.9 `README.md`

Es la documentación principal del proyecto. Explica:

- Qué hace el sistema.
- Estructura.
- Requisitos.
- Instalación.
- Ejecución.
- Primer operador.
- Migración de la base.
- Calibración.
- Privacidad.
- Pruebas.
- Uso desde VS Code.

Está pensado para que otra persona pueda entender y ejecutar el proyecto sin
preguntarte.

---

## 4.10 `GUIA_PUESTA_EN_MARCHA.md`

Es una guía operativa, más paso a paso que el README.

Incluye:

- Qué ya está hecho.
- Cómo abrir el proyecto.
- Crear el primer operador.
- Probar la cámara.
- Revisar registros.
- Registrar una persona.
- Reclasificar registros.
- Recalibrar.
- Reinstalar el entorno.
- Solución de problemas.
- Restaurar respaldos.
- Lista final de verificación.

Es la guía que deberías seguir para dejar el sistema funcionando en tu equipo.

---

## 4.11 `requirements.txt`

Es la lista de dependencias.

Sirve para que la instalación sea reproducible:

```powershell
.\.venv\Scripts\python.exe -m pip install --no-deps -r .\requirements.txt
```

Incluye versiones fijas o rangos y comentarios que explican:

- Por qué se usa `dlib-bin`.
- Por qué `--no-deps`.
- Por qué `setuptools<81`.
- Que `debugpy` es para VS Code.

Si se borra, la aplicación ya instalada sigue funcionando, pero no se podría
reconstruir el entorno de forma controlada.

---

## 4.12 `run.bat`

Es el lanzador para Windows.

Hace cuatro cosas:

1. Se coloca en la carpeta del proyecto con `cd /d "%~dp0"`.
2. Configura la consola en UTF-8 con `chcp 65001`.
3. Usa `.venv\Scripts\python.exe` si existe; si no, usa `python`.
4. Ejecuta `ReconocimientoFacial\Main.py` y, si hay error, hace `pause`.

Permite abrir la aplicación con doble clic, sin escribir comandos.

---

## 4.13 `tests/`

Contiene las pruebas automáticas.

- `__init__.py`: archivo vacío que marca la carpeta como paquete.
- `test_db.py`: 8 pruebas de migración, alias, registros de prueba, operadores, tipos de persona y datos asociados.
- `test_reconocimiento.py`: 11 pruebas de comparación, nombres y rastreo.
- `__pycache__/`: caché de bytecode generada por Python.

Las pruebas no necesitan cámara ni modelos pesados. Se ejecutan con:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s .\tests -v
```

Sirven para detectar si un cambio rompe algo que antes funcionaba.

---

## 4.14 Los scripts de mantenimiento

No se usan en el día a día, pero son importantes:

| Archivo | Para qué sirve |
| --- | --- |
| `migrar_bd.py` | Migra la base sin borrar registros y muestra un resumen. |
| `crear_operador.py` | Crea o actualiza un operador desde la consola. |
| `clasificar_registros.py` | Marca etiquetas como reales o de prueba. |
| `calibrar_umbral.py` | Calcula el umbral con las fotos del dataset. |

Sin ellos, el sistema funciona, pero no podrías hacer mantenimiento sin tocar
SQLite a mano.

---

## 4.15 `metadata.json` dentro de cada persona nueva

Cuando registras una persona desde la interfaz, se crea:

```text
dataset/Nombre_Persona/metadata.json
```

Guarda:

- Nombre visible.
- Carpeta.
- **Tipo de persona** (`estudiante`, `administrativo` o `personal de aseo`).
- **Facultad, carrera, cargo o documento**, según el tipo.
- Fecha de creación.
- Modelo usado.
- Lista de capturas e instrucciones.

El reconocimiento ignora los `.json`; solo lee `.jpg`, `.jpeg` y `.png`. El
archivo sirve para trazabilidad y para saber cómo se tomaron las fotos. Además,
al sincronizar `personas` con el dataset, el sistema lee este archivo y recupera
el tipo y los datos específicos si la base se creó de nuevo en otro equipo.

Las 9 personas históricas no tienen `metadata.json` porque sus fotos son
anteriores a esta función. La persona registrada con el esquema v2 sí lo tiene.

---

## 4.16 `__pycache__/`

Python genera esta carpeta al importar módulos. Contiene bytecode compilado
(`.pyc`).

- Acelera las importaciones.
- Se regenera sola.
- Se puede borrar sin problema.
- Está ignorada por `.gitignore`.

---

## 4.17 Qué se puede borrar y qué no

| Archivo/carpeta | ¿Se puede borrar? | ¿Se regenera? | Consecuencia |
| --- | --- | --- | --- |
| `.venv/` | Sí | No automáticamente | Hay que reinstalar todo. |
| `.cache/` | Sí | Sí | Primer arranque más lento; se pierde el informe de calibración. |
| `.backups/` | No recomendable | No | Se pierden respaldos. |
| `accesos.db` | No | No | Se pierde todo el historial. |
| `accesos.backup-...db` | Solo tras validar | No | Se pierde el rollback. |
| `Main.backup-...py` | Solo tras validar | No | Se pierde la versión anterior del código. |
| `app.log` | Sí, con la app cerrada | Sí | Se pierde el diagnóstico anterior. |
| `.vscode/` | Sí | No, pero se puede recrear | Se pierden F5, tareas y ajustes. |
| `.gitignore` | Sí, si no usas Git | No | Riesgo de subir datos sensibles. |
| `tests/` | No recomendable | No | Se pierde la red de seguridad. |
| Scripts CLI | No recomendable | No | Se pierde el mantenimiento. |
| `metadata.json` | No recomendable | No | Se pierde la trazabilidad. |
| `__pycache__/` | Sí | Sí | Ninguna. |

### Nota sobre `oracleJdk-27`

Dentro de `ReconocimientoFacial/` hay una carpeta `oracleJdk-27` que **no
pertenece a este sistema**. El código Python no la usa ni la importa. No la
creó este proyecto; si pertenece a otra herramienta, no se debe borrar sin
revisar.

---

# 5. `config.py`: el panel de control

Centraliza rutas y parámetros.

Todas las rutas se calculan desde la ubicación del archivo, no desde la carpeta
desde la que se ejecuta:

```python
APP_DIR = Path(__file__).resolve().parent
BASE_DIR = APP_DIR.parent
```

Así, abrir el programa desde VS Code, desde `run.bat` o desde otra carpeta no
crea una base "fantasma".

## Rutas

| Constante | Valor predeterminado | Qué es |
| --- | --- | --- |
| `DB_PATH` | `PPP/accesos.db` | Base SQLite. |
| `DATASET_DIR` | `PPP/dataset` | Fotos de referencia. |
| `CACHE_PATH` | `PPP/.cache/embeddings.json` | Caché. |
| `BACKUPS_DIR` | `PPP/.backups` | Respaldos. |
| `LOG_PATH` | `PPP/app.log` | Log. |
| `LOGO_PATH` | `PPP/etitc_escudo.png` | Logo. |

Cada ruta se puede cambiar con variables de entorno:

`ETITC_DB`, `ETITC_DATASET`, `ETITC_BACKUPS`, `ETITC_CACHE`, `ETITC_LOG`,
`ETITC_UMBRAL`, `ETITC_MARGEN`, `ETITC_CAMARA`, `ETITC_CONFIRMACION`,
`ETITC_COOLDOWN`, `ETITC_OLVIDO`, `ETITC_OPERADOR_USUARIO`,
`ETITC_OPERADOR_PASSWORD`, `ETITC_OPERADOR_ROL`.

## Parámetros

| Parámetro | Valor | Significado |
| --- | --- | --- |
| `MODELO` | `dlib_face_recognition_resnet_model_v1` | Modelo de embeddings. |
| `UMBRAL` | `0.577` | Distancia máxima para aceptar. |
| `MARGEN_MINIMO` | `0.05` | Diferencia mínima entre la mejor y la segunda persona. |
| `TIEMPO_CONFIRMACION` | `3.0` s | Tiempo para confirmar un evento. |
| `COOLDOWN_EVENTO` | `45` s | Tiempo mínimo entre eventos iguales. |
| `TIEMPO_OLVIDO` | `2.0` s | Tiempo para olvidar un rostro que salió. |
| `CAMARA_INDICE` | `0` | Número de cámara. |
| `INTERVALO_UI_MS` | `30` ms | Frecuencia de actualización de la interfaz. |
| `MAX_REGISTROS_UI` | `2000` | Filas máximas en la consulta. |
| `MIN_LONGITUD_PASSWORD` | `6` | Longitud mínima de contraseña. |
| `MAX_INTENTOS_LOGIN` | `5` | Intentos antes del bloqueo. |
| `BLOQUEO_LOGIN_SEGUNDOS` | `60` | Duración del bloqueo. |

`verificar_entorno()` devuelve advertencias si falta el dataset, el logo o la
carpeta de la base. `resumen_rutas()` escribe la configuración en `app.log`.

---

# 6. `recognition.py`: el cerebro del reconocimiento

No depende de la interfaz. Importa `cv2` y `face_recognition` dentro de
funciones para que los tests puedan ejecutarse sin cámara.

## 6.1 Estructuras

- `Galeria`: nombres, embeddings, rutas, carpetas, descartadas y huella del
  dataset.
- `ResultadoReconocimiento`: nombre, estado, confianza, distancia, umbral y
  motivo.
- `RostroSeguido`: un rostro en pantalla con track, posición, resultado y
  tiempos.
- `EventoAcceso`: evento listo para guardar.

## 6.2 Nombres y carpetas

- `normalizar_display()` quita espacios repetidos.
- `sanitizar_nombre()` convierte "Andrés Julián" en `Andres_Julian`, elimina
  caracteres peligrosos y evita nombres reservados de Windows como `CON`.
- `normalizar_clave()` compara sin tildes, mayúsculas, guiones ni guiones bajos.

Eso evita duplicados como `Andres_Carrillo` y `andres carrillo`.

## 6.3 Validación de capturas

Antes de aceptar una foto de registro:

1. Debe haber exactamente un rostro.
2. El rostro debe medir al menos 80 × 80 px.
3. La imagen no debe estar borrosa: varianza del Laplaciano ≥ 50.
4. El brillo medio debe estar entre 40 y 220.

Si falla, devuelve un mensaje entendible y no guarda la foto.

## 6.4 Galería y caché

La huella del dataset combina:

- Nombre del modelo.
- Ruta relativa de cada imagen.
- Tamaño.
- Fecha de modificación en nanosegundos.

Todo se resume con SHA-256. Si coincide con `.cache/embeddings.json`, se usa la
caché. Si cambió algo, se recalculan los embeddings.

La caché se escribe primero en `.tmp` y luego se reemplaza, para no dejar un
JSON a medias.

Cada imagen se procesa con:

```python
face_recognition.load_image_file(...)
face_recognition.face_locations(...)
face_recognition.face_encodings(...)
```

Se descartan:

- Imágenes sin rostro.
- Imágenes con más de un rostro.
- Embeddings inválidos.
- Imágenes corruptas.

En el dataset histórico: **48 fotos, 29 utilizables, 19 descartadas** (casi
todas de perfil). En el dataset actual de este equipo solo queda una carpeta
con 6 imágenes utilizables.

## 6.5 Comparación

La distancia es euclidiana:

```text
d = sqrt(Σ (a_i - b_i)²)
```

Luego:

1. Se calcula contra todas las fotos.
2. Se toma la distancia mínima por persona.
3. Se ordenan las personas.
4. Si la mejor distancia supera el umbral → `baja_similitud` → Denegado.
5. Si la diferencia entre la mejor y la segunda es menor que el margen →
   `ambiguo` → Denegado.
6. Si pasa ambas → Autorizado.

La confianza mostrada es:

```text
similitud = (1 - distancia) × 100
```

No es una probabilidad; es un indicador de cercanía.

El margen evita aceptar a la persona equivocada cuando dos personas se parecen
demasiado.

## 6.6 Rastreador

Registrar un evento por frame llenaría la base de duplicados. Por eso:

- Asigna un `track_id` a cada rostro.
- Compara posiciones con **IoU** (intersección sobre unión).
- Exige **3 segundos** de estabilidad.
- Emite un solo evento por track y estado.
- Aplica **45 segundos** de cooldown.
- Olvida un rostro tras **2 segundos** sin verse.
- Reinicia la confirmación si cambia el estado.
- No confirma rostros ausentes en el frame actual.

---

# 7. `db.py`: base de datos y seguridad

SQLite vive en un solo archivo (`accesos.db`). No necesita servidor.

## 7.1 Conexión

`conexion()` es un context manager:

```python
with conexion() as conn:
    ...
```

Abre la conexión, activa `foreign_keys`, configura `busy_timeout`, hace `commit`
o `rollback` y siempre cierra.

`timeout=15` y `busy_timeout=5000` ayudan si OneDrive u otro proceso bloquea el
archivo.

## 7.2 Tablas

| Tabla | Contenido |
| --- | --- |
| `personas` | Personas registradas, tipo, datos específicos y carpeta. |
| `registros_acceso` | Historial de accesos. |
| `operadores` | Usuarios, hash, salt, rol, intentos, bloqueo. |
| `auditoria_operador` | Acciones del operador. |
| `schema_version` | Versión del esquema. |

`personas` conserva `id`, `nombre`, `nombre_normalizado`, `dataset_folder`,
`activo` y `creado_en`. La versión 2 añade:

- `tipo_persona`: `estudiante`, `administrativo` o `personal de aseo`.
- `facultad` y `carrera`: solo para estudiantes.
- `cargo`: solo para administrativos.
- `documento`: solo para personal de aseo.

Los campos que no aplican al tipo se guardan como `NULL` para no mezclar datos.

`registros_acceso` conserva las columnas históricas y añade:

- `persona_id`
- `etiqueta_original`
- `origen`
- `estado_normalizado`
- `motivo`
- `distancia`
- `umbral`
- `modelo`
- `evento`
- `track_id`

No se renombra ni se borra nada.

## 7.3 Migración

1. Revisa `schema_version`.
2. Si la base es anterior, crea un respaldo.
3. Crea tablas faltantes.
4. Añade columnas con `ALTER TABLE`.
5. Crea índices.
6. Completa los registros históricos.
7. En la versión 2 agrega los campos de tipo y datos a `personas`.

Usa `COALESCE` para no sobrescribir datos ya completos y es idempotente: si ya
está en la versión actual, no se repite. Cada migración se registra en
`schema_version` (1 y 2).

## 7.4 Registros de prueba

Etiquetas:

```text
Estudiante Autorizado, Z, A, E, mimi, qwert
```

se marcan como `origen='prueba'`. No se borran: se ocultan por defecto. Se
pueden cambiar con `clasificar_registros.py`.

## 7.5 Alias

```text
ANDRES → Andres Carrillo
Andres_Julian_Carrillo_Restrepo → Andres Carrillo
```

La etiqueta original se conserva, pero todas las filas se enlazan a la misma
persona con `persona_id`. En la interfaz se muestra "Andres Carrillo".

El resumen por etiquetas puede seguir mostrando los nombres originales; es
intencional para trazabilidad.

## 7.6 Registrar evento

`registrar_evento()`:

- Valida estado y origen.
- Normaliza el nombre.
- Limita la confianza entre 0 y 100.
- Crea o encuentra la persona.
- Inserta fecha, distancia, umbral, motivo, modelo y track.

## 7.7 Consultas

`listar_registros()`:

- Une con `personas`.
- Muestra el nombre unificado.
- Devuelve `tipo_persona` para la columna **Tipo de Persona**.
- Usa el estado normalizado.
- Oculta prueba por defecto.
- Filtra por texto y estado.
- Ordena del más reciente al más antiguo.
- Limita a 2.000 filas.

`listar_personas()` devuelve el tipo, la facultad, la carrera, el cargo, el
documento, la carpeta y el total de accesos de cada persona. `guardar_persona()`
crea o actualiza esos datos y valida que el tipo sea uno de los tres permitidos.

## 7.8 Operadores y contraseñas

- Salt aleatorio de 16 bytes.
- scrypt: `n=2^14`, `r=8`, `p=1`, 32 bytes.
- Se guarda el hash, nunca la contraseña.
- Comparación con `hmac.compare_digest`.
- 5 intentos fallidos → bloqueo de 60 segundos.
- Login exitoso reinicia el contador.
- Todo queda en `auditoria_operador`.

Operador actual de esta instalación:

- **Usuario:** `OperadorEtitc`
- **Contraseña:** `OperadorADJ`
- **Rol:** `operador`

El operador anterior, `Andres Carrillo`, quedó desactivado con
`desactivar_operador()`: no se borra, conserva su historial, pero no puede
iniciar sesión. Para crear o actualizar un operador:

```powershell
.\.venv\Scripts\python.exe .\ReconocimientoFacial\crear_operador.py --usuario OperadorEtitc --rol operador
```

También se puede crear desde la interfaz.

## 7.9 Respaldos

`hacer_backup()` usa la API de SQLite para una copia consistente. Si la base no
se puede abrir como SQLite, copia el archivo tal cual.

Destino: `.backups/accesos-AAAAMMDD-HHMMSS.db`.

---

# 8. `Main.py`: la aplicación

## 8.1 Arranque

`main()`:

1. Crea la carpeta de la base.
2. Configura `logging` para consola y `app.log`.
3. Escribe la configuración.
4. Crea `tk.Tk()`.
5. Instancia `SistemaReconocimientoApp`.
6. Entra en `mainloop()`.

El constructor:

- Verifica el entorno.
- Crea carpetas.
- Inicializa/migra la base.
- Crea el operador desde variables de entorno si aplica.
- Sincroniza `personas` con el dataset.
- Construye la interfaz.
- Carga la galería 100 ms después.

## 8.2 Interfaz

- Panel izquierdo: cámara.
- Panel derecho: validación, operador, galería, estado y umbral.
- Logo con Pillow.

El botón de cámara queda deshabilitado hasta que la galería termina de cargar.

## 8.3 Cámara

`_abrir_camara()`:

- En Windows intenta `cv2.VideoCapture(0, cv2.CAP_DSHOW)`.
- Si falla, reintenta sin `CAP_DSHOW`.
- Configura 640 × 480.
- Si no abre, muestra un mensaje.

`alternar_camara()` inicia/detiene:

- Limpia la cola.
- Pregunta si se quiere continuar con galería vacía.
- Crea un hilo `daemon`.
- Reinicia el rastreador.

## 8.4 Hilo y cola

El hilo de cámara:

```text
cap.read() → _procesar_frame() → cola_ui.put()
```

La interfaz revisa la cola cada 30 ms con `after()`.

La cola tiene tamaño 2: si la interfaz se atrasa, se descarta el frame viejo.

Tkinter no es thread-safe: el hilo de cámara no toca la interfaz; solo deja
datos en la cola.

## 8.5 Procesamiento

```python
small = cv2.resize(frame, fx=0.25, fy=0.25)
rgb = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)
locations = face_recognition.face_locations(rgb)
encodings = face_recognition.face_encodings(rgb, locations)
```

Se reduce al 25 % para que el detector HOG sea rápido. Las coordenadas se
multiplican por 4 para dibujar sobre el frame original.

Luego:

- Compara con la galería.
- Actualiza el rastreador.
- Registra eventos confirmados.
- Dibuja rectángulo verde o rojo.
- Escribe nombre y confianza.

## 8.6 Evento y sonido

`_registrar_evento()` guarda:

- Nombre.
- Estado.
- Confianza.
- Distancia.
- Umbral.
- Motivo.
- Tipo: `acceso_autorizado` o `intento_denegado`.
- `track_id`.

Después reproduce:

- Autorizado: dos tonos agudos.
- Denegado: tres tonos graves.

El sonido corre en otro hilo para no bloquear.

## 8.7 Acceso de operadores

Al pulsar **Acceso Operadores**:

1. Detiene la cámara.
2. Comprueba si hay operadores activos.
3. Si no hay, abre el formulario **CREAR PRIMER OPERADOR**.
4. Si hay, muestra el login.
5. Si autentica, abre el menú:
   - Registrar Nuevo Usuario.
   - Base de Datos Institucional.
   - Auditoría de Accesos.
   - Cerrar Sesión.

## 8.8 Registro

La ventana:

- Permite elegir el tipo: estudiante, administrativo o personal de aseo.
- Pide el nombre completo.
- Muestra campos dinámicos según el tipo:
  - Estudiante: facultad y carrera.
  - Administrativo: cargo.
  - Personal de aseo: número de documento.
- Abre una cámara para la vista previa.
- Muestra la instrucción del paso.
- Captura 6 fotos:
  1. Frente serio.
  2. Frente sonriendo.
  3. Giro suave a la izquierda.
  4. Giro suave a la derecha.
  5. Inclinación arriba.
  6. Inclinación abajo.

Cada captura pasa por `validar_captura()`.

Al completar:

1. Valida el nombre y los datos obligatorios del tipo; si faltan, no deja
   capturar y muestra el aviso.
2. Bloquea el formulario para que no cambie a mitad del registro.
3. Crea `.tmp-<carpeta>-<marca>` dentro de `dataset/`.
4. Guarda `variante_1.jpg` … `variante_6.jpg`.
5. Guarda `metadata.json`.
6. Guarda el tipo y los datos específicos con `guardar_persona()`.
7. Si la persona ya existía y el operador confirma, copia la carpeta anterior a
   `.backups/dataset-...`.
8. Mueve los archivos temporales a la carpeta definitiva.
9. Elimina la temporal.
10. Registra auditoría.
11. Recarga la galería con `force=True`.

Si algo falla antes de mover los archivos, se borra la temporal y la carpeta
anterior queda intacta. Así nunca quedan registros a medias.

## 8.9 Consulta y exportación

La ventana de registros:

- Búsqueda por nombre, etiqueta o fecha.
- Filtro por estado.
- Casilla **Incluir registros de prueba**.
- Tabla con fecha, hora, nombre, condición, tipo de persona, facultad, carrera,
  resolución y origen.
- Filas de prueba en amarillo y filas desconocidas en rojo.
- Exportación CSV con `utf-8-sig` para Excel.
- Auditoría de la exportación.

La ventana **Base de Datos Institucional** muestra ID, nombre completo, tipo,
facultad, carrera, cargo, documento y total de accesos.

## 8.10 Cierre

- Detiene la cámara.
- Libera `cap`.
- Cierra la ventana de registro.
- Destruye la ventana principal.

---

# 9. Los comandos auxiliares

Ya los detallé en la sección 4.14. En resumen:

- `migrar_bd.py`: migra y resume.
- `crear_operador.py`: crea/actualiza operador.
- `clasificar_registros.py`: real/prueba.
- `calibrar_umbral.py`: calcula umbral.

`run.bat` es el lanzador diario.

---

# 10. El umbral 0.577

Con 29 embeddings:

- 46 pares genuinos.
- 360 pares impostores.

| Umbral | FAR | FRR |
| --- | --- | --- |
| 0.450 | 0.00 % | 54.35 % |
| 0.480 | 0.00 % | 32.61 % |
| 0.520 | 0.00 % | 21.74 % |
| 0.550 | 0.00 % | 17.39 % |
| **0.577** | **0.83 %** | **15.22 %** |
| 0.580 | 1.11 % | 15.22 % |
| 0.600 | 5.00 % | 13.04 % |

- **FAR**: impostores aceptados.
- **FRR**: personas reales rechazadas.

El valor anterior, `0.48`, rechazaba casi un tercio de las fotos genuinas. Con
`0.577` se aceptan pocos impostores y se rechazan menos personas reales.

La validación "dejar uno fuera" acertó **29 de 29**.

Esto se calculó con fotos del dataset, no con la cámara en vivo. La prueba final
con la webcam sigue siendo necesaria.

---

# 11. Estado actual de la base

- **381 registros** conservados.
- **303 reales** visibles.
- **78 de prueba** ocultos por defecto.
- **9 personas**: 8 históricas sin tipo asignado y 1 estudiante con facultad y
  carrera.
- **1 operador activo**: `OperadorEtitc`. El anterior, `Andres Carrillo`, está
  desactivado.

Los 78 de prueba:

- `Z`: 40.
- `Estudiante Autorizado`: 22.
- `E`: 8.
- `A`: 5.
- `mimi`: 2.
- `qwert`: 1.

Los estados `Desconocido / Alerta` se muestran como **Denegado** mediante
`estado_normalizado`; el valor original se conserva.

---

# 12. Pruebas automáticas

Son **19**:

### `test_db.py` (8)

- Respaldo y versión.
- Registros de prueba.
- Alias de Andrés.
- Estado histórico normalizado.
- Ocultar prueba por defecto.
- Cambiar origen.
- Crear y autenticar operador.
- Guardar tipo de persona, datos específicos, actualización sin duplicados y
  recuperación desde `metadata.json`.

### `test_reconocimiento.py` (11)

- Galería vacía.
- Autorización por persona.
- Baja similitud.
- Ambigüedad.
- Margen entre personas, no entre fotos.
- Confianza no negativa.
- Saneado de nombres.
- Normalización de claves.
- Confirmación a los 3 segundos.
- No confirmar rostro ausente.
- Cambio de estado genera nuevo evento.

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s .\tests -v
```

---

# 13. VS Code

## Cómo ejecutar

1. Abre VS Code en:

```text
C:\Users\HP\onedrive\Escritorio\PPP
```

2. Acepta la confianza.
3. Pulsa **F5**.
4. Elige **ETITC: Ejecutar aplicación**.

## Configuraciones disponibles

- `ETITC: Ejecutar aplicación`
- `ETITC: Crear operador`
- `ETITC: Migrar base de datos`
- `ETITC: Calibrar umbral`
- `ETITC: Listar clasificación de registros`
- `ETITC: Pruebas (unittest)`

## Recomendación

Una vez:

```text
Ctrl+Shift+P → Python: Select Interpreter → .venv\Scripts\python.exe
```

No es obligatorio para F5, porque `launch.json` ya apunta al entorno correcto,
pero ayuda al autocompletado y a la vista de pruebas.

## Qué pasa si borras `.vscode`

La app sigue funcionando con `run.bat`, pero pierdes F5, tareas y configuración
del intérprete.

---

# 14. Resumen de imports

## Biblioteca estándar

| Archivo | Imports |
| --- | --- |
| `config.py` | `os`, `pathlib` |
| `recognition.py` | `hashlib`, `json`, `logging`, `math`, `re`, `time`, `unicodedata`, `warnings`, `dataclasses`, `pathlib` |
| `db.py` | `datetime`, `hashlib`, `hmac`, `logging`, `os`, `re`, `shutil`, `sqlite3`, `unicodedata`, `contextlib`, `pathlib` |
| `Main.py` | `csv`, `datetime`, `json`, `logging`, `os`, `queue`, `shutil`, `threading`, `time`, `tkinter`, `uuid`, `pathlib` |
| CLIs | `argparse`, `getpass`, `sys`, `pathlib`, `json`, `statistics` |
| Tests | `unittest`, `tempfile`, `sqlite3`, `pathlib`, `unittest.mock` |

## Terceros

| Import | Paquete |
| --- | --- |
| `cv2` | `opencv-python` |
| `PIL` | `Pillow` |
| `numpy` | `numpy` (indirecto) |
| `dlib` | `dlib-bin` (indirecto) |
| `face_recognition` | `face-recognition` |
| `face_recognition_models` | `face-recognition-models` (indirecto) |
| `click` | `click` |
| `pkg_resources` | `setuptools<81` |
| `debugpy` | `debugpy` |

Los imports pesados se hacen dentro de funciones para que los tests no carguen
los modelos.

---

# 15. Errores comunes

| Error | Causa | Solución |
| --- | --- | --- |
| `ModuleNotFoundError: cv2` | Se usó el Python global | Usar `.venv\Scripts\python.exe` o `run.bat`. |
| `No module named 'pkg_resources'` | setuptools ≥ 81 | Instalar `setuptools<81`. |
| `dlib` intenta compilar | Se instaló sin `--no-deps` | Reinstalar con `--no-deps`. |
| Cámara en negro | Índice, permisos u otro programa | Probar `ETITC_CAMARA=1`, cerrar Teams/Zoom. |
| "Galería vacía" | No hay fotos válidas | Registrar una persona. |
| Rechaza personas reales | Umbral, luz o giro | Mejorar luz, recalibrar, ajustar umbral. |
| Acepta a quien no debe | Umbral permisivo | Bajar el umbral. |
| Base bloqueada | OneDrive | Pausar OneDrive. |
| Error inesperado | Revisar log | Abrir `app.log`. |

---

# 16. Seguridad y límites

## Lo que sí hace

- scrypt + salt.
- Bloqueo tras intentos fallidos.
- Auditoría.
- Registros de prueba separados.
- Respaldos antes de migrar.
- Nada se borra automáticamente.

## Lo que debes saber

- **No hay detección de vida**: una foto o una pantalla podrían engañar al
  sistema.
- **Los roles se guardan, pero la interfaz no diferencia permisos** entre
  operador y administrador.
- **La base y las fotos no están cifradas**: son datos biométricos.
- **HOG es sensible** a luz, pose y calidad de cámara.
- **El umbral se calibró con el dataset**, no con la cámara en vivo.
- **OneDrive puede bloquear SQLite**.
- **El `track_id` es por sesión**, no global.
- **`app.log` no rota**: puede crecer con el tiempo.

---

# 17. Resumen final

- El código está separado en configuración, reconocimiento, base de datos e
  interfaz.
- Las dependencias están aisladas en `.venv`.
- `dlib-bin` evita compiladores.
- `--no-deps` evita que pip intente compilar dlib.
- `setuptools<81` mantiene `pkg_resources`.
- `.cache` acelera el arranque; `.backups` protege los datos.
- `.vscode` es comodidad de desarrollo, no parte del producto.
- `.gitignore` protege datos biométricos y secretos si algún día usas Git.
- `README.md` y `GUIA_PUESTA_EN_MARCHA.md` documentan el proyecto.
- La base conserva 381 registros y separa 303 reales de 78 de prueba.
- El umbral calibrado es `0.577`.
- Las 19 pruebas pasan.
- El operador `OperadorEtitc` ya está creado y el anterior está desactivado.
- Solo falta probar la cámara en el equipo final.
