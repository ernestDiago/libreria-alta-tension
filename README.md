# Librería de Alta Tensión

Librería en Python con los cálculos de **líneas eléctricas de alta tensión** de la asignatura *Generación, Distribución y Utilización de la Energía Eléctrica* (Máster).

| Módulo | Clases | Qué calcula |
|---|---|---|
| **Modelos eléctricos** | `Modelo` | Tensión, intensidad, potencia, pérdidas y caída de tensión en el origen de una línea con los modelos **inductivo**, **en T**, **en π** y de **parámetros distribuidos** |
| **Cálculo mecánico** (Tema 9) | `Conductor`, `calculoMecanico` | Sobrecargas de viento y hielo, **hipótesis del RLAT** (ITC-LAT-07), tracciones, **flechas** y **tabla de tendido** |

Todo está en un único archivo, [`alta_tension.py`](alta_tension.py).

---

## Instalación

```bash
git clone https://github.com/<usuario>/libreria-alta-tension.git
cd libreria-alta-tension
pip install -r requirements.txt
```

Requisitos: Python ≥ 3.10, `pandas`, `numpy` y `openpyxl` (este último solo para exportar a Excel).

### Usarla desde otra carpeta

`import alta_tension` funciona directamente dentro de la carpeta de la librería. Para usarla desde otro proyecto, añade su ruta al principio del script:

```python
import sys
sys.path.append(r"C:\ruta\a\libreria-alta-tension")

import alta_tension as at
```

Los datos de conductores se buscan junto a `alta_tension.py`, así que funciona la ejecutes desde donde la ejecutes.

---

## Uso rápido

### Modelos eléctricos

```python
import alta_tension as at

# Unidades: Pf [MW], Uf [kV], L [km], r y x [Ω/km], g y b [S/km]
linea = at.Modelo(Pf=600, fp=0.8, Uf=400, L=80, r=0.012, x=0.15,
                  g=0, b=2.7e-6, caracter="inductivo")

linea.pi()          # diccionario con los resultados del modelo en π
linea.comparar()    # DataFrame con los cuatro modelos
linea.Z, linea.Y    # impedancia y admitancia totales
```

```
                                    Modelo Inductivo  Modelo en T  Modelo en Pi  Modelo parametros distribuidos
Tensión de línea en el origen [kV]           415.285      414.758       414.769                         414.761
Intensidad en el origen [A]                 1082.532     1051.960      1051.977                        1051.972
Potencia activa en el origen [MW]            603.375      603.281       603.283                         603.281
Pérdidas de potencia [MW]                      3.375        3.281         3.283                           3.281
Caída de tensión aritmética [kV]              15.285       14.758        14.769                          14.761
```

### Cálculo mecánico

```python
import alta_tension as at

cable = at.Conductor("LA 56")                                  # E y α típicos según composición
cable = at.Conductor("LA 56", E_dato=7949, alfa_dato=19.1e-6)  # E y α del enunciado

calc = at.calculoMecanico(cable, Un=20, alt=600, vano=170, Vv=130)

calc.resolver()          # DataFrame con todas las hipótesis
calc.dominante           # hipótesis que manda -> 'hielo'
calc.flecha_maxima       # 5.26 m
calc.tabla_tendido()     # T y flecha de 0 a 45 ºC
calc.exportar_excel("calculo_mecanico_LA56.xlsx")
```

```
Zona B, categoría normal, coef. seguridad 3
                         temp_C  p_t_daN_m  T0_daN  Tmax_daN  %_rotura  flecha_m  limite_%
hipotesis
EDS                          15       0.19  146.46    147.31      8.99      4.57     15.00
viento                      -10       0.60  447.30    450.17     27.46      4.82     33.33
CHS                          -5       0.19  161.75    162.51      9.93      4.14     20.00
viento excepcional          -10       0.69  503.10    506.52     30.88      4.96     33.33
hielo                       -15       0.74  539.35    543.00     33.11      4.95     33.33
flecha viento 15ºC           15       0.60  411.07    414.20     25.23      5.24       NaN
flecha temperatura 50ºC      50       0.19  127.28    128.25      7.81      5.26       NaN
flecha hielo 0ºC              0       0.74  514.01    517.84     31.55      5.19       NaN
flecha mínima               -15       0.19  171.18    171.91     10.51      3.91       NaN
desviación cadena           -10       0.34  280.37    281.85     17.21      4.36       NaN
```

