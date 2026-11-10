# Guía para ejecutar ETITC en otro equipo

Esta guía explica cómo llevar el sistema de control de acceso a un computador
distinto del original, desde cero y sin depender de la carpeta de OneDrive.

Hay dos escenarios:

- **Opción A — misma instalación:** quieres las mismas personas registradas y el
  mismo historial de accesos.
- **Opción B — instalación limpia:** quieres el programa funcionando, pero con
  una base de datos nueva y personas registradas desde cero.

La mayor parte del procedimiento es igual para ambas. Las diferencias se marcan
en el paso 3 y en el paso 9.

> Documentos relacionados:
> - [`GUIA_PUESTA_EN_MARCHA.md`](GUIA_PUESTA_EN_MARCHA.md): operación en el
>   equipo original.
> - [`EXPLICACION_SISTEMA.md`](EXPLICACION_SISTEMA.md): qué hace cada archivo y
>   cómo está construido el sistema.
> - [`README.md`](README.md): referencia general.

---

## 0. Resumen rápido

Para alguien con experiencia, la secuencia completa es:

```powershell
# 1. Copiar el proyecto a una carpeta local (sin .venv)
robocopy "C:\Users\HP\onedrive\Escritorio\PPP" "D:\ETITC\PPP" /E `
  /XD ".venv" ".cache" "__pycache__" ".backups" "oracleJdk-27" /XF "app.log"

# 2. Instalar Python 3.15.2 de 64 bits desde python.org

# 3. Crear el entorno e instalar dependencias
cd D:\ETITC\PPP
py -3.15 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install --no-deps -r .\requirements.txt

# 4. Verificar
.\.venv\Scripts\python.exe -c "import cv2, numpy, PIL, dlib, face_recognition, debugpy; print('OK')"
.\.venv\Scripts\python.exe -m unittest discover -s .\tests -v

# 5. Ejecutar
.\run.bat
```

Si algo falla, revisa la sección de solución de problemas al final.

---

## 1. Requisitos del equipo nuevo

| Requisito | Mínimo | Recomendado |
| --- | --- | --- |
| Sistema operativo | Windows 10 de 64 bits | Windows 11 de 64 bits |
| Arquitectura | x64 | x64 |
| Python | 3.15.2 de 64 bits | 3.15.2 de 64 bits |
| RAM | 4 GB | 8 GB o más |
| Espacio libre | 1.5 GB | 3 GB |
| Procesador | 2 núcleos | 4 núcleos o más |
| Cámara | Webcam integrada o USB | 720p o superior |
| Red | Internet para instalar | Internet o paquetes offline |
| Permisos | Usuario normal | Usuario normal |

Notas importantes:

- **No se necesita GPU.** El detector HOG y el modelo de embeddings funcionan
  en CPU.
- **No se necesita CMake ni Visual Studio.** `dlib-bin` trae dlib compilado.
- **No se necesitan permisos de administrador** si instalas Python solo para tu
  usuario.
- **No ejecutes el proyecto desde OneDrive, una USB lenta o una carpeta de red.**
  SQLite y los modelos funcionan mejor en un disco local. Una USB solo sirve
  para transportar los archivos; cópialos primero al disco.
- Si el equipo es de 32 bits, este proyecto **no funciona**: `dlib-bin` y los
  modelos requieren 64 bits.

---

## 2. Qué copiar y qué no

### 2.1 Sí se copia

| Elemento | Para qué |
| --- | --- |
| `ReconocimientoFacial\` | Todo el código Python. |
| `dataset\` | Fotos de referencia de las personas registradas. |
| `requirements.txt` | Lista exacta de dependencias. |
| `run.bat` | Lanzador para Windows. |
| `etitc_escudo.png` | Logo de la interfaz. |
| `README.md`, `GUIA_PUESTA_EN_MARCHA.md`, `EXPLICACION_SISTEMA.md` | Documentación. |
| `tests\` | Pruebas automáticas. |
| `.vscode\` | Opcional, solo si vas a usar VS Code. |
| `accesos.db` | Solo en la **Opción A** (misma instalación). |

### 2.2 No se copia

| Elemento | Por qué |
| --- | --- |
| `.venv\` | Está atado a la ruta y al Python de la máquina original. Se recrea. |
| `__pycache__\` | Bytecode generado; se regenera solo. |
| `.cache\` | Caché de embeddings; se regenera al primer arranque. |
| `app.log` | Log de la máquina anterior; no aporta y puede confundir. |
| `.backups\` | Opcional. Si quieres conservar respaldos, cópialo aparte. |
| `oracleJdk-27\` | No pertenece a este sistema. |
| `accesos.backup-*.db` | Solo si quieres conservar el respaldo histórico. |
| `Main.backup-*.py` | Solo si quieres conservar la versión anterior del código. |

> **Privacidad:** `dataset\` y `accesos.db` contienen datos biométricos y datos
> personales. No los dejes en una USB sin cifrar ni los subas a servicios en la
> nube sin control.

### 2.3 Copiar el proyecto con PowerShell

Supongamos que el origen es la carpeta actual y el destino será
`D:\ETITC\PPP`:

```powershell
robocopy "C:\Users\HP\onedrive\Escritorio\PPP" "D:\ETITC\PPP" /E `
  /XD ".venv" ".cache" "__pycache__" ".backups" "oracleJdk-27" `
  /XF "app.log"
