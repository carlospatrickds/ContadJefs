import streamlit as st
import pandas as pd
from fpdf import FPDF
import base64

# -----------------------------------------------------------------------------
# Tabelas de contribuição do RPPS (Regime Próprio da União) – 2020 a 2026
# Cada tabela é uma lista de (limite_inferior, limite_superior, alíquota)
# O cálculo é progressivo por faixas.
# -----------------------------------------------------------------------------

TABLES = {
    2020: [
        (0.00, 1045.00, 0.075),        # até um salário mínimo (R$ 1.045)
        (1045.01, 2000.00, 0.09),      # de 1.045,01 até 2.000
        (2000.01, 3000.00, 0.12),      # de 2.000,01 até 3.000
        (3000.01, 5839.45, 0.14),      # de 3.000,01 até teto INSS
        (5839.46, 10000.00, 0.145),    # de 5.839,46 até 10.000
        (10000.01, 20000.00, 0.165),   # de 10.000,01 até 20.000
        (20000.01, 39000.00, 0.19),    # de 20.000,01 até 39.000
        (39000.01, float('inf'), 0.22),# acima de 39.000,01
    ],
    2021: [
        (0.00, 1100.00, 0.075),        # até 1 salário mínimo (R$ 1.100)
        (1100.01, 2203.48, 0.09),      # de 1.100,01 até 2.203,48
        (2203.49, 3305.22, 0.12),      # de 2.203,49 até 3.305,22
        (3305.23, 6433.57, 0.14),      # de 3.305,23 até 6.433,57
        (6433.58, 11017.42, 0.145),    # de 6.433,58 até 11.017,42
        (11017.43, 22034.83, 0.165),   # de 11.017,43 até 22.034,83
        (22034.84, 42967.92, 0.19),    # de 22.034,84 até 42.967,92
        (42967.93, float('inf'), 0.22),# acima de 42.967,92
    ],
    2022: [
        (0.00, 1212.00, 0.075),
        (1212.01, 2427.35, 0.09),
        (2427.36, 3641.03, 0.12),
        (3641.04, 7087.22, 0.14),
        (7087.23, 12136.79, 0.145),
        (12136.80, 24273.57, 0.165),
        (24273.58, 47333.46, 0.19),
        (47333.47, float('inf'), 0.22),
    ],
    2023: [
        (0.00, 1302.00, 0.075),
        (1302.01, 2571.29, 0.09),
        (2571.30, 3856.94, 0.12),
        (3856.95, 7507.49, 0.14),
        (7507.50, 12856.50, 0.145),
        (12856.51, 25712.99, 0.165),
        (25713.00, 50140.33, 0.19),
        (50140.34, float('inf'), 0.22),
    ],
    2024: [
        (0.00, 1412.00, 0.075),
        (1412.01, 2666.68, 0.09),
        (2666.69, 4000.03, 0.12),
        (4000.04, 7786.02, 0.14),
        (7786.03, 13333.48, 0.145),
        (13333.49, 26666.94, 0.165),
        (26666.95, 52000.54, 0.19),
        (52000.55, float('inf'), 0.22),
    ],
    2025: [
        (0.00, 1518.00, 0.075),
        (1518.01, 2793.88, 0.09),
        (2793.89, 4190.83, 0.12),
        (4190.84, 8157.41, 0.14),
        (8157.42, 13969.49, 0.145),
        (13969.50, 27938.95, 0.165),
        (27938.96, 54480.97, 0.19),
        (54480.98, float('inf'), 0.22),
    ],
    2026: [
        (0.00, 1621.00, 0.075),
        (1621.01, 2902.84, 0.09),
        (2902.85, 4354.27, 0.12),
        (4354.28, 8475.55, 0.14),
        (8475.56, 14514.30, 0.145),
        (14514.31, 29028.57, 0.165),
        (29028.58, 56605.73, 0.19),
        (56605.74, float('inf'), 0.22),
    ],
}

# Anos disponíveis (ordenados)
AVAILABLE_YEARS = sorted(TABLES.keys())