El archivo [`ejemplos.py`](ejemplos.py) resuelve estos dos ejemplos completos. Se puede ejecutar entero o celda a celda (`# %%`):

```bash
python ejemplos.py
```

---

## Referencia

### `Modelo`

| Parámetro | Unidad | Descripción |
|---|---|---|
| `Pf` | MW | Potencia activa de la carga |
| `fp` | — | Factor de potencia de la carga (cos φ) |
| `Uf` | kV | Tensión de línea en la carga |
| `L` | km | Longitud de la línea |
| `r`, `x` | Ω/km | Resistencia y reactancia por unidad de longitud |
| `g`, `b` | S/km | Conductancia y susceptancia por unidad de longitud |
| `caracter` | — | `"inductivo"` o `"capacitivo"`. Cualquier otro valor da `ValueError` |

| Método / atributo | Devuelve |
|---|---|
| `inductivo()`, `T()`, `pi()`, `distribuidos()` | Diccionario con U₀ [kV], I₀ [A], P₀ [MW], ΔP [MW] y ΔU [kV] |
| `comparar()` | `DataFrame` con los cuatro modelos en columnas |
| `Z`, `Y` | Impedancia [Ω] y admitancia [S] totales (complejos) |
| `Ic`, `Vf` | Intensidad [A] y tensión simple [V] en la carga (complejos) |

### `Conductor`

| Parámetro | Tipo | Descripción |
|---|---|---|
| `conductor` | `str` | Nombre antiguo del conductor, p. ej. `"LA 56"`, `"LA 110"`, `"LA 280 HAWK"` |
| `archivo` | `str` | CSV de características (por defecto `caracteristicas_conductores/conductores_AL1_ST1A.csv`) |
| `E_dato` | `float \| None` | Módulo de elasticidad [daN/mm²]. Si es `None`, se toma de `PROPIEDADES` |
| `alfa_dato` | `float \| None` | Coeficiente de dilatación lineal [1/ºC]. Si es `None`, se toma de `PROPIEDADES` |

**Atributos calculados:** `datos` (fila completa del CSV), `p` (peso propio, daN/m), `d` (diámetro, mm), `S` (sección, mm²), `rotura` (carga de rotura, daN), `E` y `alfa`.

### `calculoMecanico`

| Parámetro | Tipo | Por defecto | Descripción |
|---|---|---|---|
| `conductor` | `Conductor` | — | Conductor de la línea |
| `Un` | `float` | — | Tensión nominal [kV]. Determina la categoría |
| `alt` | `float` | — | Altitud [m]. Determina la zona A / B / C |
| `vano` | `float` | — | Longitud del vano (o vano de regulación) [m] |
| `Vv` | `float \| None` | `None` | Viento máximo de la zona [km/h]. Si supera 120 (140 en categoría especial), se añade la hipótesis de **viento excepcional** |
| `antivibradores` | `bool` | `False` | Si es `True`, el límite del EDS sube del 15 % al 22 % |
| `coef_seguridad` | `float \| None` | `None` | Coeficiente de seguridad a rotura. `None` → 3 en media tensión (15–20 kV) y 2,5 en el resto |
| `chs` | `float \| None` | `0.20` | Límite CHS a −5 ºC (fracción de la rotura). `None` → no se comprueba |

