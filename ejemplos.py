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


# ============================================
#        Modelos Eléctrcos
# ============================================
"""
De esta clase podemos sacar todos lo parametros que se utilicen para el cálculo de
los modelos. Los principales métodos son el .comparar() que crea una tabla con todos
los modelos resueltos pero también se puede sacar cada uno por separado con .inductivo(),
.pi(), etc
"""

# Unidades: Pf [MW], Uf [kV], L [km], r y x [Ω/km], g y b [S/km]
modelo_electrico = at.Modelo(
    Pf=600,
    fp=0.8,
    Uf=400,
    L=80,
    r=0.012,
    x=0.15,
    g=0,
    b=2.7e-6,
    caracter="inductivo",
)
tabla_comparativa = modelo_electrico.comparar()
print(titulo("Modelos eléctricos"))
print(tabla_comparativa)

# Si quieres un modelo en concreto podemos unsar .inductivo() pero sale feo,
# así qu eprefiero usar .comparar()['{Nombre del modelo}']

# Solo parametros distribuidos
distribuidos = tabla_comparativa["Modelo parametros distribuidos"]
print("\nSolo modelo parametros distribuidos")
print(distribuidos)


# ==================================================
#        Características de la línea
# ==================================================

# La clase Linea devuelve las caractrerísticas de la linea
linea = at.Linea(
    Un=400,  # Tensión de la linea en kV
    alt=0,  # Altitud de la linea (m)
    Vv=130,  # Viento excepcional
    coef_seguridad=3,  # Coeficiente de seguridad con lo que se calculara todo
    antivibradores=True,  # Puedes añadir antivirbadores
    # chs=0.20, #Pudes añadir un CHS manualmente, si no lo haces 0.2 se pone por defecto
    # eds=0.22 #se puede poner manual, pero si no se pone se ajusta según la norma
)
print(titulo("Características de la Línea"))
print(linea.resumen())  # Este método cra una tabla resumen de la Linea


# ======================================================
#        Características de los conductores
# ======================================================

titulo("Conductores")

cable_LA56 = at.Conductor("LA 56")
cable_LA110 = at.Conductor("LA 110")

print(cable_LA110.resumen() )  # Esto devuelve una tabla con todos los datos del cable
print(cable_LA56.resumen())

# Luego también puedes modificar el límite elástico y el coef. de expansión, porque en las tablas no aparecen,
# así si son distintos al por defecto lo puedes editar

cable_LA110 = at.Conductor("LA 110", E_dato=8175, alfa_dato=17.9e-6)
print(cable_LA110.E)

#La clase tambieen devuelve las presiones por cada hiótesis Hielo para conas B,C y viento

print(cable_LA110.presion_viento())
print(cable_LA110.p_total_viento())

print(f"La sobrecarga de hielo en zona B es {cable_LA110.p_total_hielo("B")}") #Devuelve el total de helo en zona B
print(f"La sobrecarga de hielo en zona C es {cable_LA110.p_total_hielo("C")}")

# ======================================================
#        Calculo mecánico del conductor
# ======================================================

print(titulo("Calculo mecánico"))
calculo_mecanico = at.calculoMecanico(conductor=cable_LA110, linea = linea, vano = 200)
print(calculo_mecanico.resolver())
print("\nTABLA DE TENEDIDO")
print(calculo_mecanico.tabla_tendido())

# def ejemplo_vano_a_nivel():
#     """Ejemplo de clase "Cálculo mecánico de un vano a nivel":
#     20 kV, LA-56, 600 m de altitud, vano 170 m, viento máximo 130 km/h, E = 7949 daN/mm²"""
#     titulo("2. CÁLCULO MECÁNICO: VANO A NIVEL")

#     cable = at.Conductor("LA 56", E_dato=7949, alfa_dato=19.1e-6)
#     print(
#         f"{cable.conductor}: p = {cable.p:.4f} daN/m, d = {cable.d} mm, "
#         f"S = {cable.S} mm², rotura = {cable.rotura:.0f} daN"
#     )

#     calc = at.calculoMecanico(cable, at.Linea(Un=20, alt=600, Vv=130), vano=170)
#     print(
#         f"Zona {calc.linea.Zona}, categoría {calc.linea.categoria}, coef. seguridad {calc.linea.coef}\n"
#     )
#     print(calc.resolver().round(2))
#     print(f"\nHipótesis que manda: {calc.dominante}")
#     print(f"Flecha máxima: {calc.flecha_maxima:.2f} m")

#     print("\nTabla de tendido:")
#     print(calc.tabla_tendido(range(0, 45, 5)).round(2))

#     # Para guardar las tres tablas (datos, hipótesis y tendido) en un Excel:
#     # calc.exportar_excel("calculo_mecanico_LA56.xlsx", range(0, 45, 5))


# def ejemplo_vano_a_desnivel():
#     """Ejercicio de clase "Cálculo mecánico de vano desnivelado":
#     20 kV, LA-78, 400 m de altitud, vano proyectado 220 m, desnivel 70 m"""
#     titulo("3. CÁLCULO MECÁNICO: VANO A DESNIVEL")

#     cable = at.Conductor("LA 78", E_dato=7949, alfa_dato=19.1e-6)
#     calc = at.calculoMecanico(cable, at.Linea(Un=20, alt=400), vano=220, desnivel=70)

