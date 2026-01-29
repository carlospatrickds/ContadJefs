# app.py
# Extrator de Rubricas – Ficha Financeira SIAPE (controle exato de competências)
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

INICIO_FICHA_RE = re.compile(r"Siape - Sistema Integrado de Administracao de Recursos Humanos", re.IGNORECASE)
FIM_FICHA_RE = re.compile(r"TOTAL\s+L[IÍ]QUIDO", re.IGNORECASE)
ANO_RE = re.compile(r"Ficha Financeira referente a:\s*(\d{4})", re.IGNORECASE)

st.set_page_config(page_title="Extrator de Rubricas – SIAPE", layout="wide")
st.title("📊 Extrator de Rubricas – Ficha Financeira SIAPE")

pdf_file = st.file_uploader("Envie o PDF da Ficha Financeira", type="pdf")

@st.cache_data(show_spinner=False)
def extrair_dados(pdf_bytes):
    registros = []

    with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            texto = page.extract_text() or ""
            linhas = texto.split("\n")

            i = 0
            while i < len(linhas):
                if not INICIO_FICHA_RE.search(linhas[i]):
                    i += 1
                    continue

                bloco = []
                i += 1
                while i < len(linhas) and not FIM_FICHA_RE.search(linhas[i]):
                    bloco.append(linhas[i])
                    i += 1

                bloco_texto = "\n".join(bloco)
                ano_match = ANO_RE.search(bloco_texto)
                if not ano_match:
                    continue
                ano = ano_match.group(1)

                linhas_bloco = bloco_texto.split("\n")
                cabecalho_idx = None
                for idx, linha in enumerate(linhas_bloco):
                    if linha.strip().startswith("Rubrica|"):
                        cabecalho_idx = idx
                        break
                if cabecalho_idx is None:
                    continue

                cabecalho_cols = [c.strip() for c in linhas_bloco[cabecalho_idx].split("|")]
                meses = [c for c in cabecalho_cols if c in MESES]
                primeira_col_mes = cabecalho_cols.index(meses[0])

                for linha in linhas_bloco[cabecalho_idx + 1:]:
                    if FIM_FICHA_RE.search(linha):
                        break

                    colunas = [c.strip() for c in linha.split("|")]
                    if len(colunas) <= primeira_col_mes:
                        continue

                    codigo = colunas[0]
                    # Normaliza encoding da rubrica (corrige OLÃ© -> OLÉ)
                    rubrica = colunas[1]
                    rubrica = rubrica.encode('latin1', errors='ignore').decode('utf-8', errors='ignore')
                    tipo_rd = colunas[2]

                    valores_mes = colunas[primeira_col_mes:primeira_col_mes + len(meses)]

                    for mes, celula in zip(meses, valores_mes):
                        m = VALOR_RE.search(celula)
                        if not m:
                            continue

                        competencia = f"{MESES[mes]}/{ano}"

                        registros.append({
                            "Codigo": codigo,
                            "Rubrica": rubrica,
                            "Tipo": "Receita" if tipo_rd.strip() == "R" else "Despesa",
                            "Competencia": competencia,
                            "Valor": f"R$ {m.group(0)}",
                            "Pagina": page_num
                        })

                i += 1

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
