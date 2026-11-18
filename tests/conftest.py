"""Datos y escenarios compartidos por los tests."""

import dataclasses
from pathlib import Path

import matplotlib
import pytest

import alta_tension as at

matplotlib.use("Agg")  # dibujar sin abrir ventanas

CARPETA_REFERENCIAS = Path(__file__).parent / "referencias"
CAMPOS_LINEA = {campo.name for campo in dataclasses.fields(at.Linea)}

# Escenarios de cálculo mecánico: nombre -> (conductor, datos del conductor, datos de la línea)
CASOS_MECANICOS = {
    # Ejemplo de clase "Cálculo mecánico de un vano a nivel": zona B, media tensión, viento excepcional
    "zonaB_MT_LA56": ("LA 56", dict(E_dato=7949, alfa_dato=19.1e-6), dict(Un=20, alt=600, vano=170, Vv=130)),
    # Zona A: sin hielo
    "zonaA_LA110": ("LA 110", {}, dict(Un=66, alt=300, vano=250)),
    # Zona C y categoría especial: hielo + viento
    "zonaC_especial_HAWK": ("LA 280 HAWK", {}, dict(Un=220, alt=1200, vano=400)),
    # Vano de más de 500 m: flecha con la catenaria
    "zonaB_especial_catenaria_GULL": ("LA 380 GULL", {}, dict(Un=400, alt=800, vano=600)),
}


def crear_calculo(caso, **cambios):
    "Crea el calculoMecanico de un escenario. Con **cambios se sobrescriben sus datos"
    conductor, datos_conductor, datos = CASOS_MECANICOS[caso]
    datos = {**datos, **cambios}
    linea = at.Linea(**{k: v for k, v in datos.items() if k in CAMPOS_LINEA})
    resto = {k: v for k, v in datos.items() if k not in CAMPOS_LINEA}  # vano y desnivel
    return at.calculoMecanico(at.Conductor(conductor, **datos_conductor), linea, **resto)


@pytest.fixture(params=CASOS_MECANICOS)
def caso(request):
    "Ejecuta el test una vez por cada escenario"
    return request.param
