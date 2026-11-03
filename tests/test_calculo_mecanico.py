"""Tests de la clase calculoMecanico (vano a nivel)."""

import pandas as pd
import pytest
from conftest import CARPETA_REFERENCIAS, crear_calculo

import alta_tension as at

# %% Datos derivados de la línea


@pytest.mark.parametrize(
    "altitud, zona", [(0, "A"), (499.9, "A"), (500, "B"), (1000, "B"), (1000.1, "C")]
)
def test_zona_segun_altitud(altitud, zona):
    assert crear_calculo("zonaA_LA110", alt=altitud).Zona == zona


@pytest.mark.parametrize("Un, categoria", [(20, "normal"), (132, "normal"), (220, "especial"), (400, "especial")])
def test_categoria_segun_tension(Un, categoria):
    assert crear_calculo("zonaA_LA110", Un=Un).categoria == categoria


@pytest.mark.parametrize("Un, coef", [(15, 3), (20, 3), (66, 2.5), (400, 2.5)])
def test_coeficiente_de_seguridad(Un, coef):
    assert crear_calculo("zonaA_LA110", Un=Un).coef == coef


def test_coeficiente_de_seguridad_del_enunciado():
    assert crear_calculo("zonaA_LA110", coef_seguridad=3.5).coef == 3.5


@pytest.mark.parametrize(
    "Un, Vv, excepcional",
    [(66, None, None), (66, 110, None), (66, 130, 130), (220, 130, None), (220, 150, 150)],
)
def test_viento_excepcional(Un, Vv, excepcional):
    assert crear_calculo("zonaA_LA110", Un=Un, Vv=Vv).v_excepcional == excepcional


# %% Ejemplos resueltos del Tema 9


def test_tema9_ejemplo1_flecha():
    "LA 110 en un vano de 120 m con T = 800 daN -> f = 0,954 m"
    calc = at.calculoMecanico(at.Conductor("LA 110"), Un=66, alt=300, vano=120)
    assert calc._flecha(800, calc.conductor.p) == pytest.approx(0.954, abs=0.001)


def test_tema9_ejemplo2_tension():
    "LA 56 en un vano de 120 m con f = 1,2 m -> T0 = 277,8 daN y Tmax = 278 daN"
    calc = at.calculoMecanico(at.Conductor("LA 56"), Un=66, alt=300, vano=120)
    p = calc.conductor.p
    assert calc._flecha(277.8, p) == pytest.approx(1.2, abs=0.001)
    assert calc._Tmax(277.8, p) == pytest.approx(278, abs=0.05)


def test_tema9_ejemplo3_sobrecargas():
    "LA 78 a 700 m de altitud (zona B), línea de 2ª categoría"
    calc = at.calculoMecanico(at.Conductor("LA 78"), Un=66, alt=700, vano=100)
    assert calc._pv() == pytest.approx(0.678, abs=0.001)          # a) viento
    assert calc._p_viento() == pytest.approx(0.728, abs=0.001)
    assert calc._p_hielo() == pytest.approx(0.871, abs=0.001)     # b) hielo
    assert calc._pv(160) == pytest.approx(1.205, abs=0.001)       # c) viento de 160 km/h
    assert calc._p_viento(160) == pytest.approx(1.234, abs=0.001)


# %% Ejemplo de clase "Cálculo mecánico de un vano a nivel"

# Hipótesis: (T0 [daN], flecha [m]) del ejemplo resuelto en clase
EJEMPLO_CLASE = {
    "EDS": (146.88, 4.55),
    "viento": (447.72, 4.80),
    "CHS": (162.16, 4.10),
    "viento excepcional": (503.4, 4.95),
    "hielo": (539.34, 4.95),
    "flecha viento 15ºC": (411.68, 5.23),
    "flecha temperatura 50ºC": (127.76, 5.24),
    "flecha hielo 0ºC": (515, 5.18),
    "flecha mínima": (172, 3.89),
    "desviación cadena": (281.2, 4.35),
}


def test_ejemplo_de_clase():
    "El ejemplo redondea t2 a dos decimales: diferencias de hasta 1 daN y 0,05 m"
    calc = crear_calculo("zonaB_MT_LA56")
    resultados = calc.resolver()
    assert calc.dominante == "hielo"
    for hipotesis, (T0, flecha) in EJEMPLO_CLASE.items():
        assert resultados.loc[hipotesis, "T0_daN"] == pytest.approx(T0, abs=1.0), hipotesis
        assert resultados.loc[hipotesis, "flecha_m"] == pytest.approx(flecha, abs=0.05), hipotesis


