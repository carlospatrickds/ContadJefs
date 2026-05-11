import streamlit as st
import pdfplumber
import pandas as pd
import re
from datetime import datetime
from io import BytesIO

# Importamos o WeasyPrint para gerar o PDF
try:
    from weasyprint import HTML
    WEASYPRINT_INSTALADO = True
except ImportError:
    WEASYPRINT_INSTALADO = False

st.set_page_config(layout="wide", page_title="Sistema Pericial - Extração e Cálculo")

MESES_MAPA = {
    "JAN":1,"FEV":2,"MAR":3,"ABR":4,"MAI":5,"JUN":6,
    "JUL":7,"AGO":8,"SET":9,"OUT":10,"NOV":11,"DEZ":12
}

# ==============================================================================
# 1. MOTOR DE EXTRAÇÃO (Seu código original mantido)
# ==============================================================================
class FichaFinanceiraParser:
    def __init__(self, pdf_bytes):
        self.pdf_bytes = pdf_bytes
        self.tipo_atual = None
        self.ano_atual = None
        self.meses_ativos = []
        self.metadados = {}
        self.dados = []

    def _normalizar_moeda(self, valor):
        if not valor: return None
        valor = valor.replace('.', '').replace(',', '.')
        try: return float(valor)
        except: return None

    def _detectar_ano(self, linha):
        match = re.search(r"\b(20\d{2}|19\d{2})\b", linha)
        if match: self.ano_atual = int(match.group())

    def _detectar_meses(self, linha):
        meses_detectados = []
        for mes in MESES_MAPA.keys():
            if mes in linha.upper(): meses_detectados.append(mes)
        if len(meses_detectados) >= 3: self.meses_ativos = meses_detectados

    def _detectar_tipo(self, linha):
        if "RENDIMENTO" in linha.upper(): self.tipo_atual = "RECEITA"
        elif "DESCONTO" in linha.upper(): self.tipo_atual = "DESCONTO"

    def _extrair_metadados(self, texto):
        nome = re.search(r"NOME.*?\n(.+)", texto, re.IGNORECASE)
        cpf = re.search(r"\d{3}\.\d{3}\.\d{3}-\d{2}", texto)
        cargo = re.search(r"CARGO.*?\n(.+)", texto, re.IGNORECASE)
        emissao = re.search(r"EMISS[ÃA]O.*?(\d{2}/\d{2}/\d{4})", texto)
        self.metadados = {
            "Nome": nome.group(1).strip() if nome else "Não identificado",
            "CPF": cpf.group() if cpf else "Não identificado",
            "Cargo": cargo.group(1).strip() if cargo else "",
            "Data Emissão": emissao.group(1) if emissao else ""
        }

    def _processar_linha_rubrica(self, linha, pagina):
        padrao = r"(.+?)\s+((?:\d{1,3}(?:\.\d{3})*,\d{2}\s*)+)"
        match = re.match(padrao, linha)
        if not match: return

        descricao = match.group(1).strip()
        valores = re.findall(r"\d{1,3}(?:\.\d{3})*,\d{2}", match.group(2))

        for i, valor in enumerate(valores):
            if i >= len(self.meses_ativos): continue
            mes = self.meses_ativos[i]
            valor_float = self._normalizar_moeda(valor)

            if valor_float and valor_float != 0 and self.ano_atual:
                competencia = f"{MESES_MAPA[mes]:02d}/{self.ano_atual}" # Formato MM/YYYY
                self.dados.append({
                    "Discriminacao": descricao,
                    "Valor": valor_float,
                    "Competencia": competencia,
                    "Pagina": pagina,
                    "Ano": self.ano_atual,
                    "Tipo": self.tipo_atual
                })

    def executar(self):
        with pdfplumber.open(self.pdf_bytes) as pdf:
            for numero_pagina, pagina in enumerate(pdf.pages, start=1):
                texto = pagina.extract_text()
                if not texto: continue
                if numero_pagina == 1: self._extrair_metadados(texto)
                for linha in texto.split("\n"):
                    self._detectar_ano(linha)
                    self._detectar_meses(linha)
                    self._detectar_tipo(linha)
                    self._processar_linha_rubrica(linha, numero_pagina)
        df = pd.DataFrame(self.dados)
        return df, self.metadados

