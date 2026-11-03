# Documentación de los modelos eléctricos

Este documento explica qué calcula la clase `Modelo`: el estado en el **origen** de una línea trifásica a partir de lo que se conoce en la **carga**.

## Índice

1. [Datos de entrada](#1-datos-de-entrada)
2. [Magnitudes comunes](#2-magnitudes-comunes)
3. [Constantes ABCD](#3-constantes-abcd)
4. [Los cuatro modelos](#4-los-cuatro-modelos)
5. [Resultados](#5-resultados)
6. [Correspondencia con el código](#6-correspondencia-con-el-código)
7. [Validación](#7-validación)

---

## 1. Datos de entrada

| Símbolo | Parámetro | Unidad |
|---|---|---|
| $P_f$ | Potencia activa de la carga | MW |
| $\cos\varphi_f$ | Factor de potencia de la carga | — |
| $U_f$ | Tensión de línea en la carga | kV |
| $L$ | Longitud de la línea | km |
| $r$, $x$ | Resistencia y reactancia por km | Ω/km |
| $g$, $b$ | Conductancia y susceptancia por km | S/km |
| — | Carácter de la carga | inductivo / capacitivo |

Internamente, $P_f$ se pasa a W y $U_f$ a V, así que todos los cálculos se hacen en unidades del SI.

## 2. Magnitudes comunes

Se calculan una sola vez al crear el objeto, porque las usan los cuatro modelos.

| Magnitud | Fórmula |
|---|---|
| Impedancia total | $\bar Z = (r + jx)\,L$ |
| Admitancia total | $\bar Y = (g + jb)\,L$ |
| Tensión simple en la carga (origen de fases) | $\bar V_f = \dfrac{U_f}{\sqrt 3}\angle 0°$ |
| Intensidad en la carga | $\bar I_f = \dfrac{P_f}{\sqrt 3\,U_f\cos\varphi_f}\angle\mp\varphi_f$ |

El ángulo de la intensidad es $-\varphi_f$ si la carga es inductiva (la corriente va retrasada) y $+\varphi_f$ si es capacitiva.

## 3. Constantes ABCD

Cualquier modelo de línea se puede escribir como un cuadripolo:

$$\bar V_0 = \bar A\,\bar V_f + \bar B\,\bar I_f \qquad\qquad \bar I_0 = \bar C\,\bar V_f + \bar D\,\bar I_f$$

Por eso los cuatro modelos solo se diferencian en sus constantes A, B, C y D. Todo lo demás se calcula igual.

## 4. Los cuatro modelos

| | **Inductivo** | **En T** | **En π** | **Parámetros distribuidos** |
|---|---|---|---|---|
| $\bar A = \bar D$ | 1 | $1 + \dfrac{\bar Z\bar Y}{2}$ | $1 + \dfrac{\bar Z\bar Y}{2}$ | $\cosh(\bar\gamma L)$ |
| $\bar B$ | $\bar Z$ | $\bar Z\left(1 + \dfrac{\bar Z\bar Y}{4}\right)$ | $\bar Z$ | $\bar Z\,\dfrac{\sinh(\bar\gamma L)}{\bar\gamma L}$ |
| $\bar C$ | 0 | $\bar Y$ | $\bar Y\left(1 + \dfrac{\bar Z\bar Y}{4}\right)$ | $\bar Y\,\dfrac{\sinh(\bar\gamma L)}{\bar\gamma L}$ |

- **Inductivo:** ignora la capacidad de la línea. Sirve para líneas cortas.
- **En T:** la impedancia se divide en dos mitades, con toda la admitancia en el centro.
- **En π:** toda la impedancia va en serie, con media admitancia en cada extremo.
- **Parámetros distribuidos:** el modelo exacto, con la constante de propagación total $\bar\gamma L = \sqrt{\bar Z\bar Y}$.

En el modelo de parámetros distribuidos, si $\bar Y = 0$ el cociente $\sinh(\bar\gamma L)/\bar\gamma L$ es una indeterminación 0/0. Su límite es 1, y es el valor que usa el código. Con $\bar Y = 0$ los cuatro modelos coinciden con el inductivo.

## 5. Resultados

| Magnitud | Fórmula | Unidad |
|---|---|---|
| Tensión de línea en el origen | $U_0 = \sqrt 3\,\lvert\bar V_0\rvert$ | kV |
| Intensidad en el origen | $\lvert\bar I_0\rvert$ | A |
| Potencia aparente en el origen | $\bar S_0 = 3\,\bar V_0\,\bar I_0^{*}$ | — |
| Potencia activa en el origen | $P_0 = \mathrm{Re}(\bar S_0)$ | MW |
| Pérdidas de potencia | $\Delta P = P_0 - P_f$ | MW |
| Caída de tensión aritmética | $\Delta U = U_0 - U_f$ | kV |

## 6. Correspondencia con el código

| Método | Qué hace |
|---|---|
| `Modelo.__init__` | Guarda los datos y pasa $P_f$ a W y $U_f$ a V |
| `_magnitudes_comunes` | Calcula Z, Y, $\bar I_f$ y $\bar V_f$ (apartado 2) |
| `_resolver(A, B, C, D)` | Aplica las ecuaciones del cuadripolo y calcula los resultados (apartados 3 y 5) |
| `inductivo`, `T`, `pi`, `distribuidos` | Calculan las constantes de cada modelo y llaman a `_resolver` (apartado 4) |
| `comparar` | Reúne los cuatro modelos en un `DataFrame` |

## 7. Validación

Con los datos de la hoja de cálculo de la asignatura (600 MW, cos φ = 0,8 inductivo, 400 kV, 80 km, r = 0,012 Ω/km, x = 0,15 Ω/km, g = b = 0), los cuatro modelos dan los mismos valores que la hoja:

| Magnitud | Código | Hoja de cálculo |
|---|---|---|
| U₀ | 415,285 kV | 415,285 kV |
| I₀ | 1082,53 A | 1082,53 A |
| P₀ | 603,375 MW | 603,375 MW |
| ΔP | 3,375 MW | 3,375 MW |
| ΔU | 15,285 kV | 15,285 kV |

Con $b = 2{,}7\cdot10^{-6}$ S/km, los modelos se separan como cabe esperar: el inductivo no cambia, la intensidad en el origen baja por la corriente capacitiva de la línea, y el modelo de parámetros distribuidos queda entre el de T y el de π.

| | Inductivo | T | π | Distribuidos |
|---|---|---|---|---|
| U₀ [kV] | 415,285 | 414,758 | 414,769 | 414,761 |
| I₀ [A] | 1082,53 | 1051,96 | 1051,98 | 1051,97 |
| ΔP [MW] | 3,375 | 3,281 | 3,283 | 3,281 |
