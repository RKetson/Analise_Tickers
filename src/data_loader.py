"""
src/data_loader.py
Módulo de carregamento de dados com fallback multicamada para ações brasileiras.

Ordem de prioridade para dados online:
    1. fundamentus  — scraping do site fundamentus.com.br (mais completo para BR)
    2. yfinance     — API financeira com dados do Yahoo Finance
    3. Banco de Dados — dados curados localmente (analise_tickers.sqlite)

Os dados online são mesclados com a base local, priorizando dados online quando
disponíveis, mas preservando campos curados (alertas, setores, eventos, etc.).
"""

import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database import SessionLocal
from src.db_models import Company, AppConfig

DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'data',
)

# ---------------------------------------------------------------------------
# Carregamento do Banco de Dados
# ---------------------------------------------------------------------------

def obter_empresa(ticker: str) -> dict:
    """Retorna os dados configurados para um único ticker a partir do BD."""
    ticker = ticker.upper()
    db = SessionLocal()
    try:
        c = db.query(Company).filter_by(ticker=ticker).first()
        if c:
            return {
                'nome': c.nome,
                'ticker': c.ticker,
                'setor': c.setor,
                'descricao': c.descricao,
                'num_acoes_milhoes': c.num_acoes_milhoes,
                'dados': dict(c.dados) if c.dados else {},
                'alertas_analista': list(c.alertas_analista) if c.alertas_analista else [],
                'eventos_nao_recorrentes': list(c.eventos_nao_recorrentes) if c.eventos_nao_recorrentes else [],
                'referencia_ri': c.referencia_ri,
                'data_referencia': c.data_referencia,
                'premissas_valuation': dict(c.premissas_valuation) if c.premissas_valuation else {},
                'metodo_principal': c.metodo_principal,
                'dados_manuais_ativos': bool(c.dados_manuais_ativos)
            }
        return {}
    finally:
        db.close()

def obter_setores(tickers: list[str]) -> dict:
    """Retorna o setor apenas para os tickers solicitados {ticker: setor}."""
    db = SessionLocal()
    try:
        tickers = [t.upper() for t in tickers]
        results = db.query(Company.ticker, Company.setor).filter(Company.ticker.in_(tickers)).all()
        return {t: s or 'Outros' for t, s in results}
    finally:
        db.close()

def carregar_multiplos_setor() -> dict:
    """
    Retorna múltiplos setoriais a partir do AppConfig.
    """
    db = SessionLocal()
    try:
        config = db.query(AppConfig).filter_by(chave='sector_multiples').first()
        return dict(config.valor) if config and config.valor else {}
    except Exception:
        return {}
    finally:
        db.close()

def listar_tickers_disponiveis() -> list[str]:
    """Retorna lista de tickers ordenados."""
    db = SessionLocal()
    try:
        tickers = db.query(Company.ticker).all()
        return sorted([t[0] for t in tickers])
    finally:
        db.close()

def listar_empresas() -> list[dict]:
    db = SessionLocal()
    try:
        companies = db.query(Company.ticker, Company.nome).all()
        empresas = [{'ticker': t, 'nome': n or t} for t, n in companies]
        return sorted(empresas, key=lambda x: x['ticker'])
    finally:
        db.close()

