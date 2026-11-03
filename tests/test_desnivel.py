"""
Tests del vano a desnivel (PENDIENTE DE IMPLEMENTAR).

Describen cómo debe comportarse calculoMecanico con el nuevo dato `desnivel` [m].
Mientras no exista, pytest los marca como "xfail" (fallo esperado).

Cuando lo implementes y pasen, pytest dará error a propósito (strict=True):
es el aviso para borrar la línea `pytestmark = ...` y que pasen a ser tests normales.

Faltan los tests con valores numéricos: añádelos con un ejemplo resuelto en clase.
"""

import pandas as pd
import pytest
from conftest import crear_calculo

pytestmark = pytest.mark.xfail(reason="vano a desnivel aún no implementado", strict=True)


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


def test_da_igual_que_apoyo_sea_el_mas_alto():
    subiendo = crear_calculo("zonaB_MT_LA56", desnivel=25).resolver()
    bajando = crear_calculo("zonaB_MT_LA56", desnivel=-25).resolver()
    pd.testing.assert_frame_equal(subiendo, bajando)


def test_con_desnivel_aumenta_la_tension_en_el_apoyo_alto():
    a_nivel = crear_calculo("zonaB_MT_LA56")
    con_desnivel = crear_calculo("zonaB_MT_LA56", desnivel=25)
    p = a_nivel.conductor.p
    assert con_desnivel._Tmax(300, p) > a_nivel._Tmax(300, p)
