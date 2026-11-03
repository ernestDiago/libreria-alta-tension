# Librería de Alta Tensión

Librería en Python con los cálculos de **líneas eléctricas de alta tensión** de la asignatura *Generación, Distribución y Utilización de la Energía Eléctrica* (Máster).

| Módulo | Clases | Qué calcula |
|---|---|---|
| **Modelos eléctricos** | `Modelo` | Tensión, intensidad, potencia, pérdidas y caída de tensión en el origen de una línea con los modelos **inductivo**, **en T**, **en π** y de **parámetros distribuidos** |
| **Cálculo mecánico** (Tema 9) | `Conductor`, `calculoMecanico` | Sobrecargas de viento y hielo, **hipótesis del RLAT** (ITC-LAT-07), tracciones, **flechas** y **tabla de tendido**, en vanos **a nivel** y **a desnivel** |

Todo está en un único archivo, [`alta_tension.py`](alta_tension.py).

---

## Instalación

```bash
git clone https://github.com/ernestDiago/libreria-alta-tension.git
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
                         temp_C  p_t_daN_m  T0_daN  Tmax_daN  %_rotura  %_rotura_TB  flecha_m  limite_%
hipotesis
EDS                          15       0.19  146.46    147.31      8.99         9.04      4.57     15.00
viento                      -10       0.60  447.30    450.17     27.46        27.63      4.82     33.33
CHS                          -5       0.19  161.75    162.51      9.93         9.98      4.14     20.00
viento excepcional          -10       0.69  503.10    506.52     30.88        31.09      4.96     33.33
hielo                       -15       0.74  539.35    543.00     33.11        33.33      4.95     33.33
flecha viento 15ºC           15       0.60  411.07    414.20     25.23        25.43      5.24       NaN
flecha temperatura 50ºC      50       0.19  127.28    128.25      7.81         7.87      5.26       NaN
flecha hielo 0ºC              0       0.74  514.01    517.84     31.55        31.79      5.19       NaN
flecha mínima               -15       0.19  171.18    171.91     10.51        10.55      3.91       NaN
desviación cadena           -10       0.34  280.37    281.85     17.21        17.30      4.36       NaN
```

### Vano a desnivel

Basta con añadir el desnivel entre apoyos `desnivel` [m]. El signo da igual: el resultado es el mismo esté el apoyo alto a un lado o al otro.

```python
cable = at.Conductor("LA 78", E_dato=7949, alfa_dato=19.1e-6)
calc = at.calculoMecanico(cable, Un=20, alt=400, vano=220, desnivel=70)

calc.vano_real           # 230.87 m
calc.resolver()          # T0_daN es ahora Tm (punto medio) y Tmax_daN es TB (apoyo alto)
```

```
                         temp_C  p_t_daN_m  T0_daN  Tmax_daN  %_rotura  %_rotura_TB  flecha_m  limite_%
hipotesis
EDS                          15       0.27  297.03    307.96     12.85        13.32      5.98     15.00
viento                       -5       0.73  740.39    770.67     32.02        33.33      6.56     33.33
CHS                          -5       0.27  332.19    342.94     14.37        14.83      5.35     20.00
flecha viento 15ºC           15       0.73  689.30    719.93     29.81        31.14      7.04       NaN
flecha temperatura 50ºC      50       0.27  253.88    265.07     10.98        11.47      7.00       NaN
flecha mínima                -5       0.27  332.19    342.94     14.37        14.83      5.35       NaN
desviación cadena            -5       0.43  491.32    508.94     21.25        22.01      5.85       NaN
```

El archivo [`ejemplos.py`](ejemplos.py) resuelve los ejemplos de modelos eléctricos y de vano a nivel. Se puede ejecutar entero o celda a celda (`# %%`):

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
| `vano` | `float` | — | Vano **proyectado** *a*, distancia horizontal entre apoyos (o vano de regulación) [m] |
| `Vv` | `float \| None` | `None` | Viento máximo de la zona [km/h]. Si supera 120 (140 en categoría especial), se añade la hipótesis de **viento excepcional** |
| `desnivel` | `float` | `0.0` | Diferencia de altura *d* entre los dos apoyos del vano [m]. `0` → vano a nivel |
| `antivibradores` | `bool` | `False` | Si es `True`, el límite del EDS sube del 15 % al 22 % |
| `coef_seguridad` | `float \| None` | `None` | Coeficiente de seguridad a rotura. `None` → 3 en media tensión (15–20 kV) y 2,5 en el resto |
| `chs` | `float \| None` | `0.20` | Límite CHS a −5 ºC (fracción de la rotura). `None` → no se comprueba |

