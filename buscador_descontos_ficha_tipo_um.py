import streamlit as st
import pandas as pd
import pdfplumber
import re
from datetime import datetime
import io

def extrair_descontos_pdf(pdf_file):
    """
    Extrai os descontos de um PDF de demonstrativos financeiros.
    
    Args:
        pdf_file: Arquivo PDF carregado via Streamlit
        
    Returns:
        DataFrame com colunas: Discriminacao, Valor, Competencia, Pagina
    """
    
    dados = []
    
    with pdfplumber.open(pdf_file) as pdf:
        for pagina_num, pagina in enumerate(pdf.pages, 1):
            texto = pagina.extract_text()
            
            if not texto:
                continue
                
            # Extrair ano de referência
            ano_match = re.search(r'ANO REFERÊNCIA\s*(\d{4})', texto)
            ano = ano_match.group(1) if ano_match else None
            
            if not ano:
                continue
            
            # Extrair tabela como texto
            tabela_texto = pagina.extract_text()
            
            # Dividir em linhas
            linhas = tabela_texto.split('\n')
            
            # Encontrar onde começa a seção de descontos
            desconto_start = False
            
            for i, linha in enumerate(linhas):
                # Verificar se é cabeçalho de descontos
                if 'DESCONTOS' in linha.upper():
                    desconto_start = True
                    continue
                
                # Se encontrou a próxima seção (RENDIMENTOS novamente ou TOTAL), parar
                if desconto_start and ('RENDIMENTOS' in linha.upper() or 'TOTAL BRUTO' in linha.upper() or 'TOTAL LIQUIDO' in linha.upper()):
                    break
                
                # Processar linhas de descontos
                if desconto_start and linha.strip():
                    # Tentar identificar padrão de linha de desconto
                    # Geralmente começa com descrição seguida de valores
                    
                    # Remover múltiplos espaços
                    linha_limpa = ' '.join(linha.split())
                    
                    # Verificar se parece ser uma linha com valores monetários
                    # Procura por padrões como "##.###,##" ou "#.##,##"
                    padrao_valor = r'\d{1,3}(?:\.\d{3})*,\d{2}'
                    
                    if re.search(padrao_valor, linha_limpa):
                        # Tentar separar descrição e valores
                        partes = re.split(rf'({padrao_valor})', linha_limpa)
                        partes = [p.strip() for p in partes if p.strip()]
                        
                        if len(partes) > 1:
                            # Primeira parte é a descrição
                            discriminacao = partes[0]
                            
                            # Valores são as partes numéricas
                            valores = [re.sub(r'[^\d,]', '', v) for v in partes[1:] if re.match(padrao_valor, v)]
                            
                            # Mapear meses (assumindo ordem: JAN, FEV, MAR, ABR, MAI, JUN, TOTAL)
                            meses = ['JAN', 'FEV', 'MAR', 'ABR', 'MAI', 'JUN']
                            
                            for mes_idx, mes in enumerate(meses):
                                if mes_idx < len(valores) - 1:  # -1 para excluir total
                                    valor_str = valores[mes_idx]
                                    
                                    # Converter para formato numérico
                                    try:
                                        # Converter de "1.234,56" para 1234.56
                                        valor_float = float(valor_str.replace('.', '').replace(',', '.'))
                                        
                                        # Formatar para string brasileira
                                        valor_formatado = f"{valor_float:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
                                        
                                        # Criar competência
                                        competencia = f"{mes_idx + 1:02d}/{ano}"
                                        
                                        # Adicionar aos dados
                                        dados.append({
                                            'Discriminacao': discriminacao,
                                            'Valor': valor_formatado,
                                            'Competencia': competencia,
                                            'Pagina': pagina_num
                                        })
                                    except:
                                        continue
    
    # Criar DataFrame
    df = pd.DataFrame(dados)
    
    # Remover duplicados
    df = df.drop_duplicates()
    
    # Ordenar por página e descrição
    df = df.sort_values(['Pagina', 'Discriminacao', 'Competencia'])
    
    return df

