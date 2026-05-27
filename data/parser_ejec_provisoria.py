"""Parser de ejecuciones presupuestarias provisorias publicadas por GCBA Contaduría.

Scrapea https://buenosaires.gob.ar/.../ejecuciones-presupuestarias, detecta el
último PDF disponible del año en curso (preferentemente "definitivo", si no el
último trimestre "provisorio"), lo descarga y extrae los totales agregados +
breakdown por jurisdicción y por carácter económico (inciso).

Output: data/ejecucion_provisoria.json
"""
import json, re, os, sys, urllib.request, urllib.error, ssl
from datetime import datetime

DATA_DIR = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(DATA_DIR, 'ejecucion_provisoria.json')
PAGE_URL = 'https://buenosaires.gob.ar/gcaba_historico/haciendayfinanzas/direccion-general-contaduria/informacion-contable/ejecuciones-presupuestarias'

def parse_num(s):
    s = str(s).strip().replace('.', '').replace(',', '.')
    try: return float(s)
    except: return 0.0

def fetch_page(url):
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Tablero-Presupuesto-CABA)'})
    return urllib.request.urlopen(req, context=ctx, timeout=60).read().decode('utf-8', errors='replace')

def discover_latest_pdf(year_target=None):
    """Busca el último PDF disponible. Si year_target, lo limita a ese año."""
    html = fetch_page(PAGE_URL)
    # Match both absolute URLs and relative paths (the page emits relative paths
    # like /sites/default/files/2026-05/1ER_TRIM_2026.pdf, which resolve to the
    # static.buenosaires.gob.ar CDN).
    abs_urls = re.findall(r'(https?://[^\s"\']+?\.pdf)', html)
    rel_paths = re.findall(r'["\'](/sites/default/files/[^\s"\']+?\.pdf)["\']', html)
    candidates = list(abs_urls) + [f'https://static.buenosaires.gob.ar{p}' for p in rel_paths]
    # Annotate with year + trimester from filename
    parsed = []
    for url in candidates:
        fname = url.rsplit('/', 1)[-1]
        m_year = re.search(r'(20\d{2})', fname)
        if not m_year: continue
        y = int(m_year.group(1))
        if year_target and y != year_target: continue
        # Trimester from filename
        trim = 0
        if re.search(r'4[Tt][Oo]?[_\-\s]*TRIM', fname, re.I): trim = 4
        elif re.search(r'3[Ee][Rr][_\-\s]*TRIM|3ERTRIM|3ER[_\-\s]TRIM', fname, re.I): trim = 3
        elif re.search(r'2[Dd][Oo]?[_\-\s]*TRIM', fname, re.I): trim = 2
        elif re.search(r'1[Ee][Rr][_\-\s]*TRIM', fname, re.I): trim = 1
        # Detect "definitivo" (usually no "trim" suffix or has CUENTA INVERSION)
        is_definitivo = bool(re.search(r'definitiv|cuenta', fname, re.I))
        parsed.append({'url': url, 'fname': fname, 'year': y, 'trim': trim, 'definitivo': is_definitivo})
    if not parsed: return None
    # Sort: prefer definitivo, then highest year, then highest trim
    parsed.sort(key=lambda x: (x['year'], 1 if x['definitivo'] else 0, x['trim']), reverse=True)
    return parsed[0]

def download_pdf(url, path):
    """Descarga el PDF usando curl para manejar bien redirects/SSL/encoding."""
    import subprocess
    r = subprocess.run(['curl', '-sL', '--fail', '-o', path, url], capture_output=True, text=True, timeout=180)
    if r.returncode != 0:
        raise RuntimeError(f'curl failed: {r.stderr}')
    if os.path.getsize(path) < 1000:
        raise RuntimeError(f'PDF demasiado chico ({os.path.getsize(path)}b), posible error')

