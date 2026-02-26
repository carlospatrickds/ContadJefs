import streamlit as st
import pdfplumber
import pandas as pd
import re


# =====================================================
# EXTRATOR SIAPE
# =====================================================

class ExtratorDemonstrativos:

    def __init__(self):

        self.meses = [
            "JAN","FEV","MAR","ABR","MAI","JUN",
            "JUL","AGO","SET","OUT","NOV","DEZ"
        ]


    # -------------------------------------------------

    def converter_valor(self, valor):

        try:
            valor = valor.replace('.', '').replace(',', '.')
            return float(valor)

        except:
            return None


    # -------------------------------------------------

    def extrair_ano(self, texto):

        m = re.search(
            r'ANO REFER[ÊE]NCIA.*?(\d{4})',
            texto
        )

        if m:
            return m.group(1)

        return None


    # -------------------------------------------------

    def detectar_meses(self, linha):

        linha = linha.upper()

        meses_encontrados = []

        for m in self.meses:

            if m in linha:
                meses_encontrados.append(m)

        return meses_encontrados


    # -------------------------------------------------

    def linha_valida(self, linha):

        linha = linha.upper()

        ignorar = [
            "TOTAL",
            "BRUTO",
            "LIQUIDO",
            "LÍQUIDO",
            "PAGINA",
            "EMITIDO"
        ]

        for termo in ignorar:

            if termo in linha:
                return False

        return True


    # -------------------------------------------------

    def processar_pdf(self, pdf_file):

        dados = []

        with pdfplumber.open(pdf_file) as pdf:

            for pagina in pdf.pages:

                texto = pagina.extract_text()

                if not texto:
                    continue


                if "DEMONSTRATIVO" not in texto.upper():
                    continue


                ano = self.extrair_ano(texto)

                if not ano:
                    continue


                linhas = texto.split("\n")

                meses = []
                secao = None


                for linha in linhas:

                    linha = linha.strip()

                    if not linha:
                        continue


                    linha_upper = linha.upper()


                    # ----------------------------
                    # detectar cabeçalho meses

                    if "TIPO DISCRIMIN" in linha_upper:

                        meses = self.detectar_meses(linha)

                        continue


                    # ----------------------------
                    # detectar seção

                    if linha_upper.startswith("RENDIMENTOS"):

                        secao = "RENDIMENTO"

                        linha = linha.replace(
                            "RENDIMENTOS",
                            ""
                        ).strip()


                    elif linha_upper.startswith("DESCONTOS"):

                        secao = "DESCONTO"

                        linha = linha.replace(
                            "DESCONTOS",
                            ""
                        ).strip()


                    if not meses:
                        continue


                    if not secao:
                        continue


                    if not self.linha_valida(linha):
                        continue


                    # ----------------------------
                    # valores monetários

                    valores = re.findall(
                        r'\d{1,3}(?:\.\d{3})*,\d{2}',
                        linha
                    )


                    if len(valores) < len(meses):
                        continue


                    # ----------------------------
                    # discriminação

                    discrim = re.split(
                        r'\d{1,3}(?:\.\d{3})*,\d{2}',
                        linha
                    )[0].strip()


                    if len(discrim) < 3:
                        continue


                    # ----------------------------
                    # salvar

                    for i, mes in enumerate(meses):

                        valor = valores[i]

                        if valor == "0,00":
                            continue


                        competencia = f"{i+1:02d}/{ano}"

                        dados.append({

                            "Ano":ano,

                            "Competencia":competencia,

                            "Mes":mes,

                            "Discriminacao":discrim,

                            "Valor":valor,

                            "Valor_float":
                                self.converter_valor(valor),

                            "Tipo":secao

                        })


        df = pd.DataFrame(dados)

        if not df.empty:

            df = df.sort_values(
                ["Ano","Competencia","Tipo"]
            )


        return df



# =====================================================
# STREAMLIT
# =====================================================

st.title("Buscador de Rubricas - Ficha Financeira SIAPE")


pdf_file = st.file_uploader(
    "Envie a ficha financeira PDF",
    type="pdf"
)


if pdf_file:

    extrator = ExtratorDemonstrativos()

    with st.spinner("Processando ficha..."):

        df = extrator.processar_pdf(pdf_file)


    if df.empty:

        st.error("Nenhum dado encontrado.")

    else:

        st.success("Extração concluída")


        st.dataframe(df, use_container_width=True)


        csv = df.to_csv(
            index=False
        ).encode("utf-8")


        st.download_button(
            "Baixar CSV",
            csv,
            "rubricas.csv",
            "text/csv"
        )
