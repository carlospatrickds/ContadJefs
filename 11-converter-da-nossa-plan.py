import streamlit as st
import pandas as pd
import pdfplumber
import re
from io import BytesIO
from datetime import datetime

def converter_competencia(competencia):
    """Converte competência no formato 'Mmm/AA' para data válida"""
    try:
        # Mapeamento de meses em português para inglês
        meses_pt_en = {
            'jan': 'Jan', 'fev': 'Feb', 'mar': 'Mar', 'abr': 'Apr', 'mai': 'May', 'jun': 'Jun',
            'jul': 'Jul', 'ago': 'Aug', 'set': 'Sep', 'out': 'Oct', 'nov': 'Nov', 'dez': 'Dec'
        }
        
        mes_pt, ano = competencia.split('/')
        mes_en = meses_pt_en.get(mes_pt.lower(), mes_pt)
        
        # Se o ano tem 2 dígitos, converter para 4 dígitos
        if len(ano) == 2:
            ano = '19' + ano if int(ano) > 50 else '20' + ano
        
        # Criar data no primeiro dia do mês
        data = datetime.strptime(f'01/{mes_en}/{ano}', '%d/%b/%Y')
        return data
        
    except Exception as e:
        # Se não conseguir converter, retorna a competência original
        return competencia

def extract_data_from_pdf(pdf_file):
    """Extrai dados do PDF da planilha RMI"""
    data = []
    
    with pdfplumber.open(pdf_file) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            
            # Encontrar linhas com dados de competência e salário
            lines = text.split('\n')
            
            for line in lines:
                # Padrão para identificar linhas com dados (ex: "jul/94    90,15")
                pattern = r'([a-z]{3}/\d{2,4})\s+(\d{1,3}(?:\.\d{3})*,\d{2})'
                matches = re.findall(pattern, line.lower())
                
                for match in matches:
                    competencia, salario = match
                    # Converter para formato numérico
                    salario_float = float(salario.replace('.', '').replace(',', '.'))
                    
                    # Converter competência para data
                    competencia_data = converter_competencia(competencia)
                    
                    data.append({
                        'Competencia_Original': competencia.title(),
                        'Data': competencia_data,
                        'Ano_Mes': competencia_data.strftime('%Y-%m') if isinstance(competencia_data, datetime) else competencia,
                        'Salario_Contribuicao': salario_float
                    })
    
    df = pd.DataFrame(data)
    
    # Ordenar por data se possível
    if 'Data' in df.columns:
        df = df.sort_values('Data')
    
    return df

def main():
    st.title("📊 Leitor de Planilhas RMI - INSS")
    st.write("Faça upload do arquivo PDF para extrair os dados dos salários de contribuição")
    
    # Upload do arquivo
    uploaded_file = st.file_uploader("Escolha o arquivo PDF", type="pdf")
    
    if uploaded_file is not None:
        try:
            # Extrair dados do PDF
            with st.spinner("Processando arquivo PDF..."):
                df = extract_data_from_pdf(uploaded_file)
            
            if not df.empty:
                st.success(f"Dados extraídos com sucesso! {len(df)} registros encontrados.")
                
                # Mostrar preview dos dados
                st.subheader("Prévia dos Dados")
                st.dataframe(df.head(20))
                
                # Estatísticas básicas
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Total de Registros", len(df))
                with col2:
                    st.metric("Período Inicial", df['Competencia_Original'].iloc[0])
                with col3:
                    st.metric("Período Final", df['Competencia_Original'].iloc[-1])
                
                # Opções de exportação
                st.subheader("Opções de Exportação")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    formato_data = st.radio(
                        "Formato da competência no Excel:",
                        ["Data Completa", "Ano-Mês", "Original"]
                    )
                
                with col2:
                    incluir_colunas = st.multiselect(
                        "Colunas a incluir:",
                        ["Competencia_Original", "Data", "Ano_Mes", "Salario_Contribuicao"],
                        default=["Competencia_Original", "Salario_Contribuicao"]
                    )
                
                # Preparar dados para exportação
                df_export = df[incluir_colunas].copy()
                
                # Ajustar formato conforme seleção
                if formato_data == "Ano-Mês" and "Ano_Mes" in df_export.columns:
                    df_export = df_export.rename(columns={'Ano_Mes': 'Competencia'})
                elif formato_data == "Original" and "Competencia_Original" in df_export.columns:
                    df_export = df_export.rename(columns={'Competencia_Original': 'Competencia'})
                elif formato_data == "Data Completa" and "Data" in df_export.columns:
                    df_export = df_export.rename(columns={'Data': 'Competencia'})
                
                # Download para Excel
                st.subheader("Exportar para Excel")
                
                # Criar arquivo Excel em memória
                output = BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    df_export.to_excel(writer, sheet_name='Salarios_Contribuicao', index=False)
                    
                    # Ajustar formatação das colunas
                    workbook = writer.book
                    worksheet = writer.sheets['Salarios_Contribuicao']
                    
                    # Formatar coluna de salário como moeda
                    if 'Salario_Contribuicao' in df_export.columns:
                        salario_col = df_export.columns.get_loc('Salario_Contribuicao') + 1
                        for row in range(2, len(df_export) + 2):
                            worksheet.cell(row=row, column=salario_col).number_format = '#,##0.00'
                
                excel_data = output.getvalue()
                
                st.download_button(
                    label="📥 Baixar Planilha Excel",
                    data=excel_data,
                    file_name="salarios_contribuicao.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
                
                # Mostrar dados completos
                st.subheader("Dados Completos")
                st.dataframe(df)
                
            else:
                st.warning("Nenhum dado foi extraído do arquivo. Verifique o formato do PDF.")
                
        except Exception as e:
            st.error(f"Erro ao processar o arquivo: {str(e)}")
            st.info("Dica: Verifique se o PDF contém tabelas no formato mostrado no exemplo.")
    
    # Instruções
    with st.expander("ℹ️ Instruções de Uso"):
        st.markdown("""
        ### Formatos de Competência Disponíveis:
        
        - **Data Completa**: Data real (01/MM/AAAA) - Ideal para fórmulas Excel
        - **Ano-Mês**: Formato "AAAA-MM" - Padrão internacional
        - **Original**: Formato "Mmm/AA" - Como aparece no PDF
        
        ### Para usar no Excel:
        
        1. Use o formato **"Data Completa"** se quiser fazer cálculos com datas
        2. Use **"Ano-Mês"** se quiser agrupar por período
        3. Use **PROCV** ou **PROCH** normalmente com qualquer formato
        """)

if __name__ == "__main__":
    main()
