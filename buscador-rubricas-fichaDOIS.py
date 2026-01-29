import streamlit as st
import pdfplumber
import pandas as pd
import re
import io

def format_brl(val):
    """Formata valores numéricos para o padrão R$ 1.000,00"""
    try:
        return f"R$ {val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except:
        return val

def extract_data(pdf_file):
    all_data = []
    with pdfplumber.open(pdf_file) as pdf:
        for page_num, page in enumerate(pdf.pages, 1):
            text = page.extract_text()
            
            # 1. Extrair Ano de Referência
            # Busca o padrão "referente a: 2016"
            year_match = re.search(r"referente a:\s*(\d{4})", text)
            year_ref = year_match.group(1) if year_match else "9999"

            # Mapeamento de meses
            month_map = {
                "JAN": "01", "FEV": "02", "MAR": "03", "ABR": "04",
                "MAI": "05", "JUN": "06", "JUL": "07", "AGO": "08",
                "SET": "09", "OUT": "10", "NOV": "11", "DEZ": "12"
            }

            # 2. Extrair Tabelas
            tables = page.extract_tables()
            for table in tables:
                df_temp = pd.DataFrame(table)
                
                # Identifica se é a tabela de rubricas (Geralmente tem 'Rubrica' e 'Nome Rubrica')
                if any("Rubrica" in str(cell) for cell in df_temp.iloc[0]):
                    # Limpeza básica: assume a primeira linha como cabeçalho
                    headers = df_temp.iloc[0]
                    # Encontrar colunas de meses
                    month_cols = [(i, month_map[col.upper()]) for i, col in enumerate(headers) if col and col.upper() in month_map]
                    
                    for _, row in df_temp.iloc[1:].iterrows():
                        rubrica_cod = row[0]
                        rubrica_nome = row[1]
                        
                        if not rubrica_cod or str(rubrica_cod).strip() == "":
                            continue

                        for col_idx, month_val in month_cols:
                            valor_raw = row[col_idx]
                            if valor_raw and valor_raw.strip():
                                # Converte valor para float (ex: "1.234,56" -> 1234.56)
                                try:
                                    valor_clean = float(valor_raw.replace(".", "").replace(",", "."))
                                    
                                    all_data.append({
                                        "Página": page_num,
                                        "Código": rubrica_cod,
                                        "Rubrica": rubrica_nome,
                                        "Competência": f"{month_val}/{year_ref}",
                                        "Valor Numérico": valor_clean, # Para filtros
                                        "Valor": format_brl(valor_clean),
                                        "Tipo": "Receita" if valor_clean > 0 else "Despesa"
                                    })
                                except:
                                    continue
                                    
    return pd.DataFrame(all_data)

# --- Interface Streamlit ---
st.set_page_config(page_title="Extrator de Ficha Financeira SIAPE", layout="wide")
st.title("📊 Extrator de Rubricas - SIAPE")

uploaded_file = st.file_uploader("Arraste o PDF da Ficha Financeira aqui", type="pdf")

if uploaded_file:
    with st.spinner('Processando PDF...'):
        df = extract_data(uploaded_file)
    
    if not df.empty:
        st.success("Dados extraídos com sucesso!")
        
        # Filtros na Barra Lateral
        st.sidebar.header("Filtros")
        
        tipos = st.sidebar.multiselect("Filtrar por Tipo", options=df["Tipo"].unique(), default=df["Tipo"].unique())
        nomes = st.sidebar.multiselect("Selecionar Rubricas Específicas", options=df["Rubrica"].unique())
        
        # Aplicar Filtros
        df_filtered = df[df["Tipo"].isin(tipos)]
        if nomes:
            df_filtered = df_filtered[df_filtered["Rubrica"].isin(nomes)]
            
        st.dataframe(df_filtered.drop(columns=["Valor Numérico"]), use_container_width=True)
        
        # Exportação CSV
        csv = df_filtered.to_csv(index=False).encode('utf-8-sig')
        st.download_button(
            label="📥 Baixar CSV (Com número de página)",
            data=csv,
            file_name="extracao_rubricas.csv",
            mime="text/csv",
        )
    else:
        st.warning("Não foi possível encontrar rubricas no formato esperado.")