| Método / atributo | Devuelve |
|---|---|
| `resolver()` | `DataFrame` con temperatura, peso aparente, T₀, T_max, % de rotura, flecha y límite de cada hipótesis |
| `tabla_tendido(temperaturas=range(0, 50, 5))` | `DataFrame` con T y flecha sin sobrecarga para cada temperatura |
| `exportar_excel(ruta, temperaturas)` | Guarda un Excel con los datos, las hipótesis y la tabla de tendido |
| `flecha_maxima` | Mayor de las flechas máximas [m] |
| `dominante` | Nombre de la hipótesis que manda (disponible tras `resolver()`) |
| `Zona`, `categoria`, `coef`, `v_ref`, `v_excepcional` | Datos derivados de la línea |

---

## Datos de conductores

Los CSV de [`caracteristicas_conductores/`](caracteristicas_conductores) se han pasado de las tablas del Tema 9 (norma UNE-EN 50182):

| Archivo | Conductores |
|---|---|
| `conductores_AL1_ST1A.csv` | Aluminio-acero (antiguos «LA»): LA 30, LA 56, LA 78, LA 110, LA 145, LA 180, LA 280 HAWK, LA 380 GULL, LA 455 CONDOR, LA 545 CARDINAL y LA 635 FINCH. Incluye características, sobrecargas de hielo, de viento y de hielo + viento |
| `conductores_AL1.csv` | Aluminio homogéneo (L 28 … L 630) |
| `conductores_AL2.csv` | Aleación de aluminio (D 28 … D 630) |

E y α no figuran en las tablas del tema. Por defecto se asignan según la composición (diccionario `PROPIEDADES`):

| Composición (Al + Acero) | Conductores | E [daN/mm²] | α [1/ºC] |
|---|---|---|---|
| 6 + 1 | LA 30, LA 56, LA 78 | 8100 | 19,1·10⁻⁶ |
| 26 + 7 | LA 280 | 7700 | 18,9·10⁻⁶ |
| 30 + 7 | LA 110, LA 145, LA 180 | 8000 | 17,8·10⁻⁶ |
| 54 + 7 | LA 380, LA 455, LA 545 | 7000 | 19,3·10⁻⁶ |
| 54 + 19 | LA 635 | 6800 | 19,4·10⁻⁶ |

Son valores típicos de catálogo. Si el enunciado da otros, pásalos con `E_dato` y `alfa_dato`.

> **Nota sobre la tabla del tema:** en la columna «Total viento-hielo zona C», el viento está calculado sobre el manguito de hielo de la zona B. Se ha copiado tal cual. La clase `calculoMecanico` no usa esa columna: calcula la sobrecarga conjunta con el manguito de la zona que corresponda.

---

## Documentación

- [`docs/modelos_electricos.md`](docs/modelos_electricos.md): ecuaciones de los cuatro modelos y validación.
- [`docs/calculo_mecanico.md`](docs/calculo_mecanico.md): catenaria, sobrecargas, ecuación de cambio de condiciones, hipótesis del RLAT y algoritmo de la hipótesis dominante.

## Validación

- **Modelos eléctricos:** coinciden con la hoja de cálculo de la asignatura (`Lineas_de_Alta_tension.xlsx`).
- **Cálculo mecánico:** reproduce el ejemplo de clase *«Cálculo mecánico de un vano a nivel»* con diferencias menores de 1 daN, debidas al redondeo del ejemplo.

## Limitaciones

- **Cálculo mecánico:** vanos **a nivel** (sin desnivel), un único vano o vano de regulación por cálculo, y sin deformación plástica (fluencia) del conductor. La aproximación parabólica es válida para vanos de menos de 500 m y desnivel menor del 10 %. En vanos mayores, la flecha se calcula con la catenaria, pero la ecuación de cambio de condiciones sigue siendo la parabólica.
- **Modelos eléctricos:** línea trifásica equilibrada, con datos conocidos en el extremo de la carga.

## Estructura

```
libreria-alta-tension/
├── alta_tension.py               # la librería
├── ejemplos.py                   # ejemplos de uso
├── caracteristicas_conductores/  # tablas de conductores (CSV)
├── docs/                         # explicación de los cálculos
├── requirements.txt
└── README.md
```
