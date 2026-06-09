"""Descarga datos crudos del presupuesto CABA y del IPCBA.

Estrategia: cada archivo tiene una URL estable hardcodeada. Si la descarga
falla, mantiene la versión local previa (que viene committeada en el repo)
para que el build no rompa por una caída temporal del CDN.

Fuentes:
  - data.buenosaires.gob.ar — CSVs ejecutados 2020-2025 + ZIP histórico 2013-2019 + XLSX sancionado 2026
  - estadisticaciudad.gob.ar — XLSX IPCBA empalmado (mensual, base 2021=100)

Salida: archivos en data/ que build_budget_data.py espera.
"""
import os, sys, time, requests

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, 'data')
os.makedirs(DATA, exist_ok=True)

H = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                  '(KHTML, like Gecko) Chrome/120.0 Safari/537.36',
    'Accept': '*/*',
}
TIMEOUT = 60

BA = 'https://cdn.buenosaires.gob.ar/datosabiertos/datasets/ministerio-de-economia-y-finanzas'

# Cada entrada: (URL remota, nombre archivo local en data/)
ARCHIVOS = [
    # ZIP histórico 2013-2019 (~30 MB, estable, sólo si falta)
    (f'{BA}/presupuesto-ejecutado/historico_presupuesto_separados_por_cuatrimestres.zip',
     'historico_2013_2019.zip'),
    # CSVs ejecutados 2020-2025 (cierre anual = trimestre 4)
    (f'{BA}/presupuesto-ejecutado/presupuesto-ejecutado-2020-4-trimestre.csv', 'pe-2020-4.csv'),
    (f'{BA}/presupuesto-ejecutado/presupuesto-ejecutado-2021-4-trimestre.csv', 'pe-2021-4.csv'),
    (f'{BA}/presupuesto-ejecutado/presupuesto-ejecutado-2022-4.csv',           'pe-2022-4.csv'),
    (f'{BA}/presupuesto-ejecutado/presupuesto-ejecutado-2023-4.csv',           'pe-2023-4.csv'),
    (f'{BA}/presupuesto-ejecutado/presupuesto-ejecutado-2024-4.csv',           'pe-2024-4.csv'),
    (f'{BA}/presupuesto-ejecutado/presupuesto-ejecutado-2025-4.csv',           'pe-2025-4.csv'),
    # CSV ejecutado 2026 trimestres parciales (1T disponible; 2T/3T/4T en orden de publicación
    # — las que no existan aún devolverán 404 y se ignoran; cuando se publiquen, se descargan
    # automáticamente sin tocar el código).
    (f'{BA}/presupuesto-ejecutado/presupuesto-ejecutado-2026-1.csv',           'pe-2026-1.csv'),
    (f'{BA}/presupuesto-ejecutado/presupuesto-ejecutado-2026-2.csv',           'pe-2026-2.csv'),
    (f'{BA}/presupuesto-ejecutado/presupuesto-ejecutado-2026-3.csv',           'pe-2026-3.csv'),
    (f'{BA}/presupuesto-ejecutado/presupuesto-ejecutado-2026-4.csv',           'pe-2026-4.csv'),
    # XLSX sancionado 2026 (Ley 6929)
    (f'{BA}/presupuesto-sancionado/presupuesto-sancionado-2026.xlsx',          'presupuesto-sancionado-2026.xlsx'),
    # XLSX IPCBA empalmado (base 2021=100, mensual, jul-2012 → presente)
    ('https://www.estadisticaciudad.gob.ar/eyc/wp-content/uploads/2026/02/IPCBA_base_2021100-Nivel_general_empalme.xlsx',
     'IPCBA_empalmado.xlsx'),
]

def descargar(url, dest):
    """Descarga url → dest. Si falla, retorna False sin tocar el archivo previo."""
    print(f'  → {os.path.basename(dest)} ... ', end='', flush=True)
    try:
        r = requests.get(url, headers=H, timeout=TIMEOUT, stream=True)
        r.raise_for_status()
        tmp = dest + '.tmp'
        with open(tmp, 'wb') as f:
            for chunk in r.iter_content(chunk_size=65536):
                if chunk: f.write(chunk)
        os.replace(tmp, dest)
        print(f'OK ({os.path.getsize(dest):,} bytes)')
        return True
    except Exception as e:
        print(f'FAIL ({type(e).__name__}: {e})')
        if os.path.exists(dest):
            print(f'    (manteniendo versión previa de {os.path.basename(dest)})')
        return False

def main():
    print(f'Descargando datos a {DATA}/...')
    ok = 0
    fail = 0
    for url, fname in ARCHIVOS:
        dest = os.path.join(DATA, fname)
        # ZIP histórico: skip si ya existe (datos 2013-2019 son inmutables)
        if fname == 'historico_2013_2019.zip' and os.path.exists(dest):
            print(f'  → {fname} ... presente, skip')
            ok += 1
            continue
        if descargar(url, dest):
            ok += 1
        else:
            fail += 1
        time.sleep(0.3)
    print(f'\nDescarga completa: {ok} OK, {fail} fail')
    # No abortamos si fail>0: build_budget_data.py usa lo que haya.
    return 0

if __name__ == '__main__':
    sys.exit(main())
