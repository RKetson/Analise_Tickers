"""
src/models.py
Módulo de modelos de valuation para ações brasileiras.

Implementa 5 métodos clássicos:
  - Graham   : Valor intrínseco baseado em LPA e VPA
  - Bazin    : Preço-teto baseado em dividendos mínimos
  - Gordon   : Modelo de crescimento constante de dividendos
  - FCD      : Fluxo de Caixa Descontado em dois estágios
  - EV/EBITDA: Valuation por múltiplo setorial de EBITDA

Convenção de retorno
--------------------
Todos os métodos retornam um dict com as seguintes chaves garantidas:
    preco_justo : float | None  — preço justo calculado em R$ por ação
    valido      : bool          — True se o cálculo foi bem-sucedido
    erro        : str | None    — mensagem descritiva caso valido=False
    detalhes    : dict          — parâmetros intermediários para auditoria
"""

import math
import sys
import os

# Permite execução direta e importação como módulo do pacote
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------

def _resultado_erro(mensagem: str, detalhes: dict | None = None) -> dict:
    """Cria dict de resultado de erro padronizado."""
    return {
        'preco_justo': None,
        'valido': False,
        'aviso': False,
        'erro': mensagem,
        'detalhes': detalhes or {},
    }

def _resultado_aviso(mensagem: str, detalhes: dict | None = None) -> dict:
    """Cria dict indicando que o método não é aplicável (aviso visual mais leve)."""
    return {
        'preco_justo': None,
        'valido': False,
        'aviso': True,
        'erro': mensagem,
        'detalhes': detalhes or {},
    }


def _resultado_ok(preco_justo: float, detalhes: dict) -> dict:
    """Cria dict de resultado bem-sucedido padronizado."""
    return {
        'preco_justo': round(float(preco_justo), 2),
        'valido': True,
        'aviso': False,
        'erro': None,
        'detalhes': detalhes,
    }


# ---------------------------------------------------------------------------
# 1. Graham
# ---------------------------------------------------------------------------

def calcular_graham(
    lpa: float,
    vpa: float,
    margem_seguranca: float = config.MARGEM_SEGURANCA_GRAHAM,
) -> dict:
    """
    Valor Intrínseco de Benjamin Graham.

    Fórmula original adaptada:
        VI = √(22,5 × LPA × VPA)

    A margem de segurança de Graham (padrão 33%) é aplicada sobre VI,
    produzindo o preço de compra conservador ('preco_com_ms').

    Args:
        lpa: Lucro por Ação em R$. Deve ser positivo.
        vpa: Valor Patrimonial por Ação em R$. Deve ser positivo.
        margem_seguranca: Desconto percentual sobre VI (0.33 = 33%).

    Returns:
        dict com chaves 'preco_justo' (= VI sem MS), 'preco_com_ms' (= VI com MS),
        'valido', 'erro', 'detalhes'.
    """
    try:
        if lpa is None or vpa is None:
            return {**_resultado_erro('LPA ou VPA não informado'), 'preco_com_ms': None}

        lpa = float(lpa)
        vpa = float(vpa)

        if lpa <= 0:
            return {
                **_resultado_erro(
                    'LPA negativo ou zero — empresa com prejuízo; Graham não aplicável.',
                    {'lpa': lpa, 'vpa': vpa},
                ),
                'preco_com_ms': None,
            }
        if vpa <= 0:
            return {
                **_resultado_erro(
                    'VPA negativo — patrimônio líquido negativo; Graham não aplicável.',
                    {'lpa': lpa, 'vpa': vpa},
                ),
                'preco_com_ms': None,
            }

        valor_intrinseco = math.sqrt(config.MULTIPLICADOR_GRAHAM * lpa * vpa)
        preco_com_ms = valor_intrinseco * (1.0 - margem_seguranca)

        detalhes = {
            'lpa': lpa,
            'vpa': vpa,
            'multiplicador': config.MULTIPLICADOR_GRAHAM,
            'valor_intrinseco': round(valor_intrinseco, 2),
            'pl_implicito': round(valor_intrinseco / lpa, 2),
            'pvp_implicito': round(valor_intrinseco / vpa, 2),
            'margem_seguranca_aplicada': margem_seguranca,
            'formula': (
                fr'\begin{{aligned}} '
                fr'& \text{{1. Valor Intrínseco (Graham):}} \\[6pt] '
                fr'& VI = \sqrt{{22{{,}}5 \times \text{{LPA}} \times \text{{VPA}}}} \\[6pt] '
                fr'& VI = \sqrt{{22{{,}}5 \times {lpa:.2f} \times {vpa:.2f}}} = {valor_intrinseco:.2f} \\[12pt] '
                fr'& \text{{2. Aplicação da Margem de Segurança ({margem_seguranca*100:.0f}\%):}} \\[6pt] '
                fr'& P = VI \times (1 - \text{{Margem}}) \\[6pt] '
                fr'& P = {valor_intrinseco:.2f} \times (1 - {margem_seguranca:.2f}) = {preco_com_ms:.2f} '
                fr'\end{{aligned}}'
            ),
        }

        resultado = _resultado_ok(valor_intrinseco, detalhes)
        resultado['preco_com_ms'] = round(preco_com_ms, 2)
        return resultado

    except Exception as exc:
        return {**_resultado_erro(str(exc)), 'preco_com_ms': None}


