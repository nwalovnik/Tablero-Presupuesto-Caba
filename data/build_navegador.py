"""Genera navegador_data.json: datos del Navegador 2013-2026 del tablero.

Árbol función / jurisdicción → programa → proyecto y obra / actividad, con la
serie anual completa de cada nodo (sancionado, vigente y devengado), más las
aperturas por inciso y partida principal, fuente, unidad ejecutora, subprograma
y comuna para el panel de detalle.

Fuentes (las mismas que budget_data.json):
  - 2013-2019: cierre (4T) del ZIP histórico de BA Data.
  - 2020-2025: cierre (4T) de los CSV pe-{año}-4.csv.
  - 2026: último CSV trimestral disponible (sancionado + vigente y devengado
    acumulados al trimestre); si no hay ninguno, el XLSX sancionado.
Mismos filtros que el resto del tablero: sin Aplicaciones Financieras (eco 23xx)
ni filas de subtotal (jurisdicción vacía).

Identidad de los nodos a lo largo de los años:
  - Jurisdicción: código (el 65 se parte en dos porque cambió de ministerio en
    2016). Se rotula con el nombre más reciente y se guarda el historial.
  - Programa: nombre normalizado (sin tildes, mayúsculas ni puntuación) dentro
    de la jurisdicción. Los códigos de programa se renumeran seguido; los nombres
    son más estables. Programas homónimos dentro de una jurisdicción se suman.
  - Proyecto / obra / actividad: nombre normalizado dentro del programa.

Montos en miles de pesos corrientes (enteros).
"""
import os, re, json, unicodedata, importlib.util
from collections import defaultdict, Counter

BASE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location('bb', os.path.join(BASE, 'build_budget_data.py'))
bb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bb)

OUT = os.path.join(BASE, '..', 'navegador_data.json')
P27_F = os.path.join(BASE, 'proyecto_2027.json')  # extracto de los cuadernos del Proyecto 2027
INC27 = {'Personal': '1', 'Bienes de consumo': '2', 'Servicios no personales': '3', 'Bienes de uso': '4',
         'Transferencias': '5', 'Activos financieros': '6', 'Servicio de la deuda': '7'}
YEARS = bb.YEARS
Y_LAST = bb.YEAR_SANC

FTE_COD = {'11': 'Tesoro de la Ciudad', '12': 'Recursos Propios', '13': 'Recursos con Afectación Específica',
           '14': 'Transferencias Afectadas', '15': 'Transferencias Internas', '16': 'Recursos Afectados Ley 3528',
           '21': 'Financiamiento Interno', '22': 'Financiamiento Externo'}
FIN_NOM = {'1': 'Administración Gubernamental', '2': 'Servicios de Seguridad', '3': 'Servicios Sociales',
           '4': 'Servicios Económicos', '5': 'Deuda Pública', '9': 'Gastos no Clasificados'}

SMALL = {'de', 'del', 'la', 'las', 'los', 'el', 'y', 'e', 'a', 'al', 'en', 'para', 'por', 'con', 'o', 'u', 'sin', 'sobre', 'entre'}
ROMAN = re.compile(r'^(i{1,3}|iv|v|vi{0,3}|ix|x{1,3})$', re.I)


def norm(s):
    s = unicodedata.normalize('NFD', (s or '').lower())
    s = ''.join(c for c in s if unicodedata.category(c) != 'Mn')
    s = re.sub(r'[^a-z0-9ñ]+', ' ', s)
    return ' '.join(s.split())


def accents(s):
    return sum(1 for c in s if c in 'áéíóúÁÉÍÓÚñÑüÜ')


# Palabra sin tildes → forma con tildes, aprendida de las fuentes que sí las traen
# (XLSX sancionado y CSV 2020+). Los CSV 2013-2019 vienen en mayúsculas sin tildes.
ACCENT = {}
JUR_NOMBRE = {  # rótulos de jurisdicción abreviados en la fuente
    '31': 'Ministerio de Infraestructura / Movilidad e Infraestructura',
    '45': 'Ministerio de Desarrollo Humano y Hábitat',
    '65': 'Ministerio de Modernización, Innovación y Tecnología',
    '70': 'Ministerio de Desarrollo Económico y Producción',
    '90': 'Secretaría de Gestión Comunal y Atención Ciudadana',
}

