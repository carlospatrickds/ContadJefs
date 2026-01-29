import streamlit as st
import pandas as pd
import pdfplumber
import re
from datetime import datetime
import io
import plotly.express as px
from typing import Optional

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
            
            # Tenta convertir diretamente
            return float(valor_str.replace(',', '.'))
        except:
            return None
    
    def extrair_ano_referencia_robusto(self, texto: str, pagina_num: int) -> Optional[str]:
        """
        Extrai o ano de referência do texto do demonstrativo de forma robusta
        """
        if not texto:
            return None
        
        # Dividir o texto em linhas para análise mais precisa
        linhas = texto.split('\n')
        
        # Padrão 1: Busca específica por "ANO REFERÊNCIA" exatamente como aparece nos demonstrativos
        for i, linha in enumerate(linhas):
            linha_limpa = linha.strip()
            
            # Padrão exato: "ANO REFERÊNCIA" seguido de ano
            padrao_exato = re.search(r'ANO\s+REFER[EÊ]NCIA\s*[:\s]*(\d{4})\b', linha_limpa, re.IGNORECASE)
            if padrao_exato:
                return padrao_exato.group(1)
            
            # Padrão alternativo: "ANO REFERÊNCIA" pode estar em uma linha e o ano na próxima
            if 'ANO REFER' in linha_limpa.upper():
                # Verificar próxima linha
                if i + 1 < len(linhas):
                    prox_linha = linhas[i + 1].strip()
                    ano_match = re.search(r'\b(\d{4})\b', prox_linha)
                    if ano_match:
                        return ano_match.group(1)
        
        # Padrão 2: Busca na seção de dados do servidor
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
                                return ano
        
        # Padrão 3: Se ainda não encontrou, buscar ano que não está perto de "EMITIDO EM"
        for linha in linhas:
            if 'EMITIDO' not in linha.upper() and 'DATA' not in linha.upper():
                ano_match = re.search(r'\b(20\d{2})\b', linha)
                if ano_match:
                    ano = ano_match.group(1)
                    # Validar que é um ano razoável (entre 2000 e ano atual + 1)
                    if 2000 <= int(ano) <= datetime.now().year + 1:
                        return ano
        
        return None
    
    def processar_pdf(self, pdf_file, extrair_proventos: bool = True, extrair_descontos: bool = True) -> pd.DataFrame:
        """
        Processa o PDF e extrai dados de acordo com as opções selecionadas
        """
        
        dados = []
        
        with pdfplumber.open(pdf_file) as pdf:
            for pagina_num, pagina in enumerate(pdf.pages, 1):
                # Extrair texto para análise
                texto = pagina.extract_text()
                
                if not texto or 'DEMONSTRATIVO' not in texto.upper():
                    continue
                
                # Extrair ano de referência
                ano = self.extrair_ano_referencia_robusto(texto, pagina_num)
                if not ano:
                    continue
                
                # Extrair tabelas da página
                tabelas = pagina.extract_tables()
                
                if not tabelas:
                    continue
                
                # Processar cada tabela encontrada
                for tabela in tabelas:
                    if not tabela or len(tabela) < 3:
                        continue
                    
                    # Procurar por linha que contém meses
                    meses_colunas = {}
                    
                    for linha in tabela:
                        if not linha:
                            continue
                        
                        linha_str = ' '.join([str(cell) for cell in linha if cell])
                        
                        # Verificar se esta linha contém meses
                        for mes_nome, mes_num in self.meses_map.items():
                            if mes_nome in linha_str.upper():
                                # Mapear colunas para meses
                                for col_idx, cell in enumerate(linha):
                                    if cell:
                                        cell_str = str(cell).strip().upper()
                                        for mn, mn_num in self.meses_map.items():
                                            if mn in cell_str:
                                                meses_colunas[col_idx] = mn_num
                                break
                        
                        if meses_colunas:
                            break
                    
                    if not meses_colunas:
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
                            self.processar_secao_tabela(
                                tabela, inicio_rendimentos, inicio_descontos,
                                meses_colunas, ano, pagina_num, 'RENDIMENTO'
                            )
                        )
                    
                    # Processar DESCONTOS se solicitado
                    if extrair_descontos and inicio_descontos is not None:
                        # Encontrar fim da seção DESCONTOS
                        fim_descontos = len(tabela)
                        for linha_idx in range(inicio_descontos + 1, len(tabela)):
                            linha_str = ' '.join([str(cell) for cell in tabela[linha_idx] if cell])
                            if 'TOTAL' in linha_str.upper() or 'RENDIMENTOS' in linha_str.upper():
                                fim_descontos = linha_idx
                                break
                        
                        dados.extend(
                            self.processar_secao_tabela(
                                tabela, inicio_descontos, fim_descontos,
                                meses_colunas, ano, pagina_num, 'DESCONTO'
                            )
                        )
        
        # Criar DataFrame
        if dados:
            df = pd.DataFrame(dados)
            df = df.drop_duplicates()
            df = df.sort_values(['Ano', 'Pagina', 'Tipo', 'Discriminacao'])
            return df
        else:
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