# ---------------------------------------------------------------------------
# 2. Bazin
# ---------------------------------------------------------------------------

def calcular_bazin(
    dpa_historico: list,
    taxa_retorno: float = config.DY_MINIMO_BAZIN,
    usar_media: bool = True,
) -> dict:
    """
    Preço-Teto de Décio Bazin.

    Fórmula: Preço-Teto = DPA_base / taxa_retorno_mínima

    Usa a média dos últimos anos para suavizar distribuições atípicas
    (dividendos extraordinários, anos sem pagamento).

    Args:
        dpa_historico: Lista de DPA anuais [mais_antigo ... mais_recente].
                       Valores None ou zero são ignorados.
        taxa_retorno: Taxa mínima de DY exigida (padrão 6% = 0.06).
        usar_media: Se True, usa média dos valores; se False, usa apenas o último.

    Returns:
        dict padrão com 'preco_justo' (= preço-teto), 'valido', 'erro', 'detalhes'.
    """
    try:
        if not dpa_historico:
            return _resultado_erro('Histórico de DPA não informado.')

        dpas = [float(d) for d in dpa_historico if d is not None and float(d) > 0]

        if not dpas:
            return _resultado_erro('Nenhum DPA positivo no histórico.')

        if taxa_retorno <= 0:
            return _resultado_erro('Taxa de retorno deve ser positiva.')

        if usar_media:
            dpa_base = sum(dpas) / len(dpas)
            metodo_dpa = f'Média dos últimos {len(dpas)} ano(s)'
        else:
            dpa_base = dpas[-1]
            metodo_dpa = 'Último DPA declarado'

        preco_teto = dpa_base / taxa_retorno

        return _resultado_ok(
            preco_teto,
            {
                'dpa_historico': dpas,
                'dpa_base': round(dpa_base, 4),
                'dpa_mais_recente': dpas[-1],
                'taxa_retorno': taxa_retorno,
                'dy_implicito': taxa_retorno,
                'formula': (
                    fr'\begin{{aligned}} '
                    fr'& \text{{1. Preço Teto de Bazin:}} \\[6pt] '
                    fr'& P = \frac{{\text{{DPA Médio/Base}}}}{{\text{{Taxa Mínima de Retorno}}}} \\[8pt] '
                    fr'& P = \frac{{{dpa_base:.4f}}}{{{taxa_retorno:.4f}}} = {preco_teto:.2f} '
                    fr'\end{{aligned}}'
                ),
            },
        )
    except Exception as exc:
        return _resultado_erro(str(exc))


# ---------------------------------------------------------------------------
# 3. Gordon
# ---------------------------------------------------------------------------

