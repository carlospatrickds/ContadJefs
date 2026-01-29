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
            texto_topo = pagina.extract_text() or ""
            
            # 1. Identificar o Ano de Referência na página
            ano_match = re.search(r'ANO\s+REFERENCIA\s*(\d{4})', texto_topo, re.IGNORECASE)
            ano = ano_match.group(1) if ano_match else "9999"
            
            # 2. Extrair a tabela da página
            tabela = pagina.extract_table()
            if not tabela:
                continue
            
            # 3. Identificar o Semestre pelo cabeçalho
            meses_referencia = []
            colunas_indices = []
            
            # Procurar a linha que contém os nomes dos meses
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

            # 4. Processar linhas de descontos
            em_secao_descontos = False
            
            for linha in tabela:
                # Limpeza básica de cada célula (remove \n e espaços extras)
                colunas = [str(c).replace('\n', ' ').strip() if c else "" for c in linha]
                
                # Verifica se a linha indica o início da seção de Descontos
                if any("DESCONTOS" in c.upper() for c in colunas):
                    em_secao_descontos = True
                    continue
                
                # Se encontrar "TOTAL" ou "RENDIMENTOS", encerra a seção de descontos da página
                if em_secao_descontos and any(x in "".join(colunas).upper() for x in ["TOTAL", "RENDIMENTOS"]):
                    em_secao_descontos = False
                    continue
                
                if em_secao_descontos:
                    # Descrição: Geralmente na coluna 1 ou 0
                    # No SIAPE, se col[0] for 'DESCONTOS', a descrição está em col[1]
                    # Se col[0] estiver vazia, a descrição está em col[1]
                    descricao = colunas[1] if len(colunas) > 1 and colunas[1] else colunas[0]
                    
                    if not descricao or descricao.upper() in ["DISCRIMINAÇÃO", "TIPO", ""]:
                        continue

                    # Extrair valores para cada mês identificado
                    for i, mes_num in enumerate(meses_referencia):
                        if i < len(colunas_indices):
                            idx_col = colunas_indices[i]
                            if idx_col < len(colunas):
                                val_raw = colunas[idx_col]
                                
                                try:
                                    # Limpa o valor (ex: "1.234,56" -> 1234.56)
                                    val_limpo = val_raw.replace('.', '').replace(',', '.')
                                    val_float = float(re.sub(r'[^\d.]', '', val_limpo))
                                    
                                    if val_float > 0:
                                        dados.append({
                                            'Discriminacao': descricao,
                                            'Valor': formatar_valor_br(val_float),
                                            'Competencia': f"{mes_num}/{ano}",
                                            'Pagina': pagina_num
                                        })
                                except ValueError:
                                    continue
    
    df = pd.DataFrame(dados)
    if not df.empty:
        # Ordenação lógica: Ano, depois Mês
        df['temp_data'] = pd.to_datetime(df['Competencia'], format='%m/%Y')
        df = df.sort_values(by=['temp_data', 'Discriminacao']).drop(columns=['temp_data'])
    return df

# --- INTERFACE STREAMLIT ---

def main():
    st.set_page_config(page_title="Conversor SIAPE UFPE", layout="wide")
    st.title("📄 Extrator de Descontos - Fichas Financeiras")
    st.markdown("---")

    file = st.file_uploader("Arraste o PDF unificado aqui", type="pdf")

    if file:
        if st.button("🚀 Processar Documento"):
            with st.spinner("Analisando páginas e competências..."):
                df_resultado = extrair_dados_siape_ajustado(file)
                
                if not df_resultado.empty:
                    st.success(f"Sucesso! {len(df_resultado)} registros encontrados.")
                    
                    # Filtros laterais
                    st.sidebar.header("Filtros")
                    anos = sorted(df_resultado['Competencia'].str.split('/').str[1].unique())
                    ano_filter = st.sidebar.multiselect("Filtrar por Ano", anos, default=anos)
                    
                    df_final = df_resultado[df_resultado['Competencia'].str.contains('|'.join(ano_filter))]
                    
                    # Exibição
                    st.dataframe(df_final, use_container_width=True, height=600)
                    
                    # Downloads
                    c1, c2 = st.columns(2)
                    csv = df_final.to_csv(index=False, sep=';', encoding='utf-8-sig')
                    c1.download_button("📥 Baixar CSV (Excel)", csv, "descontos_siape.csv", "text/csv")
                    
                    excel_buffer = io.BytesIO()
                    with pd.ExcelWriter(excel_buffer, engine='xlsxwriter') as writer:
                        df_final.to_excel(writer, index=False, sheet_name='Dados')
                    c2.download_button("📥 Baixar Planilha Excel (.xlsx)", excel_buffer.getvalue(), "descontos_siape.xlsx")
                else:
                    st.error("Nenhum desconto identificado. Verifique se o PDF possui a palavra 'DESCONTOS' e 'ANO REFERENCIA'.")

if __name__ == "__main__":
    main()
