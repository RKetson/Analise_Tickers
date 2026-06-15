"""
backend/schemas/pluggy_schemas.py
Schemas Pydantic para validação de dados de request/response.

Divide-se em:
    - Schemas de response da API Pluggy (para parsing de dados recebidos)
    - Schemas de response da nossa API REST (para retorno ao cliente)
    - Schemas de request (para inputs do cliente)
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


# =====================================================================
# Schemas de response da API Pluggy (parsing)
# =====================================================================

class PluggyAuthResponse(BaseModel):
    """Response de POST /auth na Pluggy."""
    apiKey: str


class PluggyConnectTokenResponse(BaseModel):
    """Response de POST /connect_token na Pluggy."""
    accessToken: str


class PluggyItemResponse(BaseModel):
    """Item retornado pela Pluggy."""
    id: str
    connector: Optional[dict] = None
    status: Optional[str] = None
    executionStatus: Optional[str] = None
    createdAt: Optional[str] = None
    updatedAt: Optional[str] = None
    lastUpdatedAt: Optional[str] = None


class PluggyAccountResponse(BaseModel):
    """Conta retornada pela Pluggy."""
    id: str
    itemId: str
    type: Optional[str] = None
    subtype: Optional[str] = None
    name: Optional[str] = None
    number: Optional[str] = None
    balance: Optional[float] = None
    currencyCode: Optional[str] = "BRL"
    owner: Optional[dict] = None
    bankData: Optional[dict] = None


class PluggyTransactionResponse(BaseModel):
    """Transação retornada pela Pluggy."""
    id: str
    accountId: str
    date: str
    description: Optional[str] = None
    descriptionRaw: Optional[str] = None
    amount: float
    type: Optional[str] = None
    currencyCode: Optional[str] = "BRL"
    category: Optional[str] = None
    categoryId: Optional[str] = None
    merchant: Optional[dict] = None
    paymentData: Optional[dict] = None


class PluggyInvestmentResponse(BaseModel):
    """Investimento retornado pela Pluggy."""
    id: str
    itemId: str
    name: Optional[str] = None
    type: Optional[str] = None
    subtype: Optional[str] = None
    code: Optional[str] = None
    isin: Optional[str] = None
    issuer: Optional[str] = None
    quantity: Optional[float] = 0.0
    amount: Optional[float] = 0.0
    amountOriginal: Optional[float] = 0.0
    amountProfit: Optional[float] = 0.0
    currencyCode: Optional[str] = "BRL"
    rate: Optional[float] = None
    rateType: Optional[str] = None
    annualRate: Optional[float] = None
    dueDate: Optional[str] = None


class PluggyInvestmentTxnResponse(BaseModel):
    """Movimentação de investimento retornada pela Pluggy."""
    id: str
    investmentId: Optional[str] = None
    type: Optional[str] = None
    date: str
    quantity: Optional[float] = 0.0
    amount: Optional[float] = 0.0
    description: Optional[str] = None


class PluggyPaginatedResponse(BaseModel):
    """Resposta paginada genérica da Pluggy."""
    results: list[dict] = Field(default_factory=list)
    total: Optional[int] = None
    totalPages: Optional[int] = None
    page: Optional[int] = None
    nextCursor: Optional[str] = None


# =====================================================================
# Schemas da nossa API REST — Responses
# =====================================================================

class ConnectTokenOut(BaseModel):
    """Response para criação de connect token."""
    access_token: str
    expires_in: int = 1800  # 30 minutos


class ItemOut(BaseModel):
    """Item (conexão) retornado pela nossa API."""
    id: str
    connector_name: Optional[str] = None
    status: Optional[str] = None
    last_sync_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    accounts_count: int = 0

    class Config:
        from_attributes = True


class AccountOut(BaseModel):
    """Conta retornada pela nossa API."""
    id: str
    item_id: str
    type: Optional[str] = None
    subtype: Optional[str] = None
    name: Optional[str] = None
    balance: float = 0.0
    currency_code: str = "BRL"
    last_sync_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class TransactionOut(BaseModel):
    """Transação retornada pela nossa API."""
    id: str
    account_id: str
    date: date
    description: Optional[str] = None
    amount: float
    type: Optional[str] = None
    final_category: str = "Outros"
    is_investment: bool = False
    is_internal_transfer: bool = False
    merchant_name: Optional[str] = None

    class Config:
        from_attributes = True


class CashflowOut(BaseModel):
    """Resultado do cálculo de fluxo de caixa mensal."""
    month: str  # "YYYY-MM"
    total_income: float = 0.0
    total_expenses: float = 0.0
    net_cashflow: float = 0.0
    savings_rate: float = 0.0
    by_category: dict[str, float] = Field(default_factory=dict)
    investment_total: float = 0.0
    transfers_filtered: int = 0


class CashflowSummaryOut(BaseModel):
    """Resumo de fluxo de caixa dos últimos N meses."""
    months: list[CashflowOut] = Field(default_factory=list)
    average_income: float = 0.0
    average_expenses: float = 0.0
    average_savings_rate: float = 0.0


class InvestmentOut(BaseModel):
    """Posição de investimento retornada pela nossa API."""
    id: str
    name: Optional[str] = None
    type: Optional[str] = None
    subtype: Optional[str] = None
    code: Optional[str] = None
    quantity: float = 0.0
    amount: float = 0.0
    amount_original: float = 0.0
    amount_profit: float = 0.0
    rate: Optional[float] = None
    rate_type: Optional[str] = None
    annual_rate: Optional[float] = None
    due_date: Optional[date] = None

    class Config:
        from_attributes = True


class PortfolioSummaryOut(BaseModel):
    """Resumo consolidado da carteira de investimentos."""
    total_invested: float = 0.0
    total_current: float = 0.0
    total_return: float = 0.0
    total_return_pct: float = 0.0
    by_type: dict[str, dict[str, float]] = Field(default_factory=dict)
    by_asset: list[dict[str, Any]] = Field(default_factory=list)


class InvestmentReturnOut(BaseModel):
    """Rentabilidade calculada de um investimento."""
    investment_id: str
    investment_name: Optional[str] = None
    twrr: Optional[float] = None
    mwrr: Optional[float] = None
    simple_return: float = 0.0
    cdi_return: Optional[float] = None
    alpha: Optional[float] = None


class SyncStatusOut(BaseModel):
    """Status de uma operação de sincronização."""
    item_id: str
    sync_type: str
    status: str
    started_at: datetime
    finished_at: Optional[datetime] = None
    accounts_synced: int = 0
    transactions_synced: int = 0
    investments_synced: int = 0
    error_message: Optional[str] = None


# =====================================================================
# Schemas da nossa API REST — Requests
# =====================================================================

class ConnectTokenRequest(BaseModel):
    """Request para criação de connect token."""
    client_user_id: Optional[str] = None
    item_id: Optional[str] = Field(
        default=None,
        description="Se informado, cria token para atualizar item existente",
    )


class CategoryOverrideRequest(BaseModel):
    """Request para override manual de categoria de uma transação."""
    category: str = Field(
        ..., min_length=1, max_length=128, description="Nova categoria"
    )


class SyncRequest(BaseModel):
    """Request para disparo de sincronização."""
    from_date: Optional[str] = Field(
        default=None,
        description="Data inicial para sync incremental (YYYY-MM-DD)",
    )