def calcular_contribuicao_progressiva(salario, tabela):
    """
    Calcula a contribuição progressiva para um dado salário.
    Retorna (total_contribuicao, lista_detalhamento)
    """
    if salario <= 0:
        return 0.0, []

    restante = salario
    total = 0.0
    detalhamento = []

    for i, (lim_inf, lim_sup, aliquota) in enumerate(tabela):
        if restante <= 0:
            break

        if i == 0:
            tributavel = min(restante, lim_sup)
        else:
            if lim_sup == float('inf'):
                tributavel = restante
            else:
                largura_faixa = lim_sup - lim_inf
                tributavel = min(restante, largura_faixa)

        if tributavel > 0:
            contrib = tributavel * aliquota
            total += contrib
            detalhamento.append({
                "faixa": f"{formatar_moeda(lim_inf)} - {formatar_moeda(lim_sup) if lim_sup != float('inf') else 'acima'}",
                "base": tributavel,
                "aliquota": f"{aliquota*100:.2f}%",
                "contribuicao": contrib
            })
            restante -= tributavel

    return total, detalhamento

def formatar_moeda(valor):
    """Formata valor para o padrão brasileiro (R$ 1.000,00)."""
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

# -----------------------------------------------------------------------------
# Geração de PDF detalhado com progressividade por ano
# -----------------------------------------------------------------------------
class PDF(FPDF):
    def header(self):
        if self.page_no() == 1:
            self.set_font('Arial', 'B', 12)
            self.cell(0, 10, 'Relatório de Cálculo PSS - RPPS', ln=True, align='C')
            self.ln(5)
            self.set_font('Arial', '', 10)
            if 'processo' in st.session_state and st.session_state.processo:
                self.cell(0, 6, f"Processo: {st.session_state.processo}", ln=True)
            if 'autor' in st.session_state and st.session_state.autor:
                self.cell(0, 6, f"Autor: {st.session_state.autor}", ln=True)
            self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Página {self.page_no()}', align='C')

def gerar_pdf_detalhado(dados_anos, observacao):
    """Gera PDF com resumo e detalhamento progressivo por ano."""
    pdf = PDF()
    pdf.add_page()
    pdf.set_font('Arial', 'B', 11)
    pdf.cell(0, 10, 'Resumo por Ano', ln=True)
    pdf.set_font('Arial', '', 10)

    # Cabeçalho do resumo
    pdf.cell(30, 8, 'Ano', border=1)
    pdf.cell(50, 8, 'Salário (R$)', border=1)
    pdf.cell(60, 8, 'Contribuição Total (R$)', border=1)
    pdf.cell(40, 8, 'Alíquota Efetiva', border=1)
    pdf.ln()

    for linha in dados_anos:
        pdf.cell(30, 8, str(linha['ano']), border=1)
        pdf.cell(50, 8, linha['salario'], border=1)
        pdf.cell(60, 8, linha['contribuicao'], border=1)
        pdf.cell(40, 8, linha['aliquota'], border=1)
        pdf.ln()

    # Agora, para cada ano com dados, mostra o detalhamento progressivo
    for linha in dados_anos:
        if not linha.get('detalhes'):
            continue

        pdf.add_page()
        pdf.set_font('Arial', 'B', 11)
        pdf.cell(0, 10, f"Detalhamento Progressivo - Ano {linha['ano']}", ln=True)
        pdf.set_font('Arial', '', 10)
        pdf.cell(60, 8, 'Faixa de Salário', border=1)
        pdf.cell(50, 8, 'Base (R$)', border=1)
        pdf.cell(40, 8, 'Alíquota', border=1)
        pdf.cell(50, 8, 'Contribuição (R$)', border=1)
        pdf.ln()

        for det in linha['detalhes']:
            pdf.cell(60, 8, det['faixa'], border=1)
            pdf.cell(50, 8, formatar_moeda(det['base']), border=1)
            pdf.cell(40, 8, det['aliquota'], border=1)
            pdf.cell(50, 8, formatar_moeda(det['contribuicao']), border=1)
            pdf.ln()

        # Destaque do total em negrito
        pdf.set_font('Arial', 'B', 10)
        pdf.cell(150, 8, "Total da Contribuição:", border=1)
        pdf.cell(50, 8, formatar_moeda(linha['contrib_raw']), border=1, ln=True)
        pdf.set_font('Arial', '', 10)
        pdf.ln(5)

    if observacao:
        pdf.add_page()
        pdf.set_font('Arial', 'B', 11)
        pdf.cell(0, 10, 'Observações:', ln=True)
        pdf.set_font('Arial', '', 10)
        pdf.multi_cell(0, 6, observacao)

    # Retorna os bytes do PDF
    pdf_output = pdf.output(dest='S')
    if isinstance(pdf_output, str):
        return pdf_output.encode('latin1')
    else:
        return pdf_output