def extract_data(pdf_path, trim):
    """Extrae totales + breakdown por jurisdicción y carácter económico."""
    import pdfplumber
    out = {'totals': {}, 'by_inciso': {}, 'by_jur': {}}
    with pdfplumber.open(pdf_path) as pdf:
        for i, p in enumerate(pdf.pages):
            t = p.extract_text() or ''
            up = t.upper()
            # Page con totales por Nivel Institucional
            if 'NIVEL INSTITUCIONAL' in up and 'TOTAL' in up and out['totals'] == {}:
                for line in t.split('\n'):
                    m = re.search(r'TOTAL\s*\(?\*?\*?\)?\s+([\d\.\,]+)\s+([\d\.\,]+)\s+([\d\.\,]+)\s+([\d\.\,]+)', line)
                    if m:
                        out['totals'] = {'sancion': parse_num(m.group(1)), 'vigente': parse_num(m.group(2)),
                                         'definitivo': parse_num(m.group(3)), 'devengado': parse_num(m.group(4))}
                        break
            # Page con breakdown por carácter económico (inciso): codes 211-224
            if 'CAR' in up and 'CONOMIC' in up and not out['by_inciso']:
                for line in t.split('\n'):
                    m = re.match(r'^\s*(\d{3})\s+(.+?)\s+([\d\.,]+)\s+([\d\.,]+)\s+([\d\.,]+)\s+([\d\.,]+)\s*$', line)
                    if m and m.group(1).startswith(('21','22')):  # 211-224 son incisos económicos, 23x APF excluidos
                        if m.group(1).startswith('23'): continue
                        out['by_inciso'][m.group(2).strip().title()] = parse_num(m.group(6))
            # Page con breakdown por jurisdicción (PROGRAMA)
            if 'JURISDICCI' in up and 'PROGRAMA' in up:
                for line in t.split('\n'):
                    # Solo filas jur-level (no UE, no PROG): empieza con código corto + descripción
                    m = re.match(r'^\s*(\d{1,2})\s+([A-ZÁÉÍÓÚÑa-záéíóúñ][a-záéíóúñA-ZÁÉÍÓÚÑ\.\-\s]+?)\s+([\d\.,]+)\s+([\d\.,]+)\s+([\d\.,]+)\s+([\d\.,]+)\s*$', line)
                    if m:
                        code = int(m.group(1))
                        desc = m.group(2).strip()
                        # Filtrar las filas de "Carácter" (Admin Central, Org Descentralizados)
                        if code in (1, 2) and 'central' in desc.lower(): continue
                        if code in (1, 2) and 'descentralizad' in desc.lower(): continue
                        # Quedarse con la primera ocurrencia de cada código
                        if desc not in out['by_jur']:
                            out['by_jur'][desc.title()] = parse_num(m.group(6))
    return out

def main():
    year = datetime.now().year
    print(f'Buscando ejecución provisoria/definitiva para {year}...', flush=True)
    info = discover_latest_pdf(year_target=year)
    if not info:
        # Fallback: año anterior si no hay nada del actual
        info = discover_latest_pdf(year_target=year-1)
    if not info:
        print('No se encontró ningún PDF de ejecución.', file=sys.stderr)
        sys.exit(1)
    print(f'PDF más reciente: {info["fname"]}  (año={info["year"]} trim={info["trim"]} definitivo={info["definitivo"]})', flush=True)
    local_pdf = os.path.join(DATA_DIR, 'ejec_latest.pdf')
    if not os.path.exists(local_pdf) or os.path.getsize(local_pdf) == 0:
        print('Descargando...', flush=True)
        download_pdf(info['url'], local_pdf)
    data = extract_data(local_pdf, info['trim'])
    result = {
        'year': info['year'],
        'trim': info['trim'],
        'definitivo': info['definitivo'],
        'pdf_url': info['url'],
        'pdf_filename': info['fname'],
        'fetched_at': datetime.now().isoformat(timespec='seconds'),
        **data,
    }
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    t = result['totals']
    if t:
        pct = t['devengado'] / t['sancion'] * 100 if t['sancion'] else 0
        print(f'Total devengado al {info["trim"]}T {info["year"]}: ${t["devengado"]/1e9:,.2f} Bn  ({pct:.1f}% del sancionado)')
    print(f'Jurisdicciones: {len(result["by_jur"])}, Incisos: {len(result["by_inciso"])}')
    print(f'Wrote {OUT}')

if __name__ == '__main__':
    main()