# ==============================================================================
# 2. MOTOR DE GERAR PDF (WeasyPrint)
# ==============================================================================
def gerar_pdf_laudo(df_calculo, metadados, total_devido):
    linhas_tabela = ""
    for _, row in df_calculo.iterrows():
        linhas_tabela += f"""
        <tr>
            <td>{row['Competencia']}</td>
            <td>{row['Base']:.2f}</td>
            <td>{row['Abono']:.2f}</td>
            <td>{row['Diferenca']:.2f}</td>
            <td>{row['Fator IPCA-E']}</td>
            <td>{row['Valor Atualizado']:.2f}</td>
        </tr>
        """

    html_content = f"""
    <!DOCTYPE html>
    <html lang="pt">
    <head>
    <meta charset="UTF-8">
    <style>
        @page {{ size: A4; margin: 20mm; background-color: #faf8f5; }}
        body {{ font-family: Arial, sans-serif; font-size: 11pt; color: #2c3e50; }}
        h1 {{ color: #1a4f76; font-size: 16pt; text-align: center; border-bottom: 2px solid #1a4f76; padding-bottom: 10px; text-transform: uppercase; }}
        .subtitle {{ text-align: center; font-size: 12pt; color: #555; margin-bottom: 30px; }}
        h2 {{ color: #1a4f76; font-size: 13pt; margin-top: 25px; border-left: 4px solid #e74c3c; padding-left: 8px; }}
        .info-table {{ width: 100%; margin-bottom: 20px; border-collapse: collapse; background-color: #fff; border: 1px solid #e0e0e0; }}
        .info-table td {{ padding: 8px; border-bottom: 1px solid #eee; }}
        .data-table {{ width: 100%; border-collapse: collapse; margin-top: 15px; font-size: 10pt; background-color: #fff; }}
        .data-table th {{ background-color: #1a4f76; color: white; padding: 10px; text-align: right; border: 1px solid #bdc3c7; }}
        .data-table th:first-child {{ text-align: left; }}
        .data-table td {{ padding: 8px; border: 1px solid #bdc3c7; text-align: right; }}
        .data-table td:first-child {{ text-align: left; }}
        .total-row td {{ font-weight: bold; background-color: #e8f4f8 !important; color: #1a4f76; }}
    </style>
    </head>
    <body>
        <h1>Parecer Técnico de Cálculo Judiciário</h1>
        <div class="subtitle">Apuração de Reflexos do Abono de Permanência</div>
        <table class="info-table">
            <tr><td><strong>Servidor:</strong> {metadados.get('Nome', '')}</td><td><strong>CPF:</strong> {metadados.get('CPF', '')}</td></tr>
            <tr><td><strong>Assistente Técnico:</strong> Carlos Patrick da Silva</td><td><strong>Data:</strong> {datetime.today().strftime('%d/%m/%Y')}</td></tr>
        </table>
        <h2>1. Resumo da Apuração Financeira</h2>
        <table class="data-table">
            <thead>
                <tr>
                    <th>Competência</th><th>Base Calculada (R$)</th><th>Abono (R$)</th>
                    <th>Diferença (R$)</th><th>Fator IPCA-E</th><th>Atualizado (R$)</th>
                </tr>
            </thead>
            <tbody>
                {linhas_tabela}
                <tr class="total-row">
                    <td colspan="5">TOTAL GERAL DEVIDO</td>
                    <td>R$ {total_devido:.2f}</td>
                </tr>
            </tbody>
        </table>
    </body>
    </html>
    """
    
    pdf_buffer = BytesIO()
    HTML(string=html_content).write_pdf(pdf_buffer)
    return pdf_buffer.getvalue()

# ==============================================================================
# 3. INTERFACE DO STREAMLIT
# ==============================================================================
st.title("⚖️ Sistema de Extração e Cálculo Pericial")

if 'df_extraido' not in st.session_state:
    st.session_state.df_extraido = pd.DataFrame()
if 'metadados' not in st.session_state:
    st.session_state.metadados = {}
if 'df_final' not in st.session_state:
    st.session_state.df_final = pd.DataFrame()

tab1, tab2, tab3 = st.tabs(["📄 1. Extração da Ficha", "🧮 2. Parâmetros e Cálculo", "🖨️ 3. Relatório e PDF"])

