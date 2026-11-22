"""Tests de la clase Modelo (modelos eléctricos de líneas)."""

import cmath
import math

import pytest

import alta_tension as at

# Datos de la hoja Lineas_de_Alta_tension.xlsx
DATOS_EXCEL = dict(Pf=600, fp=0.8, Uf=400, L=80, r=0.012, x=0.15, g=0, b=0, caracter="inductivo")

# Resultados de la hoja (iguales en los cuatro modelos porque g = b = 0)
RESULTADOS_EXCEL = {
    "Tensión de línea en el origen [kV]": 415.28482997,
    "Intensidad en el origen [A]": 1082.531755,
    "Potencia activa en el origen [MW]": 603.375,
    "Pérdidas de potencia [MW]": 3.375,
    "Pérdidas respecto a P0 [%]": 0.5593536358,
    "Caída de tensión aritmética [kV]": 15.28482997,
    "Caída de tensión respecto a Uf [%]": 3.821207492,
    "Intensidad de vacío [A]": 0,
}

# Excel corregido por el profesor, con b = 2,7·10⁻⁶ S/km (hoja main). En el Excel, ΔP/P0 y ΔU/Uf
# están en tanto por uno; aquí se multiplican por 100 porque la librería los da en %
EXCEL_CORREGIDO = {
    "inductivo": (415.2848299661324, 1082.5317547305485, 603.375, 3.375,
                  0.5593536357986327, 15.284829966132406, 3.821207491533102, 0),
    "pi": (414.7685548338569, 1051.9766976953915, 603.2834795904, 3.2834795904000202,
           0.5442681096835839, 14.76855483385691, 3.692138708464228, 49.85073910006338),
    "T": (414.7575888330641, 1051.9604268455732, 603.281033865095, 3.281033865094969,
          0.5438649121909359, 14.75758883306412, 3.68939720826603, 49.8830632579836),
    "distribuidos": (414.7613555789937, 1051.9715717971421, 603.281245957274, 3.2812459572739954,
                     0.5438998774224091, 14.761355578993687, 3.690338894748422, 49.86151657921373),
}

MODELOS = ["inductivo", "T", "pi", "distribuidos"]
U0 = "Tensión de línea en el origen [kV]"
I0 = "Intensidad en el origen [A]"


@pytest.fixture
def linea_excel():
    return at.Modelo(**DATOS_EXCEL)


@pytest.fixture
def linea_con_b():
    "La misma línea con susceptancia: los modelos dejan de coincidir"
    return at.Modelo(**{**DATOS_EXCEL, "b": 2.7e-6})


# --- Comparación con la hoja de cálculo


@pytest.mark.parametrize("modelo", MODELOS)
def test_coincide_con_excel(linea_excel, modelo):
    resultado = getattr(linea_excel, modelo)()
    assert resultado == pytest.approx(RESULTADOS_EXCEL, rel=1e-8)


@pytest.mark.parametrize("modelo", EXCEL_CORREGIDO)
def test_coincide_con_excel_corregido(linea_con_b, modelo):
    "Con susceptancia los cuatro modelos dan distinto, y cada uno coincide con el Excel"
    resultado = getattr(linea_con_b, modelo)()
    esperado = dict(zip(RESULTADOS_EXCEL, EXCEL_CORREGIDO[modelo]))
    assert resultado == pytest.approx(esperado, rel=1e-10)


def test_magnitudes_comunes(linea_excel):
    assert linea_excel.Z == pytest.approx(0.96 + 12j)
    assert linea_excel.Y == 0
    assert abs(linea_excel.Ic) == pytest.approx(1082.531755, rel=1e-8)
    assert math.degrees(cmath.phase(linea_excel.Ic)) == pytest.approx(-36.86989765)
    assert linea_excel.Vf == pytest.approx(230940.1077)


# --- Comportamiento físico con susceptancia


def test_inductivo_ignora_la_capacidad(linea_excel, linea_con_b):
    assert linea_con_b.inductivo() == pytest.approx(linea_excel.inductivo())


@pytest.mark.parametrize("modelo", ["T", "pi", "distribuidos"])
def test_la_capacidad_reduce_la_intensidad(linea_excel, linea_con_b, modelo):
    assert getattr(linea_con_b, modelo)()[I0] < linea_excel.inductivo()[I0]


@pytest.mark.parametrize("magnitud", [U0, I0])
def test_distribuidos_queda_entre_T_y_pi(linea_con_b, magnitud):
    t, pi = linea_con_b.T()[magnitud], linea_con_b.pi()[magnitud]
    assert min(t, pi) <= linea_con_b.distribuidos()[magnitud] <= max(t, pi)


# --- Carácter de la carga


@pytest.mark.parametrize("caracter", ["inductivo", "Inductiva", "INDUCTIVO"])
def test_caracter_inductivo_admite_variantes(caracter):
    linea = at.Modelo(**{**DATOS_EXCEL, "caracter": caracter})
    assert linea.inductivo()[U0] == pytest.approx(RESULTADOS_EXCEL[U0])


def test_carga_capacitiva_adelanta_la_corriente():
    linea = at.Modelo(**{**DATOS_EXCEL, "caracter": "capacitivo"})
    assert math.degrees(cmath.phase(linea.Ic)) == pytest.approx(+36.86989765)


def test_carga_capacitiva_necesita_menos_tension(linea_excel):
    capacitiva = at.Modelo(**{**DATOS_EXCEL, "caracter": "capacitivo"})
    assert capacitiva.inductivo()[U0] < linea_excel.inductivo()[U0] - 10


def test_caracter_no_valido_da_error():
    with pytest.raises(ValueError, match="no válido"):
        at.Modelo(**{**DATOS_EXCEL, "caracter": "resistiva"})


# --- comparar()


def test_comparar_reune_los_cuatro_modelos(linea_con_b):
    tabla = linea_con_b.comparar()
    assert tabla.shape == (8, 4)
    assert tabla["Modelo en Pi"].to_dict() == pytest.approx(linea_con_b.pi())
