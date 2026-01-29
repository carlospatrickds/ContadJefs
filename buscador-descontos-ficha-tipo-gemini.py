import streamlit as st
import pdfplumber
import pandas as pd
import re
from datetime import datetime

# --- Configurações da Página ---
def setup_page():
    st.set_page_config(
        page_title="Extrator SIAPE - Competência",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    st.title("📊 Extrator SIAPE - Competência Correta")
    st.markdown("""
        **Instruções:**
        1. Faça upload do PDF.
        2. O sistema limpa os cabeçalhos (ex: remove quebras de linha em 'JAN').
        3. Gera a coluna **COMPETENCIA** no formato **MM/AAAA**.
    """)

# --- Mapas e Constantes ---
MAPA_MESES = {
    'JAN': '01', 'FEV': '02', 'MAR': '03', 'ABR': '04', 
    'MAI': '05', 'JUN': '06', 'JUL': '07', 'AGO': '08', 
    'SET': '09', 'OUT': '10', 'NOV': '11', 'DEZ': '12'
}

def limpar_header_mes(col_name):
    """
    Remove sujeira do PDF (quebras de linha, espaços) e retorna as 3 primeiras letras
    para bater com o MAPA_MESES.
    Ex: 'JAN\n' -> 'JAN', ' JANEIRO ' -> 'JAN'
    """
    if not col_name:
        return ""
    # Remove quebras de linha e espaços, pega os 3 primeiros chars e põe em maiúsculo
    limpo = str(col_name).replace('\n', '').replace('\r', '').strip().upper()
    return limpo[:3]

def limpar_valor_monetario(valor):
    """Converte '1.200,50' para 1200.50"""
    if pd.isna(valor) or str(valor).strip() == '':
        return 0.0
    v = str(valor).replace(' ', '').replace('.', '').replace(',', '.')
    try:
        return float(v)
    except:
        return 0.0

def extrair_ano_robusto(page_text):
    """Busca o ano especificamente após o rótulo 'ANO REFERENCIA'."""
    # Achatamos o texto para ignorar se o ano está na linha de baixo
    text_flat = page_text.replace('\n', ' ').replace('\r', ' ')
    
    # Regex estrita: Procura 'ANO REFERENCIA', ignora chars até achar 4 digitos
    match = re.search(r'ANO REFER[ÊE]NCIA.*?(\d{4})', text_flat, re.IGNORECASE)
    
    if match:
        return match.group(1)
    return None

def processar_pdf(file):
    dados_consolidados = []
    
    with pdfplumber.open(file) as pdf:
        for page_num, page in enumerate(pdf.pages):
            text = page.extract_text()
            if not text: continue
            
            # 1. Busca Ano
            ano = extrair_ano_robusto(text)
            if not ano:
                # Fallback: Se não achar, marca para auditoria
                ano = f"ERRO_ANO_PAG{page_num+1}"

            tables = page.extract_tables()
            
            for table in tables:
                df = pd.DataFrame(table)
                df = df.dropna(how='all')
                
                if df.shape[1] < 2: continue
                
                # 2. Localizar Cabeçalho
                header_idx = -1
                for idx, row in df.iterrows():
                    # Junta a linha toda e verifica se parece um cabeçalho financeiro
                    row_str = " ".join([str(x) for x in row]).upper()
                    if "DISCRIMINA" in row_str and ("JAN" in row_str or "NOV" in row_str):
                        header_idx = idx
                        break
                
                if header_idx == -1: continue
                
                # Ajustar DataFrame
                df.columns = df.iloc[header_idx]
                df = df.iloc[header_idx+1:].copy()
                
                # 3. LIMPEZA DOS CABEÇALHOS (O SEGREDO)
                # Normaliza 'JAN\n' para 'JAN' para garantir o match
                col_map = {}
                cols_meses_validos = []
                
                for col in df.columns:
                    col_limpa = limpar_header_mes(col) # Ex: JAN
                    if col_limpa in MAPA_MESES:
                        col_map[col] = col_limpa # Mapeia 'JAN\n' -> 'JAN'
                        cols_meses_validos.append(col)
                    else:
                        # Limpa colunas como 'DISCRIMINAÇÃO\n'
                        col_str = str(col).strip().upper()
                        if "DISCRIMINA" in col_str:
                            col_map[col] = "RUBRICA"
                        elif "TIPO" in col_str:
                            col_map[col] = "TIPO"
                        else:
                            col_map[col] = col_str

                df.rename(columns=col_map, inplace=True)
                
                # Verificar se temos as colunas essenciais
                if "RUBRICA" not in df.columns: continue
                
                # Preencher TIPO (ffill)
                if "TIPO" in df.columns:
                    df["TIPO"] = df["TIPO"].replace('', pd.NA).ffill()
                else:
                    df["TIPO"] = "GERAL"

                # Limpar linhas inúteis
                df = df[df["RUBRICA"] != "DISCRIMINAÇÃO"]
                df = df[~df["RUBRICA"].str.contains("TOTAL", na=False, case=False)]

                # 4. TRANSFORMAÇÃO (Melt) APENAS NAS COLUNAS DE MESES CONFIRMADOS
                # Verifica quais colunas de meses (JAN, FEV...) realmente existem nesta tabela
                meses_presentes = [c for c in df.columns if c in MAPA_MESES]
                
                if not meses_presentes: continue
                
                df_melted = df.melt(
                    id_vars=["TIPO", "RUBRICA"],
                    value_vars=meses_presentes,
                    var_name="MES_SIGLA",
                    value_name="VALOR_STR"
                )
                
                # Converter Valor
                df_melted["VALOR"] = df_melted["VALOR_STR"].apply(limpar_valor_monetario)
                df_melted = df_melted[df_melted["VALOR"] > 0] # Remove zerados
                
                # 5. GERAR COMPETÊNCIA CORRETA (MM/AAAA)
                df_melted["ANO"] = ano
                df_melted["MES_NUM"] = df_melted["MES_SIGLA"].map(MAPA_MESES)
                df_melted["COMPETENCIA"] = df_melted["MES_NUM"] + "/" + df_melted["ANO"]
                
                # Guarda apenas o necessário
                dados_consolidados.append(df_melted[["COMPETENCIA", "TIPO", "RUBRICA", "VALOR"]])

    if dados_consolidados:
        return pd.concat(dados_consolidados, ignore_index=True)
    return pd.DataFrame()

def main():
    setup_page()
    uploaded_file = st.file_uploader("Arraste o PDF aqui", type=["pdf"])
    
    if uploaded_file:
        with st.spinner("Lendo PDF e gerando competências..."):
            try:
                df = processar_pdf(uploaded_file)
                
                if not df.empty:
                    # ORDENAÇÃO POR DATA REAL
                    # Cria objeto data para ordenar corretamente (Jan/20 antes de Fev/20)
                    df['DATA_OBJ'] = pd.to_datetime(df['COMPETENCIA'], format='%m/%Y', errors='coerce')
                    df = df.sort_values(by=['DATA_OBJ', 'TIPO', 'RUBRICA'])
                    df = df.drop(columns=['DATA_OBJ'])
                    
                    st.success(f"Extraído com sucesso! {len(df)} lançamentos.")
                    
                    # --- FILTROS ---
                    st.sidebar.header("Filtros")
                    
                    # Filtro Competência
                    todas_comp = df['COMPETENCIA'].unique() # Já está ordenado pelo sort_values acima
                    comp_sel = st.sidebar.multiselect("Competência (Mês/Ano)", todas_comp, default=todas_comp)
                    
                    # Filtro Tipo
                    tipos_sel = st.sidebar.multiselect("Tipo", df['TIPO'].unique(), default=df['TIPO'].unique())
                    
                    # Filtro Rubrica
                    rubricas_sel = st.sidebar.multiselect("Rubrica", sorted(df['RUBRICA'].unique()), default=sorted(df['RUBRICA'].unique()))
                    
                    # Aplica Filtros
                    df_final = df[
                        (df['COMPETENCIA'].isin(comp_sel)) &
                        (df['TIPO'].isin(tipos_sel)) &
                        (df['RUBRICA'].isin(rubricas_sel))
                    ]
                    
                    # Exibe Tabela
                    st.dataframe(
                        df_final.style.format({'VALOR': 'R$ {:,.2f}'}),
                        use_container_width=True,
                        height=600
                    )
                    
                    # Download
                    csv = df_final.to_csv(index=False, sep=';', decimal=',').encode('utf-8-sig')
                    st.download_button(
                        "💾 Baixar CSV (Excel)",
                        data=csv,
                        file_name="siape_financeiro_competencias.csv",
                        mime="text/csv"
                    )
                else:
                    st.error("Não encontramos dados válidos. Verifique se o PDF possui as colunas de meses (JAN, FEV...).")
            
            except Exception as e:
                st.error(f"Erro no processamento: {e}")

if __name__ == "__main__":
    main()
