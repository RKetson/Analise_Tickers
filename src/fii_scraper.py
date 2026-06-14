"""
src/fii_scraper.py
Módulo de scraping da tabela de FIIs do Fundamentus.

Fonte: https://www.fundamentus.com.br/fii_resultado.php
- Retorna DataFrame com todas as colunas numéricas já convertidas
- Cache em disco (parquet) com TTL de 4 horas
"""

import os
import time
import requests
import pandas as pd
from datetime import datetime, timedelta

# ── Configurações ─────────────────────────────────────────────────────────────
_URL = "https://www.fundamentus.com.br/fii_resultado.php"
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "pt-BR,pt;q=0.9",
    "Referer": "https://www.fundamentus.com.br/",
}
_CACHE_TTL_HORAS = 4
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_CACHE_PATH = os.path.join(_BASE_DIR, "data", "fii_tabela_raw.parquet")
_CACHE_META = os.path.join(_BASE_DIR, "data", "fii_cache_meta.txt")

# Mapeamento de colunas (texto do th → nome limpo)
# Nota: O BS4 extrai o texto exato do HTML — incluindo acentos
_COL_MAP = {
    "Papel":              "ticker",
    "Segmento":           "segmento_fundamentus",
    "Cota\u00e7\u00e3o":            "cotacao",
    "FFO Yield":          "ffo_yield",
    "Dividend Yield":     "dy",
    "DY":                 "dy",
    "P/VP":               "pvp",
    "Valor de Mercado":   "valor_mercado",
    "Valor de Merc.":     "valor_mercado",
    "Liquidez":           "liquidez",
    "Liq. m\u00e9d. di\u00e1ria":   "liquidez",
    "Qtd de im\u00f3veis":    "qtd_imoveis",
    "Pre\u00e7o do m2":       "preco_m2",
    "Aluguel por m2":     "aluguel_m2",
    "Cap Rate":           "cap_rate",
    "Vac\u00e2ncia M\u00e9dia":    "vacancia_media",
    "Nome":               "nome",
}


def _cache_valido() -> bool:
    """Verifica se o cache ainda está dentro do TTL."""
    if not os.path.exists(_CACHE_PATH) or not os.path.exists(_CACHE_META):
        return False
    try:
        with open(_CACHE_META, "r") as f:
            ts = datetime.fromisoformat(f.read().strip())
        return datetime.now() - ts < timedelta(hours=_CACHE_TTL_HORAS)
    except Exception:
        return False


def _salvar_cache(df: pd.DataFrame) -> None:
    """Persiste o DataFrame e atualiza o timestamp do cache."""
    os.makedirs(os.path.dirname(_CACHE_PATH), exist_ok=True)
    df.to_parquet(_CACHE_PATH, index=False)
    with open(_CACHE_META, "w") as f:
        f.write(datetime.now().isoformat())


def _ler_cache() -> pd.DataFrame:
    """Lê o cache do disco e normaliza nomes de colunas."""
    df = pd.read_parquet(_CACHE_PATH)
    # Correção defensiva: remove aspas extras que podem ter sido salvas em versões antigas
    df.columns = [str(c).strip().strip("'").strip('"').strip() for c in df.columns]
    return df


def _limpar_percentual(serie: pd.Series) -> pd.Series:
    """Converte '12,34%' → 0.1234"""
    return (
        serie.astype(str)
        .str.replace("%", "", regex=False)
        .str.replace(".", "", regex=False)
        .str.replace(",", ".", regex=False)
        .str.strip()
        .pipe(pd.to_numeric, errors="coerce")
        / 100
    )


def _limpar_numero(serie: pd.Series) -> pd.Series:
    """Converte '1.234.567' ou '1.234,56' → float"""
    return (
        serie.astype(str)
        .str.replace(".", "", regex=False)
        .str.replace(",", ".", regex=False)
        .str.strip()
        .pipe(pd.to_numeric, errors="coerce")
    )


