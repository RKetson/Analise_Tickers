# -*- coding: utf-8 -*-
"""Script de validação dos cálculos de valuation."""
import sys
sys.stdout.reconfigure(encoding='utf-8')

from src.data_loader import carregar_dados_empresa, carregar_multiplos_setor
from src.models import calcular_todos
from src.formatters import formatar_moeda, calcular_margem, status_margem
import config

tickers = ['BBAS3', 'SAPR4', 'PETR4', 'VALE3', 'TAEE11', 'FIQE3']

for ticker in tickers:
    res  = carregar_dados_empresa(ticker)
    dados = res['dados']
    cfg   = res['empresa_config']
    setor = cfg.get('setor', '')
    preco = dados.get('preco_atual', 0)

    mult   = carregar_multiplos_setor().get(setor, {}).get('ev_ebitda')
    premio = config.PREMIO_RISCO_SETOR.get(setor, 0.05)
    wacc   = config.SELIC_ANUAL + premio

    params = {
        'wacc': wacc,
        'g_fcd': min(float(dados.get('crescimento_lucro_5a') or 0.06), 0.20),
        'g_gordon': min(float(dados.get('crescimento_dpa_5a') or 0.06), 0.20),
        'k_gordon': wacc,
        'taxa_bazin': 0.06,
        'bazin_usar_media': True,
        'margem_seguranca': 0.33,
        'multiplo_ev_ebitda': mult,
        'anos_projecao': 10,
        'g_terminal': 0.045,
    }

    calc = calcular_todos(dados, params)
    pm   = calc.get('_media')
    ms   = calcular_margem(preco, pm)
    txt, em = status_margem(ms)
    ms_pct = (ms or 0) * 100

    print(f"\n{'='*60}")
    print(f"{ticker} ({setor.upper()}) — WACC {wacc:.1%}")
    print(f"  Atual: {formatar_moeda(preco)} | Consenso: {formatar_moeda(pm)} | Margem: {ms_pct:+.1f}% {em}")
    print(f"  Status: {txt}")
    print()

    for m in ['graham', 'bazin', 'gordon', 'fcd', 'ev_ebitda']:
        r  = calc[m]
        pj = r.get('preco_justo')
        if r.get('valido'):
            ms_m = (calcular_margem(preco, pj) or 0) * 100
            print(f"  {m:12s}: {formatar_moeda(pj):>14s}  ({ms_m:+.1f}%)")
        else:
            err = r.get('erro', 'N/D')[:55]
            print(f"  {m:12s}: N/D  — {err}")

print(f"\n{'='*60}")
print("Validação concluída com sucesso!")
