import streamlit as st
import pandas as pd
import pdfplumber
import re
import io

def formatar_valor_br(valor_float):
    """Converte float para string no formato R$ 1.234,56"""
    return f"{valor_float:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')

def extrair_dados_siape_ajustado(pdf_file):
    dados = []
    
    with pdfplumber.open(pdf_file) as pdf:
        for pagina_num, pagina in enumerate(pdf.pages, 1):
            # Extração do texto para buscar o ano
            texto_topo = pagina.extract_text() or ""
            
            # 1. Identificar o Ano de Referência (Regex melhorada para capturar após quebras de linha)
            ano_match = re.search(r'ANO\s+REFERENCIA\s*[:\-\n\s]*(\d{4})', texto_topo, re.IGNORECASE)
            
            if ano_match:
                ano = ano_match.group(1)
            else:
                # Se não achar o ano, tenta buscar qualquer sequência de 4 dígitos perto do topo
                ano_resgate = re.search(r'\b(20\d{2})\b', texto_topo[:500])
                ano = ano_resgate.group(1) if ano_resgate else None
            
            # Se ainda assim não encontrar o ano, ignora a página para evitar o erro de data
            if not ano:
                continue
            
            tabela = pagina.extract_table()
            if not tabela:
                continue
            
            # 2. Identificar o Semestre pelo cabeçalho
            meses_referencia = []
            colunas_indices = []
            
            for linha in tabela:
                linha_upper = [str(c).upper() if c else "" for c in linha]
                if "JAN" in linha_upper:
                    meses_referencia = ["01", "02", "03", "04", "05", "06"]
                    colunas_indices = [i for i, c in enumerate(linha_upper) if c in ["JAN", "FEV", "MAR", "ABR", "MAI", "JUN"]]
                    break
                elif "JUL" in linha_upper:
                    meses_referencia = ["07", "08", "09", "10", "11", "12"]
                    colunas_indices = [i for i, c in enumerate(linha_upper) if c in ["JUL", "AGO", "SET", "OUT", "NOV", "DEZ"]]
                    break
            
            if not meses_referencia:
                continue

            # 3. Processar linhas de descontos
            em_secao_descontos = False
            for linha in tabela:
                colunas = [str(c).replace('\n', ' ').strip() if c else "" for c in linha]
                
                if any("DESCONTOS" in c.upper() for c in colunas):
                    em_secao_descontos = True
                    continue
                
                if em_secao_descontos and any(x in "".join(colunas).upper() for x in ["TOTAL", "RENDIMENTOS"]):
                    em_secao_descontos = False
                    continue
                
                if em_secao_descontos:
                    descricao = colunas[1] if len(colunas) > 1 and colunas[1] else colunas[0]
                    
                    if not descricao or descricao.upper() in ["DISCRIMINAÇÃO", "TIPO", ""]:
                        continue

                    for i, mes_num in enumerate(meses_referencia):
                        if i < len(colunas_indices):
                            idx_col = colunas_indices[i]
                            if idx_col < len(colunas):
                                val_raw = colunas[idx_col]
                                
                                try:
                                    val_limpo = val_raw.replace('.', '').replace(',', '.')
                                    val_float = float(re.sub(r'[^\d.]', '', val_limpo))
                                    
                                    if val_float > 0:
                                        dados.append({
                                            'Discriminacao': descricao,
                                            'Valor': formatar_valor_br(val_float),
                                            'Competencia': f"{mes_num}/{ano}",
                                            'Pagina': pagina_num
                                        })
                                except:
                                    continue
    
    df = pd.DataFrame(dados)
    if not df.empty:
        # Uso de errors='coerce' para evitar quebra do app se houver lixo nos dados
        df['temp_data'] = pd.to_datetime(df['Competencia'], format='%m/%Y', errors='coerce')
        # Remove linhas onde a data falhou na conversão
        df = df.dropna(subset=['temp_data'])
        df = df.sort_values(by=['temp_data', 'Discriminacao']).drop(columns=['temp_data'])
        
    return df

# --- INTERFACE STREAMLIT ---

def main():
    st.set_page_config(page_title="Conversor SIAPE UFPE", layout="wide")
    st.title("📊 Extrator de Descontos - SIAPE")
    
    file = st.file_uploader("Upload do PDF", type="pdf")

    if file:
        if st.button("🚀 Processar Documento"):
            with st.spinner("Extraindo dados..."):
                df_resultado = extrair_dados_siape_ajustado(file)
                
                if not df_resultado.empty:
                    st.success(f"Sucesso! {len(df_resultado)} registros encontrados.")
                    
                    anos = sorted(df_resultado['Competencia'].str.split('/').str[1].unique())
                    ano_filter = st.sidebar.multiselect("Filtrar por Ano", anos, default=anos)
                    
                    df_final = df_resultado[df_resultado['Competencia'].str.contains('|'.join(ano_filter))]
                    
                    st.dataframe(df_final, use_container_width=True, height=600)
                    
                    c1, c2 = st.columns(2)
                    csv = df_final.to_csv(index=False, sep=';', encoding='utf-8-sig')
                    c1.download_button("📥 Baixar CSV", csv, "descontos.csv", "text/csv")
                    
                    excel_buffer = io.BytesIO()
                    with pd.ExcelWriter(excel_buffer, engine='xlsxwriter') as writer:
                        df_final.to_excel(writer, index=False, sheet_name='Dados')
                    c2.download_button("📥 Baixar Excel", excel_buffer.getvalue(), "descontos.xlsx")
                else:
                    st.error("Nenhum dado válido encontrado. Verifique se o PDF contém o 'ANO REFERENCIA'.")

if __name__ == "__main__":
    main()
