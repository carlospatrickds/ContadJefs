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
# Geração de PDF detalhado com progressividade por ano e comparação
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
    """Gera PDF pericial comparativo com detalhamento progressivo para duas bases,
       e adiciona uma tabela síntese no final."""
    pdf = PDF()
    pdf.add_page()
    pdf.set_font('Arial', 'B', 11)
    pdf.cell(0, 10, 'Relatório Comparativo PSS - RPPS', ln=True, align='C')
    pdf.ln(5)

    # Processa cada ano e guarda dados para a tabela síntese
    dados_sintese = []

    for idx, ano_data in enumerate(dados_comparacao):
        ano = ano_data['ano']
        sal1 = ano_data['sal1']
        sal2 = ano_data['sal2']
        contrib1 = ano_data['contrib1']
        contrib2 = ano_data['contrib2']
        breakdown1 = ano_data['breakdown1']
        breakdown2 = ano_data['breakdown2']

        # Adiciona nova página se não for o primeiro ano
        if idx > 0:
            pdf.add_page()

        pdf.set_font('Arial', 'B', 11)
        pdf.cell(0, 10, f"Ano {ano}", ln=True, align='C')
        pdf.ln(5)

        # Tabela Base 1
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

        # Tabela Base 2
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

        # Diferenças e efetivas
        diff_sal = sal2 - sal1
        diff_contrib = contrib2 - contrib1
        pdf.ln(5)
        pdf.set_font('Arial', 'B', 10)
        pdf.cell(0, 8, "Diferenças:", ln=True)
        pdf.set_font('Arial', '', 9)
        pdf.cell(80, 8, f"Diferença Salário (Base2 - Base1):", border=1)
        pdf.cell(50, 8, formatar_moeda(diff_sal), border=1, ln=True)
        pdf.cell(80, 8, f"Diferença Contribuição (Base2 - Base1):", border=1)
        pdf.cell(50, 8, formatar_moeda(diff_contrib), border=1, ln=True)

        efetiva1 = (contrib1 / sal1 * 100) if sal1 > 0 else 0
        efetiva2 = (contrib2 / sal2 * 100) if sal2 > 0 else 0
        pdf.cell(80, 8, "Alíquota Efetiva Base 1:", border=1)
        pdf.cell(50, 8, f"{efetiva1:.2f}%", border=1, ln=True)
        pdf.cell(80, 8, "Alíquota Efetiva Base 2:", border=1)
        pdf.cell(50, 8, f"{efetiva2:.2f}%", border=1, ln=True)

        # Portaria de referência
        pdf.ln(5)
        pdf.set_font('Arial', 'I', 8)
        pdf.cell(0, 6, f"Fonte: {PORTARIAS.get(ano, 'Portaria não especificada')}", ln=True)

        pdf.ln(10)

        # Armazena dados para a síntese
        dados_sintese.append({
            "Ano": ano,
            "Salário Base 1": formatar_moeda(sal1),
            "Salário Base 2": formatar_moeda(sal2),
            "Contribuição Base 1": formatar_moeda(contrib1),
            "Contribuição Base 2": formatar_moeda(contrib2),
            "Diferença Salário": formatar_moeda(diff_sal),
            "Diferença Contribuição": formatar_moeda(diff_contrib),
        })

    # Adiciona página de síntese
    if dados_sintese:
        pdf.add_page()
        pdf.set_font('Arial', 'B', 11)
        pdf.cell(0, 10, 'Síntese Comparativa', ln=True, align='C')
        pdf.ln(5)

        # Cabeçalho da tabela síntese (ajustado para largura)
        pdf.set_font('Arial', 'B', 8)
        pdf.cell(15, 8, 'Ano', border=1)
        pdf.cell(35, 8, 'Salário Base 1', border=1)
        pdf.cell(35, 8, 'Salário Base 2', border=1)
        pdf.cell(35, 8, 'Contribuição Base 1', border=1)
        pdf.cell(35, 8, 'Contribuição Base 2', border=1)
        pdf.cell(30, 8, 'Diferença Salário', border=1)
        pdf.cell(35, 8, 'Diferença Contribuição', border=1)
        pdf.ln()

        pdf.set_font('Arial', '', 8)
        for linha in dados_sintese:
            pdf.cell(15, 8, str(linha['Ano']), border=1)
            pdf.cell(35, 8, linha['Salário Base 1'], border=1)
            pdf.cell(35, 8, linha['Salário Base 2'], border=1)
            pdf.cell(35, 8, linha['Contribuição Base 1'], border=1)
            pdf.cell(35, 8, linha['Contribuição Base 2'], border=1)
            pdf.cell(30, 8, linha['Diferença Salário'], border=1)
            pdf.cell(35, 8, linha['Diferença Contribuição'], border=1)
            pdf.ln()

    # Observações
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
# Interface Streamlit (mantida igual à versão anterior, apenas incluímos a nova função)
# -----------------------------------------------------------------------------
# ... (todo o código da interface permanece igual, apenas a função PDF foi atualizada)
# Para manter a resposta dentro do limite, vou reproduzir apenas a parte da interface
# que não muda, mas é importante manter a consistência.
# Como o usuário já tem o código anterior, fornecerei apenas a parte da função gerar_pdf_comparacao
# e a nova definição da classe PDF (a mesma já está incluída acima). A interface Streamlit é idêntica.
# -----------------------------------------------------------------------------
