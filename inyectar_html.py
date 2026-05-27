"""Inyecta budget_data.json + ejecucion_provisoria.json en tablero-presupuesto.html.

Reemplaza dos bloques inline:
  - `const DATA = {...};`        <- budget_data.json
  - `const EJEC_PROV = {...};`   <- data/ejecucion_provisoria.json (si existe)

Necesario porque el dashboard es self-contained: lee ambos bloques inline (no por fetch).
Se corre después de build_budget_data.py y de data/parser_ejec_provisoria.py.
"""
import os, re, json

BASE = os.path.dirname(os.path.abspath(__file__))
JSON_F = os.path.join(BASE, 'budget_data.json')
PROV_F = os.path.join(BASE, 'data', 'ejecucion_provisoria.json')
HTML_F = os.path.join(BASE, 'tablero-presupuesto.html')

def main():
    data = open(JSON_F, encoding='utf-8').read().strip()
    html = open(HTML_F, encoding='utf-8').read()
    new, n = re.subn(r'const DATA\s*=\s*\{.*?\};', f'const DATA = {data};', html, count=1, flags=re.DOTALL)
    if n != 1:
        raise SystemExit('No pude encontrar `const DATA = {...};` en HTML')

    # Inyectar EJEC_PROV si existe el JSON de ejecución provisoria
    if os.path.exists(PROV_F):
        prov_data = open(PROV_F, encoding='utf-8').read().strip()
        new, m = re.subn(r'const EJEC_PROV\s*=\s*\{.*?\};', f'const EJEC_PROV = {prov_data};', new, count=1, flags=re.DOTALL)
        if m == 1:
            prov_obj = json.loads(prov_data)
            t = prov_obj.get('totals', {})
            dev = t.get('devengado', 0)
            pct = dev / t['sancion'] * 100 if t.get('sancion') else 0
            print(f'EJEC_PROV inyectado: {prov_obj.get("trim", "?")}T {prov_obj.get("year", "?")} | dev ${dev/1e9:,.2f} Bn ({pct:.1f}% del sancionado)')
        else:
            print('WARN: no encontre `const EJEC_PROV = {...};` en HTML — agregar manualmente o ignorar')
    else:
        print(f'Sin EJEC_PROV (JSON {PROV_F} no existe — parser no corrió o devolvió error)')

    open(HTML_F, 'w', encoding='utf-8').write(new)
    print(f'HTML actualizado: {len(data):,} bytes DATA + EJEC_PROV opcional')

if __name__ == '__main__':
    main()
