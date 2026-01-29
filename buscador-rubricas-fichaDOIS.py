# app.py
# Extrator de Rubricas – Ficha Financeira (SIAPE)
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

            # Meses exatamente na ordem visual do cabeçalho
            meses = []
            for token in linhas[cabecalho_idx].split("|"):
                t = token.strip()
                if t in MESES:
                    meses.append(t)

            for linha in linhas[cabecalho_idx + 1:]:
                if linha.strip().startswith("*****"):
                    break

                colunas = [c.strip() for c in linha.split("|")]
                if len(colunas) < 5:
                    continue

                codigo = colunas[0]
                rubrica = colunas[1]
                tipo_rd = colunas[2]

                # valores por coluna (posição importa!)
                valores_por_coluna = []
                for c in colunas:
                    m = VALOR_RE.search(c)
                    valores_por_coluna.append(m.group(0) if m else None)

                for mes, valor in zip(meses, valores_por_coluna):
                    if not valor:
                        continue

                    competencia = f"{MESES[mes]}/{ano}"

                    registros.append({
                        "Codigo": codigo,
                        "Rubrica": rubrica,
                        "Tipo": "Receita" if tipo_rd.strip() == "R" else "Despesa",
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

        st.subheader("🔎 Filtros")
        col1, col2 = st.columns(2)
        with col1:
            tipos = st.multiselect(
                "Tipo de rubrica",
                ["Receita", "Despesa"],
                default=["Receita", "Despesa"]
            )
        with col2:
            rubricas_sel = st.multiselect(
                "Selecione as rubricas",
                sorted(df["Rubrica"].unique()),
                default=sorted(df["Rubrica"].unique())
            )

        df_filtro = df[df["Tipo"].isin(tipos)]
        df_filtro = df_filtro[df_filtro["Rubrica"].isin(rubricas_sel)]

        st.dataframe(df_filtro, use_container_width=True)

        st.subheader("📤 Exportação")
        csv = df_filtro.to_csv(index=False, sep=";", encoding="utf-8-sig")

        st.download_button(
            "📥 Baixar CSV apenas com as rubricas selecionadas",
            data=csv,
            file_name="rubricas_ficha_financeira_filtradas.csv",
            mime="text/csv"
        )
