import streamlit as st
import pdfplumber
import pandas as pd
import re
from io import BytesIO

# Configurações iniciais
MESES = {
    "JAN": "01", "FEV": "02", "MAR": "03", "ABR": "04",
    "MAI": "05", "JUN": "06", "JUL": "07", "AGO": "08",
    "SET": "09", "OUT": "10", "NOV": "11", "DEZ": "12"
}

VALOR_RE = re.compile(r"\d{1,3}(?:\.\d{3})*,\d{2}")
INICIO_FICHA_RE = re.compile(r"Siape - Sistema Integrado de Administracao de Recursos Humanos", re.IGNORECASE)
FIM_FICHA_RE = re.compile(r"TOTAL\s+L[IÍ]QUIDO", re.IGNORECASE)
ANO_RE = re.compile(r"Ficha Financeira referente a:\s*(\d{4})", re.IGNORECASE)

st.set_page_config(page_title="Extrator SIAPE", layout="wide")
st.title("📊 Extrator de Rubricas – Ficha Financeira SIAPE")

pdf_file = st.file_uploader("Envie o PDF da Ficha Financeira", type="pdf")

def corrigir_texto(texto):
    """Corrige problemas de encoding (Mojibake) como OLÃ© -> OLÉ"""
    if not texto:
        return ""
    try:
        # Tenta converter de Latin-1 para UTF-8 para corrigir acentos corrompidos
        return texto.encode('latin1').decode('utf-8')
    except (UnicodeEncodeError, UnicodeDecodeError):
        return texto

@st.cache_data(show_spinner=False)
def extrair_dados(pdf_bytes):
    registros = []

    with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            texto = page.extract_text() or ""
            linhas = texto.split("\n")

            i = 0
            while i < len(linhas):
                # Procura o início de uma ficha financeira
                if not INICIO_FICHA_RE.search(linhas[i]):
                    i += 1
                    continue

                # Captura o bloco de dados até o Total Líquido
                bloco = []
                while i < len(linhas):
                    bloco.append(linhas[i])
                    if FIM_FICHA_RE.search(linhas[i]):
                        break
                    i += 1

                bloco_texto = "\n".join(bloco)
                ano_match = ANO_RE.search(bloco_texto)
                ano = ano_match.group(1) if ano_match else "S/A"

                linhas_bloco = bloco_texto.split("\n")
                cabecalho_idx = next((idx for idx, l in enumerate(linhas_bloco) if "Rubrica|" in l), None)
                
                if cabecalho_idx is None:
                    i += 1
                    continue

                # Identifica as colunas de meses
                cabecalho_cols = [c.strip() for c in linhas_bloco[cabecalho_idx].split("|")]
                meses_na_pagina = [c for c in cabecalho_cols if c in MESES]
                
                if not meses_na_pagina:
                    i += 1
                    continue
                    
                idx_primeiro_mes = cabecalho_cols.index(meses_na_pagina[0])

                # Processa as rubricas (linhas após o cabeçalho)
                for linha in linhas_bloco[cabecalho_idx + 1:]:
                    if FIM_FICHA_RE.search(linha):
                        break

                    colunas = [c.strip() for c in linha.split("|")]
                    if len(colunas) <= idx_primeiro_mes:
                        continue

                    # Extração e Correção
                    codigo = colunas[0]
                    rubrica = corrigir_texto(colunas[1])
                    tipo_rd = colunas[2].upper()
                    
                    # Captura valores apenas para os meses presentes no cabeçalho
                    valores_celulas = colunas[idx_primeiro_mes : idx_primeiro_mes + len(meses_na_pagina)]

                    for mes_nome, celula in zip(meses_na_pagina, valores_celulas):
                        match_valor = VALOR_RE.search(celula)
                        if match_valor:
                            registros.append({
                                "Codigo": codigo,
                                "Rubrica": rubrica,
                                "Tipo": "Receita" if "R" in tipo_rd else "Despesa",
                                "Competencia": f"{MESES[mes_nome]}/{ano}",
                                "Valor": match_valor.group(0),
                                "Pagina": page_num
                            })
                i += 1

    return pd.DataFrame(registros)

if pdf_file:
    with st.spinner("Processando PDF..."):
        df = extrair_dados(pdf_file.read())

    if df.empty:
        st.warning("Nenhum dado encontrado no formato esperado.")
    else:
        st.success(f"Sucesso! {len(df)} registros extraídos.")

        # --- Filtros ---
        st.subheader("🔎 Filtros e Visualização")
        col_f1, col_f2 = st.columns(2)
        
        with col_f1:
            lista_rubricas = sorted(df["Rubrica"].unique())
            rubricas_sel = st.multiselect("Filtrar Rubricas:", lista_rubricas, default=lista_rubricas)
        
        with col_f2:
            tipos_sel = st.multiselect("Filtrar Tipo:", ["Receita", "Despesa"], default=["Receita", "Despesa"])

        # Aplicação dos filtros
        df_filtrado = df[(df["Rubrica"].isin(rubricas_sel)) & (df["Tipo"].isin(tipos_sel))]

        st.dataframe(df_filtrado, use_container_width=True, hide_index=True)

        # --- Exportação ---
        st.subheader("📤 Exportar Dados")
        # utf-8-sig garante que o Excel abra com acentos corretos
        csv_data = df_filtrado.to_csv(index=False, sep=";", encoding="utf-8-sig")
        
        st.download_button(
            label="📥 Baixar Planilha (CSV)",
            data=csv_data,
            file_name="extracao_siape_corrigida.csv",
            mime="text/csv"
        )

