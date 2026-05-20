# Tablero Presupuesto CABA

Tablero interactivo del presupuesto de la Ciudad de Buenos Aires, 2013–2026.

🔗 **[Ver tablero en vivo](https://nwalovnik.github.io/Tablero-Presupuesto-Caba/tablero-presupuesto.html)**

## Qué muestra

- **Sección 1 · Datos**: KPIs, evolución 2013-2026, jurisdicciones, finalidad, inciso y top programas.
- **Sección 2 · Explorador**: filtro interactivo por ministerio y programa, con evolución y variación real interanual.
- **Sección 3 · Calendario**: próximas publicaciones oficiales del presupuesto CABA en formato mensual.

Toggle Nominal / Real (deflactado por IPCBA empalmado base 2019=100).

## Fuentes de datos

| Dataset | Período | Fuente |
|---------|---------|--------|
| Ejecución 2013-2019 | Cierre anual (T4) | [BA Data — ZIP histórico](https://data.buenosaires.gob.ar/dataset/presupuesto-ejecutado) |
| Ejecución 2020-2025 | Cierre anual (T4) | [BA Data — CSV por año](https://data.buenosaires.gob.ar/dataset/presupuesto-ejecutado) |
| Sancionado 2026 | Ley 6929 | [BA Data — XLSX sancionado](https://data.buenosaires.gob.ar/dataset/presupuesto-sancionado) |
| IPCBA mensual | Jul-2012 → presente | [IDECBA empalmado base 2021=100](https://www.estadisticaciudad.gob.ar/eyc/banco-datos/ipcba-base-2021-100-nivel-general-indice-mensual-empalmado-con-la-serie-anterior-base-julio-2011-junio-2012-100-ciudad-de-buenos-aires-julio-de-2012-agosto-de-2025/) |

## Exclusiones metodológicas

Siguiendo la convención del **Informe de Ejecución Presupuestaria del GCBA** (*"No incluye Gastos Figurativos ni Aplicaciones Financieras"*):

- Se excluyen filas con **Clasificación Económica que comienza con `23`** (Aplicaciones Financieras: amortización de deuda e inversión financiera).
- Se excluyen filas con jurisdicción vacía (subtotales/totales pre-calculados de los CSVs).
- Programas con diferencias tipográficas menores (acentos, puntos, espacios) dentro de la misma jurisdicción se consolidan automáticamente.

Esto reconcilia el devengado del CSV con el total publicado en el PDF oficial de cierre anual.

## Actualización automática

GitHub Actions corre `.github/workflows/actualizar.yml` todos los días a las 11:00 ART:

1. `descargar_datos.py` — baja los CSVs/XLSX/ZIP desde BA Data e IDECBA.
2. `build_ipc.py` — recalcula `IPC_PROMEDIO_ANUAL` desde el IPCBA mensual (promedio anual simple; años parciales con método de períodos comparables).
3. `data/build_budget_data.py` — agrega registros por jurisdicción / finalidad / función / programa / inciso → `budget_data.json`.
4. `inyectar_html.py` — inyecta el JSON dentro del HTML autocontenido.
5. `build_calendario.py` — regenera el calendario de próximas publicaciones.
6. Commit + push.

Si algún paso falla (e.g. CDN caído), se preserva la versión committeada previa.

## Correr localmente

```bash
pip install requests openpyxl
python descargar_datos.py
python build_ipc.py
python data/build_budget_data.py
python inyectar_html.py
python build_calendario.py
# abrir tablero-presupuesto.html en el browser
```

## Stack

- HTML / CSS / Vanilla JS — sin framework, sin build step
- [Chart.js 4](https://www.chartjs.org/) — todos los gráficos
- Python 3.11 + `openpyxl` + `requests` para el pipeline
- GitHub Actions + Pages para hosting + actualización diaria

## Licencia

Datos: [Términos y Condiciones de BA Data](https://data.buenosaires.gob.ar/acerca/terminos) (uso público).
Código: MIT.
