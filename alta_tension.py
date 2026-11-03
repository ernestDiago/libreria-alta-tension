"""
Librería de Alta Tensión - Generación, distribución y utilización de la energía eléctrica

Contenido:
    1. MODELOS ELÉCTRICOS DE LÍNEAS
        Modelo           -> modelos inductivo, en T, en π y de parámetros distribuidos

    2. CÁLCULO MECÁNICO DEL CONDUCTOR (Tema 9)
        Conductor        -> datos de un conductor leídos de caracteristicas_conductores/
        calculoMecanico  -> hipótesis del RLAT, flechas, tabla de tendido y exportación a Excel

Uso:
    import alta_tension as at

    linea = at.Modelo(Pf=600, fp=0.8, Uf=400, L=80, r=0.012, x=0.15, g=0, b=0, caracter="inductivo")
    linea.pi()

    cable = at.Conductor("LA 56")
    calc = at.calculoMecanico(cable, Un=20, alt=600, vano=170)
    calc.resolver()
"""

import cmath
import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

# Carpeta con los CSV de conductores (junto a este archivo)
CARPETA_CONDUCTORES = Path(__file__).parent / "caracteristicas_conductores"


# ======================================================================
#  1. MODELOS ELÉCTRICOS DE LÍNEAS
# ======================================================================


class Modelo:
    """Modelos eléctricos de una línea a partir de las condiciones en la carga.

    Unidades de entrada: Pf [MW], Uf [kV], L [km], r y x [Ω/km], g y b [S/km].
    caracter: "inductivo" o "capacitivo".
    """

    def __init__(self, Pf, fp, Uf, L, r, x, g, b, caracter: str):
        self.Pf = Pf * 10**6
        self.fp = fp
        self.Uf = Uf * 10**3
        self.L = L
        self.r = r
        self.x = x
        self.g = g
        self.b = b
        self.caracter = caracter

        # Calculos comunes a todos los modelos
        self._magnitudes_comunes()

    def _magnitudes_comunes(self):

        # Impedancia y admitancia
        self.Z = self.L * (self.r + 1j * self.x)
        self.Y = self.L * (self.g + 1j * self.b)

        # Intensidad en la carga

        # Modulo de la intensidad de la carga
        Ic_modulo = (self.Pf) / (math.sqrt(3) * self.Uf * self.fp)

        # Argumento de la corriente en la carga
        caracter = self.caracter.lower()
        if caracter.startswith("induct"):
            arg = -math.acos(self.fp)
        elif caracter.startswith("capacit"):
            arg = math.acos(self.fp)
        else:
            raise ValueError(
                f"Carácter de carga no válido: {self.caracter!r}. Usa 'inductivo' o 'capacitivo'."
            )

        self.Ic = cmath.rect(Ic_modulo, arg)

        # Tensión final simple
        self.Vf = self.Uf / math.sqrt(3)

    def _resolver(self, A, B, C, D):
        V0 = A * self.Vf + B * self.Ic
        I0 = C * self.Vf + D * self.Ic
        S0 = 3 * V0 * I0.conjugate()
        U0 = math.sqrt(3) * abs(V0)

        return {
            "Tensión de línea en el origen [kV]": U0 * 10**-3,
            "Intensidad en el origen [A]": abs(I0),
            "Potencia activa en el origen [MW]": S0.real * 10**-6,
            "Pérdidas de potencia [MW]": (S0.real - self.Pf) * 10**-6,
            "Caída de tensión aritmética [kV]": (U0 - self.Uf) * 10**-3,
        }

    def inductivo(self):
        A = 1
        B = self.Z
        C = 0
        D = 1
        return self._resolver(A=A, B=B, C=C, D=D)

    def T(self):
        A = (self.Z * self.Y) / 2 + 1
        B = self.Z * (1 + (self.Z * self.Y) / 4)
        C = self.Y
        D = A
        return self._resolver(A=A, B=B, C=C, D=D)

    def pi(self):
        A = 1 + self.Z * self.Y / 2
        B = self.Z
        C = self.Y * (1 + self.Z * self.Y / 4)
        D = A
        return self._resolver(A=A, B=B, C=C, D=D)

    def distribuidos(self):
        gL = cmath.sqrt(self.Z * self.Y)

        # sinh(γL)/γL: si γL = 0 es 0/0, y su límite vale 1
        if gL == 0:
            factor = 1
        else:
            factor = cmath.sinh(gL) / gL

        A = cmath.cosh(gL)
        B = self.Z * factor
        C = self.Y * factor
        D = A
        return self._resolver(A=A, B=B, C=C, D=D)

    def comparar(self):
        "Tabla con los cuatro modelos en columnas"
        return pd.DataFrame(
            {
                "Modelo Inductivo": self.inductivo(),
                "Modelo en T": self.T(),
                "Modelo en Pi": self.pi(),
                "Modelo parametros distribuidos": self.distribuidos(),
            }
        )


