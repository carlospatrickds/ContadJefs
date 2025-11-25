import streamlit as st
import pandas as pd
import pdfplumber
import re
from io import BytesIO
from datetime import datetime
from openpyxl.styles import numbers

# ------------------------------------------------------------
# Funções de conversão
# ------------------------------------------------------------

def converter_competencia(competencia):
    """Converte competência no formato 'MM/AAAA' para data válida"""
    try:
        # Remove R$ e caracteres que não são da competência
        competencia = re.sub(r'[^0-9/]', '', competencia)
        
        if '/' in competencia:
            mes, ano = competencia.split('/')
            
            # Se o ano tem 2 dígitos, converter para 4 dígitos
            if len(ano) == 2:
                ano = '20' + ano if int(ano) <= 50 else '19' + ano
            
            # Criar data no primeiro dia do mês
            data = datetime.strptime(f'01/{mes}/{ano}', '%d/%m/%Y')
            return data
            
    except Exception:
        pass
    
    # Se não conseguir converter, retorna a competência original
    return competencia

def formatar_salario_para_float(salario_str):
    """Converte string de salário no formato brasileiro (X.XXX,XX) para float."""
    if isinstance(salario_str, (int, float)):
        return float(salario_str)
    
    if not isinstance(salario_str, str):
        return None

    # Remove o R$ e espaços, depois troca o ponto (milhar) por nada e a vírgula (decimal) por ponto.
    salario_str = salario_str.replace('R$', '').replace(' ', '').strip()
    salario_str = salario_str.replace('.', '').replace(',', '.')
    
    try:
        return float(salario_str)
    except ValueError:
        return None

def processar_registro(competencia_str, salario_str, modelo):
    """Processa uma única linha de dados (competência e salário)."""
    # Garante que as strings não sejam None
    if competencia_str is None or salario_str is None:
        return None
        
    salario_float = formatar_salario_para_float(salario_str)
    competencia_data = converter_competencia(competencia_str)
    
    if salario_float is not None:
        return {
            'Modelo': modelo,
            'Competencia_Original': competencia_str.strip().replace('\n', ' '),
            'Data': competencia_data,
            'Ano_Mes': competencia_data.strftime('%Y-%m') if isinstance(competencia_data, datetime) else competencia_str,
            'Salario_Contribuicao': salario_float
        }
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
        for page in pdf.pages:
            # Extrai o texto completo da página
            text = page.extract_text()
            
            # Divide o texto em linhas
            lines = text.split('\n')
            
            # Procura pelas linhas que contêm dados de contribuição
            for line in lines:
                # Padrão para identificar linhas com dados: número + data (MM/AAAA) + valores
                # Exemplo: "001 07/1994 R$ 309,24 582,86 309,24 7,521684 R$ 2.326,01"
                pattern = r'^\s*(\d{2,3})\s+(\d{2}/\d{4})\s+R\$\s*([\d\.,]+)\s+([\d\.,]+)\s+([\d\.,]+)\s+([\d\.,]+)\s+R\$\s*([\d\.,]+)'
                match = re.search(pattern, line.strip())
                
                if match:
                    numero, competencia, salario_contribuicao, teto, salario_considerado, indice, salario_corrigido = match.groups()
                    
                    # Usa o salário de contribuição (terceira coluna)
                    registro = processar_registro(competencia, salario_contribuicao, "Modelo 1")
                    if registro:
                        data.append(registro)
                
                # Tenta um padrão mais simples se o primeiro não funcionar
                else:
                    # Procura por padrão MM/AAAA seguido de valores monetários
                    simple_pattern = r'(\d{2}/\d{4})\s+R\$\s*([\d\.,]+)'
                    matches = re.findall(simple_pattern, line)
                    
                    for competencia, salario in matches:
                        registro = processar_registro(competencia, salario, "Modelo 1")
                        if registro:
                            data.append(registro)
    
    # Se não encontrou dados com o padrão de tabela, tenta uma abordagem mais genérica
    if not data:
        st.warning("Padrão de tabela não encontrado. Tentando extração genérica...")
        pdf_file.seek(0)
        
        with pdfplumber.open(pdf_file) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                lines = text.split('\n')
                
                for line in lines:
                    # Procura por qualquer padrão de data MM/AAAA seguido de valor
                    pattern = r'(\d{2}/\d{4})\s+[^\n]*?R\$\s*([\d\.,]+)'
                    matches = re.findall(pattern, line)
                    
                    for competencia, salario in matches:
                        registro = processar_registro(competencia, salario, "Modelo 1")
                        if registro:
                            data.append(registro)
    
    return pd.DataFrame(data)

# ------------------------------------------------------------
# Funções de extração de dados - MODELO 2 (Extração de Tabelas Estruturadas)
# ------------------------------------------------------------

