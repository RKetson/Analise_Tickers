import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import src.portfolio as pt
from src.data_loader import carregar_dados_empresa, carregar_base_json, DATA_DIR
from src.formatters import formatar_moeda
import json
import os

def render_carteira_tab(tipo: str):
    hide_vals = st.session_state.get('hide_vals_carteira', False)
    
    port = pt.load_portfolio()
    dados_tipo = port.get(tipo, {})
    posicoes = dados_tipo.get('posicoes', {})
    simulacoes = dados_tipo.get('simulacoes', {})
    metas = dados_tipo.get('metas_setor', {})
    
    st.markdown(f"### Gerenciamento de {tipo.capitalize()}")


    # --- Preços e Setores ---
    # Carregar preços atuais para todas as posições e simulações
    tickers = set(posicoes.keys()).union(set(simulacoes.keys()))
    precos = {}
    setores = {}
    base_json = carregar_base_json()
    
    if tickers:
        with st.spinner("Atualizando cotações..."):
            for tk in tickers:
                res = carregar_dados_empresa(tk)
                p_atual = res.get('dados', {}).get('preco_atual')
                if p_atual:
                    precos[tk] = float(p_atual)
                else:
                    precos[tk] = 0.0
                
                setor = res.get('empresa_config', {}).get('setor', 'Outros')
                if not setor or str(setor).strip() == '':
                    setor = 'Outros'
                setores[tk] = str(setor).replace('_', ' ').title()
    
    # Permitir cadastro de setor caso seja Outros (muito comum em FIIs)
    tickers_outros = [tk for tk, sec in setores.items() if sec == 'Outros']
    if tickers_outros:
        st.warning(f"Alguns ativos estão sem setor definido: {', '.join(tickers_outros)}")
        with st.expander("Definir Setores Manualmente"):
            for tk in tickers_outros:
                novo_setor = st.text_input(f"Setor para {tk}", key=f"setor_{tipo}_{tk}")
                if st.button(f"Salvar Setor {tk}", key=f"btn_setor_{tipo}_{tk}"):
                    # Atualiza no companies.json
                    emp = base_json.get(tk, {})
                    emp['setor'] = novo_setor
                    base_json[tk] = emp
                    with open(os.path.join(DATA_DIR, 'companies.json'), 'w', encoding='utf-8') as f:
                        json.dump(base_json, f, ensure_ascii=False, indent=2)
                    st.rerun()

    # --- Adicionar Posições / Simulações ---
    with st.expander("➕ Adicionar Posição Real ou Simulação"):
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            novo_tk = st.text_input("Ticker", key=f"add_tk_{tipo}").upper()
        with c2:
            nova_quant = st.number_input("Quantidade (Cotas/Ações)", value=0, key=f"add_q_{tipo}")
        with c3:
            modo = st.selectbox("Modo", ["Adicionar à Carteira Real", "Simular Aporte/Venda"], key=f"modo_{tipo}")
        with c4:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("Adicionar", key=f"btn_add_{tipo}", use_container_width=True):
                if novo_tk and nova_quant != 0:
                    if modo == "Adicionar à Carteira Real":
                        pt.add_position(tipo, novo_tk, nova_quant)
                        st.success(f"{nova_quant} {novo_tk} adicionados à carteira!")
                    else:
                        # Se simulado, calcular valor estimado se o preco for conhecido
                        p_est = precos.get(novo_tk, 0.0)
                        if p_est == 0.0:
                            # tenta buscar rapido
                            res = carregar_dados_empresa(novo_tk)
                            p_est = float(res.get('dados', {}).get('preco_atual') or 0.0)
                        
                        val_est = nova_quant * p_est
                        pt.add_simulacao(tipo, novo_tk, nova_quant, val_est)
                        st.success(f"Simulação de {nova_quant} {novo_tk} criada!")
                    st.rerun()

    # --- Consolidar Carteira Atual e Simulada ---
    patrimonio_atual = 0.0
    patrimonio_simulado = 0.0
    
    agregado = {} # Por Setor
    
    for tk, pos in posicoes.items():
        q = pos['quantidade']
        p = precos.get(tk, 0.0)
        v = q * p
        s = setores.get(tk, 'Outros')
        
        if s not in agregado:
            agregado[s] = {'atual': 0.0, 'simulado_adicional': 0.0}
        agregado[s]['atual'] += v
        patrimonio_atual += v

    for tk, sim in simulacoes.items():
        q = sim['quantidade']
        p = precos.get(tk, 0.0)
        v = q * p
        s = setores.get(tk, 'Outros')
        
        if s not in agregado:
            agregado[s] = {'atual': 0.0, 'simulado_adicional': 0.0}
        agregado[s]['simulado_adicional'] += v
        patrimonio_simulado += v

    patrimonio_futuro = patrimonio_atual + patrimonio_simulado

    # Mostrar métricas gerais
    m1, m2, m3 = st.columns(3)
    
    def fmt_val(v):
        return "R$ ✱✱✱,✱✱" if hide_vals else formatar_moeda(v)
        
    m1.metric("Patrimônio Atual", fmt_val(patrimonio_atual))
    
    delta_sim = "" if hide_vals else f"{patrimonio_simulado:+.2f}"
    m2.metric("Valor Simulado (Aporte/Venda)", fmt_val(patrimonio_simulado), delta=delta_sim)
    
    m3.metric("Patrimônio Futuro", fmt_val(patrimonio_futuro))

    st.markdown("---")

    # --- Tabela de Metas e GAPs ---
    st.markdown("### Consolidação por Setor e Metas")
    
    rows = []
    # Garantir que setores configurados nas metas mas sem ativos apareçam
    todos_setores = set(agregado.keys()).union(set(metas.keys()))
    
    for s in todos_setores:
        v_atual = agregado.get(s, {}).get('atual', 0.0)
        v_sim_add = agregado.get(s, {}).get('simulado_adicional', 0.0)
        v_futuro = v_atual + v_sim_add
        
        pct_atual = (v_atual / patrimonio_atual) if patrimonio_atual > 0 else 0.0
        pct_futuro = (v_futuro / patrimonio_futuro) if patrimonio_futuro > 0 else 0.0
        
        meta_obj = metas.get(s, {'meta': 0.0, 'observacao': '', 'margem_gap': 0.05})
        meta_pct = meta_obj.get('meta', 0.0)
        margem_pct = meta_obj.get('margem_gap', 0.05)
        obs = meta_obj.get('observacao', '')
        
        gap_atual = pct_atual - meta_pct
        gap_futuro = pct_futuro - meta_pct
        
        aporte_ideal = (patrimonio_futuro * meta_pct) - v_atual
        if patrimonio_futuro == 0 and patrimonio_atual > 0:
             aporte_ideal = (patrimonio_atual * meta_pct) - v_atual

        rows.append({
            'Setor': s,
            '% Meta': meta_pct,
            '% Margem GAP': margem_pct,
            'Observação': obs,
            '% Parcela Atual': pct_atual,
            '% GAP Atual': gap_atual,
            '% Parcela Futura': pct_futuro,
            '% GAP Futuro': gap_futuro,
            'Valor Atual': v_atual,
            'Aporte/Venda Simulado': v_sim_add,
            'Aporte Ideal p/ Meta': aporte_ideal
        })

    df = pd.DataFrame(rows)
    
    if not df.empty:
        # Interface para editar Metas e Observações
        st.markdown("<span style='font-size:12px;color:#8b949e'>Edite as colunas '% Meta', '% Margem GAP' e 'Observação' diretamente na tabela abaixo e aperte Enter. A soma das metas deve dar 100% (1.0).</span>", unsafe_allow_html=True)
        
        df_edit = df[['Setor', '% Meta', '% Margem GAP', 'Observação']].copy()
        df_edit['% Meta'] = df_edit['% Meta'] * 100 # Exibir como %
        df_edit['% Margem GAP'] = df_edit['% Margem GAP'] * 100 # Exibir como %
        
        edited_df = st.data_editor(
            df_edit,
            column_config={
                "% Meta": st.column_config.NumberColumn(
                    "% Meta",
                    help="Meta em percentual (0 a 100)",
                    min_value=0.0,
                    max_value=100.0,
                    step=1.0,
                    format="%.2f%%"
                ),
                "% Margem GAP": st.column_config.NumberColumn(
                    "% Margem GAP",
                    help="Margem de GAP tolerável (0 a 100)",
                    min_value=0.0,
                    max_value=100.0,
                    step=0.5,
                    format="%.2f%%"
                ),
            },
            disabled=["Setor"],
            hide_index=True,
            use_container_width=True,
            key=f"editor_metas_{tipo}"
        )
        
        # Salvar alterações nas metas
        novas_metas = {}
        soma_metas = 0.0
        mudou = False
        for _, row in edited_df.iterrows():
            s = row['Setor']
            m = row['% Meta'] / 100.0
            mgap = row['% Margem GAP'] / 100.0
            o = row['Observação']
            novas_metas[s] = {'meta': m, 'margem_gap': mgap, 'observacao': o}
            soma_metas += m
            
            old_m = metas.get(s, {}).get('meta', 0.0)
            old_mgap = metas.get(s, {}).get('margem_gap', 0.05)
            old_o = metas.get(s, {}).get('observacao', '')
            if m != old_m or mgap != old_mgap or o != old_o:
                mudou = True
                
        if mudou:
            pt.update_metas_setor(tipo, novas_metas)
            st.rerun()
            
        if abs(soma_metas - 1.0) > 0.001 and soma_metas > 0:
            st.warning(f"A soma das metas está em {soma_metas*100:.1f}%. O ideal é 100%.")

        # Exibir a tabela consolidada apenas para visualização com GAPs
        st.markdown("##### Resultados da Consolidação")
        
        def color_gap_row(row):
            styles = [''] * len(row)
            # Pega a margem específica do setor da linha
            margem_gap = metas.get(row['Setor'], {}).get('margem_gap', 0.05)
            
            for i, col in enumerate(row.index):
                if col in ['% GAP Atual', '% GAP Futuro']:
                    val = row[col]
                    if abs(val) <= margem_gap:
                        styles[i] = 'background-color: rgba(0,212,170,0.2); color: #00d4aa'
                    elif val > margem_gap:
                        styles[i] = 'background-color: rgba(255,159,67,0.2); color: #ff9f43'
                    else:
                        styles[i] = 'background-color: rgba(255,71,87,0.2); color: #ff4757'
            return styles
                
        df_display = df[['Setor', '% Parcela Atual', '% GAP Atual', '% Parcela Futura', '% GAP Futuro', 'Valor Atual', 'Aporte/Venda Simulado', 'Aporte Ideal p/ Meta']].copy()
        
        format_dict = {
            '% Parcela Atual': '{:.2%}',
            '% GAP Atual': '{:+.2%}',
            '% Parcela Futura': '{:.2%}',
            '% GAP Futuro': '{:+.2%}',
        }
        
        if hide_vals:
            format_dict['Valor Atual'] = lambda _: 'R$ ✱✱✱,✱✱'
            format_dict['Aporte/Venda Simulado'] = lambda _: 'R$ ✱✱✱,✱✱'
            format_dict['Aporte Ideal p/ Meta'] = lambda _: 'R$ ✱✱✱,✱✱'
        else:
            format_dict['Valor Atual'] = 'R$ {:,.2f}'
            format_dict['Aporte/Venda Simulado'] = 'R$ {:,.2f}'
            format_dict['Aporte Ideal p/ Meta'] = 'R$ {:,.2f}'
        
        styled_df = df_display.style.format(format_dict).apply(color_gap_row, axis=1)
        
        st.dataframe(styled_df, use_container_width=True, hide_index=True)

        # --- Gráficos ---
        st.markdown("### Visualizações")
        cg1, cg2, cg3 = st.columns(3)
        
        # Cores
        colors = ['#00d4aa', '#4fc3f7', '#ffd700', '#ff9f43', '#ff4757', '#a55eea', '#fd9644', '#2bcbba', '#45aaf2']
        
        with cg1:
            # Grafico Meta
            fig1 = go.Figure(data=[go.Pie(labels=df['Setor'], values=df['% Meta'], hole=.4, marker_colors=colors)])
            fig1.update_layout(title="Distribuição Meta", paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color='#e6edf3'), margin=dict(t=40, b=0, l=0, r=0))
            st.plotly_chart(fig1, use_container_width=True)
            
        with cg2:
            # Grafico Atual
            fig2 = go.Figure(data=[go.Pie(labels=df['Setor'], values=df['Valor Atual'], hole=.4, marker_colors=colors)])
            fig2.update_traces(hoverinfo='label+percent' if hide_vals else 'label+percent+value', textinfo='percent')
            fig2.update_layout(title="Distribuição Atual", paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color='#e6edf3'), margin=dict(t=40, b=0, l=0, r=0))
            st.plotly_chart(fig2, use_container_width=True)
            
        with cg3:
            # Grafico Futuro (Pós Simulação)
            v_futuros = [max(0, row['Valor Atual'] + row['Aporte/Venda Simulado']) for _, row in df.iterrows()]
            fig3 = go.Figure(data=[go.Pie(labels=df['Setor'], values=v_futuros, hole=.4, marker_colors=colors)])
            fig3.update_traces(hoverinfo='label+percent' if hide_vals else 'label+percent+value', textinfo='percent')
            fig3.update_layout(title="Distribuição Pós-Simulação", paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color='#e6edf3'), margin=dict(t=40, b=0, l=0, r=0))
            st.plotly_chart(fig3, use_container_width=True)
            
        # Grafico Barras Comparativo
        fig_bar = go.Figure()
        fig_bar.add_trace(go.Bar(x=df['Setor'], y=df['% Meta']*100, name='Meta', marker_color='#4fc3f7'))
        fig_bar.add_trace(go.Bar(x=df['Setor'], y=df['% Parcela Atual']*100, name='Real Atual', marker_color='#00d4aa'))
        fig_bar.add_trace(go.Bar(x=df['Setor'], y=df['% Parcela Futura']*100, name='Pós Simulação', marker_color='#ffd700'))
        
        fig_bar.update_layout(
            title="Comparativo: Meta vs Real vs Futuro (%)",
            barmode='group',
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            font=dict(color='#e6edf3'),
            yaxis=dict(ticksuffix="%")
        )
        st.plotly_chart(fig_bar, use_container_width=True)
        
        # Treemap Opcional
        fig_tree = go.Figure(go.Treemap(
            labels=df['Setor'],
            parents=[""] * len(df),
            values=df['Valor Atual'],
            textinfo="label+percent root" if hide_vals else "label+value+percent root",
            hoverinfo="label+percent root" if hide_vals else "label+value+percent root"
        ))
        fig_tree.update_layout(title="Treemap de Alocação Atual", margin=dict(t=30, l=0, r=0, b=0), paper_bgcolor='rgba(0,0,0,0)')
        st.plotly_chart(fig_tree, use_container_width=True)


    # --- Lista de Simulações Pendentes ---
    if simulacoes:
        st.markdown("---")
        st.markdown("### 🛒 Simulações Pendentes")
        
        for tk, sim in simulacoes.items():
            cc1, cc2, cc3 = st.columns([2, 1, 1])
            with cc1:
                v_est = "R$ ✱✱✱,✱✱" if hide_vals else formatar_moeda(sim['valor_estimado'])
                st.markdown(f"**{tk}**: {sim['quantidade']:+} cotas (Aprox. {v_est})")
            with cc2:
                if st.button("✅ Efetivar", key=f"efet_{tipo}_{tk}", use_container_width=True):
                    pt.efetivar_simulacao(tipo, tk)
                    st.rerun()
            with cc3:
                if st.button("🗑️ Excluir", key=f"del_sim_{tipo}_{tk}", use_container_width=True):
                    pt.remove_simulacao(tipo, tk)
                    st.rerun()