def calcular_gordon(
    dpa_atual: float,
    g: float,
    k: float,
) -> dict:
    """
    Modelo de Gordon — Crescimento Constante de Dividendos (DDM).

    Fórmula: P = DPA × (1 + g) / (k - g)

    Pressuposto: crescimento de dividendos constante na perpetuidade.
    Válido apenas quando k > g (caso contrário o modelo diverge).

    Args:
        dpa_atual: DPA mais recente em R$ (base para projeção do próximo ano).
        g: Taxa anual de crescimento dos dividendos (ex: 0.08 = 8%).
        k: Taxa de desconto / custo do equity (ex: 0.175 = 17,5%).

    Returns:
        dict padrão com 'preco_justo', 'valido', 'erro', 'detalhes'.
    """
    try:
        if dpa_atual is None or g is None or k is None:
            return _resultado_erro(
                'Parâmetros incompletos — DPA, g ou k não informados.'
            )

        dpa_atual = float(dpa_atual)
        g = float(g)
        k = float(k)

        if dpa_atual <= 0:
            return _resultado_erro('DPA deve ser positivo para o modelo de Gordon.')

        if k <= g:
            return _resultado_erro(
                f'Taxa de desconto (k={k:.1%}) deve ser MAIOR que g ({g:.1%}). '
                'Modelo de Gordon diverge com k ≤ g.',
                {'dpa_atual': dpa_atual, 'g': g, 'k': k},
            )

        dpa_proximo = dpa_atual * (1.0 + g)
        preco_justo = dpa_proximo / (k - g)

        return _resultado_ok(
            preco_justo,
            {
                'dpa_atual': dpa_atual,
                'dpa_proximo_ano': round(dpa_proximo, 4),
                'spread_k_g': round(k - g, 4),
                'formula': (
                    fr'\begin{{aligned}} '
                    fr'& \text{{1. Projeção do Dividendo (Ano 1):}} \\[6pt] '
                    fr'& DPA_1 = DPA_0 \times (1 + g) \\[6pt] '
                    fr'& DPA_1 = {dpa_atual:.4f} \times (1 + {g:.4f}) = {dpa_proximo:.4f} \\[12pt] '
                    fr'& \text{{2. Gordon (Crescimento Perpétuo):}} \\[6pt] '
                    fr'& P = \frac{{DPA_1}}{{k - g}} \\[8pt] '
                    fr'& P = \frac{{{dpa_proximo:.4f}}}{{{k:.4f} - {g:.4f}}} = {preco_justo:.2f} '
                    fr'\end{{aligned}}'
                ),
            },
        )
    except Exception as exc:
        return _resultado_erro(str(exc))


# ---------------------------------------------------------------------------
# 4. FCD — Fluxo de Caixa Descontado em dois estágios
# ---------------------------------------------------------------------------

