import re
import pdfplumber
import pandas as pd
from datetime import datetime

MESES_MAPA = {
    "jan": 1, "fev": 2, "mar": 3, "abr": 4,
    "mai": 5, "jun": 6, "jul": 7, "ago": 8,
    "set": 9, "out": 10, "nov": 11, "dez": 12
}

def limpar_valor(valor_str):
    if not valor_str:
        return None
    valor_str = valor_str.replace(".", "").replace(",", ".")
    try:
        return float(valor_str)
    except:
        return None


def extrair_dados_pdf(caminho_pdf):

    dados = []
    tipo_atual = None
    ano_atual = None

    with pdfplumber.open(caminho_pdf) as pdf:

        for numero_pagina, pagina in enumerate(pdf.pages, start=1):

            texto = pagina.extract_text()
            if not texto:
                continue

            linhas = texto.split("\n")

            # Detectar ano
            for linha in linhas:
                if "ANO DE REFERÊNCIA" in linha.upper():
                    ano_match = re.search(r"\d{4}", linha)
                    if ano_match:
                        ano_atual = int(ano_match.group())

            # Detectar meses ativos da página
            meses_ativos = []
            for linha in linhas:
                if "JAN" in linha.upper() and "FEV" in linha.upper():
                    partes = linha.lower().split()
                    for p in partes:
                        if p[:3] in MESES_MAPA:
                            meses_ativos.append(p[:3])

            for linha in linhas:

                linha_upper = linha.upper()

                if "RENDIMENTOS" in linha_upper:
                    tipo_atual = "RECEITA"
                    continue

                if "DESCONTOS" in linha_upper:
                    tipo_atual = "DESCONTO"
                    continue

                # Regex para capturar rubrica + valores
                match = re.match(r"(.+?)\s+([\d\.,\s]+)$", linha)

                if match and ano_atual and tipo_atual:

                    descricao = match.group(1).strip()
                    valores_str = match.group(2).split()

                    for i, valor in enumerate(valores_str):
                        if i < len(meses_ativos):

                            mes_str = meses_ativos[i]
                            mes_num = MESES_MAPA.get(mes_str)

                            valor_float = limpar_valor(valor)

                            if valor_float and valor_float != 0:

                                competencia = datetime(
                                    year=ano_atual,
                                    month=mes_num,
                                    day=1
                                ).strftime("%b/%y").lower()

                                dados.append({
                                    "Discriminacao": descricao,
                                    "Valor": valor_float,
                                    "Competencia": competencia,
                                    "Pagina": numero_pagina,
                                    "Ano": ano_atual,
                                    "Tipo": tipo_atual
                                })

    df = pd.DataFrame(dados)

    df.sort_values(["Ano", "Competencia"], inplace=True)

    return df
