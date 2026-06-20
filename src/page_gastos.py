import streamlit as st
import pandas as pd
import requests
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import os

API_BASE_URL = "http://localhost:8000/api/v1"
ENV_PATH = "API_pluggy/.env"

def formatar_moeda(valor):
    if pd.isna(valor): return "R$ 0,00"
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def get_saved_item_ids():
    item_ids = []
    if os.path.exists(ENV_PATH):
        with open(ENV_PATH, "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("PLUGGY_ITEM_IDS="):
                    val = line.strip().split("=", 1)[1]
                    if val:
                        item_ids = [i.strip() for i in val.split(",") if i.strip()]
    return item_ids

def get_saved_filters():
    cat_filters = ['same person transfer', 'transferência interna', 'internal', 'credit card payment', 'invest', 'proceeds', 'loan', 'empréstimo']
    desc_filters = ['renda variável', 'dinheiro reservado', 'resgate', 'aplicação', 'fatura', 'pagamento de fatura', 'pagamento de cartão', 'investimento', 'cdb', 'cdi', 'tesouro direto']
    if os.path.exists(ENV_PATH):
        with open(ENV_PATH, "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("PLUGGY_FILTER_CATEGORIES="):
                    val = line.strip().split("=", 1)[1]
                    if val:
                        cat_filters = [i.strip() for i in val.split(",") if i.strip()]
                elif line.startswith("PLUGGY_FILTER_DESCRIPTIONS="):
                    val = line.strip().split("=", 1)[1]
                    if val:
                        desc_filters = [i.strip() for i in val.split(",") if i.strip()]
    return cat_filters, desc_filters

def save_config(item_ids_str, cat_filters_str, desc_filters_str):
    if not os.path.exists(ENV_PATH):
        st.error(f"Arquivo {ENV_PATH} não encontrado. Configure-o primeiro.")
        return False
        
    lines = []
    with open(ENV_PATH, "r", encoding="utf-8") as f:
        lines = f.readlines()
        
    def update_or_add(key, value):
        found = False
        for i, line in enumerate(lines):
            if line.startswith(f"{key}="):
                lines[i] = f"{key}={value}\n"
                found = True
                break
        if not found:
            lines.append(f"{key}={value}\n")
            
    update_or_add("PLUGGY_ITEM_IDS", item_ids_str)
    update_or_add("PLUGGY_FILTER_CATEGORIES", cat_filters_str)
    update_or_add("PLUGGY_FILTER_DESCRIPTIONS", desc_filters_str)
        
    with open(ENV_PATH, "w", encoding="utf-8") as f:
        f.writelines(lines)
        
    return True

def fetch_accounts():
    try:
        response = requests.get(f"{API_BASE_URL}/accounts", timeout=10)
        if response.status_code == 200:
            return response.json()
        return []
    except requests.exceptions.ConnectionError:
        return []

def fetch_transactions(account_id=None):
    try:
        params = {
            "exclude_investments": "true",
            "exclude_transfers": "true",
            "limit": 5000
        }
        if account_id and account_id != "all":
            params["account_id"] = account_id
            
        response = requests.get(f"{API_BASE_URL}/transactions", params=params, timeout=10)
        if response.status_code == 200:
            return response.json()
        else:
            st.error(f"Erro da API: {response.status_code} - {response.text}")
            return []
    except requests.exceptions.ConnectionError:
        st.error("❌ Não foi possível conectar ao Backend (FastAPI). Certifique-se de ter rodado o 'start_app.bat'.")
        return []

def render_page_gastos():
    st.markdown("""
    <div class='app-hdr'>
        <div class='app-title'>💳 Controle de Gastos</div>
        <div class='app-sub'>Consolidação de transações de Contas e Cartões de Crédito (Pluggy)</div>
    </div>""", unsafe_allow_html=True)
    
    # UI Removida: Migrada para app.py -> Sistema -> Configurações
    current_ids = get_saved_item_ids()
    if current_ids:
        if st.button("🔄 Sincronizar Histórico da Pluggy (Demorado)", type="primary"):
            with st.spinner("Sincronizando com a Pluggy. Isso pode levar de 30 a 90 segundos..."):
                sucessos = 0
                for item_id in current_ids:
                    try:
                        res = requests.post(f"{API_BASE_URL}/items/{item_id}/sync", timeout=120)
                        if res.status_code == 200:
                            sucessos += 1
                        else:
                            st.error(f"Erro ao sincronizar {item_id}: {res.text}")
                    except Exception as e:
                        st.error(f"Falha na comunicação: {e}")
                
                if sucessos > 0:
                    st.success(f"{sucessos} itens sincronizados e extraídos localmente com sucesso!")
                        
    st.markdown("<hr style='border-color:rgba(255,255,255,0.07);margin:12px 0'>", unsafe_allow_html=True)
    
    # 2. CARREGAR CONTAS PARA FILTRO
    accounts = fetch_accounts()
    conta_opcoes = {"all": "🏦 Todas as Contas"}
    for acc in accounts:
        conta_opcoes[acc['id']] = f"{acc['name']} ({acc['type'].upper()})"
        
    st.markdown("<div class='sec-hdr'>🔍 Filtros Rápidos</div>", unsafe_allow_html=True)
    f1, f2, f3 = st.columns(3)
    with f1:
        selected_account_id = st.selectbox("Conta", options=list(conta_opcoes.keys()), format_func=lambda x: conta_opcoes[x])
        
    # 3. CARREGAR TRANSAÇÕES
    txns = fetch_transactions(selected_account_id)
    if not txns:
        st.info("Nenhuma transação encontrada para os filtros selecionados ou nenhuma conexão existente. Sincronize os dados acima para começar.")
        return
        
    df = pd.DataFrame(txns)
    df['date'] = pd.to_datetime(df['date'])
    df['month'] = df['date'].dt.to_period('M')
    
    # O padrão da Pluggy é type='DEBIT' para despesas e type='CREDIT' para receitas
    df['is_expense'] = df['type'] == 'DEBIT'
    # Como despesas de cartão vêm positivas e despesas de conta vêm negativas, 
    # a forma segura de somar é usar o valor absoluto e aplicar a lógica de soma com base no 'is_expense'
    df['amount_abs'] = df['amount'].abs()
    
    # -------------------------------------------------------------------------
    # Filtro de Segurança Anti-Distorção (Evita contagem dupla)
    # Removemos explícitamente categorias e DESCRIÇÕES que configuram 
    # movimentações internas, pagamentos de cartão e investimentos.
    # -------------------------------------------------------------------------
    termos_excluir_cat, termos_excluir_desc = get_saved_filters()
    
    def deve_excluir(row):
        cat_lower = str(row['final_category']).lower()
        desc_lower = str(row['description']).lower()
        
        # Checa Categoria
        for termo in termos_excluir_cat:
            if termo.lower() in cat_lower:
                return True
                
        # Checa Descrição (para pegar erros da IA da Pluggy)
        for termo in termos_excluir_desc:
            if termo.lower() in desc_lower:
                return True
                
        return False
        
    df_raw = df.copy()
    df = df[~df.apply(deve_excluir, axis=1)]
    
    if df_raw.empty:
        st.info("Não há transações na base de dados.")
        return
    # O usuário pediu categorias clássicas, a Pluggy já provê algumas. Podemos mapear se necessário.
    
    # 3. FILTROS
    meses_disponiveis = df['month'].unique().astype(str).tolist()
    meses_disponiveis.sort(reverse=True)
    
    # Processar Drill-down do Gráfico de Barras (Mês) ANTES de instanciar o widget
    if "last_bar_selection" not in st.session_state:
        st.session_state.last_bar_selection = None
    
    current_bar_selection = None
    bar_state = st.session_state.get("bar_chart_drilldown")
    if bar_state and "selection" in bar_state:
        pts = bar_state["selection"].get("points", [])
        if pts and len(pts) > 0:
            current_bar_selection = pts[0].get("x")
            
    if current_bar_selection != st.session_state.last_bar_selection:
        st.session_state.last_bar_selection = current_bar_selection
        if current_bar_selection and current_bar_selection in meses_disponiveis:
            st.session_state["filtro_mes"] = current_bar_selection
    
    with f2:
        if meses_disponiveis:
            mes_selecionado = st.selectbox("Mês de Referência", meses_disponiveis, key="filtro_mes")
        else:
            mes_selecionado = None
            st.selectbox("Mês de Referência", ["Nenhum"])
            
    with f3:
        tipos_disponiveis = ["Todas as Transações", "Despesas (Saídas)", "Receitas (Entradas)"]
        tipo_filtro = st.selectbox("Filtrar por", tipos_disponiveis, index=1)
        
    if not mes_selecionado:
        return
        
    df_mes_base = df[df['month'].astype(str) == mes_selecionado]
    
    # Calcular Totais com a base cheia (não afetada pelo filtro da UI)
    despesas_mes = df_mes_base[df_mes_base['is_expense']]['amount_abs'].sum()
    receitas_mes = df_mes_base[~df_mes_base['is_expense']]['amount_abs'].sum()
    
    # Aplicar filtro apenas para visualização da tabela e gráficos seguintes
    if tipo_filtro == "Despesas (Saídas)":
        df_mes = df_mes_base[df_mes_base['is_expense']]
    elif tipo_filtro == "Receitas (Entradas)":
        df_mes = df_mes_base[~df_mes_base['is_expense']]
    else:
        df_mes = df_mes_base
    
    # 4. CARDS
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Gasto (Despesas)", formatar_moeda(despesas_mes), delta="Saída", delta_color="inverse")
    c2.metric("Total Recebido (Entradas)", formatar_moeda(receitas_mes), delta="Entrada")
    c3.metric("Balanço do Mês", formatar_moeda(receitas_mes - despesas_mes))
    
    # 5. GRÁFICOS
    if tipo_filtro == "Receitas (Entradas)":
        titulo_grafico = "Distribuição de Receitas por Categoria"
        msg_vazio = "Nenhuma receita no mês selecionado."
    elif tipo_filtro == "Despesas (Saídas)":
        titulo_grafico = "Distribuição de Gastos por Categoria"
        msg_vazio = "Nenhuma despesa no mês selecionado."
    else:
        titulo_grafico = "Distribuição de Transações (Entradas e Saídas) por Categoria"
        msg_vazio = "Nenhuma transação no mês selecionado."

    st.markdown(f"<div class='sec-hdr'>📊 {titulo_grafico}</div>", unsafe_allow_html=True)
    
    df_chart = df_mes.copy()
    if not df_chart.empty:
        df_cat = df_chart.groupby('final_category')['amount_abs'].sum().reset_index()
        df_cat = df_cat.sort_values('amount_abs', ascending=False)
        
        # Donut Chart - Estilo Premium
        fig = px.pie(df_cat, values='amount_abs', names='final_category', hole=0.6,
                     color_discrete_sequence=px.colors.qualitative.Pastel)
        
        fig.update_traces(textposition='inside', textinfo='percent+label',
                          marker=dict(line=dict(color='#0e1117', width=2)))
        fig.update_layout(
            paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
            font=dict(family='Inter', color='#8b949e', size=12),
            margin=dict(t=20, b=20, l=0, r=0),
            showlegend=True,
            legend=dict(orientation="v", yanchor="top", y=1, xanchor="left", x=1.0)
        )
        
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.write(msg_vazio)
        
    st.markdown("<div class='sec-hdr'>📈 Histórico de Despesas e Receitas (Selecionável)</div>", unsafe_allow_html=True)
    
    df_hist = df.copy()
    df_hist['month_str'] = df_hist['month'].astype(str)
    
    todos_meses = sorted(df_hist['month_str'].unique())
    # Por padrão, pega até os ultimos 6 meses
    default_meses = todos_meses[-6:] if len(todos_meses) >= 6 else todos_meses
    
    meses_hist = st.multiselect("Filtrar Meses para o Gráfico", options=todos_meses, default=default_meses)
    
    if meses_hist:
        df_hist_group = df_hist[df_hist['month_str'].isin(meses_hist)].groupby(['month_str', 'is_expense'])['amount_abs'].sum().reset_index()
        
        fig_hist = go.Figure()
        
        # Despesas
        desp_data = df_hist_group[df_hist_group['is_expense']]
        fig_hist.add_trace(go.Bar(
            x=desp_data['month_str'],
            y=desp_data['amount_abs'],
            name='Despesas',
            marker_color='#ff4b4b',
            text=desp_data['amount_abs'].apply(lambda x: f"R$ {x:,.0f}".replace(",", ".")),
            textposition='auto'
        ))
        
        # Receitas
        rec_data = df_hist_group[~df_hist_group['is_expense']]
        fig_hist.add_trace(go.Bar(
            x=rec_data['month_str'],
            y=rec_data['amount_abs'],
            name='Receitas',
            marker_color='#00d4aa',
            text=rec_data['amount_abs'].apply(lambda x: f"R$ {x:,.0f}".replace(",", ".")),
            textposition='auto'
        ))
        
        fig_hist.update_layout(
            barmode='group',
            paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
            font=dict(family='Inter', color='#8b949e'),
            margin=dict(t=20, b=0, l=0, r=0),
            yaxis=dict(gridcolor='rgba(255,255,255,0.05)', title='Valor (R$)'),
            xaxis=dict(gridcolor='rgba(255,255,255,0.05)', title='', type='category')
        )
        
        event_bar = st.plotly_chart(fig_hist, use_container_width=True, on_select="rerun", key="bar_chart_drilldown")
    else:
        st.write("Nenhum mês selecionado para o histórico.")
    
    # 6. TABELA DE TRANSAÇÕES
    st.markdown("<div class='sec-hdr'>📋 Detalhamento das Transações</div>", unsafe_allow_html=True)
    
    t1, t2 = st.columns([1, 1])
    with t1:
        mostrar_ocultas = st.toggle("Exibir todas as transações brutas (incluindo as ocultadas pelo Filtro Anti-Distorção)", value=False)
    
    if mostrar_ocultas:
        df_table_base = df_raw[df_raw['month'].astype(str) == mes_selecionado]
    else:
        df_table_base = df_mes_base.copy()
        
    if tipo_filtro == "Despesas (Saídas)":
        df_table = df_table_base[df_table_base['is_expense']].copy()
    elif tipo_filtro == "Receitas (Entradas)":
        df_table = df_table_base[~df_table_base['is_expense']].copy()
    else:
        df_table = df_table_base.copy()
        
    categorias_disponiveis = ["Todas as Categorias"] + sorted(df_table['final_category'].dropna().unique().tolist())
    
    with t2:
        cat_filtro = st.selectbox("Filtrar Tabela por Categoria", categorias_disponiveis, key="filtro_categoria")
        
    if cat_filtro != "Todas as Categorias":
        df_table = df_table[df_table['final_category'] == cat_filtro]
    
    # Adicionar nome da conta se existir mapeamento
    df_table['account_name'] = df_table['account_id'].map(lambda x: conta_opcoes.get(x, "Desconhecida").replace("🏦 ", ""))
    
    if df_table.empty:
        st.info("Nenhuma transação para exibir com os filtros atuais.")
    else:
        df_table = df_table[['id', 'date', 'account_name', 'description', 'final_category', 'amount_abs', 'is_expense', 'type']]
        df_table['date'] = df_table['date'].dt.strftime('%d/%m/%Y')
        df_table['amount_fmt'] = df_table.apply(lambda row: ("- " if row['is_expense'] else "+ ") + formatar_moeda(row['amount_abs']), axis=1)
        
        # Prepara o df para edição
        df_edit = df_table[['id', 'date', 'account_name', 'description', 'final_category', 'amount_fmt', 'type']].copy()
        
        edited_df = st.data_editor(
            df_edit,
            column_config={
                'id': None,  # Oculta o ID
                'date': st.column_config.TextColumn('Data', disabled=True),
                'account_name': st.column_config.TextColumn('Conta', disabled=True),
                'description': st.column_config.TextColumn('Descrição', disabled=True),
                'final_category': st.column_config.TextColumn('Categoria (Editável)'),
                'amount_fmt': st.column_config.TextColumn('Valor', disabled=True),
                'type': st.column_config.TextColumn('Tipo', disabled=True)
            },
            hide_index=True,
            use_container_width=True,
            key='editor_txns'
        )
        
        # Identificar mudanças
        if not df_edit.equals(edited_df):
            st.info("Mudanças detectadas. Salvando alterações...")
            mudancas = False
            for i in range(len(df_edit)):
                old_cat = df_edit.iloc[i]['final_category']
                new_cat = edited_df.iloc[i]['final_category']
                if old_cat != new_cat:
                    txn_id = edited_df.iloc[i]['id']
                    res = requests.patch(f"{API_BASE_URL}/transactions/{txn_id}/category", json={"category": new_cat})
                    if res.status_code == 200:
                        mudancas = True
                    else:
                        st.error(f"Erro ao atualizar transação {txn_id}.")
            
            if mudancas:
                st.success("Categorias atualizadas com sucesso!")
                import time
                time.sleep(1.0)
                st.rerun()
    
    st.markdown("<div style='font-size:0.8rem;color:#8b949e;text-align:right'>* Habilite o toggle acima para ver transações bloqueadas pelo filtro.</div>", unsafe_allow_html=True)