#     print(f"Vano real b = {calc.vano_real:.2f} m")
#     print(
#         "T0_daN es la tensión Tm en el punto medio y Tmax_daN la tensión TB en el apoyo alto\n"
#     )
#     print(calc.resolver().round(2))
#     print(f"\nHipótesis que manda: {calc.dominante}")
#     print(f"Flecha máxima: {calc.flecha_maxima:.2f} m")
#     print("\nTabla de tendido:")
#     print(calc.tabla_tendido(range(0, 45, 5)).round(2))


# def ejemplo_apoyos_tensiones_del_enunciado():
#     """Ejercicio de evaluación continua SJR005: cruce de un valle con LA-180 a 600 m de altitud.
#     El enunciado da las tensiones de los vanos y pide los apoyos 3 y 4"""
#     titulo("4. APOYOS CON LAS TENSIONES DEL ENUNCIADO")

#     cable = at.Conductor("LA 180", E_dato=8000, alfa_dato=17.8e-6)
#     tensiones = pd.DataFrame(
#         {"hielo": [2107, 2107, 2116], "viento": [1747, 1747, 1758]},
#         index=["2-3", "3-4", "4-5"],
#     )
#     apoyos = at.CalculoApoyos(
#         conductor=cable,
#         linea=at.Linea(Un=20, alt=600),
#         vanos=[210, 270, 270, 240],
#         desniveles=[0, 5, -20, 20, 20],
#         tipos=["fin de línea", "amarre", "anclaje", "amarre", "fin de línea"],
#         angulos={4: 45},
#         tensiones=tensiones,
#         peso_cadena_amarre=12,  # incluye los herrajes
#         peso_cruceta=70,
#         brazo_cruceta=1.75,
#     )

#     apoyos.esquema(ruta="esquema_apoyos.png", mostrar=False)  # mostrar=True para verlo en pantalla
#     print("Esquema guardado en esquema_apoyos.png")
#     print(f"\nTensiones de cada vano (del enunciado):\n{apoyos.tensiones}")

#     for numero in (3, 4):
#         print(f"\nApoyo {numero}: {apoyos.etiqueta(numero).replace(chr(10), ' ')}")
#         print(
#             f"  gravivano viento {apoyos.gravivano(numero, 'viento'):.1f} m, "
#             f"hielo {apoyos.gravivano(numero, 'hielo'):.1f} m, "
#             f"eolovano {apoyos.eolovano(numero):.0f} m"
#         )
#         print(f"  hipótesis: {', '.join(apoyos.hipotesis_aplicables(numero))}")
#         print(apoyos.esfuerzos(numero).round(1).fillna("-"))


# def ejemplo_apoyos_tensiones_calculadas():
#     """Ejemplo SJR005 "Cálculo mecánico de apoyos de una línea aérea de 3ª categoría":
#     LA-110 a 1200 m, EDS 8,7 % y CHS 15,9 %. Las tensiones las calcula la librería por cantones.
#     Suspensiones de chapa con cruceta de bóveda; el resto, de celosía con cruceta recta"""
#     titulo("5. APOYOS CALCULANDO LAS TENSIONES POR CANTONES")

#     cable = at.Conductor("LA 110", E_dato=8047, alfa_dato=17.8e-6)
#     apoyos = at.CalculoApoyos(
#         conductor=cable,
#         linea=at.Linea(Un=20, alt=1200, eds=0.087, chs=0.159),
#         vanos=[160, 150, 145, 140, 150, 160],
#         desniveles=[0, 0, 0, 5, 10, -10, 15],
#         tipos=["fin de línea", "suspensión", "anclaje", "suspensión", "amarre", "suspensión",
#                "fin de línea"],
#         angulos={5: 30},
#         peso_cadena_amarre=10 + 2,
#         peso_cadena_suspension=8 + 1,
#         peso_cruceta=70,  # recta
#         peso_cruceta_suspension=56,  # bóveda
#         brazo_cruceta=1.75,
#         formas=["celosía", "chapa", "celosía", "chapa", "celosía", "chapa", "celosía"],
#         factor_chapa=at.factor_reduccion_chapa(b=1.365, c=0.985),
#     )

#     print("Cantones:")
#     for canton in apoyos.cantones:
#         print(f"  {canton.tramos}: vano de regulación {canton.vano_regulacion:.1f} m, "
#               f"desnivel {canton.desnivel:g} m")
#     print(f"\nTensiones de cada vano (calculadas):\n"
#           f"{apoyos.tensiones[['viento', 'hielo', 'desviación cadena']].round(1)}")

#     for numero in range(1, apoyos.n + 1):
#         print(f"\nApoyo {numero}: {apoyos.etiqueta(numero).replace(chr(10), ' ')} "
#               f"({apoyos.formas[numero - 1]})")
#         print(apoyos.esfuerzos(numero).round(1).fillna("-"))


# def main():
#     ejemplo_modelos_electricos()
#     ejemplo_vano_a_nivel()
#     ejemplo_vano_a_desnivel()
#     ejemplo_apoyos_tensiones_del_enunciado()
#     ejemplo_apoyos_tensiones_calculadas()


# if __name__ == "__main__":
#     main()
