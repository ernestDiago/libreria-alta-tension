"""Tests de la clase CalculoApoyos (datos de la línea y esquema)."""

import matplotlib.pyplot as plt
import pandas as pd
import pytest

import alta_tension as at

# Ejercicio de evaluación continua: cruce de un valle con LA-180 a 600 m de altitud
DATOS_EJERCICIO = {
    "vanos": [210, 270, 270, 240],
    "desniveles": [0, 5, -20, 20, 20],
    "tipos": ["Fin de línea", "AMARRE", "anclaje", "amarre", "fin de linea"],
    "angulos": {4: 45},
}


@pytest.fixture(scope="module")
def cable():
    return at.Conductor("LA 180", E_dato=8000, alfa_dato=17.8e-6)


@pytest.fixture
def apoyos(cable):
    return at.CalculoApoyos(cable, Un=20, alt=600, **DATOS_EJERCICIO)


# --- Datos de la línea


def test_tipos_escritos_de_cualquier_forma(apoyos):
    assert apoyos.tipos == ["fin de línea", "amarre", "anclaje", "amarre", "fin de línea"]


def test_geometria(apoyos):
    assert apoyos.n == 5
    assert apoyos.posiciones == [0, 210, 480, 750, 990]
    assert apoyos.cotas == [0, 5, -15, 5, 25]   # cada desnivel es respecto al apoyo anterior


def test_funcion_y_etiqueta(apoyos):
    assert apoyos.funcion(1) is None
    assert apoyos.funcion(3) == "alineación"
    assert apoyos.funcion(4) == "ángulo"
    assert apoyos.etiqueta(3) == "ANCLAJE\nALINEACIÓN"
    assert apoyos.etiqueta(4) == "AMARRE\nÁNGULO 45º"
    assert apoyos.etiqueta(5) == "FIN DE LÍNEA"


# --- Datos mal introducidos


@pytest.mark.parametrize(
    "cambio, mensaje",
    [
        ({"vanos": [210, 270, 270]}, "4 vanos"),
        ({"desniveles": [0, 5, -20, 20]}, "desniveles"),
        ({"desniveles": [3, 5, -20, 20, 20]}, "primer apoyo"),
        ({"tipos": ["fin de línea", "amarre", "torre", "amarre", "fin de línea"]}, "desconocido"),
        ({"angulos": {5: 30}}, "no puede ser de ángulo"),
        ({"angulos": {7: 30}}, "solo hay apoyos"),
        ({"angulos": {4: 200}}, "entre 0º y 180º"),
    ],
)
def test_datos_incorrectos_dan_error(cable, cambio, mensaje):
    with pytest.raises(ValueError, match=mensaje):
        at.CalculoApoyos(cable, Un=20, alt=600, **{**DATOS_EJERCICIO, **cambio})


# --- Cálculo del conductor de cada vano


def test_cada_vano_usa_su_longitud_y_su_desnivel(apoyos):
    for i, (vano, desnivel) in enumerate([(210, 5), (270, -20), (270, 20), (240, 20)]):
        calc = apoyos.calculo_vano(i)
        assert (calc.vano, calc.desnivel) == (vano, desnivel)
        assert (calc.Un, calc.alt) == (20, 600)


def test_los_datos_de_la_linea_pasan_a_cada_vano(cable):
    apoyos = at.CalculoApoyos(cable, Un=20, alt=600, eds=0.165, chs=None, **DATOS_EJERCICIO)
    calc = apoyos.calculo_vano(1)
    assert calc.limite_eds == 0.165
    assert calc.chs is None


# --- Cantones


def test_sin_suspensiones_cada_vano_es_un_canton(apoyos):
    assert [(c.inicio, c.fin) for c in apoyos.cantones] == [(1, 2), (2, 3), (3, 4), (4, 5)]
    assert [c.vano_regulacion for c in apoyos.cantones] == [210, 270, 270, 240]


# Ejemplo SJR005: LA-110, 1200 m, EDS 8,7 %, CHS 15,9 %, con suspensiones en 2, 4 y 6
SJR005 = {
    "vanos": [160, 150, 145, 140, 150, 160],
    "desniveles": [0, 0, 0, 5, 10, -10, 15],
    "tipos": ["fin de línea", "suspensión", "anclaje", "suspensión", "amarre", "suspensión",
              "fin de línea"],
    "angulos": {5: 30},
}


@pytest.fixture(scope="module")
def apoyos_SJR005():
    cable = at.Conductor("LA 110", E_dato=8047, alfa_dato=17.8e-6)
    return at.CalculoApoyos(cable, Un=20, alt=1200, eds=0.087, chs=0.159, **SJR005)