# %% Ecuaciones


def test_cambio_de_condiciones_ida_y_vuelta():
    calc = crear_calculo("zonaB_MT_LA56")
    p = calc.conductor.p
    T2 = calc._cambio_condiciones(500, -15, 0.739, 15, p)
    assert calc._cambio_condiciones(T2, 15, p, -15, 0.739) == pytest.approx(500, rel=1e-9)


def test_cambio_de_condiciones_sin_cambios():
    calc = crear_calculo("zonaB_MT_LA56")
    p = calc.conductor.p
    assert calc._cambio_condiciones(300, 10, p, 10, p) == pytest.approx(300, rel=1e-9)


def test_con_calor_baja_la_tension():
    calc = crear_calculo("zonaB_MT_LA56")
    p = calc.conductor.p
    assert calc._cambio_condiciones(300, 15, p, 40, p) < 300 < calc._cambio_condiciones(300, 15, p, -10, p)


def test_T0_desde_Tmax_es_la_inversa_de_Tmax():
    calc = crear_calculo("zonaB_MT_LA56")
    Tmax = calc._Tmax(300, 0.739)
    assert calc._T0_desde_Tmax(Tmax, 0.739) == pytest.approx(300, rel=1e-9)


def test_parabola_en_vanos_cortos_y_catenaria_en_largos():
    corto = crear_calculo("zonaB_MT_LA56")                    # 170 m
    largo = crear_calculo("zonaB_especial_catenaria_GULL")    # 600 m
    p = 1.0
    assert corto._flecha(1000, p) == corto._flecha_aprox(1000, p)
    assert corto._flecha_exacta(1000, p) == pytest.approx(corto._flecha_aprox(1000, p), rel=1e-3)
    assert largo._flecha(1000, p) == largo._flecha_exacta(1000, p)
    assert largo._flecha_exacta(1000, p) > largo._flecha_aprox(1000, p)


# %% Propiedades que se cumplen en todos los escenarios

LIMITE_SOBRE_T0 = {"EDS", "CHS"}   # en el resto el límite se aplica a Tmax


def _porcentaje_usado(calc, resultados):
    "Porcentaje de rotura que usa cada hipótesis limitante, comparable con limite_%"
    limitantes = resultados.dropna(subset=["limite_%"])
    R = calc.conductor.rotura
    return {
        nombre: fila["%_rotura"] if nombre in LIMITE_SOBRE_T0 else 100 * fila["Tmax_daN"] / R
        for nombre, fila in limitantes.iterrows()
    }


def test_ninguna_hipotesis_supera_su_limite(caso):
    calc = crear_calculo(caso)
    resultados = calc.resolver()
    for nombre, usado in _porcentaje_usado(calc, resultados).items():
        assert usado <= resultados.loc[nombre, "limite_%"] + 1e-6, nombre


def test_la_hipotesis_dominante_esta_en_su_limite(caso):
    calc = crear_calculo(caso)
    resultados = calc.resolver()
    usado = _porcentaje_usado(calc, resultados)[calc.dominante]
    assert usado == pytest.approx(resultados.loc[calc.dominante, "limite_%"])


def test_tabla_de_tendido(caso):
    tendido = crear_calculo(caso).tabla_tendido()
    assert tendido.T_daN.is_monotonic_decreasing       # con calor el cable se destensa
    assert tendido.flecha_m.is_monotonic_increasing    # y cuelga más


def test_flecha_maxima_supera_a_la_de_tendido(caso):
    calc = crear_calculo(caso)
    assert calc.flecha_maxima >= calc.tabla_tendido().flecha_m.max()


# %% Regresión: los resultados no deben cambiar sin querer
# Si un cambio es intencionado, regenera las referencias con: python tests/generar_referencias.py


def test_regresion_hipotesis(caso):
    esperado = pd.read_csv(CARPETA_REFERENCIAS / f"{caso}_hipotesis.csv", index_col="hipotesis")
    pd.testing.assert_frame_equal(crear_calculo(caso).resolver(), esperado, check_dtype=False, rtol=1e-9)


def test_regresion_tabla_tendido(caso):
    esperado = pd.read_csv(CARPETA_REFERENCIAS / f"{caso}_tendido.csv", index_col="temp_C")
    pd.testing.assert_frame_equal(crear_calculo(caso).tabla_tendido(), esperado, check_dtype=False, rtol=1e-9)