# ======================================================================
#  2. CÁLCULO MECÁNICO DEL CONDUCTOR (Tema 9)
# ======================================================================

PROPIEDADES = {          # (n_al, n_acero): (E [daN/mm²], α [1/°C])
        (6, 1):   (8100, 19.1e-6),
        (26, 7):  (7700, 18.9e-6),
        (30, 7):  (8000, 17.8e-6),
        (54, 7):  (7000, 19.3e-6),
        (54, 19): (6800, 19.4e-6),
    }

T_VIENTO = {"A": -5,  "B": -10, "C": -15}       # tracción máxima viento (y viento excepcional / desviación cadena)
T_HIELO  = {"B": -15, "C": -20}                 # tracción máxima hielo (en zona A no hay hielo)
T_FLECHA_MIN = {"A": -5, "B": -15, "C": -20}    # flecha mínima


@dataclass
class Conductor:
    conductor: str                 # nombre antiguo, ej: "LA 56"
    archivo:   str = str(CARPETA_CONDUCTORES / "conductores_AL1_ST1A.csv")
    E_dato:    float | None = None   # módulo de elasticidad [daN/mm²] (si el enunciado lo da)
    alfa_dato: float | None = None   # coef. de dilatación lineal [1/ºC] (si el enunciado lo da)

    def __post_init__(self):
        tabla = pd.read_csv(self.archivo, index_col="codigo_antiguo")
        self.datos: dict = tabla.loc[self.conductor].to_dict()

        self.p      = self.datos["masa_kg_km"] * 9.81 / 10_000   # daN/m
        self.d      = self.datos["d_conductor_mm"]               # mm
        self.S      = self.datos["seccion_total_mm2"]            # mm²
        self.rotura = self.datos["carga_rotura_kN"] * 100        # daN

        # E y α: los del enunciado si se dan, si no los típicos según composición
        composicion = (int(self.datos["n_alambres_al"]), int(self.datos["n_alambres_acero"]))
        E_tabla, alfa_tabla = PROPIEDADES[composicion]
        self.E:    float = self.E_dato    if self.E_dato    is not None else E_tabla
        self.alfa: float = self.alfa_dato if self.alfa_dato is not None else alfa_tabla