def render_edicao_posicoes():
    st.markdown("### ✏️ Edição Rápida de Posições")
    st.markdown("Edite as quantidades diretamente na tabela. Para remover, digite 0. Para adicionar novos ativos, você pode adicionar uma nova linha no final da tabela (quando aplicável). Você também pode editar o Setor diretamente por aqui.")
    
    port = pt.load_portfolio()
    base_json = carregar_base_json()
    
    c1, c2 = st.columns(2)
    
    # Função auxiliar para renderizar e salvar
    def render_editor(tipo, col_obj):
        with col_obj:
            st.markdown(f"**{tipo.capitalize()}**")
            posicoes = port.get(tipo, {}).get('posicoes', {})
            
            rows = []
            for tk, val in posicoes.items():
                s = base_json.get(tk, {}).get('setor', 'Outros')
                rows.append({'Ticker': tk, 'Quantidade': val['quantidade'], 'Setor': s})
                
            df = pd.DataFrame(rows)
            if df.empty:
                df = pd.DataFrame(columns=['Ticker', 'Quantidade', 'Setor'])
                
            edited_df = st.data_editor(
                df,
                num_rows="dynamic",
                key=f"editor_pos_{tipo}",
                use_container_width=True,
                column_config={
                    "Ticker": st.column_config.TextColumn("Ticker", required=True),
                    "Quantidade": st.column_config.NumberColumn("Quantidade", required=True, min_value=0.0),
                    "Setor": st.column_config.TextColumn("Setor", help="Setor de atuação. Se vazio, será 'Outros'")
                }
            )
            
            # Verificar se houve mudança e salvar
            if st.button(f"Salvar {tipo.capitalize()}", key=f"save_pos_{tipo}", use_container_width=True):
                novas_posicoes = {}
                mudou_setor = False
                for _, row in edited_df.iterrows():
                    tk = str(row['Ticker']).strip().upper()
                    try:
                        quant = float(row['Quantidade'])
                    except:
                        quant = 0.0
                    setor = str(row.get('Setor', '')).strip()
                    
                    if tk and quant > 0:
                        novas_posicoes[tk] = {'quantidade': quant}
                        if tk not in base_json:
                            base_json[tk] = {}
                        if setor and base_json[tk].get('setor') != setor:
                            base_json[tk]['setor'] = setor
                            mudou_setor = True
                        
                port[tipo]['posicoes'] = novas_posicoes
                pt.save_portfolio(port)
                
                if mudou_setor:
                    with open(os.path.join(DATA_DIR, 'companies.json'), 'w', encoding='utf-8') as f:
                        json.dump(base_json, f, ensure_ascii=False, indent=2)
                        
                st.success(f"{tipo.capitalize()} atualizados!")
                st.rerun()

    render_editor('acoes', c1)
    render_editor('fiis', c2)

