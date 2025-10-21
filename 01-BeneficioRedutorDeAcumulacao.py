import streamlit as st
import pandas as pd
from datetime import datetime

# Configuração da página
st.set_page_config(
    page_title="Cálculo de Acumulação de Benefícios",
    page_icon="📊",
    layout="centered"
)
# st.set_page_config(page_title="Cálculo de Acumulação de Benefícios", layout="WIDE",  page_icon="📊")


# Dicionário completo com os salários mínimos
SALARIOS_MINIMOS = {
    2019: {month: 998.00 for month in range(1, 13)},
    2020: {1: 1039.00, **{month: 1045.00 for month in range(2, 13)}},
    2021: {month: 1100.00 for month in range(1, 13)},
    2022: {month: 1212.00 for month in range(1, 13)},
    2023: {**{month: 1302.00 for month in range(1, 5)}, **{month: 1320.00 for month in range(5, 13)}},
    2024: {month: 1412.00 for month in range(1, 13)},
    2025: {month: 1518.00 for month in range(1, 13)}
}

def obter_salario_minimo(data):
    """Retorna o salário mínimo vigente na data especificada"""
    if isinstance(data, str):
        data = datetime.strptime(data, "%d/%m/%Y")
    return SALARIOS_MINIMOS.get(data.year, {}).get(data.month, 0)

def calcular_pensao_acumulavel(rmi, salario_minimo):
    """
    Calcula o valor acumulável de um benefício segundo as regras da EC 103/2019
    
    Args:
        rmi (float): Valor do benefício a ser reduzido
        salario_minimo (float): Valor do salário mínimo vigente
        
    Returns:
        tuple: (valor_total_recebido, dataframe_com_detalhes)
    """
    faixas = [
        {"limite": 1, "percentual": 1.00, "descricao": "Até 1 SM"},
        {"limite": 2, "percentual": 0.60, "descricao": "De 1 a 2 SM"},
        {"limite": 3, "percentual": 0.40, "descricao": "De 2 a 3 SM"},
        {"limite": 4, "percentual": 0.20, "descricao": "De 3 a 4 SM"},
        {"limite": float('inf'), "percentual": 0.10, "descricao": "Acima de 4 SM"}
    ]
    
    valor_restante = rmi
    acumulado = 0.0
    detalhes = []
    limite_anterior = 0
    
    for faixa in faixas:
        limite_atual = faixa["limite"]
        diferenca_faixa = limite_atual - limite_anterior
        
        # Calcula o valor que cabe nesta faixa (em múltiplos do SM)
        valor_faixa_sm = min(valor_restante, diferenca_faixa * salario_minimo)
        valor_faixa_sm = max(0, valor_faixa_sm)  # Garante que não seja negativo
        
        if valor_faixa_sm > 0:
            # Calcula quanto do valor está dentro desta faixa
            valor_recebido = valor_faixa_sm * faixa["percentual"]
            acumulado += valor_recebido
            
            detalhes.append((
                faixa["descricao"],
                valor_faixa_sm,
                faixa["percentual"],
                valor_recebido
            ))
            
            valor_restante -= valor_faixa_sm
            limite_anterior = limite_atual
        
        if valor_restante <= 0:
            break
    
    # Cria DataFrame com os detalhes
    df_detalhes = pd.DataFrame(
        detalhes, 
        columns=["Faixa", "Valor da Faixa (R$)", "Percentual Aplicado", "Valor Recebido (R$)"]
    )
    
    return acumulado, df_detalhes

# Interface do Streamlit
def main():
    st.title("📊 Cálculo de Acumulação de Benefícios Previdenciários")
    st.markdown("""
    **Calculadora conforme as regras de redução na acumulação de benefícios (EC 103/2019)**  
    Quando uma pessoa tem direito a receber dois benefícios previdenciários ao mesmo tempo,
    o segundo benefício será reduzido conforme as faixas estabelecidas.
    """)
    
    with st.expander("ℹ️ Instruções de Uso"):
        st.write("""
        1. Selecione a data de início do benefício
        2. Informe o valor do segundo benefício
        3. Clique em 'Calcular' para ver o resultado
        4. Você pode baixar os resultados em CSV
        """)
    
    # Formulário de entrada
    col1, col2 = st.columns(2)
    
    with col1:
        data_beneficio = st.date_input(
            "Data de início do benefício",
            value=datetime(2023, 1, 1),
            min_value=datetime(2019, 1, 1),
            max_value=datetime(2025, 12, 31),
            format="DD/MM/YYYY"
        )
        
    with col2:
        valor_beneficio = st.number_input(
            "Valor do segundo benefício (R$)",
            min_value=0.0,
            value=2000.0,
            step=10.0,
            format="%.2f"
        )
    
    # Cálculo e resultados
    if st.button("Calcular Acumulação", type="primary"):
        with st.spinner("Calculando..."):
            salario_minimo = obter_salario_minimo(data_beneficio)
            
            if salario_minimo == 0:
                st.error("Data fora do período coberto ou inválida.")
                return
            
            total_recebido, detalhes_df = calcular_pensao_acumulavel(valor_beneficio, salario_minimo)
            percentual_recebido = (total_recebido / valor_beneficio) * 100
            
            # Mostrar resultados
            st.success(f"**Salário mínimo vigente:** R$ {salario_minimo:,.2f}")
            
            cols = st.columns(3)
            cols[0].metric("Valor Original", f"R$ {valor_beneficio:,.2f}")
            cols[1].metric("Valor Acumulável", f"R$ {total_recebido:,.2f}")
            cols[2].metric("Percentual Recebido", f"{percentual_recebido:.2f}%")
            
            st.subheader("Detalhamento por Faixas")
            st.dataframe(
                detalhes_df.style.format({
                    "Valor da Faixa (R$)": "R$ {:,.2f}",
                    "Valor Recebido (R$)": "R$ {:,.2f}",
                    "Percentual Aplicado": "{:.0%}"
                }),
                use_container_width=True
            )
            
            # Gráfico
            st.subheader("Distribuição por Faixas")
            st.bar_chart(detalhes_df.set_index("Faixa")["Valor Recebido (R$)"])
            
            # Download dos resultados
            csv = detalhes_df.to_csv(index=False, sep=";", decimal=",").encode('utf-8')
            st.download_button(
                "📥 Baixar Resultados em CSV",
                data=csv,
                file_name="resultado_acumulacao.csv",
                mime="text/csv",
                help="Clique para baixar os detalhes do cálculo"
            )

if __name__ == "__main__":
    main()