@dataclass
class calculoMecanico:

    conductor : Conductor
    Un        : float   #Tensión compuesta de la linea [kV]
    alt       : float   #Altitid de la linea [m]
    vano      : float   #Longitud del vano [m]
    Vv        : float | None = None   #Velocidad máxima del viento en la zona [km/h] (si > 120/140 -> viento excepcional)
    antivibradores : bool = False     #Si hay antivibradores el EDS sube del 15 % al 22 %
    coef_seguridad : float | None = None  #None -> 3 en media tensión (15-20 kV), 2,5 en el resto
    chs       : float | None = 0.20   #Límite CHS a -5 ºC (fracción de la rotura). None -> no se comprueba


    def __post_init__(self):

        self.Zona = "A" if self.alt < 500 else ("B" if self.alt <= 1000 else "C")
        self.categoria = "especial" if self.Un >= 220 else "normal"

        # Viento de referencia del RLAT (siempre) y viento excepcional (solo si el dato de entrada lo supera)
        self.v_ref = 140 if self.categoria == "especial" else 120
        if self.Vv is not None and self.Vv > self.v_ref: self.v_excepcional = self.Vv
        else:                                            self.v_excepcional = None

        # Coeficiente de seguridad: 3 en media tensión (evita la hipótesis de rotura en apoyos)
        if self.coef_seguridad is None:
            self.coef = 3 if 15 <= self.Un <= 20 else 2.5
        else:
            self.coef = self.coef_seguridad

    #  SOBRECARGAS

    def _q(self, v, dmm):
        "Presión del viento sobre el cable [daN/m²]"

        if dmm <= 16:
            return 60 * (v / 120) ** 2
        return 50 * (v / 120) ** 2

    def _pv(self, v=None):
        "Sobrecarga de viento p_v [daN/m] (por defecto con el viento de referencia)"
        v = self.v_ref if v is None else v
        return self.conductor.d / 1000 * self._q(v, self.conductor.d)

    def _p_viento (self, v=None):
        "Peso total con viento p_t [daN/m] (por defecto con el viento de referencia)"

        pv = self._pv(v)
        return (self.conductor.p**2 + pv**2) ** 0.5

    def _p_viento_mitad(self):
        "Peso total con la mitad de la presión de viento de 120 km/h (desviación de cadenas)"
        pv = self._pv(120) / 2
        return (self.conductor.p**2 + pv**2) ** 0.5

    def _p_hielo (self):
        "Peso total con hielo [daN/m]; en zona A no hay hielo"
        if self.Zona == "A": return self.conductor.p

        k = 0.18 if self.Zona == "B" else 0.36
        return self.conductor.p + k * self.conductor.d ** 0.5

    def _sobrecarga_conjunta(self):
        "Peso total con hielo + viento a 60 km/h [daN/m]. Solo zonas B y C."
        if self.Zona == "A":
            raise ValueError("En zona A no se aplica la sobrecarga conjunta de hielo y viento")

        D = self.conductor.datos[f"d_manguito_hielo_{self.Zona}_mm"]
        pv_prima = self._q(60, D) * D / 1000
        return (self._p_hielo()**2 + pv_prima**2) ** 0.5


    #  ECUACIONES

    def _cambio_condiciones(self, T1, theta1, p1, theta2, p2):
        "Tensión T2 [daN] en el estado 2 partiendo del estado 1 conocido"

        S, E, alfa, p = self.conductor.S, self.conductor.E, self.conductor.alfa, self.conductor.p
        a = self.vano
        w  = p / S
        m1, m2 = p1 / p, p2 / p
        t1 = T1 / S

        K = a**2 * E * w**2 * m1**2 / (24 * t1**2) - t1
        A = alfa * E * (theta2 - theta1) + K
        B = a**2 * E * w**2 * m2**2 / 24

        # t2³ + A·t2² + 0·t2 − B = 0
        raices = np.roots([1, A, 0, -B])
        t2 = max(r.real for r in raices if abs(r.imag) < 1e-9 and r.real > 0)
        return t2 * S

    def _T0_desde_Tmax(self, Tmax, p_t):
        "T0 [daN] tal que T0 + a²p²/(8·T0) = Tmax (despejado de Tmax = T0 + p·f)"
        a = self.vano
        return (2 * Tmax + (4 * Tmax**2 - 2 * a**2 * p_t**2) ** 0.5) / 4

    def _Tmax(self, T0, p_t):
        "Tensión máxima en los apoyos [daN]: Tmax = T0 + p·f"
        return T0 + p_t * self._flecha(T0, p_t)

    def _flecha_exacta(self, T, p_t):
        "Flecha [m] con la catenaria exacta. T [daN], p_t [daN/m]"
        h = T / p_t                                  # parámetro de la catenaria [m]
        return h * (math.cosh(self.vano / (2 * h)) - 1)

    def _flecha_aprox(self, T, p_t):
        "Flecha aproximada si a<500m e inclinacion menor del 10%"
        return self.vano**2 * p_t / (8 * T)

    def _flecha(self, T, p_t):
        if self.vano > 500: return self._flecha_exacta(T, p_t)
        return self._flecha_aprox(T, p_t)


    #  HIPÓTESIS

    def _hipotesis_limitantes(self):
        """Hipótesis que limitan la tensión.
        Cada una: (nombre, θ [ºC], p_t [daN/m], T_límite [daN], el límite se aplica a Tmax?)"""
        R = self.conductor.rotura
        eds = 0.22 if self.antivibradores else 0.15
        t_v = T_VIENTO[self.Zona]

        lista = [
            ("EDS",    15,  self.conductor.p,             eds * R,        False),
            ("viento", t_v, self._p_viento(self.v_ref),   R / self.coef,  True),
        ]
        if self.chs is not None:
            lista.append(("CHS", -5, self.conductor.p, self.chs * R, False))
        if self.v_excepcional is not None:
            lista.append(("viento excepcional", t_v, self._p_viento(self.v_excepcional), R / self.coef, True))
        if self.Zona in T_HIELO:
            p_h = self._sobrecarga_conjunta() if self.categoria == "especial" else self._p_hielo()
            lista.append(("hielo", T_HIELO[self.Zona], p_h, R / self.coef, True))
        return lista

    def _hipotesis_resultado(self):
        "Hipótesis de flechas: (nombre, θ [ºC], p_t [daN/m])"
        t_max = 85 if self.categoria == "especial" else 50
        lista = [
            ("flecha viento 15ºC",            15,     self._p_viento(120)),   # siempre 120 km/h (aptdo. 3.2.3)
            (f"flecha temperatura {t_max}ºC", t_max,  self.conductor.p),
        ]
        if self.Zona in T_HIELO:
            lista.append(("flecha hielo 0ºC", 0, self._p_hielo()))
        lista += [
            ("flecha mínima",       T_FLECHA_MIN[self.Zona], self.conductor.p),
            ("desviación cadena",   T_VIENTO[self.Zona],     self._p_viento_mitad()),
        ]
        return lista

    def _estado_inicial(self, hipotesis):
        "Convierte una hipótesis limitante en estado conocido (nombre, θ, p_t, T0) poniéndola en su límite"
        nombre, theta, p_t, T_lim, sobre_Tmax = hipotesis
        T0 = self._T0_desde_Tmax(T_lim, p_t) if sobre_Tmax else T_lim
        return nombre, theta, p_t, T0

    def _ratio(self, T0, p_t, T_lim, sobre_Tmax):
        "Cuánto se usa del límite (>1 = se pasa)"
        T = self._Tmax(T0, p_t) if sobre_Tmax else T0
        return T / T_lim

    def _hipotesis_dominante(self):
        "Busca la hipótesis que manda. Devuelve el estado inicial (nombre, θ, p_t, T0)"
        limitantes = self._hipotesis_limitantes()
        partida = self._estado_inicial(limitantes[0])        # se empieza suponiendo el EDS

        for _ in range(len(limitantes)):                     # como mucho una vuelta por hipótesis
            nombre1, theta1, p1, T1 = partida

            # T0 en cada limitante partiendo de la supuesta, y cuánto se pasa de su límite
            ratios = []
            for hip in limitantes:
                nombre2, theta2, p2, T_lim, sobre_Tmax = hip
                T2 = self._cambio_condiciones(T1, theta1, p1, theta2, p2)
                ratios.append((self._ratio(T2, p2, T_lim, sobre_Tmax), hip))

            peor_ratio, peor = max(ratios, key=lambda r: r[0])
            if peor_ratio <= 1 + 1e-6:                       # ninguna se pasa -> la supuesta manda
                return partida
            partida = self._estado_inicial(peor)             # reiniciar desde la que más se pasa

        return partida

    def resolver(self):
        "Calcula todas las hipótesis. Devuelve un DataFrame con T0, Tmax, % rotura y flecha"
        nombre1, theta1, p1, T1 = self._hipotesis_dominante()
        self.dominante = nombre1
        R = self.conductor.rotura

        filas = []
        for nombre, theta, p_t, T_lim, sobre_Tmax in self._hipotesis_limitantes():
            T0 = self._cambio_condiciones(T1, theta1, p1, theta, p_t)
            filas.append([nombre, theta, p_t, T0, self._Tmax(T0, p_t), 100 * T0 / R,
                          self._flecha(T0, p_t), 100 * T_lim / R])
        for nombre, theta, p_t in self._hipotesis_resultado():
            T0 = self._cambio_condiciones(T1, theta1, p1, theta, p_t)
            filas.append([nombre, theta, p_t, T0, self._Tmax(T0, p_t), 100 * T0 / R,
                          self._flecha(T0, p_t), None])

        self.resultados = pd.DataFrame(
            filas,
            columns=["hipotesis", "temp_C", "p_t_daN_m", "T0_daN", "Tmax_daN", "%_rotura", "flecha_m", "limite_%"],
        ).set_index("hipotesis")
        return self.resultados

    def tabla_tendido(self, temperaturas=range(0, 50, 5)):
        "Tensión y flecha de tendido (sin sobrecarga) para cada temperatura"
        nombre1, theta1, p1, T1 = self._hipotesis_dominante()
        p = self.conductor.p

        filas = []
        for theta in temperaturas:
            T = self._cambio_condiciones(T1, theta1, p1, theta, p)
            filas.append([theta, T, self._flecha(T, p)])
        return pd.DataFrame(filas, columns=["temp_C", "T_daN", "flecha_m"]).set_index("temp_C")

    @property
    def flecha_maxima(self):
        "Mayor flecha de las hipótesis de flecha máxima [m]"
        if not hasattr(self, "resultados"):
            self.resolver()
        nombres = [n for n in self.resultados.index if n.startswith("flecha") and n != "flecha mínima"]
        return self.resultados.loc[nombres, "flecha_m"].max()

    # ------------------------------------------------------------------
    #  EXPORTAR
    # ------------------------------------------------------------------

    def exportar_excel(self, ruta="calculo_mecanico.xlsx", temperaturas=range(0, 50, 5)):
        "Guarda en un Excel los datos de entrada, la tabla de hipótesis y la tabla de tendido"
        from openpyxl.styles import Font, PatternFill, Alignment
        from openpyxl.utils import get_column_letter

        resultados = self.resolver().reset_index()
        tendido = self.tabla_tendido(temperaturas).reset_index()
        c = self.conductor

        datos = pd.DataFrame([
            ["Conductor", c.conductor, ""],
            ["Sección S", c.S, "mm²"],
            ["Diámetro d", c.d, "mm"],
            ["Peso propio p", round(c.p, 4), "daN/m"],
            ["Carga de rotura", c.rotura, "daN"],
            ["Módulo de elasticidad E", c.E, "daN/mm²"],
            ["Coef. dilatación α", c.alfa, "1/ºC"],
            ["Tensión nominal Un", self.Un, "kV"],
            ["Altitud", self.alt, "m"],
            ["Zona", self.Zona, ""],
            ["Categoría", self.categoria, ""],
            ["Vano", self.vano, "m"],
            ["Viento de referencia", self.v_ref, "km/h"],
            ["Viento excepcional", self.v_excepcional if self.v_excepcional else "—", "km/h"],
            ["Coeficiente de seguridad", self.coef, ""],
            ["Hipótesis que manda", self.dominante, ""],
            ["Flecha máxima", round(self.flecha_maxima, 2), "m"],
        ], columns=["Dato", "Valor", "Unidad"])

        resultados.columns = ["Hipótesis", "Temperatura (ºC)", "p_t (daN/m)", "T0 (daN)",
                              "Tmax (daN)", "% rotura", "Flecha (m)", "Límite (% rotura)"]
        tendido.columns = ["Temperatura (ºC)", "T (daN)", "Flecha (m)"]

        cabecera = PatternFill("solid", fgColor="1F4E79")
        with pd.ExcelWriter(ruta, engine="openpyxl") as xl:
            for nombre, df, decimales in [("Datos", datos, None),
                                          ("Hipótesis", resultados, "0.00"),
                                          ("Tabla de tendido", tendido, "0.00")]:
                df.to_excel(xl, sheet_name=nombre, index=False)
                hoja = xl.sheets[nombre]
                for celda in hoja[1]:
                    celda.font = Font(bold=True, color="FFFFFF")
                    celda.fill = cabecera
                    celda.alignment = Alignment(horizontal="center", wrap_text=True)
                for i, col in enumerate(df.columns, start=1):
                    ancho = max(len(str(col)), *(len(str(v)) for v in df.iloc[:, i - 1])) + 2
                    hoja.column_dimensions[get_column_letter(i)].width = min(ancho, 28)
                    if decimales:
                        for celda in hoja[get_column_letter(i)][1:]:
                            if isinstance(celda.value, float):
                                celda.number_format = decimales
                hoja.freeze_panes = "A2"
        return ruta
