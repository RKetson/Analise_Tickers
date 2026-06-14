"""
src/fii_classifier.py
Classificador de segmento de FIIs baseado em regras e palavras-chave.

Estratégia em 3 camadas:
  1. Palavras-chave no NOME do fundo (mais confiável)
  2. Padrão pelo prefixo do TICKER (heurística conhecida)
  3. Normalização do segmento original do Fundamentus

Segmentos padronizados:
  - Logística
  - Shopping
  - Lajes Corporativas
  - Papel (CRI/CRA)
  - Residencial
  - Hotel
  - Híbrido
  - Outros

Cache em data/fii_classificacoes.json (editável manualmente).
"""

import os
import json
import re
import pandas as pd

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_CACHE_PATH = os.path.join(_BASE_DIR, "data", "fii_classificacoes.json")

# ── Segmentos canônicos ───────────────────────────────────────────────────────
SEGMENTOS = [
    "Logística",
    "Shopping",
    "Lajes Corporativas",
    "Papel (CRI/CRA)",
    "Fundo de Fundos",
    "Residencial",
    "Hotel",
    "Hospital",
    "Híbrido",
    "Outros",
]

# ── Camada 1: palavras-chave no nome do fundo ─────────────────────────────────
# Ordem importa: mais específico primeiro
_KEYWORDS_NOME: list[tuple[str, list[str]]] = [
    ("Hotel", [
        "hotel", "hotelaria", "hospitality",
    ]),
    ("Shopping", [
        "shopping", "mall", "varejo", "comercio", "comércio",
        "shoppings", "retail",
    ]),
    ("Logística", [
        "logistic", "logística", "logistico", "logístico",
        "galpao", "galpão", "industrial", "armazem", "armazém",
        "centro de distribuicao", "centro de distribuição",
        "multilog", "brlog",
    ]),
    ("Lajes Corporativas", [
        "laje", "lajes", "escritorio", "escritório", "corporate",
        "offices", "office", "corporativo", "corporativos",
        "torre", "business", "empresarial", "centro empresarial",
        "comercial fii", "edifício", "edificio",
    ]),
    ("Papel (CRI/CRA)", [
        "cri", "cra", "recebiveis", "recebíveis", "credito", "crédito",
        "papel", "imobiliario fundo", "imobiliário fundo",
        "agro", "debenture", "debênture", "fiagro",
        "high grade", "high yield", "cri/cra",
    ]),
    ("Fundo de Fundos", [
        "fof", "fundo de fundos", "fofii",
    ]),
    ("Residencial", [
        "residencial", "habitacional", "moradias", "moradia",
        "vila", "apartamento", "apartamentos", "casa", "casas",
        "multiresidencial", "multi residencial",
    ]),
    ("Híbrido", [
        "hibrido", "híbrido", "diversificado", "multiativos",
        "multi-ativos", "multiativo",
    ]),
]

