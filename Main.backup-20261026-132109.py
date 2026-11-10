import datetime
import os
import sqlite3
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
import winsound  
import cv2
import face_recognition
import numpy as np
from PIL import Image, ImageTk

# Configuración de Rutas y Base de Datos
DB_NAME = "accesos.db"
DATASET_DIR = "dataset"
LOGO_PATH = "etitc_escudo.png"

if not os.path.exists(DATASET_DIR):
  os.makedirs(DATASET_DIR)


def inicializar_base_datos():
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
        "ETITC - Sistema de Control de Acceso"
    )
    self.window.geometry("980x720")
    self.window.config(bg="#0F381E")  # Fondo verde institucional

    inicializar_base_datos()

    # Listas para almacenar los vectores biométricos (embeddings) de la Red Neuronal
    self.conocidos_encodings = []
    self.conocidos_nombres = []
    self.cargar_dataset_neuronal()

    self.cap = None
    self.activa = False
    self.ultimo_registro = datetime.datetime.now()

    # Variables de control para el temporizador de audio de 3 segundos
    self.estado_previo = None
    self.usuario_previo = None
    self.tiempo_inicio_deteccion = None
    self.sonido_emitido = False

    self.crear_interfaz()

  def cargar_dataset_neuronal(self):
    """Carga y procesa las fotos del dataset a través de la Red Neuronal."""
    self.conocidos_encodings.clear()
    self.conocidos_nombres.clear()

    if not os.path.exists(DATASET_DIR):
      return

    for persona in os.listdir(DATASET_DIR):
      ruta_persona = os.path.join(DATASET_DIR, persona)
      if os.path.isdir(ruta_persona):
        for archivo in os.listdir(ruta_persona):
          if archivo.lower().endswith((".png", ".jpg", ".jpeg")):
            ruta_img = os.path.join(ruta_persona, archivo)
            imagen = face_recognition.load_image_file(ruta_img)
            codings = face_recognition.face_encodings(imagen)
            if codings:
              self.conocidos_encodings.append(codings[0])
              self.conocidos_nombres.append(persona)

    print(
        f"Red Neuronal cargada: {len(self.conocidos_encodings)} rostros de"
        " referencia indexados."
    )

  def crear_interfaz(self):
    # Header con diseño inspirado en la ETITC
    header = tk.Frame(self.window, bg="#0F381E", height=80)
    header.pack(fill=tk.X, padx=10, pady=5)

    # Cargar y mostrar el escudo de la ETITC si existe
    try:
      if os.path.exists(LOGO_PATH):
        img_logo = Image.open(LOGO_PATH).resize((55, 55))
        self.logo_tk = ImageTk.PhotoImage(img_logo)
        lbl_logo = tk.Label(header, image=self.logo_tk, bg="#0F381E")
        lbl_logo.pack(side=tk.LEFT, padx=10)
    except Exception as e:
      print(f"No se pudo cargar el escudo: {e}")

    # Título principal con ETITC en mayúsculas
    tk.Label(
        header,
        text="ETITC - CONTROL DE ACCESO",
        fg="white",
        bg="#0F381E",
        font=("Helvetica", 16, "bold"),
    ).pack(side=tk.LEFT, padx=15, pady=15)

    main_frame = tk.Frame(self.window, bg="#F1F5F9")
    main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    # Panel de la Cámara
    self.panel_camara = tk.Label(main_frame, bg="black", text="Cámara Apagada")
    self.panel_camara.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)

    # Panel Lateral de Control Principal (Inspirado en tonos industriales/grises del escudo)
    panel_lateral = tk.Frame(main_frame, bg="#E2E8F0", width=260)
    panel_lateral.pack(side=tk.RIGHT, fill=tk.Y, padx=5, pady=5)

    tk.Label(
        panel_lateral,
        text="Panel Principal",
        font=("Helvetica", 12, "bold"),
        bg="#E2E8F0",
        fg="#0F381E",
    ).pack(pady=15)

    self.btn_camara = tk.Button(
        panel_lateral,
        text="Iniciar Validación",
        bg="#16A34A",
        fg="white",
        font=("Helvetica", 10, "bold"),
        command=self.alternar_camara,
    )
    self.btn_camara.pack(fill=tk.X, padx=10, pady=8)

    # Botón de Acceso al Panel de Operador
    self.btn_operador = tk.Button(
        panel_lateral,
        text="Panel de Operador",
        bg="#0F381E",
        fg="white",
        font=("Helvetica", 10, "bold"),
        command=self.solicitar_login_operador,
    )
    self.btn_operador.pack(fill=tk.X, padx=10, pady=8)

    # Indicador de Estado
    tk.Label(
        panel_lateral,
        text="Estado de Diagnóstico:",
        font=("Helvetica", 10, "bold"),
        bg="#E2E8F0",
        fg="#334155",
    ).pack(pady=(30, 5))
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

  def solicitar_login_operador(self):
    """Solicita credenciales de operador antes de abrir el panel de administración."""
    if self.activa:
      self.alternar_camara()

    login_win = tk.Toplevel(self.window)
    login_win.title("Acceso Restringido - Operador ETITC")
    login_win.geometry("350x230")
    login_win.config(bg="#0F381E")
    login_win.grab_set()

    tk.Label(
        login_win,
        text="AUTORIZACIÓN DE OPERADOR",
        fg="white",
        bg="#0F381E",
        font=("Helvetica", 11, "bold"),
    ).pack(pady=15)

    tk.Label(
        login_win, text="Usuario:", fg="white", bg="#0F381E", font=("Helvetica", 9)
    ).pack()
    entry_user = tk.Entry(login_win, font=("Helvetica", 10), width=25)
    entry_user.pack(pady=5)

    tk.Label(
        login_win,
        text="Contraseña:",
        fg="white",
        bg="#0F381E",
        font=("Helvetica", 9),
    ).pack()
    entry_pass = tk.Entry(login_win, font=("Helvetica", 10), show="*", width=25)
    entry_pass.pack(pady=5)

    def validar():
      usuario = entry_user.get()
      contrasena = entry_pass.get()
      if usuario == "Operadoretitc" and contrasena == "OperadorADJ":
        login_win.destroy()
        self.abrir_panel_operador()
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

  def abrir_panel_operador(self):
    """Muestra el panel de administración secundario con las opciones del sistema."""
    panel_op = tk.Toplevel(self.window)
    panel_op.title("Panel de Administración - ETITC")
    panel_op.geometry("400x320")
    panel_op.config(bg="#F1F5F9")
    panel_op.grab_set()

    tk.Label(
        panel_op,
        text="MENÚ DE OPERADOR",
        font=("Helvetica", 13, "bold"),
        bg="#F1F5F9",
        fg="#0F381E",
    ).pack(pady=20)

    # Opción 1: Agregar Estudiante
    tk.Button(
        panel_op,
        text="Agregar Nuevo Estudiante",
        bg="#D97706",
        fg="white",
        font=("Helvetica", 11, "bold"),
        width=30,
        height=2,
        command=lambda: [panel_op.destroy(), self.abrir_ventana_registro()],
    ).pack(pady=10)

    # Opción 2: Ver Registros de Base de Datos
    tk.Button(
        panel_op,
        text=" Registros de Acceso ",
        bg="#0F381E",
        fg="white",
        font=("Helvetica", 11, "bold"),
        width=30,
        height=2,
        command=lambda: [panel_op.destroy(), self.mostrar_registros()],
    ).pack(pady=10)

    # Botón Cerrar
    tk.Button(
        panel_op,
        text="Cerrar Panel",
        bg="#64748B",
        fg="white",
        font=("Helvetica", 10),
        width=20,
        command=panel_op.destroy,
    ).pack(pady=15)

  def abrir_ventana_registro(self):
    reg_win = tk.Toplevel(self.window)
    reg_win.title("Módulo de Registro Biométrico - ETITC")
    reg_win.geometry("620x580")
    reg_win.config(bg="#F1F5F9")
    reg_win.grab_set()

    tk.Label(
        reg_win,
        text="REGISTRO - 6 ÁNGULOS Y EXPRESIONES",
        font=("Helvetica", 13, "bold"),
        bg="#F1F5F9",
        fg="#0F381E",
    ).pack(pady=10)

    frame_form = tk.Frame(reg_win, bg="#F1F5F9")
    frame_form.pack(pady=5)

    tk.Label(
        frame_form,
        text="Nombre Completo del Estudiante:",
        font=("Helvetica", 10, "bold"),
        bg="#F1F5F9",
        fg="#334155",
    ).pack(anchor="w")
    entry_nombre = tk.Entry(frame_form, font=("Helvetica", 11), width=40)
    entry_nombre.pack(pady=5)

    lbl_instruccion = tk.Label(
        reg_win,
        text=(
            "Paso 1/6: Rostro de FRENTE con expresión seria/neutral y capture."
        ),
        font=("Helvetica", 10, "bold"),
        bg="#F1F5F9",
        fg="#0F381E",
    )
    lbl_instruccion.pack(pady=5)

    lbl_preview = tk.Label(reg_win, bg="black", width=400, height=190)
    lbl_preview.pack(pady=5)

    cap_reg = cv2.VideoCapture(0)
    self.current_frame = None

    def actualizar_preview():
      if reg_win.winfo_exists():
        ret, frame = cap_reg.read()
        if ret:
          self.current_frame = frame.copy()
          frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
          img_pil = Image.fromarray(frame_rgb).resize((330, 190))
          img_tk = ImageTk.PhotoImage(image=img_pil)
          lbl_preview.img_tk = img_tk
          lbl_preview.config(image=img_tk)
        reg_win.after(20, actualizar_preview)

    actualizar_preview()
    self.fotos_temporales = []

    btn_capturar = tk.Button(
        reg_win,
        text="Capturar Foto 1/6 (Frente - Serio)",
        bg="#16A34A",
        fg="white",
        font=("Helvetica", 11, "bold"),
    )

    def procesar_captura_angulo():
      nombre = entry_nombre.get().strip()
      if not nombre:
        messagebox.showwarning(
            "Campo Vacío", "Ingrese el nombre del estudiante primero."
        )
        return

      if self.current_frame is not None:
        self.fotos_temporales.append(self.current_frame.copy())
        paso = len(self.fotos_temporales)

        if paso == 1:
          lbl_instruccion.config(
              text="Paso 2/6: Rostro de FRENTE sonriendo y capture.",
              fg="#16A34A",
          )
          btn_capturar.config(
              text="Capturar Foto 2/6 (Frente - Sonrisa)", bg="#16A34A"
          )
        elif paso == 2:
          lbl_instruccion.config(
              text=(
                  "Paso 3/6: Gire la cabeza hacia el PERFIL IZQUIERDO y"
                  " capture."
              ),
              fg="#D97706",
          )
          btn_capturar.config(
              text="Capturar Foto 3/6 (Perfil Izquierdo)", bg="#D97706"
          )
        elif paso == 3:
          lbl_instruccion.config(
              text=(
                  "Paso 4/6: Gire la cabeza hacia el PERFIL DERECHO y capture."
              ),
              fg="#D97706",
          )
          btn_capturar.config(
              text="Capturar Foto 4/6 (Perfil Derecho)", bg="#D97706"
          )
        elif paso == 4:
          lbl_instruccion.config(
              text="Paso 5/6: Incline ligeramente la cabeza HACIA ARRIBA.",
              fg="#0F381E",
          )
          btn_capturar.config(
              text="Capturar Foto 5/6 (Inclinación Arriba)", bg="#0F381E"
          )
        elif paso == 5:
          lbl_instruccion.config(
              text="Paso 6/6: Incline ligeramente la cabeza HACIA ABAJO.",
              fg="#0F381E",
          )
          btn_capturar.config(
              text="Capturar Foto 6/6 (Inclinación Abajo)", bg="#0F381E"
          )
        elif paso == 6:
          nombre_limpio = nombre.replace(" ", "_")
          dir_estudiante = os.path.join(DATASET_DIR, nombre_limpio)
          if not os.path.exists(dir_estudiante):
            os.makedirs(dir_estudiante)

          for idx, img_guardar in enumerate(self.fotos_temporales, 1):
            cv2.imwrite(
                os.path.join(dir_estudiante, f"variante_{idx}.jpg"),
                img_guardar,
            )

          cap_reg.release()
          reg_win.destroy()
          self.cargar_dataset_neuronal()
          messagebox.showinfo(
              "Registro Exitoso",
              f"¡Se han registrado 6 variantes biométricas para '{nombre}'"
              " exitosamente!",
          )

    btn_capturar.config(command=procesar_captura_angulo)
    btn_capturar.pack(pady=10)

    def cerrar_registro():
      cap_reg.release()
      reg_win.destroy()

    reg_win.protocol("WM_DELETE_WINDOW", cerrar_registro)

  def alternar_camara(self):
    if not self.activa:
      self.cap = cv2.VideoCapture(0)
      if not self.cap.isOpened():
        messagebox.showerror(
            "Error", "No se pudo acceder a la webcam del equipo."
        )
        return
      self.activa = True
      self.btn_camara.config(text="Detener Validación IA", bg="#DC2626")
      self.procesar_video_neural()
    else:
      self.activa = False
      if self.cap:
        self.cap.release()
      self.btn_camara.config(text="Iniciar Validación IA", bg="#16A34A")
      self.panel_camara.config(image="", text="Cámara Apagada")
      self.lbl_estado.config(text="Sistema Apagado", bg="#64748B")
      # Reiniciar variables de audio
      self.estado_previo = None
      self.usuario_previo = None
      self.tiempo_inicio_deteccion = None
      self.sonido_emitido = False

  def procesar_video_neural(self):
    if not self.activa:
      return

    ret, frame = self.cap.read()
    if ret:
      small_frame = cv2.resize(frame, (0, 0), fx=0.25, fy=0.25)
      rgb_small_frame = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)

      face_locations = face_recognition.face_locations(rgb_small_frame)
      face_encodings = face_recognition.face_encodings(
          rgb_small_frame, face_locations
      )

      # Si no hay rostros detectados, reiniciamos el temporizador
      if not face_locations:
        self.estado_previo = None
        self.usuario_previo = None
        self.tiempo_inicio_deteccion = None
        self.sonido_emitido = False
        self.lbl_estado.config(text="Esperando rostro...", bg="#64748B")

      for (top, right, bottom, left), face_encoding in zip(
          face_locations, face_encodings
      ):
        top *= 4
        right *= 4
        bottom *= 4
        left *= 4

        nombre = "Desconocido"
        confianza_str = "0%"
        color = (0, 0, 255)
        estado_db = "Denegado"
        confianza_val = 0.0

        if self.conocidos_encodings:
          distancias = face_recognition.face_distance(
              self.conocidos_encodings, face_encoding
          )
          mejor_idx = np.argmin(distancias)
          min_distancia = distancias[mejor_idx]

          UMBRAL_RED = 0.48

          if min_distancia <= UMBRAL_RED:
            usuario_crudo = self.conocidos_nombres[mejor_idx]
            nombre = usuario_crudo.replace("_", " ")
            confianza_val = round((1.0 - min_distancia) * 100, 1)
            confianza_str = f"{confianza_val}%"
            color = (0, 255, 0)
            estado_db = "Autorizado"
          else:
            confianza_val = round((1.0 - min_distancia) * 100, 1)
            confianza_str = f"{confianza_val}%"

        # Lógica de Temporizador y Alertas Sonoras DIFERENCIADAS (3 segundos)
        tiempo_ahora = datetime.datetime.now()
        if (
            self.estado_previo == estado_db
            and self.usuario_previo == nombre
        ):
          tiempo_transcurrido = (
              tiempo_ahora - self.tiempo_inicio_deteccion
          ).total_seconds()
          if tiempo_transcurrido >= 3.0 and not self.sonido_emitido:
            if estado_db == "Autorizado":
              # Sonido Éxito: Doble pitido agudo
              winsound.Beep(2500, 150)
              winsound.Beep(3000, 200)
            else:
              # Sonido Alerta: Tres pitidos graves
              winsound.Beep(400, 250)
              winsound.Beep(400, 250)
              winsound.Beep(400, 400)
            self.sonido_emitido = True
        else:
          self.estado_previo = estado_db
          self.usuario_previo = nombre
          self.tiempo_inicio_deteccion = tiempo_ahora
          self.sonido_emitido = False

        if estado_db == "Autorizado":
          self.lbl_estado.config(
              text=f"ACCESO PERMITIDO\nUsuario: {nombre} ({confianza_str})",
              bg="#16A34A",
          )
        else:
          self.lbl_estado.config(
              text="¡ALERTA DE SEGURIDAD!\nUsuario No Registrado o Desconocido",
              bg="#DC2626",
          )

        # Registro en base de datos cada 5 segundos
        if (tiempo_ahora - self.ultimo_registro).total_seconds() > 5:
          registrar_acceso(nombre, estado_db, confianza_val)
          self.ultimo_registro = tiempo_ahora

        cv2.rectangle(frame, (left, top), (right, bottom), color, 2)
        cv2.putText(
            frame,
            f"{nombre} ({confianza_str})",
            (left, top - 10),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            color,
            2,
        )

      cv2_image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
      img_pil = Image.fromarray(cv2_image)
      img_tk = ImageTk.PhotoImage(image=img_pil)
      self.panel_camara.img_tk = img_tk
      self.panel_camara.config(image=img_tk)

    self.window.after(10, self.procesar_video_neural)

  def mostrar_registros(self):
    vent_db = tk.Toplevel(self.window)
    vent_db.title("Consulta de Registros de Acceso - ETITC")
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
    for fila in cursor.fetchall():
      tree.insert("", tk.END, values=fila)
    conexion.close()


if __name__ == "__main__":
  root = tk.Tk()
  app = SistemaReconocimientoApp(root)
  root.mainloop()