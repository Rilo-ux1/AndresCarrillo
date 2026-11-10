# ETITC - Sistema de Control de Acceso

Aplicación de escritorio en Python + Tkinter para registrar personas y validar
accesos mediante reconocimiento facial con la webcam. Los eventos se guardan en
SQLite (`accesos.db`) y las fotos de referencia en `dataset/`.

El registro distingue **estudiantes** (facultad y carrera), **administrativos**
(cargo) y **personal de aseo** (número de documento).

## Documentación

- [`GUIA_PUESTA_EN_MARCHA.md`](GUIA_PUESTA_EN_MARCHA.md): pasos operativos para
  dejar el sistema funcionando en este equipo.
- [`GUIA_OTRO_EQUIPO.md`](GUIA_OTRO_EQUIPO.md): cómo instalar y ejecutar el
  sistema en un computador distinto, con o sin el historial existente.
- [`EXPLICACION_SISTEMA.md`](EXPLICACION_SISTEMA.md): explicación didáctica
  completa del código, la instalación, la base de datos, las pruebas y cada
  archivo extra del proyecto.
- [`Entrega2_Casos_Prueba_ReconocimientoFacial.docx`](Entrega2_Casos_Prueba_ReconocimientoFacial.docx):
  informe de estrategia y fichas de los 36 casos de prueba, con resultados
  reales y simulados claramente separados.
- [`Entrega2_Matriz_Casos_Prueba.xlsx`](Entrega2_Matriz_Casos_Prueba.xlsx):
  matriz de casos, resumen con gráficos, trazabilidad, defectos y evidencia.

## Estructura

```text
PPP/
├─ ReconocimientoFacial/
│  ├─ Main.py                 Interfaz principal
│  ├─ config.py               Rutas y parámetros
│  ├─ db.py                   Esquema, migraciones y consultas
│  ├─ recognition.py          Galería, comparación y seguimiento
│  ├─ migrar_bd.py            Migración explícita de la base
│  ├─ clasificar_registros.py Clasificar registros reales/prueba
│  ├─ calibrar_umbral.py      Calibración del umbral
│  └─ crear_operador.py       Crear/actualizar operador
├─ dataset/<Persona>/variante_1..6.jpg
├─ accesos.db
├─ requirements.txt
├─ run.bat
├─ README.md
├─ GUIA_PUESTA_EN_MARCHA.md
└─ EXPLICACION_SISTEMA.md
```

## Requisitos

- Windows 10/11.
- Python 3.10 a 3.15. En este equipo se probó con **Python 3.15.2**.
- No hace falta CMake ni Visual Studio: `requirements.txt` usa `dlib-bin`, una
  rueda precompilada de dlib para Windows.
- Webcam y permisos de cámara habilitados en Windows.

El entorno virtual `.venv` de este proyecto ya quedó creado e instalado.
`run.bat` lo detecta y lo usa automáticamente.

## Instalación

Si necesitas recrear el entorno desde cero:

```bat
cd C:\Users\HP\onedrive\Escritorio\PPP
py -3.11 -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install --no-deps -r requirements.txt
```

`requirements.txt` instala `dlib-bin` (dlib precompilado) y usa `--no-deps`
para que `face-recognition` no intente compilar `dlib` desde el código fuente.
También fija `setuptools<81` porque `face_recognition_models` todavía usa
`pkg_resources`.

Si prefieres el `dlib` oficial, necesitas CMake y Visual Studio Build Tools con
"Desarrollo para el escritorio con C++", y luego instalar `dlib` manualmente.
Para este proyecto no es necesario.

## Ejecución

```bat
run.bat
```

o, usando directamente el Python del entorno virtual:

```bat
.venv\Scripts\python.exe ReconocimientoFacial\Main.py
```

Todos los comandos de este README suponen que estás en la carpeta del proyecto
y que usas `.venv\Scripts\python.exe` (o que activaste el entorno con
`.venv\Scripts\activate`).

### Visual Studio Code

El proyecto incluye la carpeta `.vscode/` ya configurada:

1. Abre VS Code en la carpeta del proyecto:

   ```bat
   code C:\Users\HP\onedrive\Escritorio\PPP
   ```

2. Si VS Code pregunta si confías en los autores de la carpeta, acepta.
3. Pulsa **F5** y elige **ETITC: Ejecutar aplicación**. También puedes usar el
   menú **Ejecutar > Iniciar depuración**.
