"""
src/analysis.py
Módulo de análise qualitativa conservadora para empresas brasileiras.

Implementa filtros financeiros baseados em:
  - Endividamento (Dívida Líquida / EBITDA)
  - Intensidade de CAPEX (CAPEX / EBITDA)
  - Rentabilidade (ROE, LPA)
  - Qualidade e consistência de dividendos (DPA histórico)

Cada função retorna dicts padronizados com chaves:
    status  : 'ok' | 'atencao' | 'alerta' | 'aviso' | 'info'
    emoji   : str  — ícone colorido para UI
    mensagem: str  — texto explicativo para o investidor
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------

def _alerta(status: str, emoji: str, mensagem: str, **extras) -> dict:
    """Cria dict de alerta padronizado."""
    return {'status': status, 'emoji': emoji, 'mensagem': mensagem, **extras}


# ---------------------------------------------------------------------------
# 1. Endividamento
# ---------------------------------------------------------------------------

def analisar_endividamento(
    divida_liquida_milhoes: float | None,
    ebitda_milhoes: float | None,
    setor: str,
) -> dict:
    """
    Avalia o nível de endividamento medido por Dívida Líquida / EBITDA.

    Bancos e seguradoras usam métricas específicas de solvência (Basileia,
    índice de cobertura) e não são avaliados por este múltiplo.

    Escala de risco (para demais setores):
        < 0   → Caixa líquido           🟢 ok
        0–1,5 → Endividamento baixo     🟢 ok
        1,5–2,5 → Moderado             🟡 ok
        2,5–3,0 → Elevado (próximo do limite) 🟠 atenção
        > 3,0 → ALTO — acima do limite  🔴 alerta

    Args:
        divida_liquida_milhoes: Dívida líquida em R$ milhões (pode ser negativa
                                se a empresa tem caixa líquido).
        ebitda_milhoes: EBITDA em R$ milhões.
        setor: Setor da empresa (ex: 'banco', 'energia').

    Returns:
        dict com 'status', 'emoji', 'mensagem', 'valor' (ratio), 'limite'.
    """
    # Bancos e seguradoras: métrica não aplicável
    if setor in ('banco', 'seguro'):
        return _alerta(
            'info', 'ℹ️',
            'Bancos/Seguradoras: endividamento avaliado por Basileia/Índice de Solvência '
            '(não por Dívida/EBITDA).',
            valor=None, limite=None,
        )

    if divida_liquida_milhoes is None or ebitda_milhoes is None or ebitda_milhoes <= 0:
        return _alerta(
            'aviso', '⚠️',
            'Dados insuficientes para calcular Dívida Líquida / EBITDA.',
            valor=None, limite=config.MAX_DIVIDA_EBITDA,
        )

    ratio = divida_liquida_milhoes / ebitda_milhoes

    if ratio < 0:
        return _alerta(
            'ok', '🟢',
            f'Empresa em posição de caixa líquido (Dívida/EBITDA: {ratio:.1f}x) — '
            'excelente solidez financeira.',
            valor=ratio, limite=config.MAX_DIVIDA_EBITDA,
        )
    elif ratio <= 1.5:
        return _alerta(
            'ok', '🟢',
            f'Endividamento baixo ({ratio:.1f}x EBITDA) — posição financeira confortável.',
            valor=ratio, limite=config.MAX_DIVIDA_EBITDA,
        )
    elif ratio <= 2.5:
        return _alerta(
            'ok', '🟡',
            f'Endividamento moderado ({ratio:.1f}x EBITDA) — monitorar evolução.',
            valor=ratio, limite=config.MAX_DIVIDA_EBITDA,
        )
    elif ratio <= config.MAX_DIVIDA_EBITDA:
        return _alerta(
            'atencao', '🟠',
            f'Endividamento elevado ({ratio:.1f}x EBITDA) — '
            f'próximo do limite conservador de {config.MAX_DIVIDA_EBITDA}x.',
            valor=ratio, limite=config.MAX_DIVIDA_EBITDA,
        )
    else:
        return _alerta(
            'alerta', '🔴',
            f'Endividamento ALTO ({ratio:.1f}x EBITDA) — '
            f'ACIMA do limite conservador de {config.MAX_DIVIDA_EBITDA}x. '
            'Considerar redução de exposição.',
            valor=ratio, limite=config.MAX_DIVIDA_EBITDA,
        )


# ---------------------------------------------------------------------------
# 2. CAPEX
# ---------------------------------------------------------------------------

def analisar_capex(
    capex_milhoes: float | None,
    ebitda_milhoes: float | None,
) -> dict:
    """
    Avalia a intensidade de investimento de capital (CAPEX) relativa ao EBITDA.

    CAPEX/EBITDA alto indica que grande parte do lucro operacional é
    consumida por reinvestimento, comprimindo o FCL e a capacidade de
    distribuir dividendos. O FCD fica menos confiável em empresas intensivas.

    Escala:
        ≤ 30% → Baixo — alta conversão de lucro em caixa    🟢 ok
        ≤ 50% → Moderado — conversão razoável               🟡 ok
        ≤ 70% → Alto — FCL comprimido; FCD com cautela      🟠 atenção
        > 70% → Muito alto — empresa intensiva em capital   🔴 alerta

    Args:
        capex_milhoes: CAPEX em R$ milhões (valor absoluto positivo).
        ebitda_milhoes: EBITDA em R$ milhões.

    Returns:
        dict com 'status', 'emoji', 'mensagem', 'valor' (ratio CAPEX/EBITDA).
    """
    if capex_milhoes is None or ebitda_milhoes is None or ebitda_milhoes <= 0:
        return _alerta(
            'aviso', '⚠️',
            'Dados insuficientes para analisar intensidade de CAPEX.',
            valor=None,
        )

    ratio = abs(float(capex_milhoes)) / float(ebitda_milhoes)

    if ratio <= 0.30:
        return _alerta(
            'ok', '🟢',
            f'CAPEX/EBITDA baixo ({ratio:.0%}) — alta conversão de EBITDA em caixa livre.',
            valor=ratio,
        )
    elif ratio <= 0.50:
        return _alerta(
            'ok', '🟡',
            f'CAPEX/EBITDA moderado ({ratio:.0%}) — conversão razoável de caixa.',
            valor=ratio,
        )
    elif ratio <= config.MAX_CAPEX_EBITDA:
        return _alerta(
            'atencao', '🟠',
            f'CAPEX/EBITDA alto ({ratio:.0%}) — FCL comprimido. '
            'Use o FCD com cautela e verifique o CAPEX de manutenção vs. expansão.',
            valor=ratio,
        )
    else:
        return _alerta(
            'alerta', '🔴',
            f'CAPEX/EBITDA muito alto ({ratio:.0%}) — empresa intensiva em capital. '
            'FCL pode ser distorcido; priorizar análise por EV/EBITDA.',
            valor=ratio,
        )


# ---------------------------------------------------------------------------
# 3. Rentabilidade
# ---------------------------------------------------------------------------

def analisar_rentabilidade(
    roe: float | None,
    lpa: float | None,
    setor: str,
) -> list[dict]:
    """
    Avalia a rentabilidade da empresa com foco em ROE e LPA.

    Um LPA negativo invalida Graham e Bazin automaticamente.
    Um ROE abaixo do mínimo conservador (10%) indica destruição de valor
    para o acionista a longo prazo.

    Args:
        roe: Retorno sobre Patrimônio Líquido como decimal (ex: 0.18 = 18%).
        lpa: Lucro por Ação em R$.
        setor: Setor da empresa.

    Returns:
        list[dict]: Lista de alertas individuais sobre rentabilidade.
    """
    alertas = []

    # LPA
    if lpa is not None:
        lpa_f = float(lpa)
        if lpa_f <= 0:
            alertas.append(_alerta(
                'alerta', '🔴',
                f'LPA NEGATIVO (R$ {lpa_f:.2f}) — empresa com prejuízo. '
                'Graham e Bazin NÃO são aplicáveis.',
            ))
        else:
            alertas.append(_alerta(
                'ok', '🟢',
                f'LPA positivo (R$ {lpa_f:.2f}) — empresa lucrativa.',
            ))
    else:
        alertas.append(_alerta(
            'aviso', '⚠️',
            'LPA não disponível — não é possível verificar lucratividade.',
        ))

    # ROE
    if roe is not None:
        roe_f = float(roe)
        if roe_f >= 0.20:
            alertas.append(_alerta(
                'ok', '🟢',
                f'ROE excelente ({roe_f:.1%}) — alta rentabilidade do patrimônio.',
            ))
        elif roe_f >= config.MIN_ROE:
            alertas.append(_alerta(
                'ok', '🟡',
                f'ROE adequado ({roe_f:.1%}) — acima do mínimo conservador '
                f'({config.MIN_ROE:.0%}).',
            ))
        elif roe_f >= 0:
            alertas.append(_alerta(
                'atencao', '🟠',
                f'ROE baixo ({roe_f:.1%}) — abaixo do mínimo conservador '
                f'de {config.MIN_ROE:.0%}. Possível destruição de valor a longo prazo.',
            ))
        else:
            alertas.append(_alerta(
                'alerta', '🔴',
                f'ROE NEGATIVO ({roe_f:.1%}) — patrimônio sendo consumido.',
            ))
    else:
        alertas.append(_alerta(
            'aviso', '⚠️',
            'ROE não disponível — não é possível avaliar rentabilidade do patrimônio.',
        ))

    return alertas


# ---------------------------------------------------------------------------
# 4. Dividendos
# ---------------------------------------------------------------------------

def analisar_dividendos(
    dpa_historico: list,
    preco_atual: float | None,
    setor: str,
) -> list[dict]:
    """
    Avalia consistência e qualidade do histórico de dividendos.

    Critérios:
        - Anos sem pagamento comprometem a consistência (critério Bazin).
        - DY médio abaixo de 4% desqualifica o método Bazin padrão.
        - Tendência de crescimento é o principal sinal de qualidade.

    Args:
        dpa_historico: Lista de DPA anuais (R$ por ação) [mais_antigo ... mais_recente].
        preco_atual: Preço atual em R$ (usado para calcular DY médio).
        setor: Setor da empresa.

    Returns:
        list[dict]: Lista de alertas sobre dividendos.
    """
    alertas = []

    if not dpa_historico:
        return [_alerta('aviso', '⚠️', 'Histórico de dividendos não disponível.')]

    dpas = [float(d) for d in dpa_historico if d is not None]
    if not dpas:
        return [_alerta('aviso', '⚠️', 'Nenhum DPA válido no histórico.')]

    # Anos sem pagamento
    zeros = sum(1 for d in dpas if d == 0)
    if zeros > 0:
        alertas.append(_alerta(
            'atencao', '🟠',
            f'{zeros} ano(s) sem pagamento de dividendos no histórico — '
            'consistência comprometida; método Bazin menos confiável.',
        ))
    else:
        alertas.append(_alerta(
            'ok', '🟢',
            f'Dividendos pagos em todos os {len(dpas)} ano(s) do histórico — boa consistência.',
        ))

    # Tendência de crescimento
    dpas_positivos = [d for d in dpas if d > 0]
    if len(dpas_positivos) >= 2:
        n = len(dpas_positivos) - 1
        try:
            cagr_dpa = (dpas_positivos[-1] / dpas_positivos[0]) ** (1.0 / n) - 1.0
        except (ZeroDivisionError, ValueError):
            cagr_dpa = 0.0

        if cagr_dpa > 0.05:
            alertas.append(_alerta(
                'ok', '🟢',
                f'Crescimento de dividendos: {cagr_dpa:.1%} a.a. (CAGR {n} anos) — '
                'sólida trajetória de valorização dos proventos.',
            ))
        elif cagr_dpa > 0:
            alertas.append(_alerta(
                'ok', '🟡',
                f'Crescimento modesto de dividendos: {cagr_dpa:.1%} a.a. (CAGR {n} anos).',
            ))
        else:
            alertas.append(_alerta(
                'atencao', '🟠',
                f'Dividendos em queda: {cagr_dpa:.1%} a.a. (CAGR {n} anos) — '
                'atenção à sustentabilidade dos proventos.',
            ))

    # DY médio vs. piso Bazin
    if preco_atual and preco_atual > 0:
        dpa_medio = sum(dpas) / len(dpas)
        dy_medio = dpa_medio / preco_atual

        if dy_medio >= config.DY_MINIMO_BAZIN:
            alertas.append(_alerta(
                'ok', '🟢',
                f'DY médio ({dy_medio:.1%}) ≥ mínimo Bazin ({config.DY_MINIMO_BAZIN:.0%}) — '
                'elegível para valuation por Bazin.',
            ))
        elif dy_medio >= config.MIN_DY_BAZIN:
            alertas.append(_alerta(
                'ok', '🟡',
                f'DY médio ({dy_medio:.1%}) — abaixo do ideal Bazin ({config.DY_MINIMO_BAZIN:.0%}), '
                f'mas acima do mínimo absoluto ({config.MIN_DY_BAZIN:.0%}). '
                'Bazin aplicável com ressalvas.',
            ))
        else:
            alertas.append(_alerta(
                'atencao', '🟡',
                f'DY médio ({dy_medio:.1%}) < mínimo Bazin ({config.DY_MINIMO_BAZIN:.0%}) — '
                'método Bazin NÃO indicado para esta empresa. Prefira FCD ou EV/EBITDA.',
            ))

    return alertas


# ---------------------------------------------------------------------------
# Relatório completo
# ---------------------------------------------------------------------------

def gerar_relatorio_completo(
    empresa_config: dict,
    dados: dict,
    preco_atual: float,
) -> dict:
    """
    Gera relatório qualitativo completo de uma empresa.

    Consolida análises de endividamento, CAPEX, rentabilidade e dividendos,
    além de incluir alertas do analista e eventos não-recorrentes cadastrados
    no companies.json. Calcula um score de qualidade de 0–10.

    Lógica do score (base = 7):
        Endividamento alerta  → −2
        Endividamento atenção → −1
        Endividamento baixo   → +1
        CAPEX alerta          → −1
        CAPEX baixo           → +1
        LPA negativo          → −2
        LPA positivo          → +1

    Args:
        empresa_config: Configuração da empresa do companies.json (setor, alertas, etc.).
        dados: Dados fundamentais da empresa (lpa, roe, divida, etc.).
        preco_atual: Preço de mercado atual em R$.

    Returns:
        dict com:
            endividamento       : dict — análise de dívida
            capex               : dict — análise de CAPEX
            rentabilidade       : list[dict] — alertas de rentabilidade
            dividendos          : list[dict] — alertas de dividendos
            alertas_analista    : list[str] — avisos curados do analista
            eventos_nao_recorrentes: list[dict] — eventos que distorcem os números
            score_qualidade     : int (0–10)
    """
    setor = empresa_config.get('setor', '')

    analise_endividamento = analisar_endividamento(
        divida_liquida_milhoes=dados.get('divida_liquida_milhoes'),
        ebitda_milhoes=dados.get('ebitda_milhoes'),
        setor=setor,
    )

    analise_capex = analisar_capex(
        capex_milhoes=dados.get('capex_milhoes'),
        ebitda_milhoes=dados.get('ebitda_milhoes'),
    )

    analise_rentabilidade = analisar_rentabilidade(
        roe=dados.get('roe'),
        lpa=dados.get('lpa'),
        setor=setor,
    )

    analise_dividendos = analisar_dividendos(
        dpa_historico=dados.get('dpa_historico', []),
        preco_atual=preco_atual,
        setor=setor,
    )

    relatorio = {
        'endividamento': analise_endividamento,
        'capex': analise_capex,
        'rentabilidade': analise_rentabilidade,
        'dividendos': analise_dividendos,
        'alertas_analista': empresa_config.get('alertas_analista', []),
        'eventos_nao_recorrentes': empresa_config.get('eventos_nao_recorrentes', []),
    }

    # --- Score de qualidade (0–10) ---
    score = 7  # base

    end_status = analise_endividamento.get('status')
    end_emoji = analise_endividamento.get('emoji')
    if end_status == 'alerta':
        score -= 2
    elif end_status == 'atencao':
        score -= 1
    elif end_status == 'ok' and end_emoji == '🟢':
        score += 1

    cap_status = analise_capex.get('status')
    cap_emoji = analise_capex.get('emoji')
    if cap_status == 'alerta':
        score -= 1
    elif cap_status == 'ok' and cap_emoji == '🟢':
        score += 1

    lpa = dados.get('lpa')
    if lpa is not None:
        try:
            if float(lpa) > 0:
                score += 1
            else:
                score -= 2
        except (TypeError, ValueError):
            pass

    relatorio['score_qualidade'] = max(0, min(10, score))
    return relatorio
