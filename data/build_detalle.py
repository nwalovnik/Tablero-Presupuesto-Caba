"""Genera archivos de detalle línea-por-línea (máxima desagregación) por año/período.

Cada archivo `detalle/detalle_{año}_{período}.csv.gz` contiene una fila por partida
presupuestaria con sus descripciones (jurisdicción → unidad ejecutora → programa →
actividad → finalidad → inciso → partida → subparcial → fuente → geografía) y los
montos (sancionado, vigente, devengado). Es el dato crudo que el tablero deja
descargar filtrado por lo que el usuario tenga seleccionado.

Reusa los loaders de build_budget_data.py (que ya resuelven los cambios de esquema
2013-2015, el off-by-one de 2022, el prefijo SumaDe de 2024-3 y los encodings).
Aplica los mismos filtros que el tablero: sin Aplicaciones Financieras (eco 23xx)
y sin filas de subtotal (jurisdicción vacía).

Salida: detalle/*.csv.gz + detalle/manifest.json (índice de archivos disponibles).
"""
import os, io, csv, gzip, json, importlib.util

BASE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location('bb', os.path.join(BASE, 'build_budget_data.py'))
bb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bb)

OUT_DIR = os.path.join(BASE, '..', 'detalle')
os.makedirs(OUT_DIR, exist_ok=True)

# (columna_salida, claves normalizadas a probar en orden) — cubre los distintos esquemas.
COLS = [
    ('jurisdiccion',     ('jur_desc', 'desc_jur', 'desc_juris')),
    ('unidad_ejecutora', ('ue_desc', 'desc_ue')),
    ('programa',         ('prog_desc', 'desc_prog', 'desc_programa')),
    ('subprograma',      ('sprog_desc', 'desc_sprog', 'desc_sprograma')),
    ('proyecto',         ('proy_desc', 'desc_proy', 'desc_proyecto')),
    ('actividad',        ('act_desc', 'desc_act')),
    ('finalidad',        ('fin_desc', 'desc_fin')),
    ('funcion',          ('fun_desc', 'desc_fun', 'desc_fin_fun')),
    ('inciso',           ('inc_desc', 'inciso_desc', 'desc_inc', 'desc_inciso')),
    ('principal',        ('ppal_desc', 'desc_ppal', 'desc_principal')),
    ('parcial',          ('parc_desc', 'desc_parc', 'desc_parcial')),
    ('subparcial',       ('sparc_desc', 'desc_sparc', 'desc_subparcial')),
    ('fuente_fin',       ('fte_desc', 'desc_fte', 'desc_fuente_fin')),
    ('geografia',        ('geo_desc', 'desc_geo', 'desc_ubic')),
]
AMT = {
    'sancion':   ('sancion', 'sanci0n'),
    'vigente':   ('vigente', 'vigente_trim4_cont', 'vigente_trim1_cont', 'vigente_trim2_cont', 'vigente_trim3_cont'),
    'devengado': ('devengado', 'devengado_trim4_cont', 'devengado_trim1_cont', 'devengado_trim2_cont', 'devengado_trim3_cont'),
}
OUT_HEADER = [c for c, _ in COLS] + ['sancion', 'vigente', 'devengado']


def _norm_key(k):
    return (k.lower().strip().replace('ó', 'o').replace('í', 'i')
            .replace('á', 'a').replace('é', 'e').replace('ú', 'u'))


def sancionado_rows():
    """Filas crudas normalizadas del XLSX sancionado (mismo criterio de claves que el CSV)."""
    import openpyxl
    path = os.path.join(BASE, 'presupuesto-sancionado-2026.xlsx')
    if not os.path.exists(path):
        return []
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb.active
    hdr = None
    out = []
    for i, row in enumerate(ws.iter_rows(values_only=True)):
        if i == 0:
            hdr = [_norm_key(str(h)) if h is not None else '' for h in row]
            continue
        if not row or row[0] is None:
            continue
        out.append({hdr[j]: row[j] for j in range(min(len(hdr), len(row)))})
    return out


