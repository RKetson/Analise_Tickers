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
        if k == 'dpa_historico':
            empresa['dados']['dpa_historico'] = v
        elif k == 'num_acoes_milhoes_param':
            empresa['num_acoes_milhoes'] = v
        elif k == 'wacc':
            empresa['wacc'] = v
        else:
            empresa['dados'][k] = v

    empresa['dados_manuais_ativos'] = True
    empresa['data_referencia'] = datetime.now().strftime('%Y-%m-%d')
    
    path = os.path.join(DATA_DIR, 'companies.json')
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(base, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"Erro ao salvar dados manuais: {e}")
        return False

def salvar_premissas(ticker: str, premissas: dict) -> bool:
    """Salva premissas de valuation permanentemente no banco local."""
    base = carregar_base_json()
    if ticker.upper() not in base:
        return False
    
    empresa = base[ticker.upper()]
    if 'premissas_valuation' not in empresa:
        empresa['premissas_valuation'] = {}
        
    for k, v in premissas.items():
        empresa['premissas_valuation'][k] = v
        
    path = os.path.join(DATA_DIR, 'companies.json')
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(base, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"Erro ao salvar premissas: {e}")
        return False


# ---------------------------------------------------------------------------
# Camada Online: Apenas Preço
# ---------------------------------------------------------------------------

def _buscar_preco_online(ticker: str) -> float | None:
    """
    Busca o preço atual da ação via yfinance.
    Acrescenta '.SA' ao ticker para o mercado brasileiro (B3).
    """
    try:
        import yfinance as yf
        stock = yf.Ticker(ticker.upper() + '.SA')
        info = stock.info
        if info:
            preco = info.get('regularMarketPrice') or info.get('currentPrice')
            if preco:
                return float(preco)
    except Exception:
        pass
    return None

# ---------------------------------------------------------------------------
# Ponto de entrada principal
# ---------------------------------------------------------------------------

def carregar_dados_empresa(ticker: str) -> dict:
    """
    Carrega dados completos de uma empresa a partir da base JSON local.
    Sempre busca o preço atualizado online.
    """
    base = carregar_base_json()
    empresa_config = base.get(ticker.upper(), {})
    dados_json = dict(empresa_config.get('dados', {}))

    # Injetar número de ações como campo de dados (usado pelos modelos)
    if empresa_config.get('num_acoes_milhoes'):
        dados_json['num_acoes_milhoes_param'] = empresa_config['num_acoes_milhoes']
        
    # Garantir fallback se não existir
    if not dados_json.get('num_acoes_milhoes_param'):
        dados_json['num_acoes_milhoes_param'] = empresa_config.get('num_acoes_milhoes')

    sucesso_online = False
    erro_online = None

    # Tenta atualizar o preço
    preco = _buscar_preco_online(ticker)
    if preco is not None:
        dados_json['preco_atual'] = preco
        sucesso_online = True
    else:
        erro_online = "Falha ao obter preço online."

    return {
        'dados': dados_json,
        'fonte': 'json',
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


