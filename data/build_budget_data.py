"""Load CABA executed-budget CSVs 2013-2025 + sanctioned 2026 XLSX and output compact JSON."""
import json, csv, sys, os, zipfile, io
from collections import defaultdict

DATA_DIR = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(DATA_DIR, '..', 'budget_data.json')

# 2013-2019: cargados desde ZIP histórico (cuarto trimestre = cierre anual)
HIST_ZIP = os.path.join(DATA_DIR, 'historico_2013_2019.zip')
YEARS_HIST = [2013, 2014, 2015, 2016, 2017, 2018, 2019]
YEARS_EXEC = [2020, 2021, 2022, 2023, 2024, 2025]
YEAR_SANC = 2026
YEARS = YEARS_HIST + YEARS_EXEC + [YEAR_SANC]

# IPC_prom CABA — promedio anual, base 2019=100. Fuente: IDECBA (IPCBA).
# 2013-2015: proxy IPC GBA/Nacional (IPCBA suspendido ese período).
# 2016-2019: IPCBA retomado; 2020-2025: IDECBA; 2026: estimación.
# Fuente: IDECBA — IPCBA empalmado (base 2021=100 empalmada con la serie anterior
# base jul2011-jun2012=100). Datos mensuales jul-2012 a mar-2026. Archivo:
# https://www.estadisticaciudad.gob.ar/eyc/wp-content/uploads/2026/02/IPCBA_base_2021100-Nivel_general_empalme.xlsx
# Cálculo: promedio anual simple de los 12 meses para 2013-2025; rebase a 2019=100.
# 2026: IPC_prom_2025 × (avg(Jan-Mar 2026) / avg(Jan-Mar 2025)) — método de
# períodos comparables porque 2026 sólo tiene datos hasta marzo.
IPC_PROMEDIO_ANUAL = {  # base 2019=100 (auto-generado por build_ipc.py)
    2013: 15.6748,
    2014: 21.6439,
    2015: 27.3878,
    2016: 38.7235,
    2017: 49.3998,
    2018: 66.1730,
    2019: 100.0000,
    2020: 137.1328,
    2021: 196.2494,
    2022: 333.7382,
    2023: 780.2320,
    2024: 2544.6806,
    2025: 3725.4315,
    2026: 4919.8040,
}

TRIM_NOMBRE = {1: 'primer', 2: 'segundo', 3: 'tercer', 4: 'cuarto'}

def load_year_from_zip(zip_path: str, year: int, quarter: int = 4):
    """Load a quarterly CSV for a given year from the historico ZIP.

    quarter=4 (default) = cierre anual. Los archivos del ZIP se llaman
    presupuesto-ejecutado-YYYY-{primer|segundo|tercer|cuarto}-trimestre.csv
    y traen devengado ACUMULADO al trimestre."""
    nombre = TRIM_NOMBRE[quarter]
    with zipfile.ZipFile(zip_path, 'r') as zf:
        names = zf.namelist()
        candidates = [n for n in names if str(year) in n and nombre in n.lower()]
        if not candidates:
            raise FileNotFoundError(f'No CSV {nombre}-trimestre {year} in {zip_path}')
        chosen = candidates[0]
        print(f'  ZIP: using {chosen}')
        with zf.open(chosen) as raw:
            sample = raw.read(500)
        sep = detect_sep(sample)
        with zf.open(chosen) as raw:
            text = raw.read()
        for enc in ('utf-8-sig', 'cp1252', 'latin-1'):
            try:
                decoded = text.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        import io as _io
        reader = csv.DictReader(_io.StringIO(decoded), delimiter=sep)
        rows = list(reader)
    norm_rows = []
    for r in rows:
        nr = {}
        for k, v in r.items():
            if k is None: continue
            nk = k.lower().strip().replace('ó','o').replace('í','i').replace('á','a').replace('é','e').replace('ú','u')
            if nk.startswith('sumade'): nk = nk[6:]  # pe-2024-3 trae prefijo "SumaDe" en montos
            nr[nk] = v
        norm_rows.append(nr)
    return norm_rows


def detect_sep(sample: bytes) -> str:
    return ',' if sample.count(b',') > sample.count(b';') else ';'