def load_rows(year, quarter):
    """quarter=None → cierre anual (o sancionado para el año de proyecto)."""
    if year == bb.YEAR_SANC and quarter is None:
        return sancionado_rows()
    if year in bb.YEARS_HIST:
        return bb.load_year_from_zip(bb.HIST_ZIP, year, quarter=quarter or 4)
    return bb.load_year(year, quarter=quarter)


def write_detalle(year, period_key, rows):
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(OUT_HEADER)
    n = 0
    for r in rows:
        jur = (bb.get_col(r, 'jur_desc', 'desc_jur', 'desc_juris') or '').strip()
        if not jur:
            continue
        eco = str(bb.get_col(r, 'eco', 'eco_cod', 'clas_economico') or '').strip()
        if eco.startswith('23'):
            continue  # Aplicaciones Financieras — coherente con el tablero
        line = []
        for _, keys in COLS:
            line.append((bb.get_col(r, *keys) or '').strip())
        for k in ('sancion', 'vigente', 'devengado'):
            v = bb.to_float_smart(bb.get_col(r, *AMT[k]))
            line.append(round(v) if v else 0)
        w.writerow(line)
        n += 1
    data = buf.getvalue().encode('utf-8')
    fname = f'detalle_{year}_{period_key}.csv.gz'
    path = os.path.join(OUT_DIR, fname)
    # Si el contenido no cambió, no reescribir: el .gz guarda un timestamp en el
    # encabezado y reescribirlo haría que git vea los 54 archivos cambiados en cada
    # corrida del CI (≈37 MB nuevos por día en el historial).
    if os.path.exists(path):
        try:
            with gzip.open(path, 'rb') as f:
                if f.read() == data:
                    print(f'  {fname}: sin cambios ({n:,} filas)', flush=True)
                    return fname, n
        except Exception:
            pass
    gz = gzip.compress(data, 9, mtime=0)  # mtime fijo → salida determinística
    with open(path, 'wb') as f:
        f.write(gz)
    print(f'  {fname}: {n:,} filas | {len(gz)/1e6:.2f} MB gz (escrito)', flush=True)
    return fname, n


def main():
    # Sin timestamp: el manifest sólo cambia cuando cambian los archivos disponibles.
    manifest = {'archivos': {}}
    total = 0
    for y in bb.YEARS:
        # Período principal: cierre anual (o sancionado para el año de proyecto)
        try:
            fname, n = write_detalle(y, 'default', load_rows(y, None))
            manifest['archivos'][f'{y}_default'] = {'archivo': fname, 'filas': n}
            total += os.path.getsize(os.path.join(OUT_DIR, fname))
        except Exception as e:
            print(f'  {y} default: SKIP ({type(e).__name__}: {e})', flush=True)
        # Trimestres parciales (acumulado al trimestre)
        # Año en curso: todos los trimestres que existan (el 4T es su futuro cierre);
        # años cerrados: 1T-3T (el 4T es el cierre anual = 'default').
        quarters = (1, 2, 3, 4) if y == bb.YEAR_SANC else (1, 2, 3)
        for q in quarters:
            try:
                rows = load_rows(y, q)
            except FileNotFoundError:
                continue
            except Exception as e:
                print(f'  {y} {q}T: SKIP ({type(e).__name__}: {e})', flush=True)
                continue
            key = f'ejec-{q}T'
            fname, n = write_detalle(y, key, rows)
            manifest['archivos'][f'{y}_{key}'] = {'archivo': fname, 'filas': n}
            total += os.path.getsize(os.path.join(OUT_DIR, fname))
    with open(os.path.join(OUT_DIR, 'manifest.json'), 'w', encoding='utf-8') as f:
        json.dump(manifest, f, ensure_ascii=False, indent=0)
    print(f'\nTotal: {len(manifest["archivos"])} archivos, {total/1e6:.1f} MB')


if __name__ == '__main__':
    main()