# Reorganizaciones que cortan las series por programa (se muestran en el detalle)
JUR_NOTA = {
    '40': 'En 2016 Salud reordenó sus programas: hasta 2015 la atención hospitalaria se presupuestaba por región '
          'sanitaria (Atención Médica Región Sanitaria I a IV); desde 2016, por tipo de atención (agudos, materno '
          'infantil, patologías específicas, rehabilitación…), con cada hospital como subprograma. Las series por '
          'programa se cortan ahí; el total del ministerio y la función Salud siguen siendo comparables.',
    '26': 'En 2024 se dividió en el Ministerio de Justicia (24) y el Ministerio de Seguridad (29). Para la serie larga '
          'de seguridad, usá «Ver por función» → Seguridad Interior.',
    '24': 'Hasta 2023 sus programas estaban en el Ministerio de Justicia y Seguridad (26).',
    '29': 'Hasta 2023 sus programas estaban en el Ministerio de Justicia y Seguridad (26). Para la serie larga, usá '
          '«Ver por función» → Seguridad Interior.',
    '30': 'Desde 2020 sus programas de obras y transporte pasaron a la Jefatura de Gabinete de Ministros y, en 2024, '
          'al Ministerio de Infraestructura (31). Para la serie larga, usá «Ver por función» → Transporte o Vivienda y Urbanismo.',
    '31': 'Hasta 2023 sus programas estaban en la Jefatura de Gabinete de Ministros y, antes de 2020, en el Ministerio '
          'de Desarrollo Urbano y Transporte (30).',
}


ERRATAS = {'hospítal'}  # tildes mal puestas en la fuente que no hay que propagar


def learn_accents(texts):
    cnt = defaultdict(Counter)
    for t in texts:
        for w in re.findall(r"[A-Za-zÁÉÍÓÚáéíóúÑñÜü]+", t or ''):
            if len(w) > 3 and accents(w) and w.lower() not in ERRATAS:
                cnt[norm(w)][w.lower()] += 1
    for k, c in cnt.items():
        ACCENT[k] = c.most_common(1)[0][0]


def fix_word(lw):
    if accents(lw) or len(lw) <= 3:
        return lw
    return ACCENT.get(norm(lw), lw)


def pretty(s):
    """Rótulo legible: tipo título con artículos en minúscula, tildes y siglas."""
    s = ' '.join((s or '').replace('\xa0', ' ').split())
    s = re.sub(r'\.(?=[A-Za-z])', '. ', s)  # "Min.Habitat" → "Min. Habitat"
    out = []
    for i, w in enumerate(s.split(' ')):
        lw = fix_word(w.lower())
        if i and lw in SMALL:
            out.append(lw)
        elif ROMAN.match(w) and len(w) > 1:
            out.append(w.upper())
        elif w.isupper() and len(w) <= 4 and any(c.isalpha() for c in w) and not s.isupper():
            out.append(w)  # sigla en un texto en minúsculas (GCBA, IVC, SBASE)
        else:
            m = re.match(r'^([^a-záéíóúñü]*)(.*)$', lw)  # «"jorge» → «"Jorge»
            out.append(m.group(1) + m.group(2)[:1].upper() + m.group(2)[1:])
    return ' '.join(out).replace('hàbitat', 'hábitat').replace('Hàbitat', 'Hábitat')


class Label:
    """Elige el mejor rótulo entre variantes de un mismo nombre normalizado:
    el del año más reciente, desempatando por cantidad de tildes."""
    def __init__(self):
        self.v = {}

    def add(self, key, raw, year):
        cur = self.v.get(key)
        cand = (year, accents(raw), raw)
        if cur is None or cand[:2] > cur[:2]:
            self.v[key] = cand

    def get(self, key):
        return pretty(self.v[key][2])


STOP = SMALL | {'programa', 'programas', 'prog', 'progr'}


def canon(n):
    """Nombre normalizado con equivalencias de escritura ("de la Caba" = "de la Ciudad de Buenos Aires")."""
    return re.sub(r'\b(ciudad (autonoma )?de buenos aires|c a b a|caba|ciudad autonoma)\b', 'caba', n)