def calcular_fcd(
    fcl_base_milhoes: float,
    num_acoes_milhoes: float,
    wacc: float,
    g_crescimento_fase1: float,
    anos_fase1: int,
    g_terminal: float = config.G_TERMINAL_PADRAO,
    divida_liquida_milhoes: float = 0.0,
) -> dict:
    """
    Fluxo de Caixa Descontado (DCF) em dois estágios.

    Estrutura:
        Fase 1: FCL cresce a 'g_crescimento_fase1' por 'anos_fase1' anos.
                Cada fluxo é trazido a VP pela WACC.
        Valor Terminal: FCL do último ano cresce à perpetuidade por 'g_terminal'
                        (modelo de Gordon), descontado ao presente.

        EV  = VP(FCLs fase 1) + VP(Valor Terminal)
        PJ  = (EV − Dívida Líquida) / Número de Ações

    Args:
        fcl_base_milhoes: FCL do último exercício em R$ milhões. Deve ser > 0.
        num_acoes_milhoes: Número total de ações em milhões.
        wacc: Custo médio ponderado de capital (ex: 0.18 = 18%).
        g_crescimento_fase1: Crescimento anual do FCL na fase 1.
        anos_fase1: Duração da fase de crescimento em anos.
        g_terminal: Crescimento na perpetuidade (padrão = IPCA projetado).
        divida_liquida_milhoes: Dívida líquida em R$ milhões (subtrai do EV).

    Returns:
        dict padrão com 'preco_justo', 'valido', 'erro', 'detalhes'.
        'detalhes' inclui tabela de FCLs projetados por ano.
    """
    try:
        if fcl_base_milhoes is None or num_acoes_milhoes is None:
            return _resultado_erro('FCL ou número de ações não informado.')

        fcl = float(fcl_base_milhoes)
        n_acoes = float(num_acoes_milhoes)
        divida = float(divida_liquida_milhoes) if divida_liquida_milhoes is not None else 0.0

        if fcl <= 0:
            return _resultado_aviso(
                f'Empresa com FCL negativo (R$ {fcl:.0f} mi). '
                'O método de fluxo de caixa descontado não é aplicável a empresas que estão queimando caixa.',
                {'fcl_base': fcl},
            )

        if n_acoes <= 0:
            return _resultado_erro('Número de ações deve ser positivo.')

        if wacc <= g_terminal:
            return _resultado_erro(
                f'WACC ({wacc:.1%}) deve ser maior que g terminal ({g_terminal:.1%}). '
                'O modelo de dois estágios diverge.',
                {'wacc': wacc, 'g_terminal': g_terminal},
            )

        # --- Fase 1: desconto dos FCLs ---
        fcls_projetados = []
        fcl_ano = fcl
        soma_vp_fase1 = 0.0

        for t in range(1, int(anos_fase1) + 1):
            fcl_ano = fcl_ano * (1.0 + g_crescimento_fase1)
            vp = fcl_ano / (1.0 + wacc) ** t
            soma_vp_fase1 += vp
            fcls_projetados.append({
                'ano': t,
                'fcl_milhoes': round(fcl_ano, 2),
                'vp_milhoes': round(vp, 2),
            })

        # --- Valor Terminal (Gordon no último ano projetado) ---
        fcl_terminal = fcl_ano * (1.0 + g_terminal)
        valor_terminal = fcl_terminal / (wacc - g_terminal)
        vp_terminal = valor_terminal / (1.0 + wacc) ** int(anos_fase1)

        # --- Equity (Valor Justo) ---
        # ATENÇÃO FINANCEIRA: O FCL utilizado no sistema (FCO - CAPEX) parte do
        # Lucro Líquido, ou seja, as despesas financeiras JÁ FORAM PAGAS.
        # Trata-se do Fluxo de Caixa do Acionista (FCFE).
        # Logo, o Valor Presente destes fluxos JÁ É O VALOR DO EQUITY.
        # Subtrair a Dívida Líquida novamente configuraria dupla penalização.
        equity = soma_vp_fase1 + vp_terminal

        if equity <= 0:
            return _resultado_erro(
                'Equity resultante negativo.',
                {
                    'equity_milhoes': round(equity, 2),
                },
            )

        preco_justo = equity / n_acoes  # R$ por ação

        return _resultado_ok(
            preco_justo,
            {
                'fcl_base_milhoes': fcl,
                'wacc': wacc,
                'g_fase1': g_crescimento_fase1,
                'anos_fase1': anos_fase1,
                'g_terminal': g_terminal,
                'fcls_projetados': fcls_projetados,
                'soma_vp_fase1_milhoes': round(soma_vp_fase1, 2),
                'fcl_terminal_milhoes': round(fcl_terminal, 2),
                'valor_terminal_milhoes': round(valor_terminal, 2),
                'num_acoes_milhoes': n_acoes,
                'formula': (
                    fr'\begin{{aligned}} '
                    fr'& \text{{1. Valor Presente da Fase de Crescimento (1 a {int(anos_fase1)} anos):}} \\[6pt] '
                    fr'& VP(\text{{Fase 1}}) = \sum \frac{{FCL_t}}{{(1 + WACC)^t}} = {soma_vp_fase1:.2f} \text{{ mi}} \\[12pt] '
                    fr'& \text{{2. Valor Terminal (Perpetuidade):}} \\[6pt] '
                    fr'& VT = \frac{{FCL_{{último}} \times (1 + g_{{term}})}}{{WACC - g_{{term}}}} = {valor_terminal:.2f} \text{{ mi}} \\[8pt] '
                    fr'& VP(VT) = \frac{{{valor_terminal:.2f}}}{{(1 + {wacc:.4f})^{{{int(anos_fase1)}}}}} = {vp_terminal:.2f} \text{{ mi}} \\[12pt] '
                    fr'& \text{{3. Valor por Ação:}} \\[6pt] '
                    fr'& \text{{Equity}} = VP(\text{{Fase 1}}) + VP(VT) = {equity:.2f} \text{{ mi}} \\[8pt] '
                    fr'& P = \frac{{\text{{Equity}}}}{{\text{{Nº Ações}}}} = \frac{{{equity:.2f}}}{{{n_acoes:.2f}}} = {preco_justo:.2f} '
                    fr'\end{{aligned}}'
                ),
            },
        )
    except Exception as exc:
        return _resultado_erro(str(exc))


# ---------------------------------------------------------------------------
# 5. EV/EBITDA por múltiplo setorial
# ---------------------------------------------------------------------------

