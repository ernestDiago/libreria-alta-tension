# Documentación del cálculo mecánico

Este documento explica qué calcula la clase `calculoMecanico` y por qué, siguiendo el RLAT (ITC-LAT-07) y el Tema 9 de la asignatura.

## Índice

1. [Objetivo](#1-objetivo)
2. [Curva del conductor: catenaria y parábola](#2-curva-del-conductor-catenaria-y-parábola)
3. [Vano de regulación](#3-vano-de-regulación)
4. [Sobrecargas](#4-sobrecargas)
5. [Ecuación de cambio de condiciones](#5-ecuación-de-cambio-de-condiciones)
6. [Hipótesis de cálculo del RLAT](#6-hipótesis-de-cálculo-del-rlat)
7. [Algoritmo: búsqueda de la hipótesis dominante](#7-algoritmo-búsqueda-de-la-hipótesis-dominante)
8. [Correspondencia con el código](#8-correspondencia-con-el-código)
9. [Validación](#9-validación)

---

## 1. Objetivo

El cálculo mecánico del conductor busca dos cosas:

1. La **tracción de tendido**: con cuánta fuerza se tensa el cable el día del montaje para que, en ninguna condición climática, se supere el límite del reglamento. El resultado es la **tabla de tendido**.
2. Las **flechas máximas y mínimas**, que fijan la altura de los apoyos y las distancias de seguridad.

Un cable poco tenso cuelga mucho y obliga a poner apoyos más altos. Uno muy tenso puede romperse con frío, hielo o viento.

## 2. Curva del conductor: catenaria y parábola

Un cable colgado describe una **catenaria**:

$$y = h \cosh\frac{x}{h}, \qquad h = \frac{T_0}{p}$$

- **T₀** es la componente horizontal de la tracción [daN]. Es constante a lo largo del vano.
- **p** es el peso por metro [daN/m]. Con sobrecarga se usa el peso aparente **p_t**.
- **x** se mide desde el punto más bajo e **y** desde una directriz situada *h* metros por debajo de él.

| Magnitud | Catenaria (exacta) | Parábola (aproximada) |
|---|---|---|
| Flecha | $f = h\left(\cosh\frac{a}{2h} - 1\right)$ | $f = \dfrac{a^2 p}{8 T_0}$ |
| Longitud | $L = 2h \sinh\frac{a}{2h}$ | $L = a\left(1 + \dfrac{a^2 p^2}{24 T_0^2}\right)$ |
| Tracción máxima (en los apoyos) | $T_{max} = T_0 + p f$ | $T_{max} = T_0 + p f$ |

La parábola sale de desarrollar cosh y senh en serie de MacLaurin. Es válida para **vanos de menos de 500 m y desnivel menor del 10 %**.

**En el código:** `_flecha_aprox`, `_flecha_exacta` y `_flecha`, que elige una u otra según el vano.

### De T_max a T₀

El reglamento limita la tracción **máxima** (en los apoyos). Para obtener T₀ a partir de un T_max dado, se despeja de $T_{max} = T_0 + \frac{a^2 p^2}{8 T_0}$:

$$T_0 = \frac{2T_{max} + \sqrt{4T_{max}^2 - 2a^2p^2}}{4}$$

**En el código:** `_T0_desde_Tmax` y `_Tmax`.

## 3. Vano de regulación

En un cantón (el tramo entre dos apoyos de amarre) con varios vanos, la tracción se iguala en todos ellos. El cálculo se hace con un vano ideal equivalente:

$$a_r = \sqrt{\frac{\sum a_i^3}{\sum a_i}}$$

La clase recibe directamente un único `vano`. Si tienes un cantón, calcula *a_r* y pásalo como `vano`.

## 4. Sobrecargas

| Caso | Fórmula | Método |
|---|---|---|
| Peso propio | $p = \text{masa[kg/km]} \cdot 9{,}81 / 10\,000$ | `Conductor.p` |
| Presión del viento | $q = 60\left(\frac{V}{120}\right)^2$ si $d \le 16$ mm; $q = 50\left(\frac{V}{120}\right)^2$ si $d > 16$ mm | `_q(v, d)` |
| Viento | $p_v = q \cdot d$, con $p_t = \sqrt{p^2 + p_v^2}$ | `_pv`, `_p_viento` |
| Hielo | $p_h = 0{,}18\sqrt{d}$ (zona B), $0{,}36\sqrt{d}$ (zona C), 0 (zona A), con $p_t = p + p_h$ | `_p_hielo` |
| Hielo + viento | $p_t = \sqrt{(p + p_h)^2 + p_v'^2}$, con $p_v' = q(60\text{ km/h}) \cdot D$, donde *D* es el diámetro con manguito de hielo | `_sobrecarga_conjunta` |
| Mitad de presión (desviación de cadenas) | $p_v/2$ a 120 km/h | `_p_viento_mitad` |

El viento de referencia es de **120 km/h**, o de **140 km/h** en líneas de categoría especial (≥ 220 kV).

## 5. Ecuación de cambio de condiciones

Responde a esta pregunta: *si conozco la tracción del cable en un estado (temperatura y carga), ¿cuál tendrá en otro estado?*

Iguala el cambio de longitud geométrica de la parábola con el alargamiento por **dilatación térmica** y por **elasticidad**:

$$\frac{a^3}{24}\left(\frac{p_2^2}{T_2^2} - \frac{p_1^2}{T_1^2}\right) = a\,\alpha(\theta_2 - \theta_1) + a\frac{T_2 - T_1}{S E}$$

Escrita en tensiones por unidad de sección ($t = T/S$), queda una cúbica en $t_2$:

$$t_2^2(t_2 + A) = B$$

$$K = \frac{a^2 E w^2 m_1^2}{24 t_1^2} - t_1, \qquad A = \alpha E(\theta_2 - \theta_1) + K, \qquad B = \frac{a^2 E w^2 m_2^2}{24}$$

| Símbolo | Significado |
|---|---|
| $w = p/S$ | Peso por unidad de longitud y sección [daN/(m·mm²)] |
| $m = p_t/p$ | Coeficiente de sobrecarga (1 = sin sobrecarga) |
| $\theta$ | Temperatura [ºC] |
| $E$, $\alpha$ | Módulo de elasticidad [daN/mm²] y coeficiente de dilatación [1/ºC] |

**En el código:** `_cambio_condiciones(T1, theta1, p1, theta2, p2)`. Resuelve la cúbica con `numpy.roots` y toma la raíz real positiva.

## 6. Hipótesis de cálculo del RLAT

La **zona** se obtiene de la altitud (A: < 500 m, B: 500–1000 m, C: > 1000 m) y la **categoría** de la tensión nominal. Solo se comprueban las hipótesis de la zona de la línea.

### 6.1 Hipótesis limitantes (fijan cuánto se puede tensar)

| Hipótesis | Zona A | Zona B | Zona C | Límite |
|---|---|---|---|---|
| EDS | 15 ºC, p | 15 ºC, p | 15 ºC, p | T₀ ≤ 15 % rotura (22 % con antivibradores) |
| CHS (*) | −5 ºC, p | −5 ºC, p | −5 ºC, p | T₀ ≤ 20 % rotura |
| Viento | −5 ºC, p_viento | −10 ºC, p_viento | −15 ºC, p_viento | T_max ≤ rotura / CS |
| Viento excepcional (**) | −5 ºC | −10 ºC | −15 ºC | T_max ≤ rotura / CS |
| Hielo (***) | — | −15 ºC, p_hielo | −20 ºC, p_hielo | T_max ≤ rotura / CS |

- (*) El CHS no lo exige el RLAT; es un criterio habitual de las compañías. Se desactiva con `chs=None`.
- (**) Solo si `Vv` supera el viento de referencia (hipótesis adicional, ITC-LAT-07 3.2.1).
- (***) En categoría especial se aplica hielo + viento a 60 km/h.
- **CS** es el coeficiente de seguridad: 2,5 en general, o 3 en media tensión (15–20 kV) para no tener que considerar la rotura de conductores en el cálculo de apoyos.

### 6.2 Hipótesis de resultado (solo se calculan)

| Hipótesis | Temperatura | Carga | Uso |
|---|---|---|---|
| Flecha máxima viento | 15 ºC | viento a 120 km/h | Altura de apoyos |
| Flecha máxima temperatura | 50 ºC (85 ºC en categoría especial) | peso propio | Altura de apoyos |
| Flecha máxima hielo | 0 ºC | hielo (zonas B y C) | Altura de apoyos |
| Flecha mínima | −5 / −15 / −20 ºC (A / B / C) | peso propio | Cruzamientos |
| Desviación de cadena | −5 / −10 / −15 ºC | mitad de la presión del viento de 120 km/h | Distancias en apoyos |
| Tabla de tendido | 0, 5, …, 45 ºC | peso propio | Montaje |

## 7. Algoritmo: búsqueda de la hipótesis dominante

No se sabe de antemano qué hipótesis limita. Se supone una y se comprueba:

```
1. Partir del EDS: 15 ºC, sin sobrecarga, T0 = 15 % rotura
2. Con la ecuación de cambio, calcular T0 en cada hipótesis limitante
3. Para cada una, ratio = T / T_límite (T_max si el límite es a rotura, T0 si es EDS/CHS)
4. Si ningún ratio supera 1  -> la hipótesis de partida es la dominante. FIN
   Si alguno lo supera       -> la de mayor ratio pasa a ser la de partida,
                                puesta justo en su límite, y se vuelve al paso 2
5. Desde la dominante se calculan todas las hipótesis (limitantes y de resultado)
```

El ratio se compara en proporción y no en daN, porque cada hipótesis tiene un límite distinto.

**En el código:** `_hipotesis_limitantes`, `_estado_inicial`, `_ratio`, `_hipotesis_dominante` y `resolver`.

## 8. Correspondencia con el código

| Método | Qué hace |
|---|---|
| `Conductor.__post_init__` | Lee el CSV y obtiene p, d, S, rotura, E y α |
| `calculoMecanico.__post_init__` | Calcula zona, categoría, viento de referencia y excepcional, y coeficiente de seguridad |
| `_q`, `_pv`, `_p_viento`, `_p_viento_mitad`, `_p_hielo`, `_sobrecarga_conjunta` | Sobrecargas (apartado 4) |
| `_cambio_condiciones` | Ecuación de cambio de condiciones (apartado 5) |
| `_T0_desde_Tmax`, `_Tmax` | Conversión entre T₀ y T_max (apartado 2) |
| `_flecha`, `_flecha_aprox`, `_flecha_exacta` | Flecha (apartado 2) |
| `_hipotesis_limitantes`, `_hipotesis_resultado` | Listas de hipótesis según zona y categoría (apartado 6) |
| `_hipotesis_dominante` | Algoritmo del apartado 7 |
| `resolver` | Tabla con todas las hipótesis |
| `tabla_tendido` | Tabla de tendido |
| `flecha_maxima` | Mayor flecha de las hipótesis de flecha máxima |

## 9. Validación

El apartado 2 de [`ejemplos.py`](../ejemplos.py) reproduce el ejemplo de clase *«Cálculo mecánico de un vano a nivel»*: 20 kV, LA-56, 600 m de altitud, vano de 170 m, viento máximo de 130 km/h, E = 7949 daN/mm² y α = 19,1·10⁻⁶ ºC⁻¹.

| Hipótesis | Ejemplo T₀ [daN] / f [m] | Código T₀ [daN] / f [m] |
|---|---|---|
| Hielo −15 ºC (dominante) | 539,34 / 4,95 | 539,35 / 4,95 |
| Viento −10 ºC | 447,72 / 4,80 | 447,30 / 4,82 |
| Viento excepcional −10 ºC | 503,4 / 4,95 | 503,10 / 4,96 |
| EDS 15 ºC | 146,88 / 4,55 | 146,46 / 4,57 |
| CHS −5 ºC | 162,16 / 4,10 | 161,75 / 4,14 |
| Flecha viento 15 ºC | 411,68 / 5,23 | 411,07 / 5,24 |
| Flecha 50 ºC | 127,76 / 5,24 | 127,28 / 5,26 |
| Flecha hielo 0 ºC | 515 / 5,18 | 514,01 / 5,19 |
| Flecha mínima −15 ºC | 172 / 3,89 | 171,18 / 3,91 |
| Desviación de cadena | 281,2 / 4,35 | 280,37 / 4,36 |

Las diferencias, de menos de 1 daN, se deben al redondeo de t₂ a dos decimales en el ejemplo.