| Método / atributo | Devuelve |
|---|---|
| `resolver()` | `DataFrame` con la temperatura, el peso aparente, T₀, T_max, el % de rotura con T₀ (`%_rotura`) y con T_max (`%_rotura_TB`), la flecha y el límite de cada hipótesis |
| `tabla_tendido(temperaturas=range(0, 50, 5))` | `DataFrame` con T y flecha sin sobrecarga para cada temperatura |
| `exportar_excel(ruta, temperaturas)` | Guarda un Excel con los datos, las hipótesis y la tabla de tendido |
| `flecha_maxima` | Mayor de las flechas máximas [m] |
| `dominante` | Nombre de la hipótesis que manda (disponible tras `resolver()`) |
| `Zona`, `categoria`, `coef`, `v_ref`, `v_excepcional` | Datos derivados de la línea |
| `vano_real`, `con_desnivel` | Vano real *b* = √(a² + d²) [m], y si el desnivel llega a `DESNIVEL_MINIMO` |

**Con desnivel**, las tensiones de las tablas cambian de significado: `T0_daN` es la tensión **Tm en el punto medio del vano** y `Tmax_daN` es la tensión **T_B en el apoyo más alto**. A partir de `DESNIVEL_MINIMO` (1 m), el EDS y el CHS se comprueban con T_B, como el viento y el hielo. Por debajo, igual que en un vano a nivel.

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
- [`docs/calculo_mecanico.md`](docs/calculo_mecanico.md): catenaria, sobrecargas, ecuación de cambio de condiciones, hipótesis del RLAT, algoritmo de la hipótesis dominante y vano a desnivel.

## Validación

- **Modelos eléctricos:** coinciden con la hoja de cálculo de la asignatura (`Lineas_de_Alta_tension.xlsx`).
- **Cálculo mecánico a nivel:** reproduce el ejemplo de clase *«Cálculo mecánico de un vano a nivel»* con diferencias menores de 1 daN, debidas al redondeo del ejemplo.
- **Cálculo mecánico a desnivel:** reproduce el estado inicial del ejercicio de clase *«Cálculo mecánico de vano desnivelado»*: b = 230,87 m y Tm = 740,66 daN.

## Limitaciones

- **Cálculo mecánico:** un único vano o vano de regulación por cálculo, y sin deformación plástica (fluencia) del conductor. La aproximación parabólica es válida para vanos de menos de 500 m. En vanos mayores, la flecha se calcula con la catenaria, pero la ecuación de cambio de condiciones sigue siendo la parabólica.
- **Vano a desnivel:** la ecuación de cambio de condiciones usa el vano proyectado *a* con la tensión Tm, como en la asignatura. Es una aproximación que pierde precisión en vanos muy desnivelados (≈ 1 % en el término B con un desnivel del 10 %). La catenaria de los vanos de más de 500 m todavía no tiene en cuenta el desnivel.
- **Modelos eléctricos:** línea trifásica equilibrada, con datos conocidos en el extremo de la carga.

## Tests

```bash
pip install pytest
pytest
```

| Archivo | Qué comprueba |
|---|---|
| `tests/test_modelos_electricos.py` | Los cuatro modelos frente a la hoja de cálculo, el comportamiento físico con susceptancia y el carácter de la carga |
| `tests/test_conductores.py` | Que los CSV cuadran con las fórmulas del tema (detecta números mal copiados) y la clase `Conductor` |
| `tests/test_calculo_mecanico.py` | Zona, categoría y coeficiente de seguridad; los ejemplos 1, 2 y 3 del Tema 9; el ejemplo de clase de vano a nivel; que ninguna hipótesis supere su límite; y una **regresión** con cuatro escenarios (zonas A, B y C, categoría especial y vano con catenaria) |
| `tests/test_desnivel.py` | Vano a desnivel: que con `desnivel=0` todo sea idéntico al vano a nivel, que el signo no importe, el umbral `DESNIVEL_MINIMO` y los valores del ejercicio de clase |

Los tests de regresión comparan con las tablas de `tests/referencias/`. Si cambias el cálculo **a propósito** y has comprobado que el resultado nuevo es el correcto, regenéralas con:

```bash
python tests/generar_referencias.py
```

## Estructura

```
libreria-alta-tension/
├── alta_tension.py               # la librería
├── ejemplos.py                   # ejemplos de uso
├── caracteristicas_conductores/  # tablas de conductores (CSV)
├── docs/                         # explicación de los cálculos
├── tests/                        # tests (pytest)
├── pyproject.toml                # configuración de pytest
├── requirements.txt
└── README.md
```