def render_resumo_aportes():
    hide_vals = st.session_state.get('hide_vals_carteira', False)
    port = pt.load_portfolio()
    
    sim_acoes = port.get('acoes', {}).get('simulacoes', {})
    sim_fiis = port.get('fiis', {}).get('simulacoes', {})
    
    val_acoes = sum(s.get('valor_estimado', 0.0) for s in sim_acoes.values())
    val_fiis = sum(s.get('valor_estimado', 0.0) for s in sim_fiis.values())
    total_geral = val_acoes + val_fiis
    
    st.markdown("### 🛒 Resumo de Aportes Planejados")
    
    if total_geral == 0 and not sim_acoes and not sim_fiis:
        st.info("Você não possui nenhuma simulação de aporte ou venda no momento.")
        return
        
    def fmt_val(v):
        return "R$ ✱✱✱,✱✱" if hide_vals else formatar_moeda(v)
        
    c1, c2, c3 = st.columns(3)
    c1.metric("Aportes em Ações", fmt_val(val_acoes))
    c2.metric("Aportes em FIIs", fmt_val(val_fiis))
    c3.metric("Total Geral de Aportes", fmt_val(total_geral))
    
    st.markdown("---")
    
    # Prepara Tabela
    rows = []
    for tk, s in sim_acoes.items():
        rows.append({'Ticker': tk, 'Classe': 'Ações', 'Quantidade': s['quantidade'], 'Valor': s.get('valor_estimado', 0.0)})
    for tk, s in sim_fiis.items():
        rows.append({'Ticker': tk, 'Classe': 'FIIs', 'Quantidade': s['quantidade'], 'Valor': s.get('valor_estimado', 0.0)})
        
    df = pd.DataFrame(rows)
    
    c_graf, c_tab = st.columns([1, 1])
    
    with c_graf:
        st.markdown("##### Distribuição por Classe")
        if total_geral != 0:
            # Pega valor absoluto pra plotar no gráfico se tiver venda
            v_acoes_abs = abs(val_acoes)
            v_fiis_abs = abs(val_fiis)
            
            fig_pizza = go.Figure(data=[go.Pie(
                labels=["Ações", "FIIs"],
                values=[v_acoes_abs, v_fiis_abs],
                hole=.4,
                marker_colors=['#00d4aa', '#a55eea']
            )])
            fig_pizza.update_traces(hoverinfo='label+percent' if hide_vals else 'label+percent+value', textinfo='percent')
            fig_pizza.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color='#e6edf3'), margin=dict(t=0, b=0, l=0, r=0))
            st.plotly_chart(fig_pizza, use_container_width=True)
        else:
            st.warning("O saldo total planejado é R$ 0,00 (Vendas anulam as Compras)")
            
    with c_tab:
        st.markdown("##### Detalhamento de Movimentações")
        format_dict = {'Valor': lambda _: 'R$ ✱✱✱,✱✱'} if hide_vals else {'Valor': 'R$ {:,.2f}'}
        st.dataframe(df.style.format(format_dict), use_container_width=True, hide_index=True)

def page_carteira():
    c_title, c_toggle = st.columns([4, 1])
    with c_title:
        st.markdown('''
        <div class='app-hdr' style='margin-bottom: 0; padding-bottom: 0; border-bottom: none;'>
            <div class='app-title'>💼 Minha Carteira</div>
            <div class='app-sub'>Consolidação de Ações e FIIs · Simulação de Aportes · Metas de Alocação</div>
        </div>''', unsafe_allow_html=True)
    with c_toggle:
        st.markdown("<br>", unsafe_allow_html=True)
        st.toggle("👁️ Ocultar R$", key="hide_vals_carteira")
        
    st.markdown("<hr style='border-color:rgba(255,255,255,0.07); margin-top: 10px'>", unsafe_allow_html=True)
    
    t1, t2, t3, t4 = st.tabs(["📈 Ações", "🏢 FIIs", "✏️ Editar Posições", "🛒 Resumo de Aportes"])
    
    with t1:
        render_carteira_tab('acoes')
    with t2:
        render_carteira_tab('fiis')
    with t3:
        render_edicao_posicoes()
    with t4:
        render_resumo_aportes()