def test_cantones_SJR005(apoyos_SJR005):
    cantones = apoyos_SJR005.cantones
    assert [(c.inicio, c.fin) for c in cantones] == [(1, 3), (3, 5), (5, 7)]
    assert [c.tramos for c in cantones] == [["1-2", "2-3"], ["3-4", "4-5"], ["5-6", "6-7"]]
    assert [c.vano_regulacion for c in cantones] == pytest.approx([155.2, 142.6, 155.2], abs=0.05)
    assert [c.desnivel for c in cantones] == [0, 10, 15]   # el mayor de cada cantón


def test_los_vanos_de_un_canton_comparten_calculo(apoyos_SJR005):
    assert apoyos_SJR005.calculo_vano(0) is apoyos_SJR005.calculo_vano(1)
    assert apoyos_SJR005.calculo_vano(1) is not apoyos_SJR005.calculo_vano(2)


def test_tensiones_calculadas_SJR005(apoyos_SJR005):
    "Tabla de tensiones del PDF: (hielo -20 ºC, viento -15 ºC, viento mitad -15 ºC) [daN]"
    pdf = {"1-2": (1354, 840, 598), "3-4": (1329, 838, 607), "6-7": (1346, 833, 592)}
    tensiones = apoyos_SJR005.tensiones
    assert apoyos_SJR005.tensiones_calculadas
    assert list(tensiones.index) == ["1-2", "2-3", "3-4", "4-5", "5-6", "6-7"]
    for tramo, valores in pdf.items():
        calculado = tensiones.loc[tramo, ["hielo", "viento", "desviación cadena"]]
        assert list(calculado) == pytest.approx(valores, rel=0.01), tramo


# --- Hipótesis de cálculo de los apoyos (resolución del SJR005)

# Tensiones del resumen del cálculo del conductor del PDF y pesos de sus cadenas y crucetas
TENSIONES_SJR005 = pd.DataFrame(
    {"hielo": [1354, 1354, 1329, 1329, 1346, 1346], "viento": [840, 840, 838, 838, 833, 833]},
    index=["1-2", "2-3", "3-4", "4-5", "5-6", "6-7"],
)
PESOS_SJR005 = {
    "peso_cadena_amarre": 10 + 2,
    "peso_cadena_suspension": 8 + 1,
    "peso_cruceta": 70,  # recta
    "peso_cruceta_suspension": 56,  # bóveda
    "brazo_cruceta": 1.75,
}


@pytest.fixture(scope="module")
def apoyos_SJR005_resuelto():
    cable = at.Conductor("LA 110", E_dato=8047, alfa_dato=17.8e-6)
    return at.CalculoApoyos(cable, Un=20, alt=1200, tensiones=TENSIONES_SJR005, **SJR005, **PESOS_SJR005)


# (apoyo, hipótesis, esfuerzo) -> valor del PDF. En los apoyos de chapa (2, 4 y 6), T y L antes de
# reducirlos al punto del fabricante (dividiendo por 1,286 los que da el PDF ya reducidos)
RESULTADOS_SJR005 = {
    (1, "viento", "V"): 208, (1, "viento", "T"): 201.6, (1, "viento", "L"): 2520,
    (1, "hielo", "V"): 531.2, (1, "hielo", "L"): 4062,
    (1, "rotura", "V"): 389.5, (1, "rotura", "Mt"): 2369.5,
    (2, "viento", "V"): 280.6, (2, "viento", "T"): 390.6, (2, "hielo", "V"): 907,
    (2, "desequilibrio", "V"): 907, (2, "desequilibrio", "L"): 325,
    (3, "viento", "V"): 290.9, (3, "viento", "T"): 371.7, (3, "hielo", "V"): 788.4,
    (3, "desequilibrio", "L"): 2031, (3, "rotura", "V"): 705.9, (3, "rotura", "Mt"): 2369.5,
    (4, "viento", "V"): 222.7, (4, "viento", "T"): 359.1,
    (4, "desequilibrio", "V"): 693.3, (4, "desequilibrio", "L"): 319.0,
    (5, "viento", "V"): 483.2, (5, "viento", "T"): 1650.4, (5, "hielo", "V"): 1466.7,
    (5, "hielo", "T"): 2077, (5, "desequilibrio", "T"): 1933.5, (5, "desequilibrio", "L"): 585,
    (6, "viento", "V"): 99.6, (6, "viento", "T"): 390.6,
    (6, "desequilibrio", "V"): 259, (6, "desequilibrio", "L"): 323.0,
    (7, "viento", "V"): 313.8, (7, "viento", "T"): 201.6, (7, "viento", "L"): 2499,
    (7, "hielo", "V"): 909.8, (7, "hielo", "L"): 4038,
    (7, "rotura", "V"): 641.9, (7, "rotura", "Mt"): 2355.5,
}