```

`robocopy` puede devolver un código de salida distinto de cero aunque haya
copiado bien. Los códigos del 0 al 7 se consideran éxito. Revisa que el destino
tenga los archivos antes de continuar.

Si quieres una **instalación limpia** (Opción B), excluye también la base y los
respaldos:

```powershell
robocopy "C:\Users\HP\onedrive\Escritorio\PPP" "D:\ETITC\PPP" /E `
  /XD ".venv" ".cache" "__pycache__" ".backups" "oracleJdk-27" `
  /XF "app.log" "accesos.db" "accesos.backup-*.db" "Main.backup-*.py"
```

Si prefieres no usar `robocopy`, también puedes copiar la carpeta con el
Explorador de Windows y luego **borrar** `.venv`, `.cache`, `__pycache__` y
`app.log` del destino.

### 2.4 Si el origen está en OneDrive

OneDrive puede dejar los archivos como “solo en línea”. Antes de copiar:

1. Haz clic derecho en la carpeta del proyecto.
2. Elige **Mantener siempre en este dispositivo**.
3. Espera a que termine la sincronización.
4. Copia al destino local.

Si no lo haces, la copia puede quedar incompleta o el primer arranque puede
fallar.

### 2.5 Ruta recomendada en el equipo nuevo

Usa una ruta corta y sin tildes ni caracteres raros:

```text
D:\ETITC\PPP
```

o

```text
C:\ETITC\PPP
```

Evita rutas como `C:\Users\José\Mis documentos\...` si puedes. Aunque el código
soporta UTF-8, las rutas simples reducen problemas con consolas, antivirus y
scripts.

---

## 3. Instalar Python 3.15.2

### 3.1 Descargar

1. Abre <https://www.python.org/downloads/>.
2. Busca **Python 3.15.2**.
3. Descarga el instalador **Windows installer (64-bit)**.
4. No uses la versión de Microsoft Store: a veces crea rutas y permisos
   distintos.

### 3.2 Instalar

En el instalador:

1. Marca **Add python.exe to PATH**.
2. Marca **py launcher** si aparece la opción.
3. Elige **Install Now** (instalación por usuario) o **Customize**.
4. En “Optional Features”, asegúrate de que **tcl/tk and IDLE** esté marcado:
   sin eso no funciona la interfaz gráfica.
5. En “Advanced Options”, deja **pip** habilitado.

No necesitas marcar “Install for all users” ni instalar Visual Studio.

### 3.3 Verificar

Abre una consola **nueva** (PowerShell o CMD) y ejecuta:

```powershell
py -3.15 --version
```

Debe responder algo como:

```text
Python 3.15.2
```

Verifica también `tkinter`:

```powershell
py -3.15 -c "import tkinter; print('tkinter', tkinter.TkVersion)"
```

Debe imprimir una versión de Tk, por ejemplo `tkinter 8.6`.

Si `py` no se reconoce, reinstala Python marcando el lanzador `py`. Si `python`
abre la Microsoft Store, desactiva el alias en
**Configuración > Aplicaciones > Alias de ejecución de aplicaciones** o usa
`py -3.15` en todos los comandos.

---

## 4. Crear el entorno virtual e instalar dependencias

Abre PowerShell y entra a la carpeta del proyecto:

```powershell
cd D:\ETITC\PPP
```

Crea el entorno:

```powershell
py -3.15 -m venv .venv
```

Actualiza `pip`:

```powershell
.\.venv\Scripts\python.exe -m pip install --upgrade pip
```

Instala las dependencias:

```powershell
.\.venv\Scripts\python.exe -m pip install --no-deps -r .\requirements.txt
```

### 4.1 Por qué `--no-deps`

`face-recognition` declara `dlib` como dependencia. Si se instala sin
`--no-deps`, `pip` intentaría bajar el `dlib` oficial y compilarlo, lo que exige
CMake y Visual Studio.

Con `--no-deps` se instala exactamente lo que está en `requirements.txt`, que ya
incluye `dlib-bin` (dlib precompilado). El `--no-deps` va en el **comando**, no
dentro del archivo.

### 4.2 Qué esperar

- La descarga ronda los **150–250 MB**.
- `face-recognition-models` aporta cerca de **100 MB** de modelos.
- La instalación puede tardar varios minutos.
- No necesitas compilar nada.

### 4.3 Verificar paquetes

```powershell
.\.venv\Scripts\python.exe -m pip list
```

Deben aparecer, entre otros:

```text
dlib-bin
face-recognition
face-recognition-models
numpy
opencv-python
Pillow
click
setuptools
debugpy
```

Si `setuptools` quedó en 81 o superior, fuerza la versión correcta:

```powershell
.\.venv\Scripts\python.exe -m pip install "setuptools<81"
```

Esto es necesario porque `face_recognition_models` todavía importa
`pkg_resources`.

---

## 5. Verificar la instalación

### 5.1 Imports

```powershell
.\.venv\Scripts\python.exe -c "import cv2, numpy, PIL, dlib, face_recognition, debugpy; print('OK')"
```

Resultado esperado: `OK`.

Si falla, revisa que estés usando `.venv\Scripts\python.exe` y no el `python`
del sistema.

### 5.2 Pruebas automáticas

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s .\tests -v
```