def inicializar_sessao():
    """Inicializa as variáveis de sessão se não existirem"""
    if 'dados_extraidos' not in st.session_state:
        st.session_state.dados_extraidos = None
    if 'df_filtrado' not in st.session_state:
        st.session_state.df_filtrado = None
    if 'arquivo_processado' not in st.session_state:
        st.session_state.arquivo_processado = None

def main():
    st.set_page_config(
        page_title="Extrator de Demonstrativos Financeiros",
        page_icon="📊",
        layout="wide"
    )
    
    st.title("📊 Extrator de Demonstrativos Financeiros")
    
    # Inicializar variáveis de sessão
    inicializar_sessao()
    
    # Upload do arquivo - SEMPRE visível
    st.subheader("📁 Upload do Arquivo")
    uploaded_file = st.file_uploader(
        "Faça upload do PDF com os demonstrativos",
        type="pdf",
        key="uploader_principal",
        help="O PDF deve conter tabelas com os dados financeiros"
    )
    
    # Se há arquivo carregado, mostrar opções de processamento
    if uploaded_file is not None:
        # Verificar se é um novo arquivo
        if (st.session_state.arquivo_processado is None or 
            st.session_state.arquivo_processado.name != uploaded_file.name):
            st.session_state.arquivo_processado = uploaded_file
            st.session_state.dados_extraidos = None
            st.session_state.df_filtrado = None
        
        st.success(f"✅ Arquivo carregado: {uploaded_file.name}")
        
        # Se ainda não processou ou é um novo arquivo, mostrar opções de processamento
        if st.session_state.dados_extraidos is None:
            st.subheader("⚙️ Opções de Extração")
            
            col1, col2 = st.columns(2)
            
            with col1:
                extrair_proventos = st.checkbox("Extrair RENDIMENTOS (Proventos)", value=True, key="extrair_proventos")
            
            with col2:
                extrair_descontos = st.checkbox("Extrair DESCONTOS", value=True, key="extrair_descontos")
            
            if not extrair_proventos and not extrair_descontos:
                st.warning("Selecione pelo menos um tipo de dado para extrair!")
            else:
                # Botão para processar
                if st.button("🔍 Processar Demonstrativos", type="primary", use_container_width=True):
                    with st.spinner("Processando PDF. Isso pode levar alguns instantes..."):
                        try:
                            # Inicializar extrator
                            extrator = ExtratorDemonstrativos()
                            
                            # Processar PDF
                            df = extrator.processar_pdf(
                                uploaded_file,
                                extrair_proventos=extrair_proventos,
                                extrair_descontos=extrair_descontos
                            )
                            
                            if not df.empty:
                                st.session_state.dados_extraidos = df
                                st.session_state.df_filtrado = df.copy()
                                st.success(f"✅ {len(df)} registros extraídos com sucesso!")
                                st.rerun()  # Recarregar para mostrar os dados
                            else:
                                st.error("⚠️ Nenhum dado foi extraído do PDF.")
                                
                        except Exception as e:
                            st.error(f"❌ Erro durante o processamento: {str(e)}")
        
        # Se já tem dados extraídos, mostrar interface de filtros e visualização
        if st.session_state.dados_extraidos is not None:
            # Usar o dataframe filtrado ou o original
            df = st.session_state.df_filtrado if st.session_state.df_filtrado is not None else st.session_state.dados_extraidos
            
            # Criar abas para diferentes funcionalidades
            tab1, tab2, tab3, tab4 = st.tabs([
                "📋 Dados", 
                "🎯 Filtros", 
                "📈 Gráficos", 
                "📥 Exportar"
            ])
            
            with tab1:
                # Mostrar estatísticas
                st.subheader("📊 Estatísticas")
                
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Total de Registros", len(df))
                with col2:
                    st.metric("Anos Encontrados", df['Ano'].nunique())
                with col3:
                    st.metric("Tipos de Rubricas", df['Discriminacao'].nunique())
                with col4:
                    st.metric("Páginas Processadas", df['Pagina'].nunique())
                
                # Mostrar dados
                st.subheader("📋 Dados Extraídos")
                st.dataframe(
                    df[['Discriminacao', 'Valor', 'Competencia', 'Ano', 'Tipo', 'Pagina']],
                    use_container_width=True,
                    hide_index=True,
                    height=400
                )
            
            with tab2:
                st.subheader("🎯 Filtros Avançados")
                
                # Filtro por tipo (RENDIMENTO/DESCONTO)
                st.write("**Filtrar por Tipo:**")
                tipos_disponiveis = sorted(df['Tipo'].unique())
                tipos_selecionados = st.multiselect(
                    "Selecione os tipos:",
                    tipos_disponiveis,
                    default=tipos_disponiveis,
                    key="filtro_tipo"
                )
                
                # Filtro por ano
                st.write("**Filtrar por Ano:**")
                anos_disponiveis = sorted(df['Ano'].unique())
                anos_selecionados = st.multiselect(
                    "Selecione os anos:",
                    anos_disponiveis,
                    default=anos_disponiveis,
                    key="filtro_ano"
                )
                
                # Filtro por rubricas específicas
                st.write("**Filtrar por Rubricas:**")
                rubricas_disponiveis = sorted(df['Discriminacao'].unique())
                rubricas_selecionadas = st.multiselect(
                    "Selecione as rubricas:",
                    rubricas_disponiveis,
                    default=rubricas_disponiveis[:min(10, len(rubricas_disponiveis))],
                    key="filtro_rubricas"
                )
                
                # Filtro por página
                st.write("**Filtrar por Página:**")
                paginas_disponiveis = sorted(df['Pagina'].unique())
                paginas_selecionadas = st.multiselect(
                    "Selecione as páginas:",
                    paginas_disponiveis,
                    default=paginas_disponiveis,
                    key="filtro_pagina"
                )
                
                # Botões de ação
                col_btn1, col_btn2 = st.columns(2)
                
                with col_btn1:
                    if st.button("✅ Aplicar Filtros", use_container_width=True, type="primary"):
                        # Aplicar filtros
                        df_filtrado = st.session_state.dados_extraidos.copy()
                        
                        if tipos_selecionados:
                            df_filtrado = df_filtrado[df_filtrado['Tipo'].isin(tipos_selecionados)]
                        
                        if anos_selecionados:
                            df_filtrado = df_filtrado[df_filtrado['Ano'].isin(anos_selecionados)]
                        
                        if rubricas_selecionadas:
                            df_filtrado = df_filtrado[df_filtrado['Discriminacao'].isin(rubricas_selecionadas)]
                        
                        if paginas_selecionadas:
                            df_filtrado = df_filtrado[df_filtrado['Pagina'].isin(paginas_selecionadas)]
                        
                        # Atualizar sessão
                        st.session_state.df_filtrado = df_filtrado
                        st.success(f"✅ Filtros aplicados! {len(df_filtrado)} registros visíveis.")
                        st.rerun()
                
                with col_btn2:
                    if st.button("🗑️ Limpar Filtros", use_container_width=True, type="secondary"):
                        # Limpar filtros
                        st.session_state.df_filtrado = st.session_state.dados_extraidos.copy()
                        st.success("✅ Filtros removidos!")
                        st.rerun()
                
                # Mostrar resumo dos filtros ativos
                if st.session_state.df_filtrado is not None and len(st.session_state.df_filtrado) != len(st.session_state.dados_extraidos):
                    st.info(f"""
                    **Filtros Ativos:**
                    - {len(st.session_state.df_filtrado)} de {len(st.session_state.dados_extraidos)} registros visíveis
                    - Tipos: {', '.join(tipos_selecionados)}
                    - Anos: {', '.join(map(str, anos_selecionados))}
                    - Rubricas selecionadas: {len(rubricas_selecionadas)}
                    - Páginas: {', '.join(map(str, paginas_selecionadas))}
                    """)
            
            with tab3:
                st.subheader("📈 Visualizações Gráficas")
                
                if not df.empty:
                    # Converter valores para numérico para gráficos
                    df_numeric = df.copy()
                    extrator = ExtratorDemonstrativos()
                    df_numeric['Valor_Numerico'] = df_numeric['Valor'].apply(
                        lambda x: extrator.converter_valor_string(x) or 0
                    )
                    
                    # Gráfico 1: Distribuição por Ano
                    st.write("### Distribuição por Ano")
                    ano_dist = df_numeric['Ano'].value_counts().sort_index()
                    st.bar_chart(ano_dist)
                    
                    # Gráfico 2: Distribuição por Tipo
                    st.write("### Distribuição por Tipo")
                    tipo_dist = df_numeric['Tipo'].value_counts()
                    st.bar_chart(tipo_dist)
                    
                    # Gráfico 3: Top 10 Rubricas (opcional)
                    if len(df_numeric['Discriminacao'].unique()) > 1:
                        st.write("### Top 10 Rubricas Mais Frequentes")
                        top_rubricas = df_numeric['Discriminacao'].value_counts().head(10)
                        st.bar_chart(top_rubricas)
                    
                    # Tabela de totais por ano e tipo
                    st.write("### Totais por Ano e Tipo")
                    totais = df_numeric.groupby(['Ano', 'Tipo'])['Valor_Numerico'].sum().reset_index()
                    totais['Valor_Formatado'] = totais['Valor_Numerico'].apply(extrator.formatar_valor_brasileiro)
                    st.dataframe(totais[['Ano', 'Tipo', 'Valor_Formatado']], use_container_width=True)
                else:
                    st.info("Nenhum dado disponível para visualização gráfica.")
            
            with tab4:
                st.subheader("📥 Exportação de Dados")
                
                # Opções de exportação
                formato = st.radio(
                    "Selecione o formato de exportação:",
                    ["CSV (Excel compatível)", "Excel (XLSX)"],
                    horizontal=True,
                    key="formato_export"
                )
                
                # Nome do arquivo
                nome_base = f"demonstrativos_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                
                # Botões de exportação
                col_exp1, col_exp2 = st.columns(2)
                
                with col_exp1:
                    if st.button("💾 Exportar como CSV", use_container_width=True):
                        csv = df.to_csv(index=False, sep=';', encoding='utf-8-sig')
                        st.download_button(
                            label="⬇️ Baixar CSV",
                            data=csv,
                            file_name=f"{nome_base}.csv",
                            mime="text/csv",
                            use_container_width=True
                        )
                
                with col_exp2:
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
                                    'Páginas Processadas'
                                ],
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
                        
                        excel_buffer.seek(0)
                        
                        st.download_button(
                            label="⬇️ Baixar Excel",
                            data=excel_buffer,
                            file_name=f"{nome_base}.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            use_container_width=True
                        )
                
                # Informações sobre a exportação
                st.info("""
                **Formato dos arquivos exportados:**
                - **CSV**: Separador ponto-e-vírgula (;), encoding UTF-8, compatível com Excel brasileiro
                - **Excel**: Inclui abas com dados e metadados
                - **Competência**: Formato MM/AAAA
                - **Valores**: Formato brasileiro (1.234,56)
                """)
            
            # Botão para processar novo arquivo (sempre visível)
            st.divider()
            if st.button("🔄 Processar Novo Arquivo", type="secondary"):
                # Limpar sessão
                st.session_state.dados_extraidos = None
                st.session_state.df_filtrado = None
                st.session_state.arquivo_processado = None
                st.rerun()
    
    else:
        # Tela inicial - instruções
        st.info("👆 Faça upload de um arquivo PDF para começar a extração.")
        
        with st.expander("ℹ️ Instruções de Uso"):
            st.markdown("""
            ### Passo a passo:
            
            1. **Faça upload do PDF** com os demonstrativos financeiros
            2. **Selecione** se quer extrair RENDIMENTOS e/ou DESCONTOS
            3. **Clique em "Processar Demonstrativos"**
            4. **Use os filtros** para refinar os dados
            5. **Exporte** no formato desejado
            
            ### Requisitos do PDF:
            - Deve conter texto selecionável
            - Deve ter "ANO REFERÊNCIA: XXXX" claramente
            - Tabelas com meses (JAN, FEV, MAR, etc.)
            - Seções de RENDIMENTOS e DESCONTOS
            - Valores no formato brasileiro: 1.234,56
            """)

if __name__ == "__main__":
    main()
