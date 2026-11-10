# Guía de puesta en marcha - ETITC

Esta guía explica qué correcciones ya están aplicadas, cómo ejecutar el sistema
en este equipo y cómo resolver los problemas más comunes.

> Estado actual: dependencias instaladas en `.venv`, base de datos migrada a la
> versión 2 y operador configurado. Lo único pendiente es probar la cámara.

> Si quieres entender qué hace cada archivo (incluidos `.vscode`, `.gitignore`,
> `.venv`, `.cache`, `.backups` y los respaldos), consulta
> [`EXPLICACION_SISTEMA.md`](EXPLICACION_SISTEMA.md). Esta guía se centra en la
> operación paso a paso.
>
> Si vas a instalar el sistema en **otro computador**, sigue
> [`GUIA_OTRO_EQUIPO.md`](GUIA_OTRO_EQUIPO.md).

---

## 0. Lo que ya está hecho (no hay que repetirlo)

| Elemento | Estado |
| --- | --- |
| Entorno virtual `.venv` con Python 3.15.2 | Creado e instalado |
| dlib, face_recognition, OpenCV, NumPy, Pillow | Verificados con una foto real |
| Modelo de 128 dimensiones | Funcionando |
| Base de datos `accesos.db` | Migrada a la versión 2, sin borrar registros |
| Registros históricos | 381 conservados (303 reales + 78 de prueba) |
| Operador | `OperadorEtitc` activo; `Andres Carrillo` desactivado |
| Umbral de reconocimiento | Calibrado en `0.577` |
| Respaldos | En `.backups/` y en la raíz del proyecto |
| Pruebas automáticas | 19 de 19 correctas |
| VS Code | Extensiones de Python instaladas y `.vscode/` configurado |
| Depurador `debugpy` | Instalado en `.venv` |

No necesitas instalar CMake ni Visual Studio. `requirements.txt` usa
`dlib-bin`, que trae dlib ya compilado para Windows.

---

## 1. Abrir el proyecto

1. Abre el Explorador de archivos en:

   ```text
   C:\Users\HP\onedrive\Escritorio\PPP
   ```

2. Haz doble clic en **`run.bat`**.

   `run.bat` detecta automáticamente `.venv\Scripts\python.exe`, configura la
   consola en UTF-8 y abre la interfaz.

Si prefieres hacerlo desde PowerShell:

```powershell
cd C:\Users\HP\onedrive\Escritorio\PPP
.\run.bat
```

o directamente:

```powershell
cd C:\Users\HP\onedrive\Escritorio\PPP
.\.venv\Scripts\python.exe .\ReconocimientoFacial\Main.py
```

**Importante:** no uses el `python` del PATH para este proyecto. Ese Python es
3.15.2 pero no tiene las dependencias. Usa `run.bat` o la ruta `.venv\Scripts\python.exe`.

### Abrir desde Visual Studio Code

El proyecto ya tiene la carpeta `.vscode/` configurada con el intérprete, las
tareas y las configuraciones de depuración.

1. Abre VS Code en la carpeta del proyecto:

   ```powershell
   code C:\Users\HP\onedrive\Escritorio\PPP
   ```

2. Si aparece el aviso de confianza, pulsa **Sí, confío en los autores**.
3. Pulsa **F5** y elige **ETITC: Ejecutar aplicación**.
4. En el panel **Ejecutar y depurar** también están:
   - **ETITC: Crear operador**
   - **ETITC: Migrar base de datos**
   - **ETITC: Calibrar umbral**
   - **ETITC: Listar clasificación de registros**
   - **ETITC: Pruebas (unittest)**
5. La vista **Testing** detecta automáticamente las pruebas de `tests/`.

Las configuraciones apuntan de forma explícita a
`.venv\Scripts\python.exe`, así que no dependen del intérprete que VS Code
seleccione en la barra inferior. Aun así, si quieres fijarlo manualmente:
**Ctrl+Shift+P > Python: Select Interpreter > .venv\Scripts\python.exe**.

---

## 2. Operador del sistema

### 2.1 Credenciales de esta instalación

En este equipo el operador ya está creado:

- **Usuario:** `OperadorEtitc`
- **Contraseña:** `OperadorADJ`
- **Rol:** `operador`

El operador anterior, `Andres Carrillo`, quedó **desactivado**. No es necesario
volver a crearlo. Si necesitas cambiar la contraseña:

```powershell
cd C:\Users\HP\onedrive\Escritorio\PPP
.\.venv\Scripts\python.exe .\ReconocimientoFacial\crear_operador.py --usuario OperadorEtitc --rol operador
```

### 2.2 Crear el primer operador en una instalación nueva

Si la base de datos no tiene operadores, no se puede entrar al panel de registro
ni al historial. En ese caso:

### Opción A: desde la interfaz (recomendada)

1. En la ventana principal, pulsa **Acceso Operadores**.
2. Si no hay operadores activos, se abre la ventana **CREAR PRIMER OPERADOR**.
3. Escribe un usuario (por ejemplo `admin`), una contraseña de **mínimo 6
   caracteres** y su confirmación.
