import streamlit as st
import pdfplumber
import pandas as pd
import re
import os
import shutil
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm

# ------------------------------------------------------------
# Configurações do app
# ------------------------------------------------------------
st.set_page_config(page_title="Relatório Serviço Extraordinário", layout="wide")

REGEX = re.compile(
    r"(\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4})\s+(\d{2}\/\d{2}\/\d{4})\s+(\d+)"
)

PASTA_MENSAL = "base_mensal"
os.makedirs(PASTA_MENSAL, exist_ok=True)


# ------------------------------------------------------------
# Função para extrair processos
# ------------------------------------------------------------
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


# ------------------------------------------------------------
# Funções para salvar e carregar
# ------------------------------------------------------------
def salvar_mensal(mes_ano, df):
    caminho = os.path.join(PASTA_MENSAL, f"{mes_ano}.xlsx")
    df.to_excel(caminho, index=False)


def carregar_mensal(mes_ano):
    caminho = os.path.join(PASTA_MENSAL, f"{mes_ano}.xlsx")
    return pd.read_excel(caminho)


# ------------------------------------------------------------
# Função para gerar PDF
# ------------------------------------------------------------
def gerar_pdf(titulo, df, observacoes=""):
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    largura, altura = A4
    y = altura - 2*cm

    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(2*cm, y, titulo)
    y -= 1.2 * cm

    pdf.setFont("Helvetica", 11)
    for linha in observacoes.split("\n"):
        pdf.drawString(2*cm, y, linha)
        y -= 0.7 * cm

    y -= 0.8 * cm
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(2*cm, y, "Lista de processos:")
    y -= 1 * cm

    pdf.setFont("Helvetica", 10)

    for _, row in df.iterrows():
        texto = f"{row['nº']}. {row['processo']} — {row['data']}"
        pdf.drawString(2*cm, y, texto)
        y -= 0.6 * cm

        if y < 2*cm:
            pdf.showPage()
            pdf.setFont("Helvetica", 10)
            y = altura - 2*cm

    pdf.save()
    buffer.seek(0)
    return buffer


# ============================================================
#                      INTERFACE DO APP
# ============================================================
aba = st.sidebar.radio("Menu", ["Upload mensal", "Relatório mensal", "Consolidado geral"])

# ------------------------------------------------------------
# 1) UPLOAD MENSAL
# ------------------------------------------------------------
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

        if lista:
            df = pd.DataFrame(lista)

            df["data"] = df["data"].dt.strftime("%d/%m/%Y")  # remove hora
            df = df.drop(columns=["sequencial"])             # remove sequencial

            df.insert(0, "nº", df.reset_index().index + 1)
            df["nº"] = df["nº"].astype(str).zfill(2)

            salvar_mensal(mes_ano, df)

            st.success(f"Mês salvo como {mes_ano}.xlsx")
            st.dataframe(df, height=500)
        else:
            st.warning("Nenhum processo encontrado.")


# ------------------------------------------------------------
# 2) RELATÓRIO MENSAL
# ------------------------------------------------------------
elif aba == "Relatório mensal":
    st.header("📊 Relatório mensal")

    arquivos_mensais = sorted([f.replace(".xlsx", "") for f in os.listdir(PASTA_MENSAL)])

    if not arquivos_mensais:
        st.warning("Nenhum mês encontrado.")
    else:
        mes_ano = st.selectbox("Selecione o mês:", arquivos_mensais)
        df = carregar_mensal(mes_ano)

        st.subheader("🧹 Ferramentas de limpeza")
        col1, col2 = st.columns(2)

        if col1.button("Apagar este mês"):
            caminho = os.path.join(PASTA_MENSAL, f"{mes_ano}.xlsx")
            os.remove(caminho)
            st.success(f"{mes_ano} apagado.")
            st.stop()

        if col2.button("Apagar TODOS os meses"):
            shutil.rmtree(PASTA_MENSAL)
            os.makedirs(PASTA_MENSAL, exist_ok=True)
            st.success("Todos os meses foram apagados.")
            st.stop()

        st.subheader(f"📌 Resumo de {mes_ano}")
        st.write(f"**Total:** {len(df)} processos")

        total_por_data = df.groupby("data").size()
        st.table(total_por_data)

        st.subheader("Tabela completa")
        st.dataframe(df, height=500)

        st.subheader("Observações")
        observacoes = st.text_area("Digite informações adicionais:")

        pdf_buffer = gerar_pdf(f"Relatório Mensal — {mes_ano}", df, observacoes)

        st.download_button(
            "📄 Baixar PDF",
            data=pdf_buffer,
            file_name=f"Relatorio_{mes_ano}.pdf",
            mime="application/pdf"
        )


# ------------------------------------------------------------
# 3) CONSOLIDADO GERAL
# ------------------------------------------------------------
elif aba == "Consolidado geral":
    st.header("📑 Relatório Consolidado")

    arquivos = os.listdir(PASTA_MENSAL)
    if not arquivos:
        st.warning("Nenhum mês encontrado.")
    else:
        lista = []
        for arquivo in arquivos:
            mes_ano = arquivo.replace(".xlsx", "")
            df = carregar_mensal(mes_ano)
            df["mes"] = mes_ano
            lista.append(df)

        df_final = pd.concat(lista)

        st.subheader("🧹 Limpeza")
        col1, col2 = st.columns(2)

        if col1.button("Apagar TODOS os meses"):
            shutil.rmtree(PASTA_MENSAL)
            os.makedirs(PASTA_MENSAL, exist_ok=True)
            st.success("Todos os meses foram apagados.")
            st.stop()

        st.subheader("Totais por mês")
        st.table(df_final.groupby("mes").size())

        st.subheader("Total geral")
        st.write(f"**{len(df_final)} processos**")

        st.subheader("Tabela completa")
        st.dataframe(df_final, height=600)

        st.subheader("Observações")
        obs_geral = st.text_area("Digite observações gerais:")

        pdf_buffer = gerar_pdf("Relatório Consolidado", df_final, obs_geral)

        st.download_button(
            "📄 Baixar PDF Consolidado",
            data=pdf_buffer,
            file_name="Relatorio_Consolidado.pdf",
            mime="application/pdf"
        )