# ── Camada 2: prefixo do ticker → segmento ───────────────────────────────────
_TICKER_PREFIXO: dict[str, str] = {
    # Logística
    "HGLG": "Logística",
    "BRCO": "Logística",
    "BTLG": "Logística",
    "GARE": "Logística",
    "LVBI": "Logística",
    "XPLG": "Logística",
    "VILG": "Logística",
    "MALL": "Shopping",      # MALL11
    "VISC": "Shopping",
    "XPML": "Shopping",
    "HSML": "Shopping",
    "ALSC": "Shopping",
    "FLMA": "Shopping",
    "BPML": "Shopping",
    "GSFI": "Shopping",
    "ATSA": "Shopping",
    # Lajes Corporativas
    "BRCR": "Lajes Corporativas",
    "RECT": "Lajes Corporativas",
    "PVBI": "Lajes Corporativas",
    "HGPO": "Lajes Corporativas",
    "RCRB": "Lajes Corporativas",
    "VINO": "Lajes Corporativas",
    "JSRE": "Lajes Corporativas",
    "PATC": "Lajes Corporativas",
    # Papel
    "MXRF": "Papel (CRI/CRA)",
    "KNCR": "Papel (CRI/CRA)",
    "KNIP": "Papel (CRI/CRA)",
    "HGCR": "Papel (CRI/CRA)",
    "VRTA": "Papel (CRI/CRA)",
    "IRDM": "Papel (CRI/CRA)",
    "BCFF": "Fundo de Fundos",
    "RBRD": "Papel (CRI/CRA)",
    "CPTS": "Papel (CRI/CRA)",
    "XPCI": "Papel (CRI/CRA)",
    "HABT": "Papel (CRI/CRA)",
    "RBRR": "Papel (CRI/CRA)",
    "VGIR": "Papel (CRI/CRA)",
    "RECR": "Papel (CRI/CRA)",
    "RBRY": "Papel (CRI/CRA)",
    "HCTR": "Papel (CRI/CRA)",
    "DEVA": "Papel (CRI/CRA)",
    "URPR": "Papel (CRI/CRA)",
    "VSLH": "Papel (CRI/CRA)",
    # FOFs
    "HFOF": "Fundo de Fundos",
    "BPFF": "Fundo de Fundos",
    "CXRI": "Fundo de Fundos",
    "CRFF": "Fundo de Fundos",
    "BBFO": "Fundo de Fundos",
    "BCIA": "Fundo de Fundos",
    # Hotel
    "HTMX": "Hotel",
    "XPHT": "Hotel",
    "BPHA": "Hotel",
    "HGHY": "Hotel",
    # Residencial
    "HGRU": "Residencial",
    "RZAK": "Residencial",
    "RBRS": "Residencial",
    "JFLL": "Residencial",
    # Hospital
    "HUCG": "Hospital",
    "NSLU": "Hospital",
    "NVHO": "Hospital",
    # Híbrido
    "KNRI": "Híbrido",
    "ALZR": "Híbrido",
}

# ── Camada 3: mapeamento do segmento original do Fundamentus ──────────────────
# Baseado nos valores reais observados na página:
# Multicategoria, Outros, Logística, Títulos e Val. Mob., Escritórios,
# Shoppings, Residencial, Híbrido, Lajes Corporativas, Hospital, Varejo, Hotel
_FUNDAMENTUS_MAP: dict[str, str] = {
    # Logística
    "logistica":            "Logística",
    "logística":            "Logística",
    "galpoes":              "Logística",
    "galpões":              "Logística",
    "industrial":           "Logística",
    # Shopping / Varejo
    "shopping":             "Shopping",
    "shoppings":            "Shopping",
    "varejo":               "Shopping",
    "mall":                 "Shopping",
    # Lajes / Escritórios
    "lajes corporativas":   "Lajes Corporativas",
    "lajes":                "Lajes Corporativas",
    "escritorios":          "Lajes Corporativas",
    "escritórios":          "Lajes Corporativas",
    "corporate":            "Lajes Corporativas",
    "comercial":            "Lajes Corporativas",
    # Papel
    "titulos e val. mob.":  "Papel (CRI/CRA)",
    "títulos e val. mob.":  "Papel (CRI/CRA)",
    "recebiveis":           "Papel (CRI/CRA)",
    "recebíveis":           "Papel (CRI/CRA)",
    "credito":              "Papel (CRI/CRA)",
    "crédito":              "Papel (CRI/CRA)",
    "papel":                "Papel (CRI/CRA)",
    "cri":                  "Papel (CRI/CRA)",
    # Residencial
    "residencial":          "Residencial",
    # Hospital
    "hospital":             "Hospital",
    # Hotel
    "hotel":                "Hotel",
    "hotelaria":            "Hotel",
    # Híbrido / Multicategoria
    "hibrido":              "Híbrido",
    "híbrido":              "Híbrido",
    "multicategoria":       "Híbrido",
    "diversificado":        "Híbrido",
    "multi":                "Híbrido",
}


