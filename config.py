# config.py
# Configurações globais do ValuaÇão BR
# Taxas, múltiplos setoriais e parâmetros de valuation para o mercado brasileiro.

# ---------------------------------------------------------------------------
# Taxas macroeconômicas
# ---------------------------------------------------------------------------
SELIC_ANUAL = 0.145       # 14.5% a.a. (jun/2026)
IPCA_PROJETADO = 0.045    # 4.5% a.a.
CDI_ANUAL = 0.144         # CDI aproximado

# ---------------------------------------------------------------------------
# Prêmio de risco por setor (adicional sobre Selic)
# ---------------------------------------------------------------------------
PREMIO_RISCO_SETOR = {
    'banco':          0.030,
    'seguro':         0.030,
    'energia':        0.040,
    'saneamento':     0.040,
    'telecom':        0.060,
    'mineracao':      0.070,
    'petroleo':       0.070,
    'papel_celulose': 0.060,
    'transmissao':    0.030,
}

# ---------------------------------------------------------------------------
# Bazin
# ---------------------------------------------------------------------------
DY_MINIMO_BAZIN = 0.06    # taxa mínima 6% a.a.

# ---------------------------------------------------------------------------
# Graham
# ---------------------------------------------------------------------------
MULTIPLICADOR_GRAHAM = 22.5
MARGEM_SEGURANCA_GRAHAM = 0.33   # 33%

# ---------------------------------------------------------------------------
# Filtros conservadores
# ---------------------------------------------------------------------------
MAX_DIVIDA_EBITDA = 3.0
MAX_CAPEX_EBITDA = 0.70
MIN_ROE = 0.10
MIN_DY_BAZIN = 0.04
MIN_ANOS_LUCRO_CONSECUTIVO = 3

# ---------------------------------------------------------------------------
# Método Buffett
# ---------------------------------------------------------------------------
BUFFETT_PL_MAXIMO = 15.0
BUFFETT_ANOS_PROJECAO = 10

# ---------------------------------------------------------------------------
# Fluxo de Caixa Descontado
# ---------------------------------------------------------------------------
ANOS_PROJECAO_FCD = 10
G_TERMINAL_PADRAO = IPCA_PROJETADO   # = 4.5%

# ---------------------------------------------------------------------------
# Múltiplos P/L de referência por setor
# ---------------------------------------------------------------------------
MULTIPLO_PL_SETOR = {
    'banco':          8.0,
    'seguro':        12.0,
    'energia':       10.0,
    'saneamento':    12.0,
    'telecom':       10.0,
    'mineracao':      7.0,
    'petroleo':       7.0,
    'papel_celulose':12.0,
    'transmissao':   11.0,
}

# ---------------------------------------------------------------------------
# Múltiplos EV/EBITDA de referência por setor
# ---------------------------------------------------------------------------
MULTIPLO_EV_EBITDA_SETOR = {
    'banco':          None,   # não aplicável
    'seguro':         None,
    'energia':         7.0,
    'saneamento':      8.0,
    'telecom':         6.0,
    'mineracao':       5.0,
    'petroleo':        5.0,
    'papel_celulose':  7.0,
    'transmissao':     9.0,
}

# ---------------------------------------------------------------------------
# Métodos de valuation por setor (ordem de prioridade)
# ---------------------------------------------------------------------------
METODOS_POR_SETOR = {
    'banco':          ['buffett', 'gordon', 'graham', 'bazin'],
    'seguro':         ['buffett', 'bazin', 'gordon', 'graham'],
    'energia':        ['bazin', 'fcd', 'gordon', 'buffett'],
    'saneamento':     ['fcd', 'bazin', 'ev_ebitda', 'buffett'],
    'telecom':        ['fcd', 'ev_ebitda', 'buffett'],
    'mineracao':      ['fcd', 'ev_ebitda', 'graham', 'buffett'],
    'petroleo':       ['fcd', 'ev_ebitda', 'gordon', 'buffett'],
    'papel_celulose': ['fcd', 'ev_ebitda', 'buffett'],
    'transmissao':    ['bazin', 'gordon', 'fcd', 'buffett'],
}

# ---------------------------------------------------------------------------
# Metadados da aplicação
# ---------------------------------------------------------------------------
VERSAO = '1.0.0'
APP_NOME = 'ValuaÇão BR'
APP_SUBTITULO = 'Análise de Preço Justo — Mercado Brasileiro'
