import streamlit as st
import pandas as pd

# -----------------------------------------------------------------------------
# Contribution tables for RPPS (Regime Próprio de Previdência Social da União)
# Each year's table is a list of (lower_bound, upper_bound, rate)
# Rates are given as decimals (e.g., 0.075 for 7.5%)
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

def calculate_contribution(salary, table):
    """Calculate the contribution amount for a given salary and table."""
    if salary <= 0:
        return 0.0
    for lower, upper, rate in table:
        if lower <= salary <= upper:
            return salary * rate
    return 0.0  # fallback (should never happen)

def format_currency(value):
    """Format value as Brazilian real."""
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

# -----------------------------------------------------------------------------
# Streamlit UI
# -----------------------------------------------------------------------------
st.set_page_config(page_title="Calculadora PSS - RPPS", layout="centered")
st.title("📊 Calculadora PSS - Servidores Públicos Federais (RPPS)")
st.markdown("Calcule a contribuição previdenciária (PSS) para o Regime Próprio da União.")

# Year selection
year = st.selectbox("Selecione o ano", options=sorted(TABLES.keys()), index=len(TABLES)-1)

# Salary input
salary = st.number_input(
    "Salário (R$) – base de contribuição",
    min_value=0.0,
    value=10000.0,
    step=100.0,
    format="%.2f"
)

# Get the table for the selected year
table = TABLES[year]

# Calculate contribution
contribution = calculate_contribution(salary, table)
effective_rate = (contribution / salary * 100) if salary > 0 else 0.0

# Display results
col1, col2 = st.columns(2)
with col1:
    st.metric("Valor da Contribuição (PSS)", format_currency(contribution))
with col2:
    st.metric("Alíquota Efetiva", f"{effective_rate:.2f}%")

# Show the contribution table
st.subheader("📋 Tabela de Contribuição (RPPS)")
df = pd.DataFrame(table, columns=["Faixa inferior", "Faixa superior", "Alíquota"])
df["Faixa inferior"] = df["Faixa inferior"].apply(format_currency)
df["Faixa superior"] = df["Faixa superior"].replace(float('inf'), "acima")
df["Faixa superior"] = df["Faixa superior"].apply(lambda x: format_currency(x) if x != "acima" else "acima")
df["Alíquota"] = df["Alíquota"].apply(lambda x: f"{x*100:.2f}%")
st.dataframe(df, use_container_width=True, hide_index=True)

st.markdown("---")
st.caption("Fonte: Portarias Interministeriais MPS/MF dos respectivos anos.")
