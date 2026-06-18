#!/usr/bin/env python3
"""
SCRIPT DEBUG - Analizar qué datos retorna obtener_datos_bd
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import tkinter as tk
from Roles_generador_VIZUALIZADOR_10 import GeneradorRolesPagoINSEVIG
import pandas as pd

# Crear instancia del generador
dummy_root = tk.Tk()
generador = GeneradorRolesPagoINSEVIG(dummy_root)

# Obtener datos para un período específico
periodo = "2026-06"
print(f"\n{'='*80}")
print(f"EXTRAYENDO DATOS DEL PERÍODO: {periodo}")
print(f"{'='*80}\n")

df = generador.obtener_datos_bd(periodo)

if df is None:
    print("ERROR: obtener_datos_bd retornó None")
    sys.exit(1)

if df.empty:
    print("ERROR: obtener_datos_bd retornó DataFrame vacío")
    sys.exit(1)

print(f"Total de empleados: {len(df)}")
print(f"\nColumnas disponibles:")
print(df.columns.tolist())

# Mostrar primer empleado
if len(df) > 0:
    emp = df.iloc[0]
    print(f"\n{'='*80}")
    print(f"PRIMER EMPLEADO: {emp['APELLIDOS_NOMBRES']}")
    print(f"{'='*80}")
    print(f"Cédula: {emp['CEDULA']}")
    print(f"Cargo: {emp['CARGO']}")
    print(f"Depto: {emp['DEPTO']}")
    
    # Mostrar todos los conceptos
    conceptos_ing = ['SUELDO', 'BONIFICACION', 'FONDO_RESERVA', 'DECIMO_TERCERA', 'DECIMO_CUARTA',
                    'MANIOBRAS', 'REEMBOLSOS', 'SOBRETIEMPO_25', 'SOBRETIEMPO_50', 'SOBRETIEMPO_100', 'MOVILIZACION']
    conceptos_egr = ['APORT_IESS', 'PRESTAMOS_QUIROGRAFARIOS', 'PRESTAMOS_COMPANIA', 'ANTICIPO_SUELDO',
                    'ANTICIPOS_OTROS', 'ANTICIPOS_SURTIDOS', 'APORT_IESS_CONYUGE', 'IMPUESTO_RENTA',
                    'MULTAS', 'PENSION_ALIMENTICIA', 'PRESTAMO_HIPOTECARIO']
    
    print(f"\n--- INGRESOS ---")
    total_ing = 0
    for concepto in conceptos_ing:
        val = emp.get(concepto, 0)
        if val > 0 or val < 0:
            print(f"  {concepto:30s}: {val:>12.2f}")
            total_ing += val
    
    print(f"\n--- EGRESOS ---")
    total_egr = 0
    for concepto in conceptos_egr:
        val = emp.get(concepto, 0)
        if val > 0 or val < 0:
            print(f"  {concepto:30s}: {val:>12.2f}")
            total_egr += val
    
    print(f"\n--- TOTALES CALCULADOS ---")
    print(f"  TOTAL INGRESOS:    {emp.get('TOTAL_INGRESOS', total_ing):>12.2f}")
    print(f"  TOTAL EGRESOS:     {emp.get('TOTAL_EGRESOS', total_egr):>12.2f}")
    print(f"  TOTAL RECIBIR:     {emp.get('TOTAL_RECIBIR', total_ing - total_egr):>12.2f}")
    print(f"  DÍAS:              {emp.get('DIAS', 0):>12.0f}")
    
    # Mostrar todos los campos
    print(f"\n--- TODOS LOS CAMPOS (raw) ---")
    for col in df.columns:
        val = emp[col]
        if isinstance(val, float):
            print(f"  {col:30s}: {val:>15.2f}")
        else:
            print(f"  {col:30s}: {str(val):>15s}")

# Buscar un empleado específico (Pereira Campoverde)
print(f"\n{'='*80}")
print(f"BUSCANDO EMPLEADOS CON 'PEREIRA'")
print(f"{'='*80}")

mask = df['APELLIDOS_NOMBRES'].str.contains('PEREIRA', case=False, na=False)
pereira = df[mask]

if len(pereira) > 0:
    for idx, (i, emp) in enumerate(pereira.iterrows()):
        print(f"\n{idx+1}. {emp['APELLIDOS_NOMBRES']}")
        print(f"   Cédula: {emp['CEDULA']}")
        print(f"   SUELDO: {emp.get('SUELDO', 0):.2f}")
        print(f"   TOTAL_INGRESOS: {emp.get('TOTAL_INGRESOS', 0):.2f}")
        print(f"   TOTAL_EGRESOS: {emp.get('TOTAL_EGRESOS', 0):.2f}")
        print(f"   TOTAL_RECIBIR: {emp.get('TOTAL_RECIBIR', 0):.2f}")
else:
    print("No se encontraron empleados con 'PEREIRA'")

print(f"\n{'='*80}")
print("FIN DEL DEBUG")
print(f"{'='*80}\n")

dummy_root.destroy()