def extrair_descontos_pdf_alternativo(pdf_file):
    """
    Método alternativo usando extração de tabelas do pdfplumber
    """
    dados = []
    
    with pdfplumber.open(pdf_file) as pdf:
        for pagina_num, pagina in enumerate(pdf.pages, 1):
            # Extrair tabelas
            tabelas = pagina.extract_tables()
            
            if not tabelas:
                continue
                
            for tabela in tabelas:
                # Procurar por linha com "DESCONTOS"
                for i, linha in enumerate(tabela):
                    if linha and any('DESCONTOS' in str(cell).upper() for cell in linha):
                        # Encontrar ano
                        ano = None
                        for cell in linha:
                            if cell and re.search(r'\b\d{4}\b', str(cell)):
                                ano = re.search(r'\b(\d{4})\b', str(cell)).group(1)
                                break
                        
                        # Processar linhas de descontos
                        for j in range(i + 1, len(tabela)):
                            linha_desc = tabela[j]
                            
                            if not linha_desc or not any(linha_desc):
                                continue
                                
                            # Verificar se é início de nova seção
                            if any('RENDIMENTOS' in str(cell).upper() for cell in linha_desc if cell):
                                break
                                
                            if any('TOTAL' in str(cell).upper() for cell in linha_desc if cell):
                                break
                            
                            # Extrair descrição (primeira célula não vazia)
                            discriminacao = None
                            for cell in linha_desc:
                                if cell and cell.strip() and not re.match(r'\d+[,\.]\d+', str(cell)):
                                    discriminacao = cell.strip()
                                    break
                            
                            if not discriminacao:
                                continue
                            
                            # Extrair valores (células com números)
                            valores = []
                            meses = ['JAN', 'FEV', 'MAR', 'ABR', 'MAI', 'JUN']
                            
                            for idx, cell in enumerate(linha_desc):
                                if cell and re.match(r'[\d\.,]+', str(cell)):
                                    valor_str = str(cell).strip()
                                    # Limpar valor
                                    valor_str = re.sub(r'[^\d,]', '', valor_str)
                                    if valor_str and idx < 7:  # Primeiros 6 meses + total
                                        valores.append(valor_str)
                            
                            # Adicionar para cada mês
                            for mes_idx in range(min(6, len(valores) - 1)):  # Excluir total
                                try:
                                    if valores[mes_idx]:
                                        # Converter para formato numérico
                                        valor_float = float(valores[mes_idx].replace('.', '').replace(',', '.'))
                                        valor_formatado = f"{valor_float:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
                                        competencia = f"{mes_idx + 1:02d}/{ano}"
                                        
                                        dados.append({
                                            'Discriminacao': discriminacao,
                                            'Valor': valor_formatado,
                                            'Competencia': competencia,
                                            'Pagina': pagina_num
                                        })
                                except:
                                    continue
    
    df = pd.DataFrame(dados)
    df = df.drop_duplicates()
    df = df.sort_values(['Pagina', 'Discriminacao', 'Competencia'])
    
    return df

def main():
    st.title("📄 Extrator de Descontos - Demonstrativos Financeiros")
    
    st.markdown("""
    Faça upload do PDF contendo os demonstrativos financeiros.
    O sistema irá extrair automaticamente todos os descontos listados.
    """)
    
    # Upload do arquivo
    uploaded_file = st.file_uploader("Escolha o arquivo PDF", type="pdf")
    
    if uploaded_file is not None:
        st.success("Arquivo carregado com sucesso!")
        
        # Opção de método de extração
        metodo = st.radio(
            "Selecione o método de extração:",
            ["Método Padrão", "Método Alternativo"],
            horizontal=True
        )
        
        # Extrair dados
        with st.spinner("Processando PDF..."):
            try:
                if metodo == "Método Padrão":
                    df = extrair_descontos_pdf(uploaded_file)
                else:
                    df = extrair_descontos_pdf_alternativo(uploaded_file)
                
                if not df.empty:
                    st.success(f"✅ {len(df)} registros extraídos com sucesso!")
                    
                    # Mostrar dados
                    st.subheader("📊 Dados Extraídos")
                    st.dataframe(df)
                    
                    # Estatísticas
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Total de Registros", len(df))
                    with col2:
                        st.metric("Páginas Processadas", df['Pagina'].nunique())
                    with col3:
                        st.metric("Tipos de Desconto", df['Discriminacao'].nunique())
                    
                    # Download como CSV
                    csv = df.to_csv(index=False, sep=';', encoding='utf-8-sig')
                    st.download_button(
                        label="📥 Baixar como CSV",
                        data=csv,
                        file_name="descontos_extraidos.csv",
                        mime="text/csv"
                    )
                    
                    # Download como Excel
                    excel_buffer = io.BytesIO()
                    with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                        df.to_excel(writer, index=False, sheet_name='Descontos')
                    excel_buffer.seek(0)
                    
                    st.download_button(
                        label="📥 Baixar como Excel",
                        data=excel_buffer,
                        file_name="descontos_extraidos.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
                    
                    # Filtrar por página
                    st.subheader("🔍 Filtros")
                    paginas_unicas = sorted(df['Pagina'].unique())
                    pagina_selecionada = st.selectbox(
                        "Filtrar por página:",
                        ["Todas"] + paginas_unicas
                    )
                    
                    if pagina_selecionada != "Todas":
                        df_filtrado = df[df['Pagina'] == pagina_selecionada]
                        st.dataframe(df_filtrado)
                        
                        # Download do filtrado
                        csv_filtrado = df_filtrado.to_csv(index=False, sep=';', encoding='utf-8-sig')
                        st.download_button(
                            label=f"📥 Baixar Página {pagina_selecionada} como CSV",
                            data=csv_filtrado,
                            file_name=f"descontos_pagina_{pagina_selecionada}.csv",
                            mime="text/csv"
                        )
                else:
                    st.warning("Nenhum desconto foi encontrado no PDF.")
                    
            except Exception as e:
                st.error(f"Erro ao processar o arquivo: {str(e)}")
                st.info("""
                Dicas para solucionar problemas:
                1. Verifique se o PDF é selecionável (não é uma imagem)
                2. Confira se o formato segue o padrão mostrado
                3. Tente usar o método alternativo
                """)

if __name__ == "__main__":
    main()
