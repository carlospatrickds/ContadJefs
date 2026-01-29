import streamlit as st
import pdfplumber
import pandas as pd
import re
import io

# --- Configuração da Página ---
st.set_page_config(page_title="Extrator Financeiro SIAPE", layout="wide")

st.title("📂 Extrator de Fichas Financeiras (SIAPE)")
st.markdown("""
    Faça upload do seu PDF (mesmo com várias páginas/anos). 
    O sistema identificará o **Ano de Referência** correto e permitirá filtrar Proventos/Descontos.
""")

# --- Função Auxiliar: Remover Duplicatas nas Colunas ---
def make_columns_unique(columns):
    """Garante que não existam colunas com nomes iguais (ex: 'Valor', 'Valor')"""
    seen = {}
    new_columns = []
    for col in columns:
        if col in seen:
            seen[col] += 1
            new_columns.append(f"{col}_{seen[col]}")
        else:
            seen[col] = 0
            new_columns.append(col)
    return new_columns

# --- Função de Extração ---
def extract_data_from_pdf(file):
    all_data = []
    
    with pdfplumber.open(file) as pdf:
        for page_num, page in enumerate(pdf.pages):
            text = page.extract_text()
            if not text:
                continue # Pula páginas em branco ou imagens sem OCR
            
            # 1. BUSCA INTELIGENTE DO ANO DE REFERÊNCIA
            match_ano = re.search(r'ANO REFER[ÊE]NCIA\s*[\n\r]*\s*(\d{4})', text, re.IGNORECASE)
            
            if match_ano:
                ano_referencia = match_ano.group(1)
            else:
                ano_referencia = f"Desconhecido (Pág {page_num+1})"

            # 2. EXTRAÇÃO DA TABELA
            tables = page.extract_tables()
            
            for table in tables:
                df_page = pd.DataFrame(table)
                df_page = df_page.dropna(how='all') # Remove linhas totalmente vazias
                
                if df_page.shape[1] < 2: 
                    continue
                
                # Procurar a linha de cabeçalho
                header_index = -1
                for idx, row in df_page.iterrows():
                    row_str = " ".join([str(x) for x in row]).upper()
                    if "DISCRIMINA" in row_str:
                        header_index = idx
                        break
                
                if header_index != -1:
                    # Ajustar cabeçalho
                    new_header = df_page.iloc[header_index].values
                    df_page = df_page.iloc[header_index+1:].copy()
                    
                    # Normalizar nomes das colunas
                    clean_header = [str(c).strip().upper() if c else f"COL_{i}" for i, c in enumerate(new_header)]
                    
                    # CORREÇÃO PRINCIPAL: Garantir nomes únicos
                    df_page.columns = make_columns_unique(clean_header)
                    
                    # 3. TRATAMENTO DE TIPO (PROVENTO vs DESCONTO)
                    # Verifica se existe coluna TIPO ou similar
                    col_tipo = next((c for c in df_page.columns if "TIPO" in c), None)
                    
                    if col_tipo:
                        # Preenche vazios para baixo (ffill)
                        df_page[col_tipo] = df_page[col_tipo].replace("", None).ffill()
                    
                    # Adicionar coluna do Ano
                    df_page.insert(0, "ANO_REF", ano_referencia)
                    
                    # Padronizar a coluna "DISCRIMINAÇÃO" para "RUBRICA"
                    col_rubrica = next((c for c in df_page.columns if "DISCRIMINA" in c), None)
                    if col_rubrica:
                        df_page.rename(columns={col_rubrica: "RUBRICA"}, inplace=True)
                        
                        # Filtros de limpeza
                        df_page = df_page[df_page["RUBRICA"].notna()]
                        df_page = df_page[df_page["RUBRICA"].astype(str).str.strip() != ""]
                        df_page = df_page[~df_page["RUBRICA"].astype(str).str.contains("DISCRIMINA", case=False)]
                        
                        all_data.append(df_page)

    if all_data:
        # Concatenar ignorando index para evitar o erro de reindexing
        return pd.concat(all_data, ignore_index=True)
    else:
        return pd.DataFrame()

# --- Interface Principal ---
uploaded_file = st.file_uploader("Arraste seu PDF aqui", type=["pdf"])

if uploaded_file:
    with st.spinner("Processando... Lendo Ano de Referência e Rubricas..."):
        try:
            df_final = extract_data_from_pdf(uploaded_file)
            
            if not df_final.empty:
                st.success("Dados extraídos com sucesso!")
                
                # --- FILTROS LATERAIS ---
                st.sidebar.header("Filtros de Exportação")
                
                # 1. Filtro de Ano
                anos_disponiveis = sorted(df_final['ANO_REF'].unique())
                anos_selecionados = st.sidebar.multiselect(
                    "Selecione o Ano de Referência", 
                    options=anos_disponiveis,
                    default=anos_disponiveis
                )
                df_filtered = df_final[df_final['ANO_REF'].isin(anos_selecionados)]
                
                # 2. Filtro de Tipo (Proventos/Descontos)
                # Tenta achar a coluna de tipo (pode ter mudado de nome devido à unicidade, então buscamos por string)
                col_tipo_final = next((c for c in df_filtered.columns if "TIPO" in c), None)
                
                if col_tipo_final:
                    df_filtered[col_tipo_final] = df_filtered[col_tipo_final].astype(str).str.strip().str.upper()
                    
                    tipo_selecionado = st.sidebar.radio(
                        "O que você quer visualizar?",
                        options=["TUDO", "APENAS RENDIMENTOS", "APENAS DESCONTOS"]
                    )
                    
                    if tipo_selecionado == "APENAS RENDIMENTOS":
                        df_filtered = df_filtered[df_filtered[col_tipo_final].str.contains("REND|PROV", na=False)]
                    elif tipo_selecionado == "APENAS DESCONTOS":
                        df_filtered = df_filtered[df_filtered[col_tipo_final].str.contains("DESC", na=False)]
                
                # 3. Filtro de Rubricas
                if "RUBRICA" in df_filtered.columns:
                    rubricas_disponiveis = sorted(df_filtered["RUBRICA"].unique())
                    rubricas_selecionadas = st.sidebar.multiselect(
                        "Selecione as Rubricas Específicas",
                        options=rubricas_disponiveis,
                        default=rubricas_disponiveis
                    )
                    df_view = df_filtered[df_filtered["RUBRICA"].isin(rubricas_selecionadas)]
                else:
                    df_view = df_filtered
                
                # --- EXIBIÇÃO ---
                st.subheader(f"Visualizando {len(df_view)} registros")
                st.dataframe(df_view, use_container_width=True)
                
                # Botão de Download
                csv = df_view.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="💾 Baixar CSV Selecionado",
                    data=csv,
                    file_name="extracao_financeira_ajustada.csv",
                    mime="text/csv",
                )
                
            else:
                st.error("Não foi possível identificar tabelas financeiras padrão neste PDF.")
                
        except Exception as e:
            st.error(f"Ocorreu um erro técnico: {e}")
            st.code(e) # Mostra o erro exato para facilitar debug se necessário
