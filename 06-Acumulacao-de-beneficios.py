import streamlit as st
import pandas as pd
from datetime import datetime
import base64
from fpdf import FPDF
import tempfile
from unidecode import unidecode

# Configuração da página
st.set_page_config(
    page_title="Cálculo de Acumulação de Benefícios",
    page_icon="📊",
    layout="centered"
)

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

def formatar_moeda_br(valor):
    """Formata valor no padrão monetário brasileiro: 0.000,00"""
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

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

def gerar_pdf_acumulacao(resultados, numero_processo, polo_ativo, polo_passivo, observacoes=None):
    """Gera PDF com os resultados do cálculo de acumulação"""
    try:
        pdf = FPDF()
        pdf.add_page()
        
        # Configurar margens
        pdf.set_margins(left=15, top=15, right=15)
        
        # Tentar usar fonte DejaVu, fallback para Arial
        try:
            FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
            pdf.add_font("DejaVu", "", FONT_PATH, uni=True)
            pdf.set_font("DejaVu", size=10)
        except:
            pdf.set_font("Arial", size=10)
        
        # Cabeçalho com informações do processo
        pdf.set_font("Arial", "B", 12)
        pdf.cell(0, 8, "CÁLCULO DE ACUMULAÇÃO DE BENEFÍCIOS", ln=True, align="C")
        pdf.ln(5)
        
        # Informações do processo
        pdf.set_font("Arial", "", 10)
        pdf.cell(40, 6, "Número do Processo:", 0, 0)
        pdf.cell(0, 6, unidecode(numero_processo) if numero_processo else "Não informado", ln=True)
        
        pdf.cell(40, 6, "Polo Ativo:", 0, 0)
        pdf.cell(0, 6, unidecode(polo_ativo) if polo_ativo else "Não informado", ln=True)
        
        pdf.cell(40, 6, "Polo Passivo:", 0, 0)
        pdf.cell(0, 6, unidecode(polo_passivo) if polo_passivo else "Não informado", ln=True)
        
        pdf.ln(10)
        
        # Dados do cálculo
        pdf.set_font("Arial", "B", 11)
        pdf.cell(0, 8, "RESULTADO DO CÁLCULO", ln=True)
        pdf.set_font("Arial", "", 10)
        
        pdf.cell(60, 6, "Data do benefício:", 0, 0)
        pdf.cell(0, 6, resultados['data_beneficio'].strftime("%d/%m/%Y"), ln=True)
        
        pdf.cell(60, 6, "Salário mínimo vigente:", 0, 0)
        pdf.cell(0, 6, formatar_moeda_br(resultados['salario_minimo']), ln=True)
        
        pdf.cell(60, 6, "Valor original do benefício:", 0, 0)
        pdf.cell(0, 6, formatar_moeda_br(resultados['valor_beneficio']), ln=True)
        
        pdf.cell(60, 6, "Valor acumulável:", 0, 0)
        pdf.cell(0, 6, formatar_moeda_br(resultados['total_recebido']), ln=True)
        
        pdf.cell(60, 6, "Percentual recebido:", 0, 0)
        pdf.cell(0, 6, f"{resultados['percentual_recebido']:.2f}%", ln=True)
        
        pdf.ln(8)
        
        # Detalhamento por faixas
        pdf.set_font("Arial", "B", 11)
        pdf.cell(0, 8, "DETALHAMENTO POR FAIXAS", ln=True)
        pdf.set_font("Arial", "", 9)
        
        # Cabeçalho da tabela
        pdf.cell(50, 6, "Faixa", 1, 0, 'C')
        pdf.cell(45, 6, "Valor da Faixa (R$)", 1, 0, 'C')
        pdf.cell(35, 6, "Percentual", 1, 0, 'C')
        pdf.cell(45, 6, "Valor Recebido (R$)", 1, 1, 'C')
        
        # Dados da tabela
        for _, row in resultados['detalhes_df'].iterrows():
            pdf.cell(50, 6, unidecode(str(row['Faixa'])), 1, 0)
            pdf.cell(45, 6, formatar_moeda_br(row['Valor da Faixa (R$)']), 1, 0, 'R')
            pdf.cell(35, 6, f"{row['Percentual Aplicado']:.0%}", 1, 0, 'C')
            pdf.cell(45, 6, formatar_moeda_br(row['Valor Recebido (R$)']), 1, 1, 'R')
        
        pdf.ln(10)
        
        # Observações
        if observacoes and observacoes.strip():
            pdf.set_font("Arial", "B", 10)
            pdf.cell(0, 8, "OBSERVAÇÕES:", ln=True)
            pdf.set_font("Arial", "I", 9)
            pdf.multi_cell(0, 6, unidecode(observacoes.strip()))
            pdf.ln(5)
        
        # Rodapé com assinatura eletrônica
        pdf.set_font("Arial", "I", 8)
        pdf.cell(0, 6, f"Documento datado e assinado eletronicamente em {datetime.now().strftime('%d/%m/%Y às %H:%M')}.", ln=True, align='C')
        
        # Gerar PDF
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
            pdf.output(tmp_file.name)
            tmp_file.seek(0)
            return tmp_file.read()

    except Exception as e:
        st.error(f"Erro ao gerar PDF: {str(e)}")
        import traceback
        st.error(traceback.format_exc())
        return None

