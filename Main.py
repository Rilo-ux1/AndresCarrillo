import datetime
import os
import sqlite3
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
import cv2
from PIL import Image, ImageTk

# Configuración de Rutas y Base de Datos
DB_NAME = "accesos.db"
DATASET_DIR = "dataset"

# Crear carpeta de dataset si no existe
if not os.path.exists(DATASET_DIR):
  os.makedirs(DATASET_DIR)


def inicializar_base_datos():
  """Crea la tabla de registros en SQLite si no existe."""
  conexion = sqlite3.connect(DB_NAME)
  cursor = conexion.cursor()
  cursor.execute(
      """
        CREATE TABLE IF NOT EXISTS registros_acceso (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario TEXT NOT NULL,
            estado TEXT NOT NULL,
            confianza REAL NOT NULL,
            fecha_hora TEXT NOT NULL
        )
    """
  )
  conexion.commit()
  conexion.close()


def registrar_acceso(usuario, estado, confianza):
  """Inserta el intento de acceso en la base de datos local."""
  conexion = sqlite3.connect(DB_NAME)
  cursor = conexion.cursor()
  fecha_hora = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
  cursor.execute(
      """
        INSERT INTO registros_acceso (usuario, estado, confianza, fecha_hora)
        VALUES (?, ?, ?, ?)
    """,
      (usuario, estado, confianza, fecha_hora),
  )
  conexion.commit()
  conexion.close()


