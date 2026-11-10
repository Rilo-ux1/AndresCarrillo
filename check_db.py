#!/usr/bin/env python
import os
import sys

os.chdir(r"C:\Users\HP\onedrive\Escritorio\PPP")
sys.path.insert(0, ".")

import db

print('TIPOS_PERSONA:', db.TIPOS_PERSONA)
print()
print('Hay operadores:', db.hay_operadores())
personas = db.listar_personas()
print('Personas en BD:', len(personas))
for p in personas[:3]:
    n = p['nombre']
    t = p['tipo_persona']
    f = p.get('facultad')
    c = p.get('carrera')
    print('  - ' + n + ' (' + t + ') - facultad: ' + str(f) + ', carrera: ' + str(c))