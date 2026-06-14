"""
src/fii_page.py
Página de Análise de Fundos de Investimento Imobiliário (FII).

Funcionalidades:
  - Tabela completa de FIIs via scraping do Fundamentus (todas as colunas)
  - Classificação de segmento por regras offline
  - Filtros compactos: segmento, ticker, DY, P/VP, Liquidez, Vacância, Cap Rate, Qtd. Imóveis
  - KPIs dinâmicos, gráficos e download CSV
  - Salvamento de layout e filtros
"""

import os
import json
import io
import streamlit as st
import plotly.graph_objects as go
import pandas as pd

from src.fii_scraper import scrape_fii_fundamentus, obter_timestamp_cache
from src.fii_classifier import classificar_segmentos, reclassificar_todos

# ── Configurações e Mapeamentos ───────────────────────────────────────────────
_PREFS_PATH = "data/fii_layout_prefs.json"

_COR_SEGMENTO = {
    "Logística":           "#00d4aa",
    "Shopping":            "#ffd700",
    "Lajes Corporativas":  "#4fc3f7",
    "Papel (CRI/CRA)":     "#ff9f43",
    "Residencial":         "#a29bfe",
    "Hotel":               "#fd79a8",
    "Hospital":            "#e17055",
    "Fundo de Fundos":     "#00cec9",
    "Híbrido":             "#74b9ff",
    "Outros":              "#636e72",
}

_PLOT_CFG = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Inter", color="#8b949e"),
    margin=dict(l=0, r=0, t=30, b=0),
)

_COL_AMIGAVEL = {
    "ticker":               "Ticker",
    "nome":                 "Nome do Fundo",
    "segmento":             "Segmento (IA)",
    "segmento_fundamentus": "Segmento (Fund.)",
    "cotacao":              "Cotação (R$)",
    "dy":                   "DY (%)",
    "ffo_yield":            "FFO Yield (%)",
    "pvp":                  "P/VP",
    "valor_mercado":        "Valor de Mercado",
    "liquidez":             "Liquidez Diária",
    "qtd_imoveis":          "Qtd. Imóveis",
    "cap_rate":             "Cap Rate (%)",
    "preco_m2":             "Preço/m² (R$)",
    "aluguel_m2":           "Aluguel/m² (R$)",
    "vacancia_media":       "Vacância (%)",
}

# ── Carregar / Salvar Preferências ────────────────────────────────────────────
def _salvar_prefs():
    prefs = {
        "fii_seg": st.session_state.get("fii_seg", []),
        "fii_busca": st.session_state.get("fii_busca", ""),
        "fii_dy": st.session_state.get("fii_dy", (0.0, 100.0)),
        "fii_pvp": st.session_state.get("fii_pvp", (0.0, 10.0)),
        "fii_liq": st.session_state.get("fii_liq", 0),
        "fii_vac": st.session_state.get("fii_vac", 100.0),
        "fii_cap": st.session_state.get("fii_cap", 0.0),
        "fii_qtd": st.session_state.get("fii_qtd", 0),
        "fii_cols_vis": st.session_state.get("fii_cols_vis", []),
        "fii_ord_col": st.session_state.get("fii_ord_col", ""),
        "fii_ord_asc": st.session_state.get("fii_ord_asc", True),
    }
    os.makedirs(os.path.dirname(_PREFS_PATH), exist_ok=True)
    with open(_PREFS_PATH, "w", encoding="utf-8") as f:
        json.dump(prefs, f, indent=2)
    st.toast("✅ Layout e filtros salvos com sucesso!")

