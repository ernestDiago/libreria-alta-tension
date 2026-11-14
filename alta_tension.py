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
import itertools
import math
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

# Carpeta con los CSV de conductores (junto a este archivo)
CARPETA_CONDUCTORES = Path(__file__).parent / "caracteristicas_conductores"


#  MODELOS ELÉCTRICOS DE LÍNEAS


@dataclass
class Modelo:
    """Modelos eléctricos de una línea a partir de las condiciones en la carga.

    Unidades de entrada: Pf [MW], Uf [kV], L [km], r y x [Ω/km], g y b [S/km].
    caracter: "inductivo" o "capacitivo".
    """

    Pf: float  # MW
    fp: float
    Uf: float  # kV
    L: float
    r: float
    x: float
    g: float
    b: float
    caracter: str

    def __post_init__(self):
        self.Pf = self.Pf * 1e6  # MW -> W
        self.Uf = self.Uf * 1e3  # kV -> V

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


#  CÁLCULO MECÁNICO DEL CONDUCTOR

PROPIEDADES = {  # (n_al, n_acero): (E [daN/mm²], α [1/°C])
    (6, 1): (8100, 19.1e-6),
    (26, 7): (7700, 18.9e-6),
    (30, 7): (8000, 17.8e-6),
    (54, 7): (7000, 19.3e-6),
    (54, 19): (6800, 19.4e-6),
}

T_VIENTO = {
    "A": -5,
    "B": -10,
    "C": -15,
}  # tracción máxima viento (y viento excepcional / desviación cadena)
T_HIELO = {"B": -15, "C": -20}  # tracción máxima hielo (en zona A no hay hielo)
T_FLECHA_MIN = {"A": -5, "B": -15, "C": -20}  # flecha mínima
DESNIVEL_MINIMO = 1  # Desnivel entre torres para considerar el calculo con desnivel


@dataclass
class Conductor:
    conductor: str  # nombre antiguo, ej: "LA 56"
    archivo: str = str(CARPETA_CONDUCTORES / "conductores_AL1_ST1A.csv")
    E_dato: float | None = (
        None  # módulo de elasticidad [daN/mm²] (si el enunciado lo da)
    )
    alfa_dato: float | None = (
        None  # coef. de dilatación lineal [1/ºC] (si el enunciado lo da)
    )

    def __post_init__(self):
        # α de un conductor es del orden de 10⁻⁵ 1/ºC: 17,8·10⁻⁶ -> 17.8e-6
        if self.alfa_dato is not None and not 0 < self.alfa_dato < 1e-3:
            raise ValueError(
                f"alfa_dato={self.alfa_dato}: fuera de rango. "
                "17,8·10⁻⁶ ºC⁻¹ se escribe 17.8e-6"
            )

        tabla = pd.read_csv(self.archivo, index_col="codigo_antiguo")
        self.datos: dict = tabla.loc[self.conductor].to_dict()

        self.p = self.datos["masa_kg_km"] * 9.81 / 10_000  # daN/m
        self.d = self.datos["d_conductor_mm"]  # mm
        self.S = self.datos["seccion_total_mm2"]  # mm²
        self.rotura = self.datos["carga_rotura_kN"] * 100  # daN

        # E y α: los del enunciado si se dan, si no los típicos según composición
        composicion = (
            int(self.datos["n_alambres_al"]),
            int(self.datos["n_alambres_acero"]),
        )
        E_tabla, alfa_tabla = PROPIEDADES[composicion]
        self.E: float = self.E_dato if self.E_dato is not None else E_tabla
        self.alfa: float = self.alfa_dato if self.alfa_dato is not None else alfa_tabla


