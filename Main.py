"""Interfaz principal del sistema de control de acceso ETITC con CustomTkinter."""

from __future__ import annotations

import csv
import json
import logging
import queue
import shutil
import sqlite3
import threading
import time
import sys
import tkinter as tk
from tkinter import filedialog, messagebox
import tkinter.ttk as ttk
from PIL import Image

import customtkinter as ctk

try:
    import cv2
except ImportError as exc:
    raise SystemExit("Faltan dependencias para la cámara.\nInstale con: pip install opencv-python") from exc

try:
    import winsound
except ImportError:
    winsound = None

import config
import db
import recognition

logger = logging.getLogger(__name__)

# Configuración visual global de CustomTkinter
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("green")

PASOS_REGISTRO = [
    ("Paso 1/6: Rostro de FRENTE con expresión seria/neutral y capture.", "Capturar Foto 1/6 (Frente - Serio)", "#16A34A"),
    ("Paso 2/6: Rostro de FRENTE sonriendo y capture.", "Capturar Foto 2/6 (Frente - Sonrisa)", "#16A34A"),
    ("Paso 3/6: Gire ligeramente la cabeza hacia la IZQUIERDA y capture.", "Capturar Foto 3/6 (Perfil Izquierdo)", "#D97706"),
    ("Paso 4/6: Gire ligeramente la cabeza hacia la DERECHA y capture.", "Capturar Foto 4/6 (Perfil Derecho)", "#D97706"),
    ("Paso 5/6: Incline ligeramente la cabeza HACIA ARRIBA y capture.", "Capturar Foto 5/6 (Inclinación Arriba)", "#0F381E"),
    ("Paso 6/6: Incline ligeramente la cabeza HACIA ABAJO y capture.", "Capturar Foto 6/6 (Inclinación Abajo)", "#0F381E"),
]


def _area(bbox: tuple[int, int, int, int]) -> int:
    x1, y1, x2, y2 = bbox
    return max(0, x2 - x1) * max(0, y2 - y1)


