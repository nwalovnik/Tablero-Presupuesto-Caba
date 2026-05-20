"""Inyecta budget_data.json en tablero-presupuesto.html reemplazando el bloque `const DATA = {...};`.

Necesario porque el dashboard es un HTML self-contained: lee DATA del bloque inline (no por fetch).
Se corre después de build_budget_data.py.
"""
import os, re, json

BASE = os.path.dirname(os.path.abspath(__file__))
JSON_F = os.path.join(BASE, 'budget_data.json')
HTML_F = os.path.join(BASE, 'tablero-presupuesto.html')

def main():
    data = open(JSON_F, encoding='utf-8').read().strip()
    html = open(HTML_F, encoding='utf-8').read()
    new, n = re.subn(r'const DATA\s*=\s*\{.*?\};', f'const DATA = {data};', html, count=1, flags=re.DOTALL)
    if n != 1:
        raise SystemExit('No pude encontrar `const DATA = {...};` en HTML')
    open(HTML_F, 'w', encoding='utf-8').write(new)
    print(f'HTML actualizado: {len(data):,} bytes de DATA inyectados')

if __name__ == '__main__':
    main()
