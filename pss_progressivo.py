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
        (0.00, 1045.00, 0.075),
        (1045.01, 2000.00, 0.09),
        (2000.01, 3000.00, 0.12),
        (3000.01, 5839.45, 0.14),
        (5839.46, 10000.00, 0.145),
        (10000.01, 20000.00, 0.165),
        (20000.01, 39000.00, 0.19),
        (39000.01, float('inf'), 0.22),
    ],
    2021: [
        (0.00, 1100.00, 0.075),
        (1100.01, 2203.48, 0.09),
        (2203.49, 3305.22, 0.12),
        (3305.23, 6433.57, 0.14),
        (6433.58, 11017.42, 0.145),
        (11017.43, 22034.83, 0.165),
        (22034.84, 42967.92, 0.19),
        (42967.93, float('inf'), 0.22),
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

# Referências das Portarias por ano
PORTARIAS = {
    2020: "Portaria que instituiu as alíquotas progressivas em 2020 (baseada na EC nº 103/2019)",
    2021: "Portaria SEPRT/ME nº 636, de 13 de janeiro de 2021",
    2022: "Portaria MTP/ME nº 12, de 17 de janeiro de 2022",
    2023: "Portaria MPS/MF nº 26, de 10 de janeiro de 2023",
    2024: "Portaria MPS/MF nº 2, de 11 de janeiro de 2024",
    2025: "Portaria MPS/MF nº 6, de 10 de janeiro de 2025",
    2026: "Portaria MPS/MF nº 13, de 9 de janeiro de 2026",
}

AVAILABLE_YEARS = sorted(TABLES.keys())

def calcular_contribuicao_progressiva(salario, tabela):
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
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

# -----------------------------------------------------------------------------
# Geração de PDF comparativo com síntese e somatório
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

def gerar_pdf_comparacao(dados_comparacao, observacao):
    pdf = PDF()
    pdf.add_page()
    pdf.set_font('Arial', 'B', 11)
    pdf.cell(0, 10, 'Relatório Comparativo PSS - RPPS', ln=True, align='C')
    pdf.ln(5)

    dados_sintese = []

    for idx, ano_data in enumerate(dados_comparacao):
        ano = ano_data['ano']
        sal1 = ano_data['sal1']
        sal2 = ano_data['sal2']
        contrib1 = ano_data['contrib1']
        contrib2 = ano_data['contrib2']
        breakdown1 = ano_data['breakdown1']
        breakdown2 = ano_data['breakdown2']

        if idx > 0:
            pdf.add_page()

        pdf.set_font('Arial', 'B', 11)
        pdf.cell(0, 10, f"Ano {ano}", ln=True, align='C')
        pdf.ln(5)

        # Base 1
        pdf.set_font('Arial', 'B', 10)
        pdf.cell(0, 8, f"Base 1 - Salário: {formatar_moeda(sal1)}", ln=True)
        pdf.set_font('Arial', '', 9)
        pdf.cell(50, 8, 'Faixa de Salário', border=1)
        pdf.cell(40, 8, 'Base (R$)', border=1)
        pdf.cell(30, 8, 'Alíquota', border=1)
        pdf.cell(50, 8, 'Contribuição (R$)', border=1)
        pdf.ln()
        for det in breakdown1:
            pdf.cell(50, 8, det['faixa'], border=1)
            pdf.cell(40, 8, formatar_moeda(det['base']), border=1)
            pdf.cell(30, 8, det['aliquota'], border=1)
            pdf.cell(50, 8, formatar_moeda(det['contribuicao']), border=1)
            pdf.ln()
        pdf.set_font('Arial', 'B', 9)
        pdf.cell(120, 8, "Total Contribuição Base 1:", border=1)
        pdf.cell(50, 8, formatar_moeda(contrib1), border=1, ln=True)
        pdf.ln(5)

        # Base 2
        pdf.set_font('Arial', 'B', 10)
        pdf.cell(0, 8, f"Base 2 - Salário: {formatar_moeda(sal2)}", ln=True)
        pdf.set_font('Arial', '', 9)
        pdf.cell(50, 8, 'Faixa de Salário', border=1)
        pdf.cell(40, 8, 'Base (R$)', border=1)
        pdf.cell(30, 8, 'Alíquota', border=1)
        pdf.cell(50, 8, 'Contribuição (R$)', border=1)
        pdf.ln()
        for det in breakdown2:
            pdf.cell(50, 8, det['faixa'], border=1)
            pdf.cell(40, 8, formatar_moeda(det['base']), border=1)
            pdf.cell(30, 8, det['aliquota'], border=1)
            pdf.cell(50, 8, formatar_moeda(det['contribuicao']), border=1)
            pdf.ln()
        pdf.set_font('Arial', 'B', 9)
        pdf.cell(120, 8, "Total Contribuição Base 2:", border=1)
        pdf.cell(50, 8, formatar_moeda(contrib2), border=1, ln=True)

        diff_sal = sal2 - sal1
        diff_contrib = contrib2 - contrib1
        pdf.ln(5)
        pdf.set_font('Arial', 'B', 10)
        pdf.cell(0, 8, "Diferenças:", ln=True)
        pdf.set_font('Arial', '', 9)
        pdf.cell(80, 8, "Diferença Salário (Base2 - Base1):", border=1)
        pdf.cell(50, 8, formatar_moeda(diff_sal), border=1, ln=True)
        pdf.cell(80, 8, "Diferença Contribuição (Base2 - Base1):", border=1)
        pdf.cell(50, 8, formatar_moeda(diff_contrib), border=1, ln=True)

        efetiva1 = (contrib1 / sal1 * 100) if sal1 > 0 else 0
        efetiva2 = (contrib2 / sal2 * 100) if sal2 > 0 else 0
        pdf.cell(80, 8, "Alíquota Efetiva Base 1:", border=1)
        pdf.cell(50, 8, f"{efetiva1:.2f}%", border=1, ln=True)
        pdf.cell(80, 8, "Alíquota Efetiva Base 2:", border=1)
        pdf.cell(50, 8, f"{efetiva2:.2f}%", border=1, ln=True)

        pdf.ln(5)
        pdf.set_font('Arial', 'I', 8)
        pdf.cell(0, 6, f"Fonte: {PORTARIAS.get(ano, 'Portaria não especificada')}", ln=True)
        pdf.ln(10)

        dados_sintese.append({
            "Ano": ano,
            "Salário Base 1": formatar_moeda(sal1),
            "Salário Base 2": formatar_moeda(sal2),
            "Contribuição Base 1": formatar_moeda(contrib1),
            "Contribuição Base 2": formatar_moeda(contrib2),
            "Diferença Salário": formatar_moeda(diff_sal),
            "Diferença Contribuição": formatar_moeda(diff_contrib),
            "diff_sal_raw": diff_sal,
            "diff_contrib_raw": diff_contrib,
        })

    # Página de síntese
    if dados_sintese:
        pdf.add_page()
        pdf.set_font('Arial', 'B', 11)
        pdf.cell(0, 10, 'Síntese Comparativa', ln=True, align='C')
        pdf.ln(5)

        # Cabeçalho com larguras ajustadas (total 195mm)
        pdf.set_font('Arial', 'B', 8)
        pdf.cell(15, 8, 'Ano', border=1)
        pdf.cell(30, 8, 'Salário Base 1', border=1)
        pdf.cell(30, 8, 'Salário Base 2', border=1)
        pdf.cell(30, 8, 'Contribuição Base 1', border=1)
        pdf.cell(30, 8, 'Contribuição Base 2', border=1)
        pdf.cell(28, 8, 'Diferença Salário', border=1)
        pdf.cell(32, 8, 'Diferença Contribuição', border=1)
        pdf.ln()

        # Dados
        pdf.set_font('Arial', '', 8)
        total_diff_sal = 0.0
        total_diff_contrib = 0.0
        for linha in dados_sintese:
            pdf.cell(15, 8, str(linha['Ano']), border=1)
            pdf.cell(30, 8, linha['Salário Base 1'], border=1)
            pdf.cell(30, 8, linha['Salário Base 2'], border=1)
            pdf.cell(30, 8, linha['Contribuição Base 1'], border=1)
            pdf.cell(30, 8, linha['Contribuição Base 2'], border=1)
            pdf.cell(28, 8, linha['Diferença Salário'], border=1)
            pdf.cell(32, 8, linha['Diferença Contribuição'], border=1)
            pdf.ln()
            total_diff_sal += linha['diff_sal_raw']
            total_diff_contrib += linha['diff_contrib_raw']

        # Linha de total
        pdf.set_font('Arial', 'B', 8)
        pdf.cell(15, 8, 'Total', border=1)
        pdf.cell(30, 8, '', border=1)
        pdf.cell(30, 8, '', border=1)
        pdf.cell(30, 8, '', border=1)
        pdf.cell(30, 8, '', border=1)
        pdf.cell(28, 8, formatar_moeda(total_diff_sal), border=1)
        pdf.cell(32, 8, formatar_moeda(total_diff_contrib), border=1)
        pdf.ln()

    # Observações após uma linha de markdown (linha horizontal)
    if observacao:
        pdf.ln(5)
        pdf.set_draw_color(0, 0, 0)
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(5)
        pdf.set_font('Arial', 'B', 11)
        pdf.cell(0, 10, 'Observações:', ln=True)
        pdf.set_font('Arial', '', 10)
        pdf.multi_cell(0, 6, observacao)

    out = pdf.output(dest='S')
    if isinstance(out, str):
        return out.encode('latin1')
    return out

# -----------------------------------------------------------------------------
# Interface Streamlit (idêntica à versão anterior)
# -----------------------------------------------------------------------------
st.set_page_config(page_title="Calculadora PSS - RPPS", layout="wide")
st.title("📊 Calculadora PSS - Servidores Públicos Federais (RPPS)")
st.markdown("Calcule a contribuição previdenciária (PSS) para o Regime Próprio da União (2020 a 2026).")

with st.sidebar:
    st.header("Informações do Processo")
    processo = st.text_input("Número do Processo", key="processo")
    autor = st.text_input("Nome do Autor da Ação", key="autor")
    observacao = st.text_area("Observações (opcional)", height=100)

tab1, tab2, tab3 = st.tabs(["🔍 Cálculo Detalhado por Faixa", "📅 Relatório Anual (PDF Detalhado)", "⚖️ Comparação de Bases"])

# Tab 1 (cálculo detalhado) – mantido
with tab1:
    col1, col2 = st.columns(2)
    with col1:
        ano_detalhe = st.selectbox("Selecione o ano", options=AVAILABLE_YEARS, key="detail_year")
        salario_detalhe = st.number_input(
            f"Salário (R$) – base de contribuição ({ano_detalhe})",
            min_value=0.0, value=10000.0, step=100.0, format="%.2f", key="detail_salary")
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

# Tab 2 (relatório anual) – mantido
with tab2:
    st.subheader("📅 Informe os salários para cada ano (2020 a 2026)")
    salarios_anuais = {}
    for ano in AVAILABLE_YEARS:
        salarios_anuais[ano] = st.number_input(
            f"Salário para {ano} (R$)", min_value=0.0, value=10000.0, step=100.0, format="%.2f", key=f"salary_{ano}")

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
            # Função local para gerar PDF detalhado (igual à versão anterior)
            class PDFDet(FPDF):
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

            def gerar_pdf_detalhado(dados_anos, obs):
                pdf = PDFDet()
                pdf.add_page()
                pdf.set_font('Arial', 'B', 11)
                pdf.cell(0, 10, 'Resumo por Ano', ln=True)
                pdf.set_font('Arial', '', 10)
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
                    pdf.set_font('Arial', 'B', 10)
                    pdf.cell(150, 8, "Total da Contribuição:", border=1)
                    pdf.cell(50, 8, formatar_moeda(linha['contrib_raw']), border=1, ln=True)
                    pdf.set_font('Arial', '', 10)
                    pdf.ln(5)
                    pdf.set_font('Arial', 'I', 8)
                    pdf.cell(0, 6, f"Fonte: {PORTARIAS.get(linha['ano'], 'Portaria não especificada')}", ln=True)
                if obs:
                    pdf.add_page()
                    pdf.set_font('Arial', 'B', 11)
                    pdf.cell(0, 10, 'Observações:', ln=True)
                    pdf.set_font('Arial', '', 10)
                    pdf.multi_cell(0, 6, obs)
                out = pdf.output(dest='S')
                if isinstance(out, str):
                    return out.encode('latin1')
                return out

            pdf_bytes = gerar_pdf_detalhado(dados_relatorio, observacao)
            b64 = base64.b64encode(pdf_bytes).decode()
            href = f'<a href="data:application/octet-stream;base64,{b64}" download="relatorio_pss_detalhado.pdf">📥 Clique aqui para baixar o relatório PDF</a>'
            st.markdown(href, unsafe_allow_html=True)
            st.success("Relatório detalhado gerado com sucesso!")

# Tab 3 (comparação de bases)
with tab3:
    st.subheader("⚖️ Comparação entre duas bases de cálculo por ano")
    st.markdown("Informe dois valores de salário para cada ano. A diferença na contribuição será calculada.")

    cols = st.columns(2)
    bases = {}
    with cols[0]:
        st.markdown("**Base 1 (Salário)**")
        for ano in AVAILABLE_YEARS:
            bases[f"base1_{ano}"] = st.number_input(
                f"{ano} (R$)", min_value=0.0, value=10000.0, step=100.0, format="%.2f", key=f"comp_base1_{ano}")
    with cols[1]:
        st.markdown("**Base 2 (Salário)**")
        for ano in AVAILABLE_YEARS:
            bases[f"base2_{ano}"] = st.number_input(
                f"{ano} (R$)", min_value=0.0, value=10000.0, step=100.0, format="%.2f", key=f"comp_base2_{ano}")

    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
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
                        #"Diferença Salário (R$)": formatar_moeda(diff_sal),
                        "Diferença Contribuição (R$)": formatar_moeda(diff_contrib),
                    })
            if comparacao:
                df_comp = pd.DataFrame(comparacao)
                st.dataframe(df_comp, use_container_width=True, hide_index=True)
            else:
                st.warning("Nenhum ano com salários positivos informados.")

    with col_btn2:
        if st.button("📄 Gerar Relatório Comparativo PDF", key="gerar_pdf_comparacao"):
            dados_comparacao = []
            for ano in AVAILABLE_YEARS:
                sal1 = bases[f"base1_{ano}"]
                sal2 = bases[f"base2_{ano}"]
                if sal1 > 0 or sal2 > 0:
                    contrib1, breakdown1 = calcular_contribuicao_progressiva(sal1, TABLES[ano])
                    contrib2, breakdown2 = calcular_contribuicao_progressiva(sal2, TABLES[ano])
                    dados_comparacao.append({
                        "ano": ano,
                        "sal1": sal1,
                        "sal2": sal2,
                        "contrib1": contrib1,
                        "contrib2": contrib2,
                        "breakdown1": breakdown1,
                        "breakdown2": breakdown2,
                    })
            if not dados_comparacao:
                st.warning("Nenhum dado para gerar relatório. Informe pelo menos um salário positivo em algum ano.")
            else:
                pdf_bytes = gerar_pdf_comparacao(dados_comparacao, observacao)
                b64 = base64.b64encode(pdf_bytes).decode()
                href = f'<a href="data:application/octet-stream;base64,{b64}" download="relatorio_comparativo_pss.pdf">📥 Clique aqui para baixar o relatório comparativo PDF</a>'
                st.markdown(href, unsafe_allow_html=True)
                st.success("Relatório comparativo gerado com sucesso!")

# Expansor com as tabelas de referência
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
