"""
src/data_loader.py
Módulo de carregamento de dados com fallback multicamada para ações brasileiras.

Ordem de prioridade para dados online:
    1. fundamentus  — scraping do site fundamentus.com.br (mais completo para BR)
    2. yfinance     — API financeira com dados do Yahoo Finance
    3. Base JSON    — dados curados localmente (companies.json)

Os dados online são mesclados com a base JSON, priorizando dados online quando
disponíveis, mas preservando campos curados (alertas, setores, eventos, etc.).

Fluxo:
    carregar_dados_empresa(ticker)
        → tenta fundamentus
        → fallback: yfinance
        → fallback final: apenas dados do JSON
        → retorna resultado mesclado com metadados de fonte e sucesso
"""

import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'data',
)


# ---------------------------------------------------------------------------
# Carregamento de arquivos estáticos
# ---------------------------------------------------------------------------

def carregar_base_json() -> dict:
    """
    Carrega o arquivo data/companies.json com dados fundamentais curados.
    Se não existir, cria a partir de companies_template.json.

    Returns:
        dict: Mapa {ticker -> empresa_config}. Retorna {} em caso de falha.
    """
    path = os.path.join(DATA_DIR, 'companies.json')
    template_path = os.path.join(DATA_DIR, 'companies_template.json')
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        try:
            with open(template_path, 'r', encoding='utf-8') as f:
                template_data = json.load(f)
            # Salva o template como json principal para futuras edições manuais
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(template_data, f, ensure_ascii=False, indent=2)
            return template_data
        except FileNotFoundError:
            print(f'[data_loader] AVISO: {path} e template não encontrados. Usando base vazia.')
            return {}
    except json.JSONDecodeError as e:
        print(f'[data_loader] ERRO JSON em companies.json: {e}')
        return {}
    except Exception as e:
        print(f'[data_loader] ERRO ao carregar companies.json: {e}')
        return {}


def carregar_multiplos_setor() -> dict:
    """
    Carrega data/sector_multiples.json com múltiplos setoriais de referência.

    Returns:
        dict: Mapa {setor -> {pl, pvp, ev_ebitda, dy_min}}. Retorna {} em falha.
    """
    path = os.path.join(DATA_DIR, 'sector_multiples.json')
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}


def listar_tickers_disponiveis() -> list[str]:
    """
    Retorna lista de tickers disponíveis na base JSON local.

    Returns:
        list[str]: Lista de tickers ordenados alfabeticamente.
    """
    return sorted(carregar_base_json().keys())


def listar_empresas() -> list[dict]:
    """
    Retorna lista de empresas disponíveis na base JSON local.

    Returns:
        list[dict]: Lista de dicionários contendo 'ticker' e 'nome'.
    """
    base = carregar_base_json()
    empresas = [{'ticker': t, 'nome': info.get('nome', t)} for t, info in base.items()]
    return sorted(empresas, key=lambda x: x['ticker'])


def listar_acoes() -> list[dict]:
    """
    Retorna lista de ações disponíveis na base JSON local, excluindo
    ativos que estejam registrados como FIIs no portfólio ou pela sua classificação setorial.
    """
    import src.portfolio as pt
    
    todas = listar_empresas()
    port = pt.load_portfolio()
    
    fiis_pos = port.get('fiis', {}).get('posicoes', {})
    fiis_sim = port.get('fiis', {}).get('simulacoes', {})
    
    # Conjunto de tickers que são explicitamente cadastrados como FIIs na carteira
    tickers_fii = set(fiis_pos.keys()).union(set(fiis_sim.keys()))
    
    # Adicionar também FIIs que ainda não estão na carteira mas têm setor de FII
    base_json = carregar_base_json()
    for tk, info in base_json.items():
        setor = str(info.get('setor', '')).lower()
        # Se for um FII óbvio (termina em 11 e setor imobiliário)
        if tk.endswith('11') and any(s in setor for s in ['fundo', 'shopping', 'logística', 'logistica', 'laje', 'renda', 'papel', 'híbrido', 'fiagro']):
            tickers_fii.add(tk)
            
    acoes = [e for e in todas if e['ticker'] not in tickers_fii]
    return acoes


def adicionar_empresa(ticker: str, nome: str = '', setor: str = 'outros') -> bool:
    """
    Adiciona uma nova empresa à base JSON para ser listada e ter fallback.
    """
    base = carregar_base_json()
    if ticker.upper() in base:
        return False
    
    base[ticker.upper()] = {
        'nome': nome or ticker.upper(),
        'ticker': ticker.upper(),
        'setor': setor,
        'descricao': '',
        'num_acoes_milhoes': 1.0,
        'dados': {},
        'alertas_analista': [],
        'eventos_nao_recorrentes': [],
        'referencia_ri': '',
        'data_referencia': datetime.now().strftime('%Y-%m-%d')
    }
    
    path = os.path.join(DATA_DIR, 'companies.json')
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(base, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"Erro ao salvar empresa: {e}")
        return False


