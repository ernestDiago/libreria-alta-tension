"""
Ejemplos de uso de la librería alta_tension.

    python ejemplos.py
"""

import pandas as pd

import alta_tension as at

pd.set_option("display.width", 200)
pd.set_option("display.max_columns", 20)


def titulo(texto):
    "Devuelve el texto como título, para hacer print(titulo(...))"
    return f"\n{'=' * 70}\n{texto}\n{'=' * 70}"


# ============================================
#        Modelos eléctricos
# ============================================
"""
De esta clase podemos sacar todos los parámetros que se utilizan para el cálculo de
los modelos. El método principal es .comparar(), que crea una tabla con todos los
modelos resueltos, pero también se puede sacar cada uno por separado con .inductivo(),
.T(), .pi() y .distribuidos()
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
    caracter="inductivo",  # Carácter de la carga: "inductivo" o "capacitivo"
)
tabla_comparativa = modelo_electrico.comparar()
print(titulo("Modelos eléctricos"))
print(tabla_comparativa)

# Si quieres un modelo en concreto puedes usar .inductivo(), pero sale feo,
# así que prefiero usar .comparar()["Nombre del modelo"]

# Solo parámetros distribuidos
distribuidos = tabla_comparativa["Modelo parametros distribuidos"]
print("\nSolo modelo parámetros distribuidos")
print(distribuidos)


# ==================================================
#        Características de la línea
# ==================================================
"""
La clase Linea guarda los datos comunes a todos los cálculos mecánicos de la línea y
deduce de ellos la zona, la categoría, el viento de referencia, el coeficiente de
seguridad y los límites EDS y CHS. Se crea una vez y se pasa a calculoMecanico y a
CalculoApoyos.
"""

linea = at.Linea(
    Un=400,  # Tensión de la línea [kV]
    alt=0,  # Altitud de la línea [m]
    Vv=130,  # Viento máximo [km/h]; si pasa de 120 (140) hay viento excepcional
    coef_seguridad=3,  # Coeficiente de seguridad con el que se calcula todo
    antivibradores=True,  # Con antivibradores el EDS sube del 15 % al 22 %
    # chs=0.20, # Puedes poner el CHS a mano; si no, 0.2 por defecto
    # eds=0.22, # Puedes poner el EDS a mano; si no, se pone según la norma
    # temperatura_maxima=85, # Temperatura de la flecha máxima, si el enunciado da otra
)
print(titulo("Características de la línea"))
print(linea.resumen())  # Este método crea una tabla resumen de la línea

# Los datos que deduce también se pueden consultar uno a uno
print(f"\nZona {linea.Zona}, categoría {linea.categoria}, coef. {linea.coef}")


# ======================================================
#        Características de los conductores
# ======================================================
"""
La clase Conductor lee los datos del cable de los CSV de caracteristicas_conductores/.
Con .disponibles() se ven todos los que hay, sin crear ninguno, y con .resumen() los
datos de uno ordenados por grupos.
"""

print(titulo("Conductores"))

# Para ver qué conductores hay en el CSV
print(at.Conductor.disponibles())

cable_LA56 = at.Conductor("LA 56")
cable_LA110 = at.Conductor("LA 110")

print()
print(cable_LA110.resumen())  # Devuelve una tabla con todos los datos del cable
print(cable_LA56.resumen())

# También puedes poner el módulo de elasticidad y el coef. de dilatación, porque
# en las tablas no aparecen: si son distintos a los de por defecto, los pones tú
cable_LA110 = at.Conductor("LA 110", E_dato=8175, alfa_dato=17.9e-6)
print(f"\nE del LA 110 del enunciado: {cable_LA110.E} daN/mm²")

# Con un cable ya creado basta con cambiar el dato: E pasa de 8100 (típico) a 7949
cable_LA56.E_dato = 7949  # E del ejemplo de clase, que se usa más abajo

# La clase también devuelve las sobrecargas de cada hipótesis: viento, y hielo en
# las zonas B y C. "sobrecarga_..." es solo lo que se añade y "p_total_..." el peso
# total (cable + sobrecarga), que es el que se usa en el cálculo mecánico
print(f"\nPresión del viento a 120 km/h: {cable_LA110.presion_viento(120)} daN/m²")
print(f"Sobrecarga de viento 120 km/h: {cable_LA110.sobrecarga_viento(120):.3f} daN/m")
print(f"Peso total con viento a 120 km/h: {cable_LA110.p_total_viento(120):.3f} daN/m")
print(f"Sobrecarga de hielo en zona B: {cable_LA110.sobrecarga_hielo('B'):.3f} daN/m")
print(f"Peso total con hielo en zona B: {cable_LA110.p_total_hielo('B'):.3f} daN/m")
print(f"Peso total con hielo en zona C: {cable_LA110.p_total_hielo('C'):.3f} daN/m")


# ======================================================
#        Cálculo mecánico del conductor
# ======================================================
"""
La clase calculoMecanico junta un conductor, una línea y un vano. Con .resolver()
calcula todas las hipótesis del reglamento y con .tabla_tendido() la tabla de tendido.
"""

calculo_mecanico = at.calculoMecanico(
    conductor=cable_LA110,
    linea=linea,
    vano=200,  # Vano [m] (o vano de regulación de un cantón)
    # desnivel=30, # Desnivel entre los apoyos [m]; si no se pone, vano a nivel
)
print(titulo("Cálculo mecánico"))
print(calculo_mecanico.resolver().round(2))
print("\nTABLA DE TENDIDO")
print(calculo_mecanico.tabla_tendido().round(2))


# ======================================================
#        Cálculo mecánico: vano a nivel (ejemplo de clase)
# ======================================================
"""
Ejemplo de clase "Cálculo mecánico de un vano a nivel": línea de 20 kV con LA-56,
a 600 m de altitud (zona B), vano de 170 m y viento máximo de 130 km/h.
El enunciado da E = 7949 daN/mm², que ya le hemos puesto a cable_LA56 en la sección
de conductores, así que se usa ese mismo cable.
"""

linea_clase = at.Linea(
    Un=20,  # Media tensión -> coef. de seguridad 3 por defecto
    alt=600,  # Zona B -> hay hipótesis de hielo
    Vv=130,  # Supera los 120 km/h -> se añade la hipótesis de viento excepcional
)
vano_a_nivel = at.calculoMecanico(conductor=cable_LA56, linea=linea_clase, vano=170)

print(titulo("Cálculo mecánico: vano a nivel"))
print(vano_a_nivel.resolver().round(2))
print(f"\nHipótesis que manda: {vano_a_nivel.dominante}")
print(f"Flecha máxima: {vano_a_nivel.flecha_maxima:.2f} m")

# La tabla de tendido se puede pedir con las temperaturas que quieras
print("\nTABLA DE TENDIDO")
print(vano_a_nivel.tabla_tendido(range(0, 45, 5)).round(2))
print(vano_a_nivel.tabla_tendido(15).round(2))  # O con una sola temperatura

# Para guardar los datos, las hipótesis y la tabla de tendido en un Excel se usa
# vano_a_nivel.exportar_excel("calculo_mecanico_LA56.xlsx")


# ======================================================
#        Cálculo mecánico: vano a desnivel (ejemplo de clase)
# ======================================================
"""
Ejercicio de clase "Cálculo mecánico de vano desnivelado": línea de 20 kV con LA-78,
a 400 m de altitud, vano proyectado de 220 m y 70 m de desnivel entre apoyos.
Con desnivel, T0_daN es la tensión Tm en el punto medio del vano y Tmax_daN la
tensión TB en el apoyo más alto.
"""

cable_LA78 = at.Conductor("LA 78", E_dato=7949, alfa_dato=19.1e-6)
vano_a_desnivel = at.calculoMecanico(
    conductor=cable_LA78,
    linea=at.Linea(Un=20, alt=400),
    vano=220,  # Vano proyectado a (distancia horizontal) [m]
    desnivel=70,  # Diferencia de altura entre los apoyos [m]
)

print(titulo("Cálculo mecánico: vano a desnivel"))
print(f"Vano real b = {vano_a_desnivel.vano_real:.2f} m")
print(vano_a_desnivel.resolver().round(2))
print(f"\nHipótesis que manda: {vano_a_desnivel.dominante}")
print(f"Flecha máxima: {vano_a_desnivel.flecha_maxima:.2f} m")


# ======================================================
#        Armados de los apoyos
# ======================================================
"""
La clase Armado es lo que lleva montado un tipo de apoyo: la cruceta y las cadenas
de aisladores, y la forma del apoyo (celosía o chapa). Se crea uno por cada tipo de
apoyo que lleve cosas distintas y se pasan a CalculoApoyos.
Los datos se pasan siempre con su nombre (peso_cruceta=70, no 70 a secas).
"""

armado_amarre = at.Armado(
    peso_cruceta=70,  # Cruceta recta [daN]
    peso_cadena=12,  # Una cadena de aisladores con sus herrajes [daN]
    brazo=1.75,  # Distancia del conductor exterior al eje del apoyo [m]
    # forma="celosía", # Forma del apoyo; si no se pone, celosía
)
armado_suspension = at.Armado(
    peso_cruceta=56,  # Cruceta de bóveda [daN]
    peso_cadena=9,
    brazo=1.75,
    forma="chapa",
    b=1.365,  # Cotas de la bóveda [m]: con ellas calcula solo el factor de chapa
    c=0.985,
)
print(titulo("Armados"))
print(armado_amarre)
print(f"Factor de chapa de la bóveda: {armado_suspension.factor_chapa:.3f}")


# ======================================================
#        Cálculo de apoyos con las tensiones del enunciado
# ======================================================
"""
Ejercicio de evaluación continua: cruce de un valle con LA-180 a 600 m de altitud.
El enunciado da las tensiones de cada vano y pide los esfuerzos de los apoyos 3 y 4.
Las tensiones se pasan en un DataFrame con una fila por tramo y una columna por
hipótesis. Todos los apoyos llevan el mismo armado, así que se pasa uno solo.
"""

tensiones_enunciado = pd.DataFrame(
    {"hielo": [2107, 2107, 2116], "viento": [1747, 1747, 1758]},
    index=["2-3", "3-4", "4-5"],  # Los tramos que no se den quedan vacíos
)

apoyos_enunciado = at.CalculoApoyos(
    conductor=at.Conductor("LA 180", E_dato=8000, alfa_dato=17.8e-6),
    linea=at.Linea(Un=20, alt=600),
    vanos=[210, 270, 270, 240],  # Un vano entre cada par de apoyos [m]
    desniveles=[0, 5, -20, 20, 20],  # Respecto al apoyo anterior [m] (el 1º, 0)
    tipos=["fin de línea", "amarre", "anclaje", "amarre", "fin de línea"],
    angulos={4: 45},  # El apoyo 4 es de ángulo, de 45º
    tensiones=tensiones_enunciado,
    armados=armado_amarre,  # El mismo para todos los apoyos
)

print(titulo("Apoyos con las tensiones del enunciado"))
print(apoyos_enunciado.tensiones)

# El esquema de la línea se guarda en la carpeta esquemas/ y sale en pantalla
apoyos_enunciado.esquema(
    nombre="valle_LA180",  # Nombre de la imagen; si no se pone, esquema_apoyos
    # carpeta="esquemas", # Carpeta donde se guarda; si no existe, la crea
    # guardar=False, # Para no guardarlo
    # mostrar=False, # Para no mostrarlo
)

# Gravivano y eolovano del apoyo 3 [m]
print(f"\nGravivano con viento: {apoyos_enunciado.gravivano(3, 'viento'):.1f} m")
print(f"Gravivano con hielo: {apoyos_enunciado.gravivano(3, 'hielo'):.1f} m")
print(f"Eolovano: {apoyos_enunciado.eolovano(3):.0f} m")

# Cada hipótesis por separado devuelve los esfuerzos V, T, L y Mt
print(f"\n1ª hipótesis del apoyo 4: {apoyos_enunciado.hipotesis_viento(4)}")

# Tabla de esfuerzos para elegir el apoyo en las tablas del fabricante
print("\nApoyo 3")
print(apoyos_enunciado.esfuerzos(3).round(1).fillna("-"))
print("\nApoyo 4")
print(apoyos_enunciado.esfuerzos(4).round(1).fillna("-"))


# ======================================================
#        Cálculo de apoyos con las tensiones calculadas
# ======================================================
"""
Ejemplo SJR005 "Cálculo mecánico de apoyos de una línea aérea de 3ª categoría":
LA-110 a 1200 m (zona C), con EDS del 8,7 % y CHS del 15,9 % del enunciado.
Si no se le pasan las tensiones, la clase divide la línea en cantones (cortando en
los apoyos que no son de suspensión) y hace el cálculo mecánico de cada uno con su
vano de regulación.
Los apoyos de suspensión son de chapa con cruceta de bóveda y el resto de celosía
con cruceta recta: se usan los dos armados de arriba.
"""

tipos = ["fin de línea", "suspensión", "anclaje", "suspensión", "amarre"]
tipos += ["suspensión", "fin de línea"]  # Apoyos 6 y 7, en otra línea para que quepa

apoyos_calculados = at.CalculoApoyos(
    conductor=at.Conductor("LA 110", E_dato=8047, alfa_dato=17.8e-6),
    linea=at.Linea(Un=20, alt=1200, eds=0.087, chs=0.159),
    vanos=[160, 150, 145, 140, 150, 160],
    desniveles=[0, 0, 0, 5, 10, -10, 15],
    tipos=tipos,
    angulos={5: 30},
    armados={"suspensión": armado_suspension, "resto": armado_amarre},
)

print(titulo("Apoyos con las tensiones calculadas por cantones"))
# Cada cantón va de un apoyo que no es de suspensión al siguiente
for canton in apoyos_calculados.cantones:
    print(f"Cantón {canton.tramos}: vano de regulación {canton.vano_regulacion:.1f}m")

print("\nTensiones de cada vano (calculadas)")
with pd.option_context("display.precision", 1):  # Mostrarla con 1 decimal
    print(apoyos_calculados.tensiones)

# Tabla de esfuerzos de cada apoyo
for numero in range(1, apoyos_calculados.n + 1):
    print(f"\nApoyo {numero}: {apoyos_calculados.tipos[numero - 1]}")
    print(apoyos_calculados.esfuerzos(numero).round(1).fillna("-"))
