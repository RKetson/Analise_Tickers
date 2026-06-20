"""
src/portfolio.py
Gerencia a carteira de investimentos do usuário (Ações e FIIs),
salvando os dados no banco de dados SQLite (tabelas PortfolioPosition e PortfolioSimulation).
"""

import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database import SessionLocal
from src.db_models import PortfolioPosition, PortfolioSimulation, AppConfig

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
    """
    Constrói a estrutura do portfólio consultando o banco de dados
    para manter a compatibilidade com a API legada baseada em JSON.
    """
    db = SessionLocal()
    portfolio = _get_default_portfolio()
    try:
        # Posições
        posicoes = db.query(PortfolioPosition).all()
        for p in posicoes:
            if p.tipo in portfolio:
                portfolio[p.tipo]["posicoes"][p.ticker] = {"quantidade": p.quantidade}
                
        # Simulações
        simulacoes = db.query(PortfolioSimulation).all()
        for s in simulacoes:
            if s.tipo in portfolio:
                portfolio[s.tipo]["simulacoes"][s.ticker] = {
                    "quantidade": s.quantidade,
                    "valor_estimado": s.valor_estimado,
                    "timestamp": s.timestamp
                }
                
        # Configurações (Metas e Margens)
        for tipo in ['acoes', 'fiis']:
            meta_cfg = db.query(AppConfig).filter_by(chave=f'portfolio_{tipo}_metas_setor').first()
            if meta_cfg and meta_cfg.valor:
                portfolio[tipo]["metas_setor"] = dict(meta_cfg.valor)
                
            gap_cfg = db.query(AppConfig).filter_by(chave=f'portfolio_{tipo}_margem_gap').first()
            if gap_cfg and gap_cfg.valor is not None:
                portfolio[tipo]["margem_gap_saudavel"] = float(gap_cfg.valor)

        return portfolio
    except Exception as e:
        print(f"Erro ao carregar portfolio do BD: {e}")
        return _get_default_portfolio()
    finally:
        db.close()

# --- Posições ---

def add_position(tipo: str, ticker: str, quantidade: float) -> bool:
    """Adiciona ou atualiza a quantidade de uma posição na carteira."""
    if tipo not in ['acoes', 'fiis']: return False
    ticker = ticker.upper()
    db = SessionLocal()
    try:
        pos = db.query(PortfolioPosition).filter_by(tipo=tipo, ticker=ticker).first()
        if pos:
            pos.quantidade += quantidade
        else:
            pos = PortfolioPosition(tipo=tipo, ticker=ticker, quantidade=quantidade)
            db.add(pos)
            
        if pos.quantidade <= 0:
            db.delete(pos)
            
        db.commit()
        return True
    except Exception as e:
        db.rollback()
        print(f"Erro ao adicionar posição: {e}")
        return False
    finally:
        db.close()

def remove_position(tipo: str, ticker: str) -> bool:
    if tipo not in ['acoes', 'fiis']: return False
    ticker = ticker.upper()
    db = SessionLocal()
    try:
        pos = db.query(PortfolioPosition).filter_by(tipo=tipo, ticker=ticker).first()
        if pos:
            db.delete(pos)
            db.commit()
        return True
    except Exception as e:
        db.rollback()
        print(f"Erro ao remover posição: {e}")
        return False
    finally:
        db.close()

# --- Simulações (Aportes/Vendas Pretendidos) ---

def add_simulacao(tipo: str, ticker: str, quantidade: float, valor_estimado: float) -> bool:
    if tipo not in ['acoes', 'fiis']: return False
    ticker = ticker.upper()
    db = SessionLocal()
    try:
        sim = db.query(PortfolioSimulation).filter_by(tipo=tipo, ticker=ticker).first()
        if sim:
            sim.quantidade = quantidade
            sim.valor_estimado = valor_estimado
            sim.timestamp = datetime.now().isoformat()
        else:
            sim = PortfolioSimulation(
                tipo=tipo,
                ticker=ticker,
                quantidade=quantidade,
                valor_estimado=valor_estimado,
                timestamp=datetime.now().isoformat()
            )
            db.add(sim)
        db.commit()
        return True
    except Exception as e:
        db.rollback()
        print(f"Erro ao adicionar simulação: {e}")
        return False
    finally:
        db.close()

def remove_simulacao(tipo: str, ticker: str) -> bool:
    if tipo not in ['acoes', 'fiis']: return False
    ticker = ticker.upper()
    db = SessionLocal()
    try:
        sim = db.query(PortfolioSimulation).filter_by(tipo=tipo, ticker=ticker).first()
        if sim:
            db.delete(sim)
            db.commit()
        return True
    except Exception as e:
        db.rollback()
        print(f"Erro ao remover simulação: {e}")
        return False
    finally:
        db.close()

def efetivar_simulacao(tipo: str, ticker: str) -> bool:
    """Aplica a simulação na carteira real e a remove das simulações."""
    if tipo not in ['acoes', 'fiis']: return False
    ticker = ticker.upper()
    db = SessionLocal()
    try:
        sim = db.query(PortfolioSimulation).filter_by(tipo=tipo, ticker=ticker).first()
        if not sim:
            return False
            
        quant = sim.quantidade
        pos = db.query(PortfolioPosition).filter_by(tipo=tipo, ticker=ticker).first()
        
        if pos:
            pos.quantidade += quant
        else:
            if quant > 0:
                pos = PortfolioPosition(tipo=tipo, ticker=ticker, quantidade=quant)
                db.add(pos)
                
        # Limpeza caso <= 0
        if pos and pos.quantidade <= 0:
            db.delete(pos)
            
        db.delete(sim)
        db.commit()
        return True
    except Exception as e:
        db.rollback()
        print(f"Erro ao efetivar simulação: {e}")
        return False
    finally:
        db.close()

# --- Metas e Configurações ---

def update_metas_setor(tipo: str, metas: dict) -> bool:
    if tipo not in ['acoes', 'fiis']: return False
    db = SessionLocal()
    try:
        key = f'portfolio_{tipo}_metas_setor'
        cfg = db.query(AppConfig).filter_by(chave=key).first()
        if cfg:
            cfg.valor = metas
        else:
            db.add(AppConfig(chave=key, valor=metas))
        db.commit()
        return True
    except Exception as e:
        db.rollback()
        print(f"Erro ao atualizar metas de setor: {e}")
        return False
    finally:
        db.close()

def update_margem_gap(tipo: str, margem: float) -> bool:
    if tipo not in ['acoes', 'fiis']: return False
    db = SessionLocal()
    try:
        key = f'portfolio_{tipo}_margem_gap'
        cfg = db.query(AppConfig).filter_by(chave=key).first()
        if cfg:
            cfg.valor = margem
        else:
            db.add(AppConfig(chave=key, valor=margem))
        db.commit()
        return True
    except Exception as e:
        db.rollback()
        print(f"Erro ao atualizar margem gap: {e}")
        return False
    finally:
        db.close()
