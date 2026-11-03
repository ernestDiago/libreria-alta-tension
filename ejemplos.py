"""
Ejemplos de uso de la librería alta_tension.

Ejecuta el archivo entero (F5) o celda a celda (Ctrl+Enter).
"""

import pandas as pd

import alta_tension as at

pd.set_option("display.width", 200)
pd.set_option("display.max_columns", 20)

# %% 1. Modelos eléctricos de una línea
# Línea de 400 kV y 80 km que alimenta una carga de 600 MW con cos φ = 0,8 inductivo.
# Unidades: Pf [MW], Uf [kV], L [km], r y x [Ω/km], g y b [S/km]
linea = at.Modelo(
    Pf=600, fp=0.8, Uf=400, L=80, r=0.012, x=0.15, g=0, b=2.7e-6, caracter="inductivo"
)

print(f"Z = {linea.Z:.2f} Ω,  Y = {linea.Y:.6f} S")
print(linea.comparar().round(3))

# %% 1b. Un solo modelo
for magnitud, valor in linea.pi().items():
    print(f"{magnitud}: {valor:.3f}")

# %% 2. Cálculo mecánico del conductor
# Ejemplo de clase "Cálculo mecánico de un vano a nivel":
# 20 kV, LA-56, 600 m de altitud, vano 170 m, viento máximo 130 km/h, E = 7949 daN/mm²
cable = at.Conductor("LA 56", E_dato=7949, alfa_dato=19.1e-6)
print(
    f"{cable.conductor}: p = {cable.p:.4f} daN/m, d = {cable.d} mm, "
    f"S = {cable.S} mm², rotura = {cable.rotura:.0f} daN"
)

calc = at.calculoMecanico(cable, Un=20, alt=600, vano=170, Vv=130)

print(f"Zona {calc.Zona}, categoría {calc.categoria}, coef. seguridad {calc.coef}")
print(calc.resolver().round(2))
print(f"\nHipótesis que manda: {calc.dominante}")
print(f"Flecha máxima: {calc.flecha_maxima:.2f} m")

# %% 2b. Tabla de tendido
print(calc.tabla_tendido(range(0, 45, 5)).round(2))

# %% 3. Exportar el cálculo mecánico a Excel
# Descomenta la línea para generar el archivo con las tres hojas (datos, hipótesis y tendido)
# calc.exportar_excel("calculo_mecanico_LA56.xlsx", range(0, 45, 5))