def _carregar_prefs_iniciais(segmentos_disp, colunas_disp):
    if "fii_prefs_loaded" in st.session_state:
        return
    st.session_state["fii_prefs_loaded"] = True
    
    padroes = {
        "fii_seg": segmentos_disp,
        "fii_busca": "",
        "fii_dy": (0.0, 100.0),
        "fii_pvp": (0.0, 10.0),
        "fii_liq": 0,
        "fii_vac": 100.0,
        "fii_cap": 0.0,
        "fii_qtd": 0,
        "fii_cols_vis": colunas_disp,
        "fii_ord_col": colunas_disp[0] if colunas_disp else "",
        "fii_ord_asc": True,
    }
    
    if os.path.exists(_PREFS_PATH):
        try:
            with open(_PREFS_PATH, "r", encoding="utf-8") as f:
                prefs = json.load(f)
            
            if "fii_seg" in prefs:
                val = [s for s in prefs["fii_seg"] if s in segmentos_disp]
                if val: padroes["fii_seg"] = val
            if "fii_busca" in prefs: padroes["fii_busca"] = prefs["fii_busca"]
            if "fii_dy" in prefs: padroes["fii_dy"] = tuple(prefs["fii_dy"])
            if "fii_pvp" in prefs: padroes["fii_pvp"] = tuple(prefs["fii_pvp"])
            if "fii_liq" in prefs: padroes["fii_liq"] = prefs["fii_liq"]
            if "fii_vac" in prefs: padroes["fii_vac"] = prefs["fii_vac"]
            if "fii_cap" in prefs: padroes["fii_cap"] = prefs["fii_cap"]
            if "fii_qtd" in prefs: padroes["fii_qtd"] = prefs["fii_qtd"]
            if "fii_cols_vis" in prefs:
                val = [c for c in prefs["fii_cols_vis"] if c in colunas_disp]
                if val: padroes["fii_cols_vis"] = val
            if "fii_ord_col" in prefs and prefs["fii_ord_col"] in colunas_disp:
                padroes["fii_ord_col"] = prefs["fii_ord_col"]
            if "fii_ord_asc" in prefs: padroes["fii_ord_asc"] = prefs["fii_ord_asc"]
        except Exception:
            pass

    for k, v in padroes.items():
        if k not in st.session_state:
            st.session_state[k] = v

    # Garante que as faixas sejam tuplas (proteção contra estado antigo do Streamlit)
    if not isinstance(st.session_state.get("fii_dy"), (tuple, list)):
        st.session_state["fii_dy"] = (0.0, 100.0)
    if not isinstance(st.session_state.get("fii_pvp"), (tuple, list)):
        st.session_state["fii_pvp"] = (0.0, 10.0)

# ── Cache de dados + classificação ────────────────────────────────────────────
@st.cache_data(ttl=3600, show_spinner=False)
def _carregar_fii_completo(forcar: bool = False) -> pd.DataFrame:
    df = scrape_fii_fundamentus(forcar_refresh=forcar)
    df["segmento"] = classificar_segmentos(df)
    return df

# ── Formatadores ──────────────────────────────────────────────────────────────
def _fmt_pct(val):
    return f"{val * 100:.2f}%" if pd.notna(val) and val != 0 else "—"

def _fmt_r2f(val):
    return f"R$ {val:.2f}" if pd.notna(val) and val != 0 else "—"

def _fmt_moeda(val):
    if pd.isna(val) or val == 0: return "—"
    if val >= 1_000_000_000: return f"R$ {val / 1_000_000_000:.2f}B"
    if val >= 1_000_000:     return f"R$ {val / 1_000_000:.1f}M"
    return f"R$ {val:,.0f}".replace(",", ".")

def _fmt_int(val):
    return f"{int(val):,}".replace(",", ".") if pd.notna(val) and val > 0 else "—"

def _fmt_pvp(val):
    return f"{val:.2f}x" if pd.notna(val) and val != 0 else "—"

_FORMATADORES = {
    "cotacao":        _fmt_r2f,
    "dy":             _fmt_pct,
    "ffo_yield":      _fmt_pct,
    "cap_rate":       _fmt_pct,
    "vacancia_media": _fmt_pct,
    "pvp":            _fmt_pvp,
    "valor_mercado":  _fmt_moeda,
    "liquidez":       _fmt_moeda,
    "preco_m2":       _fmt_moeda,
    "aluguel_m2":     _fmt_moeda,
    "qtd_imoveis":    _fmt_int,
}

