import streamlit as st
import pandas as pd
import pdfplumber
import re
from datetime import datetime
import io

def criar_df_vazio():
    """Cria um DataFrame com as colunas necessárias para evitar KeyError."""
    return pd.DataFrame(columns=['Discriminacao', 'Valor', 'Competencia', 'Pagina'])

def extrair_descontos_pdf(pdf_file):
    dados = []
    
    with pdfplumber.open(pdf_file) as pdf:
        for pagina_num, pagina in enumerate(pdf.pages, 1):
            texto = pagina.extract_text()
            if not texto:
                continue
                
            # Extrair ano de referência (melhorado para ser mais flexível)
            ano_match = re.search(r'(?:ANO REFERÊNCIA|EXERCÍCIO|ANO)\s*:?\s*(\d{4})', texto, re.IGNORECASE)
            ano = ano_match.group(1) if ano_match else "9999"
            
            linhas = texto.split('\n')
            desconto_start = False
            
            for linha in linhas:
                if 'DESCONTOS' in linha.upper():
                    desconto_start = True
                    continue
                
                if desconto_start and any(x in linha.upper() for x in ['RENDIMENTOS', 'TOTAL BRUTO', 'TOTAL LIQUIDO']):
                    break
                
                if desconto_start and linha.strip():
                    linha_limpa = ' '.join(linha.split())
                    padrao_valor = r'\d{1,3}(?:\.\d{3})*,\d{2}'
                    
                    if re.search(padrao_valor, linha_limpa):
                        partes = re.split(rf'({padrao_valor})', linha_limpa)
                        partes = [p.strip() for p in partes if p.strip()]
                        
                        if len(partes) > 1:
                            discriminacao = partes[0]
                            valores = [re.sub(r'[^\d,]', '', v) for v in partes[1:] if re.match(padrao_valor, v)]
                            meses = ['01', '02', '03', '04', '05', '06'] # JAN a JUN
                            
                            for mes_idx, mes_num in enumerate(meses):
                                if mes_idx < len(valores):
                                    valor_str = valores[mes_idx]
                                    try:
                                        valor_float = float(valor_str.replace('.', '').replace(',', '.'))
                                        if valor_float <= 0: continue # Pula valores zerados
                                        
                                        valor_formatado = f"{valor_float:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
                                        dados.append({
                                            'Discriminacao': discriminacao,
                                            'Valor': valor_formatado,
                                            'Competencia': f"{mes_num}/{ano}",
                                            'Pagina': pagina_num
                                        })
                                    except:
                                        continue
    
    df = pd.DataFrame(dados) if dados else criar_df_vazio()
    if not df.empty:
        df = df.drop_duplicates().sort_values(['Pagina', 'Competencia'])
    return df

def extrair_descontos_pdf_alternativo(pdf_file):
    dados = []
    with pdfplumber.open(pdf_file) as pdf:
        for pagina_num, pagina in enumerate(pdf.pages, 1):
            tabelas = pagina.extract_tables()
            if not tabelas:
                continue
                
            for tabela in tabelas:
                for i, linha in enumerate(tabela):
                    if linha and any('DESCONTOS' in str(cell).upper() for cell in linha if cell):
                        # Tentar achar o ano na linha ou na página
                        ano = "9999"
                        texto_pag = pagina.extract_text() or ""
                        ano_match = re.search(r'\b(20\d{2})\b', texto_pag)
                        if ano_match: ano = ano_match.group(1)

                        for j in range(i + 1, len(tabela)):
                            linha_desc = tabela[j]
                            if not linha_desc or not any(linha_desc): continue
                            if any(x in str(linha_desc).upper() for x in ['RENDIMENTOS', 'TOTAL']): break
                            
                            # Pega a descrição (primeira célula que não é número puro)
                            desc = next((str(c).strip() for c in linha_desc if c and not re.match(r'^[\d\.,]+$', str(c))), None)
                            if not desc: continue
                            
                            # Captura valores
                            valores = []
                            for cell in linha_desc:
                                val_limpo = re.sub(r'[^\d,]', '', str(cell)) if cell else ""
                                if ',' in val_limpo: valores.append(val_limpo)
                            
                            for idx, v in enumerate(valores[:6]): # Limita aos 6 primeiros meses
                                try:
                                    vf = float(v.replace('.', '').replace(',', '.'))
                                    if vf > 0:
                                        dados.append({
                                            'Discriminacao': desc,
                                            'Valor': f"{vf:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'),
                                            'Competencia': f"{idx+1:02d}/{ano}",
                                            'Pagina': pagina_num
                                        })
                                except: continue
    
    df = pd.DataFrame(dados) if dados else criar_df_vazio()
    if not df.empty:
        df = df.drop_duplicates().sort_values(['Pagina', 'Competencia'])
    return df

# --- INTERFACE STREAMLIT ---

def main():
    st.set_page_config(page_title="Extrator de Descontos", layout="wide")
    st.title("📄 Extrator de Descontos - Financeiro")
    
    uploaded_file = st.file_uploader("Escolha o arquivo PDF", type="pdf")
    
    if uploaded_file:
        metodo = st.radio("Método de extração:", ["Padrão (Texto)", "Alternativo (Tabelas)"], horizontal=True)
        
        if st.button("Processar PDF"):
            try:
                with st.spinner("Extraindo dados..."):
                    if "Padrão" in metodo:
                        df = extrair_descontos_pdf(uploaded_file)
                    else:
                        df = extrair_descontos_pdf_alternativo(uploaded_file)
                
                if not df.empty:
                    st.success(f"✅ {len(df)} registros encontrados!")
                    
                    col1, col2, col3 = st.columns(3)
                    col1.metric("Total de Linhas", len(df))
                    col2.metric("Páginas", df['Pagina'].nunique())
                    col3.metric("Tipos de Desconto", df['Discriminacao'].nunique())

                    st.dataframe(df, use_container_width=True)

                    # Botões de Download
                    csv = df.to_csv(index=False, sep=';', encoding='utf-8-sig')
                    st.download_button("📥 Baixar CSV", csv, "descontos.csv", "text/csv")
                else:
                    st.warning("Nenhum dado foi encontrado. Tente o outro método de extração.")
                    
            except Exception as e:
                st.error(f"Ocorreu um erro no processamento: {e}")
                st.info("Dica: Certifique-se que o PDF não é uma imagem digitalizada.")

if __name__ == "__main__":
    main()