def calcular_ev_ebitda(
    ebitda_milhoes: float,
    multiplo_setor: float,
    divida_liquida_milhoes: float,
    num_acoes_milhoes: float,
) -> dict:
    """
    Valuation por Múltiplo EV/EBITDA setorial.

    Lógica:
        EV_justo = EBITDA × múltiplo_setor
        Equity   = EV_justo − Dívida Líquida
        PJ/ação  = Equity / Número de Ações

    Args:
        ebitda_milhoes: EBITDA em R$ milhões. Deve ser positivo.
        multiplo_setor: EV/EBITDA de referência do setor (ex: 7.0x para energia).
        divida_liquida_milhoes: Dívida líquida em R$ milhões.
        num_acoes_milhoes: Número de ações em milhões.

    Returns:
        dict padrão com 'preco_justo', 'valido', 'erro', 'detalhes'.
    """
    try:
        if multiplo_setor is not None and multiplo_setor <= 0:
            return _resultado_aviso('Múltiplo EV/EBITDA não se aplica a este setor (ex: Financeiro).')

        params = [ebitda_milhoes, multiplo_setor, divida_liquida_milhoes, num_acoes_milhoes]
        if any(v is None for v in params):
            return _resultado_erro(
                'Parâmetros incompletos para EV/EBITDA — '
                'verifique EBITDA, múltiplo, dívida e número de ações.'
            )

        ebitda = float(ebitda_milhoes)
        multiplo = float(multiplo_setor)
        divida = float(divida_liquida_milhoes)
        n_acoes = float(num_acoes_milhoes)

        if ebitda <= 0:
            return _resultado_aviso(
                f'EBITDA negativo (R$ {ebitda:.0f} mi). '
                'Múltiplo EV/EBITDA não aplicável a empresas com prejuízo operacional.'
            )

        if n_acoes <= 0:
            return _resultado_erro('Número de ações deve ser positivo.')

        ev_justo = ebitda * multiplo
        equity_justo = ev_justo - divida

        if equity_justo <= 0:
            return _resultado_erro(
                'Equity negativo — dívida supera o EV calculado pelo múltiplo.',
                {
                    'ev_justo_milhoes': round(ev_justo, 2),
                    'divida_liquida_milhoes': divida,
                    'equity_justo_milhoes': round(equity_justo, 2),
                },
            )

        preco_justo = equity_justo / n_acoes

        return _resultado_ok(
            preco_justo,
            {
                'ebitda_milhoes': ebitda,
                'multiplo_setor': multiplo,
                'ev_justo_milhoes': round(ev_justo, 2),
                'divida_liquida_milhoes': divida,
                'num_acoes_milhoes': n_acoes,
                'formula': (
                    fr'\begin{{aligned}} '
                    fr'& \text{{1. Enterprise Value (Valor da Firma):}} \\[6pt] '
                    fr'& EV = \text{{EBITDA}} \times \text{{Múltiplo Setorial}} \\[6pt] '
                    fr'& EV = {ebitda:.2f} \times {multiplo:.2f}x = {ev_justo:.2f} \text{{ mi}} \\[12pt] '
                    fr'& \text{{2. Patrimônio Líquido (Equity):}} \\[6pt] '
                    fr'& \text{{Equity}} = EV - \text{{Dívida Líquida}} \\[6pt] '
                    fr'& \text{{Equity}} = {ev_justo:.2f} - ({divida:.2f}) = {equity_justo:.2f} \text{{ mi}} \\[12pt] '
                    fr'& \text{{3. Valor por Ação:}} \\[6pt] '
                    fr'& P = \frac{{\text{{Equity}}}}{{\text{{Nº Ações}}}} = \frac{{{equity_justo:.2f}}}{{{n_acoes:.2f}}} = {preco_justo:.2f} '
                    fr'\end{{aligned}}'
                ),
            },
        )
    except Exception as exc:
        return _resultado_erro(str(exc))


# ---------------------------------------------------------------------------
# Função agregadora: calcula todos os métodos de uma vez
# ---------------------------------------------------------------------------