def salvar_dados_manuais(ticker: str, novos_dados: dict) -> bool:
    """
    Atualiza e salva manualmente os dados de uma empresa no companies.json.
    Isso garante que dados não encontrados online sejam salvos para futuras consultas.
    """
    base = carregar_base_json()
    if ticker.upper() not in base:
        return False
        
    empresa = base[ticker.upper()]
    # Remove chaves do dicionário de dados_orig que não são originais da base (como parametros extras que a UI poe)
    # Mas é mais fácil só fazer um update.
    
    if 'dados' not in empresa:
        empresa['dados'] = {}
        
    for k, v in novos_dados.items():
        if k in ['preco_atual', 'lpa', 'vpa', 'roe', 'ebitda_milhoes', 'fcl_milhoes', 'divida_liquida_milhoes', 'capex_milhoes', 'crescimento_lucro_5a', 'crescimento_dpa_5a']:
            empresa['dados'][k] = v
        elif k == 'dpa_historico':
            empresa['dados']['dpa_historico'] = v
        elif k == 'num_acoes_milhoes_param':
            empresa['num_acoes_milhoes'] = v
        elif k == 'wacc':
            empresa['wacc'] = v

    empresa['data_referencia'] = datetime.now().strftime('%Y-%m-%d')
    
    path = os.path.join(DATA_DIR, 'companies.json')
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(base, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"Erro ao salvar dados manuais: {e}")
        return False


# ---------------------------------------------------------------------------
# Camada 1: fundamentus
# ---------------------------------------------------------------------------

def _buscar_fundamentus(ticker: str) -> dict | None:
    """
    Busca dados via biblioteca fundamentus (scraping fundamentus.com.br).

    Normaliza os campos para o formato interno da aplicação.
    Os campos de valor (Cotacao, LPA, etc.) são convertidos para float.
    Os campos de escala (EBIT, Div.Liq) são convertidos para R$ milhões.

    Args:
        ticker: Código de negociação ex.: 'TAEE11', 'VALE3'.

    Returns:
        dict com chaves 'fonte', 'dados', 'timestamp' ou None em caso de falha.
    """
    try:
        import fundamentus  # type: ignore

        papel = fundamentus.get_papel(ticker)
        if papel is None or papel.empty:
            return None

        def _val(key: str, default=None):
            """Extrai e converte um campo do DataFrame fundamentus."""
            try:
                v = papel.get(key)
                if v is None:
                    return default
                # fundamentus retorna Series de um elemento
                raw = v.iloc[0] if hasattr(v, 'iloc') else v
                raw_str = str(raw).strip()
                if not raw_str or raw_str == '-':
                    return default
                
                is_percent = '%' in raw_str
                parsed = float(raw_str.replace(',', '.').replace('%', ''))
                
                if is_percent:
                    parsed = parsed / 100.0
                elif key in ['LPA', 'VPA', 'PL', 'PVP'] and '.' not in raw_str:
                    # Fundamentus converte "3,51" para "351", então dividimos por 100
                    parsed = parsed / 100.0
                
                return parsed
            except Exception:
                return default

        # fundamentus atualizou os nomes das colunas (ex: EBIT -> EBIT_12m)
        ebit_raw = _val('EBIT_12m')
        div_liq_raw = _val('Div_Liquida')
        patrim_raw = _val('Patrim_Liq')
        lucro_raw = _val('Lucro_Liquido_12m')

        dados: dict = {
            'preco_atual':              _val('Cotacao'),
            'lpa':                      _val('LPA'),
            'vpa':                      _val('VPA'),
            'pl':                       _val('PL'),
            'pvp':                      _val('PVP'),
            'dy':                       _val('Div_Yield'),
            'roe':                      _val('ROE'),
            # Converter de R$ absoluto → R$ milhões
            'ebitda_milhoes':           None, # PROIBIDO INFERIR EBITDA A PARTIR DO EBIT
            'divida_liquida_milhoes':   div_liq_raw / 1e6 if div_liq_raw else None,
            'patrimonio_liquido_milhoes': patrim_raw / 1e6 if patrim_raw else None,
            'lucro_liquido_milhoes':    lucro_raw / 1e6 if lucro_raw else None,
            # CAPEX não disponível no fundamentus
            'capex_milhoes':            None,
        }

        # Extrair Número de Ações exato via PL / VPA
        # A API do yfinance frequentemente retorna apenas as ações da classe (ex: PN) 
        # para empresas brasileiras, distorcendo o Valuation. O cálculo via PL/VPA 
        # é a forma mais precisa de descobrir o total absoluto de ações emitidas.
        vpa_val = dados['vpa']
        patrim_milhoes = dados['patrimonio_liquido_milhoes']
        if vpa_val and vpa_val > 0 and patrim_milhoes:
            dados['num_acoes_milhoes'] = patrim_milhoes / vpa_val
        else:
            dados['num_acoes_milhoes'] = None

        # Estimar DPA a partir de DY × preço
        if dados.get('dy') and dados.get('preco_atual'):
            dados['dpa_estimado'] = round(dados['dy'] * dados['preco_atual'], 4)

        return {
            'fonte': 'fundamentus',
            'dados': dados,
            'timestamp': datetime.now().isoformat(),
        }

    except ImportError:
        return None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Camada 2: yfinance
