import streamlit as st
import pandas as pd
import pdfplumber
import re
from io import BytesIO
from datetime import datetime

# ------------------------------------------------------------
# Funções de conversão
# ------------------------------------------------------------

def converter_competencia(competencia):
    """Converte competência no formato 'MM/AAAA' para data válida"""
    try:
        # Remove caracteres que não são números ou barra
        competencia = re.sub(r'[^0-9/]', '', str(competencia))
        
        if '/' in competencia:
            mes, ano = competencia.split('/')
            
            # Garante que o mês tem 2 dígitos e o ano tem 4
            mes = mes.zfill(2)
            if len(ano) == 2:
                ano = '20' + ano if int(ano) <= 50 else '19' + ano
            
            # Criar data no primeiro dia do mês
            data = datetime.strptime(f'01/{mes}/{ano}', '%d/%m/%Y')
            return data
            
    except Exception as e:
        print(f"Erro ao converter competência {competencia}: {e}")
    
    return None

def formatar_salario_para_float(salario_str):
    """Converte string de salário no formato brasileiro para float."""
    if isinstance(salario_str, (int, float)):
        return float(salario_str)
    
    if not isinstance(salario_str, str):
        return None

    # Remove o R$ e espaços
    salario_str = salario_str.replace('R$', '').replace(' ', '').strip()
    
    # Remove pontos (separadores de milhar) e converte vírgula decimal para ponto
    if '.' in salario_str and ',' in salario_str:
        # Formato: 1.326,01 -> remove ponto, troca vírgula por ponto
        salario_str = salario_str.replace('.', '').replace(',', '.')
    elif ',' in salario_str:
        # Formato: 326,01 -> troca vírgula por ponto
        salario_str = salario_str.replace(',', '.')
    
    try:
        return float(salario_str)
    except ValueError:
        return None

# ------------------------------------------------------------
# Funções de extração de dados - MODELO 1 (Específico para o PDF fornecido)
# ------------------------------------------------------------

def extract_data_from_pdf_model1(pdf_file):
    """Extrai dados do PDF do Modelo 1 (Específico para a estrutura do PDF fornecido)."""
    st.info("Modelo 1 selecionado: Extração específica para estrutura de tabela do PDF.")
    data = []
    
    # Resetar o ponteiro do arquivo
    pdf_file.seek(0)

    with pdfplumber.open(pdf_file) as pdf:
        for page_num, page in enumerate(pdf.pages):
            # Extrai o texto completo da página
            text = page.extract_text()
            
            if not text:
                continue
                
            # Divide o texto em linhas
            lines = text.split('\n')
            
            # Procura pelas linhas que contêm dados de contribuição
            for line_num, line in enumerate(lines):
                line = line.strip()
                if not line:
                    continue
                
                # Padrão para identificar linhas com dados: número + data (MM/AAAA) + valores
                # Exemplo: "001 07/1994 R$ 309,24 582,86 309,24 7,521684 R$ 2.326,01"
                pattern = r'^\s*(\d{2,3})\s+(\d{1,2}/\d{4})\s+R\$\s*([\d\.,]+)\s+([\d\.,]+)\s+([\d\.,]+)\s+([\d\.,]+)\s+R\$\s*([\d\.,]+)'
                match = re.search(pattern, line)
                
                if match:
                    numero, competencia, salario_contribuicao, teto, salario_considerado, indice, salario_corrigido = match.groups()
                    
                    # Processa o registro
                    salario_float = formatar_salario_para_float(salario_contribuicao)
                    competencia_data = converter_competencia(competencia)
                    
                    if salario_float is not None and competencia_data is not None:
                        data.append({
                            'Modelo': "Modelo 1",
                            'Competencia_Original': competencia,
                            'Data': competencia_data,
                            'Ano_Mes': competencia_data.strftime('%Y-%m'),
                            'Salario_Contribuicao': salario_float,
                            'Pagina': page_num + 1,
                            'Linha': line_num + 1
                        })
    
    return pd.DataFrame(data)

# ------------------------------------------------------------
# Funções de extração de dados - MODELO 2 (Extração de Tabelas Estruturadas)
# ------------------------------------------------------------