def calcular_buffett(lpa: float, roe: float, payout: float, wacc: float, pl_saida: float = config.BUFFETT_PL_MAXIMO) -> dict:
    """
    Método de Warren Buffett (EPS Growth / Equity Bond).
    
    Foco em rentabilidade sobre capital (ROE) e retenção de lucros para prever o 
    crescimento orgânico sustentável.

    Fórmula: g = ROE * (1 - Payout)
             LPA_futuro = LPA * (1 + g)^N
             Preço_futuro = LPA_futuro * P/L
             Preço_justo = Preço_futuro / (1 + WACC)^N

    Args:
        lpa: Lucro por Ação atual.
        roe: Return on Equity atual.
        payout: Taxa de distribuição de dividendos (DPA/LPA).
        wacc: Taxa de desconto exigida.
        pl_saida: Múltiplo P/L esperado no final da projeção.

    Returns:
        dict padrão de resultados.
    """
    try:
        if lpa is None or lpa <= 0:
            return _resultado_erro('LPA inválido ou negativo.')
        if roe is None or roe <= 0:
            return _resultado_erro('ROE inválido ou negativo. Crescimento inviável.')
        if wacc is None or wacc <= 0:
            return _resultado_erro('Taxa de desconto (WACC) inválida.')

        payout_val = payout if payout is not None else 0.50
        payout_val = max(0.0, min(payout_val, 1.0)) # Limita entre 0 e 100%

        retencao = 1.0 - payout_val
        g_sustentavel = roe * retencao
        
        # Limita crescimento a níveis sustentáveis conservadores (20%)
        g_sustentavel = min(g_sustentavel, 0.20)
        
        anos = config.BUFFETT_ANOS_PROJECAO
        
        vpl_dividendos = 0.0
        lpa_t = lpa
        for t in range(1, anos + 1):
            lpa_t *= (1 + g_sustentavel)
            dividendo_t = lpa_t * payout_val
            vpl_dividendos += dividendo_t / ((1 + wacc) ** t)
        
        pl_projetado = min(pl_saida, config.BUFFETT_PL_MAXIMO)
        preco_futuro = lpa_t * pl_projetado
        
        vpl_preco = preco_futuro / ((1 + wacc) ** anos)
        preco_justo = vpl_preco + vpl_dividendos
        
        return _resultado_ok(
            preco_justo,
            {
                'lpa_base': lpa,
                'roe': roe,
                'payout': payout_val,
                'taxa_retencao': retencao,
                'g_sustentavel': round(g_sustentavel, 4),
                'anos_projecao': anos,
                'lpa_futuro': round(lpa_t, 4),
                'pl_saida': pl_projetado,
                'preco_futuro': round(preco_futuro, 2),
                'vpl_preco': round(vpl_preco, 2),
                'vpl_dividendos': round(vpl_dividendos, 2),
                'taxa_desconto_wacc': round(wacc, 4),
                'formula': (
                    fr'\begin{{aligned}} '
                    fr'& \text{{1. Crescimento Sustentável (g):}} \\[6pt] '
                    fr'& g = ROE \times (1 - \text{{Payout}}) = {roe:.2f} \times (1 - {payout_val:.2f}) = {g_sustentavel:.4f} \\[12pt] '
                    fr'& \text{{2. Valor de Saída (Ano {anos}):}} \\[6pt] '
                    fr'& LPA_{{{anos}}} = LPA_0 \times (1 + g)^{{{anos}}} = {lpa:.2f} \times (1 + {g_sustentavel:.4f})^{{{anos}}} = {lpa_t:.2f} \\[6pt] '
                    fr'& P_{{{anos}}} = LPA_{{{anos}}} \times \text{{P/L}}_{{Alvo}} = {lpa_t:.2f} \times {pl_projetado:.2f} = {preco_futuro:.2f} \\[12pt] '
                    fr'& \text{{3. Valor Presente (Desconto = {wacc*100:.1f}\%):}} \\[6pt] '
                    fr'& VP(P_{{{anos}}}) = \frac{{{preco_futuro:.2f}}}{{(1 + {wacc:.4f})^{{{anos}}}}} = {vpl_preco:.2f} \\[8pt] '
                    fr'& VP(\text{{Dividendos recebidos}}) = {vpl_dividendos:.2f} \\[8pt] '
                    fr'& P = VP(P_{{{anos}}}) + VP(\text{{Dividendos}}) = {preco_justo:.2f} '
                    fr'\end{{aligned}}'
                ),
            }
        )
    except Exception as e:
        return _resultado_erro(str(e))