Resultado esperado: **19 pruebas correctas**.

Las pruebas no abren cámara ni cargan los modelos pesados. Si fallan, el
problema suele ser de rutas, permisos o versión de Python.

### 5.3 Prueba rápida de reconocimiento

Si copiaste el dataset, puedes comprobar que los modelos cargan y que hay
embeddings utilizables:

```powershell
.\.venv\Scripts\python.exe -c "import sys; sys.path.insert(0, 'ReconocimientoFacial'); import recognition; g = recognition.cargar_galeria(); print('Personas:', len(set(g.nombres))); print('Embeddings:', len(g.encodings)); print('Descartadas:', len(g.descartadas))"
```

En el dataset histórico daba 9 personas, 29 embeddings y 19 imágenes
descartadas. En el dataset actual solo queda la carpeta de una persona con 6
imágenes utilizables; en otro dataset los números cambian.

---

## 6. Primer arranque

### 6.1 Ejecutar

Doble clic en:

```text
run.bat
```

o desde PowerShell:

```powershell
cd D:\ETITC\PPP
.\run.bat
```

`run.bat` hace lo siguiente:

1. Se ubica en la carpeta del proyecto.
2. Configura la consola en UTF-8.
3. Usa `.venv\Scripts\python.exe` si existe.
4. Ejecuta `ReconocimientoFacial\Main.py`.
5. Si hay error, muestra un mensaje y espera una tecla.

### 6.2 Si Windows muestra SmartScreen

Es normal en un `.bat` descargado o copiado:

1. Pulsa **Más información**.
2. Pulsa **Ejecutar de todas formas**.

Si el antivirus bloquea `dlib` o `cv2`, agrega una exclusión para la carpeta del
proyecto **solo si confías en los archivos**. No desactives el antivirus de
forma global.

### 6.3 Qué deberías ver

- Una ventana con el logo de ETITC.
- El panel de cámara a la izquierda.
- El panel principal con los botones de cámara y **Acceso Operadores** a la
  derecha.
- En `app.log`, líneas de inicio, rutas y carga de galería.

El botón de cámara permanece deshabilitado hasta que la galería termina de
cargar. En el primer arranque, si no hay caché, puede tardar más.

### 6.4 Si la galería está vacía