def extract_data_from_pdf_model2(pdf_file):
    """Extrai dados do PDF do Modelo 2 (Extração de Tabelas Estruturadas)."""
    st.info("Modelo 2 selecionado: Extração via Tabela Estruturada.")
    data = []
    
    pdf_file.seek(0)

    with pdfplumber.open(pdf_file) as pdf:
        for page_num, page in enumerate(pdf.pages):
            # Tenta extrair tabelas
            tables = page.extract_tables()
            
            for table_num, table in enumerate(tables):
                if not table or len(table) < 2:
                    continue

                # Procura pela linha de cabeçalho que contém "Data" e "Salário"
                for i, row in enumerate(table):
                    if not row:
                        continue
                        
                    row_text = ' '.join([str(cell) if cell else '' for cell in row]).lower()
                    
                    if 'data' in row_text and any(word in row_text for word in ['salário', 'salario', 'contribuição']):
                        # Encontra os índices das colunas
                        data_col_index = -1
                        salario_col_index = -1
                        
                        for j, cell in enumerate(row):
                            if cell and 'data' in str(cell).lower():
                                data_col_index = j
                            if cell and any(word in str(cell).lower() for word in ['salário', 'salario', 'contribuição']):
                                salario_col_index = j
                        
                        # Processa as linhas seguintes
                        for k in range(i + 1, len(table)):
                            row_data = table[k]
                            if (row_data and len(row_data) > max(data_col_index, salario_col_index) and
                                data_col_index != -1 and salario_col_index != -1):
                                
                                competencia = row_data[data_col_index]
                                salario = row_data[salario_col_index]
                                
                                if competencia and salario:
                                    salario_float = formatar_salario_para_float(str(salario))
                                    competencia_data = converter_competencia(str(competencia))
                                    
                                    if salario_float is not None and competencia_data is not None:
                                        data.append({
                                            'Modelo': "Modelo 2",
                                            'Competencia_Original': str(competencia),
                                            'Data': competencia_data,
                                            'Ano_Mes': competencia_data.strftime('%Y-%m'),
                                            'Salario_Contribuicao': salario_float,
                                            'Pagina': page_num + 1,
                                            'Tabela': table_num + 1
                                        })
                        break
    
    return pd.DataFrame(data)

# ------------------------------------------------------------
# Interface Streamlit
# ------------------------------------------------------------

