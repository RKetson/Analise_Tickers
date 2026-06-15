"""
backend/api/routes.py
Endpoints REST do Analisador Financeiro.

Todos os endpoints retornam dados via Pydantic schemas e utilizam
dependency injection para sessões do banco de dados.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.core.database import get_db_session_dependency
from backend.core.logging import get_logger
from backend.models.db_models import (
    Account,
    Investment,
    PluggyItem,
    SyncLog,
    Transaction,
)
from backend.schemas.pluggy_schemas import (
    AccountOut,
    CashflowOut,
    CashflowSummaryOut,
    CategoryOverrideRequest,
    ConnectTokenOut,
    ConnectTokenRequest,
    InvestmentOut,
    InvestmentReturnOut,
    ItemOut,
    PortfolioSummaryOut,
    SyncRequest,
    SyncStatusOut,
    TransactionOut,
)
from backend.services.pluggy_service import PluggyService, PluggyServiceError
from backend.services.portfolio_analyzer import PortfolioAnalyzer
from backend.services.sync_service import SyncService
from backend.services.transaction_engine import TransactionEngine

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1", tags=["Financial Analyzer"])

# Instâncias dos serviços (stateless, podem ser reutilizadas)
_pluggy_service = PluggyService()
_sync_service = SyncService()
_tx_engine = TransactionEngine()
_portfolio = PortfolioAnalyzer()


# =====================================================================
# Connect Token
# =====================================================================

@router.post(
    "/connect-token",
    response_model=ConnectTokenOut,
    summary="Gerar connect_token para o widget meu.pluggy",
)
async def create_connect_token(body: ConnectTokenRequest | None = None):
    """Cria um token de acesso temporário (30 min) para inicializar
    o widget Pluggy Connect no frontend."""
    try:
        token = await _pluggy_service.create_connect_token(
            client_user_id=body.client_user_id if body else None,
            item_id=body.item_id if body else None,
        )
        return ConnectTokenOut(access_token=token)
    except PluggyServiceError as e:
        raise HTTPException(status_code=502, detail=str(e))


# =====================================================================
# Items (Conexões)
# =====================================================================

@router.get(
    "/items",
    response_model=list[ItemOut],
    summary="Listar todas as conexões (Items)",
)
def list_items(db: Session = Depends(get_db_session_dependency)):
    """Lista todos os Items (conexões com instituições financeiras)."""
    items = db.query(PluggyItem).order_by(PluggyItem.created_at.desc()).all()

    result = []
    for item in items:
        acc_count = (
            db.query(Account).filter(Account.item_id == item.id).count()
        )
        result.append(
            ItemOut(
                id=item.id,
                connector_name=item.connector_name,
                status=item.status,
                last_sync_at=item.last_sync_at,
                created_at=item.created_at,
                accounts_count=acc_count,
            )
        )
    return result


@router.post(
    "/items/{item_id}/sync",
    response_model=SyncStatusOut,
    summary="Sincronizar dados de um Item",
)
async def sync_item(
    item_id: str,
    body: SyncRequest | None = None,
    db: Session = Depends(get_db_session_dependency),
):
    """Dispara sincronização de um Item com a Pluggy.

    Se `from_date` for informado, faz sync incremental.
    Caso contrário, faz full sync.
    """
    try:
        if body and body.from_date:
            from_date = date.fromisoformat(body.from_date)
            sync_log = await _sync_service.incremental_sync(
                db, item_id, since=from_date
            )
        else:
            sync_log = await _sync_service.full_sync(db, item_id)

        return SyncStatusOut(
            item_id=sync_log.item_id,
            sync_type=sync_log.sync_type,
            status=sync_log.status,
            started_at=sync_log.started_at,
            finished_at=sync_log.finished_at,
            accounts_synced=sync_log.accounts_synced,
            transactions_synced=sync_log.transactions_synced,
            investments_synced=sync_log.investments_synced,
            error_message=sync_log.error_message,
        )
    except PluggyServiceError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.delete(
    "/items/{item_id}",
    summary="Remover um Item e todos os dados associados",
)
async def delete_item(
    item_id: str,
    db: Session = Depends(get_db_session_dependency),
):
    """Remove um Item e todos os dados locais associados (contas,
    transações, investimentos)."""
    db_item = db.query(PluggyItem).get(item_id)
    if not db_item:
        raise HTTPException(status_code=404, detail="Item não encontrado")

    # Tentar remover na Pluggy também
    try:
        await _pluggy_service.delete_item(item_id)
    except PluggyServiceError:
        pass  # Se falhar na Pluggy, remove localmente mesmo assim

    db.delete(db_item)
    return {"detail": f"Item {item_id} e dados associados removidos"}


# =====================================================================
# Accounts (Contas)
# =====================================================================

@router.get(
    "/accounts",
    response_model=list[AccountOut],
    summary="Listar todas as contas",
)
def list_accounts(
    item_id: str | None = Query(None, description="Filtrar por Item"),
    db: Session = Depends(get_db_session_dependency),
):
    """Lista todas as contas sincronizadas."""
    query = db.query(Account)
    if item_id:
        query = query.filter(Account.item_id == item_id)

    return query.order_by(Account.name).all()


# =====================================================================
# Transactions
# =====================================================================

@router.get(
    "/transactions",
    response_model=list[TransactionOut],
    summary="Listar transações",
)
def list_transactions(
    account_id: str | None = Query(None),
    category: str | None = Query(None),
    from_date: str | None = Query(None, description="YYYY-MM-DD"),
    to_date: str | None = Query(None, description="YYYY-MM-DD"),
    exclude_investments: bool = Query(True),
    exclude_transfers: bool = Query(True),
    limit: int = Query(500, le=5000),
    offset: int = Query(0),
    db: Session = Depends(get_db_session_dependency),
):
    """Lista transações com filtros.

    Por padrão, exclui investimentos e transferências internas.
    """
    query = db.query(Transaction)

    if account_id:
        query = query.filter(Transaction.account_id == account_id)
    if category:
        query = query.filter(Transaction.final_category == category)
    if from_date:
        query = query.filter(Transaction.date >= date.fromisoformat(from_date))
    if to_date:
        query = query.filter(Transaction.date <= date.fromisoformat(to_date))
    if exclude_investments:
        query = query.filter(Transaction.is_investment == False)  # noqa: E712
    if exclude_transfers:
        query = query.filter(
            Transaction.is_internal_transfer == False  # noqa: E712
        )

    return (
        query.order_by(Transaction.date.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )


@router.patch(
    "/transactions/{transaction_id}/category",
    response_model=TransactionOut,
    summary="Override manual de categoria",
)
def update_transaction_category(
    transaction_id: str,
    body: CategoryOverrideRequest,
    db: Session = Depends(get_db_session_dependency),
):
    """Permite ao usuário sobrescrever a categoria de uma transação."""
    txn = db.query(Transaction).get(transaction_id)
    if not txn:
        raise HTTPException(status_code=404, detail="Transação não encontrada")

    txn.custom_category = body.category
    txn.final_category = body.category

    logger.info(
        "category_override",
        transaction_id=transaction_id,
        new_category=body.category,
    )
    return txn


# =====================================================================
# Cashflow (Fluxo de Caixa)
# =====================================================================

@router.get(
    "/cashflow/{year}/{month}",
    response_model=CashflowOut,
    summary="Fluxo de caixa mensal",
)
def get_cashflow(
    year: int,
    month: int,
    account_ids: str | None = Query(
        None, description="IDs de contas separados por vírgula"
    ),
    db: Session = Depends(get_db_session_dependency),
):
    """Calcula o fluxo de caixa de um mês específico.

    Exclui investimentos e transferências internas automaticamente.
    """
    if month < 1 or month > 12:
        raise HTTPException(status_code=400, detail="Mês inválido (1-12)")

    acc_ids = account_ids.split(",") if account_ids else None
    return _tx_engine.compute_cashflow(db, month, year, acc_ids)


@router.get(
    "/cashflow/summary",
    response_model=CashflowSummaryOut,
    summary="Resumo dos últimos 12 meses",
)
def get_cashflow_summary(
    months: int = Query(12, ge=1, le=60),
    db: Session = Depends(get_db_session_dependency),
):
    """Retorna o fluxo de caixa dos últimos N meses."""
    today = date.today()
    results: list[CashflowOut] = []

    for i in range(months):
        # Calcular mês/ano retroativamente
        m = today.month - i
        y = today.year
        while m <= 0:
            m += 12
            y -= 1

        cf = _tx_engine.compute_cashflow(db, m, y)
        results.append(cf)

    results.reverse()  # Ordem cronológica

    # Médias
    incomes = [r.total_income for r in results if r.total_income > 0]
    expenses = [r.total_expenses for r in results if r.total_expenses < 0]
    rates = [r.savings_rate for r in results if r.total_income > 0]

    return CashflowSummaryOut(
        months=results,
        average_income=round(sum(incomes) / len(incomes), 2) if incomes else 0.0,
        average_expenses=round(
            sum(expenses) / len(expenses), 2
        ) if expenses else 0.0,
        average_savings_rate=round(
            sum(rates) / len(rates), 4
        ) if rates else 0.0,
    )


# =====================================================================
# Investments
# =====================================================================

@router.get(
    "/investments",
    response_model=list[InvestmentOut],
    summary="Listar posições de investimento",
)
def list_investments(
    item_id: str | None = Query(None),
    inv_type: str | None = Query(None, alias="type"),
    db: Session = Depends(get_db_session_dependency),
):
    """Lista todas as posições de investimento."""
    query = db.query(Investment)
    if item_id:
        query = query.filter(Investment.item_id == item_id)
    if inv_type:
        query = query.filter(Investment.type == inv_type)

    return query.order_by(Investment.amount.desc()).all()


@router.get(
    "/investments/summary",
    response_model=PortfolioSummaryOut,
    summary="Resumo consolidado da carteira de investimentos",
)
def get_portfolio_summary(
    db: Session = Depends(get_db_session_dependency),
):
    """Retorna resumo consolidado: total investido, valor atual,
    retorno, breakdown por tipo e por ativo."""
    return _portfolio.compute_portfolio_summary(db)


@router.get(
    "/investments/{investment_id}/return",
    response_model=InvestmentReturnOut,
    summary="Rentabilidade de um investimento",
)
def get_investment_return(
    investment_id: str,
    db: Session = Depends(get_db_session_dependency),
):
    """Calcula TWRR, MWRR, retorno simples e benchmark vs CDI
    para um investimento específico."""
    inv = db.query(Investment).get(investment_id)
    if not inv:
        raise HTTPException(
            status_code=404, detail="Investimento não encontrado"
        )

    return _portfolio.compute_full_return(db, investment_id)


# =====================================================================
# Sync Log
# =====================================================================

@router.get(
    "/sync-log",
    response_model=list[SyncStatusOut],
    summary="Histórico de sincronizações",
)
def list_sync_logs(
    item_id: str | None = Query(None),
    limit: int = Query(20, le=100),
    db: Session = Depends(get_db_session_dependency),
):
    """Lista o histórico de sincronizações."""
    query = db.query(SyncLog)
    if item_id:
        query = query.filter(SyncLog.item_id == item_id)

    logs = query.order_by(SyncLog.started_at.desc()).limit(limit).all()

    return [
        SyncStatusOut(
            item_id=log.item_id,
            sync_type=log.sync_type,
            status=log.status,
            started_at=log.started_at,
            finished_at=log.finished_at,
            accounts_synced=log.accounts_synced,
            transactions_synced=log.transactions_synced,
            investments_synced=log.investments_synced,
            error_message=log.error_message,
        )
        for log in logs
    ]