def listar_acoes() -> list[dict]:
    import src.portfolio as pt
    
    port = pt.load_portfolio()
    fiis_pos = port.get('fiis', {}).get('posicoes', {})
    fiis_sim = port.get('fiis', {}).get('simulacoes', {})
    
    tickers_fii_portfolio = set(fiis_pos.keys()).union(set(fiis_sim.keys()))
    
    db = SessionLocal()
    try:
        companies = db.query(Company.ticker, Company.nome, Company.setor).all()
        acoes = []
        
        fii_keywords = ['fundo', 'shopping', 'logística', 'logistica', 'laje', 'renda', 'papel', 'híbrido', 'fiagro']
        whitelist_units = ['KLBN11', 'TAEE11', 'SANB11', 'ALUP11', 'BPAC11', 'ENGI11', 'SULA11', 'SAPR11', 'TIET11', 'BIDI11', 'RNEW11']
        
        for t, n, s in companies:
            if t in tickers_fii_portfolio:
                continue
                
            s_lower = (s or '').lower()
            is_fii_sector = any(k in s_lower for k in fii_keywords)
            
            # Exceção: "Papel Celulose" é ação, não FII de Papel
            if 'celulose' in s_lower:
                is_fii_sector = False
                
            if is_fii_sector:
                continue
                
            # Excluir possíveis FIIs por ticker, exceto se for uma Unit conhecida
            if t.endswith('11') and len(t) == 6 and t not in whitelist_units:
                continue
                
            acoes.append({'ticker': t, 'nome': n or t})
                
        return sorted(acoes, key=lambda x: x['ticker'])
    finally:
        db.close()

def adicionar_empresa(ticker: str, nome: str = '', setor: str = 'outros') -> bool:
    ticker = ticker.upper()
    db = SessionLocal()
    try:
        if db.query(Company).filter_by(ticker=ticker).first():
            return False
            
        company = Company(
            ticker=ticker,
            nome=nome or ticker,
            setor=setor,
            descricao='',
            num_acoes_milhoes=1.0,
            dados={},
            data_referencia=datetime.now().strftime('%Y-%m-%d')
        )
        db.add(company)
        db.commit()
        return True
    except Exception as e:
        db.rollback()
        print(f"Erro ao salvar empresa no BD: {e}")
        return False
    finally:
        db.close()

def salvar_setor(ticker: str, setor: str) -> bool:
    ticker = ticker.upper()
    
    # Normalização do setor
    if setor:
        setor = str(setor).replace('_', ' ').strip().title()
    else:
        setor = 'Outros'
        
    db = SessionLocal()
    try:
        company = db.query(Company).filter_by(ticker=ticker).first()
        if company:
            company.setor = setor
            db.commit()
            return True
        return False
    except Exception as e:
        db.rollback()
        print(f"Erro ao salvar setor no BD: {e}")
        return False
    finally:
        db.close()

def salvar_dados_manuais(ticker: str, novos_dados: dict) -> bool:
    ticker = ticker.upper()
    db = SessionLocal()
    try:
        company = db.query(Company).filter_by(ticker=ticker).first()
        if not company:
            return False
            
        dados = dict(company.dados) if company.dados else {}
        
        for k, v in novos_dados.items():
            if k == 'dpa_historico':
                dados['dpa_historico'] = v
            elif k == 'num_acoes_milhoes_param':
                company.num_acoes_milhoes = float(v) if v else 1.0
            elif k == 'wacc':
                # Guardar em config root? No dict dados por enquanto
                dados['wacc'] = v
            else:
                dados[k] = v

        company.dados = dados
        company.dados_manuais_ativos = 1
        company.data_referencia = datetime.now().strftime('%Y-%m-%d')
        
        db.commit()
        return True
    except Exception as e:
        db.rollback()
        print(f"Erro ao salvar dados manuais no BD: {e}")
        return False
    finally:
        db.close()

def salvar_premissas(ticker: str, premissas: dict) -> bool:
    ticker = ticker.upper()
    db = SessionLocal()
    try:
        company = db.query(Company).filter_by(ticker=ticker).first()
        if not company:
            return False
            
        prems = dict(company.premissas_valuation) if company.premissas_valuation else {}
        for k, v in premissas.items():
            prems[k] = v
            
        company.premissas_valuation = prems
        db.commit()
        return True
    except Exception as e:
        db.rollback()
        print(f"Erro ao salvar premissas no BD: {e}")
        return False
    finally:
        db.close()

# ---------------------------------------------------------------------------
# Camada Online: Apenas Preço
# ---------------------------------------------------------------------------

