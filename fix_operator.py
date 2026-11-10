#!/usr/bin/env python
import os
import sys
import sqlite3

os.chdir(r"C:\Users\HP\onedrive\Escritorio\PPP")
sys.path.insert(0, "ReconocimientoFacial")
import db

print("=== FIX: Desbloquear cuenta OperadorEtitc ===\n")

# 1. Resetear la base de datos - desbloquear cuenta
conn = sqlite3.connect(str(db.DB_PATH))
cursor = conn.cursor()
cursor.execute('UPDATE operadores SET fallos_intentos = 0, bloqueo_hasta = NULL WHERE usuario = ?', ('OperadorEtitc',))
conn.commit()
print("✅ Cuenta OperadorEtitc desbloqueada (intentos reiniciados)")

# 2. Verificar estado actual
cursor.execute('SELECT fallos_intentos, bloqueo_hasta, activo FROM operadores WHERE usuario = ?', ('OperadorEtitc',))
row = cursor.fetchone()
print(f"Estado actual - fallos: {row[0]}, bloqueo: {row[1]}, activo: {row[2]}")
conn.close()

# 3. Probar autenticación con password por defecto
print("\n=== Probar autenticación ===")
ok, msj = db.autenticar_operador('OperadorEtitc', 'ETITC2024')
print(f"ETITC2024: ok={ok} msg={msj}")

ok, msj = db.autenticar_operador('OperadorEtitc', 'OperadorEtitc')
print(f"OperadorEtitc: ok={ok} msg={msj}")

ok, msj = db.autenticar_operador('OperadorADJ', 'OperadorADJ')
print(f"OperadorADJ: ok={ok} msg={msj}")

# 3. Si la contraseña por defecto no funciona, crear uno nuevo
if not ok:
    print("\n=== Creando nuevo operador ===")
    try:
        db.crear_operador('ETITC', 'ETITC2024')
        db.registrar_auditoria('ETITC', 'operador_inicial_creado', 'rol=operador')
        print("✅ Nuevo operador creado: ETITC / ETITC2024")
    except Exception as e:
        print(f"❌ Error creando operador: {e}")

print("\n=== Verificación final ===")
ok, msj = db.autenticar_operador('OperadorEtitc', 'ETITC2024')
print(f"Login final - ok={ok} msg={msj}")