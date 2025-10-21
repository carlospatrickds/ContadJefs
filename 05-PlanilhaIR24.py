
import streamlit as st
import pandas as pd
import numpy as np

# Configuração da página
st.set_page_config(
    page_title="Calculadora IR 2024",
    page_icon="📊",
    layout="wide"
)

# Título do aplicativo
st.title("Calculadora de Imposto de Renda 2024")
st.subheader("Com base na planilha planilha_teste_ir_2024.xlsx")

# Dados das faixas de contribuição previdenciária (INSS)
faixas_inss = [
    {"inicio": 0, "fim": 1412.00, "aliquota": 0.075, "deducao": 0},
    {"inicio": 1412.01, "fim": 2666.68, "aliquota": 0.09, "deducao": 21.18},
    {"inicio": 2666.69, "fim": 4000.03, "aliquota": 0.12, "deducao": 101.18},
    {"inicio": 4000.04, "fim": 7786.02, "aliquota": 0.14, "deducao": 181.18}
]

# Dados das faixas do IR para cálculo tradicional
faixas_ir_tradicional = [
    {"inicio": 0, "fim": 2259.20, "aliquota": 0, "deducao": 0},
    {"inicio": 2259.21, "fim": 2826.65, "aliquota": 0.075, "deducao": 169.44},
    {"inicio": 2826.66, "fim": 3751.05, "aliquota": 0.15, "deducao": 381.44},
    {"inicio": 3751.06, "fim": 4664.68, "aliquota": 0.225, "deducao": 662.77},
    {"inicio": 4664.69, "fim": 99999.99, "aliquota": 0.275, "deducao": 896.00}
]

# Dados das faixas do IR para cálculo simplificado
faixas_ir_simplificado = [
    {"inicio": 0, "fim": 1903.98, "aliquota": 0, "deducao": 0},
    {"inicio": 1903.99, "fim": 2826.65, "aliquota": 0.075, "deducao": 142.80},
    {"inicio": 2826.66, "fim": 3751.05, "aliquota": 0.15, "deducao": 354.80},
    {"inicio": 3751.06, "fim": 4664.68, "aliquota": 0.225, "deducao": 636.13},
    {"inicio": 4664.69, "fim": 99999.99, "aliquota": 0.275, "deducao": 869.36}
]

# Valor da dedução por dependente
deducao_dependente = 189.59

# Função para calcular o INSS
def calcular_inss(salario_bruto):
    if salario_bruto <= 0:
        return 0
    
    contribuicao = 0
    salario_restante = salario_bruto
    
    for faixa in faixas_inss:
        if salario_restante <= 0:
            break
            
        base_calculo_faixa = min(salario_restante, faixa["fim"] - faixa["inicio"])
        if base_calculo_faixa <= 0:
            continue
            
        contribuicao_faixa = base_calculo_faixa * faixa["aliquota"]
        contribuicao += contribuicao_faixa
        salario_restante -= base_calculo_faixa
    
    # Limite máximo de contribuição (teto)
    teto_inss = 7786.02 * 0.14  # Valor máximo da última faixa
    return min(contribuicao, teto_inss)

# Função para calcular o IR usando uma tabela específica
def calcular_ir(base_calculo, faixas_ir):
    if base_calculo <= 0:
        return 0
    
    for faixa in faixas_ir:
        if base_calculo <= faixa["fim"]:
            imposto = (base_calculo * faixa["aliquota"]) - faixa["deducao"]
            return max(imposto, 0)
    
    # Caso a base de cálculo seja maior que a última faixa
    ultima_faixa = faixas_ir[-1]
    imposto = (base_calculo * ultima_faixa["aliquota"]) - ultima_faixa["deducao"]
    return max(imposto, 0)

# Interface do usuário
with st.sidebar:
    st.header("Dados de Entrada")
    
    base_contribuicao = st.number_input(
        "Base Contribuição Previdenciária:",
        min_value=0.0,
        max_value=100000.0,
        value=5000.0,
        step=100.0
    )
    
    qtd_dependentes = st.number_input(
        "Quantidade de Dependentes:",
        min_value=0,
        max_value=20,
        value=0,
        step=1
    )
    
    outras_deducoes = st.number_input(
        "Outras Deduções (opcional):",
        min_value=0.0,
        value=0.0,
        step=100.0
    )