@pytest.mark.parametrize("clave", RESULTADOS_SJR005, ids=lambda c: f"apoyo{c[0]}-{c[1]}-{c[2]}")
def test_hipotesis_SJR005(apoyos_SJR005_resuelto, clave):
    "El PDF redondea el peso del conductor a 0,425 daN/m: diferencias de hasta el 0,5 %"
    numero, hipotesis, esfuerzo = clave
    resultado = getattr(apoyos_SJR005_resuelto, f"hipotesis_{hipotesis}")(numero)
    assert resultado[esfuerzo] == pytest.approx(RESULTADOS_SJR005[clave], rel=0.005)


def test_gravivano_y_eolovano_SJR005(apoyos_SJR005_resuelto):
    "Apoyo 3 (entre vanos a distinto nivel) y apoyo 5"
    assert apoyos_SJR005_resuelto.eolovano(3) == 147.5
    assert apoyos_SJR005_resuelto.gravivano(3, "viento") == pytest.approx(116.8, abs=0.1)
    assert apoyos_SJR005_resuelto.gravivano(3, "hielo") == pytest.approx(121.6, abs=0.1)
    assert apoyos_SJR005_resuelto.gravivano(5, "viento") == pytest.approx(267.6, abs=0.1)
    assert apoyos_SJR005_resuelto.gravivano(5, "hielo") == pytest.approx(249.2, abs=0.1)


def test_hipotesis_que_no_existen(apoyos_SJR005_resuelto, cable):
    with pytest.raises(ValueError, match="no hay 3ª hipótesis"):
        apoyos_SJR005_resuelto.hipotesis_desequilibrio(1)   # fin de línea
    en_zona_A = at.CalculoApoyos(cable, Un=20, alt=300, **DATOS_EJERCICIO, **PESOS_SJR005)
    with pytest.raises(ValueError, match="zona A"):
        en_zona_A.hipotesis_hielo(3)


def test_datos_que_faltan_en_las_hipotesis(cable):
    sin_pesos = at.CalculoApoyos(cable, Un=20, alt=600, tensiones=TENSIONES_ENUNCIADO, **DATOS_EJERCICIO)
    with pytest.raises(ValueError, match="peso_cadena_amarre"):
        sin_pesos.hipotesis_viento(3)
    with pytest.raises(ValueError, match="brazo_cruceta"):
        sin_pesos.hipotesis_rotura(3)
    con_pesos = at.CalculoApoyos(cable, Un=20, alt=600, tensiones=TENSIONES_ENUNCIADO,
                                 **DATOS_EJERCICIO, **PESOS_SJR005)
    with pytest.raises(ValueError, match="tramo 1-2"):   # el enunciado no da el vano 1-2
        con_pesos.hipotesis_viento(2)


# --- Tabla de esfuerzos para elegir el apoyo (resúmenes del SJR005)

NAN = float("nan")

# Apoyo -> filas V, T, L, Mt con las columnas 1ª, 2ª, 3ª y 4ª del "RESUMEN DE ESFUERZOS" del PDF.
# Celosía: T + L juntos van como L. Chapa (2, 4 y 6): T y L reducidos con el factor 1,286
RESUMENES_SJR005 = {
    1: [[208, 531.2, NAN, 389.5], [NAN] * 4, [2721.6, 4062, NAN, NAN], [NAN, NAN, NAN, 2369.5]],
    2: [[280.6, 907, 907, NAN], [502.3, NAN, NAN, NAN], [NAN, NAN, 418, NAN], [NAN] * 4],
    3: [[290.9, 788.4, 788.4, 705.9], [371.7, NAN, NAN, NAN], [NAN, NAN, 2031, NAN],
        [NAN, NAN, NAN, 2369.5]],
    4: [[222.7, 693.3, 693.3, NAN], [461.8, NAN, NAN, NAN], [NAN, NAN, 410.2, NAN], [NAN] * 4],
    5: [[483.2, 1466.7, 1466.7, NAN], [1650.4, 2077, NAN, NAN], [NAN, NAN, 2518.5, NAN], [NAN] * 4],
    6: [[99.6, 259, 259, NAN], [502.3, NAN, NAN, NAN], [NAN, NAN, 415.4, NAN], [NAN] * 4],
    7: [[313.8, 909.8, NAN, 641.9], [NAN] * 4, [2700.6, 4038, NAN, NAN], [NAN, NAN, NAN, 2355.5]],
}


@pytest.fixture(scope="module")
def apoyos_SJR005_con_formas():
    cable = at.Conductor("LA 110", E_dato=8047, alfa_dato=17.8e-6)
    return at.CalculoApoyos(
        cable, Un=20, alt=1200, tensiones=TENSIONES_SJR005, **SJR005, **PESOS_SJR005,
        formas=["celosía", "chapa", "celosía", "chapa", "celosía", "chapa", "celosía"],
        factor_chapa=at.factor_reduccion_chapa(b=1.365, c=0.985),   # cruceta de bóveda
    )


