"""
Tests del vano a desnivel (método del profesor: tensión Tm en el punto medio del vano).

Con un desnivel menor que DESNIVEL_MINIMO, el EDS y el CHS se comprueban con Tm, como
en un vano a nivel. A partir de ese desnivel se comprueban con TB, como hace el profesor.
"""

import pandas as pd
import pytest
from conftest import crear_calculo

import alta_tension as at


@pytest.fixture
def ejercicio():
    "Ejercicio de clase: 20 kV, LA-78, 400 m de altitud, a = 220 m, d = 70 m"
    cable = at.Conductor("LA 78", E_dato=7949, alfa_dato=19.1e-6)
    return at.calculoMecanico(cable, Un=20, alt=400, vano=220, desnivel=70)


# %% Comportamiento general


def test_por_defecto_el_vano_esta_a_nivel():
    assert crear_calculo("zonaB_MT_LA56").desnivel == 0


def test_desnivel_cero_da_lo_mismo_que_a_nivel(caso):
    a_nivel = crear_calculo(caso)
    con_cero = crear_calculo(caso, desnivel=0)
    pd.testing.assert_frame_equal(con_cero.resolver(), a_nivel.resolver())
    pd.testing.assert_frame_equal(con_cero.tabla_tendido(), a_nivel.tabla_tendido())


def test_desnivel_muy_pequeño_casi_no_cambia_nada(caso):
    a_nivel = crear_calculo(caso).resolver()
    casi_a_nivel = crear_calculo(caso, desnivel=0.01).resolver()
    pd.testing.assert_frame_equal(casi_a_nivel, a_nivel, rtol=1e-3)


@pytest.mark.parametrize("signo", [1, -1])
def test_umbral_de_desnivel_para_EDS_y_CHS(signo):
    "Por debajo de DESNIVEL_MINIMO el EDS y el CHS se comprueban con Tm; a partir de él, con TB"
    def sobre_Tmax(desnivel):
        calc = crear_calculo("zonaA_LA110", desnivel=signo * desnivel)
        return {nombre: s for nombre, _, _, _, s in calc._hipotesis_limitantes()}

    justo_debajo = sobre_Tmax(0.99 * at.DESNIVEL_MINIMO)
    en_el_umbral = sobre_Tmax(at.DESNIVEL_MINIMO)
    assert not justo_debajo["EDS"] and not justo_debajo["CHS"]
    assert en_el_umbral["EDS"] and en_el_umbral["CHS"]


def test_da_igual_que_apoyo_sea_el_mas_alto():
    subiendo = crear_calculo("zonaB_MT_LA56", desnivel=25).resolver()
    bajando = crear_calculo("zonaB_MT_LA56", desnivel=-25).resolver()
    pd.testing.assert_frame_equal(subiendo, bajando)


def test_con_desnivel_aumenta_la_tension_en_el_apoyo_alto():
    a_nivel = crear_calculo("zonaB_MT_LA56")
    con_desnivel = crear_calculo("zonaB_MT_LA56", desnivel=25)
    p = a_nivel.conductor.p
    assert con_desnivel._Tmax(300, p) > a_nivel._Tmax(300, p)


# %% Ejercicio de clase "Cálculo mecánico de vano desnivelado"


def test_ejercicio_vano_real(ejercicio):
    assert ejercicio.vano_real == pytest.approx(230.87, abs=0.01)


def test_ejercicio_Tm_desde_TB(ejercicio):
    "Con TB = rotura/3 = 771 daN y p = 0,73 daN/m (valores redondeados del ejercicio)"
    assert ejercicio._T0_desde_Tmax(771, 0.73) == pytest.approx(740.66, abs=0.01)


def test_ejercicio_manda_el_viento_con_TB_en_el_limite(ejercicio):
    resultados = ejercicio.resolver()
    assert ejercicio.dominante == "viento"
    assert resultados.loc["viento", "Tmax_daN"] == pytest.approx(2312 / 3)


def test_ejercicio_EDS_y_CHS_se_comprueban_con_TB(ejercicio):
    "Con desnivel, el límite del EDS y del CHS se aplica en el apoyo alto (punto B)"
    sobre_Tmax = {nombre: s for nombre, _, _, _, s in ejercicio._hipotesis_limitantes()}
    assert sobre_Tmax["EDS"] and sobre_Tmax["CHS"]