# ---------------------------------------------------------------------------

def _buscar_yfinance(ticker: str) -> dict | None:
    """
    Busca dados via yfinance (Yahoo Finance API).

    Acrescenta '.SA' ao ticker para o mercado brasileiro (B3).
    Tenta extrair histórico de dividendos e FCL dos demonstrativos.

    Args:
        ticker: Código de negociação ex.: 'VALE3'.

    Returns:
        dict com chaves 'fonte', 'dados', 'timestamp' ou None em caso de falha.
    """
    try:
        import yfinance as yf  # type: ignore

        stock = yf.Ticker(ticker + '.SA')
        info = stock.info

        if not info or not (info.get('regularMarketPrice') or info.get('currentPrice')):
            return None

        def _get(key: str, default=None):
            """Extrai campo do info dict com conversão segura para float."""
            v = info.get(key)
            if v is None or v == 'None' or v == 0:
                return default
            try:
                return float(v)
            except (TypeError, ValueError):
                return default

        # --- Histórico de dividendos (últimos 3 anos) ---
        dpa_historico: list[float] = []
        try:
            dividends = stock.dividends
            if dividends is not None and not dividends.empty:
                div_por_ano = dividends.groupby(dividends.index.year).sum()
                dpa_historico = [
                    round(float(v), 4)
                    for v in div_por_ano.iloc[-3:].values
                ]
        except Exception:
            dpa_historico = []

        # --- Fluxo de Caixa Livre (FCO − CAPEX) ---
        fcl: float | None = None
        capex: float | None = None
        try:
            cf = stock.cashflow
            if cf is not None and not cf.empty:
                op_cf_row = next(
                    (k for k in cf.index if 'operating' in k.lower() and 'cash' in k.lower()),
                    None,
                )
                capex_row = next(
                    (k for k in cf.index if 'capital' in k.lower() and 'expenditure' in k.lower()),
                    None,
                )
                if op_cf_row:
                    op_cf_val = cf.loc[op_cf_row].iloc[0]
                    if capex_row:
                        capex_val = cf.loc[capex_row].iloc[0]
                        # No yfinance, CAPEX é negativo → somar para obter FCL
                        fcl = (float(op_cf_val) + float(capex_val)) / 1e6
                        capex = abs(float(capex_val)) / 1e6
                    else:
                        fcl = float(op_cf_val) / 1e6
        except Exception:
            pass

        # --- Número de ações ---
        shares_raw = _get('sharesOutstanding')
        num_acoes_milhoes = shares_raw / 1e6 if shares_raw else None

        # --- Dívida líquida estimada ---
        divida_bruta = _get('totalDebt')
        caixa = _get('totalCash')
        divida_liquida = None
        if divida_bruta is not None and caixa is not None:
            divida_liquida = (divida_bruta - caixa) / 1e6

        dados: dict = {
            'preco_atual':                _get('regularMarketPrice') or _get('currentPrice'),
            'lpa':                        _get('trailingEps'),
            'vpa':                        _get('bookValue'),
            'pl':                         _get('trailingPE'),
            'pvp':                        _get('priceToBook'),
            'dy':                         _get('dividendYield'),
            'roe':                        _get('returnOnEquity'),
            'ebitda_milhoes':             _get('ebitda', 0.0) / 1e6 if _get('ebitda') else None,
            'divida_liquida_milhoes':     divida_liquida,
            'capex_milhoes':              capex,
            'fcl_milhoes':               fcl,
            'num_acoes_milhoes':          num_acoes_milhoes,
            'lucro_liquido_milhoes':      _get('netIncomeToCommon', 0.0) / 1e6 if _get('netIncomeToCommon') else None,
            'receita_liquida_milhoes':    _get('totalRevenue', 0.0) / 1e6 if _get('totalRevenue') else None,
            'dpa_historico':              dpa_historico,
        }

        return {
            'fonte': 'yfinance',
            'dados': dados,
            'timestamp': datetime.now().isoformat(),
        }

    except ImportError:
        return None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Mescla de dados
