import streamlit as st
import pdfplumber
import pandas as pd
import re
import os
from datetime import datetime

st.set_page_config(page_title="Relatório Serviço Extraordinário", layout="wide")

# Regex para capturar: processo | data | sequencial
REGEX = re.compile(
    r"(\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4})\s+(\d{2}/\d{2}/\d{4})\s+(\d+)"
)

# Pastas
PASTA_MENSAL = "base_mensal"
os.makedirs(PASTA_MENSAL, exist_ok=True)


def extrair_processos(pdf_file):
    """Extrai processos de um PDF usando regex."""
    dados = []
    with pdfplumber.open(pdf_file) as pdf:
        for page in pdf.pages:
            texto = page.extract_text()
            if not texto:
                continue

            encontrados = REGEX.findall(texto)
            for processo, data, seq in encontrados:
                dados.append({
                    "processo": processo,
                    "data": pd.to_datetime(data, dayfirst=True),
                    "sequencial": int(seq)
                })
    return dados


def salvar_mensal(mes_ano, df):
    caminho = os.path.join(PASTA_MENSAL, f"{mes_ano}.xlsx")
    df.to_excel(caminho, index=False)


def carregar_mensal(mes_ano):
    caminho = os.path.join(PASTA_MENSAL, f"{mes_ano}.xlsx")
    return pd.read_excel(caminho, parse_dates=["data"])


# ----------------------------------------------------------------------------------------------------
# ABA 1 – Upload Mensal
# ----------------------------------------------------------------------------------------------------

aba = st.sidebar.radio("Menu", ["Upload mensal", "Relatório mensal", "Consolidado geral"])

if aba == "Upload mensal":
    st.header("📁 Upload dos PDFs do mês")

    mes = st.selectbox(
        "Selecione o mês:",
        ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
         "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
    )
    ano = st.number_input("Ano", min_value=2020, max_value=2030, value=2025)

    mes_ano = f"{mes}_{ano}"

    arquivos = st.file_uploader(
        "Envie os PDFs do mês",
        type=["pdf"],
        accept_multiple_files=True
    )

    if arquivos:
        st.info("Processando arquivos…")
        lista = []

        for arq in arquivos:
            dados = extrair_processos(arq)
            for d in dados:
                d["arquivo_origem"] = arq.name
                lista.append(d)

        if lista:
            df = pd.DataFrame(lista)
            df = df.sort_values(by=["data", "processo"])
            salvar_mensal(mes_ano, df)

            st.success(f"Arquivo mensal salvo: {mes_ano}.xlsx")
            st.dataframe(df, height=500)
        else:
            st.warning("Nenhum processo encontrado nos PDFs enviados.")


# ----------------------------------------------------------------------------------------------------
# ABA 2 – Relatório Mensal
# ----------------------------------------------------------------------------------------------------

elif aba == "Relatório mensal":
    st.header("📊 Relatório do mês")

    arquivos_mensais = sorted([f.replace(".xlsx", "") for f in os.listdir(PASTA_MENSAL)])

    if not arquivos_mensais:
        st.warning("Nenhum mês processado ainda.")
    else:
        mes_ano = st.selectbox("Selecione o mês:", arquivos_mensais)
        df = carregar_mensal(mes_ano)

        st.subheader(f"📌 Resumo de {mes_ano}")
        st.write(f"**Total de processos:** {len(df)}")

        # Total por dia
        total_por_dia = df.groupby(df["data"].dt.strftime("%d/%m/%Y")).size()

        st.subheader("Totais por data")
        st.table(total_por_dia)

        st.subheader("Tabela completa")
        st.dataframe(df, height=500)

        st.download_button(
            "Baixar Excel do mês",
            df.to_excel(index=False, engine="openpyxl"),
            file_name=f"{mes_ano}.xlsx"
        )

# ----------------------------------------------------------------------------------------------------
# ABA 3 – Consolidado Geral
# ----------------------------------------------------------------------------------------------------

elif aba == "Consolidado geral":
    st.header("📑 Consolidado geral")

    arquivos_mensais = [f for f in os.listdir(PASTA_MENSAL)]
    if not arquivos_mensais:
        st.warning("Nenhum mês processado ainda.")
    else:
        lista = []
        for arquivo in arquivos_mensais:
            mes_ano = arquivo.replace(".xlsx", "")
            df = carregar_mensal(mes_ano)
            df["mes"] = mes_ano
            lista.append(df)

        df_final = pd.concat(lista).sort_values(by=["data"])

        st.subheader("Totais por mês")
        total_mes = df_final.groupby("mes").size()
        st.table(total_mes)

        st.subheader("Total geral")
        st.write(f"**{len(df_final)} processos**")

        st.subheader("Tabela consolidada")
        st.dataframe(df_final, height=600)

        st.download_button(
            "Baixar consolidado (Excel)",
            df_final.to_excel(index=False, engine="openpyxl"),
            file_name="consolidado_servico_extra.xlsx"
        )
