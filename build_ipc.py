"""Recalcula IPC_PROMEDIO_ANUAL en build_budget_data.py desde el XLSX IPCBA empalmado.

Lee data/IPCBA_empalmado.xlsx (jul-2012 → presente, base 2021=100), computa:
  - 2013-N: promedio anual simple de los 12 meses (rebase a 2019=100)
  - Año en curso (incompleto): IPC_prom_(prev) × ratio meses-disponibles-vs-mismo-período-año-anterior

Sobrescribe el bloque `IPC_PROMEDIO_ANUAL = {...}` en build_budget_data.py preservando el formato.
"""
import os, re, openpyxl, datetime

BASE = os.path.dirname(os.path.abspath(__file__))
XLSX = os.path.join(BASE, 'data', 'IPCBA_empalmado.xlsx')
SCRIPT = os.path.join(BASE, 'data', 'build_budget_data.py')

def cargar_mensuales():
    wb = openpyxl.load_workbook(XLSX, data_only=True)
    ws = wb['Nivel_general_empalme']
    monthly = {}
    for i, row in enumerate(ws.iter_rows(values_only=True)):
        if i < 4: continue
        dt, idx = row[0], row[1]
        if dt is None or idx is None: continue
        try: monthly[(dt.year, dt.month)] = float(idx)
        except (ValueError, TypeError): continue
    return monthly

def calcular_ipc():
    monthly = cargar_mensuales()
    if not monthly:
        raise SystemExit('IPCBA empalmado vacío')
    years = sorted({y for (y, _) in monthly.keys()})
    last_year_full = max(y for y in years if sum(1 for (yy, _) in monthly if yy == y) == 12)
    print(f'  IPCBA cargado: {len(monthly)} meses, {years[0]}–{years[-1]}; último año completo: {last_year_full}')

    annual = {}
    for y in years:
        meses = sorted([m for (yy, m) in monthly.keys() if yy == y])
        if len(meses) == 12:
            annual[y] = sum(monthly[(y, m)] for m in meses) / 12
        elif y > last_year_full and meses:
            # Año en curso: aplica ratio IPC anual previo × (avg_disponible_y / avg_mismos_meses_y-1)
            meses_prev = [m for m in meses if (y - 1, m) in monthly]
            if not meses_prev or (y - 1) not in annual: continue
            ratio = (sum(monthly[(y, m)] for m in meses_prev) / len(meses_prev)) / \
                    (sum(monthly[(y - 1, m)] for m in meses_prev) / len(meses_prev))
            annual[y] = annual[y - 1] * ratio
    base = annual[2019]
    rebased = {y: round(v / base * 100, 4) for y, v in annual.items() if y >= 2013}
    return rebased, last_year_full

def actualizar_script(ipc):
    txt = open(SCRIPT, encoding='utf-8').read()
    nuevo = 'IPC_PROMEDIO_ANUAL = {  # base 2019=100 (auto-generado por build_ipc.py)\n'
    for y in sorted(ipc):
        nuevo += f'    {y}: {ipc[y]:.4f},\n'
    nuevo += '}'
    out, n = re.subn(r'IPC_PROMEDIO_ANUAL = \{[^}]+\}', nuevo, txt, count=1, flags=re.DOTALL)
    if n != 1:
        raise SystemExit('No pude encontrar bloque IPC_PROMEDIO_ANUAL en build_budget_data.py')
    open(SCRIPT, 'w', encoding='utf-8').write(out)
    print(f'  build_budget_data.py actualizado con {len(ipc)} valores IPC')

def main():
    print('Recalculando IPC_PROMEDIO_ANUAL desde IPCBA empalmado...')
    ipc, last_full = calcular_ipc()
    for y in sorted(ipc):
        flag = ' (parcial)' if y > last_full else ''
        print(f'    {y}: {ipc[y]:>10.4f}{flag}')
    actualizar_script(ipc)

if __name__ == '__main__':
    main()
