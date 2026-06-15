"""
backend/services/transaction_engine.py
Motor de categorização de gastos e regras de negócio financeiras.

Responsabilidades:
    1. Categorização em 3 camadas (custom > pluggy > keyword engine)
    2. Isolamento de investimentos (nunca contabilizar como gasto)
    3. Filtragem de transferências internas entre contas
    4. Cálculo de fluxo de caixa mensal limpo

Este módulo opera sobre objetos do banco de dados (Transaction, Account)
e persiste os resultados de categorização diretamente.
"""

from __future__ import annotations

import re
from collections import defaultdict
from datetime import date, datetime
from typing import Optional

from sqlalchemy import and_, extract, func
from sqlalchemy.orm import Session

from backend.core.logging import get_logger
from backend.core.security import get_encryptor
from backend.models.db_models import Account, Transaction
from backend.schemas.pluggy_schemas import CashflowOut

logger = get_logger(__name__)


# =====================================================================
# Mapa de categorias — fallback por keywords na descrição
# =====================================================================

CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "Alimentação": [
        "ifood", "uber eats", "rappi", "restaurante", "lanchonete",
        "supermercado", "mercado", "padaria", "açougue", "hortifruti",
        "atacadão", "assaí", "carrefour", "pão de açúcar", "extra",
        "sams club", "makro", "bistek", "oba", "natural da terra",
    ],
    "Transporte": [
        "uber", "99pop", "99app", "combustível", "gasolina", "etanol",
        "estacionamento", "pedagio", "ipva", "sem parar", "conectcar",
        "movida", "localiza", "unidas", "shell", "ipiranga", "petrobrás",
    ],
    "Moradia": [
        "aluguel", "condomínio", "iptu", "energia", "cpfl", "enel",
        "cemig", "copel", "sabesp", "sanepar", "água", "gás",
        "internet", "vivo fibra", "claro net", "oi fibra",
    ],
    "Saúde": [
        "farmácia", "drogasil", "droga raia", "drogaria", "hospital",
        "médico", "clínica", "plano de saúde", "unimed", "amil",
        "sulamerica", "bradesco saúde", "hapvida", "notredame",
    ],
    "Educação": [
        "escola", "faculdade", "universidade", "curso", "udemy",
        "alura", "rocketseat", "coursera", "descomplica",
    ],
    "Lazer": [
        "cinema", "netflix", "spotify", "amazon prime", "disney",
        "hbo", "ingresso", "show", "teatro", "parque",
        "globoplay", "youtube premium", "apple tv",
    ],
    "Vestuário": [
        "renner", "c&a", "riachuelo", "zara", "shein", "centauro",
        "nike", "adidas", "netshoes",
    ],
    "Assinaturas": [
        "icloud", "google one", "microsoft 365", "chatgpt", "openai",
        "adobe", "canva", "notion",
    ],
    "Receita": [
        "salário", "salario", "prolabore", "pró-labore", "dividendo",
        "jcp", "juros sobre capital", "rendimento", "remuneração",
        "freelance", "honorário", "comissão",
    ],
}

# Pre-compile patterns
_CATEGORY_PATTERNS: dict[str, list[re.Pattern]] = {
    category: [re.compile(re.escape(kw), re.IGNORECASE) for kw in keywords]
    for category, keywords in CATEGORY_KEYWORDS.items()
}


# =====================================================================
# Patterns para detecção de investimentos
# =====================================================================

INVESTMENT_PATTERNS: list[re.Pattern] = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"tesouro\s*(direto|selic|ipca|prefixado|nacional)",
        r"(compra|aplicação|aplicacao|aporte)\s*(de\s*)?(ações|acoes|etf|fii|bdr|fundo|cdb|lci|lca|cri|cra|debenture)",
        r"b3\s*[-–]?\s*(compra|venda|liquidação|liquidacao)",
        r"(btg|xp|rico|clear|nuinvest|inter|modal|ágora|agora|órama|orama|guide|genial|warren)\s*[-–]?\s*(compra|aplicação|aplicacao|resgate|aporte|liquidação)",
        r"\b(rdb|lci|lca|cdb|cri|cra|debênture|debenture)\b",
        r"fundo\s*(de\s*)?(investimento|imobiliário|imobiliario|multimercado|renda\s*fixa|ações|acoes)",
        r"(resgate|aplicação|aplicacao)\s*(automática|automatica)?\s*(poupança|poupanca|cdb|fundo)",
        r"\b(ifix|ibov|smal11|bova11|ivvb11|hash11|qeth11)\b",
    ]
]

