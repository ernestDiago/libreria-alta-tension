"""Tests de los CSV de conductores y de la clase Conductor."""

import numpy as np
import pandas as pd
import pytest

import alta_tension as at

LA = pd.read_csv(at.CARPETA_CONDUCTORES / "conductores_AL1_ST1A.csv", index_col="codigo_antiguo")


# --- Coherencia de las tablas (detecta números mal copiados del tema)


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


# --- Clase Conductor


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


def test_conductor_desconocido_da_error_con_la_lista():
    with pytest.raises(ValueError, match="no encontrado.*Disponibles: LA 30, LA 56"):
        at.Conductor("LA 999")


@pytest.mark.parametrize("escrito", ["la 56", "LA  56", " LA 56 "])
def test_nombre_del_conductor_flexible(escrito):
    assert at.Conductor(escrito).S == 54.6


def test_nombre_sin_la_palabra_final():
    cable = at.Conductor("LA 280")
    assert cable.nombre == "LA 280 HAWK"
    assert cable.resumen().startswith("Conductor LA 280 HAWK")


@pytest.mark.parametrize("archivo, nombre", [("conductores_AL1.csv", "L 56"), ("conductores_AL2.csv", "D 56")])
def test_conductores_homogeneos(archivo, nombre):
    ruta = str(at.CARPETA_CONDUCTORES / archivo)
    with pytest.raises(ValueError, match="homogéneo"):  # sin E ni α típicos hay que darlos
        at.Conductor(nombre, archivo=ruta)
    cable = at.Conductor(nombre, archivo=ruta, E_dato=6000, alfa_dato=23e-6)
    tabla = pd.read_csv(ruta, index_col="codigo_antiguo")
    assert cable.S == tabla.loc[nombre, "seccion_mm2"]
    assert "homogéneo" in cable.resumen()
    calc = at.calculoMecanico(cable, at.Linea(Un=20, alt=700), vano=150)
    assert calc.dominante in calc.resolver().index


@pytest.mark.parametrize("E", [0, -7000])
def test_E_no_positivo_da_error(E):
    with pytest.raises(ValueError, match="E_dato"):
        at.Conductor("LA 56", E_dato=E)


def test_cambiar_el_conductor_actualiza_los_datos():
    cable = at.Conductor("LA 56")
    cable.conductor = "LA 110"
    assert cable.S == 116.2
    cable.E_dato = 7000
    assert cable.E == 7000



# --- Sobrecargas del conductor


def test_tema9_ejemplo3_sobrecargas():
    "LA 78 a 700 m de altitud (zona B), línea de 2ª categoría"
    cable = at.Conductor("LA 78")
    assert cable.sobrecarga_viento(120) == pytest.approx(0.678, abs=0.001)  # a) viento
    assert cable.p_total_viento(120) == pytest.approx(0.728, abs=0.001)
    assert cable.p_total_hielo("B") == pytest.approx(0.871, abs=0.001)  # b) hielo
    assert cable.sobrecarga_viento(160) == pytest.approx(1.205, abs=0.001)  # c) viento de 160 km/h
    assert cable.p_total_viento(160) == pytest.approx(1.234, abs=0.001)


@pytest.mark.parametrize("nombre", LA.index)
def test_sobrecargas_coinciden_con_la_tabla(nombre):
    cable = at.Conductor(nombre)
    fila = LA.loc[nombre]
    assert cable.sobrecarga_viento(120) == pytest.approx(fila.p_viento_normal_daN_m, abs=0.002)
    assert cable.sobrecarga_viento(140) == pytest.approx(fila.p_viento_cat_especial_daN_m, abs=0.002)
    assert cable.p_total_viento(120) == pytest.approx(fila.p_total_viento_normal_daN_m, abs=0.002)
    assert cable.p_total_hielo("B") == pytest.approx(fila.p_total_hielo_B_daN_m, abs=0.002)
    assert cable.p_total_hielo("C") == pytest.approx(fila.p_total_hielo_C_daN_m, abs=0.002)
    assert cable.p_total_hielo_viento("B") == pytest.approx(fila.p_total_viento_hielo_B_daN_m, abs=0.002)


def test_presion_del_viento_segun_diametro():
    cable = at.Conductor("LA 56")
    assert cable.presion_viento(120, d=16) == 60
    assert cable.presion_viento(120, d=16.1) == 50
    assert cable.presion_viento(60, d=10) == 15


def test_sobrecargas_en_zona_A():
    cable = at.Conductor("LA 56")
    assert cable.sobrecarga_hielo("A") == 0
    assert cable.p_total_hielo("A") == cable.p
    with pytest.raises(ValueError, match="zonas B y C"):
        cable.p_total_hielo_viento("A")


def test_zona_desconocida_da_error():
    with pytest.raises(ValueError, match="Zona 'D'"):
        at.Conductor("LA 56").p_total_hielo("D")


def test_mitad_de_presion_para_la_desviacion_de_cadenas():
    cable = at.Conductor("LA 110")
    pv = cable.sobrecarga_viento(120)
    assert cable.p_total_viento(120, factor=0.5) == pytest.approx((cable.p**2 + (pv / 2) ** 2) ** 0.5)


def test_resumen_del_conductor():
    resumen = at.Conductor("LA 56", E_dato=7949).resumen()
    assert resumen.startswith("Conductor LA 56 (47-AL1/8-ST1A)")
    for texto in ["6 + 1 alambres", "54.6 mm²", "1629 daN", "7949 daN/mm²  (del enunciado)",
                  "19.1·10⁻⁶ 1/ºC  (típico según composición)", "0.553 / 1.107 daN/m"]:
        assert texto in resumen, texto