def load_year(year: int, quarter: int = None):
    """Carga pe-{year}-{quarter}.csv. Si quarter es None, prefiere cierre anual
    (Q4) con fallback al último trimestre disponible."""
    path = None
    quarters = (quarter,) if quarter else (4, 3, 2, 1)
    for q in quarters:
        cand = os.path.join(DATA_DIR, f'pe-{year}-{q}.csv')
        if os.path.exists(cand):
            path = cand
            break
    if path is None:
        raise FileNotFoundError(f'No CSV for {year} (tried pe-{year}-{list(quarters)}.csv)')
    with open(path, 'rb') as f:
        sample = f.read(500)
    sep = detect_sep(sample)
    # try utf-8 then latin-1
    for enc in ('utf-8-sig','cp1252','latin-1'):
        try:
            with open(path, 'r', encoding=enc, newline='') as f:
                reader = csv.DictReader(f, delimiter=sep)
                rows = list(reader)
            break
        except UnicodeDecodeError:
            continue
    # normalize field names to lower
    norm_rows = []
    for r in rows:
        nr = {}
        for k, v in r.items():
            if k is None: continue
            nk = k.lower().strip().replace('ó','o').replace('í','i').replace('á','a').replace('é','e').replace('ú','u')
            if nk.startswith('sumade'): nk = nk[6:]  # pe-2024-3 trae prefijo "SumaDe" en montos
            nr[nk] = v
        norm_rows.append(nr)
    # Fix 2022 off-by-one: first column is composite ID, all labels shifted left
    if norm_rows and len(norm_rows) > 0:
        first = list(norm_rows[0].values())
        if first and isinstance(first[0], str) and first[0].count('-') >= 4:
            # Shift: new name for each column = old name of next column; last becomes None
            keys = list(norm_rows[0].keys())
            shifted_keys = ['_extra'] + keys[0:39] + keys[40:44]
            new_rows = []
            for r in norm_rows:
                vals = list(r.values())
                new_rows.append(dict(zip(shifted_keys, vals)))
            norm_rows = new_rows
    return norm_rows

def get_col(row, *keys):
    """Return first matching key (lowercase normalized)."""
    for k in keys:
        if k in row and row[k] not in (None, ''):
            return row[k]
    return None

def to_float(v):
    if v is None or v == '': return 0.0
    v = str(v).replace('.','').replace(',','.') if ',' in str(v) and '.' in str(v) else str(v).replace(',','.')
    # Handle: "94403424,34" → "94403424.34"
    # Handle: "94.403.424,34" → "94403424.34"
    # Already handled above
    try:
        return float(v)
    except ValueError:
        return 0.0

def to_float_smart(v):
    """Argentine number parsing: '.' = thousand sep, ',' = decimal."""
    if v is None or v == '': return 0.0
    s = str(v).strip().lstrip('-')
    neg = str(v).strip().startswith('-')
    if not s:
        return 0.0
    if ',' in s:
        s = s.replace('.','').replace(',','.')
    elif s.count('.') >= 2:
        s = s.replace('.','')
    elif s.count('.') == 1:
        a, b = s.split('.')
        if len(b) == 3:
            s = s.replace('.','')
    try:
        f = float(s)
        return -f if neg else f
    except ValueError:
        return 0.0

def agg_records(records, amount_key='devengado'):
    """records: list of dicts with keys jur,fin,fun,prog,inc,sparc + amount keys."""
    totals = {'sancion':0.0,'vigente':0.0,'devengado':0.0}
    by_jur = defaultdict(float)
    by_fin = defaultdict(float)
    by_fun = defaultdict(float)
    by_prog = defaultdict(float)
    by_inc = defaultdict(float)
    by_sparc = defaultdict(float)  # nivel máximo de desagregación del objeto del gasto
    sparc_meta = {}                # sparc_desc -> (inc_desc) parent (para etiquetar)
    vig_by_jur = defaultdict(float)
    jur_prog = defaultdict(float)   # (jur, prog) -> amount
    jur_fin = defaultdict(float)    # (jur, fin) -> amount
    for r in records:
        amt = r.get(amount_key,0.0)
        totals['devengado'] += r.get('devengado',0.0)
        totals['vigente'] += r.get('vigente',0.0)
        totals['sancion'] += r.get('sancion',0.0)
        j,f,fu,p,i = r.get('jur',''),r.get('fin',''),r.get('fun',''),r.get('prog',''),r.get('inc','')
        sp = r.get('sparc','')
        if j:
            by_jur[j] += amt
            vig_by_jur[j] += r.get('vigente',0.0)
        if f: by_fin[f] += amt
        if fu: by_fun[fu] += amt
        if p: by_prog[p] += amt
        if i: by_inc[i] += amt
        if sp:
            by_sparc[sp] += amt
            # asociar al padre inciso (primera vez gana)
            if sp not in sparc_meta and i:
                sparc_meta[sp] = i
        if j and p: jur_prog[j+'||'+p] += amt
        if j and f: jur_fin[j+'||'+f] += amt
    return {
        'totals': totals,
        'by_jur': dict(by_jur),
        'by_fin': dict(by_fin),
        'by_fun': dict(by_fun),
        'by_prog': dict(by_prog),
        'by_inc': dict(by_inc),
        'by_sparc': dict(by_sparc),
        'sparc_inc': sparc_meta,
        'vig_by_jur': dict(vig_by_jur),
        'jur_prog': dict(jur_prog),
        'jur_fin': dict(jur_fin),
    }