# Categorias da Pluggy que indicam investimento
PLUGGY_INVESTMENT_CATEGORIES = {
    "investments", "investment", "investimento", "investimentos",
    "savings", "poupança", "poupanca",
}


# =====================================================================
# Patterns para detecção de transferências internas
# =====================================================================

TRANSFER_PATTERNS: list[re.Pattern] = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"\b(ted|doc|pix|transf|transferência|transferencia)\b",
        r"(envio|recebimento)\s*(pix|ted|doc|transferência|transferencia)",
    ]
]

PLUGGY_TRANSFER_CATEGORIES = {
    "transfer", "transferência", "transferencia", "transfers",
}


# =====================================================================
# Transaction Engine
# =====================================================================

class TransactionEngine:
    """Motor de processamento de transações financeiras.

    Orquestra categorização, detecção de investimentos,
    filtragem de transferências internas e cálculo de fluxo de caixa.
    """

    # =================================================================
    # Categorização
    # =================================================================

    @staticmethod
    def _categorize_by_keywords(description: str) -> str | None:
        """Categoriza uma transação pela descrição usando keyword matching.

        Args:
            description: Descrição da transação (raw ou enriquecida).

        Returns:
            Nome da categoria ou None se não encontrada.
        """
        if not description:
            return None

        desc_lower = description.lower()
        for category, patterns in _CATEGORY_PATTERNS.items():
            for pattern in patterns:
                if pattern.search(desc_lower):
                    return category
        return None

    @staticmethod
    def categorize(transaction: Transaction) -> str:
        """Determina a categoria final de uma transação.

        Prioridade:
            1. custom_category (override manual do usuário)
            2. pluggy_category (IA da Pluggy)
            3. Keyword engine local
            4. "Outros" (fallback)

        Args:
            transaction: Objeto Transaction do banco.

        Returns:
            Nome da categoria final.
        """
        # 1. Override manual
        if transaction.custom_category:
            return transaction.custom_category

        # 2. Categoria da Pluggy
        if transaction.pluggy_category:
            return transaction.pluggy_category

        # 3. Keyword engine
        desc = transaction.description_raw or transaction.description or ""
        keyword_cat = TransactionEngine._categorize_by_keywords(desc)
        if keyword_cat:
            return keyword_cat

        # 4. Fallback
        return "Outros"

    def categorize_batch(
        self,
        session: Session,
        transactions: list[Transaction],
    ) -> int:
        """Categoriza um lote de transações e persiste no banco.

        Args:
            session: Sessão SQLAlchemy.
            transactions: Lista de transações a categorizar.

        Returns:
            Número de transações categorizadas.
        """
        count = 0
        for txn in transactions:
            txn.final_category = self.categorize(txn)
            count += 1

        logger.info("categorize_batch", count=count)
        return count

    # =================================================================
    # Detecção de Investimentos
    # =================================================================

    @staticmethod
    def is_investment_transaction(
        transaction: Transaction,
        account: Account | None = None,
    ) -> bool:
        """Verifica se uma transação é aporte/resgate de investimento.

        Critérios (qualquer um basta):
            1. A conta associada é do tipo INVESTMENT
            2. A categoria da Pluggy está em PLUGGY_INVESTMENT_CATEGORIES
            3. A descrição da transação casa com INVESTMENT_PATTERNS

        Args:
            transaction: Transação a verificar.
            account: Conta associada (opcional, para verificar tipo).

        Returns:
            True se for transação de investimento.
        """
        # 1. Tipo da conta
        if account and account.type and account.type.upper() == "INVESTMENT":
            return True

        # 2. Categoria Pluggy
        if transaction.pluggy_category:
            cat_lower = transaction.pluggy_category.lower()
            if cat_lower in PLUGGY_INVESTMENT_CATEGORIES:
                return True

        # 3. Pattern matching na descrição
        desc = transaction.description_raw or transaction.description or ""
        for pattern in INVESTMENT_PATTERNS:
            if pattern.search(desc):
                return True

        return False

    def flag_investments(
        self,
        session: Session,
        transactions: list[Transaction],
        accounts_map: dict[str, Account] | None = None,
    ) -> int:
        """Marca transações de investimento em um lote.

        Transações de investimento:
            - is_investment = True
            - is_excluded_from_cashflow = True
            - final_category = "Investimentos"

        Args:
            session: Sessão SQLAlchemy.
            transactions: Transações a processar.
            accounts_map: Mapa {account_id -> Account} para lookup rápido.

        Returns:
            Número de transações marcadas como investimento.
        """
        count = 0
        for txn in transactions:
            account = accounts_map.get(txn.account_id) if accounts_map else None
            if self.is_investment_transaction(txn, account):
                txn.is_investment = True
                txn.is_excluded_from_cashflow = True
                txn.final_category = "Investimentos"
                count += 1

        logger.info("flag_investments", count=count)
        return count

    # =================================================================
    # Filtragem de Transferências Internas
    # =================================================================

    def detect_internal_transfers(
        self,
        session: Session,
        transactions: list[Transaction],
        accounts: list[Account],
    ) -> list[tuple[str, str]]:
        """Detecta e anula transferências entre contas de mesma titularidade.

        Algoritmo:
            1. Agrupa transações por |valor| e data (±1 dia de tolerância)
            2. Para cada par (débito conta A, crédito conta B):
               a. Verifica se ambas as contas pertencem ao mesmo Item
               b. Ou se os titulares (CPF criptografado) são iguais
               c. Ou se a descrição contém patterns de transferência
            3. Marca ambas com is_internal_transfer = True

        Args:
            session: Sessão SQLAlchemy.
            transactions: Lista de transações a analisar.
            accounts: Contas do usuário para comparação de titularidade.

        Returns:
            Lista de pares (debit_txn_id, credit_txn_id) detectados.
        """
        if not transactions or len(accounts) < 2:
            return []

        # Mapa de contas por ID e por Item
        account_map = {a.id: a for a in accounts}
        item_accounts: dict[str, set[str]] = defaultdict(set)
        for acc in accounts:
            item_accounts[acc.item_id].add(acc.id)

        # Agrupar transações por |valor| arredondado
        by_amount: dict[int, list[Transaction]] = defaultdict(list)
        for txn in transactions:
            # Chave = valor absoluto em centavos (evita problemas de float)
            key = abs(int(round(txn.amount * 100)))
            by_amount[key].append(txn)

        pairs: list[tuple[str, str]] = []
        already_paired: set[str] = set()

        for amount_key, group in by_amount.items():
            if len(group) < 2 or amount_key == 0:
                continue

            # Separar débitos e créditos
            debits = [t for t in group if t.amount < 0]
            credits = [t for t in group if t.amount > 0]

            for debit in debits:
                if debit.id in already_paired:
                    continue

                for credit in credits:
                    if credit.id in already_paired:
                        continue

                    # Mesma conta? Não é transferência
                    if debit.account_id == credit.account_id:
                        continue

                    # Verificar proximidade de data (±1 dia)
                    if debit.date and credit.date:
                        delta = abs((debit.date - credit.date).days)
                        if delta > 1:
                            continue

                    # Verificar se são do mesmo titular
                    is_same_owner = False

                    # a) Mesmo Item (mesma conexão = mesmo titular)
                    debit_acc = account_map.get(debit.account_id)
                    credit_acc = account_map.get(credit.account_id)
                    if debit_acc and credit_acc:
                        if debit_acc.item_id == credit_acc.item_id:
                            is_same_owner = True
                        # b) Mesmo CPF criptografado (comparação direta de bytes)
                        elif (
                            debit_acc.owner_doc_encrypted
                            and credit_acc.owner_doc_encrypted
                            and debit_acc.owner_doc_encrypted
                            == credit_acc.owner_doc_encrypted
                        ):
                            is_same_owner = True

                    # c) Fallback: pattern de transferência na descrição
                    if not is_same_owner:
                        debit_desc = (
                            debit.description_raw or debit.description or ""
                        )
                        credit_desc = (
                            credit.description_raw or credit.description or ""
                        )
                        debit_is_transfer = any(
                            p.search(debit_desc) for p in TRANSFER_PATTERNS
                        )
                        credit_is_transfer = any(
                            p.search(credit_desc) for p in TRANSFER_PATTERNS
                        )
                        # Pluggy categories
                        debit_cat_transfer = (
                            debit.pluggy_category
                            and debit.pluggy_category.lower()
                            in PLUGGY_TRANSFER_CATEGORIES
                        )
                        credit_cat_transfer = (
                            credit.pluggy_category
                            and credit.pluggy_category.lower()
                            in PLUGGY_TRANSFER_CATEGORIES
                        )

                        if (debit_is_transfer or debit_cat_transfer) and (
                            credit_is_transfer or credit_cat_transfer
                        ):
                            is_same_owner = True

                    if is_same_owner:
                        # Marcar como transferência interna
                        debit.is_internal_transfer = True
                        debit.is_excluded_from_cashflow = True
                        debit.transfer_pair_id = credit.id
                        debit.final_category = "Transferência Interna"

                        credit.is_internal_transfer = True
                        credit.is_excluded_from_cashflow = True
                        credit.transfer_pair_id = debit.id
                        credit.final_category = "Transferência Interna"

                        pairs.append((debit.id, credit.id))
                        already_paired.add(debit.id)
                        already_paired.add(credit.id)
                        break  # próximo débito

        logger.info(
            "detect_internal_transfers",
            pairs_found=len(pairs),
        )
        return pairs

    # =================================================================
    # Processamento completo de um lote
    # =================================================================

    def process_transactions(
        self,
        session: Session,
        transactions: list[Transaction],
        accounts: list[Account],
    ) -> dict:
        """Processa um lote completo de transações: categoriza,
        detecta investimentos e transferências internas.

        Ordem de execução:
            1. Flag investimentos (prioridade máxima)
            2. Detectar transferências internas
            3. Categorizar restantes

        Args:
            session: Sessão SQLAlchemy.
            transactions: Transações a processar.
            accounts: Contas para detecção de transferências.

        Returns:
            Dict com contadores: {categorized, investments, transfer_pairs}
        """
        accounts_map = {a.id: a for a in accounts}

        # 1. Investimentos primeiro
        inv_count = self.flag_investments(session, transactions, accounts_map)

        # 2. Transferências internas (apenas em não-investimentos)
        non_inv = [t for t in transactions if not t.is_investment]
        pairs = self.detect_internal_transfers(session, non_inv, accounts)

        # 3. Categorizar as que não foram classificadas como investimento
        #    nem como transferência
        remaining = [
            t for t in transactions
            if not t.is_investment and not t.is_internal_transfer
        ]
        cat_count = self.categorize_batch(session, remaining)

        return {
            "categorized": cat_count,
            "investments": inv_count,
            "transfer_pairs": len(pairs),
        }

    # =================================================================
    # Fluxo de Caixa
    # =================================================================

    def compute_cashflow(
        self,
        session: Session,
        month: int,
        year: int,
        account_ids: list[str] | None = None,
    ) -> CashflowOut:
        """Calcula o fluxo de caixa mensal LIMPO.

        Exclui do cálculo:
            - Transações de investimento (is_investment = True)
            - Transferências internas (is_internal_transfer = True)
            - Transações explicitamente excluídas (is_excluded_from_cashflow)

        Args:
            session: Sessão SQLAlchemy.
            month: Mês (1-12).
            year: Ano (ex: 2026).
            account_ids: Se informado, filtra por essas contas.

        Returns:
            CashflowOut com todos os valores calculados.
        """
        # Filtro base: mês/ano + não excluído
        filters = [
            extract("month", Transaction.date) == month,
            extract("year", Transaction.date) == year,
            Transaction.is_excluded_from_cashflow == False,  # noqa: E712
        ]
        if account_ids:
            filters.append(Transaction.account_id.in_(account_ids))

        transactions = (
            session.query(Transaction).filter(and_(*filters)).all()
        )

        total_income = 0.0
        total_expenses = 0.0
        by_category: dict[str, float] = defaultdict(float)
        investment_total = 0.0

        # Contar transferências filtradas separadamente
        transfer_count = (
            session.query(func.count(Transaction.id))
            .filter(
                extract("month", Transaction.date) == month,
                extract("year", Transaction.date) == year,
                Transaction.is_internal_transfer == True,  # noqa: E712
            )
            .scalar()
            or 0
        )

        # Somar investimentos separadamente
        inv_sum = (
            session.query(func.coalesce(func.sum(Transaction.amount), 0.0))
            .filter(
                extract("month", Transaction.date) == month,
                extract("year", Transaction.date) == year,
                Transaction.is_investment == True,  # noqa: E712
            )
            .scalar()
            or 0.0
        )
        investment_total = float(inv_sum)

        for txn in transactions:
            cat = txn.final_category or "Outros"

            if txn.amount > 0:
                total_income += txn.amount
            else:
                total_expenses += txn.amount

            by_category[cat] += txn.amount

        net_cashflow = total_income + total_expenses  # expenses são negativos
        savings_rate = (
            net_cashflow / total_income if total_income > 0 else 0.0
        )

        return CashflowOut(
            month=f"{year:04d}-{month:02d}",
            total_income=round(total_income, 2),
            total_expenses=round(total_expenses, 2),
            net_cashflow=round(net_cashflow, 2),
            savings_rate=round(savings_rate, 4),
            by_category={k: round(v, 2) for k, v in sorted(by_category.items())},
            investment_total=round(investment_total, 2),
            transfers_filtered=transfer_count,
        )