# --- ABA 1: EXTRAÇÃO ---
with tab1:
    arquivo = st.file_uploader("Faça o Upload do PDF da Ficha Financeira", type="pdf")
    if arquivo:
        if st.button("Processar PDF"):
            with st.spinner("Extraindo rubricas..."):
                parser = FichaFinanceiraParser(arquivo)
                df, meta = parser.executar()
                st.session_state.df_extraido = df
                st.session_state.metadados = meta
                st.success("Extração concluída!")
    
    if not st.session_state.df_extraido.empty:
        st.write("### Dados Extraídos")
        st.dataframe(st.session_state.df_extraido)

# --- ABA 2: CÁLCULOS ---
with tab2:
    if not st.session_state.df_extraido.empty:
        df = st.session_state.df_extraido
        rubricas_unicas = sorted(df["Discriminacao"].unique())
        
        col1, col2 = st.columns(2)
        with col1:
            st.write("### Seleção de Rubricas")
            rubrica_base = st.selectbox("Selecione a Rubrica Base (ex: 13º ou Férias)", rubricas_unicas)
            rubrica_abono = st.selectbox("Selecione a Rubrica do Abono", rubricas_unicas)
        
        with col2:
            st.write("### Tabela de Índices (Cole do Excel)")
            st.info("Cole os dados na ordem: Competência (MM/YYYY) | Fator Correção | Mora | Selic")
            indices_texto = st.text_area("Dados Copiados", height=150, placeholder="12/2023\t1.125\t0.01\t0.00\n01/2024\t1.112\t0.01\t0.00")
        
        if st.button("Executar Cálculo"):
            if indices_texto.strip() == "":
                st.error("Por favor, cole os índices de correção.")
            else:
                # 1. Transformar o texto colado num DataFrame de índices
                linhas_indices = [linha.split() for linha in indices_texto.strip().split('\n')]
                df_indices = pd.DataFrame(linhas_indices, columns=['Competencia', 'Fator IPCA-E', 'Mora', 'Selic'])
                df_indices['Fator IPCA-E'] = df_indices['Fator IPCA-E'].str.replace(',', '.').astype(float)
                
                # 2. Separar as rubricas escolhidas
                df_base = df[df['Discriminacao'] == rubrica_base][['Competencia', 'Valor']].rename(columns={'Valor': 'Base'})
                df_ab = df[df['Discriminacao'] == rubrica_abono][['Competencia', 'Valor']].rename(columns={'Valor': 'Abono'})
                
                # 3. Juntar e Calcular (Onde teve Base e Abono na mesma competência)
                df_calc = pd.merge(df_base, df_ab, on='Competencia')
                df_calc['Diferenca'] = df_calc['Abono'] # O reflexo é a integração do próprio abono
                
                # 4. Aplicar a Correção Monetária
                df_final = pd.merge(df_calc, df_indices, on='Competencia', how='left')
                df_final['Valor Atualizado'] = df_final['Diferenca'] * df_final['Fator IPCA-E']
                
                st.session_state.df_final = df_final
                st.success("Cálculo realizado com sucesso! Vá para a Aba 3.")
    else:
        st.warning("Extraia os dados na Aba 1 primeiro.")

# --- ABA 3: RELATÓRIO ---
with tab3:
    if not st.session_state.df_final.empty:
        df_final = st.session_state.df_final.fillna(0) # Tratar vazios
        total = df_final['Valor Atualizado'].sum()
        
        st.write("### Pré-visualização do Cálculo")
        st.dataframe(df_final[['Competencia', 'Base', 'Abono', 'Diferenca', 'Fator IPCA-E', 'Valor Atualizado']])
        st.markdown(f"#### **Total Devido Apurado: R$ {total:,.2f}**")
        
        if WEASYPRINT_INSTALADO:
            pdf_bytes = gerar_pdf_laudo(df_final, st.session_state.metadados, total)
            st.download_button(
                label="📄 Baixar Laudo em PDF Profissional",
                data=pdf_bytes,
                file_name="Parecer_Tecnico_Reflexos.pdf",
                mime="application/pdf"
            )
        else:
            st.error("Biblioteca 'weasyprint' não instalada. Execute: pip install weasyprint no terminal para habilitar o PDF.")
    else:
        st.warning("Realize os cálculos na Aba 2 primeiro.")
