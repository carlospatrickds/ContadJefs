import streamlit as st
import pandas as pd
import pdfplumber
import re
from io import BytesIO

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
                    data.append({
                        'Competência': competencia.title(),
                        'Salário_de_Contribuição': salario_float
                    })
    
    return pd.DataFrame(data)

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
                    st.metric("Período Inicial", df['Competência'].min())
                with col3:
                    st.metric("Período Final", df['Competência'].max())
                
                # Download para Excel
                st.subheader("Exportar para Excel")
                
                # Criar arquivo Excel em memória
                output = BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    df.to_excel(writer, sheet_name='Salarios_Contribuicao', index=False)
                
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
    
    # Instruções
    with st.expander("ℹ️ Instruções de Uso"):
        st.markdown("""
        1. **Faça upload** do arquivo PDF da planilha RMI
        2. **Aguarde** o processamento automático dos dados
        3. **Verifique** a prévia dos dados extraídos
        4. **Baixe** a planilha em formato Excel
        5. A planilha conterá:
           - Coluna A: Competências (ex: Jul/94)
           - Coluna B: Valores dos Salários de Contribuição
        """)

if __name__ == "__main__":
    main()
