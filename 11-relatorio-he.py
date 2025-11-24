
import streamlit as st
import pdfplumber
import pandas as pd
import re
import os
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm

st.set_page_config(page_title="Relatório Serviço Extraordinário", layout="wide")

REGEX = re.compile(
    r"(\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4})\s+(\d{2}/\d{2}/\d{4})\s+(\d+)"
)

PASTA_MENSAL = "base_mensal"
os.makedirs(PASTA_MENSAL, exist_ok=True)


def extrair_processos(pdf_file):
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


def gerar_pdf(titulo, df, observacoes=""):
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    pdf.setFont("Helvetica", 11)

    largura, altura = A4
    y = altura - 2*cm

    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(2*cm, y, titulo)
    y -= 1.2*cm

    # Observações digitadas pelo usuário
    pdf.setFont("Helvetica", 11)
    for linha in observacoes.split("\n"):
        pdf.drawString(2*cm, y, linha)
        y -= 0.7*cm

    y -= 0.8*cm
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(2*cm, y, "Lista de processos:")
    y -= 1*cm

    pdf.setFont("Helvetica", 10)

    for _, row in df.iterrows():
        texto = f"{row['processo']}  |  {row['data'].strftime('%d/%m/%Y')}  | seq: {row['sequencial']}"
        pdf.drawString(2*cm, y, texto)
        y -= 0.6*cm

        if y < 2*cm:
            pdf.showPage()
            pdf.setFont("Helvetica", 10)
            y = altura - 2*cm

    pdf.save()
    buffer.seek(0)
    return buffer

# ======================
#       INTERFACE
# ======================

aba = st.sidebar.radio("Menu", ["Upload mensal", "Relatório mensal", "Consolidado geral"])

# ---------------------------------
#  ABA 1 – UPLOAD MENSAL
# ---------------------------------
if aba == "Upload mensal":
    st.header("📁 Upload dos PDFs do mês")

    mes = st.selectbox(
        "Selecione o mês:",
        ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
         "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
    )
    ano = st.number_input("Ano", min_value=2020, max_value=2035, value=2025)

    mes_ano = f"{mes}_{ano}"

    arquivos = st.file_uploader("Envie os PDFs", type=["pdf"], accept_multiple_files=True)

    if arquivos:
        lista = []
        for arq in arquivos:
            dados = extrair_processos(arq)
            for d in dados:
                d["arquivo_origem"] = arq.name
                lista.append(d)

        if not lista:
            st.warning("Nenhum processo encontrado.")
        else:
            df = pd.DataFrame(lista)
            df = df.sort_values(by=["data", "processo"])

            salvar_mensal(mes_ano, df)

            st.success(f"Mês salvo como {mes_ano}.xlsx")
            st.dataframe(df, height=500)


# ---------------------------------
#  ABA 2 – RELATÓRIO MENSAL
# ---------------------------------
elif aba == "Relatório mensal":
    st.header("📊 Relatório mensal")

    arquivos = sorted([f.replace(".xlsx", "") for f in os.listdir(PASTA_MENSAL)])

    if not arquivos:
        st.warning("Nenhum mês encontrado.")
    else:
        mes_ano = st.selectbox("Selecione o mês:", arquivos)
        df = carregar_mensal(mes_ano)

        st.subheader(f"📌 Resumo de {mes_ano}")
        st.write(f"**Total:** {len(df)} processos")

        total_dias = df.groupby(df["data"].dt.strftime("%d/%m/%Y")).size()
        st.table(total_dias)

        st.subheader("Tabela completa")
        st.dataframe(df, height=500)

        st.subheader("Observações do relatório")
        observacoes = st.text_area(
            "Digite observações, justificativas, informações adicionais:",
            placeholder="Ex.: Trabalho realizado em regime de serviço extraordinário conforme escala da contadoria."
        )

        # Botão gerar PDF
        pdf_buffer = gerar_pdf(
            f"Relatório mensal – {mes_ano}",
            df,
            observacoes
        )

        st.download_button(
            "📄 Baixar PDF do mês",
            data=pdf_buffer,
            file_name=f"Relatorio_{mes_ano}.pdf",
            mime="application/pdf"
        )


# ---------------------------------
#  ABA 3 – CONSOLIDADO
# ---------------------------------
elif aba == "Consolidado geral":
    st.header("📑 Consolidado Geral")

    arquivos = [f for f in os.listdir(PASTA_MENSAL)]
    if not arquivos:
        st.warning("Nenhum mês encontrado.")
    else:
        lista = []
        for arquivo in arquivos:
            mes_ano = arquivo.replace(".xlsx", "")
            df = carregar_mensal(mes_ano)
            df["mes"] = mes_ano
            lista.append(df)

        df_final = pd.concat(lista).sort_values(by="data")

        st.subheader("Totais por mês")
        total_mes = df_final.groupby("mes").size()
        st.table(total_mes)

        st.subheader("Total geral")
        st.write(f"**{len(df_final)} processos**")

        st.subheader("Tabela completa")
        st.dataframe(df_final, height=600)

        st.subheader("Observações gerais")
        obs_geral = st.text_area(
            "Digite observações gerais para o relatório consolidado:",
            placeholder="Informações adicionais para o relatório anual..."
        )

        pdf_buffer = gerar_pdf(
            "Relatório Consolidado do Ano",
            df_final,
            obs_geral
        )

        st.download_button(
            "📄 Baixar PDF Consolidado",
            data=pdf_buffer,
            file_name=f"Relatorio_Consolidado.pdf",
            mime="application/pdf"
        )