class SistemaReconocimientoApp:

    def __init__(self, window: ctk.CTk):
        self.window = window
        self.window.title("ETITC - Sistema de Control de Acceso")
        self.window.geometry("1024x720")
        self.window.minsize(980, 650)

        config.DATASET_DIR.mkdir(parents=True, exist_ok=True)
        config.DB_PATH.parent.mkdir(parents=True, exist_ok=True)

        try:
            db.inicializar_base_datos()
            db.asegurar_operador_desde_entorno()
            db.sincronizar_personas_con_dataset()
        except Exception:
            messagebox.showerror("Error CRÍTICO", "No se pudo inicializar la base de datos.")

        self.galeria = recognition.Galeria()
        self.umbral = config.UMBRAL
        self.margen = config.MARGEN_MINIMO
        self.rastreador = recognition.RastreadorRostros()
        
        self.cola_ui: queue.Queue = queue.Queue(maxsize=3)
        
        self.activa = False
        self.cap: cv2.VideoCapture | None = None
        self.hilo_camara: threading.Thread | None = None
        
        self.panel_op_win: ctk.CTkToplevel | None = None
        self.ventana_registro: ctk.CTkToplevel | None = None
        self.cap_registro: cv2.VideoCapture | None = None
        self.operador_actual: str | None = None

        self.configurar_estilos_treeview()
        self.crear_interfaz()
        
        self.window.protocol("WM_DELETE_WINDOW", self.cerrar_aplicacion)
        self.window.after(config.INTERVALO_UI_MS, self.actualizar_interfaz)
        self.window.after(100, self.cargar_galeria_inicial)

    def configurar_estilos_treeview(self):
        style = ttk.Style()
        style.theme_use("default")
        style.configure("Treeview", 
                        background="#1E1E1E", foreground="white", 
                        rowheight=28, fieldbackground="#1E1E1E", borderwidth=0,
                        font=("Roboto", 10))
        style.map('Treeview', background=[('selected', '#16A34A')])
        style.configure("Treeview.Heading", 
                        background="#0F381E", foreground="white", relief="flat",
                        font=("Roboto", 10, "bold"))
        style.map("Treeview.Heading", background=[('active', '#1e5e34')])

    def crear_interfaz(self) -> None:
        header = ctk.CTkFrame(self.window, fg_color="#0F381E", corner_radius=0, height=80)
        header.pack(fill=tk.X)

        ctk.CTkLabel(header, text="ETITC - CONTROL DE ACCESO BIOMÉTRICO", text_color="white",
                     font=ctk.CTkFont(family="Roboto", size=20, weight="bold")).pack(side=tk.LEFT, padx=30, pady=25)

        main_frame = ctk.CTkFrame(self.window, fg_color="transparent")
        main_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)

        camara_frame = ctk.CTkFrame(main_frame, corner_radius=10, fg_color="#1E1E1E")
        camara_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        
        self.panel_camara = ctk.CTkLabel(camara_frame, text="Cámara Apagada\n\nPresione 'Iniciar Validación'", text_color="#64748B", font=("Roboto", 16))
        self.panel_camara.pack(expand=True, fill=tk.BOTH, padx=5, pady=5)

        panel_lateral = ctk.CTkFrame(main_frame, width=300, corner_radius=10, fg_color="#2B2B2B")
        panel_lateral.pack(side=tk.RIGHT, fill=tk.Y)

        ctk.CTkLabel(panel_lateral, text="PANEL PRINCIPAL", font=ctk.CTkFont(size=15, weight="bold"), text_color="#E2E8F0").pack(pady=(20, 15))

        self.btn_camara = ctk.CTkButton(panel_lateral, text="Cargando galería...", fg_color="#64748B", hover_color="#475569", state=tk.DISABLED,
                                        height=40, font=ctk.CTkFont(weight="bold"), command=self.alternar_camara)
        self.btn_camara.pack(fill=tk.X, padx=20, pady=10)

        self.btn_operador = ctk.CTkButton(panel_lateral, text="🔐 Acceso Operadores", fg_color="#0F381E", hover_color="#1e5e34",
                                          height=40, font=ctk.CTkFont(weight="bold"), command=self.solicitar_login_operador)
        self.btn_operador.pack(fill=tk.X, padx=20, pady=10)

        ctk.CTkLabel(panel_lateral, text="Estado del Diagnóstico:", font=ctk.CTkFont(size=12, weight="bold"), text_color="#94A3B8").pack(pady=(30, 5))
        
        self.lbl_estado = ctk.CTkLabel(panel_lateral, text="Sistema en Reposo", fg_color="#64748B", text_color="white", corner_radius=8, height=70, font=ctk.CTkFont(size=14, weight="bold"))
        self.lbl_estado.pack(fill=tk.X, padx=20)

    def cargar_galeria_inicial(self) -> None:
        try:
            self.galeria = recognition.cargar_galeria(config.DATASET_DIR, config.CACHE_PATH, force=False)
            self.btn_camara.configure(state=tk.NORMAL, text="🟢 Iniciar Validación", fg_color="#16A34A", hover_color="#15803d")
        except Exception:
            logger.exception("No se pudo cargar la galería inicial")
            self.btn_camara.configure(state=tk.DISABLED, text="Error en galería", fg_color="#DC2626")

    def alternar_camara(self) -> None:
        if self.activa:
            self.detener_camara()
            return

        while not self.cola_ui.empty(): self.cola_ui.get_nowait()
        self.cap = cv2.VideoCapture(config.CAMARA_INDICE)
        if not self.cap.isOpened():
            self.cap.release()
            self.cap = None
            messagebox.showerror("Error", "No se detectó la webcam.")
            return

        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        self.activa = True
        self.rastreador.reiniciar()
        self.btn_camara.configure(text="🔴 Detener Validación", fg_color="#DC2626", hover_color="#991b1b")
        self.hilo_camara = threading.Thread(target=self._bucle_camara, args=(self.cap,), daemon=True)
        self.hilo_camara.start()

    def detener_camara(self) -> None:
        self.activa = False
        if self.hilo_camara: self.hilo_camara.join(timeout=1.0)
        if self.cap: self.cap.release()
        self.cap = None
        self.panel_camara.configure(image="", text="Cámara Apagada\n\nPresione 'Iniciar Validación'")
        self.btn_camara.configure(text="🟢 Iniciar Validación", fg_color="#16A34A", hover_color="#15803d")
        self.lbl_estado.configure(text="Sistema en Reposo", fg_color="#64748B")

    def _bucle_camara(self, cap: cv2.VideoCapture) -> None:
        try:
            import face_recognition
        except ImportError:
            logger.exception("Falta face_recognition")
            self.activa = False
            return

        contador_frames = 0
        intervalo_skipping = 3
        ultimos_resultados_ui = []

        while self.activa:
            try:
                ret, frame = cap.read()
            except Exception:
                logger.exception("La cámara dejó de responder")
                self.activa = False
                break
            if not ret: 
                time.sleep(0.05)
                continue
            
            contador_frames += 1
            eventos = []

            if contador_frames % intervalo_skipping == 0 or not ultimos_resultados_ui:
                try:
                    small = cv2.resize(frame, (0, 0), fx=0.25, fy=0.25)
                    rgb = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)
                    locs = face_recognition.face_locations(rgb)
                    encs = face_recognition.face_encodings(rgb, locs)

                    dets = []
                    for (t, r, b, l), enc in zip(locs, encs):
                        bbox = (l*4, t*4, r*4, b*4)
                        res = recognition.reconocer_rostro(enc, self.galeria, self.umbral, self.margen)
                        dets.append((bbox, res))

                    seguidos, eventos = self.rastreador.actualizar(dets, time.monotonic())
                    
                    ultimos_resultados_ui = []
                    for track in seguidos:
                        ultimos_resultados_ui.append({
                            "bbox": track.bbox, 
                            "nombre": track.resultado.nombre, 
                            "estado": track.resultado.estado, 
                            "confianza": track.resultado.confianza
                        })

                except Exception as e:
                    logger.error(f"Error en bucle cámara: {e}")

            for res in ultimos_resultados_ui:
                x1, y1, x2, y2 = res["bbox"]
                color = (0, 255, 0) if res["estado"] == "Autorizado" else (0, 0, 255)
                cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
            
            try:
                self.cola_ui.put_nowait((frame, ultimos_resultados_ui, eventos))
            except queue.Full:
                pass 

            time.sleep(0.005)

    def actualizar_interfaz(self) -> None:
        try:
            item = self.cola_ui.get_nowait()
            frame = item[0]
            resultados = item[1]
            eventos = item[2] if len(item) > 2 else []
            
            if frame is not None:
                img_tk = ctk.CTkImage(light_image=Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)), size=(640, 480))
                self.panel_camara.configure(image=img_tk, text="")
                
                if resultados:
                    autorizados = [r for r in resultados if r["estado"] == "Autorizado"]
                    principal = max(autorizados or resultados, key=lambda i: _area(i["bbox"]))
                    if autorizados:
                        self.lbl_estado.configure(text=f"✅ ACCESO PERMITIDO\n{principal['nombre']} ({principal['confianza']:.1f}%)", fg_color="#16A34A")
                    else:
                        self.lbl_estado.configure(text="⛔ ALERTA\nRostro Desconocido / Denegado", fg_color="#DC2626")
                else:
                    self.lbl_estado.configure(text="Evaluando entorno...", fg_color="#334155")
            
            for ev in eventos:
                self._registrar_evento(ev)
                
        except queue.Empty:
            pass
            
        self.window.after(config.INTERVALO_UI_MS, self.actualizar_interfaz)

    def _registrar_evento(self, evento) -> None:
        nombre = evento.resultado.nombre
        estado = evento.resultado.estado
        confianza = evento.resultado.confianza
        
        self._reproducir_sonido(estado)
        
        try:
            db.registrar_evento(
                usuario=nombre,
                estado=estado,
                confianza=confianza,
                distancia=getattr(evento.resultado, "distancia", None),
                umbral=getattr(evento.resultado, "umbral", None),
                motivo=getattr(evento.resultado, "motivo", None),
                evento="acceso_autorizado" if estado == "Autorizado" else "intento_denegado",
                track_id=str(evento.track_id),
            )
        except Exception:
            logger.exception("Imposible guardar el registro en la base de datos")

    def _reproducir_sonido(self, estado: str) -> None:
        if not winsound:
            logger.warning("winsound no está disponible (requiere Windows nativo).")
            return
        def _beep():
            try:
                if estado == "Autorizado":
                    # Sonido Éxito: Doble pitido agudo
                    winsound.Beep(2500, 150)
                    winsound.Beep(3000, 200)
                else:
                    # Sonido Alerta: Tres pitidos graves
                    winsound.Beep(500, 300)
                    time.sleep(0.05)
                    winsound.Beep(400, 400)
            except Exception as e:
                logger.error(f"No se pudo reproducir el sonido: {e}")
        threading.Thread(target=_beep, daemon=True).start()

    def cerrar_aplicacion(self) -> None:
        self.activa = False
        if self.hilo_camara and self.hilo_camara.is_alive():
            self.hilo_camara.join(timeout=1.0)
        if self.cap is not None:
            self.cap.release()
        if self.cap_registro is not None:
            self.cap_registro.release()
        try:
            self.window.quit()
            self.window.destroy()
        except Exception:
            pass
        sys.exit(0)

    def solicitar_login_operador(self) -> None:
        if self.activa: self.detener_camara()
        try:
            hay_operador = db.hay_operadores()
        except Exception:
            messagebox.showerror("Error", "No se pudo consultar la base de datos de operadores.")
            return

        if not hay_operador:
            self._crear_primer_operador()
            return

        login_win = ctk.CTkToplevel(self.window)
        login_win.title("Autorización ETITC")
        login_win.geometry("380x320")
        login_win.transient(self.window)
        login_win.grab_set()

        ctk.CTkLabel(login_win, text="INGRESO DE OPERADOR", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=(20, 15))
        e_user = ctk.CTkEntry(login_win, placeholder_text="Usuario", width=250)
        e_user.pack(pady=10)
        e_pass = ctk.CTkEntry(login_win, placeholder_text="Contraseña", show="*", width=250)
        e_pass.pack(pady=10)

        def validar(_=None):
            usuario = e_user.get().strip()
            password = e_pass.get()
            if not usuario or not password:
                messagebox.showwarning("Datos incompletos", "Ingrese usuario y contraseña.", parent=login_win)
                return
            try:
                ok, msj = db.autenticar_operador(usuario, password)
            except Exception:
                messagebox.showerror("Error", "No se pudo validar el acceso.", parent=login_win)
                return
            if ok:
                self.operador_actual = usuario
                login_win.grab_release() 
                login_win.destroy()
                self.abrir_panel_operador()
            else:
                messagebox.showerror("Denegado", msj, parent=login_win)
                e_pass.delete(0, tk.END)
                e_pass.focus_set()

        ctk.CTkButton(login_win, text="Ingresar", fg_color="#16A34A", hover_color="#15803d", command=validar).pack(pady=20)
        e_user.bind("<Return>", validar)
        e_pass.bind("<Return>", validar)
        e_user.focus_set()

    def _crear_primer_operador(self) -> None:
        vent = ctk.CTkToplevel(self.window)
        vent.title("Primer Operador")
        vent.geometry("420x400")
        vent.transient(self.window)
        vent.grab_set()

        ctk.CTkLabel(vent, text="CREAR PRIMER OPERADOR", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=(20, 5))
        ctk.CTkLabel(vent, text="No hay operadores activos. Cree uno para administrar el sistema.",
                     wraplength=360, text_color="#94A3B8").pack(pady=(0, 10))

        e_user = ctk.CTkEntry(vent, placeholder_text="Usuario", width=280)
        e_user.pack(pady=6)
        e_pass = ctk.CTkEntry(vent, placeholder_text="Contraseña", show="*", width=280)
        e_pass.pack(pady=6)
        e_conf = ctk.CTkEntry(vent, placeholder_text="Confirmar contraseña", show="*", width=280)
        e_conf.pack(pady=6)

        def crear(_=None):
            usuario = e_user.get().strip()
            if not usuario:
                messagebox.showwarning("Datos incompletos", "Ingrese un usuario.", parent=vent)
                return
            password = e_pass.get()
            if password != e_conf.get():
                messagebox.showerror("Error", "Las contraseñas no coinciden.", parent=vent)
                return
            try:
                db.crear_operador(usuario, password)
                db.registrar_auditoria(usuario, "operador_inicial_creado", "rol=operador")
            except Exception as exc:
                messagebox.showerror("Error", str(exc), parent=vent)
                return
            self.operador_actual = usuario
            vent.grab_release()
            vent.destroy()
            messagebox.showinfo("Éxito", "Operador creado correctamente.", parent=self.window)
            self.abrir_panel_operador()

        ctk.CTkButton(vent, text="Crear Operador", fg_color="#16A34A", hover_color="#15803d", command=crear).pack(pady=18)
        e_conf.bind("<Return>", crear)
        e_user.focus_set()

    def _cerrar_sesion(self) -> None:
        self.operador_actual = None
        if self.panel_op_win and self.panel_op_win.winfo_exists():
            self.panel_op_win.grab_release()
            self.panel_op_win.destroy()

    def abrir_panel_operador(self) -> None:
        if hasattr(self, 'panel_op_win') and self.panel_op_win and self.panel_op_win.winfo_exists():
            self.panel_op_win.deiconify()
            self.panel_op_win.grab_set()
            return

        panel_op = ctk.CTkToplevel(self.window)
        self.panel_op_win = panel_op
        usuario = self.operador_actual or "operador"
        panel_op.title(f"Panel de Administración - {usuario}")
        panel_op.geometry("450x450")
        panel_op.transient(self.window)
        panel_op.grab_set() 

        ctk.CTkLabel(panel_op, text="MENÚ DE ADMINISTRACIÓN", font=ctk.CTkFont(size=18, weight="bold")).pack(pady=(20, 5))
        ctk.CTkLabel(panel_op, text=f"Operador: {usuario}", text_color="#94A3B8").pack(pady=(0, 10))

        def navegar(opcion):
            panel_op.grab_release() 
            panel_op.withdraw()     
            
            if opcion == "registro": self.abrir_ventana_registro()
            elif opcion == "personas": self.mostrar_personas()
            elif opcion == "auditoria": self.mostrar_registros()

        ctk.CTkButton(panel_op, text="Registrar Nuevo Usuario", fg_color="#D97706", hover_color="#b45309", height=45, width=280, command=lambda: navegar("registro")).pack(pady=10)
        ctk.CTkButton(panel_op, text="Base de Datos Institucional", fg_color="#2563EB", hover_color="#1d4ed8", height=45, width=280, command=lambda: navegar("personas")).pack(pady=10)
        ctk.CTkButton(panel_op, text="Auditoría de Accesos", fg_color="#0F381E", hover_color="#1e5e34", height=45, width=280, command=lambda: navegar("auditoria")).pack(pady=10)
        ctk.CTkButton(panel_op, text="Cerrar Sesión", fg_color="#64748B", hover_color="#475569", height=35, command=self._cerrar_sesion).pack(pady=25)

    def _restaurar_panel(self):
        if self.panel_op_win and self.panel_op_win.winfo_exists():
            self.panel_op_win.deiconify()
            self.panel_op_win.grab_set()

    # -------------------------------------------------------------------------
    # 1. REGISTRO BIOMÉTRICO (INCLUYE PERFIL VISITANTE)
    # -------------------------------------------------------------------------
    def abrir_ventana_registro(self) -> None:
        if self.ventana_registro and self.ventana_registro.winfo_exists():
            self.ventana_registro.deiconify()
            self.ventana_registro.grab_set()
            return

        reg_win = ctk.CTkToplevel(self.window)
        reg_win.title("Registrar Nuevo Usuario")
        reg_win.geometry("750x850")
        reg_win.transient(self.window)
        reg_win.grab_set()
        self.ventana_registro = reg_win
        self.cap_registro = None
        self._registro_cerrado = False

        frame_superior = ctk.CTkFrame(reg_win, fg_color="transparent")
        frame_superior.pack(fill=tk.X, padx=20, pady=(15, 5))

        def cerrar_registro():
            if self._registro_cerrado:
                return
            self._registro_cerrado = True
            if self.cap_registro is not None:
                self.cap_registro.release()
                self.cap_registro = None
            if reg_win.winfo_exists():
                reg_win.grab_release()
                reg_win.destroy()
            self._restaurar_panel()

        ctk.CTkButton(frame_superior, text="⬅ Volver al Panel", fg_color="#64748B", hover_color="#475569", width=120, command=cerrar_registro).pack(side=tk.LEFT)
        ctk.CTkLabel(frame_superior, text="REGISTRO BIOMÉTRICO (6 ÁNGULOS)", font=ctk.CTkFont(size=16, weight="bold")).pack(side=tk.LEFT, padx=20)
        reg_win.protocol("WM_DELETE_WINDOW", cerrar_registro)

        frame_form = ctk.CTkFrame(reg_win, fg_color="transparent")
        frame_form.pack(fill=tk.X, padx=40, pady=5)

        ctk.CTkLabel(frame_form, text="Perfil Institucional / Acceso:", font=ctk.CTkFont(weight="bold")).pack(anchor="w")
        var_tipo = ctk.StringVar(value="Estudiante")
        combo_tipo = ctk.CTkComboBox(
            frame_form,
            variable=var_tipo,
            values=["Estudiante", "Profesor", "Administrativo", "Personal de aseo", "Visitante"],
            width=400,
            height=35,
            command=lambda _: construir_campos_detalle()
        )
        combo_tipo.pack(anchor="w", pady=(0, 10))

        ctk.CTkLabel(frame_form, text="Nombre Completo:", font=ctk.CTkFont(weight="bold")).pack(anchor="w")
        entry_nombre = ctk.CTkEntry(frame_form, width=400, height=35, placeholder_text="Nombres y apellidos")
        entry_nombre.pack(anchor="w", pady=(0, 10))

        frame_detalle = ctk.CTkFrame(frame_form, fg_color="transparent")
        frame_detalle.pack(fill=tk.X)

        detalles_vars: dict[str, ctk.CTkEntry] = {}

        def construir_campos_detalle():
            for widget in frame_detalle.winfo_children():
                widget.destroy()
            detalles_vars.clear()

            tipo = var_tipo.get()
            if tipo == "Estudiante":
                campos = (("Programa / Carrera:", "carrera"), ("Facultad:", "facultad"), ("Número de Celular:", "telefono"), ("Número de Documento:", "documento"))
            elif tipo == "Profesor":
                campos = (("Facultad:", "facultad"), ("Número de Teléfono:", "telefono"), ("Número de Documento:", "documento"))
            elif tipo == "Administrativo":
                campos = (("Cargo que ocupa:", "cargo"), ("Número de Teléfono:", "telefono"), ("Número de Documento:", "documento"))
            elif tipo == "Visitante":
                campos = (("Nombre del Referido (Anfitrión):", "anfitrion"), ("Número de Teléfono:", "telefono"), ("Número de Documento:", "documento"))
            else: # Personal de aseo
                campos = (("Número de Documento:", "documento"),)

            for etiqueta, clave in campos:
                ctk.CTkLabel(frame_detalle, text=etiqueta, font=ctk.CTkFont(weight="bold")).pack(anchor="w")
                entry = ctk.CTkEntry(frame_detalle, width=400, height=35)
                entry.pack(anchor="w", pady=(0, 8))
                detalles_vars[clave] = entry

        construir_campos_detalle()

        lbl_instruccion = ctk.CTkLabel(reg_win, text=PASOS_REGISTRO[0][0], text_color="#16A34A", font=ctk.CTkFont(size=14, weight="bold"))
        lbl_instruccion.pack(pady=10)

        cam_border = ctk.CTkFrame(reg_win, fg_color="#1E1E1E", width=420, height=260, corner_radius=10)
        cam_border.pack(pady=5)
        lbl_preview = ctk.CTkLabel(cam_border, text="Iniciando cámara...")
        lbl_preview.pack(expand=True)

        self.cap_registro = cv2.VideoCapture(config.CAMARA_INDICE)
        if not self.cap_registro.isOpened():
            self.cap_registro.release()
            messagebox.showerror("Cámara no disponible", "No se detectó la webcam.", parent=reg_win)
            cerrar_registro()
            return

        ultimo_frame = {"frame": None}
        fotos: list = []
        datos_registro: dict | None = None

        def actualizar_preview():
            if self._registro_cerrado or not reg_win.winfo_exists():
                return
            ret, frame = self.cap_registro.read()
            if ret:
                ultimo_frame["frame"] = frame.copy()
                img_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                img_tk = ctk.CTkImage(light_image=Image.fromarray(img_rgb), size=(400, 240))
                lbl_preview.configure(image=img_tk, text="")
            try:
                reg_win.after(30, actualizar_preview)
            except tk.TclError:
                pass

        actualizar_preview()

        def bloquear_formulario():
            combo_tipo.configure(state=tk.DISABLED)
            entry_nombre.configure(state=tk.DISABLED)
            for widget in detalles_vars.values():
                widget.configure(state=tk.DISABLED)

        def leer_formulario() -> dict:
            nombre = recognition.normalizar_display(entry_nombre.get())
            if not nombre:
                raise ValueError("Ingrese el nombre completo.")

            tipo = var_tipo.get().strip().lower()
            if tipo not in db.TIPOS_PERSONA:
                raise ValueError("Seleccione un perfil institucional o de acceso válido.")

            datos = {
                "nombre": nombre,
                "tipo_persona": tipo,
                "facultad": None,
                "carrera": None,
                "cargo": None,
                "documento": None,
                "telefono": None,
                "anfitrion": None,
            }
            for clave, widget in detalles_vars.items():
                datos[clave] = widget.get().strip() or None

            requeridos = {
                "estudiante": ("carrera", "facultad", "telefono", "documento"),
                "profesor": ("facultad", "telefono", "documento"),
                "administrativo": ("cargo", "telefono", "documento"),
                "personal de aseo": ("documento",),
                "visitante": ("anfitrion", "telefono", "documento"),
            }[tipo]
            faltantes = [campo for campo in requeridos if not datos.get(campo)]
            if faltantes:
                raise ValueError("Complete los datos obligatorios: " + ", ".join(faltantes) + ".")
            return datos

        def procesar_captura():
            nonlocal datos_registro
            frame = ultimo_frame.get("frame")
            if frame is None:
                messagebox.showwarning("Cámara", "Todavía no hay imagen de la cámara.", parent=reg_win)
                return

            valido, mensaje = recognition.validar_captura(frame)
            if not valido:
                messagebox.showwarning("Validación Fallida", mensaje, parent=reg_win)
                return

            if datos_registro is None:
                try:
                    datos_registro = leer_formulario()
                except ValueError as exc:
                    messagebox.showwarning("Datos incompletos", str(exc), parent=reg_win)
                    return
                bloquear_formulario()

            fotos.append(frame.copy())
            paso = len(fotos)

            if paso < 6:
                lbl_instruccion.configure(text=PASOS_REGISTRO[paso][0], text_color=PASOS_REGISTRO[paso][2])
                btn_capturar.configure(text=PASOS_REGISTRO[paso][1], fg_color=PASOS_REGISTRO[paso][2], hover_color=PASOS_REGISTRO[paso][2])
                return

            btn_capturar.configure(state=tk.DISABLED, text="Guardando registro...")
            carpeta = recognition.sanitizar_nombre(datos_registro["nombre"])
            existente = config.DATASET_DIR / carpeta
            if carpeta and existente.exists() and any(existente.glob("variante_*.jpg")):
                actualizar = messagebox.askyesno(
                    "Persona ya registrada",
                    "Ya existen fotos para esta persona.\n¿Desea reemplazarlas? "
                    "Las anteriores se guardarán en backups.",
                    parent=reg_win,
                )
                if not actualizar:
                    fotos.pop()
                    btn_capturar.configure(state=tk.NORMAL, text=PASOS_REGISTRO[5][1], fg_color=PASOS_REGISTRO[5][2], hover_color=PASOS_REGISTRO[5][2])
                    return

            try:
                self._guardar_registro(datos_registro, fotos)
            except Exception as exc:
                fotos.pop()
                btn_capturar.configure(state=tk.NORMAL, text=PASOS_REGISTRO[5][1], fg_color=PASOS_REGISTRO[5][2], hover_color=PASOS_REGISTRO[5][2])
                messagebox.showerror("Error al guardar", f"No se pudo guardar el registro:\n{exc}", parent=reg_win)
                return

            nombre = datos_registro["nombre"]
            cerrar_registro()
            try:
                self.galeria = recognition.cargar_galeria(config.DATASET_DIR, config.CACHE_PATH, force=True)
            except Exception:
                pass
            messagebox.showinfo("Éxito", f"Vectores biométricos guardados para {nombre}.", parent=self.window)

        btn_capturar = ctk.CTkButton(reg_win, text=PASOS_REGISTRO[0][1], fg_color=PASOS_REGISTRO[0][2], height=45, font=ctk.CTkFont(size=14, weight="bold"), command=procesar_captura)
        btn_capturar.pack(pady=20)

    def _guardar_registro(self, datos: dict, fotos: list) -> None:
        nombre = datos["nombre"]
        carpeta = recognition.sanitizar_nombre(nombre)

        config.DATASET_DIR.mkdir(parents=True, exist_ok=True)
        destino = config.DATASET_DIR / carpeta
        temporal = config.DATASET_DIR / f".tmp-{carpeta}-{int(time.time() * 1000)}"

        try:
            temporal.mkdir(parents=True, exist_ok=False)
            for indice, imagen in enumerate(fotos, 1):
                ruta_imagen = temporal / f"variante_{indice}.jpg"
                cv2.imwrite(str(ruta_imagen), imagen)

            metadata = {
                "nombre": nombre,
                "tipo_persona": datos["tipo_persona"],
                "facultad": datos.get("facultad"),
                "carrera": datos.get("carrera"),
                "cargo": datos.get("cargo"),
                "documento": datos.get("documento"),
                "telefono": datos.get("telefono"),
                "anfitrion": datos.get("anfitrion"),
                "actualizado_en": time.strftime("%Y-%m-%d %H:%M:%S"),
            }
            (temporal / "metadata.json").write_text(
                json.dumps(metadata, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            db.guardar_persona(
                nombre,
                datos["tipo_persona"],
                facultad=datos.get("facultad"),
                carrera=datos.get("carrera"),
                cargo=datos.get("cargo"),
                documento=datos.get("documento"),
                telefono=datos.get("telefono"),
                anfitrion=datos.get("anfitrion"),
                dataset_folder=carpeta,
            )

            if destino.exists():
                config.BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
                respaldo = config.BACKUPS_DIR / (f"dataset-{carpeta}-{time.strftime('%Y%m%d-%H%M%S')}")
                shutil.copytree(destino, respaldo)

            destino.mkdir(parents=True, exist_ok=True)
            for archivo in temporal.iterdir():
                archivo.replace(destino / archivo.name)
        finally:
            if temporal.exists():
                shutil.rmtree(temporal, ignore_errors=True)

        try:
            db.registrar_auditoria(self.operador_actual or "sistema", "persona_registrada", nombre)
        except Exception:
            pass

    # -------------------------------------------------------------------------
    # 2. BASE DE DATOS INSTITUCIONAL (ACTUALIZADA CON VISITANTE Y ANFITRIÓN)
    # -------------------------------------------------------------------------
    def mostrar_personas(self) -> None:
        vent = ctk.CTkToplevel(self.window)
        vent.title("Base de Datos - ETITC")
        vent.geometry("1250x600")
        vent.transient(self.window)
        vent.grab_set()
        
        def cerrar():
            vent.grab_release()
            vent.destroy()
            self._restaurar_panel()
        vent.protocol("WM_DELETE_WINDOW", cerrar)

        frame_top = ctk.CTkFrame(vent, fg_color="transparent")
        frame_top.pack(fill=tk.X, padx=20, pady=(15, 5))
        
        ctk.CTkButton(frame_top, text="⬅ Volver", width=80, fg_color="#64748B", command=cerrar).pack(side=tk.LEFT)
        ctk.CTkLabel(frame_top, text="BASE DE DATOS INSTITUCIONAL", font=ctk.CTkFont(size=16, weight="bold")).pack(side=tk.LEFT, padx=20)
        
        def exportar_personas():
            ruta = filedialog.asksaveasfilename(parent=vent, title="Exportar", defaultextension=".csv", filetypes=[("CSV", "*.csv")])
            if ruta:
                with open(ruta, "w", newline="", encoding="utf-8-sig") as f:
                    w = csv.writer(f)
                    w.writerow(columnas)
                    for item in tree.get_children(): w.writerow(tree.item(item, "values"))
                messagebox.showinfo("Éxito", f"Exportado a {ruta}", parent=vent)
                
        def importar_personas():
            ruta = filedialog.askopenfilename(parent=vent, title="Importar CSV", filetypes=[("Archivos CSV", "*.csv")])
            if not ruta: return
            
            try:
                conn = sqlite3.connect(config.DB_PATH)
                cursor = conn.cursor()
                actualizados = 0
                with open(ruta, "r", encoding="utf-8-sig") as f:
                    lector = csv.DictReader(f)
                    for fila in lector:
                        if not fila.get("ID") or not str(fila["ID"]).isdigit(): continue
                        p_id = int(fila["ID"])
                        nombre = fila.get("Nombre Completo", "")
                        rol = fila.get("Rol", "").lower()
                        facultad = fila.get("Facultad", "")
                        carrera = fila.get("Programa / Carrera", "")
                        cargo_anf = fila.get("Cargo / Anfitrión", "")
                        doc = fila.get("Documento", "")
                        tel = fila.get("Teléfono / Celular", "")
                        
                        cargo = cargo_anf if rol == "administrativo" else None
                        anfitrion = cargo_anf if rol == "visitante" else None

                        if facultad == "—": facultad = None
                        if carrera == "—": carrera = None
                        if cargo == "—": cargo = None
                        if doc == "—": doc = None
                        if tel == "—": tel = None
                        if anfitrion == "—": anfitrion = None
                        
                        cursor.execute('''
                            UPDATE personas SET nombre=?, tipo_persona=?, facultad=?, carrera=?, cargo=?, documento=?, telefono=?, anfitrion=? WHERE id=?
                        ''', (nombre, rol, facultad, carrera, cargo, doc, tel, anfitrion, p_id))
                        actualizados += 1
                conn.commit()
                conn.close()
                messagebox.showinfo("Éxito", f"Se han actualizado {actualizados} registros.", parent=vent)
                cargar() 
            except Exception as e:
                messagebox.showerror("Error de Importación", f"No se pudo actualizar:\n{e}", parent=vent)

        def eliminar_seleccionado():
            seleccion = tree.selection()
            if not seleccion:
                messagebox.showwarning("Atención", "Por favor, seleccione un registro de la lista para eliminar.", parent=vent)
                return
            
            valores = tree.item(seleccion[0], "values")
            p_id = valores[0]
            nombre = valores[1]
            
            respuesta = messagebox.askyesno(
                "Confirmar Eliminación Permanente",
                f"¿Está seguro de eliminar PERMANENTEMENTE a '{nombre}'?\n\nSe borrarán sus datos y su carpeta de fotos del dataset de forma definitiva.",
                parent=vent
            )
            if respuesta:
                try:
                    carpeta_nombre = recognition.sanitizar_nombre(nombre)
                    if carpeta_nombre:
                        ruta_fotos = config.DATASET_DIR / carpeta_nombre
                        if ruta_fotos.exists():
                            shutil.rmtree(ruta_fotos, ignore_errors=True)
                    
                    if config.DATASET_DIR.exists():
                        for item_dir in config.DATASET_DIR.iterdir():
                            if item_dir.is_dir() and item_dir.name.lower() == carpeta_nombre.lower():
                                shutil.rmtree(item_dir, ignore_errors=True)
                            if item_dir.is_dir() and item_dir.name.lower() == recognition.sanitizar_nombre(str(nombre)).lower():
                                shutil.rmtree(item_dir, ignore_errors=True)

                    conn = sqlite3.connect(config.DB_PATH)
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM personas WHERE id=?", (p_id,))
                    
                    for tbl in ["registros", "eventos", "accesos"]:
                        try:
                            cursor.execute(f"DELETE FROM {tbl} WHERE usuario = ?", (nombre,))
                        except Exception:
                            pass
                            
                    conn.commit()
                    conn.close()
                    
                    try:
                        self.galeria = recognition.cargar_galeria(config.DATASET_DIR, config.CACHE_PATH, force=True)
                    except Exception:
                        pass
                    
                    cargar()
                    messagebox.showinfo("Éxito", f"'{nombre}' y su carpeta de fotos han sido eliminados permanentemente.", parent=vent)
                except Exception as e:
                    messagebox.showerror("Error", f"No se pudo completar la eliminación:\n{e}", parent=vent)

        ctk.CTkButton(frame_top, text="🗑 Eliminar Permanente", width=160, fg_color="#DC2626", hover_color="#991b1b", font=ctk.CTkFont(weight="bold"), command=eliminar_seleccionado).pack(side=tk.RIGHT, padx=(10, 0))
        ctk.CTkButton(frame_top, text="📥 Exportar a CSV", width=140, fg_color="#2563EB", hover_color="#1d4ed8", font=ctk.CTkFont(weight="bold"), command=exportar_personas).pack(side=tk.RIGHT, padx=5)
        ctk.CTkButton(frame_top, text="📤 Importar CSV", width=140, fg_color="#16A34A", hover_color="#15803d", font=ctk.CTkFont(weight="bold"), command=importar_personas).pack(side=tk.RIGHT)
        
        frame_filtros = ctk.CTkFrame(vent, fg_color="transparent")
        frame_filtros.pack(fill=tk.X, padx=20, pady=(0, 10))

        var_buscar = ctk.StringVar()
        var_rol = ctk.StringVar(value="Todos")

        ctk.CTkLabel(frame_filtros, text="Buscar:").pack(side=tk.LEFT)
        entry_b = ctk.CTkEntry(frame_filtros, textvariable=var_buscar, width=200)
        entry_b.pack(side=tk.LEFT, padx=10)

        ctk.CTkLabel(frame_filtros, text="Rol:").pack(side=tk.LEFT)
        combo_r = ctk.CTkComboBox(frame_filtros, variable=var_rol, values=["Todos", "Estudiante", "Profesor", "Administrativo", "Personal de aseo", "Visitante"])
        combo_r.pack(side=tk.LEFT, padx=10)
        
        lbl_total = ctk.CTkLabel(frame_filtros, text="", text_color="#16A34A", font=ctk.CTkFont(weight="bold"))
        lbl_total.pack(side=tk.RIGHT)

        cont = ctk.CTkFrame(vent, fg_color="transparent")
        cont.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0,20))

        columnas = ("ID", "Nombre Completo", "Rol", "Facultad", "Programa / Carrera", "Cargo / Anfitrión", "Documento", "Teléfono / Celular", "Total Accesos")
        tree = ttk.Treeview(cont, columns=columnas, show="headings")
        for c in columnas: tree.heading(c, text=c)
        
        tree.column("ID", width=40)
        tree.column("Nombre Completo", width=180)
        tree.column("Rol", width=110)
        tree.column("Facultad", width=130)
        tree.column("Programa / Carrera", width=140)
        tree.column("Cargo / Anfitrión", width=150)
        tree.column("Documento", width=110)
        tree.column("Teléfono / Celular", width=110)
        tree.column("Total Accesos", width=90)

        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb = ttk.Scrollbar(cont, command=tree.yview)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        tree.configure(yscrollcommand=sb.set)

        def cargar(*_args):
            for i in tree.get_children(): tree.delete(i)
            txt = var_buscar.get().lower()
            rol = var_rol.get().lower()
            c = 0
            for f in db.listar_personas():
                try:
                    nombre = str(f["nombre"])
                except Exception:
                    nombre = ""
                
                if not nombre: continue
                
                carpeta = config.DATASET_DIR / recognition.sanitizar_nombre(nombre)
                if not carpeta.exists():
                    try:
                        conn_auto = sqlite3.connect(config.DB_PATH)
                        conn_auto.execute("DELETE FROM personas WHERE id = ?", (f["id"],))
                        conn_auto.commit()
                        conn_auto.close()
                    except:
                        pass
                    continue  
                
                try: t_db = (f["tipo_persona"] or "").lower()
                except: t_db = ""
                
                if rol != "todos" and rol != t_db: continue
                
                try: facultad = f["facultad"] or "—" 
                except: facultad = "—"
                try: carrera = f["carrera"] or "—" 
                except: carrera = "—"
                
                try:
                    if t_db == "visitante":
                        cargo_anf = f.get("anfitrion") or "—"
                    else:
                        cargo_anf = f["cargo"] or "—"
                except:
                    cargo_anf = "—"
                    
                try: documento = f["documento"] or "—" 
                except: documento = "—"
                try: telefono = f["telefono"] or "—"
                except: telefono = "—"
                
                vals = (f["id"], nombre, t_db.capitalize() or "—", facultad, carrera, cargo_anf, documento, telefono, f["total_registros"])
                
                if txt and txt not in " ".join(str(v).lower() for v in vals): continue
                tree.insert("", tk.END, values=vals)
                c += 1
            lbl_total.configure(text=f"Total: {c} registrados válidos")

        entry_b.bind("<KeyRelease>", cargar)
        combo_r.configure(command=cargar)
        cargar()

    # -------------------------------------------------------------------------
    # 3. AUDITORÍA DE ACCESOS
    # -------------------------------------------------------------------------
    def mostrar_registros(self) -> None:
        vent = ctk.CTkToplevel(self.window)
        vent.title("Auditoría de Accesos")
        vent.geometry("1200x600")
        vent.transient(self.window)
        vent.grab_set()

        def cerrar():
            vent.grab_release()
            vent.destroy()
            self._restaurar_panel()
        vent.protocol("WM_DELETE_WINDOW", cerrar)

        frame_top = ctk.CTkFrame(vent, fg_color="transparent")
        frame_top.pack(fill=tk.X, padx=20, pady=(15, 5))
        
        ctk.CTkButton(frame_top, text="⬅ Volver", width=80, fg_color="#64748B", command=cerrar).pack(side=tk.LEFT)
        ctk.CTkLabel(frame_top, text="AUDITORÍA Y CONTROL DE ACCESOS", font=ctk.CTkFont(size=16, weight="bold")).pack(side=tk.LEFT, padx=20)
        
        def exportar_accesos():
            ruta = filedialog.asksaveasfilename(parent=vent, title="Exportar", defaultextension=".csv", filetypes=[("CSV", "*.csv")])
            if ruta:
                with open(ruta, "w", newline="", encoding="utf-8-sig") as f:
                    w = csv.writer(f)
                    w.writerow(columnas)
                    for item in tree.get_children(): w.writerow(tree.item(item, "values"))
                messagebox.showinfo("Éxito", f"Exportado a {ruta}", parent=vent)

        ctk.CTkButton(frame_top, text="📥 Exportar a CSV", width=140, fg_color="#2563EB", hover_color="#1d4ed8", font=ctk.CTkFont(weight="bold"), command=exportar_accesos).pack(side=tk.RIGHT)

        frame_filtros = ctk.CTkFrame(vent, fg_color="transparent")
        frame_filtros.pack(fill=tk.X, padx=20, pady=(0, 10))

        var_texto = ctk.StringVar()
        var_est = ctk.StringVar(value="Todos")

        ctk.CTkLabel(frame_filtros, text="Buscar Nombre/Fecha:").pack(side=tk.LEFT)
        e_b = ctk.CTkEntry(frame_filtros, textvariable=var_texto, width=200)
        e_b.pack(side=tk.LEFT, padx=10)

        ctk.CTkLabel(frame_filtros, text="Estado:").pack(side=tk.LEFT)
        c_e = ctk.CTkComboBox(frame_filtros, variable=var_est, values=["Todos", "Autorizado", "Denegado"])
        c_e.pack(side=tk.LEFT, padx=10)

        lbl_tot = ctk.CTkLabel(frame_filtros, text="", text_color="#16A34A", font=ctk.CTkFont(weight="bold"))
        lbl_tot.pack(side=tk.RIGHT)

        cont = ctk.CTkFrame(vent, fg_color="transparent")
        cont.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0,20))

        columnas = ("Fecha", "Hora", "Nombre de Persona", "Condición", "Rol Institucional", "Facultad", "Carrera", "Resolución")
        tree = ttk.Treeview(cont, columns=columnas, show="headings")
        
        for c in columnas: tree.heading(c, text=c)
        tree.column("Fecha", width=100)
        tree.column("Hora", width=90)
        tree.column("Nombre de Persona", width=200)
        tree.column("Condición", width=130)
        tree.column("Rol Institucional", width=140)
        tree.column("Facultad", width=150)
        tree.column("Carrera", width=150)
        tree.column("Resolución", width=100)

        tree.tag_configure("desconocido", foreground="#ef4444")

        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb = ttk.Scrollbar(cont, command=tree.yview)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        tree.configure(yscrollcommand=sb.set)

        diccionario_personas = {p["nombre"]: p for p in db.listar_personas()}

        def cargar(*_args):
            for i in tree.get_children(): tree.delete(i)
            txt = var_texto.get().lower()
            est = var_est.get().lower()
            
            try:
                filas = db.listar_registros(limite=2000)
            except TypeError:
                filas = db.listar_registros()
            except Exception:
                filas = []
            
            c = 0
            for fila in filas:
                try: fh = str(fila["fecha_hora"])
                except: fh = "—"
                
                partes = fh.split(" ")
                fecha = partes[0] if len(partes) > 0 else "—"
                hora = partes[1] if len(partes) > 1 else "—"

                try: nombre = str(fila["usuario"])
                except: nombre = "Desconocido"
                
                try: resolucion = str(fila["estado"])
                except: resolucion = "Denegado"
                
                if nombre == "Desconocido" or nombre == "None" or not nombre:
                    nombre = "Desconocido"
                    condicion = "NO REGISTRADO"
                    rol = "—"
                    facultad = "—"
                    carrera = "—"
                    tags = ("desconocido",)
                else:
                    condicion = "REGISTRADO"
                    info_persona = diccionario_personas.get(nombre, {})
                    
                    try: rol = (info_persona["tipo_persona"] or "—").capitalize()
                    except: rol = "—"
                    try: facultad = info_persona["facultad"] or "—"
                    except: facultad = "—"
                    try: carrera = info_persona["carrera"] or "—"
                    except: carrera = "—"
                    
                    tags = ()

                vals = (fecha, hora, nombre, condicion, rol, facultad, carrera, resolucion)
                
                if est != "todos" and est != resolucion.lower():
                    continue
                if txt and txt not in " ".join(str(v).lower() for v in vals):
                    continue
                    
                tree.insert("", tk.END, values=vals, tags=tags)
                c += 1

            lbl_tot.configure(text=f"Total: {c} accesos")

        e_b.bind("<KeyRelease>", cargar)
        c_e.configure(command=cargar)
        cargar()

def main() -> None:
    root = ctk.CTk()
    app = SistemaReconocimientoApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()