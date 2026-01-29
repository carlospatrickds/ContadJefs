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
    
    def extrair_ano_referencia_robusto(self, texto: str, pagina_num: int) -> Optional[str]:
        """
        Extrai o ano de referência do texto do demonstrativo de forma robusta
        
        IMPORTANTE: Procura especificamente pelo padrão 'ANO REFERÊNCIA' seguido do ano
        e ignora completamente qualquer outra data no documento
        """
        if not texto:
            return None
        
        # Dividir o texto em linhas para análise mais precisa
        linhas = texto.split('\n')
        
        # Padrão 1: Busca específica por "ANO REFERÊNCIA" exatamente como aparece nos demonstrativos
        # Vamos buscar linha por linha para maior precisão
        for i, linha in enumerate(linhas):
            linha_limpa = linha.strip()
            
            # Padrão exato: "ANO REFERÊNCIA" seguido de ano
            padrao_exato = re.search(r'ANO\s+REFER[EÊ]NCIA\s*[:\s]*(\d{4})\b', linha_limpa, re.IGNORECASE)
            if padrao_exato:
                ano = padrao_exato.group(1)
                st.info(f"Página {pagina_num}: Ano de referência encontrado: {ano} (padrão exato)")
                return ano
            
            # Padrão alternativo: "ANO REFERÊNCIA" pode estar em uma linha e o ano na próxima
            if 'ANO REFER' in linha_limpa.upper():
                # Verificar próxima linha
                if i + 1 < len(linhas):
                    prox_linha = linhas[i + 1].strip()
                    ano_match = re.search(r'\b(\d{4})\b', prox_linha)
                    if ano_match:
                        ano = ano_match.group(1)
                        st.info(f"Página {pagina_num}: Ano de referência encontrado: {ano} (padrão em duas linhas)")
                        return ano
        
        # Padrão 2: Busca na seção de dados do servidor (onde estão BANCO, AGÊNCIA, CONTA)
        # Esses dados geralmente aparecem juntos
        for i in range(len(linhas)):
            linha_atual = ' '.join(linhas[max(0, i-2):min(len(linhas), i+3)]).upper()
            
            # Se encontrar palavras-chave da seção de dados
            if any(palavra in linha_atual for palavra in ['BANCO', 'AGÊNCIA', 'CONTA', 'MATRICULA', 'SIAPE']):
                # Procurar por ano nesta região
                for j in range(max(0, i-3), min(len(linhas), i+4)):
                    linha_ano = linhas[j].strip()
                    # Procurar por padrão de 4 dígitos (ano) após palavras-chave
                    if re.search(r'\b(20\d{2})\b', linha_ano):
                        ano_match = re.search(r'\b(20\d{2})\b', linha_ano)
                        if ano_match:
                            ano = ano_match.group(1)
                            # Validar que não é data de emissão
                            if 'EMITIDO' not in linha_ano.upper() and 'DATA' not in linha_ano.upper():
                                st.info(f"Página {pagina_num}: Ano de referência encontrado: {ano} (na seção de dados)")
                                return ano
        
        # Padrão 3: Se ainda não encontrou, buscar ano que não está perto de "EMITIDO EM"
        for linha in linhas:
            if 'EMITIDO' not in linha.upper() and 'DATA' not in linha.upper():
                ano_match = re.search(r'\b(20\d{2})\b', linha)
                if ano_match:
                    ano = ano_match.group(1)
                    # Validar que é um ano razoável (entre 2000 e ano atual + 1)
                    if 2000 <= int(ano) <= datetime.now().year + 1:
                        st.warning(f"Página {pagina_num}: Ano presumido: {ano} (busca genérica)")
                        return ano
        
        st.error(f"Página {pagina_num}: Não foi possível identificar o ano de referência")
        return None
    
    def identificar_meses_colunas(self, linha: str) -> Dict[int, str]:
        """Identifica quais meses estão presentes nos cabeçalhos das colunas"""
        meses_encontrados = {}
        
        for mes_nome, mes_num in self.meses_map.items():
            if mes_nome in linha.upper():
                # Encontrar posição do mês na linha
                pos = linha.upper().find(mes_nome)
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
        anos_por_pagina = {}
        
        with pdfplumber.open(pdf_file) as pdf:
            for pagina_num, pagina in enumerate(pdf.pages, 1):
                # Extrair texto para análise
                texto = pagina.extract_text()
                
                if not texto or 'DEMONSTRATIVO' not in texto.upper():
                    st.warning(f"Página {pagina_num}: Não é uma página de demonstrativo")
                    continue
                
                # Extrair ano de referência de forma robusta
                ano = self.extrair_ano_referencia_robusto(texto, pagina_num)
                if not ano:
                    st.warning(f"Página {pagina_num}: Pulando página - ano não identificado")
                    continue
                
                anos_por_pagina[pagina_num] = ano
                
                # DEBUG: Mostrar informações da página
                with st.expander(f"🔍 Debug Página {pagina_num} - Ano: {ano}", expanded=False):
                    st.text(f"Primeiras 500 caracteres:\n{texto[:500]}...")
                
                # Extrair tabelas da página
                tabelas = pagina.extract_tables()
                
                if not tabelas:
                    st.warning(f"Página {pagina_num}: Nenhuma tabela encontrada")
                    continue
                
                st.info(f"Página {pagina_num}: {len(tabelas)} tabela(s) encontrada(s)")
                
                # Processar cada tabela encontrada
                for tabela_idx, tabela in enumerate(tabelas):
                    if not tabela or len(tabela) < 3:
                        continue
                    
                    # DEBUG: Mostrar estrutura da tabela
                    with st.expander(f"📊 Tabela {tabela_idx+1} da Página {pagina_num}", expanded=False):
                        st.write(f"Tabela com {len(tabela)} linhas")
                        # Mostrar primeiras 5 linhas para debug
                        for i, linha in enumerate(tabela[:5]):
                            st.write(f"Linha {i}: {linha}")
                    
                    # Procurar por linha que contém meses
                    cabecalho_meses_idx = None
                    meses_colunas = {}  # Mapeia índice da coluna para número do mês
                    
                    for linha_idx, linha in enumerate(tabela):
                        if not linha:
                            continue
                        
                        linha_str = ' '.join([str(cell) for cell in linha if cell])
                        
                        # Verificar se esta linha contém meses
                        for mes_nome, mes_num in self.meses_map.items():
                            if mes_nome in linha_str.upper():
                                cabecalho_meses_idx = linha_idx
                                # Mapear colunas para meses
                                for col_idx, cell in enumerate(linha):
                                    if cell:
                                        cell_str = str(cell).strip().upper()
                                        for mn, mn_num in self.meses_map.items():
                                            if mn in cell_str:
                                                meses_colunas[col_idx] = mn_num
                                break
                        
                        if cabecalho_meses_idx is not None:
                            break
                    
                    if not meses_colunas:
                        st.warning(f"Página {pagina_num}, Tabela {tabela_idx+1}: Cabeçalho de meses não encontrado")
                        continue
                    
                    st.success(f"Página {pagina_num}: Encontrados meses: {list(meses_colunas.values())}")
                    
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
                        dados_secao = self.processar_secao_tabela(
                            tabela, inicio_rendimentos, inicio_descontos,
                            meses_colunas, ano, pagina_num, 'RENDIMENTO'
                        )
                        dados.extend(dados_secao)
                        st.success(f"Página {pagina_num}: {len(dados_secao)} registros de RENDIMENTOS extraídos")
                    
                    # Processar DESCONTOS se solicitado
                    if extrair_descontos and inicio_descontos is not None:
                        # Encontrar fim da seção DESCONTOS
                        fim_descontos = len(tabela)
                        for linha_idx in range(inicio_descontos + 1, len(tabela)):
                            linha_str = ' '.join([str(cell) for cell in tabela[linha_idx] if cell])
                            if 'TOTAL' in linha_str.upper() or 'RENDIMENTOS' in linha_str.upper():
                                fim_descontos = linha_idx
                                break
                        
                        dados_secao = self.processar_secao_tabela(
                            tabela, inicio_descontos, fim_descontos,
                            meses_colunas, ano, pagina_num, 'DESCONTO'
                        )
                        dados.extend(dados_secao)
                        st.success(f"Página {pagina_num}: {len(dados_secao)} registros de DESCONTOS extraídos")
        
        # Criar DataFrame
        if dados:
            df = pd.DataFrame(dados)
            
            # Remover duplicados
            df = df.drop_duplicates()
            
            # Ordenar
            df = df.sort_values(['Ano', 'Pagina', 'Tipo', 'Discriminacao'])
            
            # Log de resumo
            st.success(f"✅ Processamento concluído!")
            st.info(f"""
            **Resumo da Extração:**
            - Total de registros: {len(df)}
            - Páginas processadas: {len(anos_por_pagina)}
            - Anos encontrados: {sorted(df['Ano'].unique())}
            - Tipos de rubricas: {df['Discriminacao'].nunique()}
            """)
            
            return df
        else:
            st.error("Nenhum dado foi extraído do PDF")
            return pd.DataFrame(columns=['Discriminacao', 'Valor', 'Competencia', 'Pagina', 'Ano', 'Tipo'])
    
    def processar_secao_tabela(self, tabela, inicio_secao, fim_secao, meses_colunas, ano, pagina_num, tipo):
        """Processa uma seção específica (RENDIMENTOS ou DESCONTOS) de uma tabela"""
        dados_secao = []
        
        # Iniciar após o título da seção
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
                    if (not re.match(r'^[\d\.,]+$', cell_str) and 
                        not any(mes in cell_str.upper() for mes in self.meses_map.keys()) and
                        cell_str not in ['RENDIMENTOS', 'DESCONTOS']):
                        discriminacao = cell_str
                        break
            
            if not discriminacao:
                continue
            
            # Extrair valores para cada mês
            for col_idx, mes_num in meses_colunas.items():
                if col_idx < len(linha) and linha[col_idx]:
                    valor_str = str(linha[col_idx]).strip()
                    
                    # Verificar se é um valor monetário
                    if re.match(r'^[\d\.,\s]+$', valor_str):
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
    - Identifica automaticamente o **ano de referência** correto
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
        st.success(f"✅ Arquivo carregado: {uploaded_file.name}")
        
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
                        # Criar abas para diferentes visualizações
                        tab1, tab2, tab3 = st.tabs([
                            "📋 Dados Extraídos", 
                            "🎯 Filtros Avançados", 
                            "📥 Exportação"
                        ])
                        
                        with tab1:
                            # Mostrar estatísticas iniciais
                            st.subheader("📊 Estatísticas da Extração")
                            
                            col_stat1, col_stat2, col_stat3, col_stat4 = st.columns(4)
                            with col_stat1:
                                st.metric("Total de Registros", len(df))
                            with col_stat2:
                                st.metric("Anos Encontrados", df['Ano'].nunique())
                            with col_stat3:
                                st.metric("Tipos de Rubricas", df['Discriminacao'].nunique())
                            with col_stat4:
                                st.metric("Páginas Processadas", df['Pagina'].nunique())
                            
                            # Distribuição por ano
                            st.subheader("📈 Distribuição por Ano")
                            ano_dist = df['Ano'].value_counts().sort_index()
                            st.bar_chart(ano_dist)
                            
                            # Mostrar dados
                            st.subheader("📋 Dados Extraídos")
                            st.dataframe(
                                df[['Discriminacao', 'Valor', 'Competencia', 'Ano', 'Tipo', 'Pagina']],
                                use_container_width=True,
                                hide_index=True,
                                height=400
                            )
                        
                        with tab2:
                            st.subheader("🎯 Filtrar por Rubricas Específicas")
                            
                            # Lista de rubricas únicas
                            rubricas_unicas = sorted(df['Discriminacao'].unique())
                            
                            # Seleção múltipla de rubricas
                            rubricas_selecionadas = st.multiselect(
                                "Selecione as rubricas que deseja incluir:",
                                rubricas_unicas,
                                default=rubricas_unicas[:min(5, len(rubricas_unicas))]  # Primeiras 5 por padrão
                            )
                            
                            # Filtros adicionais
                            col_filt1, col_filt2, col_filt3 = st.columns(3)
                            
                            with col_filt1:
                                anos_unicos = sorted(df['Ano'].unique())
                                anos_selecionados = st.multiselect(
                                    "Filtrar por Ano:",
                                    anos_unicos,
                                    default=anos_unicos
                                )
                            
                            with col_filt2:
                                tipos_unicos = sorted(df['Tipo'].unique())
                                tipos_selecionados = st.multiselect(
                                    "Filtrar por Tipo:",
                                    tipos_unicos,
                                    default=tipos_unicos
                                )
                            
                            with col_filt3:
                                paginas_unicas = sorted(df['Pagina'].unique())
                                paginas_selecionadas = st.multiselect(
                                    "Filtrar por Página:",
                                    paginas_unicas,
                                    default=paginas_unicas
                                )
                            
                            # Aplicar filtros
                            df_filtrado = df.copy()
                            
                            aplicar_filtros = st.button("Aplicar Filtros", type="secondary")
                            
                            if aplicar_filtros:
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
                                    st.success(f"✅ {len(df_filtrado)} registros após filtragem")
                                    st.dataframe(
                                        df_filtrado[['Discriminacao', 'Valor', 'Competencia', 'Ano', 'Tipo']],
                                        use_container_width=True,
                                        hide_index=True
                                    )
                                    
                                    # Atualizar df para usar os dados filtrados nas exportações
                                    df = df_filtrado
                                else:
                                    st.warning("⚠️ Nenhum registro encontrado com os filtros selecionados.")
                        
                        with tab3:
                            st.subheader("📥 Exportação dos Dados")
                            
                            # Opções de formatação
                            formato_exportacao = st.radio(
                                "Formato de exportação:",
                                ["CSV (Excel compatível)", "Excel (XLSX)"],
                                horizontal=True
                            )
                            
                            # Mostrar amostra do formato de exportação
                            st.subheader("📋 Amostra dos Dados para Exportação")
                            st.dataframe(
                                df.head(10)[['Discriminacao', 'Valor', 'Competencia', 'Ano', 'Tipo']],
                                use_container_width=True,
                                hide_index=True
                            )
                            
                            # Botões de exportação
                            col_exp1, col_exp2 = st.columns(2)
                            
                            with col_exp1:
                                # Download CSV
                                if st.button("💾 Exportar como CSV", use_container_width=True):
                                    csv = df.to_csv(index=False, sep=';', encoding='utf-8-sig')
                                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                                    
                                    st.download_button(
                                        label="⬇️ Baixar Arquivo CSV",
                                        data=csv,
                                        file_name=f"demonstrativos_{timestamp}.csv",
                                        mime="text/csv",
                                        use_container_width=True
                                    )
                            
                            with col_exp2:
                                # Download Excel
                                if st.button("📊 Exportar como Excel", use_container_width=True):
                                    excel_buffer = io.BytesIO()
                                    
                                    with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                                        # Dados principais
                                        df.to_excel(writer, index=False, sheet_name='Dados')
                                        
                                        # Metadados
                                        metadados = pd.DataFrame({
                                            'Parâmetro': [
                                                'Data de Extração', 
                                                'Arquivo Original', 
                                                'Total de Registros',
                                                'Anos Extraídos', 
                                                'Rubricas Extraídas', 
                                                'Páginas Processadas',
                                                'Data Início', 
                                                'Data Fim'
                                            ],
                                            'Valor': [
                                                datetime.now().strftime('%d/%m/%Y %H:%M:%S'),
                                                uploaded_file.name,
                                                len(df),
                                                ', '.join(sorted(df['Ano'].unique())),
                                                df['Discriminacao'].nunique(),
                                                ', '.join(map(str, sorted(df['Pagina'].unique()))),
                                                df['Competencia'].min(),
                                                df['Competencia'].max()
                                            ]
                                        })
                                        metadados.to_excel(writer, index=False, sheet_name='Metadados')
                                    
                                    excel_buffer.seek(0)
                                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                                    
                                    st.download_button(
                                        label="⬇️ Baixar Arquivo Excel",
                                        data=excel_buffer,
                                        file_name=f"demonstrativos_{timestamp}.xlsx",
                                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                        use_container_width=True
                                    )
                            
                            # Informações sobre a exportação
                            st.info("""
                            **Formato dos arquivos exportados:**
                            - **CSV**: Separador ponto-e-vírgula (;), encoding UTF-8
                            - **Excel**: Inclui abas com dados e metadados
                            - **Competência**: Formato MM/AAAA
                            - **Valores**: Formato brasileiro (1.234,56)
                            """)
                    
                    else:
                        st.error("⚠️ Nenhum dado foi extraído do PDF.")
                        
                except Exception as e:
                    st.error(f"❌ Erro durante o processamento: {str(e)}")
                    
                    # Informações detalhadas para debug
                    with st.expander("🔧 Detalhes Técnicos do Erro"):
                        st.code(f"""
                        Tipo de erro: {type(e).__name__}
                        
                        Mensagem completa:
                        {str(e)}
                        
                        Para solucionar:
                        1. Verifique se o PDF contém tabelas legíveis
                        2. Confirme que há texto selecionável
                        3. Teste com um arquivo de exemplo
                        """)
    
    else:
        # Tela inicial - instruções
        st.info("👆 Faça upload de um arquivo PDF para começar a extração.")
        
        with st.expander("ℹ️ Instruções Importantes"):
            st.markdown("""
            ### Para garantir a extração correta:
            
            1. **Certifique-se que o PDF contém texto selecionável**
               - Não funcione com PDFs escaneados/imagens
               - Teste selecionando texto no PDF
            
            2. **Verifique a estrutura dos demonstrativos**
               - Deve conter "ANO REFERÊNCIA: XXXX" claramente
               - Tabelas com meses (JAN, FEV, MAR, etc.)
               - Seções de RENDIMENTOS e DESCONTOS
            
            3. **Formato dos valores**
               - Devem estar no formato brasileiro: 1.234,56
               - Separador de milhar: ponto (.)
               - Separador decimal: vírgula (,)
            
            4. **Ano de referência**
               - O sistema busca por "ANO REFERÊNCIA"
               - Não usa a data de emissão
               - Cada página pode ter um ano diferente
            """)

if __name__ == "__main__":
    main()
