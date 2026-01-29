import streamlit as st
import pandas as pd
import pdfplumber
import re
from datetime import datetime
import io

def extrair_descontos_pdf_melhorado(pdf_file):
    """
    Extrai os descontos de um PDF de demonstrativos financeiros de forma robusta.
    """
    dados = []
    
    with pdfplumber.open(pdf_file) as pdf:
        for pagina_num, pagina in enumerate(pdf.pages, 1):
            texto = pagina.extract_text()
            
            if not texto:
                continue
            
            # Verificar se é uma página de demonstrativo
            if 'DEMONSTRATIVO' not in texto.upper():
                continue
            
            # Extrair ano de referência
            ano = None
            ano_match = re.search(r'ANO\s*REFERÊNCIA\s*(\d{4})', texto, re.IGNORECASE)
            if ano_match:
                ano = ano_match.group(1)
            
            # Se não encontrar pelo padrão, procurar por ano no texto
            if not ano:
                ano_match = re.search(r'(?:20\d{2})', texto)
                if ano_match:
                    ano = ano_match.group()
            
            if not ano:
                # Tentar obter do nome do arquivo ou usar ano atual
                ano = str(datetime.now().year)
            
            # Procurar por "DESCONTOS" no texto
            linhas = texto.split('\n')
            
            # Encontrar onde começa a seção de descontos
            desconto_start = False
            meses_encontrados = False
            
            # Mapear meses
            meses_map = {
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
            
            for linha_idx, linha in enumerate(linhas):
                linha_upper = linha.upper()
                
                # Verificar se encontrou cabeçalho de meses
                if any(mes in linha_upper for mes in meses_map.keys()):
                    meses_encontrados = True
                    continue
                
                # Verificar se é linha de descontos
                if 'DESCONTOS' in linha_upper and meses_encontrados:
                    desconto_start = True
                    continue
                
                # Se encontrou a próxima seção, parar
                if desconto_start and ('RENDIMENTOS' in linha_upper or 'TOTAL' in linha_upper):
                    break
                
                # Processar linhas de descontos
                if desconto_start and linha.strip():
                    # Limpar linha
                    linha_limpa = re.sub(r'\s+', ' ', linha.strip())
                    
                    # Verificar se contém valor monetário
                    # Padrão para valores brasileiros: 1.234,56 ou 12,34
                    padrao_valor = r'(\d{1,3}(?:\.\d{3})*,\d{2})'
                    valores = re.findall(padrao_valor, linha_limpa)
                    
                    if valores and len(valores) >= 6:  # Pelo menos 6 meses
                        # Extrair descrição (tudo antes do primeiro valor)
                        primeiro_valor_idx = linha_limpa.find(valores[0])
                        discriminacao = linha_limpa[:primeiro_valor_idx].strip()
                        
                        # Remover números ou símbolos no final da descrição
                        discriminacao = re.sub(r'[\d\.\,\-\s]+$', '', discriminacao).strip()
                        
                        # Para cada mês (primeiros 6 valores assumindo que são os meses)
                        for mes_idx, valor_str in enumerate(valores[:6]):
                            try:
                                # Converter para float
                                valor_float = float(valor_str.replace('.', '').replace(',', '.'))
                                
                                # Formatar para string brasileira
                                valor_formatado = f"{valor_float:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
                                
                                # Criar competência
                                # Assumir ordem: JAN, FEV, MAR, ABR, MAI, JUN
                                competencia = f"{mes_idx + 1:02d}/{ano}"
                                
                                # Adicionar aos dados
                                dados.append({
                                    'Discriminacao': discriminacao,
                                    'Valor': valor_formatado,
                                    'Competencia': competencia,
                                    'Pagina': pagina_num,
                                    'Ano': ano
                                })
                            except:
                                continue
                    elif valores and discriminacao:  # Se tiver menos valores
                        # Tentar extrai descrição de forma diferente
                        # Procurar por texto que não seja número
                        partes = re.split(r'\s+(\d[\d\.\,]*)', linha_limpa)
                        if len(partes) > 1:
                            discriminacao = partes[0].strip()
                            # Processar valores encontrados
                            for idx, parte in enumerate(partes[1:]):
                                if re.match(padrao_valor, parte.strip()) and idx < 6:
                                    try:
                                        valor_str = parte.strip()
                                        valor_float = float(valor_str.replace('.', '').replace(',', '.'))
                                        valor_formatado = f"{valor_float:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
                                        competencia = f"{idx + 1:02d}/{ano}"
                                        
                                        dados.append({
                                            'Discriminacao': discriminacao,
                                            'Valor': valor_formatado,
                                            'Competencia': competencia,
                                            'Pagina': pagina_num,
                                            'Ano': ano
                                        })
                                    except:
                                        continue
    
    # Criar DataFrame
    if dados:
        df = pd.DataFrame(dados)
        # Remover duplicados
        df = df.drop_duplicates()
        # Ordenar
        df = df.sort_values(['Pagina', 'Discriminacao', 'Competencia'])
        return df
    else:
        return pd.DataFrame(columns=['Discriminacao', 'Valor', 'Competencia', 'Pagina', 'Ano'])

def extrair_via_tabelas(pdf_file):
    """
    Extrai descontos usando extração de tabelas do pdfplumber
    """
    dados = []
    
    with pdfplumber.open(pdf_file) as pdf:
        for pagina_num, pagina in enumerate(pdf.pages, 1):
            # Extrair todas as tabelas da página
            tabelas = pagina.extract_tables()
            
            if not tabelas:
                continue
            
            # Procurar por tabela que contenha dados financeiros
            for tabela in tabelas:
                if not tabela or len(tabela) < 5:
                    continue
                
                # Procurar por linha com descontos
                for linha_idx, linha in enumerate(tabela):
                    if not linha:
                        continue
                    
                    # Converter linha para string para verificação
                    linha_str = ' '.join([str(cell) for cell in linha if cell])
                    
                    if 'DESCONTOS' in linha_str.upper():
                        # Encontrar ano
                        ano = None
                        for cell in linha:
                            if cell and isinstance(cell, str):
                                ano_match = re.search(r'(\d{4})', cell)
                                if ano_match:
                                    ano = ano_match.group(1)
                                    break
                        
                        if not ano:
                            # Procurar em células anteriores
                            for prev_linha in tabela[:linha_idx]:
                                for cell in prev_linha:
                                    if cell and isinstance(cell, str):
                                        ano_match = re.search(r'ANO.*?(\d{4})', cell, re.IGNORECASE)
                                        if ano_match:
                                            ano = ano_match.group(1)
                                            break
                                if ano:
                                    break
                        
                        if not ano:
                            ano = str(datetime.now().year)
                        
                        # Processar linhas após DESCONTOS
                        for desc_linha in tabela[linha_idx + 1:]:
                            if not desc_linha or not any(desc_linha):
                                continue
                            
                            # Verificar se é fim da seção
                            desc_linha_str = ' '.join([str(cell) for cell in desc_linha if cell])
                            if 'TOTAL' in desc_linha_str.upper() or 'RENDIMENTOS' in desc_linha_str.upper():
                                break
                            
                            # Extrair descrição (primeira célula não numérica)
                            discriminacao = None
                            for cell in desc_linha:
                                if cell and cell.strip():
                                    cell_str = str(cell).strip()
                                    # Verificar se não é apenas número
                                    if not re.match(r'^[\d\.,]+$', cell_str):
                                        discriminacao = cell_str
                                        break
                            
                            if not discriminacao:
                                continue
                            
                            # Extrair valores
                            valores = []
                            for cell in desc_linha:
                                if cell and cell.strip():
                                    cell_str = str(cell).strip()
                                    # Verificar se é valor monetário
                                    if re.match(r'^[\d\.,]+$', cell_str):
                                        valores.append(cell_str)
                            
                            # Adicionar para cada mês (primeiros 6 valores)
                            for mes_idx, valor_str in enumerate(valores[:6]):
                                try:
                                    valor_str_limpo = re.sub(r'[^\d,]', '', valor_str)
                                    if valor_str_limpo:
                                        valor_float = float(valor_str_limpo.replace('.', '').replace(',', '.'))
                                        valor_formatado = f"{valor_float:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
                                        competencia = f"{mes_idx + 1:02d}/{ano}"
                                        
                                        dados.append({
                                            'Discriminacao': discriminacao,
                                            'Valor': valor_formatado,
                                            'Competencia': competencia,
                                            'Pagina': pagina_num,
                                            'Ano': ano
                                        })
                                except:
                                    continue
                        
                        break  # Sair após processar esta tabela
    
    if dados:
        df = pd.DataFrame(dados)
        df = df.drop_duplicates()
        df = df.sort_values(['Pagina', 'Discriminacao', 'Competencia'])
        return df
    else:
        return pd.DataFrame(columns=['Discriminacao', 'Valor', 'Competencia', 'Pagina', 'Ano'])

def main():
    st.set_page_config(
        page_title="Extrator de Descontos",
        page_icon="📄",
        layout="wide"
    )
    
    st.title("📄 Extrator de Descontos - Demonstrativos Financeiros")
    
    st.markdown("""
    ### Instruções:
    1. Faça upload do PDF contendo os demonstrativos financeiros
    2. Selecione o método de extração
    3. Visualize e baixe os dados extraídos
    """)
    
    # Upload do arquivo
    uploaded_file = st.file_uploader(
        "Escolha o arquivo PDF", 
        type="pdf",
        help="Selecione o PDF com os demonstrativos financeiros"
    )
    
    if uploaded_file is not None:
        st.success("✅ Arquivo carregado com sucesso!")
        
        # Método de extração
        metodo = st.radio(
            "Selecione o método de extração:",
            ["Método 1: Análise de Texto", "Método 2: Extração de Tabelas", "Método 3: Combinado"],
            horizontal=True
        )
        
        # Botão para processar
        if st.button("🔍 Processar PDF", type="primary"):
            with st.spinner("Processando PDF. Aguarde..."):
                try:
                    if "Análise de Texto" in metodo:
                        df = extrair_descontos_pdf_melhorado(uploaded_file)
                    elif "Extração de Tabelas" in metodo:
                        df = extrair_via_tabelas(uploaded_file)
                    else:
                        # Combinar ambos os métodos
                        df1 = extrair_descontos_pdf_melhorado(uploaded_file)
                        df2 = extrair_via_tabelas(uploaded_file)
                        df = pd.concat([df1, df2], ignore_index=True)
                        df = df.drop_duplicates()
                    
                    if not df.empty:
                        st.success(f"✅ {len(df)} registros extraídos com sucesso!")
                        
                        # Criar abas para visualização
                        tab1, tab2, tab3 = st.tabs(["📊 Dados Extraídos", "📈 Estatísticas", "⚙️ Configurações"])
                        
                        with tab1:
                            # Mostrar dados
                            st.dataframe(
                                df,
                                use_container_width=True,
                                hide_index=True
                            )
                            
                            # Resumo
                            st.subheader("Resumo")
                            col1, col2, col3, col4 = st.columns(4)
                            with col1:
                                st.metric("Total de Registros", len(df))
                            with col2:
                                st.metric("Páginas", df['Pagina'].nunique())
                            with col3:
                                st.metric("Anos", df['Ano'].nunique())
                            with col4:
                                st.metric("Tipos de Desconto", df['Discriminacao'].nunique())
                        
                        with tab2:
                            # Estatísticas detalhadas
                            st.subheader("Estatísticas por Ano")
                            anos_counts = df['Ano'].value_counts().sort_index()
                            st.bar_chart(anos_counts)
                            
                            st.subheader("Top 10 Descontos mais comuns")
                            top_descontos = df['Discriminacao'].value_counts().head(10)
                            st.dataframe(top_descontos)
                            
                            st.subheader("Distribuição por Página")
                            pagina_counts = df['Pagina'].value_counts().sort_index()
                            st.bar_chart(pagina_counts)
                        
                        with tab3:
                            # Filtros
                            st.subheader("Filtrar Dados")
                            
                            col1, col2 = st.columns(2)
                            
                            with col1:
                                anos_unicos = sorted(df['Ano'].unique())
                                anos_selecionados = st.multiselect(
                                    "Filtrar por Ano:",
                                    anos_unicos,
                                    default=anos_unicos
                                )
                            
                            with col2:
                                paginas_unicas = sorted(df['Pagina'].unique())
                                paginas_selecionadas = st.multiselect(
                                    "Filtrar por Página:",
                                    paginas_unicas,
                                    default=paginas_unicas
                                )
                            
                            # Aplicar filtros
                            if anos_selecionados or paginas_selecionadas:
                                df_filtrado = df.copy()
                                if anos_selecionados:
                                    df_filtrado = df_filtrado[df_filtrado['Ano'].isin(anos_selecionados)]
                                if paginas_selecionadas:
                                    df_filtrado = df_filtrado[df_filtrado['Pagina'].isin(paginas_selecionadas)]
                                
                                st.dataframe(df_filtrado, use_container_width=True)
                                df = df_filtrado
                        
                        # Opções de download
                        st.divider()
                        st.subheader("📥 Download dos Dados")
                        
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            # CSV
                            csv = df.to_csv(index=False, sep=';', encoding='utf-8-sig')
                            st.download_button(
                                label="Baixar como CSV (UTF-8)",
                                data=csv,
                                file_name="descontos_extraidos.csv",
                                mime="text/csv",
                                help="Formato CSV com encoding UTF-8 e separador ponto-e-vírgula"
                            )
                        
                        with col2:
                            # Excel
                            excel_buffer = io.BytesIO()
                            with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                                df.to_excel(writer, index=False, sheet_name='Descontos')
                                # Adicionar resumo
                                resumo = pd.DataFrame({
                                    'Metrica': ['Total Registros', 'Páginas', 'Anos', 'Tipos Desconto'],
                                    'Valor': [len(df), df['Pagina'].nunique(), df['Ano'].nunique(), df['Discriminacao'].nunique()]
                                })
                                resumo.to_excel(writer, index=False, sheet_name='Resumo')
                            excel_buffer.seek(0)
                            
                            st.download_button(
                                label="Baixar como Excel",
                                data=excel_buffer,
                                file_name="descontos_extraidos.xlsx",
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                help="Arquivo Excel com duas abas: Dados e Resumo"
                            )
                        
                        # Mostrar amostra dos dados
                        st.divider()
                        st.subheader("🎯 Amostra dos Dados Formatados")
                        
                        amostra = df.head(10).copy()
                        amostra_display = amostra[['Discriminacao', 'Valor', 'Competencia', 'Pagina']]
                        
                        st.table(amostra_display)
                        
                    else:
                        st.warning("⚠️ Nenhum desconto foi encontrado no PDF.")
                        st.info("""
                        **Sugestões:**
                        1. Tente outro método de extração
                        2. Verifique se o PDF contém texto selecionável
                        3. Confira se o formato segue o padrão de demonstrativos
                        """)
                        
                except Exception as e:
                    st.error(f"❌ Erro ao processar o arquivo: {str(e)}")
                    
                    # Informações para debug
                    with st.expander("🔧 Detalhes do Erro (para desenvolvedor)"):
                        st.code(f"""
                        Tipo de erro: {type(e).__name__}
                        Mensagem: {str(e)}
                        
                        Se o problema persistir:
                        1. Verifique o formato do PDF
                        2. Teste com um arquivo menor
                        3. Entre em contato com suporte
                        """)
    else:
        # Tela inicial
        st.info("👆 Faça upload de um arquivo PDF para começar.")
        
        # Exemplo de formato esperado
        with st.expander("📋 Formato Esperado do PDF"):
            st.markdown("""
            O PDF deve conter tabelas no seguinte formato:
            
            ```
            | DESCRIÇÃO       | JAN      | FEV      | MAR      | ... | TOTAL   |
            |-----------------|----------|----------|----------|-----|---------|
            | DESCONTOS       |          |          |          |     |         |
            | Empréstimo XYZ  | 100,00   | 100,00   | 100,00   | ... | 600,00  |
            | Imposto ABC     | 50,00    | 50,00    | 50,00    | ... | 300,00  |
            ```
            
            **Características importantes:**
            - Texto selecionável (não é imagem)
            - Contém a palavra "DESCONTOS"
            - Tem colunas para meses (JAN, FEV, etc.)
            - Valores no formato brasileiro (1.234,56)
            """)

if __name__ == "__main__":
    main()