# Esquema viejo (CSVs trimestrales 2013-2015): no trae descripción de finalidad,
# sólo el código numérico. Mapeo con las mismas etiquetas .title() de los años nuevos.
FIN_COD = {
    '1': 'Administracion Gubernamental',
    '2': 'Servicios De Seguridad',
    '3': 'Servicios Sociales',
    '4': 'Servicios Economicos',
    '5': 'Deuda Publica - Intereses Y Gastos',
}

def agg_year_csv(rows):
    """For executed CSVs 2013-2025. Skips subtotal/total rows (empty jurisdiction)
    and Aplicaciones Financieras (Clas. Económica = 23xx: amortización de deuda
    e inversión financiera), siguiendo la convención del PDF oficial de cierre
    anual del GCBA: 'No incluye Gastos Figurativos ni Aplicaciones Financieras'."""
    records = []
    for r in rows:
        if not r: continue
        # 'desc_juris' / 'clas_economico' etc.: esquema viejo de los CSVs
        # trimestrales 2013-2015 dentro del ZIP histórico (minúsculas, nombres largos)
        jur = (get_col(r,'jur_desc','desc_jur','desc_juris') or '').strip()
        if not jur: continue  # skip grand-total rows present in some CSVs (e.g. 2019)
        eco_code = str(get_col(r,'eco','eco_cod','clas_economico') or '').strip()
        if eco_code.startswith('23'): continue  # skip Aplicaciones Financieras
        # Sparc (máximo nivel) cuando exista; fallback a Parc; último fallback a Ppal.
        # Esto mantiene cobertura histórica: 2013-2018 + 2024-2026 traen Sparc;
        # 2019-2023 traen sólo Ppal (un nivel arriba) — los etiquetamos con prefijo
        # «[grano grueso]» para que el dashboard pueda distinguir y normalizar.
        sparc_raw = (get_col(r,'desc_sparc','sparc_desc','desc_subparcial') or '').strip()
        parc_raw = (get_col(r,'desc_parc','parc_desc','desc_parcial') or '').strip()
        ppal_raw = (get_col(r,'desc_ppal','ppal_desc','desc_principal') or '').strip()
        if sparc_raw:
            sparc = sparc_raw.title()
        elif parc_raw:
            sparc = parc_raw.title()
        elif ppal_raw:
            sparc = ppal_raw.title()
        else:
            sparc = ''
        records.append({
            'devengado': to_float_smart(get_col(r,'devengado','devengado_trim4_cont','devengado_trim1_cont','devengado_trim2_cont','devengado_trim3_cont')),
            'vigente': to_float_smart(get_col(r,'vigente','vigente_trim4_cont','vigente_trim1_cont','vigente_trim2_cont','vigente_trim3_cont')),
            'sancion': to_float_smart(get_col(r,'sancion','sanci0n')),
            'jur': jur.title(),
            'fin': ((get_col(r,'fin_desc','desc_fin') or '').title()
                    or FIN_COD.get(str(get_col(r,'finalidad') or '').strip(), '')),
            'fun': (get_col(r,'fun_desc','desc_fun','desc_fin_fun') or '').title(),
            'prog': (get_col(r,'prog_desc','desc_prog','desc_programa') or '').title(),
            'inc': (get_col(r,'inc_desc','inciso_desc','incisco_desc','desc_inc','desc_inciso') or '').title(),
            'sparc': sparc,
        })
    return agg_records(records, amount_key='devengado')

