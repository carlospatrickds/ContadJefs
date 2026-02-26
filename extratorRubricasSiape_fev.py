# ================= IMPORTS =================

import re
from datetime import datetime
from io import BytesIO

import streamlit as st
import pdfplumber
import pandas as pd
import plotly.express as px


# ================= CONFIGURAÇÃO =================

st.set_page_config(
    page_title="Extrator de Fichas Financeiras",
    page_icon="📊",
    layout="wide"
)

MESES_MAPA = {
    "JAN":1,"FEV":2,"MAR":3,"ABR":4,"MAI":5,"JUN":6,
    "JUL":7,"AGO":8,"SET":9,"OUT":10,"NOV":11,"DEZ":12
}


# ================= PARSER =================

class FichaFinanceiraParser:

    def __init__(self, pdf_bytes):
        self.pdf_bytes = pdf_bytes
        self.tipo_atual = None
        self.ano_atual = None
        self.meses_ativos = []
        self.metadados = {}
        self.dados = []

    def normalizar_moeda(self, valor):
        valor = valor.replace('.', '').replace(',', '.')
        try:
            return float(valor)
        except:
            return None

    def detectar_ano(self, linha):
        match = re.search(r"\b(19|20)\d{2}\b", linha)
        if match:
            self.ano_atual = int(match.group())

    def detectar_meses(self, linha):
        meses = []
        for mes in MESES_MAPA.keys():
            if mes in linha.upper():
                meses.append(mes)
        if len(meses) >= 3:
            self.meses_ativos = meses

    def detectar_tipo(self, linha):
        if "RENDIMENTO" in linha.upper():
            self.tipo_atual = "RECEITA"
        elif "DESCONTO" in linha.upper():
            self.tipo_atual = "DESCONTO"

    def extrair_metadados(self, texto):
        nome = re.search(r"NOME.*?\n(.+)", texto, re.IGNORECASE)
        cpf = re.search(r"\d{3}\.\d{3}\.\d{3}-\d{2}", texto)
        cargo = re.search(r"CARGO.*?\n(.+)", texto, re.IGNORECASE)

        self.metadados = {
            "Nome": nome.group(1).strip() if nome else "",
            "CPF": cpf.group() if cpf else "",
            "Cargo": cargo.group(1).strip() if cargo else ""
        }

    def processar_linha(self, linha, pagina):

        padrao = r"^([A-Z0-9\-\.\s\/]+?)\s+((?:\d{1,3}(?:\.\d{3})*,\d{2}\s*)+)$"
        match = re.match(padrao, linha)

        if not match:
            return

        descricao = match.group(1).strip()
        valores = re.findall(r"\d{1,3}(?:\.\d{3})*,\d{2}", match.group(2))

        for i, valor in enumerate(valores):
            if i >= len(self.meses_ativos):
                continue

            mes = self.meses_ativos[i]
            mes_num = MESES_MAPA[mes]
            valor_float = self.normalizar_moeda(valor)

            if valor_float and valor_float != 0 and self.ano_atual:
                competencia = datetime(self.ano_atual, mes_num, 1)

                self.dados.append({
                    "Discriminacao": descricao,
                    "Valor": valor_float,
                    "Competencia": competencia,
                    "Pagina": pagina,
                    "Ano": self.ano_atual,
                    "Tipo": self.tipo_atual
                })

    def executar(self):

        with pdfplumber.open(self.pdf_bytes) as pdf:
            for numero_pagina, pagina in enumerate(pdf.pages, start=1):

                texto = pagina.extract_text()
                if not texto:
                    continue

                if numero_pagina == 1:
                    self.extrair_metadados(texto)

                linhas = texto.split("\n")

                for linha in linhas:
                    self.detectar_ano(linha)
                    self.detectar_meses(linha)
                    self.detectar_tipo(linha)
                    self.processar_linha(linha, numero_pagina)

        df = pd.DataFrame(self.dados)

        if not df.empty:
            df["Competencia"] = pd.to_datetime(df["Competencia"])
            df = df.sort_values("Competencia")

        return df, self.metadados


# ================= EXPORTAÇÃO =================

