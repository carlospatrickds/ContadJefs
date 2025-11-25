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
    """Converte competência no formato 'Mmm/AA' para data válida"""
    try:
        # Mapeamento de meses em português para inglês
        meses_pt_en = {
            'jan': 'Jan', 'fev': 'Feb', 'mar': 'Mar', 'abr': 'Apr', 'mai': 'May', 'jun': 'Jun',
            'jul': 'Jul', 'ago': 'Aug', 'set': 'Sep', 'out': 'Oct', 'nov': 'Nov', 'dez': 'Dec'
        }
        
        # Remove R$ e caracteres que não são da competência
        competencia = re.sub(r'[^a-z0-9/]', '', competencia.lower())

        mes_pt, ano = competencia.split('/')
        mes_en = meses_pt_en.get(mes_pt.lower(), mes_pt)
        
        # Se o ano tem 2 dígitos, converter para 4 dígitos
        if len(ano) == 2:
            # Assumimos que anos <= 50 são do século 21 (20XX) e > 50 são do século 20 (19XX)
            ano = '19' + ano if int(ano) > 50 else '20' + ano
        
        # Criar data no primeiro dia do mês
        data = datetime.strptime(f'01/{mes_en}/{ano}', '%d/%b/%Y')
        return data
        
    except Exception:
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
# Funções de extração de dados - MODELO 1 (Seu código original - Padrão RMI com Regex)
# ------------------------------------------------------------

def extract_data_from_pdf_model1(pdf_file):
    """Extrai dados do PDF do Modelo 1 (Padrão RMI com Regex)."""
    st.info("Modelo 1 selecionado: Extração via Regex (padrão 'Mmm/AA' e valor próximo).")
    data = []
    
    # Resetar o ponteiro do arquivo
    pdf_file.seek(0)

    with pdfplumber.open(pdf_file) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            
            # Encontrar linhas com dados de competência e salário
            lines = text.split('\n')
            
            for line in lines:
                # O padrão mais solto que você estava usando no final, que funciona bem para o PDF fornecido.
                # Procura por "Mmm/AA" seguido de um número monetário brasileiro (com ponto opcional como milhar e vírgula como decimal).
                pattern = r'([a-z]{3}/\d{2,4})\s+R\$\s*(\d{1,3}(?:\.\d{3})*,\d{2})'
                matches = re.findall(pattern, line.lower())
                
                if not matches:
                     # Tenta o padrão mais solto (data e valor separados por espaço, sem R$)
                     pattern = r'([a-z]{3}/\d{2,4})\s+(\d{1,3}(?:\.\d{3})*,\d{2})'
                     matches = re.findall(pattern, line.lower())
                
                for match in matches:
                    competencia, salario = match
                    registro = processar_registro(competencia, salario, "Modelo 1")
                    if registro:
                        data.append(registro)
    
    return pd.DataFrame(data)

# ------------------------------------------------------------
# Funções de extração de dados - MODELO 2 (Extração de Tabelas Estruturadas)
# ------------------------------------------------------------