4. Pulsa **Crear Operador**.
5. El panel de administración se abre automáticamente con la sesión iniciada.

### Opción B: desde la consola

```powershell
cd C:\Users\HP\onedrive\Escritorio\PPP
.\.venv\Scripts\python.exe .\ReconocimientoFacial\crear_operador.py --usuario admin --rol administrador
```

El programa pedirá la contraseña dos veces (no se muestra en pantalla).

Notas de seguridad:

- La contraseña se guarda con hash scrypt, no en texto plano.
- Tras 5 intentos fallidos, el acceso se bloquea 60 segundos.
- Cada acción del operador queda registrada en la tabla de auditoría.

---

## 3. Probar la cámara

1. Cierra Teams, Zoom, Meet u otro programa que pueda estar usando la cámara.
2. En Windows, revisa **Configuración > Privacidad y seguridad > Cámara** y
   confirma que las aplicaciones de escritorio pueden usar la cámara.
3. En la ventana principal, pulsa **Iniciar Validación IA**.
4. Colócate frente a la cámara, con luz frontal y el rostro completo visible.

Qué deberías ver:

- Un recuadro sobre el rostro.
- El nombre de la persona reconocida y el estado **Autorizado**.
- Si no coincide con nadie, **Denegado**.
- El evento se confirma tras ~3 segundos y se guarda en `accesos.db`.
- La misma persona no genera otro evento hasta pasar 45 segundos.

Prueba también con una persona **no registrada**: debe salir Denegado.

### Si la cámara no abre

La cámara predeterminada es la `0`. Si tienes varias (por ejemplo, una laptop y
una USB), prueba con otro índice:

```powershell
cd C:\Users\HP\onedrive\Escritorio\PPP
$env:ETITC_CAMARA = "1"
.\run.bat
```

Prueba `0`, `1`, `2` hasta que aparezca la imagen correcta.

---

## 4. Revisar los registros

1. Pulsa **Acceso Operadores** e inicia sesión.
2. Pulsa **Auditoría de Accesos**.
3. Por defecto se ocultan los registros marcados como prueba.
4. Marca **Incluir registros de prueba** solo si quieres verlos.
5. Usa **Buscar Nombre/Fecha** y **Estado** para acotar.
6. La columna **Tipo de Persona** muestra si la persona es estudiante,
   administrativo o personal de aseo.
7. **Exportar CSV** genera un archivo con el historial filtrado.

Deberías ver 303 registros reales. Los 78 registros de prueba (`Z`,
`Estudiante Autorizado`, `E`, `A`, `mimi`, `qwert`) quedan ocultos salvo que
actives la casilla.

Los estados históricos `Desconocido / Alerta` se muestran como **Denegado**.
`ANDRES` y `Andres_Julian_Carrillo_Restrepo` se muestran unificados como
**Andres Carrillo**.

---

## 5. Registrar una persona nueva (prueba completa)

1. Entra al **Acceso Operadores**.
2. Pulsa **Registrar Nuevo Usuario**.
3. Elige el **tipo de persona**:
   - **Estudiante:** pide nombre completo, facultad y carrera.
   - **Administrativo:** pide nombre completo y cargo que ocupa.
   - **Personal de aseo:** pide nombre completo y número de documento.
4. Escribe los datos solicitados.
5. Captura las 6 fotos:
   - Frente serio.
   - Frente sonriendo.
   - Giro **suave** a la izquierda (sin perder el rostro).
   - Giro **suave** a la derecha.
   - Inclinación hacia arriba.
   - Inclinación hacia abajo.
6. Cada captura se valida: debe haber exactamente un rostro, bien iluminado,
   nítido y con tamaño suficiente.
7. Si una captura falla, repítela. Las fotos se guardan en una carpeta temporal
   y solo se publican cuando las 6 son válidas.
8. Si la persona ya existía, el sistema pide confirmación y respalda las fotos
   anteriores en `.backups/`.
9. Al finalizar, el tipo y los datos quedan en la base. Puedes verificarlos en
   **Acceso Operadores → Base de Datos Institucional**.

Consejo: no gires demasiado la cabeza. En el dataset histórico, 19 fotos de
perfil no fueron detectadas y quedaron fuera de la galería.

Después de registrarla, prueba el reconocimiento con esa persona.

---

## 6. Reclasificar registros reales o de prueba

Si algún registro quedó mal clasificado:

```powershell
cd C:\Users\HP\onedrive\Escritorio\PPP

# Ver etiquetas y su clasificación
.\.venv\Scripts\python.exe .\ReconocimientoFacial\clasificar_registros.py --listar

# Marcar etiquetas como prueba
.\.venv\Scripts\python.exe .\ReconocimientoFacial\clasificar_registros.py --prueba "Z" "A" "E"

# Marcar etiquetas como reales
.\.venv\Scripts\python.exe .\ReconocimientoFacial\clasificar_registros.py --real "ANDRES"
```

No se elimina ningún registro: solo cambia la columna `origen`.

---

## 7. Recalibrar el umbral (solo si hace falta)