# ---------------------------------------------------------------------------

def _mesclar_dados(dados_online: dict, dados_json: dict) -> dict:
    """
    Mescla dados online com a base JSON curada.

    Prioridade: dados online sobrescrevem o JSON apenas se o valor online
    for não-None e não-zero. Campos críticos como 'dpa_historico' têm
    tratamento especial: o histórico online substitui o do JSON somente
    quando contém ≥ 2 anos de dados.

    Args:
        dados_online: Dict com dados obtidos de fundamentus/yfinance.
        dados_json: Dict com dados da base companies.json.

    Returns:
        dict: Dados mesclados priorizando informações online.
    """
    resultado = dict(dados_json)
    online = dados_online.get('dados', {})

    for chave, valor in online.items():
        if chave == 'dpa_historico':
            # Substituir histórico online apenas se tiver ≥ 2 anos
            if valor and len(valor) >= 2:
                resultado[chave] = valor
            # Caso contrário, mantém o JSON
        elif chave == 'dpa_estimado':
            # Usar DPA estimado para enriquecer, não substituir
            pass
        elif valor is not None and valor != 0:
            resultado[chave] = valor

    # Enriquecer dpa_historico com DPA estimado se histórico do JSON é incompleto
    dpa_estimado = online.get('dpa_estimado')
    if dpa_estimado and not resultado.get('dpa_historico'):
        resultado['dpa_historico'] = [dpa_estimado]

    return resultado


# ---------------------------------------------------------------------------
# Ponto de entrada principal
# ---------------------------------------------------------------------------

def carregar_dados_empresa(ticker: str, forcar_online: bool = False) -> dict:
    """
    Carrega dados completos de uma empresa usando fallback multicamada.

    Sempre enriquece os dados online com os campos curados do JSON local
    (setor, alertas de analista, eventos não-recorrentes, número de ações).

    Args:
        ticker: Código do ativo ex.: 'BBAS3', 'VALE3', 'TAEE11'.
        forcar_online: Se True, tenta buscar online mesmo que o JSON exista.
                       Padrão False prioriza velocidade para dados curados.

    Returns:
        dict com as seguintes chaves:
            dados             : dict — dados fundamentais mesclados
            fonte             : str  — 'fundamentus' | 'yfinance' | 'json' | 'misto'
            empresa_config    : dict — configuração completa da empresa no JSON
            sucesso_online    : bool — True se alguma fonte online foi usada
            erro_online       : str | None — mensagem de erro das fontes online
            timestamp         : str — ISO 8601 do momento da consulta
    """
    base = carregar_base_json()
    empresa_config = base.get(ticker.upper(), {})
    dados_json = dict(empresa_config.get('dados', {}))

    # Injetar número de ações como campo de dados (usado pelos modelos)
    if empresa_config.get('num_acoes_milhoes'):
        dados_json['num_acoes_milhoes_param'] = empresa_config['num_acoes_milhoes']

    resultado_online: dict | None = None
    fonte = 'json'
    erro_online: str | None = None
    sucesso_online = False

    # --- Camada 1: fundamentus ---
    try:
        resultado_online = _buscar_fundamentus(ticker.upper())
        if resultado_online:
            fonte = 'fundamentus'
            sucesso_online = True
    except Exception as exc:
        erro_online = f'fundamentus: {str(exc)[:120]}'

    # --- Camada 2: yfinance (fallback) ---
    if not resultado_online:
        try:
            resultado_online = _buscar_yfinance(ticker.upper())
            if resultado_online:
                fonte = 'yfinance'
                sucesso_online = True
            else:
                if erro_online:
                    erro_online += ' | yfinance: sem dados'
                else:
                    erro_online = 'yfinance: dados não encontrados para este ticker'
        except Exception as exc:
            yf_err = f'yfinance: {str(exc)[:120]}'
            erro_online = f'{erro_online} | {yf_err}' if erro_online else yf_err

    # --- Mescla e retorno ---
    if resultado_online and dados_json:
        dados_finais = _mesclar_dados(resultado_online, dados_json)
        fonte = 'misto'
    elif resultado_online:
        dados_finais = resultado_online.get('dados', {})
        # Injetar num_acoes mesmo sem JSON (pode vir do yfinance)
        if not dados_finais.get('num_acoes_milhoes_param'):
            dados_finais['num_acoes_milhoes_param'] = dados_finais.get('num_acoes_milhoes')
    else:
        dados_finais = dados_json
        fonte = 'json'

    # Garantir que num_acoes_milhoes_param está sempre presente
    if not dados_finais.get('num_acoes_milhoes_param'):
        dados_finais['num_acoes_milhoes_param'] = empresa_config.get('num_acoes_milhoes')

    return {
        'dados': dados_finais,
        'fonte': fonte,
        'empresa_config': empresa_config,
        'sucesso_online': sucesso_online,
        'erro_online': erro_online,
        'timestamp': datetime.now().isoformat(),
    }