def _tokens(n):
    return [t for t in canon(n).split() if t not in STOP and not t.isdigit()]


def similar(a, b):
    """Parecido entre dos nombres normalizados: tokens en común (admite
    abreviaturas por prefijo: "prev" ~ "prevencion") sobre el más corto,
    exigiendo además cubrir la mitad del más largo."""
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    if len(ta) > len(tb):
        ta, tb = tb, ta
    hit = sum(1 for t in ta if any(t == u or (len(t) >= 2 and len(u) >= 2 and (u.startswith(t) or t.startswith(u))) for u in tb))
    return hit / len(ta) if hit / len(tb) >= 0.5 else 0.0


def generic(n):
    """Programas de apoyo ("Actividades centrales", "Act. comunes a los programas ...")."""
    return bool(re.match(r'(act|activ\w*|actividades) (comu|centr)', n))


def g(r, *ks):
    for k in ks:
        v = r.get(k)
        if v not in (None, ''):
            return str(v).strip()
    return ''


def code(v):
    v = (v or '').strip()
    try:
        return str(int(float(v)))
    except ValueError:
        return v


def rec(r, year):
    """Fila cruda (cualquier esquema) → registro unificado o None si se excluye."""
    jur_d = g(r, 'jur_desc', 'desc_jur', 'desc_juris')
    if not jur_d:
        return None
    if g(r, 'eco', 'eco_cod', 'clas_economico').startswith('23'):
        return None
    s = bb.to_float_smart(g(r, 'sancion', 'sanci0n'))
    v = bb.to_float_smart(g(r, 'vigente', 'vigente_trim4_cont', 'vigente_trim3_cont', 'vigente_trim2_cont', 'vigente_trim1_cont'))
    d = bb.to_float_smart(g(r, 'devengado', 'devengado_trim4_cont', 'devengado_trim3_cont', 'devengado_trim2_cont', 'devengado_trim1_cont'))
    if not (s or v or d):
        return None
    # Fuente y comuna: el CSV 2022 viene corrido una columna (fte trae la
    # descripción y fte_desc el código de geografía).
    fte = g(r, 'fte', 'ff')
    if fte and not fte.isdigit():
        fte_n = fte
    else:
        fte_n = FTE_COD.get(code(fte)) or g(r, 'fte_desc', 'ff_desc', 'desc_fte')
    geo = g(r, 'geo_desc', 'desc_geo') if year != 2022 else g(r, 'geo')
    if re.fullmatch(r'\d+', geo or ''):
        geo = 'Comuna ' + str(int(geo))
    proy, act, obra = code(g(r, 'proy')), code(g(r, 'act', 'actividad')), code(g(r, 'obra', 'ob'))
    return {
        'jur': code(g(r, 'jur')), 'jur_d': jur_d,
        'ue_d': g(r, 'ue_desc', 'desc_ue'),
        'prog': code(g(r, 'prog')), 'prog_d': g(r, 'prog_desc', 'desc_prog', 'desc_programa'),
        'sprog': code(g(r, 'sprog')), 'sprog_d': g(r, 'sprog_desc', 'desc_sprog'),
        'proy': proy, 'proy_d': g(r, 'proy_desc', 'desc_proy'),
        'act': act, 'act_d': g(r, 'act_desc', 'desc_act'),
        'obra': obra, 'obra_d': g(r, 'obra_desc', 'ob_desc', 'desc_obra'),
        'fin': code(g(r, 'fin')), 'fun': code(g(r, 'fun')), 'fun_d': g(r, 'fun_desc', 'desc_fun', 'desc_fin_fun'),
        'inc': code(g(r, 'inciso', 'inc')), 'inc_d': g(r, 'inciso_desc', 'incisco_desc', 'inc_desc', 'desc_inc'),
        'ppal_d': g(r, 'ppal_desc', 'desc_ppal'),
        'fte_d': fte_n, 'geo_d': geo or 'Sin dato',
        's': s, 'v': v, 'd': d,
    }