4. En el panel **Ejecutar y depurar** hay configuraciones para crear el
   operador, migrar la base, calibrar el umbral y ejecutar las pruebas.
5. La vista **Testing** (matraz) detecta las 19 pruebas de `tests/`.

Las configuraciones usan explícitamente `.venv\Scripts\python.exe`, así que
funcionan aunque el intérprete seleccionado en la barra inferior sea otro. Las
extensiones recomendadas son Python, Pylance, debugpy y Python Environments.

Las rutas se calculan desde `ReconocimientoFacial/config.py`, así que da igual
desde qué carpeta se ejecute el programa. También puedes cambiar la ubicación
de la base, el dataset, los respaldos, la caché o el log:

```bat
set ETITC_DB=D:\datos\accesos.db
set ETITC_DATASET=D:\datos\dataset
set ETITC_BACKUPS=D:\datos\respaldos
run.bat
```

Variables disponibles: `ETITC_DB`, `ETITC_DATASET`, `ETITC_BACKUPS`,
`ETITC_CACHE`, `ETITC_LOG`, `ETITC_UMBRAL`, `ETITC_MARGEN`,
`ETITC_CAMARA`, `ETITC_OPERADOR_USUARIO` y `ETITC_OPERADOR_PASSWORD`.

## Operador

El sistema no guarda usuario ni contraseña en el código. En una instalación
nueva, la primera vez que abras el **Acceso Operadores** la aplicación ofrecerá
crear uno. También puedes crearlo desde la terminal:

```bat
.venv\Scripts\python.exe ReconocimientoFacial\crear_operador.py
```

Las contraseñas se guardan con `scrypt` y sal aleatoria. Hay bloqueo temporal
tras 5 intentos fallidos. Los inicios de sesión, los registros de personas y las
exportaciones quedan en `auditoria_operador` con el usuario autenticado.

### Credenciales de esta instalación

- **Usuario:** `OperadorEtitc`
- **Contraseña:** `OperadorADJ`
- **Rol:** `operador`

El operador anterior, `Andres Carrillo`, quedó **desactivado** para que no pueda
iniciar sesión. Su historial y sus registros de auditoría se conservan. Si
necesitas cambiar la contraseña, ejecuta:

```bat
.venv\Scripts\python.exe ReconocimientoFacial\crear_operador.py --usuario OperadorEtitc --rol operador
```

## Base de datos y migración

Al arrancar, la aplicación:

1. Crea un respaldo en `.backups/` si la base todavía no está migrada.
2. Añade columnas y tablas nuevas sin borrar filas.
3. Marca los registros históricos con `origen = 'real'` o `'prueba'`.
4. Normaliza los estados antiguos (`Desconocido / Alerta` → `Denegado`).
5. Unifica alias como `ANDRES` y `Andres_Julian_Carrillo_Restrepo` con
   `Andres Carrillo`.
6. En el esquema **v2** agrega a `personas` los campos `tipo_persona`,
   `facultad`, `carrera`, `cargo` y `documento`.

Puedes ejecutar la migración manualmente:

```bat
.venv\Scripts\python.exe ReconocimientoFacial\migrar_bd.py
```

### Registros de prueba

Por defecto se marcan como prueba las etiquetas:

`Estudiante Autorizado`, `Z`, `A`, `E`, `mimi`, `qwert`.

No se borran. Se ocultan de la consulta salvo que marques
**Incluir registros de prueba**. Para revisar o ajustar la clasificación:

```bat
.venv\Scripts\python.exe ReconocimientoFacial\clasificar_registros.py --listar
.venv\Scripts\python.exe ReconocimientoFacial\clasificar_registros.py --prueba "Z" "A" "E"
.venv\Scripts\python.exe ReconocimientoFacial\clasificar_registros.py --real "ANDRES"
```

La lista muestra la etiqueta original (`ANDRES`, `Andres_Julian_Carrillo_Restrepo`),
aunque en la consulta esas filas aparezcan unificadas como `Andres Carrillo`.

## Registro de personas

Desde **Acceso Operadores → Registrar Nuevo Usuario** puedes registrar tres tipos de
persona. El formulario cambia según el tipo elegido:

| Tipo | Datos que solicita |
| --- | --- |
| Estudiante | Nombre completo, facultad y carrera |
| Administrativo | Nombre completo y cargo que ocupa |
| Personal de aseo | Nombre completo y número de documento |

