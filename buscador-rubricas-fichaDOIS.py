import streamlit as st
import pandas as pd
import pdfplumber
import re
from datetime import datetime
import io
import json
import pickle
import numpy as np
from typing import Optional, Dict, List

# ============================================
# MÓDULO PRINCIPAL: EXTRATOR PARA FORMATO GER.pdf
# ============================================

class ExtratorFichaFinanceiraGER:
    """Classe específica para extrair dados do formato GER.pdf"""
    
    def __init__(self):
        self.meses_map = {
            'JAN': 1, 'FEV': 2, 'MAR': 3, 'ABR': 4, 'MAI': 5, 'JUN': 6,
            'JUL': 7, 'AGO': 8, 'SET': 9, 'OUT': 10, 'NOV': 11, 'DEZ': 12
        }
    
    def converter_valor_para_float(self, valor_str: str) -> Optional[float]:
        """Converte string de valor brasileiro para float"""
        try:
            if not valor_str:
                return None
            
            # Remove espaços e caracteres não numéricos
            valor_str = str(valor_str).strip()
            
            # Se já for float, retorna
            if isinstance(valor_str, (int, float)):
                return float(valor_str)
            
            # Remove caracteres não numéricos exceto . e ,
            valor_str = re.sub(r'[^\d,\-\.]', '', valor_str)
            
            # Se estiver vazio, retorna None
            if not valor_str:
                return None
            
            # Verifica se tem ponto como separador de milhar
            if valor_str.count('.') > 0 and valor_str.count(',') > 0:
                # Formato: 1.234,56
                valor_str = valor_str.replace('.', '').replace(',', '.')
            elif ',' in valor_str:
                # Formato: 1234,56
                valor_str = valor_str.replace(',', '.')
            
            return float(valor_str)
        except:
            return None
    
    def formatar_valor_brasileiro(self, valor: float) -> str:
        """Formata float para string no padrão brasileiro"""
        try:
            if valor is None:
                return "0,00"
            
            valor = float(valor)
            # Formata com 2 casas decimais
            valor_str = f"{valor:,.2f}"
            # Substitui ponto por vírgula e vírgula por ponto
            valor_str = valor_str.replace(',', 'X').replace('.', ',').replace('X', '.')
            return valor_str
        except:
            return "0,00"
    
    def extrair_ano_referencia(self, texto: str) -> str:
        """Extrai o ano de referência do texto"""
        # Padrão: "Ficha Financeira referente a: 2016 - 1º Semestre"
        padroes = [
            r'Ficha Financeira referente a:\s*(\d{4})',
            r'(\d{4})\s*-\s*\d+º\s*Semestre',
            r'ANO\s+REFER[EÊ]NCIA.*?(\d{4})'
        ]
        
        for padrao in padroes:
            match = re.search(padrao, texto, re.IGNORECASE)
            if match:
                return match.group(1)
        
        # Tenta encontrar qualquer ano de 4 dígitos
        anos = re.findall(r'\b(19|20)\d{2}\b', texto)
        if anos:
            return anos[0]
        
        return None
    
    def determinar_tipo_rubrica(self, nome_rubrica: str) -> str:
        """Determina se é RECEITA ou DESPESA baseado no nome"""
        nome_upper = nome_rubrica.upper()
        
        # Padrões de receitas
        padroes_receita = [
            'VENCIMENTO', 'PROVENTO', 'AUXÍLIO', 'AUXILIO', 'GRATIFICAÇÃO',
            'ABONO', 'PER CAPITA', 'IQ', 'DECISÃO', 'ANUÊNIO', 'ADIANT',
            'FERIAS', 'NATALINA'
        ]
        
        for padrao in padroes_receita:
            if padrao in nome_upper:
                return 'RECEITA'
        
        # Padrões de despesas
        padroes_despesa = [
            'IMPOSTO', 'DESCONTO', 'CONTRIB', 'EMPREST', 'AMORT',
            'MENSALIDADE', 'CO-PARTIC', 'CAPESESP', 'CONT.', 'RETIDO'
        ]
        
        for padrao in padroes_despesa:
            if padrao in nome_upper:
                return 'DESPESA'
        
        return 'DESPESA'  # Padrão
    
    def processar_pdf(self, pdf_file) -> pd.DataFrame:
        """Processa o PDF no formato GER.pdf"""
        dados = []
        
        with pdfplumber.open(pdf_file) as pdf:
            texto_completo = ""
            
            # Primeiro, extrai todo o texto para análise
            for pagina_num, pagina in enumerate(pdf.pages, 1):
                texto_pagina = pagina.extract_text()
                texto_completo += texto_pagina + "\n"
            
            # Extrai ano de referência
            ano = self.extrair_ano_referencia(texto_completo)
            
            if not ano:
                st.error("Não foi possível identificar o ano de referência")
                return pd.DataFrame()
            
            st.info(f"Ano identificado: {ano}")
            
            # Agora processa cada página para extrair tabelas
            for pagina_num, pagina in enumerate(pdf.pages, 1):
                texto_pagina = pagina.extract_text()
                
                # Procura por padrão de tabela
                if 'Rubrica' not in texto_pagina and 'VENCIMENTO' not in texto_pagina:
                    continue
                
                # Extrai tabelas
                tabelas = pagina.extract_tables()
                
                for tabela_num, tabela in enumerate(tabelas):
                    if not tabela or len(tabela) < 2:
                        continue
                    
                    # Encontra linha de cabeçalho com meses
                    cabecalho_idx = -1
                    meses_colunas = {}  # {col_idx: mes_num}
                    
                    for i, linha in enumerate(tabela):
                        if not linha:
                            continue
                        
                        # Verifica se a linha contém meses
                        for col_idx, celula in enumerate(linha):
                            if celula:
                                celula_str = str(celula).strip().upper()
                                for mes_abrev, mes_num in self.meses_map.items():
                                    if mes_abrev in celula_str:
                                        meses_colunas[col_idx] = mes_num
                                        cabecalho_idx = i
                                        break
                        
                        if meses_colunas:
                            break
                    
                    if not meses_colunas:
                        continue
                    
                    # Processa linhas após o cabeçalho
                    for i in range(cabecalho_idx + 1, len(tabela)):
                        linha = tabela[i]
                        
                        if not linha or len(linha) < 2:
                            continue
                        
                        # Encontra código e nome da rubrica
                        codigo = None
                        nome_rubrica = None
                        
                        # Procura código (padrão: 00001, 00013, etc.)
                        for celula in linha:
                            if celula:
                                celula_str = str(celula).strip()
                                if re.match(r'^\d{5,}$', celula_str):
                                    codigo = celula_str
                                elif celula_str and not re.match(r'^[\d\.,\s]+$', celula_str):
                                    # Se não for apenas números/pontos/vírgulas, é nome
                                    nome_rubrica = celula_str
                        
                        if not nome_rubrica:
                            continue
                        
                        # Determina tipo
                        tipo = self.determinar_tipo_rubrica(nome_rubrica)
                        
                        # Extrai valores dos meses
                        for col_idx, mes_num in meses_colunas.items():
                            if col_idx < len(linha) and linha[col_idx]:
                                valor_str = str(linha[col_idx]).strip()
                                valor_float = self.converter_valor_para_float(valor_str)
                                
                                if valor_float is not None and valor_float != 0:
                                    # Formata competência
                                    competencia = f"{mes_num:02d}/{ano}"
                                    
                                    # Formata valor
                                    valor_formatado = self.formatar_valor_brasileiro(valor_float)
                                    
                                    dados.append({
                                        'Codigo_Rubrica': codigo or '',
                                        'Discriminacao': nome_rubrica,
                                        'Valor': valor_formatado,
                                        'Valor_Numerico': valor_float,
                                        'Competencia': competencia,
                                        'Pagina': pagina_num,
                                        'Ano': ano,
                                        'Tipo': tipo,
                                        'Semestre': '1' if mes_num <= 6 else '2'
                                    })
        
        if dados:
            df = pd.DataFrame(dados)
            df = df.drop_duplicates()
            return df
        else:
            return pd.DataFrame()