def ipc_out(years):
    """IPC promedio anual del tablero; el año del proyecto se proyecta con la
    inflación que usa el análisis del Proyecto 2027 (21,54%)."""
    ipc = {str(k): v for k, v in bb.IPC_PROMEDIO_ANUAL.items()}
    for y in years:
        if str(y) not in ipc and os.path.exists(P27_F):
            infl = json.load(open(P27_F, encoding='utf-8'))['infl_2027']
            ipc[str(y)] = round(ipc[str(y - 1)] * (1 + infl), 4)
    return ipc


def xlsx_2026():
    import openpyxl
    path = os.path.join(BASE, f'presupuesto-sancionado-{Y_LAST}.xlsx')
    ws = openpyxl.load_workbook(path, read_only=True, data_only=True).active
    rows = ws.iter_rows(values_only=True)
    hdr = [str(h).lower().replace('ó', 'o') for h in next(rows)]
    out = []
    for row in rows:
        if row and row[0] is not None:
            out.append({hdr[i]: row[i] for i in range(min(len(hdr), len(row)))})
    return out


def load(year):
    """→ (registros, etiqueta del período)."""
    if year in bb.YEARS_HIST:
        return bb.load_year_from_zip(bb.HIST_ZIP, year, quarter=4), 'cierre'
    if year != Y_LAST:
        return bb.load_year(year, quarter=4), 'cierre'
    for q in (4, 3, 2, 1):
        if os.path.exists(os.path.join(BASE, f'pe-{year}-{q}.csv')):
            return bb.load_year(year, quarter=q), f'{q}T'
    return xlsx_2026(), 'sancionado'


