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
    "Caída de tensión aritmética [kV]": 15.28482997,
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


# %% Comparación con la hoja de cálculo


@pytest.mark.parametrize("modelo", MODELOS)
def test_coincide_con_excel(linea_excel, modelo):
    resultado = getattr(linea_excel, modelo)()
    assert resultado == pytest.approx(RESULTADOS_EXCEL, rel=1e-8)


def test_magnitudes_comunes(linea_excel):
    assert linea_excel.Z == pytest.approx(0.96 + 12j)
    assert linea_excel.Y == 0
    assert abs(linea_excel.Ic) == pytest.approx(1082.531755, rel=1e-8)
    assert math.degrees(cmath.phase(linea_excel.Ic)) == pytest.approx(-36.86989765)
    assert linea_excel.Vf == pytest.approx(230940.1077)


# %% Comportamiento físico con susceptancia


def test_inductivo_ignora_la_capacidad(linea_excel, linea_con_b):
    assert linea_con_b.inductivo() == pytest.approx(linea_excel.inductivo())


@pytest.mark.parametrize("modelo", ["T", "pi", "distribuidos"])
def test_la_capacidad_reduce_la_intensidad(linea_excel, linea_con_b, modelo):
    assert getattr(linea_con_b, modelo)()[I0] < linea_excel.inductivo()[I0]


@pytest.mark.parametrize("magnitud", [U0, I0])
def test_distribuidos_queda_entre_T_y_pi(linea_con_b, magnitud):
    t, pi = linea_con_b.T()[magnitud], linea_con_b.pi()[magnitud]
    assert min(t, pi) <= linea_con_b.distribuidos()[magnitud] <= max(t, pi)


# %% Carácter de la carga


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


# %% comparar()


def test_comparar_reune_los_cuatro_modelos(linea_con_b):
    tabla = linea_con_b.comparar()
    assert tabla.shape == (5, 4)
    assert tabla["Modelo en Pi"].to_dict() == pytest.approx(linea_con_b.pi())