def gerar_excel(df_filtrado, metadados):

    output = BytesIO()

    df_export = df_filtrado.copy()
    df_export["Competencia"] = pd.to_datetime(df_export["Competencia"])

    consolidado = df_export.groupby(
        ["Ano","Discriminacao"]
    )["Valor"].sum().reset_index()

    df_meta = pd.DataFrame(
        list(metadados.items()),
        columns=["Campo","Valor"]
    )

    with pd.ExcelWriter(
        output,
        engine="openpyxl",
        datetime_format="DD/MM/YYYY"
    ) as writer:

        df_export.to_excel(writer, sheet_name="Rubricas Detalhadas", index=False)
        consolidado.to_excel(writer, sheet_name="Consolidado Anual", index=False)
        df_meta.to_excel(writer, sheet_name="Servidor", index=False)

    return output.getvalue()


# ================= INTERFACE =================

abas = st.tabs(["📄 Extração", "📊 Análise", "ℹ️ Sobre o App"])

df_global = None


# ===== ABA EXTRAÇÃO =====

with abas[0]:

    st.header("Upload e Extração")

    arquivo = st.file_uploader("Envie o PDF da ficha financeira", type="pdf")

    if arquivo:

        parser = FichaFinanceiraParser(arquivo)
        df, metadados = parser.executar()
        df_global = df

        if metadados:

            st.subheader("Relatório do Servidor")

            col1, col2, col3 = st.columns(3)

            col1.markdown(f"""
            <div>
                <span style="font-size:13px; color:gray;">Nome</span><br>
                <span style="font-size:15px; font-weight:600;">
                    {metadados.get("Nome","")}
                </span>
            </div>
            """, unsafe_allow_html=True)

            col2.markdown(f"""
            <div>
                <span style="font-size:13px; color:gray;">CPF</span><br>
                <span style="font-size:15px; font-weight:600;">
                    {metadados.get("CPF","")}
                </span>
            </div>
            """, unsafe_allow_html=True)

            col3.markdown(f"""
            <div>
                <span style="font-size:13px; color:gray;">Cargo</span><br>
                <span style="font-size:15px; font-weight:600;">
                    {metadados.get("Cargo","")}
                </span>
            </div>
            """, unsafe_allow_html=True)

        st.divider()

        if not df.empty:

            rubricas = sorted(df["Discriminacao"].unique())

            selecionadas = st.multiselect(
                "Selecione as rubricas",
                rubricas,
                default=rubricas
            )

            df_filtrado = df[df["Discriminacao"].isin(selecionadas)]

            st.dataframe(df_filtrado, use_container_width=True)

            excel_bytes = gerar_excel(df_filtrado, metadados)

            st.download_button(
                "📥 Baixar Excel",
                excel_bytes,
                file_name="ficha_financeira_extraida.xlsx"
            )


# ===== ABA ANÁLISE =====

with abas[1]:

    st.header("Análise")

    if df_global is not None and not df_global.empty:

        modo = st.radio(
            "Modo de visualização",
            ["Mensal", "Consolidado por Ano"]
        )

        if modo == "Mensal":

            fig = px.bar(
                df_global,
                x="Competencia",
                y="Valor",
                color="Discriminacao",
                title="Valores Mensais por Rubrica"
            )

        else:

            df_anual = df_global.groupby(
                ["Ano","Discriminacao"]
            )["Valor"].sum().reset_index()

            fig = px.bar(
                df_anual,
                x="Ano",
                y="Valor",
                color="Discriminacao",
                barmode="group",
                title="Valores Consolidados por Ano"
            )

        st.plotly_chart(fig, use_container_width=True)

    else:
        st.info("Carregue um PDF na aba Extração para visualizar análises.")


# ===== ABA SOBRE =====

with abas[2]:

    st.header("Sobre o Aplicativo")

    st.markdown("""
    Este aplicativo realiza:

    - Extração automática de fichas financeiras em PDF
    - Identificação de rendimentos e descontos
    - Conversão monetária padronizada
    - Registro da página de origem
    - Consolidação anual por rubrica
    - Exportação estruturada para Excel com datas reais
    - Análise gráfica interativa

    Indicado para auditoria administrativa e apoio em cálculos judiciais.
    """)
