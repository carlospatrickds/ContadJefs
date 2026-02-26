class ExtratorDemonstrativos:
    """Classe para extrair dados de demonstrativos financeiros em PDF usando tabelas"""

    def __init__(self):
        self.meses_map = {
            'JAN': 1, 'JANEIRO': 1,
            'FEV': 2, 'FEVEREIRO': 2,
            'MAR': 3, 'MARÇO': 3,
            'ABR': 4, 'ABRIL': 4,
            'MAI': 5, 'MAIO': 5,
            'JUN': 6, 'JUNHO': 6,
            'JUL': 7, 'JULHO': 7,
            'AGO': 8, 'AGOSTO': 8,
            'SET': 9, 'SETEMBRO': 9,
            'OUT': 10, 'OUTUBRO': 10,
            'NOV': 11, 'NOVEMBRO': 11,
            'DEZ': 12, 'DEZEMBRO': 12
        }

    def formatar_valor_brasileiro(self, valor: float) -> str:
        return f"{valor:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')

    def converter_valor_string(self, valor_str: str) -> Optional[float]:
        try:
            valor_str = re.sub(r'[^\d,\.]', '', str(valor_str))
            if re.match(r'^\d+,\d{1,2}$', valor_str):
                return float(valor_str.replace('.', '').replace(',', '.'))
            if re.match(r'^\d{1,3}(?:\.\d{3})*,\d{2}$', valor_str):
                return float(valor_str.replace('.', '').replace(',', '.'))
            return float(valor_str.replace(',', '.'))
        except:
            return None

    def extrair_ano_referencia_robusto(self, texto: str) -> Optional[str]:
        """Extrai o ano de referência de todo o texto (busca em qualquer lugar)"""
        padrao = r'ANO\s+REFER[EÊ]NCIA\s*[:\s]*(\d{4})'
        match = re.search(padrao, texto, re.IGNORECASE)
        if match:
            return match.group(1)
        # Fallback: procurar um ano de 4 dígitos próximo à palavra "REFERÊNCIA"
        padrao_fallback = r'REFER[EÊ]NCIA.*?(\d{4})'
        match = re.search(padrao_fallback, texto, re.IGNORECASE | re.DOTALL)
        if match:
            return match.group(1)
        return None

    def processar_pdf(self, pdf_file, extrair_proventos: bool = True, extrair_descontos: bool = True) -> pd.DataFrame:
        dados = []
        meses_ordenados = ["JAN", "FEV", "MAR", "ABR", "MAI", "JUN", "JUL", "AGO", "SET", "OUT", "NOV", "DEZ"]

        with pdfplumber.open(pdf_file) as pdf:
            texto_completo = ""
            for pagina in pdf.pages:
                texto_completo += pagina.extract_text() + "\n"

            ano = self.extrair_ano_referencia_robusto(texto_completo)
            if not ano:
                st.warning("Ano de referência não encontrado no documento.")
                return pd.DataFrame()

            for pagina_num, pagina in enumerate(pdf.pages, 1):
                tabelas = pagina.extract_tables()
                if not tabelas:
                    continue

                for tabela in tabelas:
                    if len(tabela) < 3:
                        continue

                    # Identificar colunas que contêm meses
                    meses_colunas = {}  # dicionário: indice_coluna -> número do mês
                    for i, linha in enumerate(tabela[:5]):  # olhar nas primeiras 5 linhas
                        for j, celula in enumerate(linha):
                            if celula:
                                celula_upper = str(celula).upper()
                                for mes_abrev, mes_num in self.meses_map.items():
                                    if mes_abrev in celula_upper:
                                        meses_colunas[j] = mes_num
                                        break
                        if meses_colunas:
                            break

                    if not meses_colunas:
                        continue  # página sem meses identificáveis

                    # Ordenar colunas de meses para garantir a ordem correta
                    colunas_meses = sorted(meses_colunas.items())  # lista de (indice, mes)

                    # Encontrar linhas de início de seção
                    inicio_rendimentos = None
                    inicio_descontos = None
                    for i, linha in enumerate(tabela):
                        linha_texto = ' '.join([str(c) for c in linha if c]).upper()
                        if 'RENDIMENTOS' in linha_texto:
                            inicio_rendimentos = i
                        elif 'DESCONTOS' in linha_texto:
                            inicio_descontos = i

                    # Processar rendimentos
                    if extrair_proventos and inicio_rendimentos is not None:
                        self._processar_secao_tabela(tabela, inicio_rendimentos + 1, inicio_descontos if inicio_descontos else len(tabela),
                                                      colunas_meses, ano, pagina_num, 'RENDIMENTO', dados)

                    # Processar descontos
                    if extrair_descontos and inicio_descontos is not None:
                        fim_descontos = len(tabela)
                        for i in range(inicio_descontos + 1, len(tabela)):
                            linha_texto = ' '.join([str(c) for c in tabela[i] if c]).upper()
                            if 'TOTAL' in linha_texto or 'RENDIMENTOS' in linha_texto:
                                fim_descontos = i
                                break
                        self._processar_secao_tabela(tabela, inicio_descontos + 1, fim_descontos,
                                                      colunas_meses, ano, pagina_num, 'DESCONTO', dados)

        if not dados:
            return pd.DataFrame(columns=['Discriminacao', 'Valor', 'Competencia', 'Pagina', 'Ano', 'Tipo'])

        df = pd.DataFrame(dados)

        # Remover registros com valor zero
        df = df[df['Valor'] != '0,00']

        # Adicionar numeração sequencial para rubricas com mesmo nome e mesma competência
        df['Sequencia'] = df.groupby(['Discriminacao', 'Competencia', 'Tipo']).cumcount() + 1
        df['Discriminacao_Original'] = df['Discriminacao']

        contagens = df.groupby(['Discriminacao_Original', 'Competencia', 'Tipo']).size().reset_index(name='Contagem')
        df = df.merge(contagens, on=['Discriminacao_Original', 'Competencia', 'Tipo'], how='left')

        df['Discriminacao'] = df.apply(
            lambda row: f"{row['Discriminacao_Original']} #{row['Sequencia']}" if row['Contagem'] > 1 else row['Discriminacao_Original'],
            axis=1
        )

        df = df[['Discriminacao', 'Valor', 'Competencia', 'Pagina', 'Ano', 'Tipo']]
        df = df.sort_values(['Ano', 'Pagina', 'Tipo', 'Discriminacao', 'Competencia']).reset_index(drop=True)
        return df

    def _processar_secao_tabela(self, tabela, linha_inicio, linha_fim, colunas_meses, ano, pagina, tipo, dados):
        """Processa uma seção da tabela (rendimentos ou descontos)"""
        for i in range(linha_inicio, linha_fim):
            linha = tabela[i]
            if not linha or not any(linha):
                continue

            # A primeira célula é a discriminação (se não estiver vazia)
            discriminacao = str(linha[0]).strip() if linha[0] else ""
            if not discriminacao or discriminacao.upper() in ['RENDIMENTOS', 'DESCONTOS', 'TOTAL', '']:
                continue

            # Para cada coluna de mês, extrair o valor
            for col_idx, mes_num in colunas_meses:
                if col_idx < len(linha) and linha[col_idx]:
                    valor_str = str(linha[col_idx]).strip()
                    if valor_str and re.match(r'^[\d\.,]+$', valor_str):
                        valor_float = self.converter_valor_string(valor_str)
                        if valor_float is not None and valor_float != 0:
                            competencia = f"{mes_num:02d}/{ano}"
                            dados.append({
                                'Discriminacao': discriminacao,
                                'Valor': valor_str,
                                'Competencia': competencia,
                                'Pagina': pagina,
                                'Ano': ano,
                                'Tipo': tipo
                            })