# Interface do Streamlit
def main():
    # Criar abas
    tab1, tab2 = st.tabs(["📊 Calculadora", "📚 Base Legal"])
    
    with tab1:
        # Cabeçalho com logo e informações do processo
        st.markdown("""
        <div style="border: 2px solid #f0f2f6; padding: 20px; border-radius: 10px; margin-bottom: 20px;">
            <table style="width: 100%; border-collapse: collapse;">
                <tr>
                    <td style="width: 20%; vertical-align: top;">
                        <img src="https://raw.githubusercontent.com/carlospatrickds/NovoRepository/main/logifpe.png" 
                             alt="Logo" style="width: 80px; height: auto;">
                    </td>
                    <td style="width: 80%; vertical-align: top;">
                        <h3 style="margin-top: 0; color: #1f77b4;">CÁLCULO DE ACUMULAÇÃO DE BENEFÍCIOS</h3>
                        <table style="width: 100%; font-size: 12px;">
                            <tr>
                                <td style="width: 30%;"><strong>Número do Processo:</strong></td>
                                <td style="width: 70%;">{numero_processo}</td>
                            </tr>
                            <tr>
                                <td><strong>Polo Ativo:</strong></td>
                                <td>{polo_ativo}</td>
                            </tr>
                            <tr>
                                <td><strong>Polo Passivo:</strong></td>
                                <td>{polo_passivo}</td>
                            </tr>
                        </table>
                    </td>
                </tr>
            </table>
        </div>
        """.format(
            numero_processo=st.session_state.get('numero_processo', 'Não informado'),
            polo_ativo=st.session_state.get('polo_ativo', 'Não informado'),
            polo_passivo=st.session_state.get('polo_passivo', 'Não informado')
        ), unsafe_allow_html=True)

        # Formulário para informações do processo
        with st.expander("📋 Informações do Processo", expanded=False):
            col1, col2, col3 = st.columns(3)
            
            with col1:
                numero_processo = st.text_input("Número do Processo", 
                                              value=st.session_state.get('numero_processo', ''),
                                              key='numero_processo_input')
            
            with col2:
                polo_ativo = st.text_input("Polo Ativo", 
                                         value=st.session_state.get('polo_ativo', ''),
                                         key='polo_ativo_input')
            
            with col3:
                polo_passivo = st.text_input("Polo Passivo", 
                                           value=st.session_state.get('polo_passivo', ''),
                                           key='polo_passivo_input')
            
            if st.button("Atualizar Informações do Processo"):
                st.session_state.numero_processo = numero_processo
                st.session_state.polo_ativo = polo_ativo
                st.session_state.polo_passivo = polo_passivo
                st.rerun()

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
            4. Você pode baixar os resultados em CSV ou PDF
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
                
                # Armazena os resultados na sessão para uso no rodapé e PDF
                st.session_state.calculo_realizado = True
                st.session_state.valor_beneficio = valor_beneficio
                st.session_state.total_recebido = total_recebido
                st.session_state.percentual_recebido = percentual_recebido
                st.session_state.salario_minimo = salario_minimo
                st.session_state.detalhes_df = detalhes_df
                st.session_state.data_beneficio = data_beneficio
                
                # Mostrar resultados com formatação brasileira
                st.success(f"**Salário mínimo vigente:** {formatar_moeda_br(salario_minimo)}")
                
                cols = st.columns(3)
                cols[0].metric("Valor Original", formatar_moeda_br(valor_beneficio))
                cols[1].metric("Valor Acumulável", formatar_moeda_br(total_recebido))
                cols[2].metric("Percentual Recebido", f"{percentual_recebido:.2f}%")
                
                st.subheader("Detalhamento por Faixas")
                
                # Formatar DataFrame para exibição com padrão brasileiro
                detalhes_df_formatado = detalhes_df.copy()
                detalhes_df_formatado["Valor da Faixa (R$)"] = detalhes_df_formatado["Valor da Faixa (R$)"].apply(formatar_moeda_br)
                detalhes_df_formatado["Valor Recebido (R$)"] = detalhes_df_formatado["Valor Recebido (R$)"].apply(formatar_moeda_br)
                detalhes_df_formatado["Percentual Aplicado"] = detalhes_df_formatado["Percentual Aplicado"].apply(lambda x: f"{x:.0%}")
                
                st.dataframe(
                    detalhes_df_formatado,
                    use_container_width=True
                )
                
                # Gráfico
                st.subheader("Distribuição por Faixas")
                st.bar_chart(detalhes_df.set_index("Faixa")["Valor Recebido (R$)"])
                
                # Download dos resultados em CSV
                csv = detalhes_df.to_csv(index=False, sep=";", decimal=",").encode('utf-8')
                st.download_button(
                    "📥 Baixar Resultados em CSV",
                    data=csv,
                    file_name="resultado_acumulacao.csv",
                    mime="text/csv",
                    help="Clique para baixar os detalhes do cálculo"
                )

        # Rodapé com observações (só aparece após o cálculo)
        if st.session_state.get('calculo_realizado', False):
            st.markdown("---")
            st.subheader("Observações sobre o Cálculo")
            
            observacoes = st.text_area(
                "Digite suas observações:",
                value=st.session_state.get('observacoes', ''),
                key='observacoes_input',
                height=100,
                placeholder="Digite aqui suas observações sobre o cálculo realizado..."
            )
            
            if st.button("Salvar Observações"):
                st.session_state.observacoes = observacoes
                st.success("Observações salvas!")
            
            # Mostra as observações salvas
            if st.session_state.get('observacoes'):
                st.markdown("**Observações salvas:**")
                st.info(st.session_state.observacoes)
            
            # Botão para gerar PDF
            st.markdown("---")
            st.subheader("📄 Gerar Relatório PDF")
            
            if st.button("🖨️ Gerar PDF", type="primary"):
                if not st.session_state.get('numero_processo'):
                    st.error("Por favor, preencha as informações do processo antes de gerar o PDF.")
                else:
                    with st.spinner("Gerando PDF..."):
                        # Prepara os dados para o PDF
                        resultados_pdf = {
                            'data_beneficio': st.session_state.data_beneficio,
                            'salario_minimo': st.session_state.salario_minimo,
                            'valor_beneficio': st.session_state.valor_beneficio,
                            'total_recebido': st.session_state.total_recebido,
                            'percentual_recebido': st.session_state.percentual_recebido,
                            'detalhes_df': st.session_state.detalhes_df
                        }
                        
                        pdf_data = gerar_pdf_acumulacao(
                            resultados_pdf,
                            st.session_state.numero_processo,
                            st.session_state.polo_ativo,
                            st.session_state.polo_passivo,
                            st.session_state.get('observacoes', '')
                        )
                        
                        if pdf_data:
                            nome_arquivo = f"acumulacao_beneficios_{st.session_state.numero_processo}_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
                            
                            st.download_button(
                                "⬇️ Baixar PDF",
                                pdf_data,
                                file_name=nome_arquivo,
                                mime="application/pdf",
                                help="Clique para baixar o relatório completo em PDF"
                            )
                            
                            st.success("PDF gerado com sucesso!")
            
            # Assinatura eletrônica
            st.markdown("""
            <div style="margin-top: 30px; padding: 15px; background-color: #f8f9fa; border-radius: 5px; text-align: center;">
                <p style="margin: 0; font-style: italic; color: #666;">
                    Documento datado e assinado eletronicamente em {data_atual}.
                </p>
            </div>
            """.format(data_atual=datetime.now().strftime("%d/%m/%Y às %H:%M")), unsafe_allow_html=True)

    with tab2:
        st.title("📚 Base Legal - Acumulação de Benefícios")
        
        st.markdown("""
        ## Emenda Constitucional 103/2019
        
        A Emenda Constitucional 103, de 13 de novembro de 2019, introduziu mudanças significativas no contexto do recebimento acumulado de benefícios previdenciários, regras de aplicações imediatas.
        
        ### Artigo 24 da Emenda Constitucional nº 103/2019:
        
        **Art. 24.** É vedada a acumulação de mais de uma pensão por morte deixada por cônjuge ou companheiro, no âmbito do mesmo regime de previdência social, ressalvadas as pensões do mesmo instituidor, decorrentes do exercício de cargos acumuláveis na forma do art. 37 da Constituição Federal.
        """)
        
                
        st.markdown("""
        ## Portaria 1.467/2022 - Ministério do Trabalho e Previdência
        
        Com intuito de trazer mais clareza as possibilidades de acumulação de benefícios o Ministério do Trabalho e Previdência disciplinou as regras da EC 103/2019 por intermédio da Portaria 1.467, de 02 de junho de 2022, trazendo em seu Capítulo VII, Seção III, detalhamento sobre as possibilidades de acúmulos, forma de apuração dos benefícios e as possibilidades de não incidência das regras.
        """)
        
        st.markdown("""
        ## Possibilidades de Acumulação de Benefícios
        
        Desta forma, as possibilidades de acumulação de benefícios são:
        
        **I** – pensão por morte deixada por cônjuge ou companheiro no âmbito do RPPS com pensão por morte concedida em outro RPPS ou no RGPS, e pensão por morte deixada por cônjuge ou companheiro no âmbito do RGPS com pensão por morte deixada no âmbito do RPPS;
        
        **II** – pensão por morte deixada por cônjuge ou companheiro no âmbito do RGPS com pensões por morte decorrentes das atividades militares de que tratam os arts. 42 e 142 da Constituição Federal;
        
        **III** – pensão por morte deixada por cônjuge ou companheiro no âmbito do RPPS com pensões por morte decorrentes das atividades militares de que tratam os arts. 42 e 142 da Constituição Federal;
        
        **IV** – pensão por morte deixada por cônjuge ou companheiro no âmbito do RGPS com aposentadoria concedida por RPPS ou RGPS;
        
        **V** – pensão por morte deixada por cônjuge ou companheiro no âmbito do RPPS com aposentadoria concedida por RPPS ou RGPS;
        
        **VI** – pensão por morte deixada por cônjuge ou companheiro no âmbito do RPPS ou do RGPS com proventos de inatividade decorrentes das atividades militares de que tratam os arts. 42 e 142 da Constituição Federal;
        
        **VII** – pensões por morte decorrentes das atividades militares de que tratam os arts. 42 e 142 da Constituição Federal com aposentadoria concedida no âmbito do RGPS;
        
        **VIII** – pensões por morte decorrentes das atividades militares de que tratam os arts. 42 e 142 da Constituição Federal com aposentadoria concedida no âmbito de RPPS.
        """)
        
        st.markdown("""
        ## Tabela de Faixas Salariais
        
        Nas hipóteses de acumulações previstas, é assegurada a percepção do valor integral do benefício mais vantajoso e de uma parte de cada um dos demais benefícios, conforme a tabela de faixa salarial a seguir:
        """)
        
        # Tabela de faixas salariais
        tabela_faixas = pd.DataFrame({
            'FAIXA SALARIAL (EM QUANTIDADE DE SALÁRIOS MÍNIMO)': [
                'Até 1',
                'De 1 a 2',
                'De 2 a 3',
                'De 3 a 4',
                'Acima de 4'
            ],
            'VALOR A SER PAGO (% DO SALÁRIO APURADO)': [
                '100%',
                '60%',
                '40%',
                '20%',
                '10%'
            ]
        })
        
        st.table(tabela_faixas)
        
        st.markdown("""
        ### Fonte:
        - [Emenda Constitucional nº 103/2019](https://www.planalto.gov.br/ccivil_03/constituicao/emendas/emc/emc103.htm)
        - [Portaria MTPS nº 1.467/2022](https://www.gov.br/previdencia/pt-br/assuntos/rpps/destaques/portaria-mtp-no-1-467-de-02-junho-de-2022)
        - [AngraPrev] (https://www.angraprev.rj.gov.br/acumulo-de-beneficios/)
        """)

if __name__ == "__main__":
    # Inicializa variáveis de sessão se não existirem
    if 'numero_processo' not in st.session_state:
        st.session_state.numero_processo = ''
    if 'polo_ativo' not in st.session_state:
        st.session_state.polo_ativo = ''
    if 'polo_passivo' not in st.session_state:
        st.session_state.polo_passivo = ''
    if 'observacoes' not in st.session_state:
        st.session_state.observacoes = ''
    if 'calculo_realizado' not in st.session_state:
        st.session_state.calculo_realizado = False
        
    main()