def test_factor_reduccion_chapa():
    assert at.factor_reduccion_chapa(b=1.365, c=0.985) == pytest.approx(1.286, abs=0.001)


@pytest.mark.parametrize("numero", RESUMENES_SJR005)
def test_resumen_de_esfuerzos_SJR005(apoyos_SJR005_con_formas, numero):
    "Mismos huecos (NaN = no aplica) y mismos valores que el PDF, salvo el redondeo de p (0,5 %)"
    esperado = pd.DataFrame(RESUMENES_SJR005[numero], index=["V", "T", "L", "Mt"],
                            columns=list(at.NOMBRES_HIPOTESIS))
    pd.testing.assert_frame_equal(apoyos_SJR005_con_formas.esfuerzos(numero), esperado,
                                  check_exact=False, rtol=0.005)


def test_hipotesis_aplicables_ejercicio(cable):
    "LA-180 (rotura 6494 daN) a 20 kV con coeficiente 3: se omite la 4ª en amarre, no en anclaje"
    apoyos = at.CalculoApoyos(cable, Un=20, alt=600, **DATOS_EJERCICIO)
    assert apoyos.hipotesis_aplicables(3) == ["viento", "hielo", "desequilibrio", "rotura"]   # anclaje
    assert apoyos.hipotesis_aplicables(4) == ["viento", "hielo", "desequilibrio"]             # amarre
    assert apoyos.hipotesis_aplicables(5) == ["viento", "hielo", "rotura"]                    # fin de línea


def test_hipotesis_aplicables_segun_datos(cable):
    forzada = at.CalculoApoyos(cable, Un=20, alt=600, rotura=True, **DATOS_EJERCICIO)
    assert "rotura" in forzada.hipotesis_aplicables(4)
    a_132_kV = at.CalculoApoyos(cable, Un=132, alt=600, **DATOS_EJERCICIO)   # > 66 kV: no se omite
    assert "rotura" in a_132_kV.hipotesis_aplicables(4)
    en_zona_A = at.CalculoApoyos(cable, Un=20, alt=300, **DATOS_EJERCICIO)
    assert "hielo" not in en_zona_A.hipotesis_aplicables(3)


@pytest.mark.parametrize("formas, mensaje", [(["celosía"] * 3, "formas constructivas"),
                                             ("hormigón", "desconocida")])
def test_formas_incorrectas(cable, formas, mensaje):
    with pytest.raises(ValueError, match=mensaje):
        at.CalculoApoyos(cable, Un=20, alt=600, formas=formas, **DATOS_EJERCICIO)


# --- Tensiones del enunciado

TENSIONES_ENUNCIADO = pd.DataFrame(
    {"hielo": [2107, 2107, 2116], "viento": [1747, 1747, 1758]}, index=["2-3", "3-4", "4-5"]
)


def test_tensiones_del_enunciado_tienen_prioridad(cable):
    apoyos = at.CalculoApoyos(cable, Un=20, alt=600, tensiones=TENSIONES_ENUNCIADO,
                              **DATOS_EJERCICIO)
    assert not apoyos.tensiones_calculadas
    assert list(apoyos.tensiones.index) == ["1-2", "2-3", "3-4", "4-5"]   # ordenada por tramos
    assert pd.isna(apoyos.tensiones.loc["1-2", "hielo"])                  # el que no se da queda vacío
    assert apoyos.tensiones.loc["4-5", "viento"] == 1758


@pytest.mark.parametrize(
    "tabla, mensaje",
    [
        (pd.DataFrame({"hielo": [2107]}, index=["5-6"]), "no existen"),
        (pd.DataFrame({"Hielo": [2107]}, index=["2-3"]), "no son hipótesis"),
    ],
)
def test_tensiones_del_enunciado_mal_escritas(cable, tabla, mensaje):
    with pytest.raises(ValueError, match=mensaje):
        at.CalculoApoyos(cable, Un=20, alt=600, tensiones=tabla, **DATOS_EJERCICIO)


# --- Esquema


def test_esquema_devuelve_la_figura(apoyos):
    fig = apoyos.esquema(mostrar=False)
    textos = [t.get_text() for t in fig.axes[0].texts]
    assert [str(i) for i in range(1, 6)] == [t for t in textos if t.isdigit()]   # nº de cada apoyo
    for vano in ["210 m", "270 m", "240 m"]:
        assert vano in textos
    for desnivel in ["+5 m", "−20 m", "+20 m"]:
        assert desnivel in textos
    assert "AMARRE\nÁNGULO 45º" in textos
    plt.close(fig)


def test_esquema_se_guarda(apoyos, tmp_path):
    ruta = tmp_path / "esquema.png"
    plt.close(apoyos.esquema(ruta=ruta, mostrar=False))
    assert ruta.stat().st_size > 10_000
