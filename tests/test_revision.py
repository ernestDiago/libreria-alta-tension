"""
Tests de los fallos de la revisión de calculoMecanico (revision/revision_calculoMecanico.pdf).

Cada test reproduce un fallo (F1-F12, D2) y comprueba que ya no ocurre.
Los de Conductor (F9 y F10) están en test_conductores.py.
"""

import pandas as pd
import pytest
from conftest import crear_calculo

import alta_tension as at


def uso_de_limites(calc):
    "Cuánto usa cada hipótesis limitante de su límite (1 = justo en el límite)"
    resultados = calc.resolver()
    return {
        nombre: resultados.loc[nombre, "Tmax_daN" if sobre_Tmax else "T0_daN"] / T_lim
        for nombre, _, _, T_lim, sobre_Tmax in calc._hipotesis_limitantes()
    }


# --- F1: con vano > 500 m la dominante superaba su límite


@pytest.mark.parametrize(
    "conductor, linea, vano, desnivel",
    [
        ("LA 56", dict(Un=20, alt=600, Vv=130), 800, 0),
        ("LA 180", dict(Un=132, alt=1200), 900, 0),
        ("LA 78", dict(Un=20, alt=1200), 650, 50),
        ("LA 455 CONDOR", dict(Un=400, alt=800), 1000, 150),
    ],
)
def test_F1_con_catenaria_la_dominante_queda_justo_en_su_limite(conductor, linea, vano, desnivel):
    calc = at.calculoMecanico(at.Conductor(conductor), at.Linea(**linea), vano=vano, desnivel=desnivel)
    uso = uso_de_limites(calc)
    assert max(uso.values()) <= 1 + 1e-9
    assert uso[calc.dominante] == pytest.approx(1, abs=1e-9)


@pytest.mark.parametrize("vano", [300, 600])
@pytest.mark.parametrize("desnivel", [0, 80])
def test_F1_T0_desde_Tmax_es_la_inversa_de_Tmax(vano, desnivel):
    calc = crear_calculo("zonaB_MT_LA56", vano=vano, desnivel=desnivel)
    p = calc.conductor.p_total_hielo("B")
    assert calc._Tmax(calc._T0_desde_Tmax(1200, p), p) == pytest.approx(1200, rel=1e-12)


# --- F2: con desnivel, la flecha saltaba un 13 % al pasar de 500 m


@pytest.mark.parametrize("desnivel", [0, 50, 200])
def test_F2_la_flecha_no_salta_en_500_m(desnivel):
    def flecha(vano):
        cable = at.Conductor("LA 180")
        return at.calculoMecanico(cable, at.Linea(Un=66, alt=300), vano=vano, desnivel=desnivel).flecha_maxima

    # Solo queda la pequeña diferencia entre la parábola y la catenaria (antes, -13,5 % con 200 m)
    assert flecha(500.001) == pytest.approx(flecha(499.999), rel=0.01)


# --- F3: la búsqueda de la dominante devolvía un resultado sin comprobar


def test_F3_si_no_converge_da_error_en_vez_de_un_resultado_malo(monkeypatch):
    calc = crear_calculo("zonaB_MT_LA56")
    monkeypatch.setattr(calc, "_ratio", lambda *args: 2.0)  # todas se pasan siempre
    with pytest.raises(RuntimeError, match="No se ha encontrado la hipótesis que manda"):
        calc.resolver()


# --- F4: un vano inviable daba "math domain error" o un resultado que incumplía el límite


@pytest.mark.parametrize(
    "conductor, linea, vano, desnivel",
    [
        ("LA 30", dict(Un=20, alt=1200), 350, 150),  # parábola: antes "math domain error"
        ("LA 56", dict(Un=66, alt=1200), 700, 0),  # catenaria: antes, hielo al 104,8 %
    ],
)
def test_F4_vano_inviable_da_un_error_claro(conductor, linea, vano, desnivel):
    calc = at.calculoMecanico(at.Conductor(conductor), at.Linea(**linea), vano=vano, desnivel=desnivel)
    with pytest.raises(ValueError, match="Vano inviable.*en hielo la tensión máxima nunca baja de"):
        calc.resolver()


# --- F5: cambiar el cálculo después de crearlo dejaba resultados viejos


def test_F5_cambiar_el_vano_actualiza_la_flecha_maxima():
    calc = crear_calculo("zonaB_MT_LA56")
    antes = calc.flecha_maxima
    calc.vano = 300
    assert calc.flecha_maxima == pytest.approx(crear_calculo("zonaB_MT_LA56", vano=300).flecha_maxima)
    assert calc.flecha_maxima != antes


