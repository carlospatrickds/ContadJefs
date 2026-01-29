import streamlit as st
import pandas as pd
import pdfplumber
import re
from datetime import datetime
import io
from typing import List, Dict, Tuple, Optional

class ExtratorDemonstrativos:
    """Classe para extrair dados de demonstrativos financeiros em PDF"""
    
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
        """Formata valor float para string no padrão brasileiro 1.234,56"""
        return f"{valor:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
    
    def converter_valor_string(self, valor_str: str) -> Optional[float]:
        """Converte string de valor brasileiro para float"""
        try:
            # Remove caracteres não numéricos exceto ponto e vírgula
            valor_str = re.sub(r'[^\d,\.]', '', str(valor_str))
            
            # Se terminar com vírgula seguida de 1 ou 2 dígitos, assume ser decimal
            if re.match(r'^\d+,\d{1,2}$', valor_str):
                return float(valor_str.replace('.', '').replace(',', '.'))
            
            # Se tiver ponto como separador de milhar e vírgula como decimal
            if re.match(r'^\d{1,3}(?:\.\d{3})*,\d{2}$', valor_str):
                return float(valor_str.replace('.', '').replace(',', '.'))
            
            # Tenta converter diretamente
            return float(valor_str.replace(',', '.'))
        except:
            return None
    
    def extrair_ano_referencia(self, texto: str) -> Optional[str]:
        """Extrai o ano de referência do texto do demonstrativo"""
        
        # Padrão 1: "ANO REFERÊNCIA" seguido de ano
        padrao1 = re.search(r'ANO\s*REFER[EÊ]NCIA\s*[:\s]*(\d{4})', texto, re.IGNORECASE)
        if padrao1:
            return padrao1.group(1)
        
        # Padrão 2: "ANO:" seguido de ano
        padrao2 = re.search(r'ANO\s*[:\s]*(\d{4})', texto, re.IGNORECASE)
        if padrao2:
            return padrao2.group(1)
        
        # Padrão 3: Ano próximo a dados de banco/agência
        padrao3 = re.search(r'(?:BANCO|AG[EÊ]NCIA|CONTA).*?(\d{4})', texto, re.IGNORECASE)
        if padrao3:
            return padrao3.group(1)
        
        # Padrão 4: Qualquer ano 20xx que não seja data de emissão
        # Evita pegar ano de emissão (geralmente após "EMITIDO EM")
        linhas = texto.split('\n')
        for linha in linhas:
            if 'EMITIDO' not in linha.upper() and 'DATA' not in linha.upper():
                ano_match = re.search(r'\b(20\d{2})\b', linha)
                if ano_match:
                    return ano_match.group(1)
        
        return None
    
    def identificar_meses_colunas(self, linha: str) -> Dict[int, str]:
        """Identifica quais meses estão presentes nos cabeçalhos das colunas"""
        meses_encontrados = {}
        
        for mes_nome, mes_num in self.meses_map.items():
            if mes_nome in linha.upper():
                # Encontrar posição do mês na linha
                pos = linha.upper().find(mes_name)
                # Tentar determinar índice da coluna (simplificado)
                # Na prática, precisaríamos mapear posições nas tabelas extraídas
                meses_encontrados[mes_num] = mes_nome
        
        return meses_encontrados
    
    def processar_pdf(self, pdf_file, extrair_proventos: bool = True, extrair_descontos: bool = True) -> pd.DataFrame:
        """
        Processa o PDF e extrai dados de acordo com as opções selecionadas
        
        Args:
            pdf_file: Arquivo PDF
            extrair_proventos: Se True, extrai rubricas de RENDIMENTOS
            extrair_descontos: Se True, extrai rubricas de DESCONTOS
            
        Returns:
            DataFrame com colunas: Discriminacao, Valor, Competencia, Pagina, Ano, Tipo
        """
        
        dados = []
        
        with pdfplumber.open(pdf_file) as pdf:
            for pagina_num, pagina in enumerate(pdf.pages, 1):
                # Extrair texto para análise
                texto = pagina.extract_text()
                
                if not texto or 'DEMONSTRATIVO' not in texto.upper():
                    continue
                
                # Extrair ano de referência
                ano = self.extrair_ano_referencia(texto)
                if not ano:
                    st.warning(f"Não foi possível identificar o ano de referência na página {pagina_num}")
                    continue
                
                # Extrair tabelas da página
                tabelas = pagina.extract_tables()
                
                if not tabelas:
                    continue
                
                # Processar cada tabela encontrada
                for tabela_idx, tabela in enumerate(tabelas):
                    if not tabela or len(tabela) < 3:
                        continue
                    
                    # Encontrar cabeçalhos de meses na tabela
                    cabecalho_meses = None
                    meses_colunas = {}  # Mapeia índice da coluna para número do mês
                    
                    for linha_idx, linha in enumerate(tabela):
                        if not linha:
                            continue
                        
                        linha_str = ' '.join([str(cell) for cell in linha if cell])
                        
                        # Verificar se esta linha contém meses
                        if any(mes in linha_str.upper() for mes in self.meses_map.keys()):
                            cabecalho_meses = linha
                            # Mapear colunas para meses
                            for col_idx, cell in enumerate(linha):
                                if cell:
                                    cell_str = str(cell).strip().upper()
                                    for mes_nome, mes_num in self.meses_map.items():
                                        if mes_nome in cell_str:
                                            meses_colunas[col_idx] = mes_num
                            break
                    
                    if not cabecalho_meses or not meses_colunas:
                        continue
                    
                    # Encontrar seções de RENDIMENTOS e DESCONTOS
                    inicio_rendimentos = None
                    inicio_descontos = None
                    
                    for linha_idx, linha in enumerate(tabela):
                        if not linha:
                            continue
                        
                        linha_str = ' '.join([str(cell) for cell in linha if cell])
                        
                        if 'RENDIMENTOS' in linha_str.upper() and inicio_rendimentos is None:
                            inicio_rendimentos = linha_idx
                        elif 'DESCONTOS' in linha_str.upper() and inicio_descontos is None:
                            inicio_descontos = linha_idx
                    
                    # Processar RENDIMENTOS se solicitado
                    if extrair_proventos and inicio_rendimentos is not None:
                        dados.extend(
                            self.processar_secao(
                                tabela, inicio_rendimentos, inicio_descontos,
                                meses_colunas, ano, pagina_num, 'RENDIMENTO'
                            )
                        )
                    
                    # Processar DESCONTOS se solicitado
                    if extrair_descontos and inicio_descontos is not None:
                        # Encontrar fim da seção (próxima seção ou fim da tabela)
                        fim_descontos = len(tabela)
                        for linha_idx in range(inicio_descontos + 1, len(tabela)):
                            linha_str = ' '.join([str(cell) for cell in tabela[linha_idx] if cell])
                            if 'TOTAL' in linha_str.upper() or 'RENDIMENTOS' in linha_str.upper():
                                fim_descontos = linha_idx
                                break
                        
                        dados.extend(
                            self.processar_secao(
                                tabela, inicio_descontos, fim_descontos,
                                meses_colunas, ano, pagina_num, 'DESCONTO'
                            )
                        )
        
        # Criar DataFrame
        if dados:
            df = pd.DataFrame(dados)
            df = df.drop_duplicates()
            df = df.sort_values(['Ano', 'Pagina', 'Tipo', 'Discriminacao', 'Competencia'])
            return df
        else:
            return pd.DataFrame(columns=['Discriminacao', 'Valor', 'Competencia', 'Pagina', 'Ano', 'Tipo'])
    
    def processar_secao(self, tabela, inicio_secao, fim_secao, meses_colunas, ano, pagina_num, tipo):
        """Processa uma seção específica (RENDIMENTOS ou DESCONTOS)"""
        dados_secao = []
        
        # Pular a linha do título da seção
        for linha_idx in range(inicio_secao + 1, fim_secao):
            linha = tabela[linha_idx]
            
            if not linha or not any(linha):
                continue
            
            # Verificar se é início de nova seção
            linha_str = ' '.join([str(cell) for cell in linha if cell])
            if 'RENDIMENTOS' in linha_str.upper() or 'DESCONTOS' in linha_str.upper() or 'TOTAL' in linha_str.upper():
                break
            
            # Extrair descrição da rubrica
            discriminacao = None
            for cell in linha:
                if cell and cell.strip():
                    cell_str = str(cell).strip()
                    # Não pegar células que são apenas números ou datas
                    if not re.match(r'^[\d\.,]+$', cell_str) and not any(mes in cell_str.upper() for mes in self.meses_map.keys()):
                        discriminacao = cell_str
                        break
            
            if not discriminacao:
                continue
            
            # Extrair valores para cada mês
            for col_idx, mes_num in meses_colunas.items():
                if col_idx < len(linha) and linha[col_idx]:
                    valor_str = str(linha[col_idx]).strip()
                    
                    # Verificar se é um valor monetário
                    if re.match(r'^[\d\.,]+$', valor_str):
                        valor_float = self.converter_valor_string(valor_str)
                        
                        if valor_float is not None and valor_float != 0:
                            valor_formatado = self.formatar_valor_brasileiro(valor_float)
                            competencia = f"{mes_num:02d}/{ano}"
                            
                            dados_secao.append({
                                'Discriminacao': discriminacao,
                                'Valor': valor_formatado,
                                'Competencia': competencia,
                                'Pagina': pagina_num,
                                'Ano': ano,
                                'Tipo': tipo
                            })
        
        return dados_secao

