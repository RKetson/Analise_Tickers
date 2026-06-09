"""
src/portfolio.py
Gerencia a carteira de investimentos do usuário (Ações e FIIs),
salvando os dados em data/portfolio.json.
"""

import json
import os
from datetime import datetime

DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'data',
)
PORTFOLIO_FILE = os.path.join(DATA_DIR, 'portfolio.json')

def _get_default_portfolio():
    return {
        "acoes": {
            "posicoes": {},
            "simulacoes": {},
            "metas_setor": {},
            "margem_gap_saudavel": 0.05
        },
        "fiis": {
            "posicoes": {},
            "simulacoes": {},
            "metas_setor": {},
            "margem_gap_saudavel": 0.05
        }
    }

def load_portfolio() -> dict:
    if not os.path.exists(PORTFOLIO_FILE):
        return _get_default_portfolio()
    
    try:
        with open(PORTFOLIO_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            # Garantir chaves principais
            if 'acoes' not in data:
                data['acoes'] = _get_default_portfolio()['acoes']
            if 'fiis' not in data:
                data['fiis'] = _get_default_portfolio()['fiis']
            return data
    except Exception as e:
        print(f"Erro ao carregar portfolio.json: {e}")
        return _get_default_portfolio()

def save_portfolio(data: dict) -> bool:
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(PORTFOLIO_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"Erro ao salvar portfolio.json: {e}")
        return False

# --- Posições ---

def add_position(tipo: str, ticker: str, quantidade: float) -> bool:
    """Adiciona ou atualiza a quantidade de uma posição na carteira."""
    if tipo not in ['acoes', 'fiis']: return False
    data = load_portfolio()
    ticker = ticker.upper()
    
    if ticker in data[tipo]['posicoes']:
        data[tipo]['posicoes'][ticker]['quantidade'] += quantidade
    else:
        data[tipo]['posicoes'][ticker] = {'quantidade': quantidade}
    
    # Se a quantidade ficar <= 0, removemos da carteira
    if data[tipo]['posicoes'][ticker]['quantidade'] <= 0:
        del data[tipo]['posicoes'][ticker]
        
    return save_portfolio(data)

def remove_position(tipo: str, ticker: str) -> bool:
    if tipo not in ['acoes', 'fiis']: return False
    data = load_portfolio()
    ticker = ticker.upper()
    
    if ticker in data[tipo]['posicoes']:
        del data[tipo]['posicoes'][ticker]
        return save_portfolio(data)
    return True

# --- Simulações (Aportes/Vendas Pretendidos) ---

def add_simulacao(tipo: str, ticker: str, quantidade: float, valor_estimado: float) -> bool:
    """Adiciona uma pretensão de compra (quant > 0) ou venda (quant < 0)."""
    if tipo not in ['acoes', 'fiis']: return False
    data = load_portfolio()
    ticker = ticker.upper()
    
    data[tipo]['simulacoes'][ticker] = {
        'quantidade': quantidade,
        'valor_estimado': valor_estimado,
        'timestamp': datetime.now().isoformat()
    }
    return save_portfolio(data)

def remove_simulacao(tipo: str, ticker: str) -> bool:
    if tipo not in ['acoes', 'fiis']: return False
    data = load_portfolio()
    ticker = ticker.upper()
    
    if ticker in data[tipo]['simulacoes']:
        del data[tipo]['simulacoes'][ticker]
        return save_portfolio(data)
    return True

def efetivar_simulacao(tipo: str, ticker: str) -> bool:
    """Aplica a simulação na carteira real e a remove das simulações."""
    if tipo not in ['acoes', 'fiis']: return False
    data = load_portfolio()
    ticker = ticker.upper()
    
    if ticker in data[tipo]['simulacoes']:
        sim = data[tipo]['simulacoes'][ticker]
        quant = sim['quantidade']
        
        # Adiciona na carteira
        if ticker in data[tipo]['posicoes']:
            data[tipo]['posicoes'][ticker]['quantidade'] += quant
        else:
            # Não permite adicionar posição negativa como nova
            if quant > 0:
                data[tipo]['posicoes'][ticker] = {'quantidade': quant}
                
        # Limpeza caso zero
        if ticker in data[tipo]['posicoes'] and data[tipo]['posicoes'][ticker]['quantidade'] <= 0:
            del data[tipo]['posicoes'][ticker]
            
        del data[tipo]['simulacoes'][ticker]
        return save_portfolio(data)
    return False

# --- Metas e Configurações ---

def update_metas_setor(tipo: str, metas: dict) -> bool:
    """
    Atualiza as metas. Formato:
    {'Setor A': {'meta': 0.25, 'observacao': 'xyz'}, ...}
    """
    if tipo not in ['acoes', 'fiis']: return False
    data = load_portfolio()
    data[tipo]['metas_setor'] = metas
    return save_portfolio(data)

def update_margem_gap(tipo: str, margem: float) -> bool:
    if tipo not in ['acoes', 'fiis']: return False
    data = load_portfolio()
    data[tipo]['margem_gap_saudavel'] = margem
    return save_portfolio(data)

