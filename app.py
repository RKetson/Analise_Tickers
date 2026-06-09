"""
ValuaçãoBR — Ferramenta de Valuation de Ações Brasileiras
Interface Streamlit com tema dark premium, 5 métodos de valuation e análise qualitativa.

Execute: streamlit run app.py
"""

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import numpy as np
import sys
import os
from datetime import datetime

# ── Path Setup ────────────────────────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
from src.data_loader import (
    carregar_dados_empresa, listar_empresas, listar_acoes, carregar_multiplos_setor,
    obter_parametros_padrao, adicionar_empresa, salvar_dados_manuais
)
from src.models import calcular_todos
from src.analysis import gerar_relatorio_completo
from src.carteira_page import page_carteira
from src.formatters import (
    formatar_moeda, formatar_percentual, formatar_multiplo,
    formatar_milhoes, calcular_margem, status_margem
)

# ── Page Config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="ValuaçãoBR — Preço Justo de Ações",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS Premium Dark Theme ────────────────────────────────────────────────────
CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

html, body, [class*="css"] { font-family: 'Inter', sans-serif !important; }

.stApp { background: #0d1117; color: #e6edf3; }

/* Sidebar */
[data-testid="stSidebar"] {
    background: #161b22 !important;
    border-right: 1px solid rgba(255,255,255,0.07) !important;
}
[data-testid="stSidebar"] p,
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] .stRadio label { color: #e6edf3 !important; }

/* Cards */
.val-card {
    background: rgba(255,255,255,0.04);
    border: 1px solid rgba(255,255,255,0.09);
    border-radius: 14px;
    padding: 20px 22px;
    margin-bottom: 14px;
    transition: all 0.2s ease;
    position: relative;
    overflow: hidden;
}
.val-card:hover {
    background: rgba(255,255,255,0.07);
    border-color: rgba(0,212,170,0.35);
    transform: translateY(-2px);
    box-shadow: 0 8px 30px rgba(0,0,0,0.4);
}
.val-card.border-green { border-left: 4px solid #00d4aa; }
.val-card.border-gold  { border-left: 4px solid #ffd700; }
.val-card.border-red   { border-left: 4px solid #ff4757; }
.val-card.border-blue  { border-left: 4px solid #4fc3f7; }
.val-card.border-orange{ border-left: 4px solid #ff9f43; }

/* Badges */
.badge { display:inline-block; padding:3px 11px; border-radius:20px; font-size:11px; font-weight:700; letter-spacing:.5px; }
.badge-green  { background:rgba(0,212,170,.12); color:#00d4aa; border:1px solid rgba(0,212,170,.3); }
.badge-yellow { background:rgba(255,215,0,.12);  color:#ffd700; border:1px solid rgba(255,215,0,.3); }
.badge-red    { background:rgba(255,71,87,.12);  color:#ff4757; border:1px solid rgba(255,71,87,.3); }
.badge-blue   { background:rgba(79,195,247,.12); color:#4fc3f7; border:1px solid rgba(79,195,247,.3); }
.badge-gray   { background:rgba(139,148,158,.12);color:#8b949e; border:1px solid rgba(139,148,158,.3); }

/* Section headers */
.sec-hdr {
    font-size:.75rem; font-weight:700; color:#8b949e;
    text-transform:uppercase; letter-spacing:1.8px;
    margin: 28px 0 12px 0; padding-bottom:8px;
    border-bottom:1px solid rgba(255,255,255,0.07);
}

/* Alert boxes */
.al-box { padding:11px 15px; border-radius:8px; margin:5px 0; font-size:.82rem; line-height:1.5; }
.al-ok      { background:rgba(0,212,170,.07);   border-left:3px solid #00d4aa; color:#b8f5ea; }
.al-atencao { background:rgba(255,215,0,.07);   border-left:3px solid #ffd700; color:#fff3b0; }
.al-alerta  { background:rgba(255,71,87,.07);   border-left:3px solid #ff4757; color:#ffc0c6; }
.al-info    { background:rgba(79,195,247,.07);  border-left:3px solid #4fc3f7; color:#b3e5fc; }
.al-aviso   { background:rgba(139,148,158,.07); border-left:3px solid #8b949e; color:#c9d1d9; }

/* App header */
.app-hdr { padding:16px 0 28px 0; margin-bottom:24px; border-bottom:1px solid rgba(255,255,255,0.07); }
.app-title { 
    font-size:2.1rem; font-weight:800; margin:0; padding:0;
    background: linear-gradient(135deg, #00d4aa, #ffd700);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text;
}
.app-sub { color:#8b949e; font-size:.9rem; margin-top:4px; }

/* Prices */
.price-big   { font-size:2.4rem; font-weight:800; color:#00d4aa; line-height:1; }
.price-atual { font-size:1.5rem; font-weight:600; color:#e6edf3; }
.ms-pos { color:#00d4aa; font-weight:700; font-size:1.05rem; }
.ms-neg { color:#ff4757; font-weight:700; font-size:1.05rem; }

/* Tabs */
.stTabs [data-baseweb="tab-list"] {
    background:rgba(255,255,255,0.03); border-radius:10px;
    padding:4px; border:1px solid rgba(255,255,255,0.08);
    gap: 4px;
}
.stTabs [data-baseweb="tab"] {
    background:transparent; color:#8b949e;
    border-radius:8px; font-weight:500; padding:8px 18px;
}
.stTabs [aria-selected="true"] {
    background:rgba(0,212,170,0.15) !important;
    color:#00d4aa !important; border:1px solid rgba(0,212,170,.3) !important;
}

/* Inputs */
.stNumberInput input, .stTextInput input { 
    background:rgba(255,255,255,0.05) !important;
    border:1px solid rgba(255,255,255,0.12) !important;
    color:#e6edf3 !important; border-radius:8px !important;
}
label { color:#c9d1d9 !important; }

/* Buttons */
.stButton > button {
    background: linear-gradient(135deg, #00d4aa, #00b894) !important;
    color:#0d1117 !important; font-weight:700 !important;
    border:none !important; border-radius:8px !important;
    transition: all .2s ease !important;
}
.stButton > button:hover {
    transform:translateY(-1px) !important;
    box-shadow:0 4px 16px rgba(0,212,170,.4) !important;
}

/* DataFrame */
[data-testid="stDataFrame"] { border:1px solid rgba(255,255,255,0.08); border-radius:8px; overflow:hidden; }

/* Metrics */
[data-testid="stMetricValue"] { font-size:1.7rem !important; font-weight:700 !important; color:#e6edf3 !important; }

/* Selectbox */
.stSelectbox > div > div { background:rgba(255,255,255,0.05) !important; border-color:rgba(255,255,255,0.12) !important; color:#e6edf3 !important; }

/* Scrollbar */
::-webkit-scrollbar { width:5px; height:5px; }
::-webkit-scrollbar-track { background:#161b22; }
::-webkit-scrollbar-thumb { background:#30363d; border-radius:3px; }
::-webkit-scrollbar-thumb:hover { background:#00d4aa; }

/* Hide Streamlit branding */
#MainMenu, footer, .stDeployButton { visibility:hidden; display:none; }

/* Expander */
.streamlit-expanderHeader {
    background:rgba(255,255,255,0.04) !important;
    border:1px solid rgba(255,255,255,0.08) !important;
    border-radius:8px !important; color:#e6edf3 !important;
}

/* Slider */
.stSlider [data-baseweb="slider"] > div:first-child { background:rgba(0,212,170,.2) !important; }
.stSlider [data-baseweb="thumb"] { background:#00d4aa !important; }
</style>
"""

# ── Session State Init ─────────────────────────────────────────────────────────
def init_session():
    defaults = {
        'page': 'dashboard',
        'selic': config.SELIC_ANUAL,
        'ipca': config.IPCA_PROJETADO,
        'taxa_bazin': config.DY_MINIMO_BAZIN,
        'margem_seguranca': config.MARGEM_SEGURANCA_GRAHAM,
        'anos_projecao': config.ANOS_PROJECAO_FCD,
        'multiplos_setor_custom': {},
        'premio_risco_custom': {},
        'valuation_ticker': 'BBAS3',
        'manual_dados': {},
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

# ── Helper: Build Params ───────────────────────────────────────────────────────
def build_params(ticker: str, setor: str, dados: dict, overrides: dict = None) -> dict:
    """Monta dicionário de parâmetros para os modelos de valuation."""
    from src.data_loader import carregar_base_json
    base = carregar_base_json()
    emp_cfg = base.get(ticker.upper(), {})
    wacc_empresa = emp_cfg.get('wacc')

    if overrides and 'wacc' in overrides:
        wacc = overrides['wacc']
    elif wacc_empresa is not None:
        wacc = float(wacc_empresa)
    else:
        selic = st.session_state.get('selic', config.SELIC_ANUAL)
        premio_custom = st.session_state.get('premio_risco_custom', {})
        premio = premio_custom.get(setor, config.PREMIO_RISCO_SETOR.get(setor, 0.05))
        wacc = selic + premio

    multiplos = carregar_multiplos_setor()
    multiplos_custom = st.session_state.get('multiplos_setor_custom', {})
    multiplo_ev = multiplos_custom.get(setor) or multiplos.get(setor, {}).get('ev_ebitda')

    params = {
        'wacc': round(wacc, 4),
        'g_fcd': min(float(dados.get('crescimento_lucro_5a') or 0.06), 0.20),
        'g_gordon': min(float(dados.get('crescimento_dpa_5a') or 0.06), 0.20),
        'k_gordon': round(wacc, 4),
        'taxa_bazin': st.session_state.get('taxa_bazin', config.DY_MINIMO_BAZIN),
        'bazin_usar_media': True,
        'margem_seguranca': st.session_state.get('margem_seguranca', config.MARGEM_SEGURANCA_GRAHAM),
        'multiplo_ev_ebitda': multiplo_ev,
        'anos_projecao': st.session_state.get('anos_projecao', config.ANOS_PROJECAO_FCD),
        'g_terminal': st.session_state.get('ipca', config.G_TERMINAL_PADRAO),
    }

    # Carrega parâmetros editados pelo usuário na sessão atual
    custom_session = st.session_state.get('custom_params_session', {}).get(ticker, {})
    if custom_session:
        params.update(custom_session)

    if overrides:
        params.update(overrides)
    return params

# ── Helper: Gauge Chart ────────────────────────────────────────────────────────
def gauge_margem(margem_pct: float, title: str = "Margem de Segurança") -> go.Figure:
    cor = '#00d4aa' if margem_pct >= 15 else ('#ffd700' if margem_pct >= 0 else '#ff4757')
    fig = go.Figure(go.Indicator(
        mode='gauge+number',
        value=margem_pct,
        number={'suffix': '%', 'font': {'color': cor, 'size': 26, 'family': 'Inter'}},
        title={'text': title, 'font': {'color': '#8b949e', 'size': 12, 'family': 'Inter'}},
        gauge={
            'axis': {'range': [-60, 80], 'tickcolor': '#30363d',
                     'tickfont': {'color': '#8b949e', 'size': 9}},
            'bar': {'color': cor, 'thickness': 0.28},
            'bgcolor': 'rgba(255,255,255,0.03)',
            'bordercolor': 'rgba(255,255,255,0.1)',
            'steps': [
                {'range': [-60, 0],  'color': 'rgba(255,71,87,0.10)'},
                {'range': [0, 15],   'color': 'rgba(255,215,0,0.07)'},
                {'range': [15, 33],  'color': 'rgba(0,212,170,0.07)'},
                {'range': [33, 80],  'color': 'rgba(0,212,170,0.16)'},
            ],
            'threshold': {'line': {'color': '#ffd700', 'width': 2},
                          'thickness': 0.8, 'value': 33},
        }
    ))
    fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                      height=200, margin=dict(l=20, r=20, t=40, b=5),
                      font=dict(family='Inter'))
    return fig

# ── Helper: Method Card HTML ───────────────────────────────────────────────────
def method_card_html(label: str, emoji: str, resultado: dict, preco_atual: float) -> str:
    valido = resultado.get('valido', False)
    pj = resultado.get('preco_justo')

    if not valido or pj is None:
        erro_msg = resultado.get('erro', 'Parâmetros inválidos ou insuficientes para este método.')
        is_aviso = resultado.get('aviso', False)
        cor = '#ffd700' if is_aviso else '#ff4757'
        icone = 'ℹ️' if is_aviso else '⚠️'
        titulo = 'Não Aplicável' if is_aviso else 'Não Calculado'
        return f"""
        <div class='val-card' style='border-left: 3px solid {cor}; min-height: 135px;'>
            <div style='font-size:10px;color:#8b949e;text-transform:uppercase;letter-spacing:1px'>{emoji} {label}</div>
            <div style='color:{cor};font-size:.85rem;margin-top:12px;line-height:1.4;'>
                <strong style='font-size:1rem'>{icone} {titulo}</strong><br>
                <span style='color:#8b949e;font-size:.78rem'>{erro_msg}</span>
            </div>
        </div>"""

    ms = calcular_margem(preco_atual, pj)
    txt, _ = status_margem(ms)
    ms_pct = (ms or 0) * 100
    cor_borda = 'border-green' if ms_pct >= 15 else ('border-gold' if ms_pct >= 0 else 'border-red')
    cor_ms = '#00d4aa' if ms_pct >= 0 else '#ff4757'
    sinal = '+' if ms_pct >= 0 else ''

    return f"""
    <div class='val-card {cor_borda}'>
        <div style='font-size:10px;color:#8b949e;text-transform:uppercase;letter-spacing:1px'>{emoji} {label}</div>
        <div class='price-big' style='margin:8px 0 4px'>{formatar_moeda(pj)}</div>
        <div style='color:#8b949e;font-size:.78rem'>Preço atual: {formatar_moeda(preco_atual)}</div>
        <div style='color:{cor_ms};font-weight:700;margin-top:6px;font-size:.95rem'>
            {sinal}{ms_pct:.1f}% &nbsp;
            <span style='font-size:.75rem;font-weight:400;color:#8b949e'>{txt}</span>
        </div>
    </div>"""

# ── Helper: Alert Box ──────────────────────────────────────────────────────────
def alert_box(item):
    if isinstance(item, str):
        st.markdown(f"<div class='al-box al-info'>💬 {item}</div>", unsafe_allow_html=True)
        return
    status = item.get('status', 'info')
    css = {'ok':'al-ok','atencao':'al-atencao','alerta':'al-alerta','info':'al-info','aviso':'al-aviso'}.get(status,'al-info')
    emoji = item.get('emoji', '•')
    msg   = item.get('mensagem', '')
    st.markdown(f"<div class='al-box {css}'>{emoji} {msg}</div>", unsafe_allow_html=True)

# ── Helper: Plot Config ────────────────────────────────────────────────────────
PLOT_CFG = dict(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                font=dict(family='Inter', color='#8b949e'),
                margin=dict(l=0, r=0, t=30, b=0))

# ══════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════════════════════════════
def render_sidebar():
    with st.sidebar:
        selic = st.session_state.get('selic', config.SELIC_ANUAL)
        st.markdown(f"""
        <div style='padding:16px 0 20px 0; text-align:center'>
            <div style='font-size:2.2rem'>📊</div>
            <div style='font-size:1.2rem;font-weight:800;
                background:linear-gradient(135deg,#00d4aa,#ffd700);
                -webkit-background-clip:text;-webkit-text-fill-color:transparent;
                background-clip:text'>ValuaçãoBR</div>
            <div style='font-size:.7rem;color:#484f58;margin-top:2px'>v{config.VERSAO} · Análise Conservadora</div>
        </div>""", unsafe_allow_html=True)

        st.markdown("<hr style='border-color:rgba(255,255,255,0.07);margin:0 0 12px 0'>", unsafe_allow_html=True)

        nav = {
            '🏠 Dashboard':       'dashboard',
            '💼 Minha Carteira':  'carteira',
            '🔍 Valuation':       'valuation',
            '⚖️ Comparativo':     'comparativo',
            '📝 Entrada Manual':  'manual',
            '⚙️ Configurações':   'config',
            '📚 Metodologia':     'metodologia',
        }
        for label, pid in nav.items():
            active = st.session_state.get('page') == pid
            if st.button(label, key=f'nav_{pid}', use_container_width=True):
                st.session_state['page'] = pid
                st.rerun()
            if active:
                st.markdown(f"""<style>
                div[data-testid="stButton"] > button[kind="secondary"]:last-of-type {{
                    background:rgba(0,212,170,0.12) !important;
                    border-left:3px solid #00d4aa !important;
                    color:#00d4aa !important;
                }}</style>""", unsafe_allow_html=True)

        st.markdown("<hr style='border-color:rgba(255,255,255,0.07);margin:12px 0'>", unsafe_allow_html=True)
        st.markdown(f"""
        <div style='font-size:11px;color:#8b949e;padding:4px 8px'>
            <div style='margin-bottom:5px'>📈 <strong style='color:#e6edf3'>Selic:</strong>
                <span style='color:#00d4aa'>{selic:.1%} a.a.</span></div>
            <div style='margin-bottom:5px'>💹 <strong style='color:#e6edf3'>IPCA proj.:</strong>
                <span style='color:#ffd700'>{st.session_state.get('ipca',config.IPCA_PROJETADO):.1%} a.a.</span></div>
            <div style='margin-bottom:5px'>🛡️ <strong style='color:#e6edf3'>Margem (Graham):</strong>
                <span style='color:#4fc3f7'>{st.session_state.get('margem_seguranca',config.MARGEM_SEGURANCA_GRAHAM):.0%}</span></div>
            <div style='color:#30363d;font-size:10px;margin-top:12px'>
                Dados: fundamentus + yfinance<br>Base curada: dez/2025
            </div>
        </div>""", unsafe_allow_html=True)

        st.markdown("<hr style='border-color:rgba(255,255,255,0.07);margin:12px 0'>", unsafe_allow_html=True)
        st.markdown("<div style='font-size:12px;color:#e6edf3;padding:0 8px 8px;font-weight:600'>➕ Adicionar Novo Ticker</div>", unsafe_allow_html=True)
        with st.form("form_add_ticker"):
            novo_ticker = st.text_input("Código na B3", placeholder="Ex: ITUB4, WEGE3").strip().upper()
            if st.form_submit_button("Buscar e Salvar", use_container_width=True):
                if novo_ticker:
                    if adicionar_empresa(novo_ticker):
                        st.success(f"{novo_ticker} adicionado! Atualize a página se necessário.")
                        st.cache_data.clear()
                    else:
                        st.error(f"Ticker inválido ou já existe.")

# ══════════════════════════════════════════════════════════════════════════════
# PAGE: DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════
@st.cache_data(ttl=300, show_spinner=False)
def _carregar_todas_empresas():
    empresas = listar_empresas()
    resultados = []
    for emp in empresas:
        ticker = emp['ticker']
        try:
            res = carregar_dados_empresa(ticker)
            dados = res['dados']
            cfg   = res['empresa_config']
            setor = cfg.get('setor', '')
            preco = float(dados.get('preco_atual') or 0)

            multiplos = carregar_multiplos_setor()
            multiplo_ev = multiplos.get(setor, {}).get('ev_ebitda')
            params = build_params(ticker, setor, dados, {'multiplo_ev_ebitda': multiplo_ev})
            calc = calcular_todos(dados, params)

            # Define o método principal
            metodo_str = cfg.get('metodo_principal')
            if not metodo_str:
                metodo_str = METODO_INFO.get(config.METODOS_POR_SETOR.get(setor, ['bazin'])[0])[0]

            # Acha a key correspondente
            key_metodo = next((k for k, v in METODO_INFO.items() if v[0] == metodo_str), 'bazin')
            
            pm = calc.get(key_metodo, {}).get('preco_justo')
            if not pm:
                pm = calc.get('_media')

            ms = calcular_margem(preco, pm)
            txt, em = status_margem(ms)

            resultados.append({
                'ticker': ticker, 'nome': emp['nome'],
                'setor': setor.replace('_', ' ').title(),
                'preco_atual': preco, 'preco_medio': pm,
                'graham': calc['graham'].get('preco_justo'),
                'bazin':  calc['bazin'].get('preco_justo'),
                'gordon': calc['gordon'].get('preco_justo'),
                'fcd':    calc['fcd'].get('preco_justo'),
                'ev_ebitda': calc['ev_ebitda'].get('preco_justo'),
                'buffett': calc.get('buffett', {}).get('preco_justo'),
                'margem_pct': (ms or 0) * 100,
                'status': f'{em} {txt}',
                'fonte': res.get('fonte', ''),
                'metodo_principal': metodo_str,
            })
        except Exception as e:
            resultados.append({'ticker': ticker, 'nome': emp['nome'],
                               'setor': '', 'status': f'⚠️ {str(e)[:40]}'})
    return resultados

def page_dashboard():
    st.markdown("""
    <div class='app-hdr'>
        <div class='app-title'>📊 Dashboard de Valuation</div>
        <div class='app-sub'>Visão geral · 9 empresas · 5 métodos · Análise conservadora</div>
    </div>""", unsafe_allow_html=True)

    col_btn, col_info = st.columns([1, 4])
    with col_btn:
        atualizar = st.button('🔄 Atualizar Dados', use_container_width=True)
    with col_info:
        st.markdown("<div style='color:#8b949e;font-size:.82rem;padding-top:10px'>"
                    "Busca dados em fundamentus.com.br e yfinance. Pode levar 30–60s.</div>",
                    unsafe_allow_html=True)

    if atualizar:
        st.cache_data.clear()

    with st.spinner('Calculando valuations para todas as empresas...'):
        rows = _carregar_todas_empresas()

    # KPIs
    oport = [r for r in rows if r.get('margem_pct', -999) >= 33]
    boas  = [r for r in rows if 15 <= r.get('margem_pct', -999) < 33]
    caras = [r for r in rows if r.get('margem_pct', 0) < 0]

    k1, k2, k3, k4 = st.columns(4)
    with k1:
        st.markdown(f"""<div class='val-card border-green'>
            <div style='font-size:10px;color:#8b949e;text-transform:uppercase;letter-spacing:1px'>🟢 Excelentes Oportunidades</div>
            <div style='font-size:2.5rem;font-weight:800;color:#00d4aa'>{len(oport)}</div>
            <div style='font-size:.78rem;color:#8b949e'>Margem de segurança ≥ 33%</div>
        </div>""", unsafe_allow_html=True)
    with k2:
        st.markdown(f"""<div class='val-card border-gold'>
            <div style='font-size:10px;color:#8b949e;text-transform:uppercase;letter-spacing:1px'>🟡 Boas Oportunidades</div>
            <div style='font-size:2.5rem;font-weight:800;color:#ffd700'>{len(boas)}</div>
            <div style='font-size:.78rem;color:#8b949e'>Margem entre 15% e 33%</div>
        </div>""", unsafe_allow_html=True)
    with k3:
        st.markdown(f"""<div class='val-card border-red'>
            <div style='font-size:10px;color:#8b949e;text-transform:uppercase;letter-spacing:1px'>🔴 Sobrevalorizadas</div>
            <div style='font-size:2.5rem;font-weight:800;color:#ff4757'>{len(caras)}</div>
            <div style='font-size:.78rem;color:#8b949e'>Preço acima do justo</div>
        </div>""", unsafe_allow_html=True)
    with k4:
        selic = st.session_state.get('selic', config.SELIC_ANUAL)
        st.markdown(f"""<div class='val-card border-blue'>
            <div style='font-size:10px;color:#8b949e;text-transform:uppercase;letter-spacing:1px'>📈 Selic (base WACC)</div>
            <div style='font-size:2.5rem;font-weight:800;color:#4fc3f7'>{selic:.1%}</div>
            <div style='font-size:.78rem;color:#8b949e'>Ajustável em Configurações</div>
        </div>""", unsafe_allow_html=True)

    # Tabela
    st.markdown("<div class='sec-hdr'>⚙️ Método Principal por Ticker</div>", unsafe_allow_html=True)
    with st.expander("Configurar Valuation Principal"):
        from src.data_loader import salvar_metodo_principal
        cols = st.columns(3)
        mudou = False
        for i, row in enumerate([r for r in rows if r.get('setor')]): # Apenas válidos
            tk = row['ticker']
            m_atual = row.get('metodo_principal', 'Bazin')
            opcoes = [info[0] for info in METODO_INFO.values()]
            idx = opcoes.index(m_atual) if m_atual in opcoes else 1
            
            novo_m = cols[i % 3].selectbox(f"{tk}", opcoes, index=idx, key=f"sel_{tk}")
            if novo_m != m_atual:
                salvar_metodo_principal(tk, novo_m)
                mudou = True
        
        if mudou:
            st.cache_data.clear()
            st.rerun()

    st.markdown("<div class='sec-hdr'>📋 Carteira Monitorada</div>", unsafe_allow_html=True)
    df = pd.DataFrame(rows)
    if not df.empty:
        display = df.copy()
        for col in ['preco_atual','preco_medio','graham','bazin','gordon','fcd','ev_ebitda', 'buffett']:
            if col in display.columns:
                display[col] = display[col].apply(
                    lambda x: f'R$ {x:.2f}' if pd.notna(x) and x and x != 0 else 'N/D'
                )
        if 'margem_pct' in display.columns:
            display['margem_pct'] = display['margem_pct'].apply(
                lambda x: f'{x:+.1f}%' if pd.notna(x) else 'N/D'
            )
        rename = {'ticker':'Ticker','nome':'Empresa','setor':'Setor','preco_atual':'Preço Atual',
                  'metodo_principal': 'Método Principal',
                  'graham':'Graham','bazin':'Bazin','gordon':'Gordon','fcd':'FCD',
                  'ev_ebitda':'EV/EBITDA','buffett':'Buffett','preco_medio':'Preço Principal','margem_pct':'Margem','status':'Status'}
        cols_show = [c for c in rename if c in display.columns]
        display = display[cols_show].rename(columns=rename)
        st.dataframe(display, use_container_width=True, hide_index=True)

    # Gráfico de margens
    df_chart = pd.DataFrame(rows).dropna(subset=['margem_pct'])
    if not df_chart.empty:
        st.markdown("<div class='sec-hdr'>📊 Margem de Segurança por Empresa</div>", unsafe_allow_html=True)
        cores = ['#00d4aa' if v >= 33 else ('#ffd700' if v >= 15 else ('#ff9f43' if v >= 0 else '#ff4757'))
                 for v in df_chart['margem_pct']]
        fig = go.Figure(go.Bar(
            x=df_chart['ticker'], y=df_chart['margem_pct'],
            marker_color=cores, marker_line_color='rgba(255,255,255,0.1)', marker_line_width=1,
            text=[f'{v:+.1f}%' for v in df_chart['margem_pct']],
            textposition='outside', textfont=dict(color='#e6edf3', size=10),
        ))
        fig.add_hline(y=33, line_dash='dash', line_color='#ffd700', line_width=1.5,
                      annotation_text='Ideal (33%)', annotation_font_color='#ffd700', annotation_font_size=10)
        fig.add_hline(y=0, line_color='rgba(255,255,255,0.15)', line_width=1)
        fig.update_layout(**PLOT_CFG, height=300, showlegend=False,
                          xaxis=dict(gridcolor='rgba(255,255,255,0.05)', tickfont=dict(color='#e6edf3', size=11)),
                          yaxis=dict(gridcolor='rgba(255,255,255,0.05)', ticksuffix='%',
                                     tickfont=dict(color='#8b949e')))
        st.plotly_chart(fig, use_container_width=True)

# ══════════════════════════════════════════════════════════════════════════════
# PAGE: VALUATION DETALHADO
# ══════════════════════════════════════════════════════════════════════════════
METODO_INFO = {
    'graham':   ('Graham',   '🧮', 'Valor Intrínseco de Benjamin Graham — √(22,5 × LPA × VPA)'),
    'bazin':    ('Bazin',    '🏠', 'Preço-Teto de Décio Bazin — DPA_médio ÷ Taxa_retorno_mínima'),
    'gordon':   ('Gordon',   '📈', 'Modelo de Gordon — crescimento constante de dividendos'),
    'fcd':      ('FCD',      '💰', 'Fluxo de Caixa Descontado em 2 estágios — método mais robusto'),
    'ev_ebitda':('EV/EBITDA','📊', 'Múltiplo EV/EBITDA setorial — comparação com pares'),
    'buffett':  ('Buffett',  '🦅', 'Modelo de Warren Buffett — Foco em ROE e Crescimento de Lucros'),
}

def page_valuation():
    st.markdown("""
    <div class='app-hdr'>
        <div class='app-title'>🔍 Valuation Detalhado</div>
        <div class='app-sub'>Análise completa por empresa · Premissas editáveis · 5 métodos</div>
    </div>""", unsafe_allow_html=True)

    empresas = listar_acoes()
    opcoes = {f"{e['ticker']} — {e['nome']}": e['ticker'] for e in empresas}
    sel_label = st.selectbox('Selecionar empresa', list(opcoes.keys()),
                              index=list(opcoes.values()).index(
                                  st.session_state.get('valuation_ticker','BBAS3')
                              ) if st.session_state.get('valuation_ticker','BBAS3') in opcoes.values() else 0)
    ticker = opcoes[sel_label]
    st.session_state['valuation_ticker'] = ticker

    col_load, col_fonte = st.columns([1, 4])
    with col_load:
        load_btn = st.button('🔄 Buscar Online', use_container_width=True)

    with st.spinner(f'Carregando dados de {ticker}...'):
        result = carregar_dados_empresa(ticker)

    dados_orig  = result['dados']
    emp_cfg     = result['empresa_config']
    fonte       = result.get('fonte', 'json')
    suc_online  = result.get('sucesso_online', False)
    erro_online = result.get('erro_online')
    setor       = emp_cfg.get('setor', '')

    with col_fonte:
        cor_fonte = '#00d4aa' if suc_online else '#ffd700'
        st.markdown(f"<div style='padding-top:10px;font-size:.82rem;color:{cor_fonte}'>"
                    f"📡 Fonte: <strong>{fonte}</strong></div>", unsafe_allow_html=True)

    if erro_online and not suc_online:
        st.warning(f"⚠️ Dados online indisponíveis — usando base local. ({erro_online[:80]})")

    # Descrição da empresa
    descricao = emp_cfg.get('descricao', '')
    metodos_rec = config.METODOS_POR_SETOR.get(setor, list(METODO_INFO.keys()))
    ri_url = emp_cfg.get('referencia_ri', '')

    if descricao:
        st.markdown(f"<div class='al-box al-info'>📋 {descricao}</div>", unsafe_allow_html=True)

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📊 Dados & Premissas", "📈 Resultados", "🛡️ Análise de Qualidade", "💰 Detalhamento FCD", "📈 Histórico Trimestral"
    ])

    # ── Tab 1: Dados & Premissas ──────────────────────────────────────────────
    with tab1:
        st.markdown("<div class='sec-hdr'>Parâmetros de Valuation</div>", unsafe_allow_html=True)
        st.markdown("<div style='color:#8b949e;font-size:.85rem;margin-bottom:15px;'>"
                    "Ajuste as premissas de projeção de cada método. Dados fundamentalistas puros (LPA, VPA, FCL) "
                    "devem ser editados na aba 'Entrada Manual'.</div>", unsafe_allow_html=True)

        # Carrega parâmetros costumizados em sessão, se houver
        custom_p = st.session_state.get('custom_params_session', {}).get(ticker, {})
        
        selic = st.session_state.get('selic', config.SELIC_ANUAL)
        premio = config.PREMIO_RISCO_SETOR.get(setor, 0.05)
        wacc_default = selic + premio
        wacc_cfg = emp_cfg.get('wacc')
        wacc_inicial = custom_p.get('wacc', wacc_cfg if wacc_cfg is not None else wacc_default)
        
        margem_seguranca_inicial = custom_p.get('margem_seguranca', st.session_state.get('margem_seguranca', config.MARGEM_SEGURANCA_GRAHAM))

        # --- SEÇÕES POR MÉTODO ---
        c1, c2, c3 = st.columns(3)
        
        with c1:
            with st.container(border=True):
                st.markdown("##### 📍 Método Graham")
                margem_seguranca = st.number_input('Margem de Segurança (%)',
                    value=float(margem_seguranca_inicial * 100), min_value=0.0, max_value=80.0, step=1.0,
                    help='Desconto exigido sobre o valor intrínseco. Padrão: 33%.') / 100
                
            with st.container(border=True):
                st.markdown("##### 📍 Método Bazin")
                taxa_b_inicial = custom_p.get('taxa_bazin', st.session_state.get('taxa_bazin', config.DY_MINIMO_BAZIN))
                taxa_bazin = st.number_input('Taxa Bazin (% a.a.)',
                    value=taxa_b_inicial * 100, min_value=3.0, max_value=15.0, step=0.5,
                    help='Taxa mínima de dividend yield exigida por Bazin (padrão 6%).') / 100
                
        with c2:
            with st.container(border=True):
                st.markdown("##### 📍 Método FCD")
                wacc_fcd = st.number_input('WACC / Custo de Capital (%)',
                    value=round(wacc_inicial * 100, 1), min_value=5.0, max_value=40.0, step=0.5, key="wacc_fcd",
                    help=f'Usado para descontar fluxos futuros. Padrão Setor {setor}: {wacc_default:.1%}.') / 100
                    
                g_fcd_inicial = custom_p.get('g_fcd', min(float(dados_orig.get('crescimento_lucro_5a') or 0.06), 0.20))
                g_fcd_ui = st.number_input('Cresc. FCL Fase 1 (%)',
                    value=float(g_fcd_inicial * 100), min_value=-10.0, max_value=25.0, step=0.5,
                    help='Taxa de crescimento do FCL na fase de projeção.') / 100
                    
                anos_inicial = custom_p.get('anos_projecao', int(st.session_state.get('anos_projecao', 10)))
                anos_proj = st.number_input('Anos de Projeção',
                    value=int(anos_inicial), min_value=5, max_value=15, step=1)
                
            with st.container(border=True):
                st.markdown("##### 📍 Método Gordon")
                g_gordon_inicial = custom_p.get('g_gordon', min(float(dados_orig.get('crescimento_dpa_5a') or 0.06), 0.15))
                g_gordon = st.number_input('Cresc. Dividendos Perpetuidade (%)',
                    value=float(g_gordon_inicial * 100), min_value=0.0, max_value=20.0, step=0.5,
                    help='Taxa de crescimento perpétuo dos dividendos.') / 100
                
                # Sincronizar WACC Gordon e FCD (o usuário pediu sincronia visual)
                wacc_gordon = st.number_input('Taxa de Desconto (WACC) (%)',
                    value=wacc_fcd * 100, min_value=5.0, max_value=40.0, step=0.5, key="wacc_gordon", disabled=True,
                    help="Sincronizado com o WACC do FCD.") / 100

        with c3:
            with st.container(border=True):
                st.markdown("##### 📍 Método EV/EBITDA")
                multiplos = carregar_multiplos_setor()
                multiplo_ev_default = multiplos.get(setor, {}).get('ev_ebitda')
                if multiplo_ev_default is not None:
                    mev_inicial = custom_p.get('multiplo_ev_ebitda', float(multiplo_ev_default or 6.0))
                    multiplo_ev = st.number_input('Múltiplo EV/EBITDA Alvo',
                        value=float(mev_inicial), min_value=1.0, max_value=25.0, step=0.5,
                        help=f'Padrão baseado no setor {setor}.')
                else:
                    st.info('Múltiplo EV/EBITDA não se aplica a empresas do setor financeiro (Bancos, Seguradoras).')
                    multiplo_ev = 0.0

            with st.container(border=True):
                st.markdown("##### 📍 Método Buffett")
                payout_inicial = custom_p.get('payout_buffett', 0.50)
                payout_buffett = st.number_input('Payout Projetado (%)',
                    value=float(payout_inicial * 100), min_value=0.0, max_value=100.0, step=1.0) / 100
                    
                pl_setor_default = config.MULTIPLO_PL_SETOR.get(setor, config.BUFFETT_PL_MAXIMO)
                pl_inicial = custom_p.get('pl_buffett', pl_setor_default)
                pl_buffett = st.number_input('P/L Projetado Saída',
                    value=float(pl_inicial), min_value=1.0, max_value=50.0, step=0.5)
                    
                roe_buffett_default = min(2.0, max(0.0, float(dados_orig.get('roe') or 0.15)))
                roe_inicial = custom_p.get('roe_buffett', roe_buffett_default)
                roe_buffett = st.number_input('ROE Projetado (%)',
                    value=roe_inicial * 100, min_value=0.0, max_value=200.0, step=0.5) / 100

        # Seleção de métodos
        st.markdown("<div class='sec-hdr'>Métodos a Calcular</div>", unsafe_allow_html=True)
        st.markdown("<div style='color:#8b949e;font-size:.82rem;margin-bottom:10px'>"
                    "✨ Métodos recomendados para o setor estão pré-selecionados. "
                    "Você pode escolher qualquer combinação.</div>", unsafe_allow_html=True)

        metodos_keys = list(METODO_INFO.keys())
        metodos_cols = st.columns(max(1, len(metodos_keys)))
        metodos_sel = {}
        for col, key in zip(metodos_cols, metodos_keys):
            info = METODO_INFO[key]
            rec = key in metodos_rec
            label = f"{info[1]} {info[0]}"
            if rec:
                label += " ⭐"
            with col:
                metodos_sel[key] = st.checkbox(label, value=True, key=f'chk_{key}',
                                                help=info[2])

        calc_col, save_col = st.columns(2)
        with calc_col:
            calcular = st.button('🧮 Calcular Valuation', use_container_width=True)
        with save_col:
            salvar = st.button('💾 Salvar Parâmetros Customizados', use_container_width=True, help="Salva estas premissas para a empresa na sessão.")

        if calcular or salvar or True:  # sempre calcular para manter estado
            # Preenche dados calc puramente com a origem
            dados_calc = dict(dados_orig)
            dados_calc['wacc'] = wacc_fcd # WACC ainda é considerado dado fundamental em alguns scripts, então atualizamos
            
            preco_atual = float(dados_orig.get('preco_atual') or 0.0)
            
            if salvar:
                st.success('✅ Parâmetros de valuation atualizados na sessão!')

            g_terminal = st.session_state.get('ipca', config.G_TERMINAL_PADRAO)
            params_calc = {
                'wacc': wacc_fcd, 'taxa_bazin': taxa_bazin, 'g_fcd': g_fcd_ui,
                'g_gordon': g_gordon, 'k_gordon': wacc_gordon, 'g_terminal': g_terminal,
                'anos_projecao': int(anos_proj),
                'multiplo_ev_ebitda': multiplo_ev,
                'margem_seguranca': margem_seguranca,
                'bazin_usar_media': True,
                'payout_buffett': payout_buffett,
                'pl_buffett': pl_buffett,
                'roe_buffett': roe_buffett,
            }
            
            # Salva na sessão para priorizar a edição do usuário ao mudar de página
            if 'custom_params_session' not in st.session_state:
                st.session_state['custom_params_session'] = {}
            st.session_state['custom_params_session'][ticker] = params_calc
            st.session_state['_calc_dados'] = dados_calc
            st.session_state['_calc_params'] = params_calc
            st.session_state['_calc_result'] = calcular_todos(dados_calc, params_calc)
            st.session_state['_calc_ticker'] = ticker
            st.session_state['_calc_preco'] = preco_atual
            st.session_state['_calc_metodos_sel'] = metodos_sel
            st.session_state['_emp_cfg'] = emp_cfg

    # ── Tab 2: Resultados ─────────────────────────────────────────────────────
    with tab2:
        calc = st.session_state.get('_calc_result')
        preco_c = st.session_state.get('_calc_preco', 0)
        metodos_s = st.session_state.get('_calc_metodos_sel', {k: True for k in METODO_INFO})
        cfg_c = st.session_state.get('_emp_cfg', emp_cfg)

        if not calc:
            st.info('⬅️ Configure os dados na aba "Dados & Premissas" e clique em "Calcular Valuation".')
        else:
            pm = calc.get('_media')
            ms = calcular_margem(preco_c, pm)
            txt, em = status_margem(ms)
            ms_pct = (ms or 0) * 100

            # Consenso
            cor_big = '#00d4aa' if ms_pct >= 0 else '#ff4757'
            st.markdown(f"""
            <div class='val-card border-{"green" if ms_pct >= 0 else "red"}' style='text-align:center;padding:28px'>
                <div style='font-size:.8rem;color:#8b949e;text-transform:uppercase;letter-spacing:1.5px'>
                    Preço Justo — Consenso ({calc.get('_num_metodos_validos',0)} Métodos)</div>
                <div style='font-size:3.2rem;font-weight:800;color:{cor_big};margin:8px 0'>
                    {formatar_moeda(pm) if pm else 'N/D'}</div>
                <div style='color:#8b949e;font-size:1rem'>
                    Preço atual: <strong style='color:#e6edf3'>{formatar_moeda(preco_c)}</strong></div>
                <div style='font-size:1.4rem;font-weight:700;color:{cor_big};margin-top:8px'>
                    {em} {ms_pct:+.1f}% — {txt}</div>
            </div>""", unsafe_allow_html=True)

            # Gauges
            st.markdown("<div class='sec-hdr'>Margem de Segurança por Método</div>", unsafe_allow_html=True)
            g_cols = st.columns(max(1, len(METODO_INFO)))
            for i, (key, info) in enumerate(METODO_INFO.items()):
                if not metodos_s.get(key, True):
                    continue
                res = calc.get(key, {})
                pj  = res.get('preco_justo')
                with g_cols[i]:
                    if pj and preco_c:
                        ms_m = (calcular_margem(preco_c, pj) or 0) * 100
                        st.plotly_chart(gauge_margem(ms_m, f'{info[1]} {info[0]}'),
                                        use_container_width=True, key=f'gauge_{key}')
                    else:
                        erro_msg = res.get('erro','Não foi possível calcular')
                        is_aviso = res.get('aviso', False)
                        cor = '#ffd700' if is_aviso else '#ff4757'
                        bg_rgba = 'rgba(255,215,0,0.02)' if is_aviso else 'rgba(255,71,87,0.02)'
                        bord_rgba = 'rgba(255,215,0,0.3)' if is_aviso else 'rgba(255,71,87,0.3)'
                        icone = 'ℹ️' if is_aviso else '⚠️'
                        st.markdown(f"""
                        <div style='height:200px; display:flex; flex-direction:column; justify-content:center; align-items:center; border:1px dashed {bord_rgba}; border-radius:12px; background:{bg_rgba}; margin:10px; padding:15px'>
                            <div style='font-size:1.8rem;margin-bottom:8px'>{icone}</div>
                            <div style='color:{cor};font-size:11px;text-align:center;font-weight:700;text-transform:uppercase;letter-spacing:1px;margin-bottom:8px'>{info[1]} {info[0]}</div>
                            <div style='color:#8b949e;font-size:11px;text-align:center;line-height:1.4'>{erro_msg}</div>
                        </div>
                        """, unsafe_allow_html=True)

            # Cards de métodos
            st.markdown("<div class='sec-hdr'>Detalhamento por Método</div>", unsafe_allow_html=True)
            card_cols = st.columns(3)
            idx = 0
            for key, info in METODO_INFO.items():
                if not metodos_s.get(key, True):
                    continue
                with card_cols[idx % 3]:
                    res = calc.get(key, {})
                    st.markdown(method_card_html(info[0], info[1], res, preco_c), unsafe_allow_html=True)
                    with st.expander(f'Cálculo Passo a Passo — {info[0]}', expanded=False):
                        det = res.get('detalhes', {})
                        formula = det.get('formula', '')
                        if formula:
                            st.latex(formula)
                        for k, v in det.items():
                            if k not in ('formula', 'fcls_projetados') and v is not None:
                                if isinstance(v, float):
                                    if 0 < v < 1:
                                        st.write(f"**{k}:** {v:.2%}")
                                    else:
                                        st.write(f"**{k}:** {formatar_moeda(v) if 'preco' in k or 'dpa' in k else f'{v:.2f}'}")
                                else:
                                    st.write(f"**{k}:** {v}")
                idx += 1

            # Sensibilidade FCD
            fcd_res = calc.get('fcd', {})
            if fcd_res.get('valido'):
                st.markdown("<div class='sec-hdr'>🔬 Análise de Sensibilidade FCD (g × WACC)</div>", unsafe_allow_html=True)
                params_c = st.session_state.get('_calc_params', {})
                g_base = params_c.get('g_fcd', 0.06)
                w_base = params_c.get('wacc', 0.185)
                g_vals = [g_base - 0.03, g_base - 0.015, g_base, g_base + 0.015, g_base + 0.03]
                w_vals = [w_base - 0.02, w_base - 0.01, w_base, w_base + 0.01, w_base + 0.02]
                dados_s = st.session_state.get('_calc_dados', {})
                from src.models import calcular_fcd as _fcd

                sens_data = {}
                for w in w_vals:
                    row = {}
                    for g in g_vals:
                        r = _fcd(dados_s.get('fcl_milhoes', 0), dados_s.get('num_acoes_milhoes_param', 1),
                                  w, g, params_c.get('anos_projecao', 10),
                                  params_c.get('g_terminal', 0.045),
                                  dados_s.get('divida_liquida_milhoes', 0))
                        row[f'g={g:.1%}'] = f"R$ {r['preco_justo']:.2f}" if r.get('preco_justo') else 'N/D'
                    sens_data[f'WACC={w:.1%}'] = row
                df_sens = pd.DataFrame(sens_data).T
                st.dataframe(df_sens, use_container_width=True)
                st.markdown("<div style='color:#8b949e;font-size:.75rem'>Células em destaque = cenário base. "
                            "Leia: cada linha = WACC diferente, cada coluna = crescimento (g) diferente.</div>",
                            unsafe_allow_html=True)

    # ── Tab 3: Análise de Qualidade ───────────────────────────────────────────
    with tab3:
        dados_q = st.session_state.get('_calc_dados', dados_orig)
        cfg_q   = st.session_state.get('_emp_cfg', emp_cfg)
        preco_q = st.session_state.get('_calc_preco', float(dados_orig.get('preco_atual') or 0))

        relatorio = gerar_relatorio_completo(cfg_q, dados_q, preco_q)
        score = relatorio.get('score_qualidade', 5)

        # Score
        cor_score = '#00d4aa' if score >= 7 else ('#ffd700' if score >= 5 else '#ff4757')
        q1, q2 = st.columns([1, 3])
        with q1:
            st.markdown(f"""
            <div class='val-card' style='text-align:center;padding:24px'>
                <div style='font-size:.75rem;color:#8b949e;text-transform:uppercase;letter-spacing:1px'>Score de Qualidade</div>
                <div style='font-size:4rem;font-weight:800;color:{cor_score};line-height:1'>{score}</div>
                <div style='font-size:.75rem;color:#8b949e'>/10 — Conservador</div>
            </div>""", unsafe_allow_html=True)
        with q2:
            st.markdown("<div class='sec-hdr'>Endividamento</div>", unsafe_allow_html=True)
            alert_box(relatorio['endividamento'])
            st.markdown("<div class='sec-hdr'>CAPEX</div>", unsafe_allow_html=True)
            alert_box(relatorio['capex'])

        r1, r2 = st.columns(2)
        with r1:
            st.markdown("<div class='sec-hdr'>Rentabilidade</div>", unsafe_allow_html=True)
            for item in relatorio.get('rentabilidade', []):
                alert_box(item)
        with r2:
            st.markdown("<div class='sec-hdr'>Dividendos</div>", unsafe_allow_html=True)
            for item in relatorio.get('dividendos', []):
                alert_box(item)

        st.markdown("<div class='sec-hdr'>⚠️ Alertas do Analista</div>", unsafe_allow_html=True)
        for a in relatorio.get('alertas_analista', []):
            st.markdown(f"<div class='al-box al-atencao'>⚠️ {a}</div>", unsafe_allow_html=True)

        eventos = relatorio.get('eventos_nao_recorrentes', [])
        if eventos:
            st.markdown("<div class='sec-hdr'>🚫 Eventos Não-Recorrentes Identificados</div>", unsafe_allow_html=True)
            for ev in eventos:
                ano = ev.get('ano', '?')
                desc = ev.get('descricao', '')
                imp_l = ev.get('impacto_lucro_milhoes')
                imp_d = ev.get('impacto_dpa')
                impacto = ''
                if imp_l:
                    impacto = f" | Impacto lucro: {formatar_milhoes(imp_l)}"
                elif imp_d:
                    impacto = f" | Impacto DPA: R$ {imp_d:.2f}"
                st.markdown(f"<div class='al-box al-alerta'>🔴 <strong>{ano}:</strong> {desc}{impacto}</div>",
                            unsafe_allow_html=True)

        if ri_url:
            st.markdown(f"<div style='margin-top:20px'>"
                        f"<a href='{ri_url}' target='_blank' style='color:#4fc3f7;font-size:.85rem'>"
                        f"🔗 Acessar Relações com Investidores (RI)</a></div>", unsafe_allow_html=True)

    # ── Tab 4: Detalhamento FCD ───────────────────────────────────────────────
    with tab4:
        calc_fcd = st.session_state.get('_calc_result', {}).get('fcd', {})
        if not calc_fcd.get('valido'):
            st.info(f"ℹ️ FCD não calculado ou inválido. Razão: {calc_fcd.get('erro','Dados insuficientes')}")
        else:
            det = calc_fcd.get('detalhes', {})
            fcls = det.get('fcls_projetados', [])

            m1, m2, m3 = st.columns(3)
            with m1:
                st.metric('FCL Base', formatar_milhoes(det.get('fcl_base_milhoes')))
                st.metric('WACC', formatar_percentual(det.get('wacc')))
            with m2:
                st.metric('VP FCLs (Fase 1)', formatar_milhoes(det.get('soma_vp_fase1_milhoes')))
                st.metric('g Fase 1', formatar_percentual(det.get('g_fase1')))
            with m3:
                st.metric('VP Valor Terminal', formatar_milhoes(det.get('vp_terminal_milhoes')))
                st.metric('g Terminal', formatar_percentual(det.get('g_terminal')))

            st.markdown("<div style='margin-top:4px'></div>", unsafe_allow_html=True)
            m4, m5, m6 = st.columns(3)
            with m4:
                st.metric('EV Total', formatar_milhoes(det.get('ev_milhoes')))
            with m5:
                st.metric('(−) Dívida Líquida', formatar_milhoes(det.get('divida_liquida_milhoes')))
            with m6:
                st.metric('= Equity', formatar_milhoes(det.get('equity_milhoes')))

            st.markdown("<div class='sec-hdr'>Projeção Anual de FCL</div>", unsafe_allow_html=True)
            if fcls:
                from datetime import datetime
                ano_atual = datetime.now().year
                for f in fcls:
                    f['ano_calendario'] = ano_atual + f['ano']

                df_fcl = pd.DataFrame(fcls)
                df_fcl['AnoStr'] = df_fcl['ano_calendario'].astype(str)
                df_show = df_fcl[['AnoStr', 'fcl_milhoes', 'vp_milhoes']].copy()
                df_show.columns = ['Ano', 'FCL Projetado (R$ mi)', 'VP do FCL (R$ mi)']
                st.dataframe(df_show, use_container_width=True, hide_index=True)

                fig_fcl = go.Figure()
                fig_fcl.add_trace(go.Bar(
                    x=[str(f["ano_calendario"]) for f in fcls],
                    y=[f['fcl_milhoes'] for f in fcls],
                    name='FCL Projetado', marker_color='rgba(0,212,170,0.6)',
                ))
                fig_fcl.add_trace(go.Scatter(
                    x=[str(f["ano_calendario"]) for f in fcls],
                    y=[f['vp_milhoes'] for f in fcls],
                    name='VP do FCL', mode='lines+markers',
                    line=dict(color='#ffd700', width=2), marker=dict(size=6),
                ))
                fig_fcl.update_layout(**PLOT_CFG, height=300,
                                      xaxis=dict(gridcolor='rgba(255,255,255,0.05)', type='category'),
                                      yaxis=dict(gridcolor='rgba(255,255,255,0.05)', ticksuffix=' mi'),
                                      legend=dict(font=dict(color='#e6edf3')))
                st.plotly_chart(fig_fcl, use_container_width=True)

    # ── Tab 5: Histórico Trimestral ───────────────────────────────────────────
    with tab5:
        st.markdown("<div class='sec-hdr'>📈 Histórico Trimestral (yfinance)</div>", unsafe_allow_html=True)
        st.markdown("<div style='color:#8b949e;font-size:.85rem;margin-bottom:15px'>Dados brutos trimestrais obtidos através da API do Yahoo Finance. Útil para verificar defasagens ou validar efeitos não-recorrentes.</div>", unsafe_allow_html=True)
        
        from src.data_loader import buscar_historico_trimestral
        with st.spinner("Buscando histórico na API..."):
            hist = buscar_historico_trimestral(ticker)
        
        if hist and not hist.get('financials', pd.DataFrame()).empty:
            fin = hist['financials']
            bs = hist.get('balance_sheet', pd.DataFrame())
            cf = hist.get('cashflow', pd.DataFrame())
            
            metrics = {}
            if 'Total Revenue' in fin.index: metrics['Receita Líquida'] = fin.loc['Total Revenue']
            if 'Net Income' in fin.index: metrics['Lucro Líquido'] = fin.loc['Net Income']
            if 'EBITDA' in fin.index: metrics['EBITDA'] = fin.loc['EBITDA']
            
            if not cf.empty:
                if 'Free Cash Flow' in cf.index: metrics['FCL (Free Cash Flow)'] = cf.loc['Free Cash Flow']
                elif 'Operating Cash Flow' in cf.index and 'Capital Expenditure' in cf.index:
                    metrics['FCL (Free Cash Flow)'] = cf.loc['Operating Cash Flow'] + cf.loc['Capital Expenditure']
            
            if not bs.empty:
                if 'Total Debt' in bs.index: metrics['Dívida Bruta'] = bs.loc['Total Debt']
                if 'Cash And Cash Equivalents' in bs.index: metrics['Caixa e Equivalentes'] = bs.loc['Cash And Cash Equivalents']
            
            if metrics:
                df_hist = pd.DataFrame(metrics).T
                df_hist.columns = [c.strftime('%Y-%m-%d') if pd.notnull(c) else c for c in df_hist.columns]
                
                for col in df_hist.columns:
                    df_hist[col] = df_hist[col].apply(lambda x: formatar_moeda(x/1e6) + ' mi' if pd.notnull(x) else 'N/D')
                
                st.dataframe(df_hist, use_container_width=True)
            else:
                st.info("As métricas principais não foram encontradas nos dados trimestrais deste ticker.")
        else:
            st.warning("Histórico trimestral indisponível para este ativo.")

# ══════════════════════════════════════════════════════════════════════════════
# PAGE: COMPARATIVO
# ══════════════════════════════════════════════════════════════════════════════
def page_comparativo():
    st.markdown("""
    <div class='app-hdr'>
        <div class='app-title'>⚖️ Comparativo de Empresas</div>
        <div class='app-sub'>Compare múltiplos e margens de diferentes ativos lado a lado</div>
    </div>""", unsafe_allow_html=True)

    empresas = listar_acoes()
    opcoes = {f"{e['ticker']} - {e['nome']}": e['ticker'] for e in empresas}
    selecionadas = st.multiselect('Selecionar empresas (2 a 5)', list(opcoes.keys()),
                                   default=list(opcoes.keys())[:4], max_selections=5)
    if len(selecionadas) < 2:
        st.warning('Selecione pelo menos 2 empresas para comparar.')
        return

    tickers_sel = [opcoes[s] for s in selecionadas]
    multiplos = carregar_multiplos_setor()

    rows = []
    with st.spinner('Carregando dados...'):
        for ticker in tickers_sel:
            try:
                res = carregar_dados_empresa(ticker)
                dados = res['dados']
                cfg   = res['empresa_config']
                setor = cfg.get('setor', '')
                preco = float(dados.get('preco_atual') or 0)
                multiplo_ev = multiplos.get(setor, {}).get('ev_ebitda')
                params = build_params(ticker, setor, dados, {'multiplo_ev_ebitda': multiplo_ev})
                calc = calcular_todos(dados, params)
                pm = calc.get('_media')
                ms = (calcular_margem(preco, pm) or 0) * 100
                rows.append({
                    'Ticker': ticker, 'Nome': cfg.get('nome', ticker),
                    'Setor': setor.replace('_',' ').title(),
                    'Preço Atual': preco, 'Graham': calc['graham'].get('preco_justo'),
                    'Bazin': calc['bazin'].get('preco_justo'),
                    'Gordon': calc['gordon'].get('preco_justo'),
                    'FCD': calc['fcd'].get('preco_justo'),
                    'EV/EBITDA': calc['ev_ebitda'].get('preco_justo'),
                    'Preço Médio': pm, 'Margem (%)': ms,
                    'ROE (%)': float((dados.get('roe') or 0) * 100),
                    'DY (%)': float((dados.get('dy') or 0) * 100),
                    'D/EBITDA': (float(dados.get('divida_liquida_milhoes') or 0) /
                                  float(dados.get('ebitda_milhoes') or 1)
                                  if dados.get('ebitda_milhoes') and setor not in ('banco','seguro') else None),
                })
            except Exception:
                pass

    if not rows:
        st.error('Erro ao carregar dados.')
        return

    df = pd.DataFrame(rows)

    # Cards resumo
    st.markdown("<div class='sec-hdr'>Resumo Comparativo</div>", unsafe_allow_html=True)
    cols = st.columns(len(rows))
    for i, (col, row) in enumerate(zip(cols, rows)):
        ms = row.get('Margem (%)', 0)
        cor = '#00d4aa' if ms >= 15 else ('#ffd700' if ms >= 0 else '#ff4757')
        borda = 'border-green' if ms >= 15 else ('border-gold' if ms >= 0 else 'border-red')
        with col:
            st.markdown(f"""
            <div class='val-card {borda}' style='text-align:center'>
                <div style='font-size:.75rem;color:#8b949e'>{row.get('Setor','')}</div>
                <div style='font-size:1.2rem;font-weight:700;color:#e6edf3'>{row['Ticker']}</div>
                <div style='font-size:.75rem;color:#8b949e;margin-bottom:8px'>{row.get('Nome','')[:20]}</div>
                <div style='font-size:1.6rem;font-weight:800;color:#00d4aa'>{formatar_moeda(row.get('Preço Médio'))}</div>
                <div style='font-size:.8rem;color:#8b949e'>Atual: {formatar_moeda(row.get('Preço Atual'))}</div>
                <div style='font-size:1.1rem;font-weight:700;color:{cor};margin-top:6px'>{ms:+.1f}%</div>
            </div>""", unsafe_allow_html=True)

    # Gráfico comparativo de métodos
    st.markdown("<div class='sec-hdr'>Preço Justo por Método</div>", unsafe_allow_html=True)
    metodos_plot = ['Graham','Bazin','Gordon','FCD','EV/EBITDA','Preço Atual']
    cores_m = ['#00d4aa','#ffd700','#4fc3f7','#ff9f43','#a29bfe','#ff4757']
    fig2 = go.Figure()
    for metodo, cor in zip(metodos_plot, cores_m):
        vals = [row.get(metodo) for row in rows]
        fig2.add_trace(go.Bar(
            name=metodo, x=[r['Ticker'] for r in rows], y=vals,
            marker_color=cor, marker_line_color='rgba(255,255,255,0.1)', marker_line_width=1,
            text=[f'R$ {v:.2f}' if v else 'N/D' for v in vals],
            textposition='outside', textfont=dict(size=9),
        ))
    fig2.update_layout(**PLOT_CFG, height=380, barmode='group', showlegend=True,
                       legend=dict(font=dict(color='#e6edf3'), bgcolor='rgba(0,0,0,0)'),
                       xaxis=dict(gridcolor='rgba(255,255,255,0.05)'),
                       yaxis=dict(gridcolor='rgba(255,255,255,0.05)', tickprefix='R$ '))
    st.plotly_chart(fig2, use_container_width=True)

    # Radar de indicadores
    st.markdown("<div class='sec-hdr'>Radar de Indicadores de Qualidade</div>", unsafe_allow_html=True)
    categorias = ['Margem (%)', 'ROE (%)', 'DY (%)']
    fig_radar = go.Figure()
    cores_r = ['#00d4aa','#ffd700','#4fc3f7','#ff9f43','#a29bfe']
    for row, cor in zip(rows, cores_r):
        vals_r = [
            min(max(row.get('Margem (%)') or 0, -50), 80),
            min(row.get('ROE (%)') or 0, 40),
            min(row.get('DY (%)') or 0, 20),
        ]
        fig_radar.add_trace(go.Scatterpolar(
            r=vals_r + [vals_r[0]], theta=categorias + [categorias[0]],
            name=row['Ticker'], line=dict(color=cor, width=2),
            fill='toself', fillcolor=f"rgba({int(cor[1:3], 16)}, {int(cor[3:5], 16)}, {int(cor[5:7], 16)}, 0.08)",
        ))
    fig_radar.update_layout(**PLOT_CFG, height=350, showlegend=True,
                             polar=dict(bgcolor='rgba(255,255,255,0.02)',
                                        radialaxis=dict(gridcolor='rgba(255,255,255,0.1)', color='#8b949e'),
                                        angularaxis=dict(gridcolor='rgba(255,255,255,0.1)', color='#8b949e')),
                             legend=dict(font=dict(color='#e6edf3'), bgcolor='rgba(0,0,0,0)'))
    st.plotly_chart(fig_radar, use_container_width=True)

    # Tabela completa
    st.markdown("<div class='sec-hdr'>Tabela Completa</div>", unsafe_allow_html=True)
    df_show = df.copy()
    for col in ['Preço Atual','Graham','Bazin','Gordon','FCD','EV/EBITDA','Preço Médio']:
        if col in df_show:
            df_show[col] = df_show[col].apply(lambda x: f'R$ {x:.2f}' if pd.notna(x) and x else 'N/D')
    for col in ['Margem (%)','ROE (%)','DY (%)']:
        if col in df_show:
            df_show[col] = df_show[col].apply(lambda x: f'{x:.1f}%' if pd.notna(x) and x is not None else 'N/D')
    if 'D/EBITDA' in df_show:
        df_show['D/EBITDA'] = df_show['D/EBITDA'].apply(lambda x: f'{x:.1f}x' if pd.notna(x) and x is not None else 'N/A')
    st.dataframe(df_show, use_container_width=True, hide_index=True)

# ══════════════════════════════════════════════════════════════════════════════
# PAGE: ENTRADA MANUAL
# ══════════════════════════════════════════════════════════════════════════════
def page_manual():
    st.markdown("""
    <div class='app-hdr'>
        <div class='app-title'>📝 Entrada Manual de Dados</div>
        <div class='app-sub'>Documentação completa de cada campo · Como encontrar e calcular</div>
    </div>""", unsafe_allow_html=True)

    st.markdown("""
    <div class='al-box al-info'>
    ℹ️ <strong>Quando usar esta página:</strong> quando os dados online (fundamentus/yfinance) estiverem 
    desatualizados, incorretos ou indisponíveis. Preencha com dados do RI da empresa ou da CVM. 
    Os dados salvos aqui serão usados no Valuation.
    </div>""", unsafe_allow_html=True)

    empresas = listar_empresas()
    opcoes = {f"{e['ticker']} — {e['nome']}": e['ticker'] for e in empresas}
    sel = st.selectbox('Selecionar empresa', list(opcoes.keys()))
    ticker = opcoes[sel]

    res = carregar_dados_empresa(ticker)
    dados = res['dados']
    cfg   = res['empresa_config']

    st.markdown(f"<div class='al-box al-info'>🔗 RI: <a href='{cfg.get('referencia_ri','')}' target='_blank' "
                f"style='color:#4fc3f7'>{cfg.get('referencia_ri','—')}</a> | "
                f"Base de referência: {cfg.get('data_referencia','—')}</div>", unsafe_allow_html=True)
                
    st.markdown("<div style='color:#8b949e;font-size:.75rem;margin-bottom:15px;'>"
                "🕒 <i>Campos com este símbolo frequentemente exigem atualização manual lendo os relatórios do RI, "
                "pois apis gratuitas podem defasar ou distorcer (ex: efeitos não-recorrentes).</i><br>"
                "🤖 <i>Campos com este símbolo são utilizados exclusivamente pela IA na Análise de Qualidade "
                "e NÃO impactam os cálculos matemáticos dos Valuations.</i></div>", 
                unsafe_allow_html=True)

    with st.form('form_manual'):
        st.markdown("<div class='sec-hdr'>💲 Dados de Mercado</div>", unsafe_allow_html=True)
        f1, f2 = st.columns(2)
        with f1:
            m_preco = st.number_input('💲 Preço Atual (R$)',
                value=float(dados.get('preco_atual') or 0), min_value=0.0, step=0.01,
                help=('**O que é:** Cotação atual da ação na B3.\n\n'
                      '**Importância:** Base de comparação com o preço justo calculado.\n\n'
                      '**Como encontrar:** B3.com.br, corretora, Investing.com, fundamentus.com.br'))
        with f2:
            m_num_acoes = st.number_input('🔢 Nº de Ações (milhões)',
                value=float(cfg.get('num_acoes_milhoes') or 1), min_value=0.1, step=1.0,
                help=('**O que é:** Total de ações ordinárias + preferenciais em circulação.\n\n'
                      '**Importância:** Converte o valor da empresa (equity) em valor por ação.\n\n'
                      '**Como encontrar:** RI da empresa → Dados de Mercado, ou calcule: PL ÷ VPA.'))

        st.markdown("<div class='sec-hdr'>📊 Indicadores de Lucro e Patrimônio</div>", unsafe_allow_html=True)
        l1, l2, l3 = st.columns(3)
        with l1:
            m_lpa = st.number_input('📊 LPA — Lucro por Ação (R$)',
                value=float(dados.get('lpa') or 0), step=0.01,
                help=('**O que é:** Lucro Líquido ÷ Número de Ações em circulação.\n\n'
                      '**Importância:** Fundamento do método Graham (junto com VPA).\n\n'
                      '**Como calcular:** Lucro Líquido (DRE) ÷ Total de Ações. Disponível no fundamentus.com.br.\n\n'
                      '⚠️ **Atenção:** Use LPA normalizado (últimos 12 meses). EXCLUA eventos não-recorrentes '
                      '(provisões, ganhos de arbitragem, variação cambial sobre dívida).'))
        with l2:
            m_vpa = st.number_input('🏦 VPA — Valor Patrimonial por Ação (R$)',
                value=float(dados.get('vpa') or 0), min_value=0.0, step=0.01,
                help=('**O que é:** Patrimônio Líquido Total ÷ Número de Ações.\n\n'
                      '**Importância:** Fundamento do método Graham. Representa o valor contábil por ação.\n\n'
                      '**Como calcular:** PL (Balanço Patrimonial) ÷ Nº Ações. Encontre no RI ou CVM.'))
        with l3:
            m_roe = st.number_input('📈 ROE Atual (%) 🤖',
                value=float((dados.get('roe') or 0) * 100), min_value=0.0, max_value=200.0, step=0.1,
                help=('**O que é:** Retorno sobre Patrimônio Líquido = Lucro Líquido ÷ PL.\n\n'
                      '**Importância:** Mede eficiência da empresa. ROE > 15% = excelente, '
                      '< 10% = preocupante.\n\n'
                      '**Como encontrar:** fundamentus.com.br → coluna ROE, ou calcule manualmente.')) / 100

        st.markdown("<div class='sec-hdr'>💰 Dividendos por Ação (DPA)</div>", unsafe_allow_html=True)
        st.markdown("<div style='color:#8b949e;font-size:.8rem;margin-bottom:10px'>"
                    "📌 <strong>Como encontrar:</strong> RI da empresa → Proventos, "
                    "ou fundamentus.com.br → coluna Div.Yield × cotação ÷ 100. "
                    "Extrato de proventos na sua corretora também funciona.<br>"
                    "⚠️ <strong>Bazin:</strong> Use DPA normalizado — EXCLUA dividendos extraordinários "
                    "(acima do payout normal da empresa).</div>", unsafe_allow_html=True)
        dpa_h = list(dados.get('dpa_historico', [0, 0, 0])) + [0, 0, 0]
        d1, d2, d3 = st.columns(3)
        with d1:
            md1 = st.number_input('DPA Ano -2 (R$)', value=float(dpa_h[0]), min_value=0.0, step=0.01,
                                   help='DPA pago 2 anos atrás.')
        with d2:
            md2 = st.number_input('DPA Ano -1 (R$)', value=float(dpa_h[1]), min_value=0.0, step=0.01,
                                   help='DPA pago 1 ano atrás.')
        with d3:
            md3 = st.number_input('DPA Último Ano (R$)', value=float(dpa_h[2]), min_value=0.0, step=0.01,
                                   help='DPA do exercício mais recente.')

        st.markdown("<div class='sec-hdr'>🏗️ Balanço & Fluxo de Caixa</div>", unsafe_allow_html=True)
        b1, b2, b3 = st.columns(3)
        with b1:
            m_ebitda = st.number_input('💹 EBITDA (R$ milhões) 🕒',
                value=float(dados.get('ebitda_milhoes') or 0), min_value=0.0, step=10.0,
                help=('**O que é:** Lucro antes de Juros, Impostos, Depreciação e Amortização. '
                      'Proxy do caixa operacional bruto.\n\n'
                      '**Importância:** Base do EV/EBITDA e do índice D/EBITDA (endividamento).\n\n'
                      '**Como encontrar:** DRE + Notas Explicativas (RI ou CVM).\n\n'
                      '⚠️ **Atenção:** AJUSTE por itens não-recorrentes. Use EBITDA ajustado da empresa '
                      'quando disponível.'))
            m_fcl = st.number_input('💰 FCL — Fluxo Caixa Livre (R$ mi) 🕒',
                value=float(dados.get('fcl_milhoes') or 0), step=10.0,
                help=('**O que é:** FCO (Fluxo de Caixa Operacional) − CAPEX.\n\n'
                      '**Importância:** Fundamento do FCD. FCL < 0 → FCD não aplicável.\n\n'
                      '**Como calcular:** Na DFC: FCO (atividades operacionais) − CAPEX (atividades de investimento).\n\n'
                      '⚠️ **Atenção:** EXCLUA variações não-recorrentes de capital de giro. '
                      'FCL pode ser negativo em anos de forte investimento (ex: Klabin com Puma II).'))
        with b2:
            m_divida = st.number_input('🏋️ Dívida Líquida (R$ milhões) 🕒',
                value=float(dados.get('divida_liquida_milhoes') or 0), step=100.0,
                help=('**O que é:** Dívida Bruta Total − Caixa e Equivalentes.\n\n'
                      '**Importância:** D/EBITDA > 3x = sinal de alerta conservador. '
                      'Desconta do EV no FCD e EV/EBITDA.\n\n'
                      '**Como encontrar:** Balanço Patrimonial → Passivo (Empréstimos e Financiamentos) '
                      '− Ativo (Caixa). Notas Explicativas dão o detalhe.\n\n'
                      '⚠️ **Bancos/Seguradoras:** Não usar D/EBITDA. Usar Índice de Basileia.'))
            m_capex = st.number_input('🏗️ CAPEX (R$ milhões) 🕒 🤖',
                value=float(dados.get('capex_milhoes') or 0), min_value=0.0, step=10.0,
                help=('**O que é:** Capital Expenditure — investimentos em ativos fixos (imobilizado, intangível).\n\n'
                      '**Importância:** CAPEX/EBITDA > 70% = empresa intensiva em capital → FCL comprimido.\n\n'
                      '**Como encontrar:** DFC (atividades de investimento) → '
                      '"Aquisição de imobilizado" ou "Adições ao ativo imobilizado". '
                      'Nota: sai negativo na DFC.'))
        with b3:
            m_pl = st.number_input('🏦 Patrimônio Líquido (R$ mi) 🤖',
                value=float(dados.get('patrimonio_liquido_milhoes') or 0), min_value=0.0, step=100.0,
                help=('**O que é:** Ativos − Passivos. Capital dos acionistas.\n\n'
                      '**Importância:** Base de cálculo do VPA e ROE.\n\n'
                      '**Como encontrar:** Balanço Patrimonial → Patrimônio Líquido total (RI ou CVM).'))
            m_receita = st.number_input('📊 Receita Líquida (R$ mi) 🕒 🤖',
                value=float(dados.get('receita_liquida_milhoes') or 0), min_value=0.0, step=100.0,
                help=('**O que é:** Receita total − deduções (impostos sobre vendas, devoluções).\n\n'
                      '**Como encontrar:** DRE → primeira linha após deduções (RI ou CVM).'))

        st.markdown("<div class='sec-hdr'>📈 Crescimentos Históricos (CAGR 5 anos)</div>", unsafe_allow_html=True)
        cr1, cr2 = st.columns(2)
        with cr1:
            m_g_lucro = st.number_input('📊 Crescimento LPA/Lucro — 5a (%)',
                value=float((dados.get('crescimento_lucro_5a') or 0.06) * 100),
                min_value=-50.0, max_value=50.0, step=0.5,
                help=('**O que é:** CAGR do LPA nos últimos 5 anos.\n\n'
                      '**Importância:** Taxa g usada na Fase 1 do FCD como premissa de crescimento.\n\n'
                      '**Como calcular:** (LPA_atual ÷ LPA_5anos_atrás)^(1/5) − 1.\n\n'
                      '⚠️ Crescimento passado NÃO garante o futuro. Use com conservadorismo.')) / 100
        with cr2:
            m_g_dpa = st.number_input('💰 Crescimento DPA — 5a (%)',
                value=float((dados.get('crescimento_dpa_5a') or 0.06) * 100),
                min_value=-50.0, max_value=50.0, step=0.5,
                help=('**O que é:** CAGR do DPA nos últimos 5 anos.\n\n'
                      '**Importância:** Taxa g usada no Modelo de Gordon.\n\n'
                      '**Como calcular:** (DPA_atual ÷ DPA_5anos_atrás)^(1/5) − 1.')) / 100
                      
        st.markdown("<div class='sec-hdr'>⚙️ Parâmetros Específicos do Ativo</div>", unsafe_allow_html=True)
        w1, w2 = st.columns(2)
        with w1:
            m_wacc = st.number_input('🏦 WACC / Custo do Capital (%)',
                value=float(cfg.get('wacc') * 100) if cfg.get('wacc') is not None else 0.0, step=0.5,
                help='Custo médio ponderado de capital específico para esta empresa. Se deixado em 0.0, o sistema usará o WACC padrão do setor (Selic + Prêmio).') / 100
            
            if m_wacc == 0: m_wacc = None

        submitted = st.form_submit_button('💾 Salvar e Ir para Valuation', use_container_width=True)

    if submitted:
        from src.data_loader import salvar_dados_manuais
        dpa_lista = [x for x in [md1, md2, md3] if x > 0]
        dados_manual = {
            'preco_atual': m_preco, 'lpa': m_lpa, 'vpa': m_vpa, 'roe': m_roe,
            'ebitda_milhoes': m_ebitda, 'fcl_milhoes': m_fcl,
            'divida_liquida_milhoes': m_divida, 'capex_milhoes': m_capex,
            'patrimonio_liquido_milhoes': m_pl, 'receita_liquida_milhoes': m_receita,
            'num_acoes_milhoes_param': m_num_acoes, 'dpa_historico': dpa_lista,
            'crescimento_lucro_5a': m_g_lucro, 'crescimento_dpa_5a': m_g_dpa,
            'wacc': m_wacc,
        }
        st.session_state['manual_dados'][ticker] = dados_manual
        
        if salvar_dados_manuais(ticker, dados_manual):
            st.success('✅ Dados salvos com sucesso na base local! Redirecionando...')
            st.session_state['valuation_ticker'] = ticker
            st.session_state['page'] = 'valuation'
            st.cache_data.clear()
            st.rerun()
        else:
            st.error('❌ Erro ao salvar os dados.')
        st.session_state['valuation_ticker'] = ticker
        st.session_state['_calc_dados'] = dados_manual
        setor = cfg.get('setor', '')
        params_m = build_params(ticker, setor, dados_manual,
                                {'multiplo_ev_ebitda': carregar_multiplos_setor().get(setor, {}).get('ev_ebitda')})
        st.session_state['_calc_params'] = params_m
        st.session_state['_calc_result'] = calcular_todos(dados_manual, params_m)
        st.session_state['_calc_ticker'] = ticker
        st.session_state['_calc_preco'] = m_preco
        st.session_state['_calc_metodos_sel'] = {k: True for k in METODO_INFO}
        st.session_state['_emp_cfg'] = cfg
        st.success(f'✅ Dados de {ticker} salvos! Redirecionando para Valuation...')
        st.session_state['page'] = 'valuation'
        st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
# PAGE: CONFIGURAÇÕES
# ══════════════════════════════════════════════════════════════════════════════
def page_config():
    st.markdown("""
    <div class='app-hdr'>
        <div class='app-title'>⚙️ Configurações</div>
        <div class='app-sub'>Taxas macroeconômicas · Parâmetros de valuation · Múltiplos setoriais</div>
    </div>""", unsafe_allow_html=True)

    with st.form('form_config'):
        st.markdown("<div class='sec-hdr'>📈 Taxas Macroeconômicas</div>", unsafe_allow_html=True)
        m1, m2 = st.columns(2)
        with m1:
            nova_selic = st.slider('Selic (% a.a.)',
                min_value=5.0, max_value=25.0,
                value=float(st.session_state.get('selic', config.SELIC_ANUAL) * 100), step=0.25,
                help='Taxa Selic atual. Base para cálculo do WACC. Jun/2026: 14,5%.') / 100
        with m2:
            novo_ipca = st.slider('IPCA Projetado (% a.a.)',
                min_value=2.0, max_value=12.0,
                value=float(st.session_state.get('ipca', config.IPCA_PROJETADO) * 100), step=0.25,
                help='IPCA projetado para o longo prazo. Usado como g terminal no FCD.') / 100

        st.markdown("<div class='sec-hdr'>🏠 Método Bazin</div>", unsafe_allow_html=True)
        nova_taxa_b = st.slider('Taxa Mínima de Retorno (%)',
            min_value=3.0, max_value=12.0,
            value=float(st.session_state.get('taxa_bazin', 0.06) * 100), step=0.25,
            help='Taxa de DY mínima para o Preço-Teto de Bazin. Padrão: 6%.') / 100

        st.markdown("<div class='sec-hdr'>🧮 Método Graham</div>", unsafe_allow_html=True)
        g1, g2 = st.columns(2)
        with g1:
            nova_ms = st.slider('Margem de Segurança (%)',
                min_value=10, max_value=50,
                value=int(st.session_state.get('margem_seguranca', 0.33) * 100), step=1,
                help='Desconto aplicado ao valor intrínseco de Graham. Padrão conservador: 33%.') / 100
        with g2:
            novo_mult = st.slider('Multiplicador Graham',
                min_value=15.0, max_value=30.0, value=22.5, step=0.5,
                help='Constante da fórmula de Graham. Original: 22,5 (P/L ≤ 15 × P/VP ≤ 1,5).')

        st.markdown("<div class='sec-hdr'>💰 FCD — Parâmetros</div>", unsafe_allow_html=True)
        novos_anos = st.slider('Anos de Projeção',
            min_value=5, max_value=15,
            value=int(st.session_state.get('anos_projecao', 10)), step=1,
            help='Horizonte de projeção da Fase 1. Padrão: 10 anos.')

        st.markdown("<div class='sec-hdr'>📊 Múltiplos EV/EBITDA Setoriais</div>", unsafe_allow_html=True)
        multiplos = carregar_multiplos_setor()
        custom_m = st.session_state.get('multiplos_setor_custom', {})
        mult_cols = st.columns(3)
        setores_com_ev = [(s, d) for s, d in multiplos.items() if d.get('ev_ebitda')]
        novos_mult = {}
        for i, (setor, data) in enumerate(setores_com_ev):
            with mult_cols[i % 3]:
                v = st.number_input(f'{setor.replace("_"," ").title()}',
                    value=float(custom_m.get(setor) or data.get('ev_ebitda', 7.0)),
                    min_value=1.0, max_value=25.0, step=0.5, key=f'mult_{setor}',
                    help=f'Múltiplo EV/EBITDA de referência para o setor {setor}.')
                novos_mult[setor] = v

        st.markdown("<div class='sec-hdr'>⚠️ Prêmios de Risco Setoriais (sobre Selic)</div>", unsafe_allow_html=True)
        premio_cols = st.columns(3)
        custom_p = st.session_state.get('premio_risco_custom', {})
        novos_premios = {}
        for i, (setor, premio) in enumerate(config.PREMIO_RISCO_SETOR.items()):
            with premio_cols[i % 3]:
                v = st.number_input(f'{setor.replace("_"," ").title()} (%)',
                    value=float((custom_p.get(setor) or premio) * 100),
                    min_value=0.5, max_value=15.0, step=0.25, key=f'premio_{setor}',
                    help=f'Prêmio de risco adicional sobre a Selic para o setor {setor}.') / 100
                novos_premios[setor] = v

        c1, c2 = st.columns(2)
        with c1:
            salvar = st.form_submit_button('💾 Salvar Configurações', use_container_width=True)
        with c2:
            resetar = st.form_submit_button('🔄 Resetar para Padrão', use_container_width=True)

    if salvar:
        st.session_state['selic'] = nova_selic
        st.session_state['ipca'] = novo_ipca
        st.session_state['taxa_bazin'] = nova_taxa_b
        st.session_state['margem_seguranca'] = nova_ms
        st.session_state['anos_projecao'] = novos_anos
        st.session_state['multiplos_setor_custom'] = novos_mult
        st.session_state['premio_risco_custom'] = novos_premios
        st.cache_data.clear()
        st.success('✅ Configurações salvas! Valuations recalculados com os novos parâmetros.')
        st.rerun()

    if resetar:
        for k in ['selic','ipca','taxa_bazin','margem_seguranca','anos_projecao',
                  'multiplos_setor_custom','premio_risco_custom']:
            if k in st.session_state:
                del st.session_state[k]
        st.cache_data.clear()
        st.success('✅ Configurações resetadas para os valores padrão.')
        st.rerun()

    # Tabela resumo das configurações atuais
    st.markdown("<div class='sec-hdr'>Configurações Atuais</div>", unsafe_allow_html=True)
    selic = st.session_state.get('selic', config.SELIC_ANUAL)
    resumo = {
        'Selic': formatar_percentual(selic),
        'IPCA proj.': formatar_percentual(st.session_state.get('ipca', config.IPCA_PROJETADO)),
        'Taxa Bazin': formatar_percentual(st.session_state.get('taxa_bazin', 0.06)),
        'Margem Graham': formatar_percentual(st.session_state.get('margem_seguranca', 0.33)),
        'Anos FCD': str(st.session_state.get('anos_projecao', 10)),
    }
    st.dataframe(pd.DataFrame([resumo]), use_container_width=True, hide_index=True)

# ══════════════════════════════════════════════════════════════════════════════
# PAGE: METODOLOGIA
# ══════════════════════════════════════════════════════════════════════════════
def page_metodologia():
    st.markdown("""
    <div class='app-hdr'>
        <div class='app-title'>📚 Metodologia de Valuation</div>
        <div class='app-sub'>Cálculos detalhados · Parâmetros · Aplicação de cada método</div>
    </div>""", unsafe_allow_html=True)
    
    st.markdown("""
    A plataforma **ValuaçãoBR** utiliza métodos consagrados no mercado financeiro para determinar o *Preço Justo* de uma ação. Diferentes métodos servem para diferentes tipos de empresas. Abaixo, detalhamos como cada modelo matemático é calculado nos bastidores.
    
    ---
    
    ### 1. Método de Bazin (Décio Bazin)
    
    O método de Bazin foca em empresas que são excelentes pagadoras de dividendos. Ele determina o preço máximo que você deve pagar por uma ação para garantir um Retorno em Dividendos (*Dividend Yield* - DY) de no mínimo 6% ao ano.
    
    **Fórmula (Preço-Teto):**
    
    $$ P_{teto} = \\frac{DPA_{projetado}}{Taxa_{minima}} $$
    
    **Parâmetros Principais:**
    * **$DPA_{projetado}$**: Dividendo por Ação esperado. Na ferramenta, utilizamos a média dos dividendos pagos nos últimos 3 anos para suavizar anos atípicos.
    * **$Taxa_{minima}$**: O retorno exigido pelo investidor. A regra de ouro de Bazin é **6%** (0.06), mas você pode ajustar isso na tela de Configurações.
    
    **Aplicações Ideais:** 
    * Bancos, Seguradoras, Transmissoras de Energia e Saneamento.
    * Empresas maduras, com lucros estáveis e alto repasse de proventos (*payout* alto).
    * *Cuidado:* Não serve para empresas em fase de crescimento acelerado que retêm caixa para investir (pois o DY será quase nulo).
    
    ---
    
    ### 2. Método de Graham (Benjamin Graham)
    
    Criado pelo mentor de Warren Buffett, foca exclusivamente em "comprar barato" olhando o patrimônio tangível da empresa e seu lucro, ignorando projeções otimistas de crescimento futuro. 
    
    **Fórmula (Valor Intrínseco):**
    
    $$ V_{intrinseco} = \\sqrt{22,5 \\times LPA \\times VPA} $$
    
    $$ Preço_{Justo} = V_{intrinseco} \\times (1 - Margem\\ de\\ Segurança) $$
    
    **Parâmetros Principais:**
    * **$22,5$**: Multiplicador empírico de Graham, que pressupõe que o Preço/Lucro (P/L) não deve exceder 15x, e o Preço/Valor Patrimonial (P/VP) não deve exceder 1,5x ($15 \\times 1,5 = 22,5$).
    * **$LPA$**: Lucro por Ação. Calculado como Lucro Líquido $\\div$ Número de Ações.
    * **$VPA$**: Valor Patrimonial da Ação. Calculado como Patrimônio Líquido $\\div$ Número de Ações.
    * **$Margem\\ de\\ Segurança$**: Um desconto aplicado sobre o valor intrínseco para proteger contra erros de estimativa (padrão conservador da ferramenta: 33%).
    
    **Aplicações Ideais:**
    * Indústria tradicional, bancos com forte base patrimonial, empresas de commodities (ciclo de baixa).
    * *Cuidado:* O método falha em empresas de tecnologia ou prestadoras de serviço cujo valor não está no patrimônio físico (máquinas, imóveis), mas sim em propriedade intelectual ou marca.
    
    ---
    
    ### 3. Modelo de Gordon (Gordon Growth Model)
    
    É um modelo de desconto de dividendos. Diferente do Bazin que considera o dividendo estático, o Modelo de Gordon precifica o fato de que os dividendos de uma boa empresa *crescerão* ao longo do tempo até o infinito.
    
    **Fórmula:**
    
    $$ Preço_{Justo} = \\frac{DPA_0 \\times (1 + g)}{k - g} $$
    
    **Parâmetros Principais:**
    * **$DPA_0$**: O dividendo pago no último ano.
    * **$g$**: Taxa de crescimento anual projetada para os dividendos. Na ferramenta, utilizamos o CAGR (Crescimento Anual Composto) histórico de 5 anos como base, limitado a um teto conservador. Como calcular o CAGR: $\\left(\\frac{Valor_{Atual}}{Valor_{Anterior}}\\right)^{\\frac{1}{Anos}} - 1$.
    * **$k$**: Custo de Capital do Acionista (geralmente usamos o WACC como proxy do custo de oportunidade).
    * *Nota:* O método exige matematicamente que a taxa de desconto $k$ seja maior que o crescimento $g$ ($k > g$).
    
    **Aplicações Ideais:**
    * Empresas sólidas com forte histórico de repasse de lucros, que crescem de forma sustentável (ex: grandes bancos, energia).
    
    ---
    
    ### 4. Fluxo de Caixa Descontado (FCD / DCF)
    
    O método mais complexo e mais utilizado no mundo acadêmico e corporativo. Ele assume que o valor de uma empresa hoje é a soma de todo o dinheiro (caixa) que ela vai colocar no bolso dos acionistas no futuro, descontado pelo custo de oportunidade.
    
    **Fórmulas Básicas:**
    
    $$ Valor\\ da\\ Empresa (EV) = \\sum_{t=1}^{n} \\frac{FCL_t}{(1+WACC)^t} + \\frac{Valor\\ Terminal}{(1+WACC)^n} $$
    
    $$ Preço_{Justo} = \\frac{EV - Divida\\ Liquida + Caixa}{Numero\\ de\\ Ações} $$
    
    **Parâmetros e Cálculos Secundários:**
    * **$FCL$ (Fluxo de Caixa Livre)**: É o dinheiro que sobra após pagar despesas, impostos e reinvestir na operação. 
      * *Como calcular:* $FCL = Fluxo\\ Operacional\\ (FCO) - CAPEX\\ (Investimentos)$. Retirado da Demonstração de Fluxo de Caixa (DFC).
    * **$WACC$ (Custo Médio Ponderado de Capital)**: A taxa de desconto. Funciona como a "gravidade" que puxa o valor do dinheiro no futuro para o presente.
      * *Como calcular na ferramenta:* Utilizamos um método simplificado somando a Taxa Macro Base (Selic) com um Prêmio de Risco Setorial (ex: Selic 10% + Prêmio Energia 4% = WACC 14%).
    * **$Valor\\ Terminal$**: O valor da empresa do ano $n$ em diante até o infinito, assumindo um crescimento perpétuo constante.
      * *Como calcular:* $Valor\\ Terminal = \\frac{FCL_{n} \\times (1 + g_{terminal})}{WACC - g_{terminal}}$. Onde $g_{terminal}$ geralmente é a inflação de longo prazo (IPCA projetado).
    
    **Aplicações Ideais:**
    * A maioria das empresas da Bolsa, especialmente concessões (rodovias, telecom), indústria, papel/celulose e varejo não-financeiro.
    * *Cuidado:* Não se aplica diretamente a Bancos e Seguradoras, pois para estes negócios a "dívida" (depósitos dos clientes) e o "estoque" (dinheiro) se confundem. Use Bazin ou Gordon para o setor financeiro.
    
    ---
    
    ### 5. Múltiplos EV / EBITDA
    
    Método de valuation relativo. Estima o valor de mercado justo da empresa ao compará-la com o múltiplo de aquisição padrão do seu setor.
    
    **Fórmulas:**
    
    $$ Valor\\ da\\ Empresa (EV_{projetado}) = EBITDA \\times Multiplo_{Setor} $$
    
    $$ Preço_{Justo} = \\frac{EV_{projetado} - Divida\\ Liquida + Caixa}{Numero\\ de\\ Ações} $$
    
    **Parâmetros Principais:**
    * **$EBITDA$**: Geração de caixa operacional bruta (Lucro antes de Juros, Impostos, Depreciação e Amortização).
    * **$Multiplo_{Setor}$**: Referência de mercado (quantas vezes o EBITDA os investidores pagam em média por empresas deste segmento). Exemplo: Setor de Transmissão costuma negociar a 9x EV/EBITDA.
    * **Dívida Líquida**: Subtraída do EV porque quem compra a empresa, herda a dívida. Calculada como $Dívida\\ Bruta - Caixa\\ e\\ Equivalentes$.
    
    **Aplicações Ideais:**
    * Empresas industriais, mineração, petróleo, onde grandes investimentos em maquinário (depreciação) distorcem o Lucro Líquido, tornando o EBITDA uma métrica mais limpa.
    * Fusões e Aquisições (M&A).
    
    ---
    
    ### 6. Método de Warren Buffett (Owner Earnings / EPS Growth)
    
    Inspirado na filosofia do maior investidor de todos os tempos, este método trata a ação como um "título de renda variável" (*Equity Bond*). Ele foca na premissa de que o crescimento sustentável de uma empresa no longo prazo é ditado por sua rentabilidade (ROE) e sua capacidade de reter lucros para reinvestir, sem depender de dívidas.
    
    **Fórmulas:**
    
    $$ g_{sustentável} = ROE \\times Retenção $$
    
    $$ LPA_{futuro} = LPA_{atual} \\times (1 + g_{sustentável})^{10} $$
    
    $$ Preço_{Justo} = \\frac{LPA_{futuro} \\times P/L_{projetado}}{(1 + WACC)^{10}} $$
    
    **Parâmetros e Cálculos Secundários:**
    * **$Retenção$**: O percentual do lucro que a empresa NÃO distribui como dividendos. Calculado como $1 - Payout$. Onde $Payout = DPA \\div LPA$.
    * **$g_{sustentável}$**: A taxa máxima que a empresa consegue crescer seus lucros de forma orgânica e estrutural.
    * **$P/L_{projetado}$**: Múltiplo Preço/Lucro estimado para a venda da empresa no ano 10. Na ferramenta, utilizamos a média do setor limitando a 15x.
    * **$WACC$ (Taxa de Desconto)**: Utilizamos o WACC da ferramenta, ao invés da taxa clássica de 15% de Buffett, para padronizar com a taxa macroeconômica atual do Brasil (conforme parametrizado).
    
    **Aplicações Ideais:**
    * Empresas maduras, de alta qualidade, com forte vantagem competitiva (fosso econômico / *moat*).
    * Excelente para empresas com altíssimo ROE e que conseguem reter lucros produtivamente.
    """)

# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════
def main():
    st.markdown(CSS, unsafe_allow_html=True)
    init_session()
    render_sidebar()

    page = st.session_state.get('page', 'dashboard')
    if page == 'dashboard':
        page_dashboard()
    elif page == 'carteira':
        page_carteira()
    elif page == 'valuation':
        page_valuation()
    elif page == 'comparativo':
        page_comparativo()
    elif page == 'manual':
        page_manual()
    elif page == 'config':
        page_config()
    elif page == 'metodologia':
        page_metodologia()

if __name__ == '__main__':
    main()