def main():
    st.title("📊 Leitor de Planilhas de Salários de Contribuição")
    st.write("Faça upload do arquivo PDF e selecione o modelo de extração para obter os dados.")
    
    # Seletor do modelo de planilha
    extraction_model = st.radio(
        "Selecione o Modelo de Planilha PDF:",
        ["Modelo 1 (Extração Específica)", "Modelo 2 (Tabela Estruturada)"],
        index=0,
        help="Modelo 1 é otimizado para a estrutura do PDF fornecido. Modelo 2 usa detecção genérica de tabelas."
    )

    # Upload do arquivo
    uploaded_file = st.file_uploader("Escolha o arquivo PDF", type="pdf")
    
    if uploaded_file is not None:
        try:
            # Selecionar a função de extração
            if "Modelo 1" in extraction_model:
                extraction_func = extract_data_from_pdf_model1
            else:
                extraction_func = extract_data_from_pdf_model2

            # Extrair dados do PDF
            with st.spinner(f"Processando arquivo PDF com {extraction_model}..."):
                df = extraction_func(uploaded_file)
            
            if not df.empty:
                st.success(f"✅ Dados extraídos com sucesso! **{len(df)} registros** encontrados.")
                
                # Ordenar por data
                df = df.sort_values('Data').reset_index(drop=True)

                # Mostrar estatísticas detalhadas
                st.subheader("📈 Estatísticas da Extração")
                
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.metric("Total de Registros", len(df))
                
                with col2:
                    st.metric("Período Inicial", df['Competencia_Original'].iloc[0])
                
                with col3:
                    st.metric("Período Final", df['Competencia_Original'].iloc[-1])
                
                with col4:
                    total_salarios = df['Salario_Contribuicao'].sum()
                    st.metric("Soma dos Salários", f"R$ {total_salarios:,.2f}")

                # Mostrar preview dos dados com opção de ver mais
                st.subheader("👀 Prévia dos Dados")
                
                # Opção para mostrar mais linhas
                show_all = st.checkbox("Mostrar todos os registros", value=False)
                
                df_display = df.copy()
                if 'Data' in df_display.columns and pd.api.types.is_datetime64_any_dtype(df_display['Data']):
                    df_display['Data'] = df_display['Data'].dt.strftime('%d/%m/%Y')
                
                # Selecionar colunas para exibir
                display_cols = ['Competencia_Original', 'Data', 'Salario_Contribuicao']
                if 'Pagina' in df_display.columns:
                    display_cols.append('Pagina')
                
                if show_all:
                    st.dataframe(df_display[display_cols], use_container_width=True)
                else:
                    # Mostrar primeiros e últimos 10 registros
                    st.write("**Primeiros 10 registros:**")
                    st.dataframe(df_display[display_cols].head(10), use_container_width=True)
                    
                    st.write("**Últimos 10 registros:**")
                    st.dataframe(df_display[display_cols].tail(10), use_container_width=True)
                
                # Opções de exportação
                st.subheader("💾 Opções de Exportação")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    formato_data = st.radio(
                        "Formato da competência no Excel:",
                        ["Data Completa", "Ano-Mês", "Original"],
                        key="formato_data_radio"
                    )
                
                data_col_map = {
                    "Data Completa": "Data",
                    "Ano-Mês": "Ano_Mes",
                    "Original": "Competencia_Original"
                }
                coluna_data_selecionada = data_col_map[formato_data]
                
                default_cols = [coluna_data_selecionada, "Salario_Contribuicao"]
                
                all_cols_options = ["Competencia_Original", "Data", "Ano_Mes", "Salario_Contribuicao", "Modelo", "Pagina"]
                
                with col2:
                    incluir_colunas = st.multiselect(
                        "Colunas a incluir:",
                        all_cols_options,
                        default=default_cols,
                        key="incluir_colunas_multiselect"
                    )
                
                # Preparar dados para exportação
                df_export = df[incluir_colunas].copy()
                
                # Renomear a coluna de competência selecionada para "Competencia"
                if coluna_data_selecionada in df_export.columns and coluna_data_selecionada != "Competencia":
                    df_export = df_export.rename(columns={coluna_data_selecionada: 'Competencia'})
                
                # Exportação para Excel
                st.subheader("📥 Exportar para Excel")
                
                output = BytesIO()
                
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    # Se exportando com datas, converter para formato de data pura (sem hora)
                    if 'Data' in df_export.columns:
                        # Criar uma cópia para exportação com datas formatadas como string no formato brasileiro
                        df_export_excel = df_export.copy()
                        df_export_excel['Data'] = df_export_excel['Data'].dt.strftime('%d/%m/%Y')
                        df_export_excel.to_excel(writer, sheet_name='Salarios_Contribuicao', index=False)
                    else:
                        df_export.to_excel(writer, sheet_name='Salarios_Contribuicao', index=False)
                    
                    workbook = writer.book
                    worksheet = writer.sheets['Salarios_Contribuicao']
                    
                    # Formatar coluna de salário como moeda brasileira
                    if 'Salario_Contribuicao' in df_export.columns:
                        salario_col_idx = df_export.columns.get_loc('Salario_Contribuicao')
                        for row in range(2, len(df_export) + 2):
                            worksheet.cell(row=row, column=salario_col_idx + 1).number_format = '#,##0.00'
                    
                    # Se estiver exportando a coluna Data, formatar como data brasileira
                    if 'Data' in df_export.columns:
                        data_col_idx = df_export.columns.get_loc('Data')
                        for row in range(2, len(df_export) + 2):
                            cell = worksheet.cell(row=row, column=data_col_idx + 1)
                            cell.number_format = 'DD/MM/YYYY'  # Formato apenas de data, sem hora
                
                excel_data = output.getvalue()
                
                st.download_button(
                    label="📥 Baixar Planilha Excel",
                    data=excel_data,
                    file_name="salarios_contribuicao.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
                
                # Mostrar informações detalhadas
                with st.expander("🔍 Detalhes da Extração"):
                    st.write("**Resumo dos dados:**")
                    st.write(f"- Total de registros extraídos: {len(df)}")
                    st.write(f"- Período coberto: {df['Competencia_Original'].iloc[0]} a {df['Competencia_Original'].iloc[-1]}")
                    st.write(f"- Valor médio: R$ {df['Salario_Contribuicao'].mean():.2f}")
                    st.write(f"- Valor máximo: R$ {df['Salario_Contribuicao'].max():.2f}")
                    st.write(f"- Valor mínimo: R$ {df['Salario_Contribuicao'].min():.2f}")
                    
            else:
                st.error("❌ Nenhum dado foi extraído com sucesso. Tente o outro modelo de extração.")
                
        except Exception as e:
            st.error(f"❌ Erro ao processar o arquivo: {str(e)}")
            st.info("💡 Dica: Verifique se o PDF não está corrompido e tente o outro modelo de extração.")
            
    # Instruções
    with st.expander("ℹ️ Instruções de Uso"):
        st.markdown("""
        ### 📋 Modelos de Extração:
        
        **Modelo 1 (Extração Específica):**
        - ✅ **Recomendado para o PDF fornecido**
        - Otimizado para a estrutura específica da tabela
        - Procura por padrões como: `"001 07/1994 R$ 309,24 582,86 309,24 7,521684 R$ 2.326,01"`
        
        **Modelo 2 (Tabela Estruturada):**
        - Abordagem genérica para extração de tabelas
        - Funciona bem com PDFs que têm estrutura de tabela clara
        
        ### 💡 Dicas:
        - Se um modelo não funcionar, tente o outro
        - Verifique sempre o total de registros extraídos
        - Use a opção "Mostrar todos os registros" para verificar dados completos
        - O download em Excel mantém a formatação correta de datas (apenas data, sem hora)
        """)

if __name__ == "__main__":
    main()