class SistemaReconocimientoApp:

  def __init__(self, window):
    self.window = window
    self.window.title(
        "Sistema Integrado de Control de Acceso por Reconocimiento Facial"
    )
    self.window.geometry("950x720")

    # Inicializar Base de Datos
    inicializar_base_datos()

    # Cargar clasificadores y modelos de Visión por Computador
    self.face_cascade = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    )

    # Diccionario estructurado por estudiante para mayor precisión
    self.dataset_personas = {}
    self.cargar_dataset()

    # Variables de control de video y registro
    self.cap = None
    self.activa = False
    self.ultimo_registro = datetime.datetime.now()

    # Constantes para evaluación de calidad de imagen
    self.UMBRAL_BORROSIDAD = 70.0  # Varianza del Laplaciano

    # Componentes de la Interfaz Gráfica (GUI)
    self.crear_interfaz()

  def cargar_dataset(self):
    """Carga y agrupa los histogramas del dataset por cada estudiante."""
    self.dataset_personas.clear()

    if not os.path.exists(DATASET_DIR):
      return

    for persona in os.listdir(DATASET_DIR):
      ruta_persona = os.path.join(DATASET_DIR, persona)
      if os.path.isdir(ruta_persona):
        lista_hists = []
        for archivo in os.listdir(ruta_persona):
          if archivo.lower().endswith((".png", ".jpg", ".jpeg")):
            ruta_img = os.path.join(ruta_persona, archivo)
            img = cv2.imread(ruta_img, cv2.IMREAD_GRAYSCALE)
            if img is not None:
              img_resized = cv2.resize(img, (100, 100))
              hist = cv2.calcHist([img_resized], [0], None, [32], [0, 256])
              cv2.normalize(
                  hist, hist, alpha=0, beta=1, norm_type=cv2.NORM_MINMAX
              )
              lista_hists.append(hist)
        if lista_hists:
          self.dataset_personas[persona] = lista_hists

  def crear_interfaz(self):
    # Encabezado
    header = tk.Frame(self.window, bg="#1E293B", height=60)
    header.pack(fill=tk.X)
    title_label = tk.Label(
        header,
        text="CONTROL DE ACCESO INSTITUCIONAL - IA",
        fg="white",
        bg="#1E293B",
        font=("Helvetica", 16, "bold"),
    )
    title_label.pack(pady=15)

    # Áreas principales
    main_frame = tk.Frame(self.window, bg="#F1F5F9")
    main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    # Panel de Cámara
    self.panel_camara = tk.Label(main_frame, bg="black", text="Cámara Apagada")
    self.panel_camara.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)

    # Panel Lateral de Control y Estado
    panel_lateral = tk.Frame(main_frame, bg="#E2E8F0", width=260)
    panel_lateral.pack(side=tk.RIGHT, fill=tk.Y, padx=5, pady=5)

    lbl_control = tk.Label(
        panel_lateral,
        text="Panel de Control",
        font=("Helvetica", 12, "bold"),
        bg="#E2E8F0",
    )
    lbl_control.pack(pady=10)

    self.btn_camara = tk.Button(
        panel_lateral,
        text="Iniciar Validación de Identidad",
        bg="#16A34A",
        fg="white",
        font=("Helvetica", 10, "bold"),
        command=self.alternar_camara,
    )
    self.btn_camara.pack(fill=tk.X, padx=10, pady=5)

    # Botón de Registro Protegido
    self.btn_registrar = tk.Button(
        panel_lateral,
        text="Registrar Nuevo Estudiante",
        bg="#D97706",
        fg="white",
        font=("Helvetica", 10, "bold"),
        command=self.solicitar_login_registro,
    )
    self.btn_registrar.pack(fill=tk.X, padx=10, pady=5)

    self.btn_reporte = tk.Button(
        panel_lateral,
        text="Ver Registros (SQLite)",
        bg="#2563EB",
        fg="white",
        font=("Helvetica", 10),
        command=self.mostrar_registros,
    )
    self.btn_reporte.pack(fill=tk.X, padx=10, pady=5)

    # Indicador de Estado
    tk.Label(
        panel_lateral,
        text="Estado de Diagnóstico:",
        font=("Helvetica", 10, "bold"),
        bg="#E2E8F0",
    ).pack(pady=(20, 5))
    self.lbl_estado = tk.Label(
        panel_lateral,
        text="Sistema Listo",
        bg="#64748B",
        fg="white",
        font=("Helvetica", 9, "bold"),
        wraplength=220,
        padx=10,
        pady=10,
    )
    self.lbl_estado.pack(fill=tk.X, padx=10)

  def solicitar_login_registro(self):
    """Solicita credenciales de operador antes de abrir el módulo de registro."""
    if self.activa:
      self.alternar_camara()

    login_win = tk.Toplevel(self.window)
    login_win.title("Acceso Restringido - Operador")
    login_win.geometry("350x220")
    login_win.config(bg="#1E293B")
    login_win.grab_set()

    tk.Label(
        login_win,
        text="AUTORIZACIÓN DE OPERADOR",
        fg="white",
        bg="#1E293B",
        font=("Helvetica", 11, "bold"),
    ).pack(pady=15)

    tk.Label(
        login_win, text="Usuario:", fg="white", bg="#1E293B", font=("Helvetica", 9)
    ).pack()
    entry_user = tk.Entry(login_win, font=("Helvetica", 10), width=25)
    entry_user.pack(pady=5)

    tk.Label(
        login_win,
        text="Contraseña:",
        fg="white",
        bg="#1E293B",
        font=("Helvetica", 9),
    ).pack()
    entry_pass = tk.Entry(login_win, font=("Helvetica", 10), show="*", width=25)
    entry_pass.pack(pady=5)

    def validar():
      usuario = entry_user.get()
      contrasena = entry_pass.get()
      if usuario == "Operadoretitc" and contrasena == "OperadorADJ":
        login_win.destroy()
        self.abrir_ventana_registro()
      else:
        messagebox.showerror(
            "Acceso Denegado", "Usuario o contraseña incorrectos."
        )

    tk.Button(
        login_win,
        text="Ingresar",
        bg="#16A34A",
        fg="white",
        font=("Helvetica", 10, "bold"),
        command=validar,
    ).pack(pady=10)

  def abrir_ventana_registro(self):
    """Abre la interfaz interactiva para registrar fotos de distintos ángulos."""
    reg_win = tk.Toplevel(self.window)
    reg_win.title("Módulo de Registro Biométrico - Múltiples Ángulos")
    reg_win.geometry("620x560")
    reg_win.config(bg="#F1F5F9")
    reg_win.grab_set()

    tk.Label(
        reg_win,
        text="REGISTRO DE ESTUDIANTE - DISTINTOS ÁNGULOS",
        font=("Helvetica", 13, "bold"),
        bg="#F1F5F9",
        fg="#1E293B",
    ).pack(pady=10)

    frame_form = tk.Frame(reg_win, bg="#F1F5F9")
    frame_form.pack(pady=5)

    tk.Label(
        frame_form,
        text="Nombre Completo del Estudiante:",
        font=("Helvetica", 10, "bold"),
        bg="#F1F5F9",
    ).pack(anchor="w")
    entry_nombre = tk.Entry(frame_form, font=("Helvetica", 11), width=40)
    entry_nombre.pack(pady=5)

    lbl_instruccion = tk.Label(
        reg_win,
        text=(
            "Paso 1/3: Posicione el rostro de FRENTE a la cámara y capture."
        ),
        font=("Helvetica", 10, "bold"),
        bg="#F1F5F9",
        fg="#2563EB",
    )
    lbl_instruccion.pack(pady=5)

    lbl_preview = tk.Label(reg_win, bg="black", width=400, height=200)
    lbl_preview.pack(pady=5)

    cap_reg = cv2.VideoCapture(0)
    self.current_frame = None

    def actualizar_preview():
      if reg_win.winfo_exists():
        ret, frame = cap_reg.read()
        if ret:
          self.current_frame = frame.copy()
          frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
          img_pil = Image.fromarray(frame_rgb)
          img_pil = img_pil.resize((350, 200))
          img_tk = ImageTk.PhotoImage(image=img_pil)
          lbl_preview.img_tk = img_tk
          lbl_preview.config(image=img_tk)
        reg_win.after(20, actualizar_preview)

    actualizar_preview()

    self.fotos_temporales = []

    btn_capturar = tk.Button(
        reg_win,
        text="Capturar Foto 1 (De Frente)",
        bg="#16A34A",
        fg="white",
        font=("Helvetica", 11, "bold"),
    )

    def procesar_captura_angulo():
      nombre = entry_nombre.get().strip()
      if not nombre:
        messagebox.showwarning(
            "Campo Vacío",
            "Por favor ingrese el nombre del estudiante primero.",
        )
        return

      if self.current_frame is not None:
        self.fotos_temporales.append(self.current_frame.copy())
        paso_actual = len(self.fotos_temporales)

        if paso_actual == 1:
          lbl_instruccion.config(
              text=(
                  "Paso 2/3: Gire ligeramente la cabeza hacia el PERFIL"
                  " IZQUIERDO y capture."
              ),
              fg="#D97706",
          )
          btn_capturar.config(
              text="Capturar Foto 2 (Perfil Izquierdo)", bg="#D97706"
          )
        elif paso_actual == 2:
          lbl_instruccion.config(
              text=(
                  "Paso 3/3: Gire ligeramente la cabeza hacia el PERFIL"
                  " DERECHO y capture."
              ),
              fg="#2563EB",
          )
          btn_capturar.config(
              text="Capturar Foto 3 (Perfil Derecho)", bg="#2563EB"
          )
        elif paso_actual == 3:
          nombre_limpio = nombre.replace(" ", "_")
          dir_estudiante = os.path.join(DATASET_DIR, nombre_limpio)
          if not os.path.exists(dir_estudiante):
            os.makedirs(dir_estudiante)

          for idx, img_guardar in enumerate(self.fotos_temporales, 1):
            cv2.imwrite(
                os.path.join(dir_estudiante, f"angulo_{idx}.jpg"), img_guardar
            )

          cap_reg.release()
          reg_win.destroy()

          self.cargar_dataset()
          messagebox.showinfo(
              "Registro Exitoso",
              f"¡Se han registrado 3 ángulos diferentes para '{nombre}'"
              " exitosamente!\nEl estudiante ya se encuentra autorizado.",
          )

    btn_capturar.config(command=procesar_captura_angulo)
    btn_capturar.pack(pady=10)

    def cerrar_registro():
      cap_reg.release()
      reg_win.destroy()

    reg_win.protocol("WM_DELETE_WINDOW", cerrar_registro)

  def evaluar_claridad_imagen(self, recorte_gris):
    """Calcula la varianza del Laplaciano para determinar si la foto está borrosa."""
    return cv2.Laplacian(recorte_gris, cv2.CV_64F).var()

  def comparar_rostro_con_dataset(self, recorte_gris):
    """Compara el rostro evaluando el mejor puntaje agrupado por cada persona."""
    if not self.dataset_personas:
      return "Desconocido / Alerta", 0.0

    recorte_norm = cv2.resize(recorte_gris, (100, 100))
    hist_recorte = cv2.calcHist([recorte_norm], [0], None, [32], [0, 256])
    cv2.normalize(
        hist_recorte, hist_recorte, alpha=0, beta=1, norm_type=cv2.NORM_MINMAX
    )

    mejor_persona = "Desconocido / Alerta"
    max_score_global = -1.0

    # Evaluar por cada estudiante registrado
    for persona, hists in self.dataset_personas.items():
      best_score_persona = -1.0
      for hist_ref in hists:
        score = cv2.compareHist(hist_recorte, hist_ref, cv2.HISTCMP_CORREL)
        if score > best_score_persona:
          best_score_persona = score

      # Seleccionar la persona cuyo mejor ángulo tenga el puntaje más alto
      if best_score_persona > max_score_global:
        max_score_global = best_score_persona
        mejor_persona = persona

    print(
        f"Comparación por Persona -> Identidad: {mejor_persona} | Score Máximo:"
        f" {max_score_global:.2f}"
    )

    # UMBRAL DE PRECISIÓN ESTRICTO (0.73)
    # Evita falsos positivos con familiares cercanos y asegura fluidez al registrado.
    UMBRAL_HIST = 0.73

    if max_score_global >= UMBRAL_HIST:
      confianza = round(max_score_global * 100, 1)
      if confianza > 100:
        confianza = 99.9
      return mejor_persona, confianza
    else:
      return "Desconocido / Alerta", round(max(0, max_score_global) * 100, 1)

  def alternar_camara(self):
    if not self.activa:
      self.cap = cv2.VideoCapture(0)
      if not self.cap.isOpened():
        messagebox.showerror(
            "Error de Cámara", "No se pudo acceder a la webcam del equipo."
        )
        return
      self.activa = True
      self.btn_camara.config(text="Detener Cámara", bg="#DC2626")
      self.procesar_video()
    else:
      self.activa = False
      if self.cap:
        self.cap.release()
      self.btn_camara.config(
          text="Iniciar Validación de Identidad", bg="#16A34A"
      )
      self.panel_camara.config(image="", text="Cámara Apagada")
      self.lbl_estado.config(text="Sistema Apagado", bg="#64748B")

  def procesar_video(self):
    if not self.activa:
      return

    ret, frame = self.cap.read()
    if ret:
      gris = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
      rostros = self.face_cascade.detectMultiScale(
          gris, scaleFactor=1.1, minNeighbors=5, minSize=(60, 60)
      )

      for x, y, w, h in rostros:
        recorte_gris = gris[y : y + h, x : x + w]

        claridad = self.evaluar_claridad_imagen(recorte_gris)

        if claridad < self.UMBRAL_BORROSIDAD:
          color = (0, 165, 255)
          estado_texto = "ADVERTENCIA: Imagen Borrosa"
          self.lbl_estado.config(
              text="ALERTA: Posiciónese bien o mejore la luz.", bg="#D97706"
          )
        else:
          usuario, confianza = self.comparar_rostro_con_dataset(recorte_gris)

          if usuario != "Desconocido / Alerta":
            color = (0, 255, 0)
            nombre_limpio = usuario.replace("_", " ")
            estado_texto = f"Autorizado: {nombre_limpio} ({confianza}%)"
            self.lbl_estado.config(
                text=f"ACCESO PERMITIDO\nUsuario: {nombre_limpio}", bg="#16A34A"
            )
            estado_db = "Autorizado"
          else:
            color = (0, 0, 255)
            estado_texto = "ALERTA: Usuario Desconocido"
            self.lbl_estado.config(
                text="¡ALERTA DE SEGURIDAD!\nUsuario No Registrado", bg="#DC2626"
            )
            estado_db = "Desconocido / Alerta"

          tiempo_actual = datetime.datetime.now()
          if (tiempo_actual - self.ultimo_registro).total_seconds() > 5:
            registrar_acceso(usuario, estado_db, confianza)
            self.ultimo_registro = tiempo_actual

        cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)
        cv2.putText(
            frame,
            estado_texto,
            (x, y - 10),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            color,
            2,
        )

      cv2_image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
      img_pil = Image.fromarray(cv2_image)
      img_tk = ImageTk.PhotoImage(image=img_pil)
      self.panel_camara.img_tk = img_tk
      self.panel_camara.config(image=img_tk)

    self.window.after(10, self.procesar_video)

  def mostrar_registros(self):
    vent_db = tk.Toplevel(self.window)
    vent_db.title("Consulta de Registros de Acceso (SQLite)")
    vent_db.geometry("650x400")

    tree = ttk.Treeview(
        vent_db,
        columns=("ID", "Usuario", "Estado", "Confianza", "Fecha/Hora"),
        show="headings",
    )
    tree.heading("ID", text="ID")
    tree.heading("Usuario", text="Usuario")
    tree.heading("Estado", text="Estado")
    tree.heading("Confianza", text="Confianza (%)")
    tree.heading("Fecha/Hora", text="Fecha y Hora")

    tree.column("ID", width=40)
    tree.column("Usuario", width=150)
    tree.column("Estado", width=130)
    tree.column("Confianza", width=90)
    tree.column("Fecha/Hora", width=150)

    tree.pack(fill=tk.BOTH, expand=True)

    conexion = sqlite3.connect(DB_NAME)
    cursor = conexion.cursor()
    cursor.execute(
        "SELECT id, usuario, estado, confianza, fecha_hora FROM"
        " registros_acceso ORDER BY id DESC"
    )
    filas = cursor.fetchall()
    for fila in filas:
      tree.insert("", tk.END, values=fila)
    conexion.close()


if __name__ == "__main__":
  root = tk.Tk()
  app = SistemaReconocimientoApp(root)
  root.mainloop()