# Cálculos
inss = calcular_inss(base_contribuicao)
deducao_total_dependentes = qtd_dependentes * deducao_dependente

# Cálculo tradicional
base_calculo_tradicional = base_contribuicao - inss - deducao_total_dependentes - outras_deducoes
ir_tradicional = calcular_ir(base_calculo_tradicional, faixas_ir_tradicional)

# Cálculo simplificado
base_calculo_simplificado = base_contribuicao - inss
deducao_simplificada = base_calculo_simplificado * 0.20  # 20% de dedução padrão
base_calculo_simplificado -= deducao_simplificada
ir_simplificado = calcular_ir(base_calculo_simplificado, faixas_ir_simplificado)

# Exibição dos resultados
col1, col2 = st.columns(2)

with col1:
    st.header("Cálculo Tradicional")
    st.metric("Base de Cálculo", f"R$ {base_calculo_tradicional:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
    st.metric("INSS", f"R$ {inss:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
    st.metric("Dedução por Dependentes", f"R$ {deducao_total_dependentes:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
    st.metric("Outras Deduções", f"R$ {outras_deducoes:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
    st.metric("IR a Pagar (Tradicional)", f"R$ {ir_tradicional:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."), 
              delta_color="inverse")

with col2:
    st.header("Cálculo Simplificado")
    st.metric("Base de Cálculo", f"R$ {base_calculo_simplificado:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
    st.metric("INSS", f"R$ {inss:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
    st.metric("Dedução Simplificada (20%)", f"R$ {deducao_simplificada:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
    st.metric("IR a Pagar (Simplificado)", f"R$ {ir_simplificado:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."), 
              delta_color="inverse")

# Comparação entre os dois métodos
st.header("Comparação")
diferenca = ir_tradicional - ir_simplificado

if diferenca > 0:
    st.success(f"O cálculo simplificado é mais vantajoso em R$ {abs(diferenca):,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
elif diferenca < 0:
    st.info(f"O cálculo tradicional é mais vantajoso em R$ {abs(diferenca):,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
else:
    st.warning("Ambos os métodos resultam no mesmo valor de imposto")

# Tabela com as faixas de imposto
st.header("Tabelas de Referência")

tab1, tab2, tab3 = st.tabs(["INSS", "IR Tradicional", "IR Simplificado"])

with tab1:
    st.subheader("Tabela de Contribuição Previdenciária (INSS) 2024")
    df_inss = pd.DataFrame(faixas_inss)
    df_inss["inicio"] = df_inss["inicio"].apply(lambda x: f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
    df_inss["fim"] = df_inss["fim"].apply(lambda x: f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
    df_inss["aliquota"] = df_inss["aliquota"].apply(lambda x: f"{x*100:.1f}%")
    st.dataframe(df_inss, hide_index=True)

with tab2:
    st.subheader("Tabela do Imposto de Renda (Cálculo Tradicional) 2024")
    df_ir_trad = pd.DataFrame(faixas_ir_tradicional)
    df_ir_trad["inicio"] = df_ir_trad["inicio"].apply(lambda x: f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
    df_ir_trad["fim"] = df_ir_trad["fim"].apply(lambda x: f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
    df_ir_trad["aliquota"] = df_ir_trad["aliquota"].apply(lambda x: f"{x*100:.1f}%")
    df_ir_trad["deducao"] = df_ir_trad["deducao"].apply(lambda x: f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
    st.dataframe(df_ir_trad, hide_index=True)

with tab3:
    st.subheader("Tabela do Imposto de Renda (Cálculo Simplificado) 2024")
    df_ir_simp = pd.DataFrame(faixas_ir_simplificado)
    df_ir_simp["inicio"] = df_ir_simp["inicio"].apply(lambda x: f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
    df_ir_simp["fim"] = df_ir_simp["fim"].apply(lambda x: f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
    df_ir_simp["aliquota"] = df_ir_simp["aliquota"].apply(lambda x: f"{x*100:.1f}%")
    df_ir_simp["deducao"] = df_ir_simp["deducao"].apply(lambda x: f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
    st.dataframe(df_ir_simp, hide_index=True)

# Informações adicionais
st.info("""
**Nota:** Este aplicativo é baseado na planilha fornecida e nas tabelas vigentes em 2024.
Valores arredondados para duas casas decimais. Consulte um contador para análise específica do seu caso.
""")