# ============================================
# INTERFACE STREAMLOT SIMPLIFICADA
# ============================================

def main():
    st.set_page_config(
        page_title="Extrator de Ficha Financeira GER",
        page_icon="📊",
        layout="wide"
    )
    
    st.title("📊 Extrator de Ficha Financeira GER.pdf")
    st.markdown("### Extraia dados de fichas financeiras no formato específico do GER.pdf")
    
    # Upload do arquivo
    uploaded_file = st.file_uploader(
        "Faça upload do arquivo GER.pdf",
        type="pdf",
        help="Arquivo no formato de ficha financeira com padrão 'Ficha Financeira referente a: ANO - SEMESTRE'"
    )
    
    if uploaded_file is not None:
        st.success(f"✅ Arquivo carregado: {uploaded_file.name}")
        
        # Botão para processar
        if st.button("🔍 Processar Arquivo", type="primary", use_container_width=True):
            with st.spinner("Processando PDF..."):
                try:
                    extrator = ExtratorFichaFinanceiraGER()
                    df = extrator.processar_pdf(uploaded_file)
                    
                    if not df.empty:
                        st.success(f"✅ {len(df)} registros extraídos com sucesso!")
                        
                        # Mostrar estatísticas
                        col1, col2, col3, col4 = st.columns(4)
                        with col1:
                            st.metric("Total Registros", len(df))
                        with col2:
                            st.metric("Anos", df['Ano'].nunique())
                        with col3:
                            st.metric("Rubricas", df['Discriminacao'].nunique())
                        with col4:
                            total_valor = df['Valor_Numerico'].sum()
                            st.metric("Valor Total", f"R$ {total_valor:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'))
                        
                        # Mostrar tipos
                        st.subheader("📋 Distribuição por Tipo")
                        tipo_counts = df['Tipo'].value_counts()
                        for tipo, count in tipo_counts.items():
                            st.write(f"**{tipo}**: {count} registros")
                        
                        # Mostrar primeiros registros
                        st.subheader("📋 Dados Extraídos (Primeiros 50 registros)")
                        st.dataframe(
                            df[['Discriminacao', 'Valor', 'Competencia', 'Ano', 'Tipo', 'Pagina']].head(50),
                            use_container_width=True,
                            hide_index=True
                        )
                        
                        # Filtros
                        st.subheader("🎯 Filtros")
                        col_f1, col_f2 = st.columns(2)
                        with col_f1:
                            tipos_filtro = st.multiselect(
                                "Tipo:",
                                df['Tipo'].unique(),
                                default=df['Tipo'].unique()
                            )
                        
                        with col_f2:
                            anos_filtro = st.multiselect(
                                "Ano:",
                                df['Ano'].unique(),
                                default=df['Ano'].unique()
                            )
                        
                        # Aplicar filtros
                        df_filtrado = df.copy()
                        if tipos_filtro:
                            df_filtrado = df_filtrado[df_filtrado['Tipo'].isin(tipos_filtro)]
                        if anos_filtro:
                            df_filtrado = df_filtrado[df_filtrado['Ano'].isin(anos_filtro)]
                        
                        # Exportação
                        st.subheader("📥 Exportar Dados")
                        
                        col_e1, col_e2 = st.columns(2)
                        
                        with col_e1:
                            # Exportar CSV
                            csv = df_filtrado.to_csv(index=False, sep=';', encoding='utf-8-sig')
                            st.download_button(
                                label="⬇️ Baixar CSV",
                                data=csv,
                                file_name=f"ficha_financeira_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                                mime="text/csv"
                            )
                        
                        with col_e2:
                            # Exportar Excel
                            buffer = io.BytesIO()
                            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                                df_filtrado.to_excel(writer, index=False, sheet_name='Dados')
                            buffer.seek(0)
                            st.download_button(
                                label="⬇️ Baixar Excel",
                                data=buffer,
                                file_name=f"ficha_financeira_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                            )
                        
                        # Mostrar dados filtrados
                        st.write(f"**Registros após filtro:** {len(df_filtrado)}")
                        st.dataframe(
                            df_filtrado[['Discriminacao', 'Valor', 'Competencia', 'Ano', 'Tipo', 'Pagina']],
                            use_container_width=True,
                            hide_index=True
                        )
                        
                    else:
                        st.error("⚠️ Nenhum dado extraído. Verifique se o formato do arquivo está correto.")
                        
                except Exception as e:
                    st.error(f"❌ Erro ao processar arquivo: {str(e)}")
    
    else:
        # Instruções
        st.info("👆 Faça upload de um arquivo PDF no formato GER.pdf para começar.")
        
        with st.expander("ℹ️ Sobre o formato esperado"):
            st.markdown("""
            ### 📋 **FORMATO ESPERADO:**
            
            O extrator foi desenvolvido para processar fichas financeiras no formato **GER.pdf**.
            
            **Características do formato:**
            1. **Cabeçalho**: "Ficha Financeira referente a: 2016 - 1º Semestre"
            2. **Ano de referência**: Extraído automaticamente (ex: 2016, 2017, etc.)
            3. **Meses**: JAN, FEV, MAR, ABR, MAI, JUN (1º semestre) ou JUL, AGO, SET, OUT, NOV, DEZ (2º semestre)
            4. **Rubricas**: Código (ex: 00001) e Nome (ex: VENCIMENTO BASICO)
            5. **Valores**: No formato brasileiro (ex: 4.100,61)
            
            **Exemplos de rubricas esperadas:**
            - VENCIMENTO BASICO
            - ANUÊNIO-ART.244,LEI 8112/90 AT
            - AUXÍLIO-ALIMENTAÇÃO
            - IMPOSTO DE RENDA RETIDO FONTE
            - EMPREST BCO PRIVADOS - ITAU BM
            """)
        
        with st.expander("🔄 Como testar"):
            st.markdown("""
            ### 🧪 **TESTE RÁPIDO:**
            
            1. **Use o arquivo GER.pdf** que você já tem
            2. **Faça upload** usando o botão acima
            3. **Clique em "Processar Arquivo"**
            4. **Verifique os dados** extraídos
            
            **Colunas extraídas:**
            - `Discriminacao`: Nome da rubrica
            - `Valor`: Valor formatado (ex: 4.100,61)
            - `Competencia`: Mês/Ano (ex: 01/2016)
            - `Ano`: Ano de referência
            - `Tipo`: RECEITA ou DESPESA
            - `Pagina`: Número da página no PDF
            """)

if __name__ == "__main__":
    main()