def _buscar_preco_online(ticker: str) -> float | None:
    try:
        import requests
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
            'Accept': 'application/json'
        }
        symbol = f"{ticker.upper()}.SA"
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
        
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200:
            url = f"https://query2.finance.yahoo.com/v8/finance/chart/{symbol}"
            response = requests.get(url, headers=headers, timeout=10)
            
        if response.status_code == 200:
            data = response.json()
            res = data.get('chart', {}).get('result', [])
            if res:
                meta = res[0].get('meta', {})
                preco = meta.get('regularMarketPrice')
                if preco:
                    return float(preco)
    except Exception as e:
        print(f"Erro ao buscar preço online para {ticker}: {e}")
    return None

# ---------------------------------------------------------------------------
# Ponto de entrada principal
# ---------------------------------------------------------------------------

def carregar_dados_empresa(ticker: str) -> dict:
    empresa_config = obter_empresa(ticker)
    dados_json = dict(empresa_config.get('dados', {}))

    if empresa_config.get('num_acoes_milhoes'):
        dados_json['num_acoes_milhoes_param'] = empresa_config['num_acoes_milhoes']
        
    if not dados_json.get('num_acoes_milhoes_param'):
        dados_json['num_acoes_milhoes_param'] = empresa_config.get('num_acoes_milhoes')

    sucesso_online = False
    erro_online = None

    preco = _buscar_preco_online(ticker)
    if preco is not None:
        dados_json['preco_atual'] = preco
        sucesso_online = True
    else:
        erro_online = "Falha ao obter preço online."

    return {
        'dados': dados_json,
        'fonte': 'banco_dados',
        'empresa_config': empresa_config,
        'sucesso_online': sucesso_online,
        'erro_online': erro_online,
        'timestamp': datetime.now().isoformat(),
    }

def normalize_config_key(setor: str) -> str:
    if not setor:
        return ''
    import unicodedata
    s = str(setor).lower().replace(' ', '_').strip()
    return ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')

def obter_multiplo_ev_ebitda(ticker: str) -> float | None:
    empresa = obter_empresa(ticker)
    setor = empresa.get('setor')
    if not setor:
        return None

    setor_key = normalize_config_key(setor)
    multiplos = carregar_multiplos_setor()
    setor_data = multiplos.get(setor_key, {})
    return setor_data.get('ev_ebitda')

def obter_parametros_padrao(ticker: str) -> dict:
    import config
    empresa = obter_empresa(ticker)
    setor = empresa.get('setor', '')
    setor_key = normalize_config_key(setor)
    dados = empresa.get('dados', {})

    premio = config.PREMIO_RISCO_SETOR.get(setor_key, 0.05)
    wacc = config.SELIC_ANUAL + premio

    g_lucro = dados.get('crescimento_lucro_5a', 0.06)
    g_dpa = dados.get('crescimento_dpa_5a', 0.06)

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
    ticker = ticker.upper()
    db = SessionLocal()
    try:
        company = db.query(Company).filter_by(ticker=ticker).first()
        if not company:
            return False
        company.metodo_principal = metodo
        db.commit()
        return True
    except Exception as e:
        db.rollback()
        print(f"Erro ao salvar método principal: {e}")
        return False
    finally:
        db.close()

def carregar_config_global() -> dict:
    db = SessionLocal()
    try:
        config = db.query(AppConfig).filter_by(chave='global_config').first()
        return dict(config.valor) if config and config.valor else {}
    except Exception:
        return {}
    finally:
        db.close()

def salvar_config_global(config_dict: dict) -> bool:
    db = SessionLocal()
    try:
        config = db.query(AppConfig).filter_by(chave='global_config').first()
        if config:
            config.valor = config_dict
        else:
            db.add(AppConfig(chave='global_config', valor=config_dict))
        db.commit()
        return True
    except Exception as e:
        db.rollback()
        print(f"Erro ao salvar global config: {e}")
        return False
    finally:
        db.close()
