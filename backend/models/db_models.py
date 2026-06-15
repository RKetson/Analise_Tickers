"""
backend/models/db_models.py
Modelos SQLAlchemy ORM para o banco de dados do consolidador financeiro.

Campos sensíveis (CPF, nome do titular, número de conta) são armazenados
como LargeBinary (BLOB) após criptografia Fernet. Utilize as funções
de backend.core.security para encrypt/decrypt ao ler/escrever.

Tabelas:
    - pluggy_items: Conexões com instituições financeiras
    - accounts: Contas bancárias e de investimento
    - transactions: Transações financeiras (com flags de categorização)
    - investments: Posições de investimento
    - investment_transactions: Movimentações em investimentos
    - sync_log: Registro de sincronizações
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    """Classe base para todos os modelos ORM."""
    pass


# =====================================================================
# Pluggy Items — Conexões com instituições
# =====================================================================

class PluggyItem(Base):
    """Representa uma conexão com uma instituição financeira via Pluggy."""

    __tablename__ = "pluggy_items"

    id = Column(String(64), primary_key=True, comment="ID do Item na Pluggy")
    connector_id = Column(Integer, comment="ID numérico do conector Pluggy")
    connector_name = Column(String(128), comment="Nome da instituição (ex: Nubank)")
    status = Column(
        String(32),
        default="CREATED",
        comment="Status: UPDATED, UPDATING, LOGIN_ERROR, OUTDATED, etc.",
    )
    execution_status = Column(String(32), comment="Status da última execução")
    last_sync_at = Column(DateTime, comment="Última sincronização bem-sucedida")
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    # Relationships
    accounts = relationship(
        "Account", back_populates="item", cascade="all, delete-orphan"
    )
    investments = relationship(
        "Investment", back_populates="item", cascade="all, delete-orphan"
    )


# =====================================================================
# Accounts — Contas bancárias / cartão / investimento
# =====================================================================

class Account(Base):
    """Conta bancária, cartão de crédito ou conta de investimento."""

    __tablename__ = "accounts"

    id = Column(String(64), primary_key=True, comment="ID da conta na Pluggy")
    item_id = Column(
        String(64),
        ForeignKey("pluggy_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    type = Column(
        String(32),
        comment="Tipo: BANK, CREDIT, INVESTMENT",
    )
    subtype = Column(
        String(32),
        comment="Subtipo: CHECKING_ACCOUNT, SAVINGS_ACCOUNT, CREDIT_CARD, etc.",
    )
    name = Column(String(256), comment="Nome da conta")
    number = Column(String(64), comment="Número da conta (pode estar mascarado)")

    # --- Campos criptografados (PII) ---
    owner_name_encrypted = Column(
        LargeBinary, comment="Nome do titular — CRIPTOGRAFADO com Fernet"
    )
    owner_doc_encrypted = Column(
        LargeBinary, comment="CPF/CNPJ do titular — CRIPTOGRAFADO com Fernet"
    )

    # --- Saldo ---
    balance = Column(Float, default=0.0, comment="Saldo atual")
    currency_code = Column(String(8), default="BRL")

    # --- Metadados ---
    bank_data = Column(Text, comment="JSON com dados adicionais do banco")
    last_sync_at = Column(DateTime)
    created_at = Column(DateTime, default=func.now())

    # Relationships
    item = relationship("PluggyItem", back_populates="accounts")
    transactions = relationship(
        "Transaction", back_populates="account", cascade="all, delete-orphan"
    )


# =====================================================================
# Transactions — Transações financeiras
# =====================================================================

class Transaction(Base):
    """Transação financeira individual.

    Flags de categorização:
        - is_investment: Aporte/resgate em investimento
        - is_internal_transfer: Transferência entre contas próprias
        - is_excluded_from_cashflow: Excluída do cálculo de fluxo de caixa
    """

    __tablename__ = "transactions"
    __table_args__ = (
        Index("ix_transactions_date", "date"),
        Index("ix_transactions_account_date", "account_id", "date"),
        Index("ix_transactions_category", "final_category"),
    )

    id = Column(String(64), primary_key=True, comment="ID da transação na Pluggy")
    account_id = Column(
        String(64),
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # --- Dados da transação ---
    date = Column(Date, nullable=False, comment="Data da transação")
    description = Column(String(512), comment="Descrição limpa/enriquecida")
    description_raw = Column(String(512), comment="Descrição original bruta")
    amount = Column(
        Float,
        nullable=False,
        comment="Valor: positivo = entrada, negativo = saída",
    )
    type = Column(String(16), comment="DEBIT ou CREDIT")
    currency_code = Column(String(8), default="BRL")

    # --- Categorização ---
    pluggy_category = Column(String(128), comment="Categoria atribuída pela Pluggy")
    pluggy_category_id = Column(String(64), comment="ID da categoria na Pluggy")
    custom_category = Column(
        String(128), comment="Override manual do usuário"
    )
    final_category = Column(
        String(128),
        default="Outros",
        comment="Categoria final: custom > pluggy > engine > 'Outros'",
    )

    # --- Flags do motor de regras ---
    is_investment = Column(
        Boolean, default=False, comment="Aporte ou resgate de investimento"
    )
    is_internal_transfer = Column(
        Boolean, default=False, comment="Transferência intra-contas"
    )
    is_excluded_from_cashflow = Column(
        Boolean, default=False, comment="Excluída do fluxo de caixa"
    )
    transfer_pair_id = Column(
        String(64),
        comment="ID da transação par (para transferências internas)",
    )

    # --- Metadados extras ---
    merchant_name = Column(String(256), comment="Nome do estabelecimento")
    payment_method = Column(String(64), comment="Método de pagamento")

    created_at = Column(DateTime, default=func.now())

    # Relationships
    account = relationship("Account", back_populates="transactions")


# =====================================================================
# Investments — Posições de investimento
# =====================================================================

class Investment(Base):
    """Posição individual em um ativo de investimento."""

    __tablename__ = "investments"

    id = Column(String(64), primary_key=True, comment="ID do investimento na Pluggy")
    item_id = Column(
        String(64),
        ForeignKey("pluggy_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    account_id = Column(
        String(64), comment="ID da conta de investimento associada"
    )

    # --- Dados do ativo ---
    name = Column(String(256), comment="Nome do ativo (ex: Tesouro IPCA+ 2035)")
    type = Column(
        String(64),
        comment="Tipo: FIXED_INCOME, EQUITY, MUTUAL_FUND, ETF, COE, etc.",
    )
    subtype = Column(String(64), comment="Subtipo específico")
    code = Column(String(32), comment="Ticker ou código do ativo")
    isin = Column(String(32), comment="Código ISIN")
    issuer = Column(String(256), comment="Emissor do título")

    # --- Valores ---
    quantity = Column(Float, default=0.0, comment="Quantidade de cotas/papéis")
    amount = Column(Float, default=0.0, comment="Valor de mercado atual")
    amount_original = Column(Float, default=0.0, comment="Valor investido original")
    amount_profit = Column(Float, default=0.0, comment="Lucro/prejuízo")
    currency_code = Column(String(8), default="BRL")

    # --- Taxas ---
    rate = Column(Float, comment="Taxa contratada (renda fixa)")
    rate_type = Column(String(32), comment="Tipo da taxa: CDI, IPCA, PRE, etc.")
    annual_rate = Column(Float, comment="Rentabilidade anual")

    # --- Datas ---
    due_date = Column(Date, comment="Data de vencimento (renda fixa)")
    last_sync_at = Column(DateTime)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    # Relationships
    item = relationship("PluggyItem", back_populates="investments")
    inv_transactions = relationship(
        "InvestmentTransaction",
        back_populates="investment",
        cascade="all, delete-orphan",
    )


# =====================================================================
# Investment Transactions — Movimentações em investimentos
# =====================================================================

class InvestmentTransaction(Base):
    """Movimentação individual em um ativo de investimento."""

    __tablename__ = "investment_transactions"
    __table_args__ = (
        Index("ix_inv_txn_date", "date"),
    )

    id = Column(String(64), primary_key=True)
    investment_id = Column(
        String(64),
        ForeignKey("investments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    type = Column(
        String(32),
        comment="Tipo: BUY, SELL, TAX, INCOME, TRANSFER, etc.",
    )
    date = Column(Date, nullable=False)
    quantity = Column(Float, default=0.0)
    amount = Column(Float, default=0.0)
    description = Column(String(512))

    created_at = Column(DateTime, default=func.now())

    # Relationships
    investment = relationship("Investment", back_populates="inv_transactions")


# =====================================================================
# Sync Log — Registro de sincronizações
# =====================================================================

class SyncLog(Base):
    """Registro de cada operação de sincronização com a Pluggy."""

    __tablename__ = "sync_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    item_id = Column(String(64), index=True, comment="ID do Item sincronizado")
    sync_type = Column(
        String(16), comment="Tipo: FULL, INCREMENTAL, MANUAL"
    )
    status = Column(String(16), comment="Status: SUCCESS, ERROR, PARTIAL")
    started_at = Column(DateTime, default=func.now())
    finished_at = Column(DateTime)
    accounts_synced = Column(Integer, default=0)
    transactions_synced = Column(Integer, default=0)
    investments_synced = Column(Integer, default=0)
    error_message = Column(Text)