def load_2026_xlsx():
    """Parse sanctioned 2026 XLSX from Downloads."""
    import openpyxl
    path = os.path.join(DATA_DIR, 'presupuesto-sancionado-2026.xlsx')
    if not os.path.exists(path):
        # fallback to Downloads
        alt = os.path.expanduser(r'~\Downloads\presupuesto-sancionado-2026.xlsx')
        path = alt if os.path.exists(alt) else path
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb.active
    hdr = None
    records = []
    for i,row in enumerate(ws.iter_rows(values_only=True)):
        if i==0:
            hdr = list(row)
            continue
        if not row or row[0] is None: continue
        d = dict(zip(hdr,row))
        # Skip Aplicaciones Financieras (eco code starts with 23)
        eco_val = str(d.get('Eco') or d.get('eco') or '').strip()
        if eco_val.startswith('23'): continue
        sanc_val = row[40] if len(row)>40 else 0  # Sanción column (encoding garbled name)
        try: sanc = float(sanc_val) if sanc_val is not None else 0.0
        except (ValueError,TypeError): sanc = 0.0
        # Sparc con fallback Parc/Ppal (mismo criterio que CSV ejecutados)
        sparc_raw = str(d.get('Desc_Sparc') or '').strip()
        parc_raw = str(d.get('Desc_Parc') or '').strip()
        ppal_raw = str(d.get('Desc_Ppal') or '').strip()
        sparc = (sparc_raw or parc_raw or ppal_raw).title()
        records.append({
            'devengado': 0.0, 'vigente': 0.0, 'sancion': sanc,
            'jur': str(d.get('Desc_Jur') or '').title(),
            'fin': str(d.get('Desc_Fin') or '').title(),
            'fun': str(d.get('Desc_Fun') or '').title(),
            'prog': str(d.get('Desc_Prog') or '').title(),
            'inc': str(d.get('Desc_Inc') or '').title(),
            'sparc': sparc,
        })
    return agg_records(records, amount_key='sancion')

