import streamlit as st
import pdfplumber
import pandas as pd
import re

# --- Configurações Iniciais ---
def setup_page():
    st.set_page_config(
        page_title="Extrator Financeiro SIAPE",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    st.title("📊 Extrator SIAPE - Análise por Competência")
    st.markdown("""
        **Instruções:**
        1. Faça upload do PDF contendo as Fichas Financeiras.
        2. O sistema detectará automaticamente o **Ano de Referência** e transformará a tabela.
        3. Use os filtros laterais para selecionar Rubricas, Tipos e Competências específicas.
    """)

# --- Constantes e Mapas ---
MAPA_MESES = {
    'JAN': '01', 'JANEIRO': '01',
    'FEV': '02', 'FEVEREIRO': '02',
    'MAR': '03', 'MARÇO': '03',
    'ABR': '04', 'ABRIL': '04',
    'MAI': '05', 'MAIO': '05',
    'JUN': '06', 'JUNHO': '06',
    'JUL': '07', 'JULHO': '07',
    'AGO': '08', 'AGOSTO': '08',
    'SET': '09', 'SETEMBRO': '09',
    'OUT': '10', 'OUTUBRO': '10',
    'NOV': '11', 'NOVEMBRO': '11',
    'DEZ': '12', 'DEZEMBRO': '12'
}

# --- Funções Auxiliares ---
def limpar_valor_monetario(valor):
    """Converte strings financeiras (ex: '1.200,50') para float (1200.50)."""
    if pd.isna(valor) or str(valor).strip() == '':
        return 0.0
    # Remove pontos de milhar e troca vírgula decimal por ponto
    v = str(valor).replace('.', '').replace(',', '.')
    try:
        return float(v)
    except ValueError:
        return 0.0

def extrair_ano_robusto(page_text):
    """
    Busca o ano de referência ignorando quebras de linha.
    Procura por 'ANO REFERENCIA' seguido de 4 dígitos.
    """
    # Remove quebras de linha para tratar o texto como fluxo contínuo
    text_flat = page_text.replace('\n', ' ').replace('\r', ' ')
    
    # Regex que busca 'ANO REFERENCIA' + caracteres opcionais + 4 dígitos
    match = re.search(r'ANO REFER[ÊE]NCIA.*?(\d{4})', text_flat, re.IGNORECASE)
    
    if match:
        return match.group(1)
    return None

def processar_pdf(file):
    """Lê o PDF e transforma as tabelas horizontais em formato de banco de dados (Competência/Valor)."""
    dados_consolidados = []
    
    with pdfplumber.open(file) as pdf:
        for page_num, page in enumerate(pdf.pages):
            text = page.extract_text()
            if not text: 
                continue
            
            # 1. Identificar o Ano da Página
            ano = extrair_ano_robusto(text)
            if not ano:
                # Se falhar, tenta achar no topo da página um ano isolado ou marca como INDEFINIDO
                ano = f"INDEFINIDO_PAG_{page_num+1}"

            # 2. Extrair Tabelas da Página
            tables = page.extract_tables()
            
            for table in tables:
                df = pd.DataFrame(table)
                
                # Limpeza básica de linhas vazias
                df = df.dropna(how='all')
                if df.shape[1] < 2: 
                    continue
                
                # 3. Localizar o Cabeçalho (Linha que contém 'DISCRIMINAÇÃO' ou similar)
                header_idx = -1
                for idx, row in df.iterrows():
                    row_str = " ".join([str(x) for x in row]).upper()
                    if "DISCRIMINA" in row_str:
                        header_idx = idx
                        break
                
                if header_idx == -1: 
                    continue # Não é a tabela financeira desejada
                
                # Definir novo cabeçalho e cortar o dataframe
                df.columns = df.iloc[header_idx]
                df = df.iloc[header_idx+1:].copy()
                
                # Normalizar nomes das colunas (Upper case, strip)
                df.columns = [str(c).strip().upper() for c in df.columns]
                
                # Identificar colunas chave
                col_tipo = next((c for c in df.columns if "TIPO" in c), None)
                col_rubrica = next((c for c in df.columns if "DISCRIMINA" in c), None)
                
                if not col_rubrica: 
                    continue

                # Preencher a coluna TIPO (ffill) pois o PDF só traz na primeira linha do grupo
                if col_tipo:
                    df[col_tipo] = df[col_tipo].replace('', pd.NA).ffill()
                    df.rename(columns={col_tipo: 'TIPO'}, inplace=True)
                else:
                    df['TIPO'] = 'GERAL' # Caso não exista coluna Tipo
                
                # Renomear Rubrica
                df.rename(columns={col_rubrica: 'RUBRICA'}, inplace=True)
                
                # Remover linhas de cabeçalho repetido ou totais
                df = df[df['RUBRICA'] != 'DISCRIMINAÇÃO']
                df = df[~df['RUBRICA'].str.contains('TOTAL', na=False, case=False)]
                
                # 4. TRANSFORMAÇÃO (Unpivot/Melt)
                # Identificar colunas que são Meses (JAN, FEV...)
                cols_meses = [c for c in df.columns if c[:3] in MAPA_MESES]
                
                if not cols_meses: 
                    continue
                
                # Transforma colunas de meses em linhas
                df_melted = df.melt(
                    id_vars=['TIPO', 'RUBRICA'], 
                    value_vars=cols_meses,
                    var_name='MES_NOME',
                    value_name='VALOR_STR'
                )
                
                # Converter valores monetários
                df_melted['VALOR'] = df_melted['VALOR_STR'].apply(limpar_valor_monetario)
                
                # Filtrar apenas valores maiores que zero (remove meses vazios)
                df_melted = df_melted[df_melted['VALOR'] > 0]
                
                if df_melted.empty:
                    continue

                # Criar coluna COMPETENCIA (MM/AAAA)
                df_melted['ANO'] = ano
                df_melted['MES_NUM'] = df_melted['MES_NOME'].apply(lambda x: MAPA_MESES.get(x[:3], '00'))
                df_melted['COMPETENCIA'] = df_melted['MES_NUM'] + '/' + df_melted['ANO']
                
                # Selecionar colunas finais
                df_final = df_melted[['COMPETENCIA', 'TIPO', 'RUBRICA', 'VALOR']]
                dados_consolidados.append(df_final)

    if dados_consolidados:
        return pd.concat(dados_consolidados, ignore_index=True)
    return pd.DataFrame()

# --- Função Principal ---
def main():
    setup_page()
    
    uploaded_file = st.file_uploader("Arraste seu PDF aqui", type=["pdf"])
    
    if uploaded_file:
        with st.spinner("Processando PDF e gerando competências..."):
            try:
                df = processar_pdf(uploaded_file)
                
                if not df.empty:
                    # Ordenação Cronológica para exibição
                    # Cria coluna auxiliar de data para ordenar corretamente
                    df['DATA_ORDEM'] = pd.to_datetime(df['COMPETENCIA'], format='%m/%Y', errors='coerce')
                    df = df.sort_values(by=['DATA_ORDEM', 'TIPO', 'RUBRICA'])
                    df = df.drop(columns=['DATA_ORDEM'])
                    
                    st.success(f"Sucesso! {len(df)} registros extraídos.")
                    
                    # --- FILTROS (SIDEBAR) ---
                    st.sidebar.header("Filtros")
                    
                    # 1. Filtro de Competência
                    todas_comp = sorted(df['COMPETENCIA'].unique(), 
                                      key=lambda x: (x.split('/')[1], x.split('/')[0])) # Ordena por Ano depois Mês
                    comp_selecionadas = st.sidebar.multiselect(
                        "Competências (MM/AAAA)", 
                        options=todas_comp, 
                        default=todas_comp
                    )
                    
                    # 2. Filtro de Tipo (Proventos/Descontos)
                    tipos_disponiveis = df['TIPO'].unique()
                    tipos_selecionados = st.sidebar.multiselect(
                        "Tipo", 
                        options=tipos_disponiveis, 
                        default=tipos_disponiveis
                    )
                    
                    # Filtragem Intermediária (para atualizar rubricas disponíveis)
                    df_temp = df[
                        (df['COMPETENCIA'].isin(comp_selecionadas)) & 
                        (df['TIPO'].isin(tipos_selecionados))
                    ]
                    
                    # 3. Filtro de Rubrica
                    rubricas_disponiveis = sorted(df_temp['RUBRICA'].unique())
                    rubricas_selecionadas = st.sidebar.multiselect(
                        "Rubricas", 
                        options=rubricas_disponiveis, 
                        default=rubricas_disponiveis
                    )
                    
                    # --- DATAFRAME FINAL ---
                    df_view = df_temp[df_temp['RUBRICA'].isin(rubricas_selecionadas)]
                    
                    # Exibir tabela formatada
                    st.subheader("Visualização dos Dados")
                    st.dataframe(
                        df_view.style.format({'VALOR': 'R$ {:,.2f}'}), 
                        use_container_width=True,
                        height=500
                    )
                    
                    # Botão de Download
                    csv = df_view.to_csv(index=False, sep=';', decimal=',').encode('utf-8-sig')
                    st.download_button(
                        label="💾 Baixar CSV (Excel)",
                        data=csv,
                        file_name="siape_financeiro_competencias.csv",
                        mime="text/csv",
                    )
                    
                else:
                    st.warning("O PDF foi lido, mas não encontramos tabelas financeiras no formato esperado.")
                    st.info("Dica: Verifique se o PDF contém as colunas 'DISCRIMINAÇÃO' e meses (JAN, FEV...).")
                    
            except Exception as e:
                st.error(f"Erro ao processar o arquivo: {e}")
                # st.exception(e) # Descomente para ver o erro completo em desenvolvimento

# --- Ponto de Entrada ---
if __name__ == "__main__":
    main()