Pasos:

1. Elige el **tipo de persona**.
2. Escribe el **nombre completo** y los datos que correspondan al tipo.
3. Captura las 6 variantes: frente serio, frente sonriendo, giro suave a la
   izquierda, giro suave a la derecha e inclinaciones arriba/abajo.
4. Cada captura se valida: debe haber exactamente una cara, con tamaño
   suficiente, nitidez e iluminación adecuadas.
5. Las fotos se guardan primero en una carpeta temporal y solo se publican si
   las 6 son válidas.
6. Si la persona ya existe, se pide confirmación y se guarda una copia de las
   fotos anteriores en `.backups/`.
7. El tipo y los datos se guardan en `personas` y en el `metadata.json` de la
   carpeta. Puedes consultarlos en **Acceso Operadores → Base de Datos Institucional**.

Los giros deben ser suaves: si giras demasiado, el detector puede no encontrar
el rostro y rechazar la captura. En el dataset histórico, 19 fotos antiguas de
perfil no fueron detectadas y se descartan de la galería.

Los nombres se sanean para evitar rutas como `..\..\` y caracteres inválidos de
Windows. La galería usa una caché en `.cache/embeddings.json` para no recalcular
todos los embeddings en cada arranque.

## Reconocimiento y eventos

- El video y el reconocimiento corren en un hilo aparte para no congelar Tkinter.
- Cada rostro recibe un seguimiento y un temporizador propio.
- Solo se registra un evento cuando el estado se mantiene 3 segundos.
- Hay un enfriamiento de 45 segundos por persona/estado para evitar duplicados.
- Se guarda la distancia, el umbral, el motivo y la versión del modelo.
- Si la mejor y la segunda persona están demasiado cerca, el resultado se marca
  como ambiguo y se deniega.
- Los pitidos se reproducen en un hilo para no bloquear el video.

## Calibración del umbral

El umbral por defecto es `0.577`, calibrado con el dataset histórico (29 embeddings
utilizables de 9 personas):

- FAR (impostores aceptados): aproximadamente 0.83 %.
- FRR (personas reales rechazadas): aproximadamente 15.2 %.
- El valor anterior, `0.48`, rechazaba cerca del 32.6 % de los pares genuinos.

Para recalcularlo con tus fotos o con una cámara nueva:

```bat
.venv\Scripts\python.exe ReconocimientoFacial\calibrar_umbral.py --json .cache\calibracion.json
```

El script calcula distancias entre fotos de la misma persona (genuinas) y entre
personas distintas (impostoras), y sugiere un umbral para una tasa de falsos
positivos del 1 %. Después puedes cambiarlo sin tocar el código:

```bat
set ETITC_UMBRAL=0.577
run.bat
```

En PowerShell:

```powershell
$env:ETITC_UMBRAL = "0.577"
.\run.bat
```

## Consulta y exportación

La ventana **Auditoría de Accesos** permite:

- Buscar por nombre, etiqueta o fecha, y filtrar por estado.
- Incluir o excluir registros de prueba.
- Exportar a CSV compatible con Excel.
- Ver el tipo de persona (estudiante, administrativo o personal de aseo), el
  origen, motivo y tipo de evento de cada fila.

## Pruebas

```bat
.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Las pruebas no necesitan cámara ni `face_recognition`; cubren comparación de
embeddings, ambigüedad, seguimiento, saneado de nombres y migración de la base.
Actualmente son 19 pruebas.

## Privacidad

El dataset contiene datos biométricos de personas reales. Eso son datos
personales sensibles. Antes de usar el sistema fuera de una demostración:

- Documenta el consentimiento informado.
- Restringe el acceso a `dataset/`, `accesos.db` y `.cache/`.
- Define cuánto tiempo conservar fotos y registros.
- No subas rostros reales a repositorios públicos.
- Revisa la normativa aplicable (en Colombia, Ley 1581 de 2012 y sus decretos).

## Limitaciones conocidas

- `face_recognition` funciona mejor con rostros frontales; los perfiles pueden
  producir embeddings pobres o ser descartados.
- El umbral debe calibrarse con las personas y la cámara reales.
- La base sigue en OneDrive por defecto. Para producción conviene moverla a una
  carpeta local y hacer respaldos periódicos.
- La prueba final con webcam debe hacerse en el equipo donde está conectada.
