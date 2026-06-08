"""
src/formatters.py
Funções utilitárias de formatação para exibição financeira no mercado brasileiro.
Todas as funções são puras (sem efeitos colaterais) e retornam strings prontas para UI.
"""


def formatar_moeda(valor, decimais: int = 2) -> str:
    """
    Formata um valor em reais brasileiros com notação pt-BR.

    Args:
        valor: Valor numérico a formatar.
        decimais: Casas decimais (padrão 2).

    Returns:
        str: Ex. 1234.56 → 'R$ 1.234,56'. Retorna 'N/D' para None ou inválido.

    Examples:
        >>> formatar_moeda(1234.56)
        'R$ 1.234,56'
        >>> formatar_moeda(None)
        'N/D'
    """
    if valor is None:
        return 'N/D'
    try:
        return (
            f'R$ {valor:,.{decimais}f}'
            .replace(',', 'X')
            .replace('.', ',')
            .replace('X', '.')
        )
    except (TypeError, ValueError):
        return 'N/D'


def formatar_percentual(valor, decimais: int = 1) -> str:
    """
    Formata um valor decimal como percentual em notação pt-BR.

    Args:
        valor: Valor decimal (ex: 0.145 representa 14,5%).
        decimais: Casas decimais (padrão 1).

    Returns:
        str: Ex. 0.145 → '14,5%'. Retorna 'N/D' para None ou inválido.

    Examples:
        >>> formatar_percentual(0.145)
        '14,5%'
        >>> formatar_percentual(0.0, decimais=2)
        '0,00%'
    """
    if valor is None:
        return 'N/D'
    try:
        return f'{valor * 100:.{decimais}f}%'.replace('.', ',')
    except (TypeError, ValueError):
        return 'N/D'


def formatar_multiplo(valor, decimais: int = 1) -> str:
    """
    Formata um múltiplo financeiro em notação pt-BR com sufixo 'x'.

    Args:
        valor: Valor numérico do múltiplo.
        decimais: Casas decimais (padrão 1).

    Returns:
        str: Ex. 5.48 → '5,5x'. Retorna 'N/D' para None ou inválido.

    Examples:
        >>> formatar_multiplo(5.48)
        '5,5x'
        >>> formatar_multiplo(None)
        'N/D'
    """
    if valor is None:
        return 'N/D'
    try:
        return f'{valor:.{decimais}f}x'.replace('.', ',')
    except (TypeError, ValueError):
        return 'N/D'


def formatar_milhoes(valor, decimais: int = 1) -> str:
    """
    Formata valor em R$ milhões ou bilhões de forma legível.

    Aplica escala automática: valores ≥ 1.000 são exibidos em bilhões (bi),
    valores menores em milhões (mi). Usa notação pt-BR.

    Args:
        valor: Valor em milhões de R$.
        decimais: Casas decimais (padrão 1).

    Returns:
        str: Ex. 14000.0 → 'R$ 14,0 bi' | 500.0 → 'R$ 500,0 mi'.
             Retorna 'N/D' para None ou inválido.

    Examples:
        >>> formatar_milhoes(14000.0)
        'R$ 14,0 bi'
        >>> formatar_milhoes(500.0)
        'R$ 500,0 mi'
    """
    if valor is None:
        return 'N/D'
    try:
        if abs(valor) >= 1_000:
            return f'R$ {valor / 1_000:.{decimais}f} bi'.replace('.', ',')
        else:
            return f'R$ {valor:.{decimais}f} mi'.replace('.', ',')
    except (TypeError, ValueError):
        return 'N/D'


def calcular_margem(preco_atual: float, preco_justo: float) -> float | None:
    """
    Calcula a margem de segurança entre preço atual e preço justo.

    Convenção:
        - Positivo → ativo com desconto (oportunidade de compra).
        - Negativo → ativo com prêmio (sobrevalorizado).

    Fórmula: (preco_justo - preco_atual) / preco_justo

    Args:
        preco_atual: Preço de mercado atual em R$.
        preco_justo: Preço justo calculado por um método de valuation em R$.

    Returns:
        float | None: Margem como decimal (ex: 0.33 = 33% de desconto),
                      ou None se os dados forem inválidos.

    Examples:
        >>> calcular_margem(27.50, 41.00)  # desconto de ~33%
        0.3292682926829268
        >>> calcular_margem(50.0, 41.00)   # prêmio de ~22%
        -0.21951219512195122
    """
    if preco_atual is None or preco_justo is None or preco_justo == 0:
        return None
    return (preco_justo - preco_atual) / preco_justo


def status_margem(margem: float | None) -> tuple[str, str]:
    """
    Converte a margem de segurança em status textual e emoji de cor.

    Escala:
        ≥ 33%  → Excelente oportunidade  🟢
        ≥ 15%  → Boa oportunidade        🟡
        ≥  0%  → Preço justo             🟠
        ≥ -20% → Ligeiramente caro       🔴
        <  -20% → Sobrevalorizado        🔴

    Args:
        margem: Margem de segurança decimal retornada por `calcular_margem`.

    Returns:
        tuple[str, str]: (descrição_textual, emoji).

    Examples:
        >>> status_margem(0.40)
        ('Excelente oportunidade', '🟢')
        >>> status_margem(-0.30)
        ('Sobrevalorizado', '🔴')
        >>> status_margem(None)
        ('N/D', '⚪')
    """
    if margem is None:
        return 'N/D', '⚪'
    if margem >= 0.33:
        return 'Excelente oportunidade', '🟢'
    elif margem >= 0.15:
        return 'Boa oportunidade', '🟡'
    elif margem >= 0.00:
        return 'Preço justo', '🟠'
    elif margem >= -0.20:
        return 'Ligeiramente caro', '🔴'
    else:
        return 'Sobrevalorizado', '🔴'
