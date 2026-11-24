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
    calc = at.calculoMecanico(cable, at.Linea(Un=20, alt=600), vano=170)
    calc.resolver()
"""

import cmath
import itertools
import math
import unicodedata
import warnings
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

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
        I_vacio = C * self.Vf  # corriente que absorbe la línea en vacío (por su capacidad)

        return {
            "Tensión de línea en el origen [kV]": U0 * 10**-3,
            "Intensidad en el origen [A]": abs(I0),
            "Potencia activa en el origen [MW]": S0.real * 10**-6,
            "Pérdidas de potencia [MW]": (S0.real - self.Pf) * 10**-6,
            "Pérdidas respecto a P0 [%]": 100 * (S0.real - self.Pf) / S0.real,
            "Caída de tensión aritmética [kV]": (U0 - self.Uf) * 10**-3,
            "Caída de tensión respecto a Uf [%]": 100 * (U0 - self.Uf) / self.Uf,
            "Intensidad de vacío [A]": abs(I_vacio),
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
T_FLECHA_MAXIMA = {"normal": 50, "especial": 85}  # mínimo de la hipótesis de temperatura
DESNIVEL_MINIMO = 1  # Desnivel entre torres para considerar el calculo con desnivel
COEF_SEGURIDAD_MINIMO = 2.5  # ITC-LAT-07 3.2.1: Tmax <= rotura / 2,5
VANO_CATENARIA = 500  # A partir de este vano [m] la flecha se calcula con la catenaria
U_CATENARIA = 1.1996786402577337  # solución de u·tanh(u) = 1 (mínimo de la Tmax con la catenaria)


def _leer_conductor(nombre: str, archivo) -> tuple[str, dict]:
    """Busca un conductor en el CSV y devuelve (nombre de la tabla, datos).
    Da igual escribirlo en mayúsculas o minúsculas, con espacios de más o sin el nombre
    final ("LA 280" -> "LA 280 HAWK")"""
    tabla = pd.read_csv(archivo, index_col="codigo_antiguo")

    def limpio(texto):
        return " ".join(str(texto).split()).upper()

    buscado = limpio(nombre)
    candidatos = [n for n in tabla.index if limpio(n) == buscado]
    if not candidatos:  # "LA 280" -> "LA 280 HAWK", si solo hay uno
        candidatos = [n for n in tabla.index if limpio(n).startswith(buscado + " ")]
    if len(candidatos) != 1:
        raise ValueError(
            f"Conductor {nombre!r} no encontrado en {Path(archivo).name}. "
            f"Disponibles: {', '.join(tabla.index)}"
        )
    return candidatos[0], tabla.loc[candidatos[0]].to_dict()


ARCHIVO_LA = str(CARPETA_CONDUCTORES / "conductores_AL1_ST1A.csv")

# Nombres de los conductores LA del CSV. Sirven para que el editor (Pylance) muestre un
# desplegable con ellos al escribir at.Conductor(" ... Si se añade uno al CSV, hay que añadirlo aquí
# (un test comprueba que coinciden)
NombreLA = Literal[
    "LA 30",
    "LA 56",
    "LA 78",
    "LA 110",
    "LA 145",
    "LA 180",
    "LA 280 HAWK",
    "LA 380 GULL",
    "LA 455 CONDOR",
    "LA 545 CARDINAL",
    "LA 635 FINCH",
]


@dataclass
class Conductor:
    conductor: NombreLA | str  # nombre antiguo, ej: "LA 56" (ver Conductor.disponibles())
    archivo: str = ARCHIVO_LA
    E_dato: float | None = (
        None  # módulo de elasticidad [daN/mm²] (si el enunciado lo da)
    )
    alfa_dato: float | None = (
        None  # coef. de dilatación lineal [1/ºC] (si el enunciado lo da)
    )

    def __post_init__(self):
        self._clave = None  # (conductor, archivo) con que se leyeron los datos
        self.validar()

    @classmethod
    def disponibles(cls, archivo: str = ARCHIVO_LA) -> pd.DataFrame:
        """Tabla con los conductores del CSV y sus datos principales.
        Es de clase (cls): se usa sin crear ningún conductor, at.Conductor.disponibles()"""
        tabla = pd.read_csv(archivo, index_col="codigo_antiguo")
        seccion = "seccion_total_mm2" if "seccion_total_mm2" in tabla else "seccion_mm2"
        return pd.DataFrame(
            {
                "Designación": tabla["codigo"],
                "Sección [mm²]": tabla[seccion],
                "Diámetro [mm]": tabla["d_conductor_mm"],
                "Peso [daN/m]": (tabla["masa_kg_km"] * 9.81 / 10_000).round(4),
                "Rotura [daN]": (tabla["carga_rotura_kN"] * 100).round().astype(int),
            }
        ).rename_axis("Conductor")

    def validar(self):
        "Comprueba los datos. Se llama al crear el conductor y antes de cada cálculo mecánico"
        # α de un conductor es del orden de 10⁻⁵ 1/ºC: 17,8·10⁻⁶ -> 17.8e-6
        if self.alfa_dato is not None and not 0 < self.alfa_dato < 1e-3:
            raise ValueError(
                f"alfa_dato={self.alfa_dato}: fuera de rango. "
                "17,8·10⁻⁶ ºC⁻¹ se escribe 17.8e-6"
            )
        if self.E_dato is not None and not self.E_dato > 0:
            raise ValueError(f"E_dato={self.E_dato}: el módulo de elasticidad tiene que ser positivo [daN/mm²]")
        _ = self.E, self.alfa  # en los conductores homogéneos, comprueba que se han dado

    #  DATOS DE LA TABLA
    # Son propiedades: se calculan cada vez que se consultan, así que si se cambia el
    # conductor, el archivo, E_dato o alfa_dato, nunca se quedan desactualizados.

    @property
    def datos(self) -> dict:
        "Fila del CSV del conductor (se vuelve a leer solo si cambia el conductor o el archivo)"
        clave = (self.conductor, self.archivo)
        if self._clave != clave:
            self.nombre, self._datos = _leer_conductor(self.conductor, self.archivo)
            self._clave = clave
        return self._datos

    @property
    def homogeneo(self) -> bool:
        "True en los conductores de un solo material (AL1, AL2), que no tienen alma de acero"
        return "n_alambres_acero" not in self.datos

    @property
    def p(self) -> float:
        "Peso propio [daN/m]"
        return self.datos["masa_kg_km"] * 9.81 / 10_000

    @property
    def d(self) -> float:
        "Diámetro [mm]"
        return self.datos["d_conductor_mm"]

    @property
    def S(self) -> float:
        "Sección total [mm²]"
        return self.datos["seccion_mm2" if self.homogeneo else "seccion_total_mm2"]

    @property
    def rotura(self) -> float:
        "Carga de rotura [daN]"
        return self.datos["carga_rotura_kN"] * 100

    def _propiedades_tipicas(self) -> tuple[float, float]:
        "(E, α) típicos según la composición. Los conductores homogéneos no tienen"
        if self.homogeneo:
            raise ValueError(
                f"El conductor {self.conductor} es homogéneo (sin acero): no hay E ni α típicos "
                "en el temario, hay que darlos con E_dato y alfa_dato"
            )
        composicion = (int(self.datos["n_alambres_al"]), int(self.datos["n_alambres_acero"]))
        return PROPIEDADES[composicion]

    @property
    def E(self) -> float:
        "Módulo de elasticidad [daN/mm²]: el del enunciado si se da, si no el típico"
        return self.E_dato if self.E_dato is not None else self._propiedades_tipicas()[0]

    @property
    def alfa(self) -> float:
        "Coeficiente de dilatación [1/ºC]: el del enunciado si se da, si no el típico"
        return self.alfa_dato if self.alfa_dato is not None else self._propiedades_tipicas()[1]

    #  SOBRECARGAS (ITC-LAT-07 3.1.2 y 3.1.3)
    # Solo dependen del cable. La velocidad del viento y la zona las decide la línea,
    # por eso se pasan como parámetro.

    def presion_viento(self, v: float = 120, d: float | None = None) -> float:
        "Presión del viento q [daN/m²] a v km/h sobre un cable de diámetro d [mm] (por defecto el del conductor)"
        d = self.d if d is None else d
        q_120 = 60 if d <= 16 else 50
        return q_120 * (v / 120) ** 2

    def sobrecarga_viento(self, v: float = 120) -> float:
        "Sobrecarga de viento p_v [daN/m] a v km/h, sin el peso propio"
        return self.presion_viento(v) * self.d / 1000

    def p_total_viento(self, v: float = 120, factor: float = 1.0) -> float:
        """Peso total con viento p_t = √(p² + p_v²) [daN/m] a v km/h.
        factor multiplica la presión: 0.5 es la mitad de presión de la desviación de cadenas"""
        pv = factor * self.sobrecarga_viento(v)
        return math.hypot(self.p, pv)

    def sobrecarga_hielo(self, zona: str) -> float:
        "Sobrecarga de hielo p_h [daN/m], sin el peso propio: 0 en zona A, 0,18·√d en B y 0,36·√d en C"
        k = {"A": 0, "B": 0.18, "C": 0.36}
        if zona not in k:
            raise ValueError(f"Zona '{zona}' desconocida: tiene que ser 'A', 'B' o 'C'")
        return k[zona] * self.d**0.5

    def p_total_hielo(self, zona: str) -> float:
        "Peso total con hielo p_t = p + p_h [daN/m] (en zona A, solo el peso propio)"
        return self.p + self.sobrecarga_hielo(zona)

    def p_total_hielo_viento(self, zona: str) -> float:
        """Peso total con hielo + viento a 60 km/h [daN/m]: √((p + p_h)² + p_v'²), con p_v'
        calculado sobre el diámetro D del manguito de hielo. Solo zonas B y C."""
        if zona not in ("B", "C"):
            raise ValueError(
                f"La sobrecarga de hielo + viento solo se aplica en zonas B y C, no en '{zona}'"
            )
        columna = f"d_manguito_hielo_{zona}_mm"
        if columna not in self.datos:
            raise ValueError(
                f"La tabla de {self.conductor} no tiene el diámetro del manguito de hielo ({columna})"
            )
        D = self.datos[columna]
        pv_prima = self.presion_viento(60, D) * D / 1000
        return math.hypot(self.p_total_hielo(zona), pv_prima)

    def resumen(self):
        "Texto con las características del conductor, ordenadas por grupos"
        d = self.datos
        origen_E = "del enunciado" if self.E_dato is not None else "típico según composición"
        origen_alfa = "del enunciado" if self.alfa_dato is not None else "típico según composición"

        if self.homogeneo:  # AL1 o AL2: un solo material
            composicion = f"{d['n_alambres']:g} alambres (homogéneo)"
            seccion = f"{self.S:.1f} mm²"
        else:
            composicion = f"{d['n_alambres_al']:g} + {d['n_alambres_acero']:g} alambres (Al + acero)"
            seccion = f"{self.S:.1f} mm²  (Al {d['seccion_al_mm2']:.1f} + acero {d['seccion_acero_mm2']:.1f})"

        grupos = {
            "Características": [
                ("Composición", composicion),
                ("Sección", seccion),
                ("Diámetro", f"{self.d:.2f} mm"),
                ("Peso propio", f"{self.p:.4f} daN/m  ({d['masa_kg_km']:.1f} kg/km)"),
                ("Resistencia en c.c.", f"{d['resistencia_cc_ohm_km']:.4f} Ω/km"),
            ],
            "Propiedades mecánicas": [
                ("Carga de rotura", f"{self.rotura:.0f} daN"),
                ("Módulo de elasticidad", f"{self.E:g} daN/mm²  ({origen_E})"),
                ("Coef. de dilatación", f"{self.alfa * 1e6:g}·10⁻⁶ 1/ºC  ({origen_alfa})"),
            ],
            "Sobrecargas (sin el peso propio)": [
                ("Hielo zona B / C",
                 f"{self.sobrecarga_hielo('B'):.3f} / {self.sobrecarga_hielo('C'):.3f} daN/m"),
                ("Viento 120 / 140 km/h",
                 f"{self.sobrecarga_viento(120):.3f} / {self.sobrecarga_viento(140):.3f} daN/m"),
            ],
        }

        lineas = [f"Conductor {self.nombre} ({d['codigo']})"]
        for grupo, filas in grupos.items():
            lineas.append(f"  {grupo}")
            lineas += [f"    {etiqueta + ':':<24}{valor}" for etiqueta, valor in filas]
        return "\n".join(lineas)


@dataclass
class Linea:
    "Datos de la línea comunes a todos sus cálculos mecánicos: tensión, altitud, viento y límites"

    Un: float  # Tensión nominal de la línea [kV]
    alt: float  # Altitud de la línea [m]
    Vv: float | None = (
        None  # Viento máximo de la zona [km/h] (si > 120/140 -> viento excepcional)
    )
    antivibradores: bool = False  # Si hay antivibradores el EDS sube del 15 % al 22 %
    coef_seguridad: float | None = (
        None  # None -> 3 en media tensión (15-20 kV), 2,5 en el resto
    )
    chs: float | None = (
        0.20  # Límite CHS a -5 ºC (fracción de la rotura). None -> no se comprueba
    )
    eds: float | None = (
        None  # Límite EDS a 15 ºC (fracción de la rotura). None -> 15 % (22 %)
    )
    temperatura_maxima: float | None = (
        None  # Temperatura de la flecha máxima [ºC]. None -> 50 ºC (85 ºC en cat. especial)
    )

    def __post_init__(self):
        self.validar()

    def validar(self):
        "Comprueba los datos. Se llama al crear la línea y antes de cada cálculo mecánico"
        # "not x > 0" en vez de "x <= 0" para que también falle con nan
        if not self.Un > 0:
            raise ValueError(f"Un={self.Un}: la tensión nominal tiene que ser positiva [kV]")
        if not self.alt >= 0:
            raise ValueError(f"alt={self.alt}: la altitud no puede ser negativa [m]")
        if self.Vv is not None and not self.Vv > 0:
            raise ValueError(f"Vv={self.Vv}: la velocidad del viento tiene que ser positiva [km/h]")

        # Los límites van en tanto por uno: 15 % -> 0.15
        for nombre in ("eds", "chs"):
            valor = getattr(self, nombre)
            if valor is not None and not 0 < valor < 1:
                raise ValueError(
                    f"{nombre}={valor}: el límite va en tanto por uno (15 % -> 0.15)"
                )

        if self.coef_seguridad is not None:
            if not self.coef_seguridad > 0:
                raise ValueError(f"coef_seguridad={self.coef_seguridad}: tiene que ser positivo")
            if self.coef_seguridad < COEF_SEGURIDAD_MINIMO:
                warnings.warn(
                    f"coef_seguridad={self.coef_seguridad:g} es menor que el mínimo del reglamento "
                    f"({COEF_SEGURIDAD_MINIMO:g}, ITC-LAT-07 3.2.1)",
                    stacklevel=3,
                )

        minimo = T_FLECHA_MAXIMA[self.categoria]
        if self.temperatura_maxima is not None and not self.temperatura_maxima >= minimo:
            raise ValueError(
                f"temperatura_maxima={self.temperatura_maxima}: en categoría {self.categoria} "
                f"no puede ser menor de {minimo} ºC"
            )

    #  DATOS DEDUCIDOS
    # Son propiedades: se calculan cada vez que se consultan, así que si después se cambia
    # la altitud, la tensión, etc., nunca se quedan desactualizados.

    @property
    def limite_eds(self) -> float:
        "Límite EDS (tanto por uno): el del enunciado si se da, si no el del RLAT"
        if self.eds is not None:
            return self.eds
        return 0.22 if self.antivibradores else 0.15

    @property
    def Zona(self) -> str:
        "Zona según la altitud: A (< 500 m), B (500-1000 m) o C (> 1000 m)"
        return "A" if self.alt < 500 else ("B" if self.alt <= 1000 else "C")

    @property
    def categoria(self) -> str:
        "'especial' desde 220 kV, 'normal' por debajo"
        return "especial" if self.Un >= 220 else "normal"

    @property
    def v_ref(self) -> float:
        "Viento de referencia del RLAT [km/h]"
        return 140 if self.categoria == "especial" else 120

    @property
    def v_excepcional(self) -> float | None:
        "Viento excepcional [km/h]: solo si el dato de entrada supera el de referencia"
        if self.Vv is not None and self.Vv > self.v_ref:
            return self.Vv
        return None

    @property
    def coef(self) -> float:
        "Coeficiente de seguridad: el del enunciado, o 3 en media tensión (15-20 kV) y 2,5 en el resto"
        if self.coef_seguridad is not None:
            return self.coef_seguridad
        return 3 if 15 <= self.Un <= 20 else 2.5  # el 3 evita la hipótesis de rotura en apoyos

    @property
    def t_flecha_maxima(self) -> float:
        "Temperatura de la hipótesis de flecha máxima [ºC]: la del enunciado o el mínimo del RLAT"
        if self.temperatura_maxima is not None:
            return self.temperatura_maxima
        return T_FLECHA_MAXIMA[self.categoria]

    def resumen(self):
        "Texto con las características de la línea según el RLAT"
        if self.v_excepcional is not None:
            viento = f"{self.v_ref} km/h (excepcional: {self.v_excepcional} km/h)"
        else:
            viento = f"{self.v_ref} km/h"
        chs = f"{self.chs:.0%}" if self.chs is not None else "no se comprueba"

        return "\n".join(
            [
                f"Línea de {self.Un:g} kV a {self.alt:g} m de altitud",
                f"  Categoría:          {self.categoria}",
                f"  Zona:               {self.Zona}",
                f"  Viento:             {viento}",
                f"  Antivibradores:     {self.antivibradores}",
                f"  Coef. de seguridad: {self.coef:g}",
                f"  Límite EDS (15 ºC): {self.limite_eds:.0%}",
                f"  Límite CHS (-5 ºC): {chs}",
                f"  Flecha máxima a:    {self.t_flecha_maxima:g} ºC",
            ]
        )


def _lista_de_temperaturas(temperaturas) -> list[float]:
    "Acepta una temperatura suelta (25) o una lista/range de temperaturas [ºC]"
    error = TypeError(
        f"temperaturas={temperaturas!r}: tiene que ser una temperatura o una lista "
        "de temperaturas, p. ej. range(0, 50, 5) o [0, 15, 50]"
    )
    if isinstance(temperaturas, bool):  # True/False también son int en Python
        raise error
    if isinstance(temperaturas, (int, float)):
        return [temperaturas]
    try:
        lista = list(temperaturas)
    except TypeError:
        raise error from None
    if not all(isinstance(t, (int, float)) and not isinstance(t, bool) for t in lista):
        raise TypeError(f"temperaturas={temperaturas!r}: todas tienen que ser números [ºC]")
    return lista


@dataclass
class calculoMecanico:
    conductor: Conductor
    linea: Linea  # Datos de la línea (tensión, altitud, viento, límites...)
    vano: float  # Vano proyectado a, o vano de regulación [m]
    desnivel: float = 0.0  # Desnivel entre los apoyos del vano [m]

    def __post_init__(self):
        self.validar()

    def validar(self):
        "Comprueba los datos del vano, de la línea y del conductor (al crearlo y antes de calcular)"
        if not self.vano > 0:
            raise ValueError(f"vano={self.vano}: tiene que ser mayor que 0 [m]")
        if not math.isfinite(self.desnivel):
            raise ValueError(f"desnivel={self.desnivel}: tiene que ser un número [m]")
        self.linea.validar()
        self.conductor.validar()

    #  DESNIVEL
    # Son propiedades para que, si se cambia el vano o el desnivel, no se queden viejas.

    @property
    def vano_real(self) -> float:
        "Vano real b = √(a² + d²) [m]"
        return math.hypot(self.vano, self.desnivel)

    @property
    def con_desnivel(self) -> bool:
        "Si el desnivel llega a DESNIVEL_MINIMO (por debajo, el vano se calcula a nivel)"
        return abs(self.desnivel) >= DESNIVEL_MINIMO

    @property
    def _d(self) -> float:
        "|desnivel| que entra en las fórmulas [m]: 0 por debajo de DESNIVEL_MINIMO"
        return abs(self.desnivel) if self.con_desnivel else 0.0

    @property
    def _b(self) -> float:
        "Vano real que entra en las fórmulas [m]: el vano a si el desnivel no llega al mínimo"
        return math.hypot(self.vano, self._d)

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

    def _Tmax_minima(self, p_t):
        """(T0, Tmax) en el punto en que la Tmax es la más pequeña posible.
        Tmax(T0) baja y luego sube: con T0 pequeña la flecha se dispara. Si el límite de una
        hipótesis es menor que esta Tmax mínima, ninguna tensión lo cumple (vano inviable)."""
        b, d = self._b, self._d
        if self.vano > VANO_CATENARIA:
            # Tmax = p·h·cosh(b/2h) + p·d/2 es mínima cuando u·tanh(u) = 1, con u = b/2h
            h = b / 2 / U_CATENARIA
            return p_t * h, p_t * h * math.cosh(U_CATENARIA) + p_t * d / 2
        # Tmax = T0 + b²p²/(8·T0) + p·d/2 es mínima en T0 = b·p/(2√2)
        return b * p_t / (2 * math.sqrt(2)), b * p_t / math.sqrt(2) + p_t * d / 2

    def _T0_desde_Tmax(self, Tmax, p_t, nombre="la hipótesis"):
        """T0 [daN] tal que _Tmax(T0) = Tmax: pone una hipótesis justo en su límite.
        Es la inversa exacta de _Tmax. Con la parábola se despeja (método del profesor);
        con la catenaria (vano > 500 m) no se puede despejar y se busca por bisección."""
        T_min, Tmax_min = self._Tmax_minima(p_t)
        if Tmax < Tmax_min * (1 - 1e-12):
            raise ValueError(
                f"Vano inviable con el {self.conductor.conductor}: en {nombre} la tensión máxima "
                f"nunca baja de {Tmax_min:.1f} daN y el límite es {Tmax:.1f} daN. "
                "Reduce el vano o el desnivel, o usa un conductor más resistente"
            )

        if self.vano <= VANO_CATENARIA:  # despejado de Tmax = T0 + p·(f + d/2)
            b, d = self._b, self._d
            raiz = math.sqrt(max(0.0, (p_t * d - 2 * Tmax) ** 2 - 2 * (b * p_t) ** 2))
            return ((2 * Tmax - p_t * d) + raiz) / 4

        # Catenaria: bisección en la rama de tensiones altas, entre T_min y Tmax
        bajo, alto = T_min, Tmax
        for _ in range(200):
            medio = (bajo + alto) / 2
            if self._Tmax(medio, p_t) < Tmax:
                bajo = medio
            else:
                alto = medio
            if alto - bajo <= 1e-12 * alto:
                break
        return (bajo + alto) / 2

    def _Tmax(self, T0, p_t):
        "Tensión máxima en los apoyos [daN]: Tmax = T0 + p·(f + d/2)"
        return T0 + p_t * (self._flecha(T0, p_t) + self._d / 2)

    def _flecha_exacta(self, T, p_t):
        """Flecha [m] con la catenaria. T [daN], p_t [daN/m].
        Usa el vano real b, como la parábola, para que la flecha no salte al pasar de 500 m"""
        h = T / p_t  # parámetro de la catenaria [m]
        u = self._b / (2 * h)
        if u > 700:  # cosh desborda: con una tensión tan pequeña la flecha es enorme
            return math.inf
        return h * (math.cosh(u) - 1)

    def _flecha_aprox(self, T, p_t):
        "Flecha con la parábola [m]: b²·p/(8·T). Vale si a < 500 m"
        return self._b**2 * p_t / (8 * T)

    def _flecha(self, T, p_t):
        "Flecha [m]: con la catenaria si el vano pasa de 500 m, si no con la parábola"
        if self.vano > VANO_CATENARIA:
            return self._flecha_exacta(T, p_t)
        return self._flecha_aprox(T, p_t)

    #  HIPÓTESIS

    def _hipotesis_limitantes(self):
        """Hipótesis que limitan la tensión.
        Cada una: (nombre, θ [ºC], p_t [daN/m], T_límite [daN], el límite se aplica a Tmax?)"""
        R = self.conductor.rotura
        t_v = T_VIENTO[self.linea.Zona]

        lista = [
            ("EDS", 15, self.conductor.p, self.linea.limite_eds * R, self.con_desnivel),
            (
                "viento",
                t_v,
                self.conductor.p_total_viento(self.linea.v_ref),
                R / self.linea.coef,
                True,
            ),
        ]
        if self.linea.chs is not None:
            lista.append(
                ("CHS", -5, self.conductor.p, self.linea.chs * R, self.con_desnivel)
            )
        if self.linea.v_excepcional is not None:
            lista.append(
                (
                    "viento excepcional",
                    t_v,
                    self.conductor.p_total_viento(self.linea.v_excepcional),
                    R / self.linea.coef,
                    True,
                )
            )
        if self.linea.Zona in T_HIELO:
            p_h = (
                self.conductor.p_total_hielo_viento(self.linea.Zona)
                if self.linea.categoria == "especial"
                else self.conductor.p_total_hielo(self.linea.Zona)
            )
            lista.append(
                ("hielo", T_HIELO[self.linea.Zona], p_h, R / self.linea.coef, True)
            )
        return lista

    def _hipotesis_resultado(self):
        "Hipótesis de flechas: (nombre, θ [ºC], p_t [daN/m])"
        t_max = self.linea.t_flecha_maxima
        lista = [
            (
                "flecha viento 15ºC",
                15,
                self.conductor.p_total_viento(120),
            ),  # siempre 120 km/h (aptdo. 3.2.3)
            (f"flecha temperatura {t_max:g}ºC", t_max, self.conductor.p),
        ]
        if self.linea.Zona in T_HIELO:
            lista.append(("flecha hielo 0ºC", 0, self.conductor.p_total_hielo(self.linea.Zona)))
        lista += [
            ("flecha mínima", T_FLECHA_MIN[self.linea.Zona], self.conductor.p),
            (
                "desviación cadena",  # mitad de la presión del viento de 120 km/h
                T_VIENTO[self.linea.Zona],
                self.conductor.p_total_viento(120, factor=0.5),
            ),
        ]
        return lista

    def _estado_inicial(self, hipotesis):
        "Convierte una hipótesis limitante en estado conocido (nombre, θ, p_t, T0) poniéndola en su límite"
        nombre, theta, p_t, T_lim, sobre_Tmax = hipotesis
        T0 = self._T0_desde_Tmax(T_lim, p_t, nombre) if sobre_Tmax else T_lim
        return nombre, theta, p_t, T0

    def _ratio(self, T0, p_t, T_lim, sobre_Tmax):
        "Cuánto se usa del límite (>1 = se pasa)"
        T = self._Tmax(T0, p_t) if sobre_Tmax else T0
        return T / T_lim

    def _hipotesis_dominante(self):
        "Busca la hipótesis que manda. Devuelve el estado inicial (nombre, θ, p_t, T0)"
        limitantes = self._hipotesis_limitantes()
        partida = self._estado_inicial(limitantes[0])  # se empieza suponiendo el EDS

        # Una vuelta por hipótesis y una más: así también se comprueba el último reinicio
        peor_ratio, peor = math.inf, limitantes[0]
        for _ in range(len(limitantes) + 1):
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

        # No debería pasar nunca, pero si pasa, mejor un error que un resultado que incumple
        raise RuntimeError(
            f"No se ha encontrado la hipótesis que manda: {peor[0]} queda al "
            f"{100 * peor_ratio:.2f} % de su límite"
        )

    @property
    def dominante(self) -> str:
        "Nombre de la hipótesis que manda"
        return self._hipotesis_dominante()[0]

    def resolver(self):
        "Calcula todas las hipótesis. Devuelve un DataFrame con T0, Tmax, % rotura (con T0 y con Tmax) y flecha"
        self.validar()
        nombre1, theta1, p1, T1 = self._hipotesis_dominante()
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

    def tabla_tendido(self, temperaturas: Iterable[float] | float = range(0, 50, 5)):
        "Tensión y flecha de tendido (sin sobrecarga) para cada temperatura [ºC]"
        temperaturas = _lista_de_temperaturas(temperaturas)
        self.validar()
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
        "Mayor flecha de las hipótesis de flecha máxima [m] (se recalcula siempre)"
        resultados = self.resolver()
        nombres = [
            n
            for n in resultados.index
            if n.startswith("flecha") and n != "flecha mínima"
        ]
        return resultados.loc[nombres, "flecha_m"].max()

    #  EXPORTAR

    def exportar_excel(
        self,
        ruta: str | Path = "calculo_mecanico.xlsx",
        temperaturas: Iterable[float] | float = range(0, 50, 5),
    ):
        "Guarda en un Excel los datos de entrada, la tabla de hipótesis y la tabla de tendido"
        from openpyxl.styles import Alignment, Font, PatternFill
        from openpyxl.utils import get_column_letter

        # Sin extensión se le pone .xlsx; con otra extensión, error (se escribiría un .xlsx mal nombrado)
        ruta = Path(ruta)
        if ruta.suffix == "":
            ruta = ruta.with_suffix(".xlsx")
        elif ruta.suffix.lower() != ".xlsx":
            raise ValueError(f"ruta={str(ruta)!r}: el archivo tiene que ser .xlsx")

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
                ["Tensión nominal Un", self.linea.Un, "kV"],
                ["Altitud", self.linea.alt, "m"],
                ["Zona", self.linea.Zona, ""],
                ["Categoría", self.linea.categoria, ""],
                ["Vano", self.vano, "m"],
                ["Desnivel", self.desnivel, "m"],
                ["Vano real b", round(self.vano_real, 2), "m"],
                ["Viento de referencia", self.linea.v_ref, "km/h"],
                [
                    "Viento excepcional",
                    self.linea.v_excepcional if self.linea.v_excepcional else "—",
                    "km/h",
                ],
                ["Coeficiente de seguridad", self.linea.coef, ""],
                ["Límite EDS", round(100 * self.linea.limite_eds, 2), "% rotura"],
                [
                    "Límite CHS",
                    round(100 * self.linea.chs, 2)
                    if self.linea.chs is not None
                    else "—",
                    "% rotura",
                ],
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
                    # max() de una lista, para que funcione también con una tabla vacía
                    ancho = max([len(str(col)), *(len(str(v)) for v in df.iloc[:, i - 1])]) + 2
                    hoja.column_dimensions[get_column_letter(i)].width = min(ancho, 28)
                    if decimales:
                        for celda in hoja[get_column_letter(i)][1:]:
                            if isinstance(celda.value, float):
                                celda.number_format = decimales
                hoja.freeze_panes = "A2"
        return str(ruta)


#  CÁLCULO MECÁNICO DE APOYOS

# Tipos de apoyo según su función (ITC-LAT-07). Los de suspensión, amarre y anclaje
# pueden ser de alineación o de ángulo; los de principio y fin de línea, no.
TIPOS_APOYO = ("principio de línea", "fin de línea", "suspensión", "amarre", "anclaje")
TIPOS_SIN_ANGULO = ("principio de línea", "fin de línea")

# Cadenas de aisladores por fase: una en suspensión y en los extremos, dos (una a cada lado) en amarre
CADENAS_POR_FASE = {
    "principio de línea": 1,
    "fin de línea": 1,
    "suspensión": 1,
    "amarre": 2,
    "anclaje": 2,
}

# 3ª hipótesis: desequilibrio de tracciones en tanto por uno (Un <= 66 kV, Un > 66 kV). ITC-LAT-07 3.1.4
DESEQUILIBRIO = {
    "suspensión": (0.08, 0.15),
    "amarre": (0.15, 0.25),
    "anclaje": (0.50, 0.50),
}

# 4ª hipótesis: tensión del conductor roto que llega al apoyo (un conductor por fase). ITC-LAT-07 3.1.5
ROTURA = {
    "suspensión": 0.50,
    "amarre": 1.0,
    "anclaje": 1.0,
    "principio de línea": 1.0,
    "fin de línea": 1.0,
}

# Formas constructivas: celosía (UNE 207017) y chapa (UNE 207018)
FORMAS_APOYO = ("celosía", "chapa")

# Columnas de la tabla de esfuerzos, como en los resúmenes de clase
NOMBRES_HIPOTESIS = ("1ª viento", "2ª hielo", "3ª desequilibrio", "4ª rotura")


def factor_reduccion_chapa(
    b: float, c: float, hc: float = 5.0, h0: float = 0.25
) -> float:
    """Factor para llevar los esfuerzos de una cruceta de bóveda al punto donde los da el
    fabricante en apoyos de chapa (h0 por debajo de la cogolla): (h + hc) / (hc - h0),
    con h = (b + 2c) / 3 la altura de la resultante. b y c: cotas de la cruceta [m]"""
    h = (b + 2 * c) / 3
    return (h + hc) / (hc - h0)


def _normalizar(texto: str) -> str:
    "Minúsculas y sin tildes, para aceptar 'Fin de linea', 'AMARRE', etc."
    descompuesto = unicodedata.normalize("NFD", texto.strip().lower())
    return "".join(c for c in descompuesto if unicodedata.category(c) != "Mn")


@dataclass(kw_only=True)  # kw_only: los datos se pasan siempre con su nombre (peso_cruceta=70...)
class Armado:
    """Lo que lleva montado un tipo de apoyo: la cruceta y las cadenas de aisladores, y la
    forma del apoyo. Se crea uno por cada tipo de apoyo y se pasan a CalculoApoyos(armados=...)"""

    peso_cruceta: float  # Peso de la cruceta [daN]
    peso_cadena: float  # Peso de una cadena de aisladores con sus herrajes [daN]
    brazo: float | None = None  # Distancia del conductor exterior al eje del apoyo [m] (4ª hipótesis)
    forma: str = "celosía"  # Forma del apoyo: "celosía" (UNE 207017) o "chapa" (UNE 207018)
    b: float | None = None  # Cotas de la cruceta de bóveda [m], para el factor de chapa
    c: float | None = None
    hc: float = 5.0  # Datos del fabricante para el factor de chapa [m] (ver factor_reduccion_chapa)
    h0: float = 0.25

    def __post_init__(self):
        formas = {_normalizar(f): f for f in FORMAS_APOYO}
        if _normalizar(self.forma) not in formas:
            raise ValueError(f"Forma {self.forma!r} desconocida. Usa una de {FORMAS_APOYO}")
        self.forma = formas[_normalizar(self.forma)]

        for nombre in ("peso_cruceta", "peso_cadena"):
            if not getattr(self, nombre) >= 0:
                raise ValueError(f"{nombre}={getattr(self, nombre)}: no puede ser negativo [daN]")
        if self.brazo is not None and not self.brazo > 0:
            raise ValueError(f"brazo={self.brazo}: tiene que ser positivo [m]")
        if (self.b is None) != (self.c is None):
            raise ValueError("Las cotas de la cruceta de bóveda van juntas: da b y c")

    @property
    def factor_chapa(self) -> float:
        """Factor por el que se multiplican T y L en los apoyos de chapa para llevarlos al punto
        del fabricante. 1 en celosía, o en chapa si no se dan las cotas b y c"""
        if self.forma == "chapa" and self.b is not None and self.c is not None:
            return factor_reduccion_chapa(self.b, self.c, self.hc, self.h0)
        return 1.0


@dataclass
class Canton:
    "Tramo entre dos apoyos con cadenas de amarre. Todos sus vanos tienen la misma tensión"

    inicio: int  # Nº del apoyo donde empieza
    fin: int  # Nº del apoyo donde acaba
    vano_regulacion: float  # Vano de regulación [m]
    desnivel: float  # Mayor desnivel de sus vanos [m]
    calculo: calculoMecanico = field(
        repr=False
    )  # Cálculo mecánico del conductor del cantón

    @property
    def tramos(self) -> list[str]:
        "Vanos del cantón, p. ej. ['3-4', '4-5']"
        return [f"{k}-{k + 1}" for k in range(self.inicio, self.fin)]


@dataclass
class CalculoApoyos:
    conductor: Conductor  # Propiedades de los conductores
    linea: Linea  # Datos de la línea (tensión, altitud, viento, límites...)
    vanos: list[float]  # Vano entre cada par de apoyos consecutivos [m] (n - 1 valores)
    desniveles: list[
        float
    ]  # Desnivel de cada apoyo respecto al anterior [m] (n valores, el 1º = 0)
    tipos: list[str]  # Tipo de cada apoyo, uno de TIPOS_APOYO (n valores)
    angulos: dict[int, float] = field(
        default_factory=dict  # {nº de apoyo: ángulo [º]} de los apoyos de ángulo
    )
    tensiones: pd.DataFrame | None = (
        None  # Tabla que me da el enuunciado en caso de que me de las tensiones
    )

    # Datos de los apoyos para calcular los esfuerzos
    armados: Armado | dict[str, Armado] | None = (
        None  # Uno para todos, o {tipo de apoyo: Armado}; "resto" vale para los demás tipos
    )
    n_conductores: int = 3  # Nº de conductores (3 en un circuito simplex)
    rotura: bool | None = None  # 4ª hipótesis: None -> según ITC-LAT-07 3.5.3

    def __post_init__(self):
        self.n = len(self.tipos)

        if len(self.desniveles) != self.n:
            raise ValueError(
                f"Hay {self.n} tipos de apoyo pero {len(self.desniveles)} desniveles"
            )
        if len(self.vanos) != self.n - 1:
            raise ValueError(
                f"Con {self.n} apoyos hay {self.n - 1} vanos, no {len(self.vanos)}"
            )
        if self.desniveles[0] != 0:
            raise ValueError(
                "El primer apoyo no tiene apoyo anterior: su desnivel debe ser 0"
            )

        # Tipos escritos de cualquier forma -> nombre del reglamento
        nombres = {_normalizar(t): t for t in TIPOS_APOYO}
        tipos = []
        for numero, tipo in enumerate(self.tipos, start=1):
            if _normalizar(tipo) not in nombres:
                raise ValueError(
                    f"Apoyo {numero}: tipo {tipo!r} desconocido. Usa uno de {TIPOS_APOYO}"
                )
            tipos.append(nombres[_normalizar(tipo)])
        self.tipos = tipos

        for numero, angulo in self.angulos.items():
            if not 1 <= numero <= self.n:
                raise ValueError(
                    f"Ángulo en el apoyo {numero}, pero solo hay apoyos del 1 al {self.n}"
                )
            if self.tipos[numero - 1] in TIPOS_SIN_ANGULO:
                raise ValueError(
                    f"El apoyo {numero} es de {self.tipos[numero - 1]}: no puede ser de ángulo"
                )
            if not 0 < angulo < 180:
                raise ValueError(
                    f"Apoyo {numero}: el ángulo debe estar entre 0º y 180º, no {angulo}"
                )

        # Geometría: posición horizontal y cota de cada apoyo, tomando el 1º como origen
        self.posiciones = [float(x) for x in np.cumsum([0, *self.vanos])]
        self.cotas = [float(z) for z in np.cumsum(self.desniveles)]

        # Armados: las claves escritas de cualquier forma -> nombre del reglamento (o "resto")
        if isinstance(self.armados, dict):
            armados = {}
            for clave, armado in self.armados.items():
                if _normalizar(clave) == "resto":
                    armados["resto"] = armado
                elif _normalizar(clave) in nombres:
                    armados[nombres[_normalizar(clave)]] = armado
                else:
                    raise ValueError(
                        f"armados: {clave!r} no es un tipo de apoyo. Usa uno de {TIPOS_APOYO} o 'resto'"
                    )
            self.armados = armados
        valores = self.armados.values() if isinstance(self.armados, dict) else [self.armados]
        if not all(a is None or isinstance(a, Armado) for a in valores):
            raise TypeError("armados: cada armado tiene que ser un at.Armado(...)")

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
        cortes = (
            [1]
            + [k for k in range(2, self.n) if self.tipos[k - 1] != "suspensión"]
            + [self.n]
        )

        cantones = []
        for inicio, fin in itertools.pairwise(cortes):
            vanos = self.vanos[inicio - 1 : fin - 1]
            desniveles = self.desniveles[
                inicio:fin
            ]  # de cada vano: apoyo final respecto al inicial
            vano_regulacion = math.sqrt(sum(a**3 for a in vanos) / sum(vanos))
            desnivel = max(desniveles, key=abs)

            calculo = calculoMecanico(
                self.conductor, self.linea, vano=vano_regulacion, desnivel=desnivel
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
            raise ValueError(
                f"Los tramos {desconocidos} no existen. Los tramos son {self.tramos}"
            )

        hipotesis = list(self.cantones[0].calculo.resultados.index)
        columnas = [c for c in tabla.columns if c not in hipotesis]
        if columnas:
            raise ValueError(
                f"{columnas} no son hipótesis del cálculo. Usa nombres de {hipotesis}"
            )

        return tabla.reindex(self.tramos).rename_axis("tramo")

    #  AUXILIARES PARA LAS HIPÓTESIS

    def _lados(self, numero: int) -> list[tuple[str, float, float, int]]:
        """Vanos a cada lado del apoyo: (tramo, vano [m], desnivel [m], signo en el gravivano).
        El desnivel es el del apoyo final del vano respecto al inicial."""
        lados = []
        if numero > 1:  # vano anterior: este apoyo es su extremo final
            lados.append(
                (
                    f"{numero - 1}-{numero}",
                    self.vanos[numero - 2],
                    self.desniveles[numero - 1],
                    1,
                )
            )
        if numero < self.n:  # vano siguiente: este apoyo es su extremo inicial
            lados.append(
                (
                    f"{numero}-{numero + 1}",
                    self.vanos[numero - 1],
                    self.desniveles[numero],
                    -1,
                )
            )
        return lados

    def _tension(self, tramo: str, hipotesis: str) -> float:
        "Tensión del conductor del tramo en la hipótesis [daN], de la tabla de tensiones"
        tabla = self.tensiones  # siempre es un DataFrame tras __post_init__
        T = math.nan
        if tabla is not None and hipotesis in tabla.columns:
            T = float(tabla[hipotesis].to_numpy(dtype=float)[self.tramos.index(tramo)])
        if math.isnan(T):
            raise ValueError(f"Falta la tensión de {hipotesis} del tramo {tramo}")
        return T

    def _peso_aparente(self, hipotesis: str) -> float:
        "Peso del conductor con la sobrecarga de la hipótesis [daN/m], el del gravivano"
        if hipotesis == "viento":
            return self.conductor.p_total_viento(self.linea.v_ref)
        return self.conductor.p_total_hielo(self.linea.Zona)

    def gravivano(self, numero: int, hipotesis: str) -> float:
        "Longitud de conductor cuyo peso soporta el apoyo [m]: Σ a/2 ± (T/p)·(d/a)"
        p = self._peso_aparente(hipotesis)
        return sum(
            a / 2 + signo * self._tension(tramo, hipotesis) / p * d / a
            for tramo, a, d, signo in self._lados(numero)
        )

    def eolovano(self, numero: int) -> float:
        "Longitud de conductor cuyo viento soporta el apoyo [m]: Σ a/2"
        return sum(a / 2 for _, a, _, _ in self._lados(numero))

    def armado(self, numero: int) -> Armado | None:
        "Armado del apoyo: el de su tipo, o el de 'resto' (None si no se ha dado)"
        if not isinstance(self.armados, dict):
            return self.armados
        tipo = self.tipos[numero - 1]
        return self.armados.get(tipo, self.armados.get("resto"))

    def _armado_obligatorio(self, numero: int) -> Armado:
        "Armado del apoyo, con un error claro si falta"
        armado = self.armado(numero)
        if armado is None:
            tipo = self.tipos[numero - 1]
            raise ValueError(
                f"Falta el armado del apoyo {numero} ({tipo}): pásalo en "
                f"armados={{'{tipo}': at.Armado(...)}} o con la clave 'resto'"
            )
        return armado

    @property
    def formas(self) -> list[str]:
        "Forma de cada apoyo (celosía si no tiene armado)"
        formas = []
        for numero in range(1, self.n + 1):
            armado = self.armado(numero)
            formas.append(armado.forma if armado is not None else "celosía")
        return formas

    def _peso_cadenas_y_cruceta(self, numero: int) -> float:
        "Peso de las cadenas (con herrajes) y de la cruceta del apoyo [daN]"
        armado = self._armado_obligatorio(numero)
        cadenas = self.n_conductores * CADENAS_POR_FASE[self.tipos[numero - 1]]
        return cadenas * armado.peso_cadena + armado.peso_cruceta

    def _hipotesis_base(self) -> str:
        "Sobrecarga de la 3ª y 4ª hipótesis: hielo en zonas B y C, viento en zona A"
        return "viento" if self.linea.Zona == "A" else "hielo"

    #  HIPÓTESIS DE CÁLCULO DE APOYOS (ITC-LAT-07 3.5.3)
    # Cada una devuelve los esfuerzos del apoyo sin reducir al punto del fabricante [daN, daN·m]:
    # V vertical, T transversal, L longitudinal y Mt momento torsor. None = no aplica.

    def hipotesis_viento(self, numero: int) -> dict:
        "1ª hipótesis: viento de 120 km/h (140 en categoría especial)"
        n, tipo, alfa = (
            self.n_conductores,
            self.tipos[numero - 1],
            self.angulos.get(numero),
        )
        lados = self._lados(numero)
        pv = self.conductor.sobrecarga_viento(self.linea.v_ref)  # viento por metro de conductor [daN/m]

        V = n * self.conductor.p * self.gravivano(
            numero, "viento"
        ) + self._peso_cadenas_y_cruceta(numero)
        T = n * pv * self.eolovano(numero)
        if alfa:  # resultante de ángulo + viento proyectado en la bisectriz
            tensiones = sum(self._tension(tramo, "viento") for tramo, *_ in lados)
            T = n * (
                tensiones * math.sin(math.radians(alfa / 2))
                + pv * self.eolovano(numero) * math.cos(math.radians(alfa / 2))
            )
        L = (
            n * self._tension(lados[0][0], "viento")
            if tipo in TIPOS_SIN_ANGULO
            else None
        )
        return {"V": V, "T": T, "L": L, "Mt": None}

    def hipotesis_hielo(self, numero: int) -> dict:
        "2ª hipótesis: hielo (solo zonas B y C)"
        if self.linea.Zona == "A":
            raise ValueError("En zona A no hay 2ª hipótesis (hielo)")
        if self.linea.categoria == "especial":
            raise NotImplementedError(
                "Falta la 2ª hipótesis de categoría especial (hielo + viento)"
            )

        n, tipo, alfa = (
            self.n_conductores,
            self.tipos[numero - 1],
            self.angulos.get(numero),
        )
        lados = self._lados(numero)

        V = n * self.conductor.p_total_hielo(self.linea.Zona) * self.gravivano(
            numero, "hielo"
        ) + self._peso_cadenas_y_cruceta(numero)
        T = None
        if alfa:  # resultante de ángulo
            tensiones = sum(self._tension(tramo, "hielo") for tramo, *_ in lados)
            T = n * tensiones * math.sin(math.radians(alfa / 2))
        L = (
            n * self._tension(lados[0][0], "hielo")
            if tipo in TIPOS_SIN_ANGULO
            else None
        )
        return {"V": V, "T": T, "L": L, "Mt": None}

    def hipotesis_desequilibrio(self, numero: int) -> dict:
        "3ª hipótesis: desequilibrio de tracciones (no se aplica en principio ni fin de línea)"
        tipo, alfa, n = (
            self.tipos[numero - 1],
            self.angulos.get(numero),
            self.n_conductores,
        )
        if tipo in TIPOS_SIN_ANGULO:
            raise ValueError(
                f"En los apoyos de {tipo} no hay 3ª hipótesis: el 100 % ya está en la 1ª y la 2ª"
            )

        base = self._hipotesis_base()
        V = (
            self.hipotesis_hielo(numero)
            if base == "hielo"
            else self.hipotesis_viento(numero)
        )["V"]
        k = DESEQUILIBRIO[tipo][self.linea.Un > 66]
        T_max = max(self._tension(tramo, base) for tramo, *_ in self._lados(numero))

        if alfa:  # por un lado T_max y por el otro (1 - k)·T_max
            T = n * (2 - k) * T_max * math.sin(math.radians(alfa / 2))
            L = n * k * T_max * math.cos(math.radians(alfa / 2))
        else:
            T, L = None, n * k * T_max
        return {"V": V, "T": T, "L": L, "Mt": None}

    def hipotesis_rotura(self, numero: int) -> dict:
        """4ª hipótesis: rotura del conductor exterior del vano con más tensión.
        Produce un momento torsor Mt = T·brazo. La fase rota sostiene la mitad de su vano, como
        en los ejemplos de clase (en fin de línea, nada)."""
        brazo = self._armado_obligatorio(numero).brazo
        if brazo is None:
            raise ValueError(f"Falta el brazo en el armado del apoyo {numero}")
        tipo, n = self.tipos[numero - 1], self.n_conductores
        base = self._hipotesis_base()
        p = (
            self.conductor.p_total_hielo(self.linea.Zona) if base == "hielo" else self.conductor.p
        )  # peso vertical del conductor

        lados = self._lados(numero)
        tramo_roto, a_roto, *_ = max(
            lados, key=lambda lado: self._tension(lado[0], base)
        )
        a_g_fase_rota = a_roto / 2 if len(lados) == 2 else 0
        V = (
            (n - 1) * p * self.gravivano(numero, base)
            + p * a_g_fase_rota
            + self._peso_cadenas_y_cruceta(numero)
        )
        Mt = ROTURA[tipo] * self._tension(tramo_roto, base) * brazo
        return {"V": V, "T": None, "L": None, "Mt": Mt}

    #  TABLA DE ESFUERZOS PARA ELEGIR EL APOYO

    def _calcula_rotura(self, numero: int) -> bool:
        """Si se calcula la 4ª hipótesis. Por defecto (rotura=None), según ITC-LAT-07 3.5.3: se puede
        omitir en suspensión y amarre si Un <= 66 kV, la carga de rotura del conductor es menor de
        6600 daN y su coeficiente de seguridad es al menos 3"""
        if self.rotura is not None:
            return self.rotura
        if self.tipos[numero - 1] not in ("suspensión", "amarre"):
            return True
        exenta = (
            self.linea.Un <= 66
            and self.conductor.rotura < 6600
            and self.linea.coef >= 3
        )
        return not exenta

    def hipotesis_aplicables(self, numero: int) -> list[str]:
        "Hipótesis que se calculan en el apoyo, según la zona, su tipo y la 4ª hipótesis"
        hipotesis = ["viento"]
        if self.linea.Zona != "A":
            hipotesis.append("hielo")
        if self.tipos[numero - 1] not in TIPOS_SIN_ANGULO:
            hipotesis.append("desequilibrio")
        if self._calcula_rotura(numero):
            hipotesis.append("rotura")
        return hipotesis

    def esfuerzos(self, numero: int) -> pd.DataFrame:
        """Resumen de esfuerzos del apoyo preparado para buscar en las tablas del fabricante.
        Celosía (UNE 207017): T y L juntos se suman en un esfuerzo horizontal, que se da como L.
        Chapa (UNE 207018): T y L se multiplican por el factor_chapa del armado (punto de
        aplicación del fabricante).
        Columnas: hipótesis; filas: V, T, L [daN] y Mt [daN·m]. NaN = no aplica."""
        metodos = {
            "viento": self.hipotesis_viento,
            "hielo": self.hipotesis_hielo,
            "desequilibrio": self.hipotesis_desequilibrio,
            "rotura": self.hipotesis_rotura,
        }
        aplicables = self.hipotesis_aplicables(numero)
        armado = self._armado_obligatorio(numero)
        forma, factor_chapa = armado.forma, armado.factor_chapa

        tabla = {}
        for nombre, columna in zip(metodos, NOMBRES_HIPOTESIS):
            esf = metodos[nombre](numero) if nombre in aplicables else {}
            V, T, L, Mt = (esf.get(e) for e in ("V", "T", "L", "Mt"))
            if forma == "celosía" and T is not None and L is not None:
                T, L = None, T + L
            elif forma == "chapa":
                T = T * factor_chapa if T is not None else None
                L = L * factor_chapa if L is not None else None
            tabla[columna] = {"V": V, "T": T, "L": L, "Mt": Mt}

        return pd.DataFrame(tabla, index=["V", "T", "L", "Mt"], dtype=float)

    #  ESQUEMA

    def _parametro_catenaria(self, i: int) -> float:
        "h = T/p [m] del vano i en la hipótesis de temperatura máxima, para dibujarlo"
        resultados = self.calculo_vano(i).resultados
        fila = resultados[resultados.index.str.startswith("flecha temperatura")].iloc[0]
        return fila["T0_daN"] / fila["p_t_daN_m"]

    def esquema(
        self,
        nombre: str = "esquema_apoyos",
        carpeta: str | Path = "esquemas",
        guardar: bool = True,
        mostrar: bool = True,
    ):
        """Dibuja el perfil de la línea con los apoyos, los vanos y los desniveles.
        Por defecto lo guarda en carpeta/nombre.png, dentro de la carpeta de trabajo (la
        del archivo que ejecutas), creándola si no existe, y lo muestra en pantalla.
        guardar=False: no lo guarda. mostrar=False: no lo muestra y devuelve la figura."""
        import matplotlib.pyplot as plt

        x = np.array(self.posiciones)
        z = np.array(self.cotas)
        largo = x[-1]
        alto = max(15, 0.6 * (z.max() - z.min()))  # altura de dibujo de los apoyos [m]

        y_cota_min = z.min() - 0.55 * alto  # línea de cotas de los vanos
        ancho = 0.018 * largo  # ancho de la base de los apoyos en el dibujo

        fondo = {
            "facecolor": "white",
            "edgecolor": "none",
            "alpha": 0.85,
            "pad": 1.5,
        }  # fondo de los textos

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
            ax.plot(
                xs, yv + (xs - xv) ** 2 / (2 * h), color="#1f4e79", lw=1.4, zorder=2
            )

        for i in range(self.n):
            numero = i + 1
            self._dibujar_apoyo(ax, x[i], z[i], alto, ancho)
            ax.text(
                x[i],
                z[i] + 1.08 * alto,
                str(numero),
                ha="center",
                va="bottom",
                fontsize=11,
                fontweight="bold",
            )
            ax.text(
                x[i],
                z[i] - 0.06 * alto,
                self.etiqueta(numero),
                ha="center",
                va="top",
                fontsize=8,
                zorder=4,
                bbox=fondo,
            )

            # Desnivel respecto al apoyo anterior
            d = self.desniveles[i]
            if i > 0 and d != 0:
                xa = (
                    x[i] - 3.6 * ancho
                )  # a la izquierda del apoyo, sin pisar su etiqueta
                ax.plot(
                    [x[i - 1], xa],
                    [z[i - 1], z[i - 1]],
                    color="0.55",
                    lw=0.8,
                    ls=":",
                    zorder=1,
                )
                ax.annotate(
                    "",
                    xy=(xa, z[i]),
                    xytext=(xa, z[i - 1]),
                    arrowprops={"arrowstyle": "<->", "color": "#b03a2e", "lw": 1},
                )
                ax.text(
                    xa - 0.4 * ancho,
                    (z[i] + z[i - 1]) / 2,
                    f"{d:+g} m".replace("-", "−"),
                    ha="right",
                    va="center",
                    fontsize=9,
                    color="#b03a2e",
                    zorder=4,
                    bbox=fondo,
                )

        # Cotas de los vanos
        for i in range(self.n - 1):
            ax.annotate(
                "",
                xy=(x[i + 1], y_cota_min),
                xytext=(x[i], y_cota_min),
                arrowprops={"arrowstyle": "<->", "color": "0.25", "lw": 1},
            )
            ax.text(
                (x[i] + x[i + 1]) / 2,
                y_cota_min + 0.03 * alto,
                f"{self.vanos[i]:g} m",
                ha="center",
                va="bottom",
                fontsize=9,
            )
        for i in range(self.n):
            ax.plot(
                [x[i], x[i]],
                [y_cota_min - 0.05 * alto, z[i] - 0.45 * alto],
                color="0.6",
                lw=0.6,
                ls="--",
                zorder=1,
            )

        ax.set_xlim(x[0] - 0.06 * largo, x[-1] + 0.06 * largo)
        ax.set_ylim(y_cota_min - 0.2 * alto, z.max() + 1.35 * alto)
        ax.axis("off")
        ax.set_title(
            f"Esquema de la línea: {self.n} apoyos, {largo:g} m "
            "(escala vertical exagerada)",
            fontsize=11,
        )
        fig.tight_layout()

        if guardar:
            carpeta = Path(carpeta)
            carpeta.mkdir(parents=True, exist_ok=True)
            ruta = carpeta / f"{nombre}.png"
            fig.savefig(ruta, dpi=150, bbox_inches="tight")
            print(f"Esquema guardado en {ruta}")
        if mostrar:
            # En la consola interactiva sale debajo del código; ejecutando el archivo en
            # una terminal se abre una ventana y el programa sigue al cerrarla
            plt.show()
            return None  # sin devolver la figura, para que no salga dos veces
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
        ax.plot(
            [x - 1.1 * ancho, x + 1.1 * ancho],
            [y_cruceta, y_cruceta],
            color=color,
            lw=1.6,
            zorder=3,
        )
        ax.plot(
            [izq(y_cruceta), x, der(y_cruceta)],
            [y_cruceta, z + alto, y_cruceta],
            color=color,
            lw=1.2,
            zorder=3,
        )
