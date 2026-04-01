import streamlit as st
import pandas as pd
from fpdf import FPDF
import io
import base64

# -----------------------------------------------------------------------------
# Contribution tables for RPPS (Regime Próprio de Previdência Social da União)
# Each year's table is a list of (lower_bound, upper_bound, rate)
# The calculation uses these brackets progressively.
# -----------------------------------------------------------------------------

TABLES = {
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

# Years with available tables
AVAILABLE_YEARS = sorted(TABLES.keys())

def calculate_progressive_contribution(salary, table):
    """
    Calculate the progressive contribution for a given salary.
    Returns total contribution and a list of bracket contributions.
    """
    if salary <= 0:
        return 0.0, []

    remaining = salary
    total = 0.0
    breakdown = []

    for i, (lower, upper, rate) in enumerate(table):
        if remaining <= 0:
            break

        # Determine the portion of salary that falls into this bracket
        if i == 0:
            taxable = min(remaining, upper)
        else:
            # The width of the bracket (if upper is finite)
            if upper == float('inf'):
                bracket_amount = remaining
            else:
                bracket_amount = upper - lower
                # But we must not exceed the remaining salary
                bracket_amount = min(bracket_amount, remaining)
            taxable = bracket_amount

        if taxable > 0:
            contrib = taxable * rate
            total += contrib
            breakdown.append({
                "faixa": f"{format_currency(lower)} - {format_currency(upper) if upper != float('inf') else 'acima'}",
                "base": taxable,
                "aliquota": f"{rate*100:.2f}%",
                "contribuicao": contrib
            })
            remaining -= taxable

    return total, breakdown

def format_currency(value):
    """Format value as Brazilian real."""
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

# -----------------------------------------------------------------------------
# PDF generation using fpdf
# -----------------------------------------------------------------------------
class PDF(FPDF):
    def header(self):
        if self.page_no() == 1:
            self.set_font('Arial', 'B', 12)
            self.cell(0, 10, 'Relatório de Cálculo PSS - RPPS', ln=True, align='C')
            self.ln(5)
            self.set_font('Arial', '', 10)
            # Header info from session state
            if 'processo' in st.session_state:
                self.cell(0, 6, f"Processo: {st.session_state.processo}", ln=True)
            if 'autor' in st.session_state:
                self.cell(0, 6, f"Autor: {st.session_state.autor}", ln=True)
            self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Página {self.page_no()}', align='C')

def generate_pdf(years_data, observacao):
    """Generate PDF from the data."""
    pdf = PDF()
    pdf.add_page()
    pdf.set_font('Arial', 'B', 11)
    pdf.cell(0, 10, 'Resumo por Ano', ln=True)
    pdf.set_font('Arial', '', 10)

    # Table header
    pdf.cell(30, 8, 'Ano', border=1)
    pdf.cell(50, 8, 'Salário (R$)', border=1)
    pdf.cell(60, 8, 'Contribuição Total (R$)', border=1)
    pdf.cell(40, 8, 'Alíquota Efetiva', border=1)
    pdf.ln()

    for row in years_data:
        pdf.cell(30, 8, str(row['ano']), border=1)
        pdf.cell(50, 8, row['salario'], border=1)
        pdf.cell(60, 8, row['contribuicao'], border=1)
        pdf.cell(40, 8, row['aliquota'], border=1)
        pdf.ln()

    # Observations
    if observacao:
        pdf.ln(10)
        pdf.set_font('Arial', 'B', 11)
        pdf.cell(0, 10, 'Observações:', ln=True)
        pdf.set_font('Arial', '', 10)
        pdf.multi_cell(0, 6, observacao)

    return pdf.output(dest='S').encode('latin1')

# -----------------------------------------------------------------------------
# Streamlit UI
# -----------------------------------------------------------------------------
st.set_page_config(page_title="Calculadora PSS - RPPS", layout="wide")
st.title("📊 Calculadora PSS - Servidores Públicos Federais (RPPS)")
st.markdown("Calcule a contribuição previdenciária (PSS) para o Regime Próprio da União.")

# Sidebar for global info (process, author)
with st.sidebar:
    st.header("Informações do Processo")
    processo = st.text_input("Número do Processo", key="processo")
    autor = st.text_input("Nome do Autor da Ação", key="autor")
    observacao = st.text_area("Observações (opcional)", height=100)

# -----------------------------------------------------------------------------
# Two main sections: 1) Single-year detailed breakdown, 2) Multi-year report
# -----------------------------------------------------------------------------
col1, col2 = st.columns(2)

with col1:
    st.subheader("🔍 Cálculo Detalhado por Faixa")
    year_detail = st.selectbox("Selecione o ano para detalhamento", options=AVAILABLE_YEARS, key="detail_year")
    salary_detail = st.number_input(
        f"Salário (R$) – base de contribuição ({year_detail})",
        min_value=0.0,
        value=10000.0,
        step=100.0,
        format="%.2f",
        key="detail_salary"
    )
    table = TABLES[year_detail]
    total_contrib, breakdown = calculate_progressive_contribution(salary_detail, table)
    effective_rate = (total_contrib / salary_detail * 100) if salary_detail > 0 else 0.0

    st.metric("Total Contribuição", format_currency(total_contrib))
    st.metric("Alíquota Efetiva", f"{effective_rate:.2f}%")

    if breakdown:
        st.subheader("Detalhamento por Faixa")
        df_breakdown = pd.DataFrame(breakdown)
        df_breakdown["base"] = df_breakdown["base"].apply(format_currency)
        df_breakdown["contribuicao"] = df_breakdown["contribuicao"].apply(format_currency)
        st.dataframe(df_breakdown, use_container_width=True, hide_index=True)

with col2:
    st.subheader("📅 Cálculo Anual para Relatório")
    st.markdown("Informe os salários para cada ano (de 2022 a 2026).")

    # Input salaries per year
    yearly_salaries = {}
    for year in AVAILABLE_YEARS:
        yearly_salaries[year] = st.number_input(
            f"Salário para {year} (R$)",
            min_value=0.0,
            value=10000.0,
            step=100.0,
            format="%.2f",
            key=f"salary_{year}"
        )

    # Build data for report
    report_data = []
    for year in AVAILABLE_YEARS:
        sal = yearly_salaries[year]
        if sal > 0:
            contrib, _ = calculate_progressive_contribution(sal, TABLES[year])
            eff_rate = (contrib / sal * 100) if sal > 0 else 0.0
            report_data.append({
                "ano": year,
                "salario": format_currency(sal),
                "contribuicao": format_currency(contrib),
                "aliquota": f"{eff_rate:.2f}%"
            })

    if st.button("📄 Gerar Relatório PDF"):
        if not report_data:
            st.warning("Nenhum dado para gerar relatório. Informe pelo menos um salário positivo.")
        else:
            pdf_bytes = generate_pdf(report_data, observacao)
            b64 = base64.b64encode(pdf_bytes).decode()
            href = f'<a href="data:application/octet-stream;base64,{b64}" download="relatorio_pss.pdf">📥 Clique aqui para baixar o relatório PDF</a>'
            st.markdown(href, unsafe_allow_html=True)
            st.success("Relatório gerado com sucesso!")

# -----------------------------------------------------------------------------
# Display the progressive table for reference (optional)
# -----------------------------------------------------------------------------
with st.expander("📋 Ver Tabelas de Contribuição (por ano)"):
    year_tables = st.selectbox("Selecione o ano para visualizar a tabela", options=AVAILABLE_YEARS)
    table_show = TABLES[year_tables]
    df_table = pd.DataFrame(table_show, columns=["Faixa inferior", "Faixa superior", "Alíquota"])
    df_table["Faixa inferior"] = df_table["Faixa inferior"].apply(format_currency)
    df_table["Faixa superior"] = df_table["Faixa superior"].replace(float('inf'), "acima")
    df_table["Faixa superior"] = df_table["Faixa superior"].apply(lambda x: format_currency(x) if x != "acima" else "acima")
    df_table["Alíquota"] = df_table["Alíquota"].apply(lambda x: f"{x*100:.2f}%")
    st.dataframe(df_table, use_container_width=True, hide_index=True)

st.markdown("---")
st.caption("Fonte: Portarias Interministeriais MPS/MF dos respectivos anos. O cálculo é progressivo por faixas.")