def extract_data_from_pdf_model2(pdf_file):
    """Extrai dados do PDF do Modelo 2 (Extração de Tabelas Estruturadas)."""
    st.info("Modelo 2 selecionado: Extração via Tabela Estruturada.")
    data = []
    
    # Resetar o ponteiro do arquivo
    pdf_file.seek(0)

    with pdfplumber.open(pdf_file) as pdf:
        for page in pdf.pages:
            # Tenta extrair tabelas
            tables = page.extract_tables()
            
            for table in tables:
                if not table or len(table) < 2:
                    continue

                # Procura pela linha de cabeçalho
                header_found = False
                data_col_index = -1
                salario_col_index = -1
                
                for i, row in enumerate(table):
                    if not row:
                        continue
                        
                    # Converte toda a linha para string e junta para análise
                    row_text = ' '.join([str(cell) if cell else '' for cell in row]).lower()
                    
                    # Procura por cabeçalhos que indiquem as colunas que precisamos
                    if 'data' in row_text and any(word in row_text for word in ['salário', 'contribuição']):
                        header_found = True
                        
                        # Encontra os índices das colunas
                        for j, cell in enumerate(row):
                            if cell and 'data' in str(cell).lower():
                                data_col_index = j
                            if cell and any(word in str(cell).lower() for word in ['salário', 'contribuição']):
                                salario_col_index = j
                        break
                
                # Se encontrou o cabeçalho, processa as linhas seguintes
                if header_found and data_col_index != -1 and salario_col_index != -1:
                    for row in table[i+1:]:
                        if row and len(row) > max(data_col_index, salario_col_index):
                            competencia = row[data_col_index]
                            salario = row[salario_col_index]
                            
                            if competencia and salario:
                                registro = processar_registro(str(competencia), str(salario), "Modelo 2")
                                if registro:
                                    data.append(registro)
    
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
                st.success(f"Dados extraídos com sucesso! {len(df)} registros encontrados.")
                
                # Ordenar por data se a coluna for datetime
                if 'Data' in df.columns and pd.api.types.is_datetime64_any_dtype(df['Data']):
                    df = df.sort_values('Data').reset_index(drop=True)

                # Mostrar preview dos dados
                st.subheader("Prévia dos Dados")
                df_display = df.copy()
                if 'Data' in df_display.columns and pd.api.types.is_datetime64_any_dtype(df_display['Data']):
                    df_display['Data'] = df_display['Data'].dt.strftime('%d/%m/%Y')
                    
                st.dataframe(df_display[['Modelo', 'Competencia_Original', 'Data', 'Salario_Contribuicao']].head(20))
                
                # Estatísticas básicas
                col1, col2, col3 = st.columns(3)
                df_filtered = df[pd.api.types.is_datetime64_any_dtype(df['Data'])].sort_values('Data')

                with col1:
                    st.metric("Total de Registros", len(df_filtered))
                
                if not df_filtered.empty:
                    with col2:
                        st.metric("Período Inicial", df_filtered['Competencia_Original'].iloc[0])
                    with col3:
                        st.metric("Período Final", df_filtered['Competencia_Original'].iloc[-1])
                
                # Opções de exportação
                st.subheader("Opções de Exportação")
                
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
                
                all_cols_options = ["Competencia_Original", "Data", "Ano_Mes", "Salario_Contribuicao", "Modelo"]
                
                with col2:
                    incluir_colunas = st.multiselect(
                        "Colunas a incluir:",
                        all_cols_options,
                        default=list(set(default_cols)),
                        key="incluir_colunas_multiselect"
                    )
                
                # Preparar dados para exportação
                df_export = df[incluir_colunas].copy()
                
                # Renomear a coluna de competência selecionada para "Competencia"
                if coluna_data_selecionada in df_export.columns and coluna_data_selecionada != "Competencia":
                    df_export = df_export.rename(columns={coluna_data_selecionada: 'Competencia'})
                
                # Exportação para Excel
                st.subheader("Exportar para Excel")
                
                output = BytesIO()
                
                with pd.ExcelWriter(output, engine='openpyxl', datetime_format='dd/mm/yyyy') as writer:
                    df_export.to_excel(writer, sheet_name='Salarios_Contribuicao', index=False)
                    
                    workbook = writer.book
                    worksheet = writer.sheets['Salarios_Contribuicao']
                    
                    # Formatar coluna de salário como moeda
                    if 'Salario_Contribuicao' in df_export.columns:
                        salario_col_idx = df_export.columns.get_loc('Salario_Contribuicao')
                        for row in range(2, len(df_export) + 2):
                            worksheet.cell(row=row, column=salario_col_idx + 1).number_format = '#,##0.00'
                
                excel_data = output.getvalue()
                
                st.download_button(
                    label="📥 Baixar Planilha Excel",
                    data=excel_data,
                    file_name="salarios_contribuicao.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
                
            else:
                st.warning(f"Nenhum dado foi extraído com sucesso usando o **{extraction_model}**.")
                
        except Exception as e:
            st.error(f"Erro ao processar o arquivo: {str(e)}")
            
    # Instruções
    with st.expander("ℹ️ Instruções de Uso"):
        st.markdown("""
        ### Modelos de Extração:
        
        **Modelo 1 (Extração Específica):**
        - Otimizado para a estrutura do PDF fornecido
        - Procura por padrões específicos de tabela com números, datas MM/AAAA e valores
        - Mais preciso para o formato do documento anexo
        
        **Modelo 2 (Tabela Estruturada):**
        - Abordagem genérica para extração de tabelas
        - Funciona bem com PDFs que têm estrutura de tabela clara
        
        ### Dica:
        Se o Modelo 1 não extrair todos os dados, tente o Modelo 2 como alternativa.
        """)

if __name__ == "__main__":
    main()