def calcular_todos(empresa_dados: dict, parametros: dict) -> dict:
    """
    Calcula todos os 5 métodos de valuation para uma empresa e agrega resultados.

    Convenções de 'parametros':
        wacc              : WACC para FCD e Gordon (padrão Selic + 4%)
        g_fcd             : Crescimento FCL fase 1 (padrão = crescimento_lucro_5a)
        g_gordon          : Crescimento DPA para Gordon (padrão = crescimento_dpa_5a)
        k_gordon          : Custo do equity Gordon (padrão = wacc)
        taxa_bazin        : Taxa mínima DY Bazin (padrão 6%)
        bazin_usar_media  : bool, usar média do DPA (padrão True)
        margem_seguranca  : Margem Graham (padrão 33%)
        multiplo_ev_ebitda: Múltiplo EV/EBITDA setorial
        anos_projecao     : Anos projeção FCD (padrão 10)
        g_terminal        : Crescimento terminal FCD (padrão IPCA)

    Args:
        empresa_dados: Dicionário de dados fundamentais da empresa (vem do data_loader).
        parametros: Dicionário de parâmetros ajustáveis pelo usuário.

    Returns:
        dict com resultados por método + chaves especiais:
            '_media'              : float | None — média dos preços justos válidos
            '_num_metodos_validos': int — quantidade de métodos que convergiram
    """
    d = empresa_dados
    p = parametros

    wacc_padrao = p.get('wacc', config.SELIC_ANUAL + 0.04)
    dpa_hist = d.get('dpa_historico', [])
    dpa_recente = dpa_hist[-1] if dpa_hist else None

    resultados: dict = {}

    # --- Graham ---
    resultados['graham'] = calcular_graham(
        lpa=d.get('lpa'),
        vpa=d.get('vpa'),
        margem_seguranca=p.get('margem_seguranca', config.MARGEM_SEGURANCA_GRAHAM),
    )

    # --- Bazin ---
    resultados['bazin'] = calcular_bazin(
        dpa_historico=dpa_hist,
        taxa_retorno=p.get('taxa_bazin', config.DY_MINIMO_BAZIN),
        usar_media=p.get('bazin_usar_media', True),
    )

    # --- Gordon ---
    g_gordon = p.get('g_gordon', d.get('crescimento_dpa_5a', 0.08))
    k_gordon = p.get('k_gordon', wacc_padrao)
    resultados['gordon'] = calcular_gordon(
        dpa_atual=dpa_recente,
        g=g_gordon,
        k=k_gordon,
    )

    # --- FCD ---
    resultados['fcd'] = calcular_fcd(
        fcl_base_milhoes=d.get('fcl_milhoes'),
        num_acoes_milhoes=d.get('num_acoes_milhoes_param'),
        wacc=wacc_padrao,
        g_crescimento_fase1=p.get('g_fcd', d.get('crescimento_lucro_5a', 0.06)),
        anos_fase1=p.get('anos_projecao', config.ANOS_PROJECAO_FCD),
        g_terminal=p.get('g_terminal', config.G_TERMINAL_PADRAO),
        divida_liquida_milhoes=d.get('divida_liquida_milhoes', 0.0),
    )

    # --- EV/EBITDA ---
    resultados['ev_ebitda'] = calcular_ev_ebitda(
        ebitda_milhoes=d.get('ebitda_milhoes'),
        multiplo_setor=p.get('multiplo_ev_ebitda'),
        divida_liquida_milhoes=d.get('divida_liquida_milhoes', 0.0),
        num_acoes_milhoes=d.get('num_acoes_milhoes_param'),
    )

    # --- Buffett ---
    roe = d.get('roe')
    lpa = d.get('lpa')
    payout_default = 0.50
    payout = p.get('payout_buffett', payout_default)
    
    pl_setor_default = config.MULTIPLO_PL_SETOR.get(d.get('setor', ''), config.BUFFETT_PL_MAXIMO)
    pl_setor = p.get('pl_buffett', pl_setor_default)
    
    resultados['buffett'] = calcular_buffett(
        lpa=lpa,
        roe=roe,
        payout=payout,
        wacc=wacc_padrao,
        pl_saida=pl_setor
    )

    # --- Agregação ---
    precos_validos = [
        r['preco_justo']
        for r in resultados.values()
        if isinstance(r, dict) and r.get('valido') and r.get('preco_justo') is not None
    ]

    resultados['_media'] = (
        round(sum(precos_validos) / len(precos_validos), 2)
        if precos_validos
        else None
    )
    resultados['_num_metodos_validos'] = len(precos_validos)

    return resultados
