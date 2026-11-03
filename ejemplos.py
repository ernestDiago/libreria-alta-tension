"""
Ejemplos de uso de la librería alta_tension.

    python ejemplos.py
"""

import pandas as pd

import alta_tension as at

pd.set_option("display.width", 200)
pd.set_option("display.max_columns", 20)


def titulo(texto):
    print(f"\n{'=' * 70}\n{texto}\n{'=' * 70}")


def ejemplo_modelos_electricos():
    "Línea de 400 kV y 80 km que alimenta una carga de 600 MW con cos φ = 0,8 inductivo"
    titulo("1. MODELOS ELÉCTRICOS")

    # Unidades: Pf [MW], Uf [kV], L [km], r y x [Ω/km], g y b [S/km]
    linea = at.Modelo(
        Pf=600, fp=0.8, Uf=400, L=80, r=0.012, x=0.15, g=0, b=2.7e-6, caracter="inductivo"
    )

    print(f"Z = {linea.Z:.2f} Ω,  Y = {linea.Y:.6f} S\n")
    print(linea.comparar().round(3))

    print("\nSolo el modelo en π:")
    for magnitud, valor in linea.pi().items():
        print(f"  {magnitud}: {valor:.3f}")


def ejemplo_vano_a_nivel():
    """Ejemplo de clase "Cálculo mecánico de un vano a nivel":
    20 kV, LA-56, 600 m de altitud, vano 170 m, viento máximo 130 km/h, E = 7949 daN/mm²"""
    titulo("2. CÁLCULO MECÁNICO: VANO A NIVEL")

    cable = at.Conductor("LA 56", E_dato=7949, alfa_dato=19.1e-6)
    print(
        f"{cable.conductor}: p = {cable.p:.4f} daN/m, d = {cable.d} mm, "
        f"S = {cable.S} mm², rotura = {cable.rotura:.0f} daN"
    )

    calc = at.calculoMecanico(cable, Un=20, alt=600, vano=170, Vv=130)
    print(f"Zona {calc.Zona}, categoría {calc.categoria}, coef. seguridad {calc.coef}\n")
    print(calc.resolver().round(2))
    print(f"\nHipótesis que manda: {calc.dominante}")
    print(f"Flecha máxima: {calc.flecha_maxima:.2f} m")

    print("\nTabla de tendido:")
    print(calc.tabla_tendido(range(0, 45, 5)).round(2))

    # Para guardar las tres tablas (datos, hipótesis y tendido) en un Excel:
    # calc.exportar_excel("calculo_mecanico_LA56.xlsx", range(0, 45, 5))


def ejemplo_vano_a_desnivel():
    """Ejercicio de clase "Cálculo mecánico de vano desnivelado":
    20 kV, LA-78, 400 m de altitud, vano proyectado 220 m, desnivel 70 m"""
    titulo("3. CÁLCULO MECÁNICO: VANO A DESNIVEL")

    cable = at.Conductor("LA 78", E_dato=7949, alfa_dato=19.1e-6)
    calc = at.calculoMecanico(cable, Un=20, alt=400, vano=220, desnivel=70)

    print(f"Vano real b = {calc.vano_real:.2f} m")
    print("T0_daN es la tensión Tm en el punto medio y Tmax_daN la tensión TB en el apoyo alto\n")
    print(calc.resolver().round(2))
    print(f"\nHipótesis que manda: {calc.dominante}")
    print(f"Flecha máxima: {calc.flecha_maxima:.2f} m")


def main():
    ejemplo_modelos_electricos()
    ejemplo_vano_a_nivel()
    ejemplo_vano_a_desnivel()


if __name__ == "__main__":
    main()
