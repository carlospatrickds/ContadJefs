import pdfplumber
import pandas as pd
import re


class ExtratorDemonstrativos:
    """
    Extrator robusto para fichas financeiras SIAPE
    Compatível com PDFs consolidados (2010+)
    """

    def __init__(self):

        self.meses = [
            "JAN","FEV","MAR","ABR","MAI","JUN",
            "JUL","AGO","SET","OUT","NOV","DEZ"
        ]


    # --------------------------------------------------

    def converter_valor_string(self, valor_str):

        try:
            valor_str = valor_str.replace('.', '').replace(',', '.')
            return float(valor_str)
        except:
            return None


    # --------------------------------------------------

    def extrair_ano(self, texto):

        m = re.search(r'ANO REFER[ÊE]NCIA.*?(\d{4})', texto)

        if m:
            return m.group(1)

        return None


    # --------------------------------------------------

    def detectar_meses(self, linha):

        linha = linha.upper()

        meses = [m for m in self.meses if m in linha]

        return meses


    # --------------------------------------------------

    def linha_e_total(self, linha):

        linha = linha.upper()

        termos = [
            "TOTAL",
            "BRUTO",
            "LIQUIDO",
            "LÍQUIDO",
            "BASE"
        ]

        return any(t in linha for t in termos)


    # --------------------------------------------------

    def processar_pdf(
        self,
        pdf_file,
        extrair_proventos=True,
        extrair_descontos=True
    ):

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


                linhas = texto.split('\n')

                meses_pagina = []

                secao = None


                for linha in linhas:

                    linha = linha.strip()

                    if not linha:
                        continue


                    linha_upper = linha.upper()


                    # ----------------------
                    # detectar meses

                    if "TIPO DISCRIMIN" in linha_upper:

                        meses_pagina = self.detectar_meses(linha)

                        continue


                    # ----------------------
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


                    # ----------------------

                    if not meses_pagina:
                        continue


                    if not secao:
                        continue


                    # ----------------------
                    # ignorar totais

                    if self.linha_e_total(linha):
                        continue


                    # ----------------------
                    # extrair valores

                    valores = re.findall(
                        r'\d{1,3}(?:\.\d{3})*,\d{2}',
                        linha
                    )


                    if len(valores) < len(meses_pagina):
                        continue


                    # ----------------------
                    # discriminação

                    discrim = re.split(
                        r'\d{1,3}(?:\.\d{3})*,\d{2}',
                        linha
                    )[0].strip()


                    if len(discrim) < 3:
                        continue


                    # ----------------------
                    # gravar

                    for i, mes in enumerate(meses_pagina):

                        valor = valores[i]

                        if valor == "0,00":
                            continue


                        competencia = f"{i+1:02d}/{ano}"

                        dados.append({

                            "Ano": ano,

                            "Competencia": competencia,

                            "Mes": mes,

                            "Discriminacao": discrim,

                            "Valor": valor,

                            "Valor_float":
                                self.converter_valor_string(valor),

                            "Tipo": secao

                        })


        df = pd.DataFrame(dados)


        # ordenar

        if not df.empty:

            df = df.sort_values(
                ["Ano","Competencia","Tipo"]
            )


        return df


# --------------------------------------------------

def exportar_excel(df, arquivo_saida):

    with pd.ExcelWriter(
        arquivo_saida,
        engine="xlsxwriter"
    ) as writer:

        df.to_excel(
            writer,
            index=False,
            sheet_name="Dados"
        )



# --------------------------------------------------

if __name__ == "__main__":

    pdf = "Fichas_financeiras_consolidadas_2015_A_2026.pdf"

    extrator = ExtratorDemonstrativos()

    df = extrator.processar_pdf(pdf)

    exportar_excel(df, "resultado_siape.xlsx")

    print("Extração concluída.")