Significa que no hay fotos válidas en `dataset\`.

- En la **Opción A**, revisa que copiaste el dataset completo y que las fotos
  están en `dataset\<Persona>\variante_1.jpg` … `variante_6.jpg`.
- En la **Opción B**, registra una persona desde el panel de operador.

También puede pasar que las fotos existan pero ningún rostro sea detectable
(perfiles, fotos borrosas, muy oscuras). En ese caso el log indica cuántas se
descartaron.

---

## 7. Crear o usar el operador

Sin operador no se puede entrar a **Registrar Nuevo Usuario**, **Base de Datos
Institucional** ni **Auditoría de Accesos**.

Si copiaste la base de este equipo, ya existe el operador:

- **Usuario:** `OperadorEtitc`
- **Contraseña:** `OperadorADJ`

El operador anterior, `Andres Carrillo`, está desactivado. En una instalación
nueva, crea el primero así:

### 7.1 Desde la interfaz

1. Pulsa **Acceso Operadores**.
2. Si no hay operadores, la aplicación ofrece crear el primero.
3. Escribe un usuario, por ejemplo `admin`.
4. Escribe una contraseña de **mínimo 6 caracteres**.
5. Confirma y guarda.

### 7.2 Desde la consola

```powershell
cd D:\ETITC\PPP
.\.venv\Scripts\python.exe .\ReconocimientoFacial\crear_operador.py --usuario admin --rol administrador
```

El programa pedirá la contraseña dos veces y no la mostrará en pantalla.

### 7.3 Si la base copiada ya tiene operadores

Usa las credenciales que ya existían. En esta instalación son
`OperadorEtitc` / `OperadorADJ`. Si no las recuerdas, puedes **actualizar** la
contraseña con el mismo comando y el mismo nombre de usuario:

```powershell
.\.venv\Scripts\python.exe .\ReconocimientoFacial\crear_operador.py --usuario admin --rol administrador
```

Ese comando crea el operador si no existe o actualiza su contraseña, rol y
estado de bloqueo si ya existe. La acción queda registrada en la auditoría.

### 7.4 Crear el operador automáticamente (opcional)

Solo sirve cuando la base **no tiene ningún operador**. Antes de arrancar:

```powershell
$env:ETITC_OPERADOR_USUARIO = "admin"
$env:ETITC_OPERADOR_PASSWORD = "unaClaveSegura"
$env:ETITC_OPERADOR_ROL = "administrador"
.\run.bat
```

La aplicación crea el operador al iniciar. Después cierra la consola: la
contraseña no queda guardada en el proyecto, pero sí en el historial de la
terminal. Para uso normal, es mejor crearlo desde la interfaz o con el CLI.

### 7.5 Registrar estudiantes, administrativos y personal de aseo

En **Acceso Operadores → Registrar Nuevo Usuario** el formulario cambia según el tipo:

| Tipo | Datos solicitados |
| --- | --- |
| Estudiante | Nombre completo, facultad y carrera |
| Administrativo | Nombre completo y cargo |
| Personal de aseo | Nombre completo y número de documento |

El tipo y los datos quedan en la tabla `personas` (esquema v2) y en el
`metadata.json` de cada carpeta. La ventana **Base de Datos Institucional** permite
consultarlos, y la columna **Tipo de Persona** de **Auditoría de Accesos**
muestra el tipo de cada persona.

---

## 8. Configurar la cámara

### 8.1 Permisos de Windows

1. Abre **Configuración > Privacidad y seguridad > Cámara**.
2. Activa **Acceso a la cámara**.
3. Activa **Permitir que las aplicaciones de escritorio accedan a la cámara**.
4. Cierra Teams, Zoom, Meet, OBS o cualquier programa que pueda estar usando la
   cámara.

### 8.2 Probar la cámara sin el sistema

Abre la aplicación **Cámara** de Windows. Si ahí se ve bien, el hardware y los
permisos están correctos.

### 8.3 Índice de cámara

Por defecto el sistema usa la cámara `0`. Si el equipo tiene varias (por ejemplo,
una integrada y una USB), prueba otros índices.

En CMD:

```bat
set ETITC_CAMARA=1
run.bat
```

En PowerShell:

```powershell
$env:ETITC_CAMARA = "1"
.\run.bat
```

Prueba `0`, `1`, `2` hasta que aparezca la imagen correcta.

### 8.4 Qué probar

1. Pulsa **Iniciar Validación IA**.
2. Colócate de frente, con luz frontal y el rostro completo visible.
3. Una persona registrada debe salir **Autorizado**.
4. Una persona no registrada debe salir **Denegado**.
5. El evento se confirma tras unos 3 segundos y aparece en **Registros de
   Acceso**.
6. La misma persona no genera otro evento hasta pasar 45 segundos.

---

## 9. Llevar la base de datos y el dataset

Esta sección aplica a la **Opción A**. Si elegiste la Opción B, salta al paso
9.5.

### 9.1 Cerrar la aplicación

Cierra la aplicación en el equipo original **antes** de copiar `accesos.db`. Si
quedó un proceso abierto, SQLite puede tener archivos temporales o la copia
puede quedar inconsistente.

### 9.2 Copiar la base

Copia:

```text
accesos.db
```

Si junto a ella existen:

```text
accesos.db-wal
accesos.db-shm
```

cópialos también. Son parte del estado de SQLite.

### 9.3 Copiar el dataset

Copia la carpeta completa:

```text
dataset\
```

Debe conservar la estructura:

```text
dataset\
├─ Andres_Carrillo\
│  ├─ variante_1.jpg
│  ├─ ...
│  └─ variante_6.jpg
├─ Otra_Persona\
│  └─ ...
```

No cambies los nombres de las carpetas ni de las fotos: la base y la galería
los usan.

### 9.4 Primer arranque con la base copiada

Al iniciar, la aplicación:

1. Detecta la versión del esquema.
2. Si la base es anterior, crea un respaldo en `.backups\`.
3. Aplica la migración sin borrar filas. La versión 2 agrega a `personas` los
   campos de tipo, facultad, carrera, cargo y documento.
4. Sincroniza la tabla `personas` con el dataset. Si una carpeta tiene
   `metadata.json`, recupera de allí el tipo de persona y sus datos.

Si la base copiada ya estaba migrada, no vuelve a migrar.

Verifica la integridad:

```powershell
.\.venv\Scripts\python.exe -c "import sqlite3; c = sqlite3.connect(r'accesos.db'); print('Registros:', c.execute('select count(*) from registros_acceso').fetchone()[0]); print('Integridad:', c.execute('pragma integrity_check').fetchone()[0])"
```

Debe imprimir `Integridad: ok`. En el equipo original hay 381 registros, pero
ese número puede cambiar si se siguieron usando.

También puedes comprobar la versión del esquema:

```powershell
.\.venv\Scripts\python.exe -c "import sqlite3; c = sqlite3.connect(r'accesos.db'); print(c.execute('select * from schema_version').fetchall())"
```

En una base migrada deben aparecer las versiones **1 y 2**.

### 9.5 Opción B: base nueva

Si no copiaste `accesos.db`, la aplicación crea una base vacía al arrancar.
Después:

1. Crea el primer operador.
2. Registra cada persona con las 6 fotos.
3. Prueba el reconocimiento.

No necesitas ejecutar ningún script de creación: `main()` inicializa el
esquema automáticamente.

### 9.6 No fusionar bases copiando archivos

No existe una función para combinar dos `accesos.db`. Si tienes historiales en
dos equipos y quieres unificarlos, hay que exportar a CSV y consolidar aparte, o
hacer una migración manual con SQLite. Copiar un archivo sobre otro **borra** el
historial del destino.

### 9.7 Respaldos

Antes de mover o reemplazar la base:

```powershell
Copy-Item .\accesos.db .\accesos.antes-de-mover.db
```

Guarda también una copia de `dataset\`. Un respaldo en el mismo disco no protege
contra fallos del disco: cópialo a otro medio.

---

## 10. Recalibrar el umbral para la cámara nueva

El valor `0.577` se calculó con las fotos del dataset original. La cámara, la
luz y el ángulo del equipo nuevo pueden cambiar los resultados.

### 10.1 Síntomas de que hace falta recalibrar

- Personas registradas salen **Denegado** con frecuencia.
- Personas distintas salen **Autorizado**.
- El sistema duda demasiado entre dos personas.

### 10.2 Recalcular con el dataset

```powershell
cd D:\ETITC\PPP
.\.venv\Scripts\python.exe .\ReconocimientoFacial\calibrar_umbral.py --json .cache\calibracion.json
```

El script calcula distancias entre fotos de la misma persona (genuinas) y entre
personas distintas (impostoras), y sugiere un umbral.

### 10.3 Probar sin tocar el código

```powershell
$env:ETITC_UMBRAL = "0.577"
.\run.bat
```

Reglas prácticas:

- Bajar el umbral = más estricto (menos falsos positivos, más rechazos).
- Subir el umbral = más permisivo (menos rechazos, más falsos positivos).
- No subas por encima de `0.60` sin recalibrar.
- El margen entre la mejor y la segunda persona es `0.05`. Si dos personas se
  parecen demasiado, el sistema deniega por ambigüedad.

La calibración con fotos no reemplaza la prueba con la cámara real. Haz pruebas
con varias personas y varias condiciones de luz.

---

## 11. Usar VS Code en el equipo nuevo (opcional)

### 11.1 Instalar

1. Descarga Visual Studio Code.
2. Instala las extensiones:
   - Python (`ms-python.python`)
   - Pylance (`ms-python.vscode-pylance`)
   - Python Debugger (`ms-python.debugpy`)
   - Python Environments (`ms-python.vscode-python-envs`)

### 11.2 Abrir el proyecto

```powershell
code D:\ETITC\PPP
```

Acepta la confianza en los autores de la carpeta.

### 11.3 Seleccionar el intérprete

```text
Ctrl+Shift+P > Python: Select Interpreter > .venv\Scripts\python.exe
```

No es obligatorio para F5, porque `.vscode\launch.json` apunta explícitamente a
`.venv\Scripts\python.exe`, pero ayuda al autocompletado y a la vista de
pruebas.

### 11.4 Ejecutar y depurar

Pulsa **F5** y elige:

- `ETITC: Ejecutar aplicación`
- `ETITC: Crear operador`
- `ETITC: Migrar base de datos`
- `ETITC: Calibrar umbral`
- `ETITC: Listar clasificación de registros`
- `ETITC: Pruebas (unittest)`

La carpeta `.vscode` usa rutas relativas a la carpeta del proyecto, así que
funciona igual en otra ubicación. Si no copiaste `.vscode`, la aplicación sigue
funcionando con `run.bat`.

---

## 12. Variables de entorno útiles

Se pueden definir por sesión (solo afectan a esa consola) o de forma permanente.

### 12.1 Por sesión

CMD:

```bat
set ETITC_CAMARA=1
set ETITC_UMBRAL=0.577
run.bat
```

PowerShell:

```powershell
$env:ETITC_CAMARA = "1"
$env:ETITC_UMBRAL = "0.577"
.\run.bat
```

### 12.2 Permanentes

```powershell
setx ETITC_CAMARA 1
```

Hay que abrir una consola nueva para que tome efecto. `setx` no cambia la sesión
actual.

No uses `setx` para `ETITC_OPERADOR_PASSWORD`: quedaría guardada en el registro
de Windows. Úsala solo en una sesión temporal.

### 12.3 Lista de variables

| Variable | Valor predeterminado | Para qué |
| --- | --- | --- |
| `ETITC_DB` | `PPP\accesos.db` | Ruta de la base. |
| `ETITC_DATASET` | `PPP\dataset` | Fotos de referencia. |
| `ETITC_BACKUPS` | `PPP\.backups` | Respaldos. |
| `ETITC_CACHE` | `PPP\.cache\embeddings.json` | Caché de embeddings. |
| `ETITC_LOG` | `PPP\app.log` | Log. |
| `ETITC_UMBRAL` | `0.577` | Distancia máxima para autorizar. |
| `ETITC_MARGEN` | `0.05` | Diferencia mínima con la segunda persona. |
| `ETITC_CAMARA` | `0` | Índice de cámara. |
| `ETITC_CONFIRMACION` | `3.0` | Segundos para confirmar un evento. |
| `ETITC_COOLDOWN` | `45` | Segundos entre eventos iguales. |
| `ETITC_OLVIDO` | `2.0` | Segundos para olvidar un rostro ausente. |
| `ETITC_INTERVALO_UI` | `30` | Milisegundos entre actualizaciones. |
| `ETITC_PAUSA_CAMARA` | `0.01` | Pausa del bucle de cámara. |
| `ETITC_MAX_REGISTROS` | `2000` | Filas máximas en la consulta. |
| `ETITC_MIN_PASSWORD` | `6` | Longitud mínima de contraseña. |
| `ETITC_MAX_INTENTOS` | `5` | Intentos antes del bloqueo. |
| `ETITC_BLOQUEO_SEGUNDOS` | `60` | Duración del bloqueo. |
| `ETITC_OPERADOR_USUARIO` | vacío | Primer operador automático. |
| `ETITC_OPERADOR_PASSWORD` | vacío | Contraseña del primer operador. |
| `ETITC_OPERADOR_ROL` | `operador` | Rol del primer operador. |

Las rutas relativas se interpretan desde la carpeta donde está `config.py`, no
desde la consola. Si usas `ETITC_DB` con una ruta relativa, conviene usar una
ruta absoluta para evitar dudas.

---

## 13. Lista de verificación

Marca cada punto en el equipo nuevo:

- [ ] Windows es de 64 bits.
- [ ] Python 3.15.2 de 64 bits está instalado y `py -3.15 --version` funciona.
- [ ] `tkinter` está disponible.
- [ ] El proyecto está en una carpeta local, no en OneDrive ni en una USB.
- [ ] `.venv` se creó sin errores.
- [ ] Las dependencias se instalaron con `--no-deps`.
- [ ] `import cv2, numpy, PIL, dlib, face_recognition, debugpy` imprime `OK`.
- [ ] Las 19 pruebas pasan.
- [ ] `run.bat` abre la ventana.
- [ ] El operador `OperadorEtitc` inicia sesión con `OperadorADJ` (o el operador propio de la instalación).
- [ ] La cámara enciende y muestra el rostro.
- [ ] Una persona registrada sale **Autorizado**.
- [ ] Una persona no registrada sale **Denegado**.
- [ ] El evento aparece en **Auditoría de Accesos**.
- [ ] La base tiene integridad `ok` (si copiaste historial).
- [ ] El dataset tiene las carpetas y fotos esperadas.
- [ ] `app.log` no muestra errores nuevos.
- [ ] Hay un respaldo de `accesos.db` y `dataset` en otro medio.

---

## 14. Solución de problemas

| Síntoma | Causa probable | Solución |
| --- | --- | --- |
| `py` no se reconoce | Python no se instaló con el lanzador o no está en PATH | Reinstala marcando **py launcher** y **Add python.exe to PATH**. |
| `python` abre la Microsoft Store | Alias de ejecución de Windows | Desactiva el alias o usa `py -3.15`. |
| `No module named tkinter` | Instalación sin tcl/tk | Reinstala Python con **tcl/tk and IDLE**. |
| `No module named 'cv2'` | Se usó el Python global | Usa `.venv\Scripts\python.exe` o `run.bat`. |
| `No module named 'pkg_resources'` | setuptools 81 o superior | `.\.venv\Scripts\python.exe -m pip install "setuptools<81"`. |
| `No matching distribution found for dlib-bin` | Python de 32 bits, versión no soportada o sin internet | Usa Python 3.15.2 de 64 bits y revisa la conexión. |
| `DLL load failed` al importar `dlib` o `cv2` | Falta el runtime de Visual C++ | Instala **Microsoft Visual C++ Redistributable 2015–2022 (x64)**. |
| `dlib` intenta compilar | Se instaló sin `--no-deps` | Reinstala con `pip install --no-deps -r requirements.txt`. |
| `pip` falla por SSL o proxy | Red corporativa | Configura el proxy o usa la instalación offline (sección 16). |
| La cámara no abre o se ve negra | Índice incorrecto, permisos u otro programa | Prueba `ETITC_CAMARA=1`, revisa permisos, cierra Teams/Zoom. |
| `Galería vacía` | Dataset ausente o sin rostros válidos | Copia el dataset o registra una persona. |
| Rechaza a personas reales | Umbral estricto, poca luz o giro excesivo | Mejora la luz, recalibra, ajusta `ETITC_UMBRAL`. |
| Acepta a quien no debe | Umbral permisivo | Baja `ETITC_UMBRAL` y recalibra. |
| `database is locked` | OneDrive, antivirus u otro proceso | Mueve el proyecto a disco local, pausa OneDrive, cierra la app. |
| `PermissionError` al escribir | Carpeta protegida o de solo lectura | Usa una carpeta del usuario, por ejemplo `D:\ETITC\PPP`. |
| El antivirus bloquea `dlib` | Falso positivo | Agrega exclusión solo para la carpeta del proyecto si confías en ella. |
| El primer arranque tarda mucho | Se están calculando embeddings | Es normal; luego se usa `.cache\embeddings.json`. |
| `UnicodeEncodeError` en la consola | Consola sin UTF-8 | Usa `run.bat`, que ejecuta `chcp 65001`. |
| La app abre pero no hay cámara | Cámara desconectada o deshabilitada | Revisa el Administrador de dispositivos. |
| Los eventos no aparecen | La cámara no confirma 3 segundos o hay cooldown | Mantén el rostro estable y espera. |

---

## 15. Seguridad y privacidad al mover el sistema

`dataset\` contiene rostros y `accesos.db` contiene historial de accesos. Son
datos personales sensibles.

Recomendaciones:

- Usa **BitLocker** o cifrado de disco en el equipo nuevo.
- No dejes copias en el escritorio, en Descargas o en una USB sin cifrar.
- Borra la carpeta temporal de transporte cuando termines.
- Restringe el acceso a `dataset\`, `accesos.db` y `.cache\`.
- Define cuánto tiempo se conservan fotos y registros.
- Documenta el consentimiento informado de las personas registradas.
- No subas rostros reales a repositorios públicos.
- En Colombia, revisa la Ley 1581 de 2012 y sus decretos reglamentarios.

Si el equipo es compartido, crea una cuenta de Windows específica para el
sistema y protege la carpeta del proyecto con permisos de esa cuenta.

---

## 16. Instalación sin internet (opcional)

Si el equipo nuevo no tiene internet, puedes descargar los paquetes en otro
equipo con la **misma versión de Python y la misma arquitectura** (3.15.2,
64 bits).

### 16.1 En el equipo con internet

```powershell
cd D:\ETITC\PPP
py -3.15 -m venv .venv-descarga
.\.venv-descarga\Scripts\python.exe -m pip install --upgrade pip
New-Item -ItemType Directory .\paquetes-offline -Force
.\.venv-descarga\Scripts\python.exe -m pip download --no-deps -r .\requirements.txt wheel -d .\paquetes-offline
```

Copia al equipo nuevo:

- La carpeta del proyecto, sin `.venv`.
- La carpeta `paquetes-offline`.

### 16.2 En el equipo sin internet

```powershell
cd D:\ETITC\PPP
py -3.15 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install --no-index --find-links .\paquetes-offline --no-deps -r .\requirements.txt
```

`--no-index` le dice a pip que no consulte internet y `--find-links` que busque
en la carpeta local. Si algún paquete no tiene rueda para tu versión de Python,
la descarga fallará en el primer equipo y sabrás que necesitas otra versión.

### 16.3 Último recurso: copiar `.venv`

Copiar `.venv` de una máquina a otra **no es recomendable**. Puede fallar por
rutas absolutas, versión de Python o DLLs. Si lo intentas, debe ser con la misma
versión de Python, la misma arquitectura y una ruta idéntica. Lo correcto es
recrear el entorno como se explicó.

---

## 17. Qué no incluye el proyecto

Para evitar expectativas incorrectas:

- No hay instalador `.msi` ni `.exe` autónomo.
- No hay actualización automática.
- No hay servicio de Windows ni inicio automático.
- No hay soporte multiusuario concurrente: SQLite es de un solo equipo.
- No hay detección de vida (una foto o una pantalla podrían engañar al
  sistema).
- No hay cifrado de la base ni del dataset.
- Los roles se guardan, pero la interfaz no diferencia permisos entre operador y
  administrador.
- No hay fusión automática de bases de datos.

Si más adelante necesitas un `.exe`, se puede evaluar PyInstaller, pero requiere
trabajo adicional con los modelos de `face_recognition` y dlib.

---

## 18. Si algo sale mal

1. Abre `app.log` en la raíz del proyecto: es la primera fuente de diagnóstico.
2. Confirma que estás usando `.venv\Scripts\python.exe`.
3. Ejecuta las 19 pruebas.
4. Verifica que `dataset\` y `accesos.db` estén completos.
5. Si la base se dañó, restaura el respaldo más reciente de `.backups\`.
6. Si el entorno se corrompió, bórralo y recréalo:

```powershell
Remove-Item -Recurse -Force .venv
py -3.15 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install --no-deps -r .\requirements.txt
```

No borres `accesos.db` ni `dataset\` para “solucionar” un problema: son los
datos irremplazables del sistema.