def main():
    st.set_page_config(
        page_title="Extrator de Demonstrativos Financeiros",
        page_icon="📊",
        layout="wide"
    )
    
    st.title("📊 Extrator Inteligente de Demonstrativos Financeiros")
    
    st.markdown("""
    ### Extraia automaticamente dados de demonstrativos financeiros em PDF
    
    **Funcionalidades:**
    - Extrai **RENDIMENTOS** e **DESCONTOS**
    - Identifica automaticamente o **ano de referência**
    - Filtra por rubricas específicas
    - Exporta para CSV e Excel
    - Suporte a PDFs com múltiplas páginas
    """)
    
    # Inicializar extrator
    extrator = ExtratorDemonstrativos()
    
    # Upload do arquivo
    uploaded_file = st.file_uploader(
        "📁 Faça upload do PDF com os demonstrativos",
        type="pdf",
        help="O PDF deve conter tabelas com os dados financeiros"
    )
    
    if uploaded_file is not None:
        # Configurações de extração
        st.subheader("⚙️ Configurações de Extração")
        
        col1, col2 = st.columns(2)
        
        with col1:
            extrair_proventos = st.checkbox("Extrair RENDIMENTOS (Proventos)", value=True)
        
        with col2:
            extrair_descontos = st.checkbox("Extrair DESCONTOS", value=True)
        
        if not extrair_proventos and not extrair_descontos:
            st.warning("Selecione pelo menos um tipo de dado para extrair!")
            return
        
        # Botão para processar
        if st.button("🔍 Processar Demonstrativos", type="primary", use_container_width=True):
            with st.spinner("Processando PDF. Isso pode levar alguns instantes..."):
                try:
                    # Processar PDF
                    df = extrator.processar_pdf(
                        uploaded_file,
                        extrair_proventos=extrair_proventos,
                        extrair_descontos=extrair_descontos
                    )
                    
                    if not df.empty:
                        st.success(f"✅ {len(df)} registros extraídos com sucesso!")
                        
                        # Criar abas para diferentes visualizações
                        tab1, tab2, tab3, tab4 = st.tabs([
                            "📋 Dados Extraídos", 
                            "🎯 Filtros Avançados", 
                            "📈 Estatísticas", 
                            "⚙️ Configurações"
                        ])
                        
                        with tab1:
                            # Mostrar dados
                            st.dataframe(
                                df[['Discriminacao', 'Valor', 'Competencia', 'Ano', 'Tipo', 'Pagina']],
                                use_container_width=True,
                                hide_index=True
                            )
                            
                            # Resumo rápido
                            st.subheader("📊 Resumo da Extração")
                            
                            col1, col2, col3, col4 = st.columns(4)
                            with col1:
                                st.metric("Total de Registros", len(df))
                            with col2:
                                st.metric("Anos Encontrados", df['Ano'].nunique())
                            with col3:
                                st.metric("Tipos de Rubricas", df['Discriminacao'].nunique())
                            with col4:
                                st.metric("Páginas Processadas", df['Pagina'].nunique())
                        
                        with tab2:
                            st.subheader("🎯 Filtrar por Rubricas Específicas")
                            
                            # Lista de rubricas únicas
                            rubricas_unicas = sorted(df['Discriminacao'].unique())
                            
                            # Seleção múltipla de rubricas
                            rubricas_selecionadas = st.multiselect(
                                "Selecione as rubricas que deseja incluir:",
                                rubricas_unicas,
                                default=rubricas_unicas[:min(10, len(rubricas_unicas))]  # Primeiras 10 por padrão
                            )
                            
                            # Filtros adicionais
                            col1, col2, col3 = st.columns(3)
                            
                            with col1:
                                anos_unicos = sorted(df['Ano'].unique())
                                anos_selecionados = st.multiselect(
                                    "Filtrar por Ano:",
                                    anos_unicos,
                                    default=anos_unicos
                                )
                            
                            with col2:
                                tipos_unicos = sorted(df['Tipo'].unique())
                                tipos_selecionados = st.multiselect(
                                    "Filtrar por Tipo:",
                                    tipos_unicos,
                                    default=tipos_unicos
                                )
                            
                            with col3:
                                paginas_unicas = sorted(df['Pagina'].unique())
                                paginas_selecionadas = st.multiselect(
                                    "Filtrar por Página:",
                                    paginas_unicas,
                                    default=paginas_unicas
                                )
                            
                            # Aplicar filtros
                            df_filtrado = df.copy()
                            
                            if rubricas_selecionadas:
                                df_filtrado = df_filtrado[df_filtrado['Discriminacao'].isin(rubricas_selecionadas)]
                            
                            if anos_selecionados:
                                df_filtrado = df_filtrado[df_filtrado['Ano'].isin(anos_selecionados)]
                            
                            if tipos_selecionados:
                                df_filtrado = df_filtrado[df_filtrado['Tipo'].isin(tipos_selecionados)]
                            
                            if paginas_selecionadas:
                                df_filtrado = df_filtrado[df_filtrado['Pagina'].isin(paginas_selecionadas)]
                            
                            # Mostrar dados filtrados
                            if not df_filtrado.empty:
                                st.info(f"Mostrando {len(df_filtrado)} registros filtrados")
                                st.dataframe(
                                    df_filtrado[['Discriminacao', 'Valor', 'Competencia', 'Ano', 'Tipo']],
                                    use_container_width=True,
                                    hide_index=True
                                )
                                
                                # Atualizar df para usar os dados filtrados nas exportações
                                df = df_filtrado
                            else:
                                st.warning("Nenhum registro encontrado com os filtros selecionados.")
                        
                        with tab3:
                            st.subheader("📈 Análise Estatística")
                            
                            # Estatísticas por ano
                            st.write("### Distribuição por Ano")
                            ano_counts = df['Ano'].value_counts().sort_index()
                            st.bar_chart(ano_counts)
                            
                            # Estatísticas por tipo
                            st.write("### Distribuição por Tipo")
                            tipo_counts = df['Tipo'].value_counts()
                            st.bar_chart(tipo_counts)
                            
                            # Top rubricas
                            st.write("### Top 10 Rubricas Mais Frequentes")
                            top_rubricas = df['Discriminacao'].value_counts().head(10)
                            st.dataframe(top_rubricas, use_container_width=True)
                            
                            # Valores totais por ano
                            st.write("### Valores Totais por Ano")
                            # Converter valores para numérico para soma
                            df_numeric = df.copy()
                            df_numeric['Valor_Numerico'] = df_numeric['Valor'].apply(
                                lambda x: extrator.converter_valor_string(x) or 0
                            )
                            
                            totais_ano = df_numeric.groupby(['Ano', 'Tipo'])['Valor_Numerico'].sum().reset_index()
                            totais_ano['Valor'] = totais_ano['Valor_Numerico'].apply(extrator.formatar_valor_brasileiro)
                            st.dataframe(totais_ano[['Ano', 'Tipo', 'Valor']], use_container_width=True)
                        
                        with tab4:
                            st.subheader("⚙️ Configurações de Exportação")
                            
                            # Opções de formatação
                            formato_exportacao = st.radio(
                                "Formato de exportação:",
                                ["CSV (Excel compatível)", "Excel (XLSX)"]
                            )
                            
                            incluir_metadados = st.checkbox(
                                "Incluir página de metadados no Excel",
                                value=True
                            )
                        
                        # Seção de download
                        st.divider()
                        st.subheader("📥 Download dos Dados")
                        
                        col_d1, col_d2 = st.columns(2)
                        
                        with col_d1:
                            # Download CSV
                            if st.button("💾 Baixar como CSV", use_container_width=True):
                                csv = df.to_csv(index=False, sep=';', encoding='utf-8-sig')
                                
                                st.download_button(
                                    label="⬇️ Clique para baixar CSV",
                                    data=csv,
                                    file_name=f"demonstrativos_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                                    mime="text/csv",
                                    use_container_width=True
                                )
                        
                        with col_d2:
                            # Download Excel
                            if st.button("📊 Baixar como Excel", use_container_width=True):
                                excel_buffer = io.BytesIO()
                                
                                with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                                    # Dados principais
                                    df.to_excel(writer, index=False, sheet_name='Dados')
                                    
                                    # Metadados (se solicitado)
                                    if incluir_metadados:
                                        metadados = pd.DataFrame({
                                            'Parâmetro': ['Data de Extração', 'Arquivo Original', 'Total Registros', 
                                                         'Anos Extraídos', 'Rubricas Extraídas', 'Páginas Processadas'],
                                            'Valor': [
                                                datetime.now().strftime('%d/%m/%Y %H:%M:%S'),
                                                uploaded_file.name,
                                                len(df),
                                                ', '.join(sorted(df['Ano'].unique())),
                                                df['Discriminacao'].nunique(),
                                                ', '.join(map(str, sorted(df['Pagina'].unique())))
                                            ]
                                        })
                                        metadados.to_excel(writer, index=False, sheet_name='Metadados')
                                        
                                        # Resumo por ano e tipo
                                        resumo = df.groupby(['Ano', 'Tipo']).size().reset_index(name='Quantidade')
                                        resumo.to_excel(writer, index=False, sheet_name='Resumo')
                                
                                excel_buffer.seek(0)
                                
                                st.download_button(
                                    label="⬇️ Clique para baixar Excel",
                                    data=excel_buffer,
                                    file_name=f"demonstrativos_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                    use_container_width=True
                                )
                        
                        # Amostra dos dados no formato final
                        st.divider()
                        st.subheader("🎯 Amostra dos Dados no Formato Final")
                        
                        amostra = df.head(10).copy()
                        amostra_display = amostra[['Discriminacao', 'Valor', 'Competencia', 'Ano', 'Tipo']]
                        
                        # Estilizar a tabela de amostra
                        st.table(amostra_display.style.set_properties(**{
                            'text-align': 'left',
                            'white-space': 'nowrap'
                        }))
                        
                    else:
                        st.warning("⚠️ Nenhum dado foi extraído do PDF.")
                        st.info("""
                        **Possíveis causas:**
                        1. O PDF não contém tabelas no formato esperado
                        2. As tabelas não estão sendo detectadas corretamente
                        3. O ano de referência não foi identificado
                        4. As seções RENDIMENTOS/DESCONTOS não foram encontradas
                        
                        **Sugestões:**
                        - Verifique se o PDF contém texto selecionável
                        - Confirme se o formato segue o padrão de demonstrativos
                        - Tente um arquivo de exemplo
                        """)
                        
                except Exception as e:
                    st.error(f"❌ Erro durante o processamento: {str(e)}")
                    
                    # Informações detalhadas para debug
                    with st.expander("🔧 Detalhes Técnicos do Erro"):
                        st.code(f"""
                        Tipo de erro: {type(e).__name__}
                        
                        Mensagem completa:
                        {str(e)}
                        
                        Para relatar este problema:
                        1. Verifique se o PDF está corrompido
                        2. Tente com um arquivo menor
                        3. Entre em contato com suporte técnico
                        """)
    
    else:
        # Tela inicial - instruções
        st.info("👆 Faça upload de um arquivo PDF para começar a extração.")
        
        # Exemplos e instruções
        with st.expander("📋 Formato Esperado do PDF"):
            st.markdown("""
            ### Estrutura esperada dos demonstrativos:
            
            **Cabeçalho (informações do servidor):**
            ```
            NOME DO SERVIDOR: GERSON JOSE DE SOUZA MENDES
            MAT. SIAPE: 675733
            ANO REFERÊNCIA: 2020
            ```
            
            **Tabela de dados:**
            ```
            | DISCRIMINAÇÃO                | JAN      | FEV      | MAR      | ... | TOTAL   |
            |------------------------------|----------|----------|----------|-----|---------|
            | **RENDIMENTOS**              |          |          |          |     |         |
            | PROVENTO BASICO              | 4.872,00 | 4.872,00 | 4.872,00 | ... |         |
            | ANUÊNIO-ART.244,LEI 8112/90  | 1.071,84 | 1.071,84 | 1.071,84 | ... |         |
            |                              |          |          |          |     |         |
            | **DESCONTOS**                |          |          |          |     |         |
            | EMPREST BCO PRIVADOS - ITAU  | 67,15    | 67,15    | 67,15    | ... |         |
            | IMPOSTO DE RENDA             | 1.229,77 | 1.229,77 | 1.211,10 | ... |         |
            ```
            
            **Características importantes:**
            - PDF com texto selecionável (não é imagem escaneada)
            - Contém as palavras **RENDIMENTOS** e **DESCONTOS**
            - Colunas para cada mês (JAN, FEV, MAR, etc.)
            - Valores no formato brasileiro (1.234,56)
            - Ano de referência identificável
            """)
        
        with st.expander("🎯 Dicas para Melhor Extração"):
            st.markdown("""
            1. **Verifique a qualidade do PDF**: Certifique-se de que o texto é selecionável
            2. **Formato consistente**: Os demonstrativos devem seguir um padrão similar
            3. **Ano de referência**: Deve estar claro no documento
            4. **Teste com amostra**: Comece com um arquivo pequeno para validar
            5. **Use os filtros**: Após extrair, use os filtros para refinar os dados
            """)

if __name__ == "__main__":
    main()