# -----------------------------------------------------------------------------
# Interface Streamlit
# -----------------------------------------------------------------------------
st.set_page_config(page_title="Calculadora PSS - RPPS", layout="wide")
st.title("📊 Calculadora PSS - Servidores Públicos Federais (RPPS)")
st.markdown("Calcule a contribuição previdenciária (PSS) para o Regime Próprio da União (2020 a 2026).")

# Sidebar: informações do processo
with st.sidebar:
    st.header("Informações do Processo")
    processo = st.text_input("Número do Processo", key="processo")
    autor = st.text_input("Nome do Autor da Ação", key="autor")
    observacao = st.text_area("Observações (opcional)", height=100)

# Criação de abas (tabs)
tab1, tab2, tab3 = st.tabs(["🔍 Cálculo Detalhado por Faixa", "📅 Relatório Anual (PDF Detalhado)", "⚖️ Comparação de Bases"])

# -----------------------------------------------------------------------------
# Tab 1: Cálculo Detalhado por Faixa (um ano)
# -----------------------------------------------------------------------------
with tab1:
    col1, col2 = st.columns(2)
    with col1:
        ano_detalhe = st.selectbox("Selecione o ano", options=AVAILABLE_YEARS, key="detail_year")
        salario_detalhe = st.number_input(
            f"Salário (R$) – base de contribuição ({ano_detalhe})",
            min_value=0.0,
            value=10000.0,
            step=100.0,
            format="%.2f",
            key="detail_salary"
        )
    with col2:
        tabela = TABLES[ano_detalhe]
        total_contrib, detalhes = calcular_contribuicao_progressiva(salario_detalhe, tabela)
        aliquota_efetiva = (total_contrib / salario_detalhe * 100) if salario_detalhe > 0 else 0.0
        st.metric("Total Contribuição", formatar_moeda(total_contrib))
        st.metric("Alíquota Efetiva", f"{aliquota_efetiva:.2f}%")

    if detalhes:
        st.subheader("Detalhamento por Faixa")
        df_detalhe = pd.DataFrame(detalhes)
        df_detalhe["base"] = df_detalhe["base"].apply(formatar_moeda)
        df_detalhe["contribuicao"] = df_detalhe["contribuicao"].apply(formatar_moeda)
        st.dataframe(df_detalhe, use_container_width=True, hide_index=True)

# -----------------------------------------------------------------------------
# Tab 2: Relatório Anual (PDF Detalhado)
# -----------------------------------------------------------------------------
with tab2:
    st.subheader("📅 Informe os salários para cada ano (2020 a 2026)")
    salarios_anuais = {}
    for ano in AVAILABLE_YEARS:
        salarios_anuais[ano] = st.number_input(
            f"Salário para {ano} (R$)",
            min_value=0.0,
            value=10000.0,
            step=100.0,
            format="%.2f",
            key=f"salary_{ano}"
        )

    # Botão para gerar PDF
    if st.button("📄 Gerar Relatório PDF Detalhado", key="gerar_pdf"):
        dados_relatorio = []
        for ano in AVAILABLE_YEARS:
            sal = salarios_anuais[ano]
            if sal > 0:
                contrib, detalhes = calcular_contribuicao_progressiva(sal, TABLES[ano])
                efetiva = (contrib / sal * 100) if sal > 0 else 0.0
                dados_relatorio.append({
                    "ano": ano,
                    "salario": formatar_moeda(sal),
                    "contribuicao": formatar_moeda(contrib),
                    "aliquota": f"{efetiva:.2f}%",
                    "contrib_raw": contrib,
                    "detalhes": detalhes
                })

        if not dados_relatorio:
            st.warning("Nenhum dado para gerar relatório. Informe pelo menos um salário positivo.")
        else:
            pdf_bytes = gerar_pdf_detalhado(dados_relatorio, observacao)
            b64 = base64.b64encode(pdf_bytes).decode()
            href = f'<a href="data:application/octet-stream;base64,{b64}" download="relatorio_pss_detalhado.pdf">📥 Clique aqui para baixar o relatório PDF</a>'
            st.markdown(href, unsafe_allow_html=True)
            st.success("Relatório detalhado gerado com sucesso!")

