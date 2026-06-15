"""
backend/services/sync_service.py
Orquestrador de sincronização de dados entre a Pluggy e o banco local.

Dois modos de operação:
    - full_sync: Sincronização completa (todos os dados do Item)
    - incremental_sync: Apenas transações novas desde a última sync

Sem webhooks — a sincronização é disparada:
    1. Manualmente via endpoint POST /api/v1/items/{id}/sync
    2. Opcionalmente via APScheduler a cada N minutos
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from backend.core.logging import get_logger
from backend.core.security import get_encryptor
from backend.models.db_models import (
    Account,
    Investment,
    InvestmentTransaction,
    PluggyItem,
    SyncLog,
    Transaction,
)
from backend.services.pluggy_service import PluggyService, PluggyServiceError
from backend.services.transaction_engine import TransactionEngine

logger = get_logger(__name__)


class SyncService:
    """Orquestrador de sincronização Pluggy → banco local.

    Coordena o fluxo completo: fetch de dados via API, persistência
    no SQLite, criptografia de PII e processamento de transações.
    """

    def __init__(self) -> None:
        self._pluggy = PluggyService()
        self._engine = TransactionEngine()

    # =================================================================
    # Full Sync
    # =================================================================

    async def full_sync(self, session: Session, item_id: str) -> SyncLog:
        """Sincronização completa de um Item.

        Fluxo:
            1. Buscar detalhes do Item → persistir em pluggy_items
            2. Listar Accounts → persistir em accounts (PII criptografado)
            3. Para cada Account:
               a. Listar Transactions → persistir em transactions
            4. Listar Investments → persistir em investments
            5. Para cada Investment:
               a. Listar InvestmentTransactions → persistir
            6. Processar transações (categorização, investimentos, transferências)
            7. Registrar no sync_log

        Args:
            session: Sessão SQLAlchemy.
            item_id: ID do item na Pluggy.

        Returns:
            SyncLog com resultado da sincronização.
        """
        sync_log = SyncLog(
            item_id=item_id,
            sync_type="FULL",
            status="RUNNING",
            started_at=datetime.utcnow(),
        )
        session.add(sync_log)
        session.flush()

        try:
            # 1. Item
            item_data = await self._pluggy.get_item(item_id)
            self._upsert_item(session, item_data)

            # 2. Accounts
            accounts_data = await self._pluggy.list_accounts(item_id)
            accounts = self._upsert_accounts(session, accounts_data)
            sync_log.accounts_synced = len(accounts)

            # 3. Transactions
            all_transactions: list[Transaction] = []
            for acc in accounts:
                txns_data = await self._pluggy.list_transactions(acc.id)
                txns = self._upsert_transactions(session, txns_data)
                all_transactions.extend(txns)

            sync_log.transactions_synced = len(all_transactions)

            # 4. Investments
            investments_data = await self._pluggy.list_investments(item_id)
            investments = self._upsert_investments(session, investments_data)
            sync_log.investments_synced = len(investments)

            # 5. Investment Transactions
            for inv in investments:
                inv_txns_data = await self._pluggy.list_investment_transactions(
                    inv.id
                )
                self._upsert_investment_transactions(session, inv.id, inv_txns_data)

            # 6. Processar transações (categorização + regras de negócio)
            session.flush()  # garantir que ORM objects estão sync
            result = self._engine.process_transactions(
                session, all_transactions, accounts
            )

            # 7. Finalizar sync log
            sync_log.status = "SUCCESS"
            sync_log.finished_at = datetime.utcnow()

            # Atualizar last_sync_at do item
            db_item = session.query(PluggyItem).get(item_id)
            if db_item:
                db_item.last_sync_at = datetime.utcnow()

            logger.info(
                "full_sync_complete",
                item_id=item_id,
                accounts=sync_log.accounts_synced,
                transactions=sync_log.transactions_synced,
                investments=sync_log.investments_synced,
                categorized=result.get("categorized", 0),
                investment_flags=result.get("investments", 0),
                transfer_pairs=result.get("transfer_pairs", 0),
            )

        except PluggyServiceError as e:
            sync_log.status = "ERROR"
            sync_log.error_message = str(e)[:1000]
            sync_log.finished_at = datetime.utcnow()
            logger.error("full_sync_error", item_id=item_id, error=str(e))
        except Exception as e:
            sync_log.status = "ERROR"
            sync_log.error_message = str(e)[:1000]
            sync_log.finished_at = datetime.utcnow()
            logger.error(
                "full_sync_unexpected_error", item_id=item_id, error=str(e)
            )
            raise

        return sync_log

    # =================================================================
    # Incremental Sync
    # =================================================================

    async def incremental_sync(
        self,
        session: Session,
        item_id: str,
        since: date | None = None,
    ) -> SyncLog:
        """Sincronização incremental — apenas transações novas.

        Busca transações de cada conta a partir de `since` (ou da
        última sincronização) e reprocessa as regras de negócio.

        Args:
            session: Sessão SQLAlchemy.
            item_id: ID do item na Pluggy.
            since: Data inicial. Se None, usa last_sync_at - 3 dias.

        Returns:
            SyncLog com resultado.
        """
        sync_log = SyncLog(
            item_id=item_id,
            sync_type="INCREMENTAL",
            status="RUNNING",
            started_at=datetime.utcnow(),
        )
        session.add(sync_log)
        session.flush()

        try:
            # Determinar data inicial
            if since is None:
                db_item = session.query(PluggyItem).get(item_id)
                if db_item and db_item.last_sync_at:
                    since = (db_item.last_sync_at - timedelta(days=3)).date()
                else:
                    # Primeira sync → full sync de 90 dias
                    since = (datetime.utcnow() - timedelta(days=90)).date()

            from_date_str = since.isoformat()

            # Buscar contas
            accounts = (
                session.query(Account)
                .filter(Account.item_id == item_id)
                .all()
            )

            if not accounts:
                # Se não tem contas, precisa de full sync
                logger.warning(
                    "incremental_sync_no_accounts",
                    item_id=item_id,
                    fallback="full_sync",
                )
                return await self.full_sync(session, item_id)

            # Buscar transações incrementais
            all_transactions: list[Transaction] = []
            for acc in accounts:
                txns_data = await self._pluggy.list_transactions(
                    acc.id, from_date=from_date_str
                )
                txns = self._upsert_transactions(session, txns_data)
                all_transactions.extend(txns)

            sync_log.transactions_synced = len(all_transactions)

            # Atualizar saldos de conta
            accounts_data = await self._pluggy.list_accounts(item_id)
            accounts = self._upsert_accounts(session, accounts_data)
            sync_log.accounts_synced = len(accounts)

            # Atualizar investimentos
            investments_data = await self._pluggy.list_investments(item_id)
            investments = self._upsert_investments(session, investments_data)
            sync_log.investments_synced = len(investments)

            # Processar novas transações
            session.flush()
            result = self._engine.process_transactions(
                session, all_transactions, accounts
            )

            sync_log.status = "SUCCESS"
            sync_log.finished_at = datetime.utcnow()

            # Atualizar last_sync_at
            db_item = session.query(PluggyItem).get(item_id)
            if db_item:
                db_item.last_sync_at = datetime.utcnow()

            logger.info(
                "incremental_sync_complete",
                item_id=item_id,
                since=from_date_str,
                transactions=sync_log.transactions_synced,
            )

        except PluggyServiceError as e:
            sync_log.status = "ERROR"
            sync_log.error_message = str(e)[:1000]
            sync_log.finished_at = datetime.utcnow()
            logger.error("incremental_sync_error", item_id=item_id, error=str(e))
        except Exception as e:
            sync_log.status = "ERROR"
            sync_log.error_message = str(e)[:1000]
            sync_log.finished_at = datetime.utcnow()
            logger.error(
                "incremental_sync_unexpected_error",
                item_id=item_id,
                error=str(e),
            )
            raise

        return sync_log

    # =================================================================
    # Upsert helpers
    # =================================================================

    def _upsert_item(self, session: Session, data: dict) -> PluggyItem:
        """Cria ou atualiza um Item no banco."""
        item_id = data["id"]
        db_item = session.query(PluggyItem).get(item_id)

        connector = data.get("connector", {})

        if db_item is None:
            db_item = PluggyItem(
                id=item_id,
                connector_id=connector.get("id"),
                connector_name=connector.get("name", "Desconhecido"),
                status=data.get("status"),
                execution_status=data.get("executionStatus"),
            )
            session.add(db_item)
        else:
            db_item.status = data.get("status", db_item.status)
            db_item.execution_status = data.get(
                "executionStatus", db_item.execution_status
            )
            if connector:
                db_item.connector_name = connector.get(
                    "name", db_item.connector_name
                )

        return db_item

    def _upsert_accounts(
        self, session: Session, accounts_data: list[dict]
    ) -> list[Account]:
        """Cria ou atualiza contas no banco, criptografando PII."""
        encryptor = get_encryptor()
        accounts: list[Account] = []

        for data in accounts_data:
            acc_id = data["id"]
            db_acc = session.query(Account).get(acc_id)

            # Extrair e criptografar PII do owner
            owner = data.get("owner") or {}
            owner_name = owner.get("name", "")
            owner_doc = owner.get("document", "") or owner.get("taxNumber", "")

            if db_acc is None:
                db_acc = Account(
                    id=acc_id,
                    item_id=data["itemId"],
                    type=data.get("type"),
                    subtype=data.get("subtype"),
                    name=data.get("name"),
                    number=data.get("number"),
                    owner_name_encrypted=encryptor.encrypt(owner_name),
                    owner_doc_encrypted=encryptor.encrypt(owner_doc),
                    balance=data.get("balance", 0.0),
                    currency_code=data.get("currencyCode", "BRL"),
                    last_sync_at=datetime.utcnow(),
                )
                session.add(db_acc)
            else:
                db_acc.balance = data.get("balance", db_acc.balance)
                db_acc.name = data.get("name", db_acc.name)
                db_acc.type = data.get("type", db_acc.type)
                db_acc.subtype = data.get("subtype", db_acc.subtype)
                if owner_name:
                    db_acc.owner_name_encrypted = encryptor.encrypt(owner_name)
                if owner_doc:
                    db_acc.owner_doc_encrypted = encryptor.encrypt(owner_doc)
                db_acc.last_sync_at = datetime.utcnow()

            accounts.append(db_acc)

        return accounts

    def _upsert_transactions(
        self, session: Session, txns_data: list[dict]
    ) -> list[Transaction]:
        """Cria ou atualiza transações no banco."""
        transactions: list[Transaction] = []

        for data in txns_data:
            txn_id = data["id"]
            db_txn = session.query(Transaction).get(txn_id)

            # Parse da data
            date_str = data.get("date", "")
            try:
                txn_date = datetime.fromisoformat(
                    date_str.replace("Z", "+00:00")
                ).date()
            except (ValueError, AttributeError):
                txn_date = datetime.utcnow().date()

            # Extrair merchant
            merchant = data.get("merchant") or {}
            merchant_name = merchant.get("name") or merchant.get("businessName")

            # Extrair payment data
            payment = data.get("paymentData") or {}
            payment_method = payment.get("paymentMethod")

            if db_txn is None:
                db_txn = Transaction(
                    id=txn_id,
                    account_id=data["accountId"],
                    date=txn_date,
                    description=data.get("description"),
                    description_raw=data.get("descriptionRaw"),
                    amount=data.get("amount", 0.0),
                    type=data.get("type"),
                    currency_code=data.get("currencyCode", "BRL"),
                    pluggy_category=data.get("category"),
                    pluggy_category_id=data.get("categoryId"),
                    merchant_name=merchant_name,
                    payment_method=payment_method,
                )
                session.add(db_txn)
            else:
                # Atualizar campos mutáveis (categoria pode mudar)
                db_txn.description = data.get("description", db_txn.description)
                db_txn.pluggy_category = data.get(
                    "category", db_txn.pluggy_category
                )
                db_txn.pluggy_category_id = data.get(
                    "categoryId", db_txn.pluggy_category_id
                )
                if merchant_name:
                    db_txn.merchant_name = merchant_name

            transactions.append(db_txn)

        return transactions

    def _upsert_investments(
        self, session: Session, inv_data: list[dict]
    ) -> list[Investment]:
        """Cria ou atualiza posições de investimento no banco."""
        investments: list[Investment] = []

        for data in inv_data:
            inv_id = data["id"]
            db_inv = session.query(Investment).get(inv_id)

            # Parse de due_date
            due_date = None
            if data.get("dueDate"):
                try:
                    due_date = datetime.fromisoformat(
                        data["dueDate"].replace("Z", "+00:00")
                    ).date()
                except (ValueError, AttributeError):
                    due_date = None

            if db_inv is None:
                db_inv = Investment(
                    id=inv_id,
                    item_id=data["itemId"],
                    name=data.get("name"),
                    type=data.get("type"),
                    subtype=data.get("subtype"),
                    code=data.get("code"),
                    isin=data.get("isin"),
                    issuer=data.get("issuer"),
                    quantity=data.get("quantity", 0.0),
                    amount=data.get("amount", 0.0),
                    amount_original=data.get("amountOriginal", 0.0),
                    amount_profit=data.get("amountProfit", 0.0),
                    currency_code=data.get("currencyCode", "BRL"),
                    rate=data.get("rate"),
                    rate_type=data.get("rateType"),
                    annual_rate=data.get("annualRate"),
                    due_date=due_date,
                    last_sync_at=datetime.utcnow(),
                )
                session.add(db_inv)
            else:
                # Atualizar valores dinâmicos
                db_inv.quantity = data.get("quantity", db_inv.quantity)
                db_inv.amount = data.get("amount", db_inv.amount)
                db_inv.amount_original = data.get(
                    "amountOriginal", db_inv.amount_original
                )
                db_inv.amount_profit = data.get(
                    "amountProfit", db_inv.amount_profit
                )
                db_inv.annual_rate = data.get("annualRate", db_inv.annual_rate)
                db_inv.last_sync_at = datetime.utcnow()

            investments.append(db_inv)

        return investments

    def _upsert_investment_transactions(
        self,
        session: Session,
        investment_id: str,
        txns_data: list[dict],
    ) -> list[InvestmentTransaction]:
        """Cria ou atualiza movimentações de investimento."""
        transactions: list[InvestmentTransaction] = []

        for data in txns_data:
            txn_id = data["id"]
            db_txn = session.query(InvestmentTransaction).get(txn_id)

            # Parse da data
            date_str = data.get("date", "")
            try:
                txn_date = datetime.fromisoformat(
                    date_str.replace("Z", "+00:00")
                ).date()
            except (ValueError, AttributeError):
                txn_date = datetime.utcnow().date()

            if db_txn is None:
                db_txn = InvestmentTransaction(
                    id=txn_id,
                    investment_id=investment_id,
                    type=data.get("type"),
                    date=txn_date,
                    quantity=data.get("quantity", 0.0),
                    amount=data.get("amount", 0.0),
                    description=data.get("description"),
                )
                session.add(db_txn)

            transactions.append(db_txn)

        return transactions