# ── Página principal ──────────────────────────────────────────────────────────
def page_fii():
    st.markdown("""
    <div class='app-hdr'>
        <div class='app-title'>🏢 Análise de FII</div>
        <div class='app-sub'>Fundos Imobiliários · Dados Fundamentus · Segmento por IA · Todas as colunas</div>
    </div>""", unsafe_allow_html=True)

    # ── Controles de atualização ──────────────────────────────────────────────
    c_ts, c_ref, c_reclf, c_save = st.columns([2.5, 1.2, 1.8, 1.2])
    with c_ts:
        ts = obter_timestamp_cache()
        st.markdown(
            f"<div style='color:#8b949e;font-size:.82rem;padding-top:10px'>"
            f"📡 Última atualização: <strong style='color:#00d4aa'>{ts}</strong></div>",
            unsafe_allow_html=True,
        )
    with c_ref:
        if st.button("🔄 Atualizar Dados", use_container_width=True):
            st.cache_data.clear()
            st.session_state["_fii_refresh"] = True
            st.rerun()
    with c_reclf:
        if st.button("🔖 Reclassificar Segmentos", use_container_width=True):
            st.cache_data.clear()
            st.session_state["_fii_reclassificar"] = True
            st.rerun()
    with c_save:
        if st.button("💾 Salvar Layout", use_container_width=True):
            _salvar_prefs()

    # ── Carregamento ──────────────────────────────────────────────────────────
    forcar = st.session_state.pop("_fii_refresh", False)
    reclassificar = st.session_state.pop("_fii_reclassificar", False)

    with st.spinner("Carregando dados de FIIs..."):
        try:
            df_raw = _carregar_fii_completo(forcar)
            if reclassificar:
                df_raw["segmento"] = reclassificar_todos(df_raw)
        except Exception as e:
            st.error(f"❌ Erro ao carregar dados: {e}")
            return

    if df_raw.empty:
        st.warning("Nenhum dado disponível. Tente atualizar.")
        return

    # Inicia preferências
    segmentos_disp = sorted(df_raw["segmento"].dropna().unique().tolist())
    ORDEM_COLS = [
        "ticker", "nome", "segmento", "segmento_fundamentus",
        "cotacao", "dy", "ffo_yield", "pvp",
        "valor_mercado", "liquidez",
        "qtd_imoveis", "cap_rate", "preco_m2", "aluguel_m2", "vacancia_media",
    ]
    extras = [c for c in df_raw.columns if c not in ORDEM_COLS and c != "Endereço"]
    cols_exibir = [c for c in ORDEM_COLS if c in df_raw.columns] + extras
    nomes_amigaveis = [_COL_AMIGAVEL.get(c, c.replace("_", " ").title()) for c in cols_exibir]

    _carregar_prefs_iniciais(segmentos_disp, nomes_amigaveis)

    # ── Painel de filtros compacto ────────────────────────────────────────────
    st.markdown("<div class='sec-hdr'>🔎 Filtros</div>", unsafe_allow_html=True)

    fl1, fl2 = st.columns([4, 2])
    with fl1:
        seg_sel = st.multiselect(
            "🏷️ Segmento",
            options=segmentos_disp,
            key="fii_seg",
            placeholder="Todos os segmentos",
        )
    with fl2:
        busca = st.text_input(
            "🔍 Ticker / Nome",
            key="fii_busca",
            placeholder="Ex: HGLG, Logística...",
        )

    fn1, fn2, fn3, fn4, fn5, fn6 = st.columns(6)
    with fn1:
        dy_faixa = st.slider(
            "DY (%)", min_value=0.0, max_value=100.0,
            step=0.5, key="fii_dy",
            help="Faixa de Dividend Yield anual",
        )
    with fn2:
        pvp_faixa = st.slider(
            "P/VP", min_value=0.0, max_value=10.0,
            step=0.1, key="fii_pvp",
            help="Faixa de Preço / Valor Patrimonial",
        )
    with fn3:
        liq_min_sel = st.number_input(
            "Liquidez mín (R$)", min_value=0,
            step=500_000, key="fii_liq", format="%d",
            help="Volume médio diário mínimo em R$",
        )
    with fn4:
        vac_max_sel = st.number_input(
            "Vacância máx (%)", min_value=0.0, max_value=100.0,
            step=5.0, key="fii_vac",
            help="Vacância física máxima do fundo",
        )
    with fn5:
        cap_min_sel = st.number_input(
            "Cap Rate mín (%)", min_value=0.0, max_value=30.0,
            step=0.5, key="fii_cap",
            help="Cap Rate mínimo",
        )
    with fn6:
        qtd_min_sel = st.number_input(
            "Qtd. Imóveis mín", min_value=0, max_value=500,
            step=1, key="fii_qtd",
            help="Número mínimo de imóveis no portfólio",
        )

    # ── Aplicar filtros ───────────────────────────────────────────────────────
    df = df_raw.copy()

    if seg_sel:
        df = df[df["segmento"].isin(seg_sel)]

    if busca.strip():
        mask_ticker = df["ticker"].str.contains(busca.strip().upper(), na=False)
        mask_nome = df["nome"].str.contains(busca.strip(), case=False, na=False) if "nome" in df.columns else pd.Series(False, index=df.index)
        df = df[mask_ticker | mask_nome]

    if "dy" in df.columns:
        df = df[(df["dy"].fillna(0) >= dy_faixa[0] / 100) & (df["dy"].fillna(0) <= dy_faixa[1] / 100)]
    if "pvp" in df.columns:
        df = df[(df["pvp"].fillna(0) >= pvp_faixa[0]) & (df["pvp"].fillna(999) <= pvp_faixa[1])]
    if "liquidez" in df.columns:
        df = df[df["liquidez"].fillna(0) >= liq_min_sel]
    if "vacancia_media" in df.columns:
        mask_vacancia = df["vacancia_media"].fillna(1) <= vac_max_sel / 100
        mask_is_papel = df["segmento"].isin(["Papel (CRI/CRA)", "Fundo de Fundos"])
        df = df[mask_vacancia | mask_is_papel]
    if "cap_rate" in df.columns and cap_min_sel > 0:
        df = df[df["cap_rate"].fillna(0) >= cap_min_sel / 100]
    if "qtd_imoveis" in df.columns and qtd_min_sel > 0:
        mask_qtd = df["qtd_imoveis"].fillna(0) >= qtd_min_sel
        mask_is_papel = df["segmento"].isin(["Papel (CRI/CRA)", "Fundo de Fundos"])
        df = df[mask_qtd | mask_is_papel]

    # ── KPIs ──────────────────────────────────────────────────────────────────
    st.markdown("<div class='sec-hdr'>📊 Visão Geral</div>", unsafe_allow_html=True)

    k1, k2, k3, k4 = st.columns(4)
    dy_medio  = df["dy"].mean() * 100  if "dy"        in df.columns and not df.empty else 0
    pvp_medio = df["pvp"].mean()       if "pvp"       in df.columns and not df.empty else 0
    liq_total = df["liquidez"].sum()   if "liquidez"  in df.columns and not df.empty else 0

    with k1:
        st.markdown(f"""<div class='val-card border-green'>
            <div style='font-size:10px;color:#8b949e;text-transform:uppercase;letter-spacing:1px'>🏢 FIIs</div>
            <div style='font-size:2.5rem;font-weight:800;color:#00d4aa'>{len(df)}</div>
            <div style='font-size:.78rem;color:#8b949e'>de {len(df_raw)} disponíveis</div>
        </div>""", unsafe_allow_html=True)
    with k2:
        st.markdown(f"""<div class='val-card border-gold'>
            <div style='font-size:10px;color:#8b949e;text-transform:uppercase;letter-spacing:1px'>💰 DY Médio</div>
            <div style='font-size:2.5rem;font-weight:800;color:#ffd700'>{dy_medio:.2f}%</div>
            <div style='font-size:.78rem;color:#8b949e'>Dividend Yield anual</div>
        </div>""", unsafe_allow_html=True)
    with k3:
        st.markdown(f"""<div class='val-card border-blue'>
            <div style='font-size:10px;color:#8b949e;text-transform:uppercase;letter-spacing:1px'>📐 P/VP Médio</div>
            <div style='font-size:2.5rem;font-weight:800;color:#4fc3f7'>{pvp_medio:.2f}x</div>
            <div style='font-size:.78rem;color:#8b949e'>Preço / Valor Patrimonial</div>
        </div>""", unsafe_allow_html=True)
    with k4:
        st.markdown(f"""<div class='val-card border-orange'>
            <div style='font-size:10px;color:#8b949e;text-transform:uppercase;letter-spacing:1px'>💧 Liquidez Total</div>
            <div style='font-size:2rem;font-weight:800;color:#ff9f43'>{_fmt_moeda(liq_total)}</div>
            <div style='font-size:.78rem;color:#8b949e'>Volume diário somado</div>
        </div>""", unsafe_allow_html=True)

    # ── Gráficos ──────────────────────────────────────────────────────────────
    if not df.empty:
        g1, g2 = st.columns([1, 2])

        with g1:
            st.markdown("<div class='sec-hdr'>🥧 Segmentos</div>", unsafe_allow_html=True)
            seg_counts = df["segmento"].value_counts().reset_index()
            seg_counts.columns = ["segmento", "qtd"]
            cores = [_COR_SEGMENTO.get(s, "#636e72") for s in seg_counts["segmento"]]
            fig_pizza = go.Figure(go.Pie(
                labels=seg_counts["segmento"], values=seg_counts["qtd"],
                marker=dict(colors=cores, line=dict(color="#0d1117", width=2)),
                textinfo="label+percent",
                textfont=dict(family="Inter", size=10, color="#e6edf3"),
                hole=0.45,
                hovertemplate="<b>%{label}</b><br>%{value} FIIs (%{percent})<extra></extra>",
            ))
            fig_pizza.update_layout(
                **_PLOT_CFG, height=300, showlegend=False,
                annotations=[dict(text=f"{len(df)}<br>FIIs", x=0.5, y=0.5,
                                  font=dict(size=13, color="#e6edf3", family="Inter"),
                                  showarrow=False)],
            )
            st.plotly_chart(fig_pizza, use_container_width=True)

        with g2:
            st.markdown("<div class='sec-hdr'>📈 DY × P/VP por Segmento</div>", unsafe_allow_html=True)
            df_plot = df.dropna(subset=["dy", "pvp"]).copy()
            if not df_plot.empty:
                df_plot["dy_pct"] = df_plot["dy"] * 100
                fig_sc = go.Figure()
                for seg in df_plot["segmento"].unique():
                    ds = df_plot[df_plot["segmento"] == seg]
                    fig_sc.add_trace(go.Scatter(
                        x=ds["pvp"], y=ds["dy_pct"],
                        mode="markers+text",
                        name=seg,
                        text=ds["ticker"],
                        textposition="top center",
                        textfont=dict(size=7, color="#8b949e"),
                        marker=dict(size=8, color=_COR_SEGMENTO.get(seg, "#636e72"),
                                    opacity=0.85, line=dict(color="#0d1117", width=1)),
                        hovertemplate=(
                            "<b>%{text}</b><br>P/VP: %{x:.2f}x<br>DY: %{y:.2f}%<extra></extra>"
                        ),
                    ))
                fig_sc.add_vline(x=1.0, line_dash="dash",
                                 line_color="rgba(255,255,255,0.2)", line_width=1,
                                 annotation_text="P/VP=1",
                                 annotation_font=dict(color="rgba(255,255,255,0.3)", size=9))
                fig_sc.update_layout(
                    **_PLOT_CFG, height=300,
                    legend=dict(orientation="h", yanchor="bottom", y=1.02,
                                xanchor="left", x=0,
                                font=dict(size=9, color="#8b949e"),
                                bgcolor="rgba(0,0,0,0)"),
                    xaxis=dict(title=dict(text="P/VP", font=dict(color="#8b949e")),
                               gridcolor="rgba(255,255,255,0.05)",
                               tickfont=dict(color="#8b949e")),
                    yaxis=dict(title=dict(text="DY (%)", font=dict(color="#8b949e")),
                               gridcolor="rgba(255,255,255,0.05)",
                               ticksuffix="%", tickfont=dict(color="#8b949e")),
                )
                st.plotly_chart(fig_sc, use_container_width=True)

    # ── Tabela: TODAS as colunas ──────────────────────────────────────────────
    st.markdown("<div class='sec-hdr'>📋 Tabela Completa de FIIs</div>", unsafe_allow_html=True)

    if df.empty:
        st.info("Nenhum FII corresponde aos filtros aplicados.")
        return

    # Seletor de colunas visíveis
    with st.expander("🔧 Escolher colunas visíveis", expanded=False):
        selecionadas = st.multiselect(
            "Colunas na tabela",
            options=nomes_amigaveis,
            key="fii_cols_vis",
        )
        
    _inv_map = {v: k for k, v in _COL_AMIGAVEL.items()}
    cols_internas = [
        _inv_map.get(n, next((c for c, nm in zip(cols_exibir, nomes_amigaveis) if nm == n), n))
        for n in selecionadas
    ]
    cols_internas = [c for c in cols_internas if c in df.columns]
    if not cols_internas:
        cols_internas = cols_exibir

    # Ordenação
    o1, o2 = st.columns([3, 1])
    with o1:
        nomes_ord = [_COL_AMIGAVEL.get(c, c.replace("_", " ").title()) for c in cols_internas]
        if st.session_state.get("fii_ord_col") not in nomes_ord:
            st.session_state["fii_ord_col"] = nomes_ord[0] if nomes_ord else ""
            
        col_ord_nome = st.selectbox("Ordenar por", nomes_ord, key="fii_ord_col")
    with o2:
        st.write("")
        asc = st.checkbox("Crescente", key="fii_ord_asc")

    col_ord_int = cols_internas[nomes_ord.index(col_ord_nome)] if col_ord_nome in nomes_ord else cols_internas[0]

    if col_ord_int in df.columns and pd.api.types.is_numeric_dtype(df[col_ord_int]):
        df_sorted = df.sort_values(col_ord_int, ascending=asc, na_position="last")
    else:
        df_sorted = df.sort_values(col_ord_int, ascending=asc, na_position="last")

    # Formata para exibição
    df_display = df_sorted[cols_internas].copy()
    for col in cols_internas:
        if col in _FORMATADORES:
            df_display[col] = df_display[col].apply(_FORMATADORES[col])

    df_display = df_display.rename(
        columns={c: _COL_AMIGAVEL.get(c, c.replace("_", " ").title()) for c in cols_internas}
    )

    st.dataframe(df_display, use_container_width=True, hide_index=True, height=520)

    # Download CSV
    csv_buf = io.StringIO()
    df_sorted[cols_internas].rename(
        columns={c: _COL_AMIGAVEL.get(c, c.replace("_", " ").title()) for c in cols_internas}
    ).to_csv(csv_buf, index=False, sep=";", decimal=",")

    st.download_button(
        label="⬇️ Baixar CSV (dados filtrados — valores numéricos brutos)",
        data=csv_buf.getvalue().encode("utf-8-sig"),
        file_name="fii_analise.csv",
        mime="text/csv",
        use_container_width=True,
    )