# ---------------------------------------------------------------------------
# Função auxiliar: multiplo EV/EBITDA do setor para o ticker
# ---------------------------------------------------------------------------

def obter_multiplo_ev_ebitda(ticker: str) -> float | None:
    """
    Retorna o múltiplo EV/EBITDA de referência setorial para um ticker.

    Consulta primeiro o companies.json para identificar o setor,
    depois o sector_multiples.json para o múltiplo correspondente.

    Args:
        ticker: Código do ativo.

    Returns:
        float | None: Múltiplo EV/EBITDA setorial ou None se não disponível.
    """
    base = carregar_base_json()
    empresa = base.get(ticker.upper(), {})
    setor = empresa.get('setor')
    if not setor:
        return None

    multiplos = carregar_multiplos_setor()
    setor_data = multiplos.get(setor, {})
    return setor_data.get('ev_ebitda')


def obter_parametros_padrao(ticker: str) -> dict:
    """
    Retorna dicionário de parâmetros de valuation padrão para um ticker,
    baseado no setor e nas configurações globais do config.py.

    Usado para inicializar controles deslizantes na UI sem valores nulos.

    Args:
        ticker: Código do ativo.

    Returns:
        dict com parâmetros: wacc, g_fcd, g_gordon, k_gordon, taxa_bazin,
                              bazin_usar_media, margem_seguranca, multiplo_ev_ebitda,
                              anos_projecao, g_terminal.
    """
    import config  # import local para evitar circularidade

    base = carregar_base_json()
    empresa = base.get(ticker.upper(), {})
    setor = empresa.get('setor', '')
    dados = empresa.get('dados', {})

    # WACC = Selic + prêmio de risco do setor
    premio = config.PREMIO_RISCO_SETOR.get(setor, 0.05)
    wacc = config.SELIC_ANUAL + premio

    # Crescimentos históricos como ponto de partida
    g_lucro = dados.get('crescimento_lucro_5a', 0.06)
    g_dpa = dados.get('crescimento_dpa_5a', 0.06)

    # Ajuste conservador: limitar crescimento da fase 1 a 20%
    g_lucro = min(float(g_lucro) if g_lucro is not None else 0.06, 0.20)
    g_dpa = min(float(g_dpa) if g_dpa is not None else 0.06, 0.20)

    multiplo_ev = obter_multiplo_ev_ebitda(ticker)

    return {
        'wacc': round(wacc, 4),
        'g_fcd': round(g_lucro, 4),
        'g_gordon': round(g_dpa, 4),
        'k_gordon': round(wacc, 4),
        'taxa_bazin': config.DY_MINIMO_BAZIN,
        'bazin_usar_media': True,
        'margem_seguranca': config.MARGEM_SEGURANCA_GRAHAM,
        'multiplo_ev_ebitda': multiplo_ev,
        'anos_projecao': config.ANOS_PROJECAO_FCD,
        'g_terminal': config.G_TERMINAL_PADRAO,
    }

def salvar_metodo_principal(ticker: str, metodo: str) -> bool:
    """Salva o método de valuation principal para o ticker no companies.json."""
    base = carregar_base_json()
    if ticker.upper() not in base:
        return False
        
    base[ticker.upper()]['metodo_principal'] = metodo
    path = os.path.join(DATA_DIR, 'companies.json')
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(base, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"Erro ao salvar método principal: {e}")
        return False

def buscar_historico_trimestral(ticker: str) -> dict:
    """Busca o histórico financeiro trimestral via yfinance."""
    import yfinance as yf
    try:
        tk = yf.Ticker(ticker + '.SA')
        fin = tk.quarterly_financials
        bs = tk.quarterly_balance_sheet
        cf = tk.quarterly_cashflow
        
        return {
            'financials': fin,
            'balance_sheet': bs,
            'cashflow': cf
        }
    except Exception as e:
        print(f"Erro ao buscar histórico trimestral: {e}")
        return {}

