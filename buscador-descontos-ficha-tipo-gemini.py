import streamlit as st
import pandas as pd
import pdfplumber
import re
from datetime import datetime
import io
from typing import List, Dict, Optional

# --- CONFIGURAÇÃO DA PÁGINA (Deve ser a primeira linha) ---
st.set_page_config(
    page_title="Extrator Financeiro SIAPE",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- ESTILIZAÇÃO CSS PERSONALIZADA ---
st.markdown("""
    <style>
    .main {
        background-color: #f8f9fa;
    }
    .stButton>button {
        width: 100%;
        border-radius: 5px;
        height: 3em;
    }
    div[data-testid="stMetricValue"] {
        font-size: 1.8rem;
        color: #0f52ba;
    }
    </style>
""", unsafe_allow_html=True)

# --- CLASSE DE EXTRAÇÃO (Lógica Robusta do Usuário) ---
class ExtratorDemonstrativos:
    """Classe otimizada para extrair dados financeiros com regex robusto para o Ano"""
    
    def __init__(self):
        self.meses_map = {
            'JAN': 1, 'JANEIRO': 1, 'FEV': 2, 'FEVEREIRO': 2,
            'MAR': 3, 'MARÇO': 3, 'ABR': 4, 'ABRIL': 4,
            'MAI': 5, 'MAIO': 5, 'JUN': 6, 'JUNHO': 6,
            'JUL': 7, 'JULHO': 7, 'AGO': 8, 'AGOSTO': 8,
            'SET': 9, 'SETEMBRO': 9, 'OUT': 10, 'OUTUBRO': 10,
            'NOV': 11, 'NOVEMBRO': 11, 'DEZ': 12, 'DEZEMBRO': 12
        }
    
    def formatar_valor_brasileiro(self, valor: float) -> str:
        return f"{valor:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
    
    def converter_valor_string(self, valor_str: str) -> Optional[float]:
        try:
            # Limpa sujeira e padroniza para float python
            valor_limpo = re.sub(r'[^\d,\.]', '', str(valor_str))
            if not valor_limpo: return 0.0
            
            # Lógica para detectar se o ponto é milhar ou decimal
            if ',' in valor_limpo:
                # Padrão Brasileiro (1.000,00)
                valor_final = valor_limpo.replace('.', '').replace(',', '.')
            else:
                valor_final = valor_limpo
                
            return float(valor_final)
        except:
            return 0.0
    
    def extrair_ano_referencia_robusto(self, texto: str) -> Optional[str]:
        """Lógica 'Hardcore' para achar o ano ignorando quebras de linha"""
        if not texto: return None
        
        # 1. Achata o texto para ignorar quebras de linha (A mágica acontece aqui)
        texto_flat = texto.replace('\n', ' ').replace('\r', ' ')
        
        # 2. Busca exata por ANO REFERENCIA + dígitos
        match = re.search(r'ANO\s*REFER[ÊE]NCIA.*?(\d{4})', texto_flat, re.IGNORECASE)
        
        if match:
            ano = match.group(1)
            # Validação básica para não pegar ano absurdo (ex: 1900 ou 2100)
            ano_int = int(ano)
            if 2000 <= ano_int <= datetime.now().year + 5:
                return ano
        
        return None # Retorna None se não achar com certeza absoluta

    def processar_pdf(self, pdf_file, extrair_proventos=True, extrair_descontos=True) -> pd.DataFrame:
        dados = []
        
        with pdfplumber.open(pdf_file) as pdf:
            total_paginas = len(pdf.pages)
            
            # Barra de progresso na interface
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            for i, page in enumerate(pdf.pages):
                # Atualiza progresso visualmente
                progress = (i + 1) / total_paginas
                progress_bar.progress(progress)
                status_text.text(f"Lendo página {i+1} de {total_paginas}...")
                
                texto = page.extract_text()
                if not texto: continue
                
                # BUSCA DO ANO
                ano = self.extrair_ano_referencia_robusto(texto)
                if not ano:
                    ano = f"DESCONHECIDO (Pág {i+1})"
                
                tabelas = page.extract_tables()
                
                for tabela in tabelas:
                    if not tabela: continue
                    
                    df_tab = pd.DataFrame(tabela).dropna(how='all')
                    
                    # Identificar linha de cabeçalho dos meses
                    header_idx = -1
                    mapa_colunas_meses = {} # {idx_coluna: numero_mes}
                    
                    for idx, row in df_tab.iterrows():
                        row_str = " ".join([str(c) for c in row if c]).upper()
                        
                        # Verifica se a linha tem JAN, FEV, etc
                        meses_nesta_linha = {}
                        for col_idx, cell in enumerate(row):
                            cell_clean = str(cell).strip().upper()[:3] # Pega 3 primeiras letras
                            if cell_clean in self.meses_map:
                                meses_nesta_linha[col_idx] = self.meses_map[cell_clean]
                        
                        if len(meses_nesta_linha) > 0 and "DISCRIMINA" in row_str:
                            header_idx = idx
                            mapa_colunas_meses = meses_nesta_linha
                            break
                    
                    if header_idx == -1 or not mapa_colunas_meses:
                        continue
                        
                    # Processar dados abaixo do cabeçalho
                    # Detectar contexto (Rendimentos ou Descontos)
                    contexto_atual = "DESCONHECIDO"
                    
                    for idx in range(header_idx + 1, len(df_tab)):
                        linha = df_tab.iloc[idx]
                        linha_texto = " ".join([str(c) for c in linha if c]).upper()
                        
                        # Detectar mudança de seção
                        if "RENDIMENTOS" in linha_texto:
                            contexto_atual = "RENDIMENTOS"
                            continue
                        elif "DESCONTOS" in linha_texto:
                            contexto_atual = "DESCONTOS"
                            continue
                        elif "TOTAL" in linha_texto or "LÍQUIDO" in linha_texto:
                            continue
                        
                        # Filtrar pelo que o usuário pediu
                        if contexto_atual == "RENDIMENTOS" and not extrair_proventos: continue
                        if contexto_atual == "DESCONTOS" and not extrair_descontos: continue
                        if contexto_atual == "DESCONHECIDO": 
                            # Tenta adivinhar pelo conteúdo anterior ou assume geral
                            if "EMPREST" in linha_texto: contexto_atual = "DESCONTOS"
                        
                        # Extrair Rubrica (Geralmente a coluna 1 ou a que tem texto longo)
                        rubrica = None
                        for cell in linha:
                            c_str = str(cell).strip()
                            # Rubrica não é número, nem data, nem vazio
                            if c_str and not re.match(r'^[\d\.,]+$', c_str) and len(c_str) > 3:
                                rubrica = c_str
                                break
                        
                        if not rubrica or rubrica in ["RENDIMENTOS", "DESCONTOS"]:
                            continue
                            
                        # Extrair Valores dos Meses mapeados
                        for col_idx, mes_num in mapa_colunas_meses.items():
                            if col_idx < len(linha):
                                valor_bruto = linha[col_idx]
                                valor_float = self.converter_valor_string(valor_bruto)
                                
                                if valor_float > 0:
                                    dados.append({
                                        'COMPETENCIA': f"{mes_num:02d}/{ano}",
                                        'ANO_REF': ano,
                                        'MES': mes_num,
                                        'TIPO': contexto_atual,
                                        'RUBRICA': rubrica,
                                        'VALOR': valor_float,
                                        'VALOR_FMT': self.formatar_valor_brasileiro(valor_float)
                                    })
            
            # Limpa UI
            status_text.empty()
            progress_bar.empty()
            
            if dados:
                return pd.DataFrame(dados)
            return pd.DataFrame()

# --- FUNÇÃO PRINCIPAL COM SESSION STATE ---
def main():
    
    # --- BARRA LATERAL (Inputs e Controles) ---
    with st.sidebar:
        st.header("📂 Configuração")
        
        uploaded_file = st.file_uploader("Carregar PDF", type=["pdf"])
        
        st.divider()
        st.subheader("O que extrair?")
        opt_proventos = st.checkbox("Rendimentos", value=True)
        opt_descontos = st.checkbox("Descontos", value=True)
        
        # Botão de Reset
        if st.button("🔄 Limpar Tudo"):
            st.session_state.clear()
            st.rerun()

    # --- ÁREA PRINCIPAL ---
    st.title("📊 Análise de Fichas Financeiras")
    st.markdown("Extração automática de competências e valores do SIAPE.")

    # Verifica se há arquivo novo para limpar o estado anterior
    if uploaded_file:
        # Se mudou o arquivo, reseta o processamento
        if 'last_file' not in st.session_state or st.session_state['last_file'] != uploaded_file.name:
            st.session_state['df_financeiro'] = None
            st.session_state['last_file'] = uploaded_file.name

        # Botão de Processamento (Só aparece se ainda não processou)
        if 'df_financeiro' not in st.session_state or st.session_state['df_financeiro'] is None:
            st.info("Arquivo carregado. Clique abaixo para iniciar a leitura.")
            
            if st.button("🚀 Processar Arquivo", type="primary"):
                extrator = ExtratorDemonstrativos()
                
                with st.spinner("Lendo PDF e identificando anos..."):
                    try:
                        df_resultado = extrator.processar_pdf(uploaded_file, opt_proventos, opt_descontos)
                        
                        if not df_resultado.empty:
                            # Ordenação Cronológica
                            df_resultado = df_resultado.sort_values(by=['ANO_REF', 'MES', 'TIPO', 'RUBRICA'])
                            st.session_state['df_financeiro'] = df_resultado
                            st.toast("Processamento concluído com sucesso!", icon="✅")
                            st.rerun() # Recarrega a página para mostrar o dashboard
                        else:
                            st.error("Nenhum dado financeiro encontrado. Verifique se o PDF é selecionável.")
                    except Exception as e:
                        st.error(f"Erro ao processar: {e}")

        # --- DASHBOARD (Só aparece se o DF estiver na memória) ---
        if 'df_financeiro' in st.session_state and st.session_state['df_financeiro'] is not None:
            df = st.session_state['df_financeiro']
            
            # --- FILTROS (Sem reprocessar o PDF!) ---
            with st.container():
                c1, c2, c3 = st.columns(3)
                
                anos_disp = sorted(df['ANO_REF'].unique())
                filtro_anos = c1.multiselect("Filtrar Ano", anos_disp, default=anos_disp)
                
                tipos_disp = sorted(df['TIPO'].unique())
                filtro_tipos = c2.multiselect("Filtrar Tipo", tipos_disp, default=tipos_disp)
                
                # Rubricas filtradas pelo que já foi selecionado acima
                df_temp = df[df['ANO_REF'].isin(filtro_anos) & df['TIPO'].isin(filtro_tipos)]
                rubricas_disp = sorted(df_temp['RUBRICA'].unique())
                filtro_rubricas = c3.multiselect("Filtrar Rubricas", rubricas_disp, default=rubricas_disp)
            
            # Aplicação dos Filtros
            df_view = df[
                (df['ANO_REF'].isin(filtro_anos)) &
                (df['TIPO'].isin(filtro_tipos)) &
                (df['RUBRICA'].isin(filtro_rubricas))
            ]
            
            st.divider()
            
            # --- KPIs (Indicadores) ---
            if not df_view.empty:
                k1, k2, k3, k4 = st.columns(4)
                
                total_valor = df_view['VALOR'].sum()
                contagem = len(df_view)
                media = df_view['VALOR'].mean()
                meses_count = df_view['COMPETENCIA'].nunique()
                
                k1.metric("Valor Total Selecionado", f"R$ {total_valor:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'))
                k2.metric("Lançamentos", contagem)
                k3.metric("Média por Lançamento", f"R$ {media:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'))
                k4.metric("Competências", meses_count)
                
                # --- ABAS DE VISUALIZAÇÃO ---
                tab_dados, tab_grafico, tab_export = st.tabs(["📋 Tabela Detalhada", "📈 Análise Visual", "💾 Exportar"])
                
                with tab_dados:
                    # Configuração da Tabela para exibição bonita
                    st.dataframe(
                        df_view[['COMPETENCIA', 'TIPO', 'RUBRICA', 'VALOR']],
                        use_container_width=True,
                        column_config={
                            "VALOR": st.column_config.NumberColumn(
                                "Valor (R$)",
                                format="R$ %.2f"
                            )
                        },
                        height=500
                    )
                
                with tab_grafico:
                    if len(df_view) > 0:
                        st.caption("Evolução dos valores selecionados por competência")
                        chart_data = df_view.groupby(['COMPETENCIA', 'TIPO'])['VALOR'].sum().reset_index()
                        st.bar_chart(chart_data, x="COMPETENCIA", y="VALOR", color="TIPO", stack=False)
                    else:
                        st.info("Sem dados para gráfico.")

                with tab_export:
                    st.subheader("Baixar Resultados")
                    col_d1, col_d2 = st.columns(2)
                    
                    # CSV
                    csv = df_view.to_csv(index=False, sep=';', decimal=',').encode('utf-8-sig')
                    col_d1.download_button(
                        label="📄 Download CSV (Excel)",
                        data=csv,
                        file_name="extracao_siape.csv",
                        mime="text/csv",
                        use_container_width=True
                    )
                    
                    # Excel
                    buffer = io.BytesIO()
                    with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                        df_view.to_excel(writer, sheet_name='Dados', index=False)
                    
                    col_d2.download_button(
                        label="📊 Download Planilha (.xlsx)",
                        data=buffer.getvalue(),
                        file_name="extracao_siape.xlsx",
                        mime="application/vnd.ms-excel",
                        use_container_width=True
                    )
            else:
                st.warning("Nenhum dado corresponde aos filtros selecionados.")

    else:
        # TELA INICIAL (Sem arquivo)
        st.markdown("---")
        st.markdown("""
        ### Como usar:
        1. Abra a barra lateral (**<** no topo esquerdo).
        2. Arraste seu PDF de fichas financeiras.
        3. Clique em **Processar Arquivo**.
        4. O sistema identificará automaticamente os anos (2020, 2021...) e gerará as competências.
        """)

if __name__ == "__main__":
    main()
