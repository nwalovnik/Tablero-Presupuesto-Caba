"""Construye calendario.json con fechas oficiales del presupuesto CABA.

Datos hardcodeados con las publicaciones recurrentes:
  - Ejecución trimestral: ~45 días después de cierre de cada trimestre
  - Cuenta de inversión anual: 30 de junio del año siguiente
  - Proyecto sancionado: 15 de diciembre del año en curso (Ley)

Inyecta el JSON resultante en tablero-presupuesto.html dentro del <script id="calData">.
"""
import os, re, json, datetime

BASE = os.path.dirname(os.path.abspath(__file__))
OUT_JSON = os.path.join(BASE, 'calendario.json')
HTML = os.path.join(BASE, 'tablero-presupuesto.html')

URL_BA = 'https://data.buenosaires.gob.ar/dataset/presupuesto-ejecucion'
URL_CI = 'https://www.buenosaires.gob.ar/hacienda/cuenta-de-inversion'
URL_SAN = 'https://www.buenosaires.gob.ar/hacienda/presupuesto'

def trim_close(y, q):
    """Devuelve la fecha aproximada de publicación del trimestre q del año y (~45d post-cierre)."""
    cierres = {1: (5,15), 2: (8,15), 3: (11,15), 4: (3,15)}
    mm, dd = cierres[q]
    yr = y if q < 4 else y + 1
    return datetime.date(yr, mm, dd).isoformat()

def main():
    hoy = datetime.date.today()
    items = []

    # Trimestres de los próximos 2 años (con base año actual)
    for y in range(hoy.year - 1, hoy.year + 2):
        for q in range(1, 5):
            fecha = trim_close(y, q)
            prev_q = q - 1 or 4
            prev_y = y if q > 1 else y - 1
            items.append({
                'id': f'pe-q{q}',
                'label': f'Presupuesto ejecutado · Q{q} {y}',
                'descripcion': 'Ejecución trimestral · estructura programática',
                'freq': 'Trimestral',
                'ultimo_periodo': f'Q{prev_q} {prev_y}',
                'proxima_fecha': fecha,
                'proximo_periodo': f'Q{q} {y}',
                'url': URL_BA,
            })

    # Cuenta de inversión anual (30 jun del año siguiente)
    for y in range(hoy.year - 1, hoy.year + 2):
        items.append({
            'id': 'cinv',
            'label': f'Cuenta de Inversión {y}',
            'descripcion': 'Ejecución anual definitiva · formato cerrado',
            'freq': 'Anual',
            'ultimo_periodo': str(y - 1),
            'proxima_fecha': f'{y+1}-06-30',
            'proximo_periodo': str(y),
            'url': URL_CI,
        })

    # Presupuesto sancionado (Ley anual, ~15 dic)
    for y in range(hoy.year, hoy.year + 3):
        items.append({
            'id': 'sanc',
            'label': f'Presupuesto sancionado {y+1}',
            'descripcion': 'Ley anual de presupuesto',
            'freq': 'Anual',
            'ultimo_periodo': str(y),
            'proxima_fecha': f'{y}-12-15',
            'proximo_periodo': str(y+1),
            'url': URL_SAN,
        })

    # Filtrar: futuras + las últimas 2 ya publicadas (referencia)
    items.sort(key=lambda x: x['proxima_fecha'])
    futuras = [x for x in items if x['proxima_fecha'] >= hoy.isoformat()][:8]
    pasadas = [x for x in items if x['proxima_fecha'] < hoy.isoformat()][-2:]
    final = sorted(pasadas + futuras, key=lambda x: x['proxima_fecha'])

    out = {
        'generado': datetime.datetime.utcnow().isoformat(timespec='seconds'),
        'fuente': 'BA Data · data.buenosaires.gob.ar/dataset/presupuesto-ejecucion',
        'hoy': hoy.isoformat(),
        'presupuesto': final,
    }

    with open(OUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f'calendario.json: {len(final)} publicaciones')

    # Inyectar inline en HTML
    html = open(HTML, encoding='utf-8').read()
    payload = json.dumps(out, ensure_ascii=False, separators=(',', ':'))
    new, n = re.subn(r'(<script id="calData"[^>]*>)[^<]*(</script>)',
                     lambda m: m.group(1) + payload + m.group(2), html, count=1)
    if n == 1:
        open(HTML, 'w', encoding='utf-8').write(new)
        print('HTML actualizado con calendario inline')

if __name__ == '__main__':
    main()
