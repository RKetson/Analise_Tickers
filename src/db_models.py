from sqlalchemy import Column, Integer, String, Float, JSON
from src.database import Base

class Company(Base):
    __tablename__ = 'companies'
    
    ticker = Column(String, primary_key=True, index=True)
    nome = Column(String)
    setor = Column(String)
    descricao = Column(String)
    num_acoes_milhoes = Column(Float)
    dados = Column(JSON, default=dict)
    alertas_analista = Column(JSON, default=list)
    eventos_nao_recorrentes = Column(JSON, default=list)
    referencia_ri = Column(String)
    data_referencia = Column(String)
    premissas_valuation = Column(JSON, default=dict)
    metodo_principal = Column(String)
    dados_manuais_ativos = Column(Integer, default=0) # SQLite usa int para bool (0/1)

class PortfolioPosition(Base):
    __tablename__ = 'portfolio_positions'
    
    id = Column(Integer, primary_key=True, index=True)
    tipo = Column(String, index=True) # 'acoes' ou 'fiis'
    ticker = Column(String, index=True)
    quantidade = Column(Float, default=0.0)

class PortfolioSimulation(Base):
    __tablename__ = 'portfolio_simulations'
    
    id = Column(Integer, primary_key=True, index=True)
    tipo = Column(String, index=True) # 'acoes' ou 'fiis'
    ticker = Column(String, index=True)
    quantidade = Column(Float, default=0.0)
    valor_estimado = Column(Float, default=0.0)
    timestamp = Column(String)

class FiiClassification(Base):
    __tablename__ = 'fii_classifications'
    
    ticker = Column(String, primary_key=True, index=True)
    segmento = Column(String)

class AppConfig(Base):
    __tablename__ = 'app_config'
    
    chave = Column(String, primary_key=True, index=True)
    valor = Column(JSON)