# -----------------------------------------------------------------------------
# Tab 3: Comparação de Bases
# -----------------------------------------------------------------------------
with tab3:
    st.subheader("⚖️ Comparação entre duas bases de cálculo por ano")
    st.markdown("Informe dois valores de salário para cada ano. A diferença na contribuição será calculada.")

    # Criar duas colunas para os inputs
    cols = st.columns(2)
    bases = {}
    with cols[0]:
        st.markdown("**Base 1 (Salário)**")
        for ano in AVAILABLE_YEARS:
            bases[f"base1_{ano}"] = st.number_input(
                f"{ano} (R$)",
                min_value=0.0,
                value=10000.0,
                step=100.0,
                format="%.2f",
                key=f"comp_base1_{ano}"
            )
    with cols[1]:
        st.markdown("**Base 2 (Salário)**")
        for ano in AVAILABLE_YEARS:
            bases[f"base2_{ano}"] = st.number_input(
                f"{ano} (R$)",
                min_value=0.0,
                value=10000.0,
                step=100.0,
                format="%.2f",
                key=f"comp_base2_{ano}"
            )

    # Botão para calcular comparação
    if st.button("Calcular Diferenças", key="calcular_comparacao"):
        comparacao = []
        for ano in AVAILABLE_YEARS:
            sal1 = bases[f"base1_{ano}"]
            sal2 = bases[f"base2_{ano}"]
            if sal1 > 0 or sal2 > 0:
                contrib1, _ = calcular_contribuicao_progressiva(sal1, TABLES[ano])
                contrib2, _ = calcular_contribuicao_progressiva(sal2, TABLES[ano])
                diff_contrib = contrib2 - contrib1
                diff_sal = sal2 - sal1
                comparacao.append({
                    "Ano": ano,
                    "Salário 1 (R$)": formatar_moeda(sal1),
                    "Contribuição 1 (R$)": formatar_moeda(contrib1),
                    "Salário 2 (R$)": formatar_moeda(sal2),
                    "Contribuição 2 (R$)": formatar_moeda(contrib2),
                    "Diferença Salário (R$)": formatar_moeda(diff_sal),
                    "Diferença Contribuição (R$)": formatar_moeda(diff_contrib),
                })
        if comparacao:
            df_comp = pd.DataFrame(comparacao)
            st.dataframe(df_comp, use_container_width=True, hide_index=True)
        else:
            st.warning("Nenhum ano com salários positivos informados.")

# -----------------------------------------------------------------------------
# Expansor com as tabelas de referência
# -----------------------------------------------------------------------------
with st.expander("📋 Ver Tabelas de Contribuição (por ano)"):
    ano_tabela = st.selectbox("Selecione o ano para visualizar a tabela", options=AVAILABLE_YEARS, key="table_year")
    tabela_exibir = TABLES[ano_tabela]
    df_tabela = pd.DataFrame(tabela_exibir, columns=["Faixa inferior", "Faixa superior", "Alíquota"])
    df_tabela["Faixa inferior"] = df_tabela["Faixa inferior"].apply(formatar_moeda)
    df_tabela["Faixa superior"] = df_tabela["Faixa superior"].replace(float('inf'), "acima")
    df_tabela["Faixa superior"] = df_tabela["Faixa superior"].apply(lambda x: formatar_moeda(x) if x != "acima" else "acima")
    df_tabela["Alíquota"] = df_tabela["Alíquota"].apply(lambda x: f"{x*100:.2f}%")
    st.dataframe(df_tabela, use_container_width=True, hide_index=True)

st.markdown("---")
st.caption("Fonte: Portarias Interministeriais MPS/MF dos respectivos anos. Cálculo progressivo por faixas.")