def extract_data_from_pdf_model2(pdf_file):
    """Extrai dados do PDF do Modelo 2 (Padrão Tabela Estruturada).
    Aprimorado para ser mais tolerante com quebras de linha e nomes de coluna.
    """
    st.info("Modelo 2 selecionado: Extração via Tabela Estruturada (Aprimorada para mais tolerância).")
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

                # Normaliza e limpa a linha de cabeçalho
                header = [
                    (col.strip().lower().replace('\n', ' ') if col else '')
                    for col in table[0]
                ]
                
                # Procura por colunas de Data/Competência
                data_keywords = ['data', 'competência', 'periodo']
                data_col_index = -1
                for i, h in enumerate(header):
                    if any(kw in h for kw in data_keywords):
                        data_col_index = i
                        break
                
                # Procura por colunas de Salário
                salario_keywords = ['salário de contribuição', 'salario', 'valor considerado']
                salario_col_index = -1
                for i, h in enumerate(header):
                    if any(kw in h for kw in salario_keywords):
                        # Pega o primeiro match, mas prefere "Salário de Contribuição" se existir
                        if 'salário de contribuição' in h:
                            salario_col_index = i
                            break
                        elif salario_col_index == -1:
                            salario_col_index = i

                # Verifica se ambas as colunas foram encontradas
                if data_col_index == -1 or salario_col_index == -1:
                    continue

                # Processa as linhas de dados (a partir da segunda linha)
                max_index = max(data_col_index, salario_col_index)
                for row in table[1:]:
                    # Garante que a linha não é vazia e tem colunas suficientes
                    if row and len(row) > max_index:
                        competencia = row[data_col_index]
                        salario = row[salario_col_index]

                        if competencia and salario:
                            registro = processar_registro(competencia, salario, "Modelo 2")
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
        ["Modelo 1 (Padrão RMI INSS - Regex)", "Modelo 2 (Padrão Tabela Estruturada)"],
        index=0,
        help="Modelo 1 usa reconhecimento de texto por padrão de data/valor. Modelo 2 usa detecção de tabelas estruturadas."
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
                # Passa o arquivo, mas não se esquece de resetar o ponteiro dentro da função, caso a função chame o seek()
                df = extraction_func(uploaded_file)
            
            if not df.empty:
                st.success(f"Dados extraídos com sucesso! {len(df)} registros encontrados.")
                
                # Ordenar por data se a coluna for datetime
                if 'Data' in df.columns and pd.api.types.is_datetime64_any_dtype(df['Data']):
                    df = df.sort_values('Data').reset_index(drop=True)

                # Mostrar preview dos dados
                st.subheader("Prévia dos Dados")
                # Formata a coluna 'Data' para exibir DD/MM/AAAA no Streamlit
                df_display = df.copy()
                if 'Data' in df_display.columns and pd.api.types.is_datetime64_any_dtype(df_display['Data']):
                    df_display['Data'] = df_display['Data'].dt.strftime('%d/%m/%Y')
                    
                # Exibir colunas relevantes para o usuário
                st.dataframe(df_display[['Modelo', 'Competencia_Original', 'Data', 'Salario_Contribuicao']].head(20))
                
                # Estatísticas básicas
                col1, col2, col3 = st.columns(3)
                df_filtered = df[pd.api.types.is_datetime64_any_dtype(df['Data'])].sort_values('Data')

                with col1:
                    st.metric("Total de Registros Válidos", len(df_filtered))
                
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
                
                # Lógica para determinar as colunas a incluir
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
                
                coluna_data_nome = 'Competencia' if 'Competencia' in df_export.columns else coluna_data_selecionada

                # Exportação para Excel
                st.subheader("Exportar para Excel")
                
                # Criar arquivo Excel em memória
                output = BytesIO()
                
                # Usar a biblioteca openpyxl para aplicar formatação customizada
                with pd.ExcelWriter(output, engine='openpyxl', datetime_format='dd/mm/yyyy') as writer:
                    df_export.to_excel(writer, sheet_name='Salarios_Contribuicao', index=False)
                    
                    # Ajustar formatação das colunas
                    workbook = writer.book
                    worksheet = writer.sheets['Salarios_Contribuicao']
                    
                    # Formatar coluna de salário como moeda
                    if 'Salario_Contribuicao' in df_export.columns:
                        salario_col_idx = df_export.columns.get_loc('Salario_Contribuicao')
                        salario_col = salario_col_idx + 1
                        
                        # Aplicar formato numérico brasileiro
                        for row in range(2, len(df_export) + 2):
                            worksheet.cell(row=row, column=salario_col).number_format = '#,##0.00'
                        
                    # Forçar formato de Data (DD/MM/AAAA) no Excel
                    if coluna_data_nome == 'Competencia' and formato_data == "Data Completa":
                        data_col_idx = df_export.columns.get_loc('Competencia')
                        data_col = data_col_idx + 1
                        
                        # Aplicar formato de data 'dd/mm/yyyy' em todas as células de dados
                        for row in range(2, len(df_export) + 2):
                            cell = worksheet.cell(row=row, column=data_col)
                            # Se o valor é um datetime, aplica o formato
                            if isinstance(cell.value, datetime):
                                cell.number_format = 'dd/mm/yyyy'
                
                excel_data = output.getvalue()
                
                st.download_button(
                    label="📥 Baixar Planilha Excel",
                    data=excel_data,
                    file_name="salarios_contribuicao.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
                
                # Mostrar dados completos (todos, incluindo os que não foram convertidos para data)
                st.subheader("Dados Completos (Com colunas de processamento)")
                st.dataframe(df)
                
            else:
                st.warning(f"Nenhum dado foi extraído com sucesso usando o **{extraction_model}**. Verifique o formato do PDF ou tente o outro modelo.")
                
        except Exception as e:
            st.error(f"Erro ao processar o arquivo: {str(e)}")
            st.info("Dica: Verifique se o PDF está legível e corresponde ao modelo de extração selecionado.")
            
    # Instruções
    with st.expander("ℹ️ Instruções de Uso e Modelos"):
        st.markdown("""
        ### Formatos de Planilha Suportados:
        
        **1. Modelo 1 (Padrão RMI INSS - Regex):**
        - Ideal para relatórios de cálculo de RMI (Renda Mensal Inicial) do INSS.
        - Usa um padrão de expressão regular (`Regex`) para buscar a competência (`Mmm/AA` ou `Mmm/AAAA`) e o valor de salário de contribuição próximo na mesma linha, mesmo que estejam fora de uma estrutura de tabela perfeita.
        
        **2. Modelo 2 (Padrão Tabela Estruturada - Aprimorado):**
        - **Mais tolerante.** Ideal para PDFs que contêm tabelas, mesmo com quebras de linha nos cabeçalhos ou dados.
        - Procura por colunas que contenham os termos **"Data"**, **"Competência"** e **"Salário de Contribuição"** (ou similar).
        
        ### Dicas de Exportação:
        
        - **Data Completa**: Exporta como `01/MM/AAAA`. **Recomendado para fórmulas e cálculos de data no Excel.** O sistema garante o formato correto.
        - **Ano-Mês**: Formato `"AAAA-MM"` - Padrão internacional para agrupar.
        - **Original**: Formato `"Mmm/AA"` - Como aparece no PDF.
        """)

if __name__ == "__main__":
    main()