def _parse_tabela_bs4(html: bytes | str) -> pd.DataFrame:
    """
    Parseia a tabela de FIIs do Fundamentus usando BeautifulSoup.
    Aceita bytes (preferido) para que o lxml detecte o charset (ISO-8859-1) do
    <meta charset> do HTML, evitando corrupção de caracteres acentuados.
    """
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "lxml")

    # Tenta pelo id; fallback: primeira tabela grande
    tabela = soup.find("table", {"id": "tabelaResultado"})
    if tabela is None:
        tabelas = soup.find_all("table")
        tabela = max(tabelas, key=lambda t: len(t.find_all("tr")), default=None)

    if tabela is None:
        raise ValueError("Tabela não encontrada no HTML do Fundamentus.")

    # Cabeçalhos — adiciona "Nome" ao final
    header_row = tabela.find("thead")
    if header_row:
        headers = [th.get_text(strip=True) for th in header_row.find_all("th")]
    else:
        first_tr = tabela.find("tr")
        headers = [th.get_text(strip=True) for th in first_tr.find_all(["th", "td"])]
    headers_ext = headers + ["Nome"]

    # Linhas de dados
    tbody = tabela.find("tbody") or tabela
    rows = []
    for tr in tbody.find_all("tr"):
        cells = tr.find_all("td")
        if not cells:
            continue

        nome_fundo = ""
        row = []
        for i, td in enumerate(cells):
            # Ignora células ocultas (endereços etc.)
            style = td.get("style", "")
            if "display:none" in style.replace(" ", ""):
                continue

            # Primeira célula: extrai ticker do <a> e nome do <span title="">
            if i == 0:
                span_tips = td.find("span", class_="tips")
                if span_tips:
                    nome_fundo = span_tips.get("title", "").strip()
                a = td.find("a")
                row.append(a.get_text(strip=True) if a else td.get_text(strip=True))
            else:
                a = td.find("a")
                row.append(a.get_text(strip=True) if a else td.get_text(strip=True))

        if row:
            # Alinha ao número de headers originais e adiciona nome
            row = row[:len(headers)] + [""] * max(0, len(headers) - len(row))
            row.append(nome_fundo)
            rows.append(row)

    if not rows:
        raise ValueError("Nenhuma linha de dado encontrada na tabela.")

    return pd.DataFrame(rows, columns=headers_ext)


def scrape_fii_fundamentus(forcar_refresh: bool = False) -> pd.DataFrame:
    """
    Retorna a tabela completa de FIIs do Fundamentus como DataFrame.

    Args:
        forcar_refresh: Se True, ignora o cache e faz novo scraping.

    Returns:
        pd.DataFrame com colunas normalizadas e tipos corretos.
    """
    if not forcar_refresh and _cache_valido():
        return _ler_cache()

    try:
        resp = requests.get(_URL, headers=_HEADERS, timeout=30)
        resp.raise_for_status()
        # Passa bytes brutos — o lxml detecta o charset ISO-8859-1 do <meta>
        df = _parse_tabela_bs4(resp.content)

    except Exception as exc:
        # Se falhar e houver cache antigo, usa ele como fallback
        if os.path.exists(_CACHE_PATH):
            return _ler_cache()
        raise RuntimeError(f"Erro ao fazer scraping do Fundamentus: {exc}") from exc

    # ── Renomear colunas ──────────────────────────────────────────────────────
    # Remove aspas extras que o BS4 pode incluir e normaliza espaços
    df.columns = [str(c).strip().strip("'").strip('"').strip() for c in df.columns]
    rename = {k: v for k, v in _COL_MAP.items() if k in df.columns}
    df = df.rename(columns=rename)

    # Remove coluna de endereço se presente
    for col_drop in ["Endereço", "endereco", "Endere\u00e7o"]:
        if col_drop in df.columns:
            df = df.drop(columns=[col_drop])

    # ── Converter tipos ───────────────────────────────────────────────────────
    percentuais = ["ffo_yield", "dy", "vacancia_media", "cap_rate"]
    numericos   = ["cotacao", "pvp", "valor_mercado", "liquidez", "qtd_imoveis", "preco_m2", "aluguel_m2"]

    for col in percentuais:
        if col in df.columns:
            df[col] = _limpar_percentual(df[col])

    for col in numericos:
        if col in df.columns:
            df[col] = _limpar_numero(df[col])

    # ── Limpeza geral ─────────────────────────────────────────────────────────
    if "ticker" in df.columns:
        df["ticker"] = df["ticker"].astype(str).str.strip().str.upper()
        # Remove linhas sem ticker válido (ex: ABCD11)
        df = df[df["ticker"].str.match(r"^[A-Z]{4}11$", na=False)].copy()

    if "segmento_fundamentus" in df.columns:
        df["segmento_fundamentus"] = (
            df["segmento_fundamentus"].astype(str).str.strip()
        )

    df = df.reset_index(drop=True)
    _salvar_cache(df)
    return df


def obter_timestamp_cache() -> str:
    """Retorna a data/hora da última atualização do cache, ou 'nunca'."""
    if os.path.exists(_CACHE_META):
        try:
            with open(_CACHE_META, "r") as f:
                ts = datetime.fromisoformat(f.read().strip())
            return ts.strftime("%d/%m/%Y %H:%M")
        except Exception:
            pass
    return "nunca"