def test_F5_cambiar_el_desnivel_actualiza_el_vano_real():
    calc = crear_calculo("zonaB_MT_LA56")
    calc.desnivel = 70
    assert calc.vano_real == pytest.approx((170**2 + 70**2) ** 0.5)
    assert calc.con_desnivel


def test_F5_dominante_existe_sin_llamar_a_resolver():
    assert crear_calculo("zonaB_MT_LA56").dominante == "hielo"


# --- F6: cambiar una Linea no actualizaba lo que se deduce de ella


def test_F6_cambiar_la_linea_actualiza_sus_datos():
    linea = at.Linea(Un=20, alt=600)
    linea.alt, linea.Un = 1200, 132
    assert (linea.Zona, linea.categoria, linea.coef) == ("C", "normal", 2.5)
    linea.eds = 0.10
    assert linea.limite_eds == 0.10


def test_F6_un_cambio_invalido_se_detecta_al_calcular():
    calc = crear_calculo("zonaB_MT_LA56")
    calc.linea.eds = 15  # en % en vez de en tanto por uno
    with pytest.raises(ValueError, match="tanto por uno"):
        calc.resolver()


# --- F7: se aceptaban datos imposibles


@pytest.mark.parametrize("vano", [0, -170])
def test_F7_vano_no_positivo(vano):
    with pytest.raises(ValueError, match="vano"):
        crear_calculo("zonaB_MT_LA56", vano=vano)


@pytest.mark.parametrize(
    "dato, mensaje",
    [
        (dict(Un=-20), "Un"),
        (dict(Un=0), "Un"),
        (dict(alt=-600), "alt"),
        (dict(Vv=-200), "Vv"),
        (dict(coef_seguridad=0), "coef_seguridad"),
        (dict(coef_seguridad=-3), "coef_seguridad"),
    ],
)
def test_F7_datos_de_linea_imposibles(dato, mensaje):
    with pytest.raises(ValueError, match=mensaje):
        at.Linea(**{"Un": 20, "alt": 600, **dato})


# --- F8: se aceptaba un coeficiente de seguridad menor que el del reglamento


def test_F8_coeficiente_menor_que_2_5_da_aviso():
    with pytest.warns(UserWarning, match="menor que el mínimo del reglamento"):
        at.Linea(Un=20, alt=300, coef_seguridad=2.0)


# --- F11: exportar_excel y tabla_tendido


def test_F11_tabla_tendido_con_una_sola_temperatura():
    calc = crear_calculo("zonaB_MT_LA56")
    assert list(calc.tabla_tendido(15).index) == [15]


@pytest.mark.parametrize("temperaturas", [None, "15", [0, "a"]])
def test_F11_tabla_tendido_con_temperaturas_raras(temperaturas):
    with pytest.raises(TypeError, match="temperaturas"):
        crear_calculo("zonaB_MT_LA56").tabla_tendido(temperaturas)


def test_F11_exportar_sin_temperaturas_y_con_desnivel(tmp_path):
    calc = crear_calculo("zonaB_MT_LA56", desnivel=30)
    ruta = calc.exportar_excel(tmp_path / "calculo", temperaturas=[])  # sin extensión
    assert ruta.endswith(".xlsx")
    datos = pd.read_excel(ruta, sheet_name="Datos", index_col="Dato")
    assert datos.loc["Desnivel", "Valor"] == 30
    assert datos.loc["Vano real b", "Valor"] == pytest.approx(round((170**2 + 30**2) ** 0.5, 2))


def test_F11_exportar_con_otra_extension_da_error(tmp_path):
    with pytest.raises(ValueError, match="xlsx"):
        crear_calculo("zonaB_MT_LA56").exportar_excel(tmp_path / "calculo.xls")


# --- F12: la temperatura de la flecha máxima era fija


def test_F12_temperatura_de_flecha_maxima_del_enunciado():
    calc = crear_calculo("zonaB_MT_LA56", temperatura_maxima=75)
    resultados = calc.resolver()
    assert "flecha temperatura 75ºC" in resultados.index
    assert calc.flecha_maxima > crear_calculo("zonaB_MT_LA56").flecha_maxima


@pytest.mark.parametrize("Un, minimo", [(20, 50), (220, 85)])
def test_F12_temperatura_menor_que_el_minimo_da_error(Un, minimo):
    with pytest.raises(ValueError, match=f"menor de {minimo}"):
        at.Linea(Un=Un, alt=600, temperatura_maxima=minimo - 5)


# --- D2: por debajo de DESNIVEL_MINIMO el vano se calcula del todo a nivel


def test_D2_desnivel_menor_que_el_minimo_es_exactamente_a_nivel(caso):
    a_nivel = crear_calculo(caso).resolver()
    casi = crear_calculo(caso, desnivel=0.99 * at.DESNIVEL_MINIMO).resolver()
    pd.testing.assert_frame_equal(casi, a_nivel)