def _normalizar_texto(texto: str) -> str:
    """Remove acentos e converte para minúsculas para comparação."""
    import unicodedata
    nfkd = unicodedata.normalize("NFKD", str(texto))
    ascii_str = nfkd.encode("ascii", errors="ignore").decode("ascii")
    return ascii_str.lower().strip()


def _classificar_por_nome(nome: str) -> str | None:
    """Camada 1: busca palavras-chave no nome do fundo."""
    nome_norm = _normalizar_texto(nome)
    for segmento, keywords in _KEYWORDS_NOME:
        for kw in keywords:
            kw_norm = _normalizar_texto(kw)
            if kw_norm in nome_norm:
                return segmento
    return None


def _classificar_por_ticker(ticker: str) -> str | None:
    """Camada 2: heurística por prefixo do ticker."""
    prefix4 = ticker[:4].upper()
    return _TICKER_PREFIXO.get(prefix4)


def _classificar_por_fundamentus(segmento_original: str) -> str | None:
    """Camada 3: normaliza o segmento original do Fundamentus."""
    seg_norm = _normalizar_texto(segmento_original)
    # Busca exata
    if seg_norm in _FUNDAMENTUS_MAP:
        return _FUNDAMENTUS_MAP[seg_norm]
    # Busca parcial (substring)
    for chave, valor in _FUNDAMENTUS_MAP.items():
        if chave in seg_norm or seg_norm in chave:
            return valor
    return None


def _carregar_cache() -> dict:
    """Carrega classificações previamente salvas."""
    if os.path.exists(_CACHE_PATH):
        try:
            with open(_CACHE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _salvar_cache(classificacoes: dict) -> None:
    """Persiste as classificações em disco."""
    os.makedirs(os.path.dirname(_CACHE_PATH), exist_ok=True)
    with open(_CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(classificacoes, f, ensure_ascii=False, indent=2, sort_keys=True)


def classificar_segmentos(df: pd.DataFrame) -> pd.Series:
    """
    Classifica o segmento de cada FII no DataFrame.

    Colunas necessárias: 'ticker', opcionalmente 'segmento_fundamentus'.
    Coluna de nome aceita: qualquer coluna que contenha 'nome' ou 'fundo'.

    Returns:
        pd.Series com o segmento classificado (índice alinhado ao df).
    """
    cache = _carregar_cache()
    resultado = {}
    modificou_cache = False

    # Detecta coluna de nome do fundo (se disponível)
    col_nome = None
    for col in df.columns:
        if "nome" in col.lower() or "fundo" in col.lower():
            col_nome = col
            break

    for _, row in df.iterrows():
        ticker = str(row.get("ticker", "")).strip().upper()
        if not ticker:
            resultado[ticker] = "Outros"
            continue

        # Se já foi classificado e salvo no cache, usa diretamente
        if ticker in cache:
            resultado[ticker] = cache[ticker]
            continue

        nome = str(row.get(col_nome, "")) if col_nome else ""
        seg_fund = str(row.get("segmento_fundamentus", ""))

        # Aplica as 3 camadas em sequência
        seg = (
            _classificar_por_nome(nome)
            or _classificar_por_ticker(ticker)
            or _classificar_por_fundamentus(seg_fund)
            or "Outros"
        )

        resultado[ticker] = seg
        cache[ticker] = seg
        modificou_cache = True

    if modificou_cache:
        _salvar_cache(cache)

    # Retorna Series alinhada ao índice original
    return df["ticker"].map(resultado).fillna("Outros")


def reclassificar_todos(df: pd.DataFrame) -> pd.Series:
    """
    Força reclassificação de todos os tickers (ignora cache).
    Útil quando a lógica de regras foi atualizada.
    """
    # Limpa cache do disco
    if os.path.exists(_CACHE_PATH):
        os.remove(_CACHE_PATH)
    return classificar_segmentos(df)


def listar_segmentos() -> list[str]:
    """Retorna lista dos segmentos padronizados."""
    return SEGMENTOS.copy()