def main():
    result = {'years': YEARS, 'year_sanc': YEAR_SANC, 'ipc_indice': IPC_PROMEDIO_ANUAL, 'data': {}}
    for y in YEARS_HIST:
        print(f'Loading {y} (historico ZIP)...', flush=True)
        rows = load_year_from_zip(HIST_ZIP, y)
        agg = agg_year_csv(rows)
        print(f'  rows:{len(rows):,} devengado:{agg["totals"]["devengado"]:,.0f}')
        result['data'][str(y)] = agg
    for y in YEARS_EXEC:
        print(f'Loading {y} (ejecutado)...', flush=True)
        rows = load_year(y)
        agg = agg_year_csv(rows)
        print(f'  rows:{len(rows):,} devengado:{agg["totals"]["devengado"]:,.0f}')
        result['data'][str(y)] = agg
    print(f'Loading {YEAR_SANC} (sanción XLSX)...', flush=True)
    agg26 = load_2026_xlsx()
    print(f'  sancion XLSX: {agg26["totals"]["sancion"]:,.0f}')
    result['data'][str(YEAR_SANC)] = agg26
    # Si hay CSV ejecutado parcial del año sanc (1T, 2T, etc.), parsearlo y guardarlo
    # como provisorio detallado (con by_sparc) — sobrescribe el provisorio del PDF
    # que es menos granular.
    csv_exec_paths = [(q, os.path.join(DATA_DIR, f'pe-{YEAR_SANC}-{q}.csv')) for q in (4,3,2,1)]
    csv_exec = next(((q,p) for q,p in csv_exec_paths if os.path.exists(p)), None)
    if csv_exec:
        q, path = csv_exec
        print(f'  + CSV ejecutado {q}T {YEAR_SANC} encontrado: {os.path.basename(path)}', flush=True)
        rows_exec = load_year(YEAR_SANC)
        agg26_exec = agg_year_csv(rows_exec)
        print(f'  CSV rows:{len(rows_exec):,} devengado:{agg26_exec["totals"]["devengado"]:,.0f}')
        agg26['provisorio_csv'] = {
            'trimestre': q,
            'ejercicio': YEAR_SANC,
            'etiqueta': f'{q}T {YEAR_SANC} ejecutado (CSV BA Data)',
            'totals': agg26_exec['totals'],
            'by_jur': agg26_exec['by_jur'],
            'by_fin': agg26_exec['by_fin'],
            'by_inc': agg26_exec['by_inc'],
            'by_sparc': agg26_exec['by_sparc'],
            'sparc_inc': agg26_exec.get('sparc_inc', {}),
            'source': f'pe-{YEAR_SANC}-{q}.csv (BA Data)',
        }

    # ── Ejecución trimestral acumulada (Q1-Q3) para TODOS los años ──
    # Permite comparar 1T vs 1T entre años y poblar todos los gráficos en
    # períodos parciales. Q4 no se duplica aquí: es el cierre anual (data
    # principal del año). Los CSVs trimestrales 2020+ no están commiteados
    # (pesan ~30MB c/u): se descargan en CI; si faltan, se preservan los
    # trims del budget_data.json previo.
    prev_trims = {}
    if os.path.exists(OUT):
        try:
            with open(OUT, 'r', encoding='utf-8') as f:
                prev_json = json.load(f)
            for ystr, ydata in prev_json.get('data', {}).items():
                if 'trims' in ydata:
                    prev_trims[ystr] = ydata['trims']
        except Exception as e:
            print(f'  (no pude leer trims previos: {e})')

    def compact_trim(agg, q):
        top_sparc = dict(sorted(agg.get('by_sparc', {}).items(), key=lambda x: -x[1])[:50])
        return {
            'trimestre': q,
            'totals': agg['totals'],
            'by_jur': agg['by_jur'],
            'by_fin': agg['by_fin'],
            'by_inc': agg['by_inc'],
            'by_prog': dict(sorted(agg['by_prog'].items(), key=lambda x: -x[1])[:30]),
            'by_sparc': top_sparc,
            'sparc_inc': {k: v for k, v in agg.get('sparc_inc', {}).items() if k in top_sparc},
        }

    for y in YEARS:
        trims = {}
        quarters = (1, 2, 3) if y != YEAR_SANC else (1, 2, 3, 4)
        for q in quarters:
            try:
                if y in YEARS_HIST:
                    rows_q = load_year_from_zip(HIST_ZIP, y, quarter=q)
                else:
                    csv_path = os.path.join(DATA_DIR, f'pe-{y}-{q}.csv')
                    if not os.path.exists(csv_path):
                        raise FileNotFoundError(csv_path)
                    rows_q = load_year(y, quarter=q)
                agg_q = agg_year_csv(rows_q)
                trims[str(q)] = compact_trim(agg_q, q)
                print(f'  trim {y}-{q}T: devengado {agg_q["totals"]["devengado"]:,.0f}')
            except FileNotFoundError:
                # CSV no disponible: heredar del JSON previo si existía
                prev_q = prev_trims.get(str(y), {}).get(str(q))
                if prev_q:
                    trims[str(q)] = prev_q
                    print(f'  trim {y}-{q}T: CSV ausente, preservado del JSON previo')
        if trims:
            result['data'][str(y)]['trims'] = trims

    # Merge ejecución provisoria (PDF GCBA Contaduría) si existe el JSON parseado
    prov_path = os.path.join(DATA_DIR, 'provisorio.json')
    if os.path.exists(prov_path):
        with open(prov_path, 'r', encoding='utf-8') as f:
            prov = json.load(f)
        ejercicio = prov.get('meta', {}).get('ejercicio')
        if ejercicio and str(ejercicio) in result['data']:
            # Source URL (si existe)
            src_url = ''
            src_path = os.path.join(DATA_DIR, 'provisorio_source.txt')
            if os.path.exists(src_path):
                with open(src_path, 'r', encoding='utf-8') as f:
                    lines = f.read().strip().split('\n')
                    if len(lines) >= 2: src_url = lines[1]
            # Adjuntar provisorio al año del ejercicio
            result['data'][str(ejercicio)]['provisorio'] = {
                'etiqueta': prov['meta'].get('etiqueta', ''),
                'trimestre': prov['meta'].get('trimestre'),
                'totals': prov['totals'],
                'by_jur': prov['by_jur'],
                'by_inc': prov['by_inc'],
                'by_fin': prov['by_fin'],
                'source_url': src_url,
                'source_pdf': prov.get('source_pdf', ''),
            }
            print(f'  + provisorio adjuntado a {ejercicio}: {prov["meta"].get("etiqueta")} | dev=${prov["totals"]["devengado"]:,.0f}')

    def round_tree(o, key=None):
        if isinstance(o, dict): return {k: round_tree(v, k) for k,v in o.items()}
        if isinstance(o, list): return [round_tree(v) for v in o]
        if isinstance(o, float):
            # Preserve decimals for IPC values (years 2013-2026 inside ipc_indice)
            if key and isinstance(key, (str,int)) and str(key).isdigit() and 2013 <= int(key) <= 2030:
                return round(o, 4)
            return round(o)
        return o
    result = round_tree(result)
    # Deduplicate jurisdictions with typographic differences (accents, dots, spaces)
    import unicodedata
    def norm_jur(s):
        s = s.strip().lower()
        s = ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')
        s = s.replace('.', ' ').replace(',', ' ')
        s = ' '.join(s.split())
        return s
    # Build canonical map: pick variant with most accented chars (richest form)
    variants = defaultdict(set)
    for y in YEARS:
        for jur in result['data'][str(y)].get('by_jur', {}):
            variants[norm_jur(jur)].add(jur)
        for t in result['data'][str(y)].get('trims', {}).values():
            for jur in t.get('by_jur', {}):
                variants[norm_jur(jur)].add(jur)
    canonical = {}
    for k, vs in variants.items():
        # prefer variant with accents (more complete)
        canonical[k] = max(vs, key=lambda x: sum(1 for c in x if unicodedata.category(c) == 'Mn' or c in 'áéíóúÁÉÍÓÚñÑ'))
    # Apply canonicalization across all dimensions that use jur as key
    for y in YEARS:
        d = result['data'][str(y)]
        for dim in ('by_jur', 'vig_by_jur'):
            new = defaultdict(int)
            for jur, v in d.get(dim, {}).items():
                new[canonical[norm_jur(jur)]] += v
            d[dim] = dict(new)
        for dim in ('jur_prog', 'jur_fin'):
            new = defaultdict(int)
            for k, v in d.get(dim, {}).items():
                jur, rest = k.split('||', 1)
                new[canonical[norm_jur(jur)] + '||' + rest] += v
            d[dim] = dict(new)
        for t in d.get('trims', {}).values():
            new = defaultdict(int)
            for jur, v in t.get('by_jur', {}).items():
                new[canonical[norm_jur(jur)]] += v
            t['by_jur'] = dict(new)
    # Deduplicate conceptos Sparc con diferencias tipográficas (tildes), igual que jur:
    # sin esto la serie histórica de un concepto se parte en dos claves distintas
    # (ej. "Productos Farmaceuticos" 2019-2023 vs "Productos Farmacéuticos" resto).
    def _sparc_sources(d):
        srcs = [d]
        if 'provisorio_csv' in d: srcs.append(d['provisorio_csv'])
        srcs.extend(d.get('trims', {}).values())
        return srcs
    sp_variants = defaultdict(set)
    for y in YEARS:
        for src in _sparc_sources(result['data'][str(y)]):
            for sp in src.get('by_sparc', {}):
                sp_variants[norm_jur(sp)].add(sp)
    sp_canon = {}
    for k, vs in sp_variants.items():
        sp_canon[k] = max(vs, key=lambda x: sum(1 for c in x if unicodedata.category(c) == 'Mn' or c in 'áéíóúÁÉÍÓÚñÑ'))
    for y in YEARS:
        for src in _sparc_sources(result['data'][str(y)]):
            if 'by_sparc' in src:
                new = defaultdict(int)
                for sp, v in src['by_sparc'].items():
                    new[sp_canon[norm_jur(sp)]] += v
                src['by_sparc'] = dict(new)
            if 'sparc_inc' in src:
                src['sparc_inc'] = {sp_canon[norm_jur(sp)]: v for sp, v in src['sparc_inc'].items()}
    # limit by_prog top 30, by_sparc top 50, keep by_jur/fin full, jur_prog full (filters)
    for y in YEARS:
        d = result['data'][str(y)]
        d['by_prog'] = dict(sorted(d['by_prog'].items(), key=lambda x:-x[1])[:30])
        if 'by_sparc' in d:
            d['by_sparc'] = dict(sorted(d['by_sparc'].items(), key=lambda x:-x[1])[:50])
            # Limpiar sparc_inc para que coincida con los 50 top
            if 'sparc_inc' in d:
                d['sparc_inc'] = {k: v for k, v in d['sparc_inc'].items() if k in d['by_sparc']}
        # También recortar by_sparc del provisorio_csv si existe (año sanc)
        if 'provisorio_csv' in d and 'by_sparc' in d['provisorio_csv']:
            pc = d['provisorio_csv']
            pc['by_sparc'] = dict(sorted(pc['by_sparc'].items(), key=lambda x:-x[1])[:50])
            if 'sparc_inc' in pc:
                pc['sparc_inc'] = {k: v for k, v in pc['sparc_inc'].items() if k in pc['by_sparc']}
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, separators=(',',':'))
    print(f'Wrote {OUT} ({os.path.getsize(OUT):,} bytes)')

if __name__ == '__main__':
    main()
