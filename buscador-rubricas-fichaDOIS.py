# app.py
# Streamlit app para extrair rubricas de Ficha Financeira SIAPE (PDF)
# Requisitos: streamlit, pdfplumber, pandas

import streamlit as st
import pdfplumber
import pandas as pd
import re
from io import BytesIO

MESES = {
    "JAN": "01", "FEV": "02", "MAR": "03", "ABR": "04",
    "MAI": "05", "JUN": "06", "JUL": "07", "AGO": "08",
    "SET": "09", "OUT": "10", "NOV": "11", "DEZ": "12"
}

VALOR_RE = re.compile(r"\d{1,3}(?:\.\d{3})*,\d{2}")

st.set_page_config(page_title="Extrator de Rubricas – SIAPE", layout="wide")
st.title("📊 Extrator de Rubricas – Ficha Financeira SIAPE")

pdf_file = st.file_uploader("Envie o PDF da Ficha Financeira", type="pdf")

@st.cache_data(show_spinner=False)
def extrair_dados(pdf_bytes):
    registros = []

    with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            texto = page.extract_text() or ""

            # Ano de referência
            ano_match = re.search(r"Ficha Financeira referente a:\s*(\d{4})", texto)
            if not ano_match:
                continue
            ano = ano_match.group(1)

            linhas = texto.split("\n")
            cabecalho_idx = None

            for i, linha in enumerate(linhas):
                if linha.strip().startswith("Rubrica|"):
                    cabecalho_idx = i
                    break

            if cabecalho_idx is None:
                continue

            meses_linha = linhas[cabecalho_idx]
            meses = [m for m in MESES.keys() if m in meses_linha]

            for linha in linhas[cabecalho_idx + 1:]:
                if linha.strip().startswith("*****"):
                    break

                partes = [p.strip() for p in linha.split("|")]
                if len(partes) < 5:
                    continue

                cod = partes[0]
                nome = partes[1]
                rd = partes[2] or ""

                valores = VALOR_RE.findall(linha)

                for mes, valor in zip(meses, valores):
                    competencia = f"{MESES[mes]}/{ano}"
                    registros.append({
                        "Codigo": cod,
                        "Rubrica": nome,
                        "Tipo": "Receita" if rd.strip() == "R" else "Despesa",
                        "Competencia": competencia,
                        "Valor": f"R$ {valor}",
                        "Pagina": page_num
                    })

    return pd.DataFrame(registros)

if pdf_file:
    with st.spinner("Processando PDF..."):
        df = extrair_dados(pdf_file.read())

    if df.empty:
        st.warning("Nenhum dado encontrado.")
    else:
        st.success(f"{len(df)} registros extraídos.")

        col1, col2 = st.columns(2)
        with col1:
            tipo = st.multiselect("Filtrar por tipo", ["Receita", "Despesa"], default=["Receita", "Despesa"])
        with col2:
            rubricas = st.multiselect("Filtrar por rubrica", sorted(df["Rubrica"].unique()))

        df_filtro = df[df["Tipo"].isin(tipo)]
        if rubricas:
            df_filtro = df_filtro[df_filtro["Rubrica"].isin(rubricas)]

        st.dataframe(df_filtro, use_container_width=True)

        csv = df_filtro.to_csv(index=False, sep=";", encoding="utf-8-sig")
        st.download_button(
            "📥 Baixar CSV",
            data=csv,
            file_name="rubricas_ficha_financeira.csv",
            mime="text/csv"
        )
