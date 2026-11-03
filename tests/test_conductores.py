"""Tests de los CSV de conductores y de la clase Conductor."""

import numpy as np
import pandas as pd
import pytest

import alta_tension as at

LA = pd.read_csv(at.CARPETA_CONDUCTORES / "conductores_AL1_ST1A.csv", index_col="codigo_antiguo")


# %% Coherencia de las tablas (detecta números mal copiados del tema)


def test_seccion_total_es_aluminio_mas_acero():
    suma = LA.seccion_al_mm2 + LA.seccion_acero_mm2
    assert np.allclose(suma, LA.seccion_total_mm2, atol=0.15)


@pytest.mark.parametrize("zona, k", [("B", 0.18), ("C", 0.36)])
def test_sobrecarga_de_hielo(zona, k):
    p = LA.masa_kg_km * 9.81 / 10000
    ph = k * np.sqrt(LA.d_conductor_mm)
    assert np.allclose(ph, LA[f"p_hielo_{zona}_daN_m"], atol=0.002)
    assert np.allclose(p + ph, LA[f"p_total_hielo_{zona}_daN_m"], atol=0.002)


@pytest.mark.parametrize("columna, velocidad", [("normal", 120), ("cat_especial", 140)])
def test_sobrecarga_de_viento(columna, velocidad):
    p = LA.masa_kg_km * 9.81 / 10000
    q = np.where(LA.d_conductor_mm <= 16, 60, 50) * (velocidad / 120) ** 2
    pv = q * LA.d_conductor_mm / 1000
    assert np.allclose(pv, LA[f"p_viento_{columna}_daN_m"], atol=0.002)
    assert np.allclose(np.hypot(p, pv), LA[f"p_total_viento_{columna}_daN_m"], atol=0.002)


def test_sobrecarga_de_hielo_y_viento_zona_B():
    p = LA.masa_kg_km * 9.81 / 10000
    pv = 50 * (60 / 120) ** 2 * LA.d_manguito_hielo_B_mm / 1000
    assert np.allclose(pv, LA.p_viento_60kmh_daN_m, atol=0.002)
    total = np.hypot(p + LA.p_hielo_B_daN_m, pv)
    assert np.allclose(total, LA.p_total_viento_hielo_B_daN_m, atol=0.002)


@pytest.mark.parametrize("archivo", ["conductores_AL1.csv", "conductores_AL2.csv"])
def test_tablas_homogeneas_completas(archivo):
    tabla = pd.read_csv(at.CARPETA_CONDUCTORES / archivo)
    assert len(tabla) == 12
    assert not tabla.isna().any().any()


# %% Clase Conductor


def test_datos_del_LA56():
    cable = at.Conductor("LA 56")
    assert cable.p == pytest.approx(188.8 * 9.81 / 10000)
    assert cable.d == 9.45
    assert cable.S == 54.6
    assert cable.rotura == pytest.approx(1629)
    assert (cable.E, cable.alfa) == (8100, 19.1e-6)


def test_E_y_alfa_del_enunciado_tienen_prioridad():
    cable = at.Conductor("LA 56", E_dato=7949, alfa_dato=18e-6)
    assert (cable.E, cable.alfa) == (7949, 18e-6)


@pytest.mark.parametrize("nombre", LA.index)
def test_todos_los_LA_tienen_E_y_alfa(nombre):
    cable = at.Conductor(nombre)
    assert cable.E > 0 and cable.alfa > 0


def test_conductor_desconocido_da_error():
    with pytest.raises(KeyError):
        at.Conductor("LA 999")