def main():
    recs = {}
    periodo = {}
    for y in YEARS:
        rows, per = load(y)
        recs[y] = [x for x in (rec(r, y) for r in rows) if x]
        periodo[y] = per
        t = [sum(x[k] for x in recs[y]) / 1e9 for k in 'svd']
        print(f'{y} ({per}): {len(recs[y]):,} filas | sanc {t[0]:,.1f} vig {t[1]:,.1f} dev {t[2]:,.1f} (miles de M)', flush=True)

    texts = []
    for y in YEARS:
        if y >= 2020:
            for x in recs[y]:
                texts += [x['jur_d'], x['ue_d'], x['prog_d'], x['proy_d'], x['act_d'], x['obra_d'], x['ppal_d'], x['fun_d']]
    try:
        for r in xlsx_2026():
            texts += [str(r.get(k) or '') for k in r if k.startswith('desc_')]
    except Exception as e:
        print('  (sin XLSX para aprender tildes:', e, ')')
    learn_accents(texts)
    print(f'  {len(ACCENT):,} palabras con tilde aprendidas', flush=True)

    # ── Jurisdicciones: código, el 65 partido en 2016 ──
    def jkey(x, y):
        return '65a' if x['jur'] == '65' and y <= 2015 else x['jur']

    jur_year = defaultdict(dict)  # clave → año → rótulo de ese año
    for y in YEARS:
        for x in recs[y]:
            k = jkey(x, y)
            cur = jur_year[k].get(y)
            if cur is None or accents(x['jur_d']) > accents(cur):
                jur_year[k][y] = x['jur_d']
    jur_list = []
    for k, by_y in jur_year.items():
        hist = []
        for y in sorted(by_y):
            lab = pretty(by_y[y])
            if hist and norm(hist[-1][0]) == norm(lab) and hist[-1][2] == y - 1:
                hist[-1][2] = y
                if accents(lab) > accents(hist[-1][0]):
                    hist[-1][0] = lab
            else:
                hist.append([lab, y, y])
        jur_list.append({'k': k, 'name': JUR_NOMBRE.get(k, hist[-1][0]), 'hist': hist})
    order = lambda k: (int(re.sub(r'\D', '', k)), k)
    jur_list.sort(key=lambda j: order(j['k']))
    jur_idx = {j['k']: i for i, j in enumerate(jur_list)}

    # ── Funciones ──
    fun_lab = Label()
    fun_keys = set()
    for y in YEARS:
        for x in recs[y]:
            k = (x['fin'], x['fun'])
            fun_keys.add(k)
            fun_lab.add(k, x['fun_d'], y)
    # Una misma función que cambia de finalidad (Servicios Urbanos pasó de
    # Servicios Económicos a Servicios Sociales en 2020) se une por nombre y queda
    # en la finalidad más reciente.
    fun_last = defaultdict(int)
    for y in YEARS:
        for x in recs[y]:
            fun_last[(x['fin'], x['fun'])] = y
    groups = defaultdict(list)
    for k in fun_keys:
        groups[norm(fun_lab.get(k))].append(k)
    fun_list = sorted((max(ks, key=lambda k: fun_last[k]) for ks in groups.values()),
                      key=lambda k: (int(k[0] or 0), int(k[1] or 0)))
    fun_idx = {}
    for i, k in enumerate(fun_list):
        for kk in groups[norm(fun_lab.get(k))]:
            fun_idx[kk] = i

    # ── Continuidad de programas ──
    # Un programa que conserva el código de un año al siguiente y cambia poco el
    # nombre (abreviaturas, typos, "2014" al final) se trata como el mismo.
    parent = {}

    def find(k):
        while parent.get(k, k) != k:
            k = parent[k]
        return k

    def union(a, b):  # b se cuelga de a
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    by_code = {}  # año → (jur, código) → nombre normalizado de mayor monto
    for y in YEARS:
        m = defaultdict(Counter)
        for x in recs[y]:
            m[(jkey(x, y), x['prog'])][norm(x['prog_d'])] += abs(x['d']) + abs(x['s'])
        by_code[y] = {k: c.most_common(1)[0][0] for k, c in m.items()}
    linked = 0
    for y in YEARS[1:]:
        for (jk, c), nm in by_code[y].items():
            prev = by_code[y - 1].get((jk, c))
            if prev and prev != nm and (similar(prev, nm) >= 0.8 or (generic(prev) and generic(nm))):
                union((jk, nm), (jk, prev))  # el nombre más nuevo queda como raíz
                linked += 1
    print(f'  {linked} cambios de nombre de programa unidos por código', flush=True)

    # ── Programas, hojas y dimensiones de detalle ──
    prog_lab, leaf_lab, proj_lab = Label(), Label(), Label()
    prog_idx, leaf_idx = {}, {}
    prog_years = defaultdict(dict)  # índice → año → rótulo crudo de ese año
    dims = {k: {} for k in ('inc', 'ppal', 'fte', 'geo', 'ue', 'sprog')}
    dim_lab = {k: Label() for k in dims}

    def di(kind, key, raw, y):
        dim_lab[kind].add(key, raw, y)
        m = dims[kind]
        if key not in m:
            m[key] = len(m)
        return m[key]

    tree = defaultdict(lambda: [0.0, 0.0, 0.0])
    brk = defaultdict(lambda: [0.0, 0.0, 0.0])
    c2p = defaultdict(Counter)  # (jur, código de programa) en el último año → programa del navegador
    for y in YEARS:
        yi = YEARS.index(y)
        for x in recs[y]:
            jk = jkey(x, y)
            pk = find((jk, norm(x['prog_d'])))
            prog_lab.add(pk, x['prog_d'], y)
            if pk not in prog_idx:
                prog_idx[pk] = len(prog_idx)
            pi = prog_idx[pk]
            py = prog_years[pi]
            if y not in py or accents(x['prog_d']) > accents(py[y]):
                py[y] = x['prog_d']
            if y == Y_LAST:
                c2p[(x['jur'], x['prog'])][pi] += abs(x['s']) + abs(x['v'])
            # Hoja: actividad, o proyecto (+ obra / actividad del proyecto)
            if x['proy'] not in ('', '0'):
                pj = norm(x['proy_d'])
                proj_lab.add((pi, pj), x['proy_d'], y)
                if x['obra'] not in ('', '0'):
                    lk = (pi, 'O', pj, norm(x['obra_d']))
                    leaf_lab.add(lk, x['obra_d'], y)
                else:
                    lk = (pi, 'O', pj, norm(x['act_d']) or pj)
                    leaf_lab.add(lk, x['act_d'] or x['proy_d'], y)
            else:
                lk = (pi, 'A', '', norm(x['act_d']))
                leaf_lab.add(lk, x['act_d'], y)
            if lk not in leaf_idx:
                leaf_idx[lk] = len(leaf_idx)
            li = leaf_idx[lk]
            fi = fun_idx[(x['fin'], x['fun'])]
            amt = (x['s'], x['v'], x['d'])
            t = tree[(yi, fi, li)]
            for i in range(3):
                t[i] += amt[i]
            inc_i = di('inc', x['inc'] or norm(x['inc_d']), x['inc_d'], y)
            keys = [
                ('ppal', di('ppal', (x['inc'], norm(x['ppal_d'])), x['ppal_d'], y)),
                ('fte', di('fte', norm(x['fte_d']), x['fte_d'], y)),
                ('geo', di('geo', norm(x['geo_d']), x['geo_d'], y)),
                ('ue', di('ue', norm(x['ue_d']), x['ue_d'], y)),
            ]
            if x['sprog'] not in ('', '0'):
                keys.append(('sprog', di('sprog', (pi, norm(x['sprog_d'])), x['sprog_d'], y)))
            for kind, idx in keys:
                b = brk[(yi, fi, pi, kind, idx)]
                for i in range(3):
                    b[i] += amt[i]

    # ── Proyecto 2027 (cuadernos jurisdiccionales) ──
    years_out = list(YEARS)
    if os.path.exists(P27_F):
        P27 = json.load(open(P27_F, encoding='utf-8'))
        y27 = Y_LAST + 1
        yi27 = len(years_out)
        years_out.append(y27)
        periodo[y27] = 'proyecto'
        yi26 = YEARS.index(Y_LAST)
        leaf_pi = {li: lk[0] for lk, li in leaf_idx.items()}
        # reparto por función del sancionado del último año de cada programa
        fshare = defaultdict(Counter)
        for (yi, fi, li), a in tree.items():
            if yi == yi26 and a[0] > 0:
                fshare[leaf_pi[li]][fi] += a[0]
        fun_by_name = {norm(fun_lab.get(k)): fun_idx[k] for k in fun_list}
        how = Counter()
        pend = []
        for q in P27['progs']:
            jk = str(q['jur'])
            if jk not in jur_idx:
                jur_idx[jk] = len(jur_list)
                jur_list.append({'k': jk, 'name': pretty(q['jur_n']), 'hist': [[pretty(q['jur_n']), y27, y27]]})
            hj = jur_list[jur_idx[jk]]['hist']
            if hj[-1][2] == Y_LAST:
                hj[-1][2] = y27
            elif hj[-1][2] != y27:
                hj.append([pretty(q['jur_n']), y27, y27])
            pi = None
            if q['k26']:
                c = c2p.get((str(q['k26'][0]), str(q['k26'][2])))
                if c:
                    pi = c.most_common(1)[0][0]
                    how['código 2026'] += 1
            if pi is None:
                pk = find((jk, norm(q['prog_n'])))
                if pk in prog_idx:
                    how['nombre'] += 1
                else:
                    prog_idx[pk] = len(prog_idx)
                    how['nuevo'] += 1
                pi = prog_idx[pk]
            pk = next(k for k, v in prog_idx.items() if v == pi)
            prog_lab.add(pk, q['prog_n'], y27)
            prog_years[pi][y27] = q['prog_n']
            # funciones: como en el último año; si es nuevo, la función del cuaderno
            sh = fshare.get(pi)
            if not sh:
                sh = Counter({fun_by_name[norm(q['fun'])]: 1})
            tot_sh = sum(sh.values())
            lk = (pi, 'Z', '', 'proyecto')
            leaf_lab.add(lk, f'Proyecto {y27} (sin apertura por actividad u obra)', y27)
            if lk not in leaf_idx:
                leaf_idx[lk] = len(leaf_idx)
            li = leaf_idx[lk]
            parts = []
            for i, n, v in q['pp']:
                ic = INC27.get(i, 'sa')
                if ic == 'sa':
                    di('inc', 'sa', 'Sin apertura en el cuaderno', y27)
                parts.append(('ppal', di('ppal', (ic, norm(n) if ic != 'sa' else 'sin apertura'), n if ic != 'sa' else 'Sin apertura en el cuaderno', y27), v))
            for f, v in q['fte'].items():
                parts.append(('fte', di('fte', norm(f), f, y27), v))
            parts.append(('ue', di('ue', norm(q['ue_n']), q['ue_n'], y27), q['total']))
            for _, n, v in q['sub']:
                parts.append(('sprog', di('sprog', (pi, norm(n)), n, y27), v))
            cell = {fi: q['total'] * w / tot_sh for fi, w in sh.items()}
            cell.setdefault(fun_by_name[norm(q['fun'])], 0.0)
            pend.append((q, jk, pi, li, parts, cell))
        print(f'  Proyecto {y27}: {len(P27["progs"])} programas · {dict(how)}', flush=True)

        # Ajuste a la planilla 8 (función × jurisdicción): reparto proporcional
        # iterativo dentro de cada jurisdicción, con el total de cada programa fijo.
        jcode = {norm(q['jur_n']): str(q['jur']) for q in P27['progs']}
        target = defaultdict(float)
        for fin, fun, jur, v in P27['fun_jur']:
            target[(jcode[norm(jur)], fun_by_name[norm(fun)])] += v
        for jk in {x[1] for x in pend}:
            rows = [x for x in pend if x[1] == jk]
            cols = {f for (j, f) in target if j == jk}
            for x in rows:  # semilla mínima donde la planilla tiene la función
                for f in cols:
                    if x[5].get(f, 0) == 0 and f == fun_by_name[norm(x[0]['fun'])]:
                        x[5][f] = 1.0
            for f in cols:  # función de la planilla sin ningún programa candidato
                if not any(x[5].get(f, 0) for x in rows):
                    for x in rows:
                        x[5][f] = 1.0
            for _ in range(200):
                for f in cols:
                    cur = sum(x[5].get(f, 0) for x in rows)
                    if cur > 0:
                        k = target[(jk, f)] / cur
                        for x in rows:
                            if f in x[5]:
                                x[5][f] *= k
                for x in rows:
                    cur = sum(x[5].values())
                    if cur > 0:
                        k = x[0]['total'] / cur
                        for f in x[5]:
                            x[5][f] *= k
        for q, jk, pi, li, parts, cell in pend:
            for fi, amt in cell.items():
                if amt <= 0:
                    continue
                f = amt / q['total'] if q['total'] else 0
                t = tree[(yi27, fi, li)]
                for i in range(3):
                    t[i] += amt
                for kind, idx, v in parts:
                    b = brk[(yi27, fi, pi, kind, idx)]
                    for i in range(3):
                        b[i] += v * f
        # control: función según el reparto vs planilla 8
        pl = defaultdict(float)
        for fin, fun, jur, v in P27['fun_jur']:
            pl[fun_by_name.get(norm(fun), norm(fun))] += v
        est = defaultdict(float)
        for (yi, fi, li), a in tree.items():
            if yi == yi27:
                est[fi] += a[0]
        print('  función: estimado vs planilla 8 (miles de M)')
        for fi in sorted(set(est) | set(pl), key=lambda k: -pl.get(k, 0)):
            lab = fun_lab.get(fun_list[fi]) if isinstance(fi, int) else fi
            print(f'    {lab[:34]:34} {est.get(fi, 0)/1e9:10,.0f} {pl.get(fi, 0)/1e9:10,.0f}', flush=True)

    # inciso de cada partida principal
    inc_of_ppal = {}
    for (inc, _), i in dims['ppal'].items():
        inc_of_ppal[i] = dims['inc'].get(inc, -1)

    # Programa → [jurisdicción, rótulo, historial de nombres, viene de, pasa a].
    # "Viene de / pasa a": mismo nombre en otra jurisdicción que termina el año
    # anterior a que éste empiece, o ese mismo año (traspasos entre ministerios).
    # El navegador une la cadena en una sola serie.
    progs = [None] * len(prog_idx)
    for pk, i in prog_idx.items():
        hist = []
        for y, raw in sorted(prog_years[i].items()):
            lab = pretty(raw)
            if hist and norm(hist[-1][0]) == norm(lab):
                hist[-1][2] = y
            else:
                hist.append([lab, y, y])
        progs[i] = [jur_idx[pk[0]], prog_lab.get(pk), hist if len(hist) > 1 else [], -1, -1]
    span = {i: (min(py), max(py)) for i, py in prog_years.items()}
    # Se compara con todos los nombres que tuvo cada programa, y el traspaso puede
    # superponerse un año (el año del cambio el programa figura en los dos ministerios).
    def name_key(raw):
        nm = re.sub(r'^\d+ ', '', canon(norm(raw))).split()  # "Comuna 4" no es "Comuna 10"
        return ' '.join(t for t in nm if t not in SMALL)
    by_name = defaultdict(set)
    for pk, i in prog_idx.items():
        if pk[0] in ('98', '99'):  # OCT repite nombres de programas
            continue
        for raw in set(prog_years[i].values()) | {pk[1]}:
            nm = name_key(raw)
            if nm and not generic(norm(raw)):
                by_name[nm].add(i)
    cands = set()
    for name, idxs in by_name.items():
        for a in idxs:
            for b in idxs:
                if (progs[a][0] != progs[b][0] and span[a][0] < span[b][0] and span[a][1] < span[b][1]
                        and span[b][0] - 1 <= span[a][1] <= span[b][0]):
                    same = name_key(prog_years[a][span[a][1]]) == name_key(prog_years[b][span[b][0]])
                    cands.add((span[b][0] - span[a][1], same, a, b))
    moves = 0
    # primero los traspasos sin superposición y con el mismo nombre en el año del cambio
    for _, _, a, b in sorted(cands, key=lambda c: (-c[0], not c[1], c[2], c[3])):
        if progs[a][4] == -1 and progs[b][3] == -1:
            progs[a][4], progs[b][3] = b, a
            moves += 1
    print(f'  {moves} traspasos de programas entre jurisdicciones detectados', flush=True)
    leaves = [None] * len(leaf_idx)
    for lk, i in leaf_idx.items():
        pi, kind, pj, _ = lk
        leaves[i] = [pi, kind, leaf_lab.get(lk), proj_lab.get((pi, pj)) if kind == 'O' else '']

    K = 1000.0
    def pack(a):
        return [round(a[0] / K), round(a[1] / K), round(a[2] / K)]

    tree_rows = [[yi, fi, li] + pack(a) for (yi, fi, li), a in tree.items() if any(round(v / K) for v in a)]
    kinds = ['ppal', 'fte', 'geo', 'ue', 'sprog']
    brk_rows = [[yi, fi, pi, kinds.index(kind), idx] + pack(a)
                for (yi, fi, pi, kind, idx), a in brk.items() if any(round(v / K) for v in a)]
    tree_rows.sort()
    brk_rows.sort()

    def dim_out(kind):
        out = [None] * len(dims[kind])
        for k, i in dims[kind].items():
            out[i] = dim_lab[kind].get(k)
        return out

    result = {
        'years': years_out,
        'base': Y_LAST,  # año de los pesos constantes y año en curso
        'periodo': {str(y): periodo[y] for y in years_out},
        'ipc': ipc_out(years_out),
        'unidad': 'miles de pesos corrientes',
        'fin': FIN_NOM,
        'fun': [[k[0], fun_lab.get(k)] for k in fun_list],
        'jur': [[j['k'], j['name'], j['hist'], JUR_NOTA.get(j['k'], '')] for j in jur_list],
        'prog': progs,
        'leaf': leaves,
        'inc': dim_out('inc'),
        'ppal': [[n, inc_of_ppal[i]] for i, n in enumerate(dim_out('ppal'))],
        'fte': dim_out('fte'), 'geo': dim_out('geo'), 'ue': dim_out('ue'), 'sprog': dim_out('sprog'),
        'kinds': kinds,
        't': tree_rows,
        'b': brk_rows,
    }
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, separators=(',', ':'))
    print(f'\n{OUT}: {os.path.getsize(OUT)/1e6:.2f} MB | {len(jur_list)} jur, {len(progs)} programas, '
          f'{len(leaves)} hojas, {len(tree_rows):,} filas árbol, {len(brk_rows):,} filas detalle')


if __name__ == '__main__':
    main()