El valor actual es `0.577`, calculado con las 29 fotos utilizables del dataset:

- Falsos positivos (impostor aceptado): ~0.83 %.
- Falsos negativos (persona real rechazada): ~15.2 %.
- Con el valor anterior, `0.48`, se rechazaba ~32.6 % de las fotos genuinas.

Si con la cámara real ves muchas personas rechazadas o aceptaciones
incorrectas, recalibra:

```powershell
cd C:\Users\HP\onedrive\Escritorio\PPP
.\.venv\Scripts\python.exe .\ReconocimientoFacial\calibrar_umbral.py --json .cache\calibracion.json
```

Luego prueba sin tocar el código:

```powershell
$env:ETITC_UMBRAL = "0.55"
.\run.bat
```

Reglas prácticas:

- Bajar el umbral = más estricto (menos falsos positivos, más rechazos).
- Subir el umbral = más permisivo (menos rechazos, más falsos positivos).
- No subas por encima de `0.60` sin recalibrar.
- El margen entre la mejor y la segunda coincidencia es `0.05`. Si dos personas
  se parecen demasiado, el sistema deniega por ambigüedad.

---

## 8. Reinstalar el entorno desde cero (solo si se dañó)

Si `.venv` se corrompe o cambias de equipo:

```powershell
cd C:\Users\HP\onedrive\Escritorio\PPP
Remove-Item -Recurse -Force .venv
py -3.15 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install --no-deps -r .\requirements.txt
```

`--no-deps` es obligatorio en el comando, no dentro de `requirements.txt`:
`face-recognition` declara `dlib` como dependencia y intentaría compilarlo.

Verifica la instalación:

```powershell
.\.venv\Scripts\python.exe -c "import cv2, numpy, PIL, dlib, face_recognition; print('dependencias OK')"
```

Verifica las pruebas:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s .\tests -v
```

Deben pasar 19 pruebas.

---

## 9. Solución de problemas

| Síntoma | Causa probable | Solución |
| --- | --- | --- |
| `ModuleNotFoundError: cv2` o `face_recognition` | Se usó el Python del PATH | Ejecutar con `.venv\Scripts\python.exe` o `run.bat` |
| `No module named 'pkg_resources'` | setuptools 81 o superior | `.\.venv\Scripts\python.exe -m pip install "setuptools<81"` |
| La cámara no abre o se queda en negro | Índice incorrecto, permisos o programa en uso | Probar `ETITC_CAMARA=1`, revisar permisos, cerrar Teams/Zoom |
| "Galería vacía" | No hay fotos válidas en `dataset/` | Registrar una persona desde el Acceso Operadores |
| Rechaza a personas reales | Umbral estricto, poca luz o giro excesivo | Mejorar iluminación, recalibrar, ajustar `ETITC_UMBRAL` |
| Acepta a quien no debe | Umbral demasiado permisivo | Bajar `ETITC_UMBRAL` y recalibrar |
| Error inesperado | Revisar el registro | Abrir `app.log` en la raíz del proyecto |
| Base de datos bloqueada | OneDrive sincronizando el archivo | Pausar OneDrive mientras uses la aplicación |
| `dlib` intenta compilar | Se instaló sin `--no-deps` | Reinstalar con `pip install --no-deps -r requirements.txt` |

---

## 10. Restaurar un respaldo

Cierra la aplicación antes de copiar archivos.

### Base de datos previa a la migración

```powershell
cd C:\Users\HP\onedrive\Escritorio\PPP
Copy-Item .\.backups\accesos-20261026-132838.db .\accesos.db -Force
```

### Respaldo anterior de la base

```powershell
Copy-Item .\accesos.backup-20261026-132109.db .\accesos.db -Force
```

### Código anterior de la interfaz

```powershell
Copy-Item .\ReconocimientoFacial\Main.backup-20261026-132109.py .\ReconocimientoFacial\Main.py -Force
```

Si restauras la base anterior, vuelve a ejecutar la migración:

```powershell
.\.venv\Scripts\python.exe .\ReconocimientoFacial\migrar_bd.py
```

---

## 11. Lista final de verificación

- [ ] `run.bat` abre la ventana sin errores.
- [ ] F5 en VS Code ejecuta la aplicación.
- [ ] El operador `OperadorEtitc` puede iniciar sesión con `OperadorADJ`.
- [ ] El operador anterior `Andres Carrillo` ya no puede iniciar sesión.
- [ ] Se puede registrar un estudiante con facultad y carrera.
- [ ] Se puede registrar un administrativo con su cargo.
- [ ] Se puede registrar personal de aseo con su documento.
- [ ] La columna **Tipo de Persona** aparece en los registros de acceso.
- [ ] La cámara enciende y muestra el rostro.
- [ ] Una persona registrada sale **Autorizado**.
- [ ] Una persona no registrada sale **Denegado**.
- [ ] El evento aparece en **Auditoría de Accesos**.
- [ ] Los 78 registros de prueba están ocultos por defecto.
- [ ] **Exportar CSV** genera el archivo.
- [ ] `app.log` no muestra errores nuevos.
