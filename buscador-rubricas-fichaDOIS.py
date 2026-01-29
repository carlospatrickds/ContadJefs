import streamlit as st
import pandas as pd
import re
from datetime import datetime
import io

def extract_from_text(text):
    """Extrai dados diretamente do texto colado"""
    dados = []
    
    # Dividir por linhas
    linhas = text.split('\n')
    
    # Encontrar ano
    ano = None
    for linha in linhas:
        if '2016' in linha:
            ano = '2016'
            break
        elif '2017' in linha:
            ano = '2017'
            break
        elif '2018' in linha:
            ano = '2018'
            break
    
    if not ano:
        ano = '2024'
    
    # Procurar por padrões específicos
    for linha in linhas:
        linha = linha.strip()
        
        # Padrão: código + rubrica + valores
        # Ex: "00001 VENCIMENTO BASICOR 04.100,614.100,614.100,614.100.614.256,444.256,44"
        
        # Procura por código de 5 dígitos no início
        match = re.match(r'^(\d{5})\s+(.+?)\s+([RD])\s+', linha)
        if match:
            codigo = match.group(1)
            rubrica = match.group(2).strip()
            tipo = "RECEITA" if match.group(3) == "R" else "DESPESA"
            
            # Tentar extrair valores (últimos números da linha)
            valores_match = re.findall(r'([\d\.,]+)', linha)
            if valores_match and len(valores_match) > 1:
                # Pegar o primeiro valor após o código/rubrica
                primeiro_valor = valores_match[0]
                
                # Converter
                try:
                    valor_clean = primeiro_valor.replace('.', '').replace(',', '.')
                    valor_num = float(valor_clean)
                    valor_formatado = f"{valor_num:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
                    
                    dados.append({
                        'Codigo': codigo,
                        'Rubrica': rubrica,
                        'Valor': valor_formatado,
                        'Valor_Num': valor_num,
                        'Ano': ano,
                        'Tipo': tipo
                    })
                except:
                    pass
    
    return pd.DataFrame(dados)

def main_manual():
    """Interface para entrada manual de texto"""
    st.set_page_config(page_title="Extrator Manual GER", layout="wide")
    
    st.title("📝 Extrator Manual - Cole o texto do GER.pdf")
    
    st.markdown("""
    ### Como usar:
    1. Abra o arquivo GER.pdf
    2. Selecione e copie UM TRECHO com dados (exemplo abaixo)
    3. Cole na área de texto
    4. Clique em Processar
    
    **Exemplo do formato esperado:**
    ```
    00001 VENCIMENTO BASICOR 04.100,614.100,614.100,614.100.614.256,444.256,44
    00013 ANUÊNIO-ART.244,LEI 8112/90 AT10902,13902,13902,13936,41936,41
    00136 AUXÍLIO-ALIMENTAÇÃO10458,00458,00458,00458,00458,00
    ```
    """)
    
    texto_input = st.text_area(
        "Cole o texto do GER.pdf aqui:",
        height=300,
        placeholder="Cole aqui o texto copiado do PDF..."
    )
    
    if st.button("🔍 Processar Texto", type="primary"):
        if texto_input:
            with st.spinner("Processando..."):
                df = extract_from_text(texto_input)
                
                if not df.empty:
                    st.success(f"✅ {len(df)} registros encontrados!")
                    
                    # Mostrar dados
                    st.dataframe(df, use_container_width=True)
                    
                    # Exportar
                    csv = df.to_csv(index=False, sep=';', encoding='utf-8-sig')
                    st.download_button(
                        "⬇️ Baixar CSV",
                        csv,
                        f"ger_manual_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                        "text/csv"
                    )
                else:
                    st.error("Nenhum dado encontrado no texto.")
                    
                    # Mostrar análise do texto
                    with st.expander("🔍 Análise do texto"):
                        st.write(f"Tamanho do texto: {len(texto_input)} caracteres")
                        st.write("Primeiras 500 caracteres:")
                        st.code(texto_input[:500])
        else:
            st.warning("Por favor, cole algum texto primeiro.")

if __name__ == "__main__":
    main_manual()
