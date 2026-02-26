class ExtratorDemonstrativos:

    def __init__(self):

        self.meses = [
            "JAN","FEV","MAR","ABR","MAI","JUN",
            "JUL","AGO","SET","OUT","NOV","DEZ"
        ]


    def converter_valor(self, valor):

        try:
            valor = valor.replace('.', '').replace(',', '.')
            return float(valor)

        except:
            return None


    def extrair_ano(self, texto):

        m = re.search(r'ANO REFER[ÊE]NCIA.*?(\d{4})', texto)

        if m:
            return m.group(1)

        return None


    def detectar_meses(self, linha):

        encontrados = []

        for m in self.meses:

            if m in linha.upper():
                encontrados.append(m)

        return encontrados


    def linha_e_total(self, linha):

        linha = linha.upper()

        termos = [
            "TOTAL",
            "BRUTO",
            "LIQUIDO",
            "LÍQUIDO",
            "PAGINA",
            "EMITIDO"
        ]

        for t in termos:
            if t in linha:
                return True

        return False


    def extrair_valores(self, linha):

        return re.findall(
            r'\d{1,3}(?:\.\d{3})*,\d{2}',
            linha
        )


    def extrair_discriminacao(self, linha):

        partes = re.split(
            r'\d{1,3}(?:\.\d{3})*,\d{2}',
            linha
        )

        if partes:
            return partes[0].strip()

        return ""


    def processar_pdf(self, pdf_file):

        dados = []

        meses_atuais = []
        secao_atual = None
        ano_atual = None


        with pdfplumber.open(pdf_file) as pdf:

            for pagina in pdf.pages:

                texto = pagina.extract_text()

                if not texto:
                    continue


                linhas = texto.split("\n")


                # detectar ano uma vez por página

                ano = self.extrair_ano(texto)

                if ano:
                    ano_atual = ano


                for linha in linhas:

                    linha = linha.strip()

                    if not linha:
                        continue


                    linha_upper = linha.upper()


                    # ---------------------
                    # detectar meses

                    if "TIPO DISCRIMINA" in linha_upper:

                        meses_atuais = self.detectar_meses(linha)

                        continue


                    # ignorar linha SEMESTRE

                    if "SEMESTRE" in linha_upper:

                        continue


                    # ---------------------
                    # detectar seção

                    if linha_upper.startswith("RENDIMENTOS"):

                        secao_atual = "RENDIMENTO"

                        linha = linha.replace(
                            "RENDIMENTOS",
                            ""
                        ).strip()


                    elif linha_upper.startswith("DESCONTOS"):

                        secao_atual = "DESCONTO"

                        linha = linha.replace(
                            "DESCONTOS",
                            ""
                        ).strip()


                    # ---------------------

                    if not meses_atuais:
                        continue


                    if not secao_atual:
                        continue


                    if not ano_atual:
                        continue


                    if self.linha_e_total(linha):
                        continue


                    valores = self.extrair_valores(linha)

                    if len(valores) < len(meses_atuais):
                        continue


                    discrim = self.extrair_discriminacao(linha)

                    if len(discrim) < 3:
                        continue


                    for i, mes in enumerate(meses_atuais):

                        valor = valores[i]

                        if valor == "0,00":
                            continue


                        competencia = f"{i+1:02d}/{ano_atual}"


                        dados.append({

                            "Ano":ano_atual,

                            "Competencia":competencia,

                            "Mes":mes,

                            "Discriminacao":discrim,

                            "Valor":valor,

                            "Valor_float":
                                self.converter_valor(valor),

                            "Tipo":secao_atual

                        })


        df = pd.DataFrame(dados)

        return df
