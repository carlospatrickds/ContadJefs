# ⚠️ VERSÃO ESTENDIDA
# Tudo que já funcionava foi MANTIDO.
# Apenas adicionados recursos OPCIONAIS (ativados por checkbox).

import streamlit as st
import pdfplumber
import pandas as pd
import re
from io import BytesIO

# ---------------- CONFIGURAÇÕES ----------------
MESES = {
    "JAN": "01", "FEV": "02", "MAR": "03", "ABR": "04",
    "MAI": "05", "JUN": "06", "JUL": "07", "AGO": "08",
    "SET": "09", "OUT": "10", "NOV": "11", "DEZ": "12"
}

VALOR_RE = re.compile(r"\d{1,3}(?:\.\d{3})*,\d{2}")
INICIO_FICHA_RE = re.compile(r"Siape\s*-\s*Sistema Integrado de Administracao de Recursos Humanos", re.IGNORECASE)
FIM_FICHA_RE = re.compile(r"TOTAL\s+L[IÍ]QUIDO", re.IGNORECASE)
ANO_RE = re.compile(r"Ficha Financeira referente a:\s*(\d{4})", re.IGNORECASE)

# ---------------- STREAMLIT ----------------
st.set_page_config(page_title="Extrator SIAPE", layout="wide")
st.title("📊 Extrator de Rubricas – Ficha Financeira SIAPE")

pdf_file = st.file_uploader("Envie o PDF da Ficha Financeira", type="pdf")

# ---------------- FUNÇÕES ----------------
def corrigir_texto(txt):
    if not txt:
        return ""
    if "Ã" in txt or "�" in txt:
        try:
            return txt.encode("latin1").decode("utf-8")
        except Exception:
            return txt
    return txt

@st.cache_data(show_spinner=False)
def extrair_dados(pdf_bytes):
    registros = []

    with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
        texto_completo = "\n".join(page.extract_text() or "" for page in pdf.pages)

    linhas = texto_completo.split("\n")
    i = 0
    ano_atual = None
    meses_correntes = []
    idx_primeiro_mes = None

    while i < len(linhas):
        linha = linhas[i]

        if INICIO_FICHA_RE.search(linha):
            ano_atual = None
            meses_correntes = []
            idx_primeiro_mes = None
            i += 1
            continue

        ano_match = ANO_RE.search(linha)
        if ano_match:
            ano_atual = ano_match.group(1)
            i += 1
            continue

        if "|" in linha and any(m in linha for m in MESES):
            colunas = [c.strip() for c in linha.split("|")]
            meses_correntes = [c for c in colunas if c in MESES]
            if meses_correntes:
                idx_primeiro_mes = colunas.index(meses_correntes[0])
            i += 1
            continue

        if FIM_FICHA_RE.search(linha):
            meses_correntes = []
            idx_primeiro_mes = None
            i += 1
            continue

        if meses_correntes and idx_primeiro_mes is not None and "|" in linha:
            colunas = [c.strip() for c in linha.split("|")]
            if len(colunas) <= idx_primeiro_mes or not ano_atual:
                i += 1
                continue

            codigo = colunas[0]
            rubrica = corrigir_texto(colunas[1])
            tipo_rd = colunas[2].upper()
            valores = colunas[idx_primeiro_mes: idx_primeiro_mes + len(meses_correntes)]

            for mes_nome, celula in zip(meses_correntes, valores):
                match = VALOR_RE.search(celula)
                if match:
                    registros.append({
                        "Codigo": codigo,
                        "Rubrica": rubrica,
                        "Tipo": "Receita" if "R" in tipo_rd else "Despesa",
                        "Competencia": f"{MESES[mes_nome]}/{ano_atual}",
                        "Valor": match.group(0)
                    })
        i += 1

    df = pd.DataFrame(registros)
    df["Valor_num"] = df["Valor"].str.replace(".", "", regex=False).str.replace(",", ".", regex=False).astype(float)
    return df

# ---------------- EXECUÇÃO ----------------
if pdf_file:
    with st.spinner("Processando PDF..."):
        df = extrair_dados(pdf_file.read())

    if df.empty:
        st.warning("Nenhum dado encontrado.")
        st.stop()

    st.success(f"✅ {len(df)} registros extraídos")

    # -------- FILTROS --------
    rubricas_sel = st.multiselect("Rubricas", sorted(df["Rubrica"].unique()), default=df["Rubrica"].unique())
    tipos_sel = st.multiselect("Tipo", ["Receita", "Despesa"], default=["Receita", "Despesa"])

    df_f = df[df["Rubrica"].isin(rubricas_sel) & df["Tipo"].isin(tipos_sel)]

    st.dataframe(df_f.drop(columns="Valor_num"), use_container_width=True)

    # -------- EXTENSÕES OPCIONAIS --------
    st.markdown("---")
    st.subheader("🧠 Análises Opcionais")

    if st.checkbox("📊 Totalizar por Rubrica / Ano"):
        df_f[["Mes", "Ano"]] = df_f["Competencia"].str.split("/", expand=True)
        resumo = df_f.groupby(["Ano", "Rubrica"])["Valor_num"].sum().reset_index()
        st.dataframe(resumo, use_container_width=True)

    if st.checkbox("💰 Identificar Consignados / Empréstimos"):
        chave = df_f["Rubrica"].str.contains("EMPREST|CARTAO|CONSIGN", case=False, regex=True)
        st.dataframe(df_f[chave].drop(columns="Valor_num"), use_container_width=True)

    if st.checkbox("📈 Total mensal"):
        total_mes = df_f.groupby("Competencia")["Valor_num"].sum().reset_index()
        st.dataframe(total_mes, use_container_width=True)

    # -------- EXPORTAÇÃO --------
    csv = df_f.drop(columns="Valor_num").to_csv(index=False, sep=";", encoding="utf-8-sig")
    st.download_button("📥 Baixar CSV", csv, "extracao_siape_com_analises.csv", "text/csv")
