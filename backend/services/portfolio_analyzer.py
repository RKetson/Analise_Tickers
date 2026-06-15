"""
backend/services/portfolio_analyzer.py
Análise de rentabilidade e consolidação da carteira de investimentos.

Calcula:
    - Resumo consolidado (total investido, valor atual, retorno, por tipo)
    - TWRR (Time-Weighted Rate of Return) — isola o efeito do timing
    - MWRR / TIR (Money-Weighted Rate of Return) — avalia decisão de timing
    - Benchmark vs CDI acumulado

Opera sobre os dados persistidos no banco local (tabelas investments
e investment_transactions), previamente sincronizados via SyncService.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Any, Optional

import numpy as np
from scipy.optimize import brentq
from sqlalchemy.orm import Session

from backend.core.logging import get_logger
from backend.models.db_models import Investment, InvestmentTransaction
from backend.schemas.pluggy_schemas import (
    InvestmentReturnOut,
    PortfolioSummaryOut,
)

logger = get_logger(__name__)

# CDI / Selic aproximado para benchmark (taxa diária)
# Em produção, isso viria de uma API (ex: Banco Central PTAX)
# Por ora, usamos a taxa anual do config.py
CDI_ANUAL = 0.144  # 14.4% a.a. — alinhado com config.py


def _cdi_daily_rate(cdi_annual: float = CDI_ANUAL) -> float:
    """Converte CDI anual em taxa diária (dias úteis = 252)."""
    return (1 + cdi_annual) ** (1 / 252) - 1


class PortfolioAnalyzer:
    """Analisador de rentabilidade e consolidação de carteira."""

    # =================================================================
    # Consolidação
    # =================================================================

    def compute_portfolio_summary(
        self,
        session: Session,
    ) -> PortfolioSummaryOut:
        """Consolida toda a carteira de investimentos.

        Agrupa por tipo de investimento e calcula:
            - Total investido (original)
            - Valor atual de mercado
            - Retorno absoluto e percentual
            - Peso de cada tipo e ativo na carteira

        Args:
            session: Sessão SQLAlchemy.

        Returns:
            PortfolioSummaryOut com resumo completo.
        """
        investments = session.query(Investment).all()

        if not investments:
            return PortfolioSummaryOut()

        total_invested = 0.0
        total_current = 0.0

        by_type: dict[str, dict[str, float]] = defaultdict(
            lambda: {"invested": 0.0, "current": 0.0}
        )
        by_asset: list[dict[str, Any]] = []

        for inv in investments:
            invested = inv.amount_original or 0.0
            current = inv.amount or 0.0
            inv_type = inv.type or "UNKNOWN"

            total_invested += invested
            total_current += current

            by_type[inv_type]["invested"] += invested
            by_type[inv_type]["current"] += current

            return_pct = (
                (current - invested) / invested if invested > 0 else 0.0
            )

            by_asset.append({
                "id": inv.id,
                "name": inv.name or "Sem nome",
                "type": inv_type,
                "code": inv.code,
                "invested": round(invested, 2),
                "current": round(current, 2),
                "profit": round(current - invested, 2),
                "return_pct": round(return_pct, 4),
                "weight": 0.0,  # calculado após totalizar
            })

        # Calcular pesos
        for asset in by_asset:
            asset["weight"] = round(
                asset["current"] / total_current if total_current > 0 else 0.0,
                4,
            )

        # Pesos por tipo
        by_type_final = {}
        for inv_type, vals in by_type.items():
            inv_val = vals["invested"]
            cur_val = vals["current"]
            by_type_final[inv_type] = {
                "invested": round(inv_val, 2),
                "current": round(cur_val, 2),
                "profit": round(cur_val - inv_val, 2),
                "pct": round(
                    (cur_val - inv_val) / inv_val if inv_val > 0 else 0.0, 4
                ),
                "weight": round(
                    cur_val / total_current if total_current > 0 else 0.0, 4
                ),
            }

        total_return = total_current - total_invested
        total_return_pct = (
            total_return / total_invested if total_invested > 0 else 0.0
        )

        # Ordenar por peso decrescente
        by_asset.sort(key=lambda x: x["weight"], reverse=True)

        return PortfolioSummaryOut(
            total_invested=round(total_invested, 2),
            total_current=round(total_current, 2),
            total_return=round(total_return, 2),
            total_return_pct=round(total_return_pct, 4),
            by_type=by_type_final,
            by_asset=by_asset,
        )

    # =================================================================
    # TWRR — Time-Weighted Rate of Return
    # =================================================================

    def compute_return_twrr(
        self,
        session: Session,
        investment_id: str,
    ) -> float | None:
        """Calcula a rentabilidade por TWRR.

        O TWRR elimina o efeito dos aportes/resgates, medindo a
        performance pura do ativo independente do timing.

        Fórmula: TWRR = Π(1 + Ri) - 1
        Onde Ri é o retorno em cada sub-período entre aportes.

        Args:
            session: Sessão SQLAlchemy.
            investment_id: ID do investimento.

        Returns:
            TWRR como float (ex: 0.15 = 15%), ou None se insuficiente.
        """
        investment = session.query(Investment).get(investment_id)
        if not investment:
            return None

        transactions = (
            session.query(InvestmentTransaction)
            .filter(InvestmentTransaction.investment_id == investment_id)
            .order_by(InvestmentTransaction.date)
            .all()
        )

        if not transactions:
            # Retorno simples se não há movimentações
            if investment.amount_original and investment.amount_original > 0:
                return (
                    (investment.amount - investment.amount_original)
                    / investment.amount_original
                )
            return None

        # Construir sub-períodos
        # Cada aporte/resgate divide o período
        sub_returns: list[float] = []
        portfolio_value = 0.0  # valor do portfólio no início do sub-período

        for txn in transactions:
            if txn.type in ("BUY", "TRANSFER_IN", "INCOME"):
                cashflow = abs(txn.amount)
            elif txn.type in ("SELL", "TRANSFER_OUT", "TAX"):
                cashflow = -abs(txn.amount)
            else:
                cashflow = txn.amount

            if portfolio_value > 0 and cashflow != 0:
                # Estimar o valor antes do cashflow
                # Aproximação: assumimos que o cashflow ocorre no final do dia
                value_before_cf = portfolio_value + cashflow
                if portfolio_value > 0:
                    period_return = (value_before_cf / portfolio_value) - 1
                    sub_returns.append(period_return)

            portfolio_value += cashflow

        if not sub_returns:
            # Fallback: retorno simples
            if investment.amount_original and investment.amount_original > 0:
                return (
                    (investment.amount - investment.amount_original)
                    / investment.amount_original
                )
            return None

        # TWRR = Π(1 + Ri) - 1
        twrr = 1.0
        for r in sub_returns:
            twrr *= (1 + r)
        twrr -= 1

        return round(twrr, 6)

    # =================================================================
    # MWRR — Money-Weighted Rate of Return (TIR / IRR)
    # =================================================================

    def compute_return_mwrr(
        self,
        session: Session,
        investment_id: str,
    ) -> float | None:
        """Calcula a rentabilidade por MWRR (TIR / IRR).

        O MWRR considera o impacto do timing dos aportes, medindo
        a taxa de retorno que iguala o valor presente dos fluxos
        de caixa ao valor atual da posição.

        Usa scipy.optimize.brentq para resolver a equação.

        Args:
            session: Sessão SQLAlchemy.
            investment_id: ID do investimento.

        Returns:
            MWRR anualizada como float, ou None se não convergir.
        """
        investment = session.query(Investment).get(investment_id)
        if not investment:
            return None

        transactions = (
            session.query(InvestmentTransaction)
            .filter(InvestmentTransaction.investment_id == investment_id)
            .order_by(InvestmentTransaction.date)
            .all()
        )

        if not transactions:
            return None

        # Montar fluxos de caixa: (dias desde t0, valor)
        # Aportes são negativos (saída de caixa do investidor)
        # Resgates são positivos (entrada de caixa)
        t0 = transactions[0].date
        cashflows: list[tuple[int, float]] = []

        for txn in transactions:
            days = (txn.date - t0).days

            if txn.type in ("BUY", "TRANSFER_IN"):
                # Investidor pagou → cashflow negativo
                cashflows.append((days, -abs(txn.amount)))
            elif txn.type in ("SELL", "TRANSFER_OUT", "INCOME"):
                # Investidor recebeu → cashflow positivo
                cashflows.append((days, abs(txn.amount)))
            elif txn.type == "TAX":
                # Imposto → cashflow negativo
                cashflows.append((days, -abs(txn.amount)))

        # Adicionar valor atual como "venda" final
        today = date.today()
        days_total = (today - t0).days
        if days_total <= 0:
            return None

        current_value = investment.amount or 0.0
        cashflows.append((days_total, current_value))

        # Resolver TIR: encontrar r tal que Σ CF_i / (1+r)^(t_i/365) = 0
        def npv(rate: float) -> float:
            return sum(
                cf / (1 + rate) ** (days / 365.0)
                for days, cf in cashflows
            )

        try:
            irr = brentq(npv, -0.99, 10.0, xtol=1e-8, maxiter=1000)
            return round(irr, 6)
        except (ValueError, RuntimeError):
            logger.warning(
                "mwrr_no_convergence",
                investment_id=investment_id,
            )
            return None

    # =================================================================
    # Benchmark vs CDI
    # =================================================================

    def benchmark_vs_cdi(
        self,
        session: Session,
        investment_id: str,
    ) -> dict[str, float | None]:
        """Compara a rentabilidade do ativo com o CDI acumulado.

        Calcula o CDI acumulado no mesmo período do investimento
        e retorna o alpha (excesso de retorno).

        Args:
            session: Sessão SQLAlchemy.
            investment_id: ID do investimento.

        Returns:
            Dict com: asset_return, cdi_return, alpha
        """
        investment = session.query(Investment).get(investment_id)
        if not investment:
            return {"asset_return": None, "cdi_return": None, "alpha": None}

        # Retorno simples do ativo
        invested = investment.amount_original or 0.0
        current = investment.amount or 0.0

        if invested <= 0:
            return {"asset_return": None, "cdi_return": None, "alpha": None}

        asset_return = (current - invested) / invested

        # Calcular CDI acumulado no período
        # Determinar período a partir da primeira transação ou created_at
        first_txn = (
            session.query(InvestmentTransaction)
            .filter(InvestmentTransaction.investment_id == investment_id)
            .order_by(InvestmentTransaction.date)
            .first()
        )

        if first_txn:
            start_date = first_txn.date
        elif investment.created_at:
            start_date = investment.created_at.date()
        else:
            return {
                "asset_return": round(asset_return, 4),
                "cdi_return": None,
                "alpha": None,
            }

        # Dias úteis aproximados (252 por ano)
        total_days = (date.today() - start_date).days
        business_days = int(total_days * 252 / 365)

        if business_days <= 0:
            return {
                "asset_return": round(asset_return, 4),
                "cdi_return": None,
                "alpha": None,
            }

        # CDI acumulado
        daily_rate = _cdi_daily_rate()
        cdi_return = (1 + daily_rate) ** business_days - 1

        alpha = asset_return - cdi_return

        return {
            "asset_return": round(asset_return, 4),
            "cdi_return": round(cdi_return, 4),
            "alpha": round(alpha, 4),
        }

    # =================================================================
    # Retorno completo de um investimento
    # =================================================================

    def compute_full_return(
        self,
        session: Session,
        investment_id: str,
    ) -> InvestmentReturnOut:
        """Calcula todas as métricas de rentabilidade de um investimento.

        Args:
            session: Sessão SQLAlchemy.
            investment_id: ID do investimento.

        Returns:
            InvestmentReturnOut com TWRR, MWRR, retorno simples e benchmark.
        """
        investment = session.query(Investment).get(investment_id)
        if not investment:
            return InvestmentReturnOut(
                investment_id=investment_id,
                simple_return=0.0,
            )

        # Retorno simples
        invested = investment.amount_original or 0.0
        current = investment.amount or 0.0
        simple_return = (
            (current - invested) / invested if invested > 0 else 0.0
        )

        # TWRR
        twrr = self.compute_return_twrr(session, investment_id)

        # MWRR
        mwrr = self.compute_return_mwrr(session, investment_id)

        # Benchmark
        benchmark = self.benchmark_vs_cdi(session, investment_id)

        return InvestmentReturnOut(
            investment_id=investment_id,
            investment_name=investment.name,
            twrr=twrr,
            mwrr=mwrr,
            simple_return=round(simple_return, 4),
            cdi_return=benchmark.get("cdi_return"),
            alpha=benchmark.get("alpha"),
        )
