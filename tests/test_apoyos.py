"""Tests de la clase CalculoApoyos (datos de la línea y esquema)."""

import matplotlib.pyplot as plt
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