@dataclass
class calculoMecanico:
    conductor: Conductor
    Un: float  # Tensión compuesta de la linea [kV]
    alt: float  # Altitid de la linea [m]
    vano: float  # Longitud del vano [m]
    Vv: float | None = (
        None  # Velocidad máxima del viento en la zona [km/h] (si > 120/140 -> viento excepcional)
    )
    desnivel: float = 0.0  # Desnivel entre vanos
    antivibradores: bool = False  # Si hay antivibradores el EDS sube del 15 % al 22 %
    coef_seguridad: float | None = (
        None  # None -> 3 en media tensión (15-20 kV), 2,5 en el resto
    )
    chs: float | None = (
        0.20  # Límite CHS a -5 ºC (fracción de la rotura). None -> no se comprueba
    )
    eds: float | None = (
        None  # Límite EDS a 15 ºC (fracción de la rotura). None -> 15 % (22 % con antivibradores)
    )

    def __post_init__(self):

        # Los límites van en tanto por uno: 15 % -> 0.15
        for nombre in ("eds", "chs"):
            valor = getattr(self, nombre)
            if valor is not None and not 0 < valor < 1:
                raise ValueError(
                    f"{nombre}={valor}: el límite va en tanto por uno (15 % -> 0.15)"
                )

        # Límite EDS: el del enunciado si se da, si no el del RLAT
        if self.eds is not None:
            self.limite_eds = self.eds
        else:
            self.limite_eds = 0.22 if self.antivibradores else 0.15

        self.Zona = "A" if self.alt < 500 else ("B" if self.alt <= 1000 else "C")
        self.categoria = "especial" if self.Un >= 220 else "normal"

        # Viento de referencia del RLAT (siempre) y viento excepcional (solo si el dato de entrada lo supera)
        self.v_ref = 140 if self.categoria == "especial" else 120
        if self.Vv is not None and self.Vv > self.v_ref:
            self.v_excepcional = self.Vv
        else:
            self.v_excepcional = None

        # Coeficiente de seguridad: 3 en media tensión (evita la hipótesis de rotura en apoyos)
        if self.coef_seguridad is None:
            self.coef = 3 if 15 <= self.Un <= 20 else 2.5
        else:
            self.coef = self.coef_seguridad

        # Desnivel
        self.vano_real = math.sqrt(self.vano**2 + self.desnivel**2)
        self.con_desnivel = abs(self.desnivel) >= DESNIVEL_MINIMO

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

    def _p_viento(self, v=None):
        "Peso total con viento p_t [daN/m] (por defecto con el viento de referencia)"

        pv = self._pv(v)
        return (self.conductor.p**2 + pv**2) ** 0.5

    def _p_viento_mitad(self):
        "Peso total con la mitad de la presión de viento de 120 km/h (desviación de cadenas)"
        pv = self._pv(120) / 2
        return (self.conductor.p**2 + pv**2) ** 0.5

    def _p_hielo(self):
        "Peso total con hielo [daN/m]; en zona A no hay hielo"
        if self.Zona == "A":
            return self.conductor.p

        k = 0.18 if self.Zona == "B" else 0.36
        return self.conductor.p + k * self.conductor.d**0.5

    def _sobrecarga_conjunta(self):
        "Peso total con hielo + viento a 60 km/h [daN/m]. Solo zonas B y C."
        if self.Zona == "A":
            raise ValueError(
                "En zona A no se aplica la sobrecarga conjunta de hielo y viento"
            )

        D = self.conductor.datos[f"d_manguito_hielo_{self.Zona}_mm"]
        pv_prima = self._q(60, D) * D / 1000
        return (self._p_hielo() ** 2 + pv_prima**2) ** 0.5

    #  ECUACIONES

    def _cambio_condiciones(self, T1, theta1, p1, theta2, p2):
        "Tensión T2 [daN] en el estado 2 partiendo del estado 1 conocido"

        S, E, alfa, p = (
            self.conductor.S,
            self.conductor.E,
            self.conductor.alfa,
            self.conductor.p,
        )
        a = self.vano
        w = p / S
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
        b = self.vano_real
        deslvl = abs(self.desnivel)
        return (
            1
            / 4
            * (
                (2 * Tmax - p_t * deslvl)
                + math.sqrt((p_t * deslvl - 2 * Tmax) ** 2 - 2 * (b * p_t) ** 2)
            )
        )

    def _Tmax(self, T0, p_t):
        "Tensión máxima en los apoyos [daN]: Tmax = T0 + p·f"
        return T0 + p_t * (self._flecha(T0, p_t) + abs(self.desnivel) / 2)

    def _flecha_exacta(self, T, p_t):
        "Flecha [m] con la catenaria exacta. T [daN], p_t [daN/m]"
        h = T / p_t  # parámetro de la catenaria [m]
        return h * (math.cosh(self.vano / (2 * h)) - 1)

    def _flecha_aprox(self, T, p_t):
        "Flecha aproximada si a<500m e inclinacion menor del 10%"
        return self.vano_real**2 * p_t / (8 * T)

    def _flecha(self, T, p_t):
        if self.vano > 500:
            return self._flecha_exacta(T, p_t)
        return self._flecha_aprox(T, p_t)

    #  HIPÓTESIS

    def _hipotesis_limitantes(self):
        """Hipótesis que limitan la tensión.
        Cada una: (nombre, θ [ºC], p_t [daN/m], T_límite [daN], el límite se aplica a Tmax?)"""
        R = self.conductor.rotura
        t_v = T_VIENTO[self.Zona]

        lista = [
            ("EDS", 15, self.conductor.p, self.limite_eds * R, self.con_desnivel),
            ("viento", t_v, self._p_viento(self.v_ref), R / self.coef, True),
        ]
        if self.chs is not None:
            lista.append(("CHS", -5, self.conductor.p, self.chs * R, self.con_desnivel))
        if self.v_excepcional is not None:
            lista.append(
                (
                    "viento excepcional",
                    t_v,
                    self._p_viento(self.v_excepcional),
                    R / self.coef,
                    True,
                )
            )
        if self.Zona in T_HIELO:
            p_h = (
                self._sobrecarga_conjunta()
                if self.categoria == "especial"
                else self._p_hielo()
            )
            lista.append(("hielo", T_HIELO[self.Zona], p_h, R / self.coef, True))
        return lista

    def _hipotesis_resultado(self):
        "Hipótesis de flechas: (nombre, θ [ºC], p_t [daN/m])"
        t_max = 85 if self.categoria == "especial" else 50
        lista = [
            (
                "flecha viento 15ºC",
                15,
                self._p_viento(120),
            ),  # siempre 120 km/h (aptdo. 3.2.3)
            (f"flecha temperatura {t_max}ºC", t_max, self.conductor.p),
        ]
        if self.Zona in T_HIELO:
            lista.append(("flecha hielo 0ºC", 0, self._p_hielo()))
        lista += [
            ("flecha mínima", T_FLECHA_MIN[self.Zona], self.conductor.p),
            ("desviación cadena", T_VIENTO[self.Zona], self._p_viento_mitad()),
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
        partida = self._estado_inicial(limitantes[0])  # se empieza suponiendo el EDS

        for _ in range(len(limitantes)):  # como mucho una vuelta por hipótesis
            _nombre1, theta1, p1, T1 = partida

            # T0 en cada limitante partiendo de la supuesta, y cuánto se pasa de su límite
            ratios = []
            for hip in limitantes:
                _nombre2, theta2, p2, T_lim, sobre_Tmax = hip
                T2 = self._cambio_condiciones(T1, theta1, p1, theta2, p2)
                ratios.append((self._ratio(T2, p2, T_lim, sobre_Tmax), hip))

            peor_ratio, peor = max(ratios, key=lambda r: r[0])
            if peor_ratio <= 1 + 1e-6:  # ninguna se pasa -> la supuesta manda
                return partida
            partida = self._estado_inicial(peor)  # reiniciar desde la que más se pasa

        return partida

    def resolver(self):
        "Calcula todas las hipótesis. Devuelve un DataFrame con T0, Tmax, % rotura (con T0 y con Tmax) y flecha"
        nombre1, theta1, p1, T1 = self._hipotesis_dominante()
        self.dominante = nombre1
        R = self.conductor.rotura

        filas = []
        for nombre, theta, p_t, T_lim, sobre_Tmax in self._hipotesis_limitantes():
            T0 = self._cambio_condiciones(T1, theta1, p1, theta, p_t)
            Tmax = self._Tmax(T0, p_t)
            filas.append(
                [
                    nombre,
                    theta,
                    p_t,
                    T0,
                    Tmax,
                    100 * T0 / R,
                    100 * Tmax / R,
                    self._flecha(T0, p_t),
                    100 * T_lim / R,
                ]
            )
        for nombre, theta, p_t in self._hipotesis_resultado():
            T0 = self._cambio_condiciones(T1, theta1, p1, theta, p_t)
            Tmax = self._Tmax(T0, p_t)
            filas.append(
                [
                    nombre,
                    theta,
                    p_t,
                    T0,
                    Tmax,
                    100 * T0 / R,
                    100 * Tmax / R,
                    self._flecha(T0, p_t),
                    None,
                ]
            )

        self.resultados = pd.DataFrame(
            filas,
            columns=[
                "hipotesis",
                "temp_C",
                "p_t_daN_m",
                "T0_daN",
                "Tmax_daN",
                "%_rotura",
                "%_rotura_TB",
                "flecha_m",
                "limite_%",
            ],
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
        return pd.DataFrame(filas, columns=["temp_C", "T_daN", "flecha_m"]).set_index(
            "temp_C"
        )

    @property
    def flecha_maxima(self):
        "Mayor flecha de las hipótesis de flecha máxima [m]"
        if not hasattr(self, "resultados"):
            self.resolver()
        nombres = [
            n
            for n in self.resultados.index
            if n.startswith("flecha") and n != "flecha mínima"
        ]
        return self.resultados.loc[nombres, "flecha_m"].max()

    #  EXPORTAR

    def exportar_excel(
        self, ruta="calculo_mecanico.xlsx", temperaturas=range(0, 50, 5)
    ):
        "Guarda en un Excel los datos de entrada, la tabla de hipótesis y la tabla de tendido"
        from openpyxl.styles import Alignment, Font, PatternFill
        from openpyxl.utils import get_column_letter

        resultados = self.resolver().reset_index()
        tendido = self.tabla_tendido(temperaturas).reset_index()
        c = self.conductor

        datos = pd.DataFrame(
            [
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
                [
                    "Viento excepcional",
                    self.v_excepcional if self.v_excepcional else "—",
                    "km/h",
                ],
                ["Coeficiente de seguridad", self.coef, ""],
                ["Límite EDS", round(100 * self.limite_eds, 2), "% rotura"],
                ["Límite CHS", round(100 * self.chs, 2) if self.chs is not None else "—", "% rotura"],
                ["Hipótesis que manda", self.dominante, ""],
                ["Flecha máxima", round(self.flecha_maxima, 2), "m"],
            ],
            columns=["Dato", "Valor", "Unidad"],
        )

        # Renombrar por nombre (no por posición) para que no se rompa al añadir columnas
        resultados = resultados.rename(
            columns={
                "hipotesis": "Hipótesis",
                "temp_C": "Temperatura (ºC)",
                "p_t_daN_m": "p_t (daN/m)",
                "T0_daN": "T0 (daN)",
                "Tmax_daN": "Tmax (daN)",
                "%_rotura": "% rotura (T0)",
                "%_rotura_TB": "% rotura (Tmax)",
                "flecha_m": "Flecha (m)",
                "limite_%": "Límite (% rotura)",
            }
        )
        tendido = tendido.rename(
            columns={
                "temp_C": "Temperatura (ºC)",
                "T_daN": "T (daN)",
                "flecha_m": "Flecha (m)",
            }
        )

        cabecera = PatternFill("solid", fgColor="1F4E79")
        with pd.ExcelWriter(ruta, engine="openpyxl") as xl:
            for nombre, df, decimales in [
                ("Datos", datos, None),
                ("Hipótesis", resultados, "0.00"),
                ("Tabla de tendido", tendido, "0.00"),
            ]:
                df.to_excel(xl, sheet_name=nombre, index=False)
                hoja = xl.sheets[nombre]
                for celda in hoja[1]:
                    celda.font = Font(bold=True, color="FFFFFF")
                    celda.fill = cabecera
                    celda.alignment = Alignment(horizontal="center", wrap_text=True)
                for i, col in enumerate(df.columns, start=1):
                    ancho = (
                        max(len(str(col)), *(len(str(v)) for v in df.iloc[:, i - 1]))
                        + 2
                    )
                    hoja.column_dimensions[get_column_letter(i)].width = min(ancho, 28)
                    if decimales:
                        for celda in hoja[get_column_letter(i)][1:]:
                            if isinstance(celda.value, float):
                                celda.number_format = decimales
                hoja.freeze_panes = "A2"
        return ruta


#  CÁLCULO MECÁNICO DE APOYOS

# Tipos de apoyo según su función (ITC-LAT-07). Los de suspensión, amarre y anclaje
# pueden ser de alineación o de ángulo; los de principio y fin de línea, no.
TIPOS_APOYO = ("principio de línea", "fin de línea", "suspensión", "amarre", "anclaje")
TIPOS_SIN_ANGULO = ("principio de línea", "fin de línea")


def _normalizar(texto: str) -> str:
    "Minúsculas y sin tildes, para aceptar 'Fin de linea', 'AMARRE', etc."
    descompuesto = unicodedata.normalize("NFD", texto.strip().lower())
    return "".join(c for c in descompuesto if unicodedata.category(c) != "Mn")


@dataclass
class Canton:
    "Tramo entre dos apoyos con cadenas de amarre. Todos sus vanos tienen la misma tensión"

    inicio: int  # Nº del apoyo donde empieza
    fin: int  # Nº del apoyo donde acaba
    vano_regulacion: float  # Vano de regulación [m]
    desnivel: float  # Mayor desnivel de sus vanos [m]
    calculo: calculoMecanico = field(repr=False)  # Cálculo mecánico del conductor del cantón

    @property
    def tramos(self) -> list[str]:
        "Vanos del cantón, p. ej. ['3-4', '4-5']"
        return [f"{k}-{k + 1}" for k in range(self.inicio, self.fin)]


@dataclass
class CalculoApoyos:

    conductor: Conductor        # Propiedades de los conductores
    Un : float                  # Tensión de la linea
    alt: float                  # Altitud de la linea
    vanos: list[float]          # Vano entre cada par de apoyos consecutivos [m] (n - 1 valores)
    desniveles: list[float]     # Desnivel de cada apoyo respecto al anterior [m] (n valores, el 1º = 0)
    tipos: list[str]            # Tipo de cada apoyo, uno de TIPOS_APOYO (n valores)
    angulos: dict[int, float] = field(
        default_factory=dict  # {nº de apoyo: ángulo [º]} de los apoyos de ángulo
    )
    tensiones: pd.DataFrame | None = None # Tabla que me da el enuunciado en caso de que me de las tensiones

    # Datos de la línea para calcular cada vano (mismos valores por defecto que calculoMecanico)
    Vv: float | None = None  # Viento máximo de la zona [km/h]
    antivibradores: bool = False  # Si hay antivibradores el EDS sube del 15 % al 22 %
    coef_seguridad: float | None = None  # None -> 3 en media tensión (15-20 kV), 2,5 en el resto
    chs: float | None = 0.20  # Límite CHS a -5 ºC (fracción de la rotura). None -> no se comprueba
    eds: float | None = None  # Límite EDS a 15 ºC (fracción de la rotura). None -> 15 % (22 %)

    def __post_init__(self):
        self.n = len(self.tipos)

        if len(self.desniveles) != self.n:
            raise ValueError(
                f"Hay {self.n} tipos de apoyo pero {len(self.desniveles)} desniveles"
            )
        if len(self.vanos) != self.n - 1:
            raise ValueError(f"Con {self.n} apoyos hay {self.n - 1} vanos, no {len(self.vanos)}")
        if self.desniveles[0] != 0:
            raise ValueError("El primer apoyo no tiene apoyo anterior: su desnivel debe ser 0")

        # Tipos escritos de cualquier forma -> nombre del reglamento
        nombres = {_normalizar(t): t for t in TIPOS_APOYO}
        tipos = []
        for numero, tipo in enumerate(self.tipos, start=1):
            if _normalizar(tipo) not in nombres:
                raise ValueError(f"Apoyo {numero}: tipo {tipo!r} desconocido. Usa uno de {TIPOS_APOYO}")
            tipos.append(nombres[_normalizar(tipo)])
        self.tipos = tipos

        for numero, angulo in self.angulos.items():
            if not 1 <= numero <= self.n:
                raise ValueError(f"Ángulo en el apoyo {numero}, pero solo hay apoyos del 1 al {self.n}")
            if self.tipos[numero - 1] in TIPOS_SIN_ANGULO:
                raise ValueError(f"El apoyo {numero} es de {self.tipos[numero - 1]}: no puede ser de ángulo")
            if not 0 < angulo < 180:
                raise ValueError(f"Apoyo {numero}: el ángulo debe estar entre 0º y 180º, no {angulo}")

        # Geometría: posición horizontal y cota de cada apoyo, tomando el 1º como origen
        self.posiciones = [float(x) for x in np.cumsum([0, *self.vanos])]
        self.cotas = [float(z) for z in np.cumsum(self.desniveles)]

        # Tramos ("1-2", "2-3"...) y cantones, cada uno con su cálculo mecánico
        self.tramos = [f"{k}-{k + 1}" for k in range(1, self.n)]
        self.cantones = self._cantones()

        # Tensiones de cada vano: las del enunciado si se dan, si no las de su cantón
        self.tensiones_calculadas = self.tensiones is None
        if self.tensiones_calculadas:
            self.tensiones = self._tensiones_de_cantones()
        else:
            self.tensiones = self._comprobar_tensiones(self.tensiones)

    def funcion(self, numero: int) -> str | None:
        "'alineación' o 'ángulo' (None en principio y fin de línea)"
        if self.tipos[numero - 1] in TIPOS_SIN_ANGULO:
            return None
        return "ángulo" if numero in self.angulos else "alineación"

    def etiqueta(self, numero: int) -> str:
        "Texto del apoyo en el esquema, p. ej. 'AMARRE\\nÁNGULO 45º'"
        texto = self.tipos[numero - 1].upper()
        if self.funcion(numero) == "ángulo":
            texto += f"\nÁNGULO {self.angulos[numero]:g}º"
        elif self.funcion(numero) == "alineación":
            texto += "\nALINEACIÓN"
        return texto

    #  CANTONES Y TENSIONES

    def _cantones(self) -> list[Canton]:
        """Divide la línea en cantones, cortando en todos los apoyos que no son de suspensión.
        Cada cantón se calcula con su vano de regulación y su mayor desnivel."""
        cortes = [1] + [k for k in range(2, self.n) if self.tipos[k - 1] != "suspensión"] + [self.n]

        cantones = []
        for inicio, fin in itertools.pairwise(cortes):
            vanos = self.vanos[inicio - 1 : fin - 1]
            desniveles = self.desniveles[inicio:fin]  # de cada vano: apoyo final respecto al inicial
            vano_regulacion = math.sqrt(sum(a**3 for a in vanos) / sum(vanos))
            desnivel = max(desniveles, key=abs)

            calculo = calculoMecanico(
                self.conductor,
                Un=self.Un,
                alt=self.alt,
                vano=vano_regulacion,
                desnivel=desnivel,
                Vv=self.Vv,
                antivibradores=self.antivibradores,
                coef_seguridad=self.coef_seguridad,
                chs=self.chs,
                eds=self.eds,
            )
            calculo.resolver()  # los resultados quedan guardados en calculo.resultados
            cantones.append(Canton(inicio, fin, vano_regulacion, desnivel, calculo))
        return cantones

    def canton_de_vano(self, i: int) -> Canton:
        "Cantón al que pertenece el vano i (0 = vano 1-2)"
        return next(c for c in self.cantones if c.inicio <= i + 1 < c.fin)

    def calculo_vano(self, i: int) -> calculoMecanico:
        "Cálculo mecánico del vano i (0 = vano 1-2): el de su cantón, hecho con el vano de regulación"
        return self.canton_de_vano(i).calculo

    def _tensiones_de_cantones(self) -> pd.DataFrame:
        "Tensión T0 (Tm si hay desnivel) [daN] de cada vano en cada hipótesis, la de su cantón"
        filas = {}
        for canton in self.cantones:
            for tramo in canton.tramos:
                filas[tramo] = canton.calculo.resultados["T0_daN"]
        return pd.DataFrame(filas).T.rename_axis("tramo")

    def _comprobar_tensiones(self, tabla) -> pd.DataFrame:
        "Comprueba la tabla del enunciado y la ordena por tramos (los que falten quedan vacíos)"
        tabla = pd.DataFrame(tabla)

        desconocidos = [t for t in tabla.index if t not in self.tramos]
        if desconocidos:
            raise ValueError(f"Los tramos {desconocidos} no existen. Los tramos son {self.tramos}")

        hipotesis = list(self.cantones[0].calculo.resultados.index)
        columnas = [c for c in tabla.columns if c not in hipotesis]
        if columnas:
            raise ValueError(f"{columnas} no son hipótesis del cálculo. Usa nombres de {hipotesis}")

        return tabla.reindex(self.tramos).rename_axis("tramo")

    #  ESQUEMA

    def _parametro_catenaria(self, i: int) -> float:
        "h = T/p [m] del vano i en la hipótesis de temperatura máxima, para dibujarlo"
        resultados = self.calculo_vano(i).resultados
        fila = resultados[resultados.index.str.startswith("flecha temperatura")].iloc[0]
        return fila["T0_daN"] / fila["p_t_daN_m"]

    def esquema(self, ruta=None, mostrar=True):
        """Dibuja el perfil de la línea con los apoyos, los vanos y los desniveles.
        ruta: si se da, guarda la imagen. mostrar=False devuelve la figura sin mostrarla."""
        import matplotlib.pyplot as plt

        x = np.array(self.posiciones)
        z = np.array(self.cotas)
        largo = x[-1]
        alto = max(15, 0.6 * (z.max() - z.min()))  # altura de dibujo de los apoyos [m]

        y_cota_min = z.min() - 0.55 * alto  # línea de cotas de los vanos
        ancho = 0.018 * largo  # ancho de la base de los apoyos en el dibujo

        fondo = {"facecolor": "white", "edgecolor": "none", "alpha": 0.85, "pad": 1.5}  # fondo de los textos

        fig, ax = plt.subplots(figsize=(13, 5.5))

        # Terreno simplificado: une la base de los apoyos
        ax.fill_between(x, z, y_cota_min - 0.2 * alto, color="#e8dcc4", zorder=0)
        ax.plot(x, z, color="#8c7853", lw=1.2, zorder=1)

        # Conductor: parábola de parámetro h (el de cada vano) entre los puntos de sujeción
        y_suj = z + 0.85 * alto
        for i in range(self.n - 1):
            h = self._parametro_catenaria(i)
            x0, x1, y0, y1 = x[i], x[i + 1], y_suj[i], y_suj[i + 1]
            xv = (x0 + x1) / 2 - h * (y1 - y0) / (x1 - x0)  # vértice (punto más bajo)
            yv = y0 - (x0 - xv) ** 2 / (2 * h)
            xs = np.linspace(x0, x1, 200)
            ax.plot(xs, yv + (xs - xv) ** 2 / (2 * h), color="#1f4e79", lw=1.4, zorder=2)

        for i in range(self.n):
            numero = i + 1
            self._dibujar_apoyo(ax, x[i], z[i], alto, ancho)
            ax.text(x[i], z[i] + 1.08 * alto, str(numero), ha="center", va="bottom",
                    fontsize=11, fontweight="bold")
            ax.text(x[i], z[i] - 0.06 * alto, self.etiqueta(numero), ha="center", va="top",
                    fontsize=8, zorder=4, bbox=fondo)

            # Desnivel respecto al apoyo anterior
            d = self.desniveles[i]
            if i > 0 and d != 0:
                xa = x[i] - 3.6 * ancho  # a la izquierda del apoyo, sin pisar su etiqueta
                ax.plot([x[i - 1], xa], [z[i - 1], z[i - 1]], color="0.55", lw=0.8, ls=":", zorder=1)
                ax.annotate("", xy=(xa, z[i]), xytext=(xa, z[i - 1]),
                            arrowprops={"arrowstyle": "<->", "color": "#b03a2e", "lw": 1})
                ax.text(xa - 0.4 * ancho, (z[i] + z[i - 1]) / 2, f"{d:+g} m".replace("-", "−"),
                        ha="right", va="center", fontsize=9, color="#b03a2e", zorder=4, bbox=fondo)

        # Cotas de los vanos
        for i in range(self.n - 1):
            ax.annotate("", xy=(x[i + 1], y_cota_min), xytext=(x[i], y_cota_min),
                        arrowprops={"arrowstyle": "<->", "color": "0.25", "lw": 1})
            ax.text((x[i] + x[i + 1]) / 2, y_cota_min + 0.03 * alto, f"{self.vanos[i]:g} m",
                    ha="center", va="bottom", fontsize=9)
        for i in range(self.n):
            ax.plot([x[i], x[i]], [y_cota_min - 0.05 * alto, z[i] - 0.45 * alto],
                    color="0.6", lw=0.6, ls="--", zorder=1)

        ax.set_xlim(x[0] - 0.06 * largo, x[-1] + 0.06 * largo)
        ax.set_ylim(y_cota_min - 0.2 * alto, z.max() + 1.35 * alto)
        ax.axis("off")
        ax.set_title(f"Esquema de la línea: {self.n} apoyos, {largo:g} m "
                     "(escala vertical exagerada)", fontsize=11)
        fig.tight_layout()

        if ruta is not None:
            fig.savefig(ruta, dpi=150, bbox_inches="tight")
        if mostrar:
            plt.show()
            return None
        return fig

    @staticmethod
    def _dibujar_apoyo(ax, x, z, alto, ancho):
        "Apoyo de celosía: fuste troncopiramidal con celosía, cruceta y punta"
        color = "#333333"
        y_cruceta = z + 0.85 * alto
        arriba = 0.35 * ancho
        izq = lambda y: x - ancho / 2 + (ancho - arriba) / 2 * (y - z) / (y_cruceta - z)
        der = lambda y: 2 * x - izq(y)

        ax.plot([izq(z), izq(y_cruceta)], [z, y_cruceta], color=color, lw=1.2, zorder=3)
        ax.plot([der(z), der(y_cruceta)], [z, y_cruceta], color=color, lw=1.2, zorder=3)
        niveles = np.linspace(z, y_cruceta, 6)
        for y0, y1 in itertools.pairwise(niveles):
            ax.plot([izq(y0), der(y1)], [y0, y1], color=color, lw=0.5, zorder=3)
            ax.plot([der(y0), izq(y1)], [y0, y1], color=color, lw=0.5, zorder=3)
        ax.plot([x - 1.1 * ancho, x + 1.1 * ancho], [y_cruceta, y_cruceta], color=color, lw=1.6,
                zorder=3)
        ax.plot([izq(y_cruceta), x, der(y_cruceta)], [y_cruceta, z + alto, y_cruceta],
                color=color, lw=1.2, zorder=3)
