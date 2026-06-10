import streamlit as st
import pandas as pd
from fpdf import FPDF
import base64
import json
from datetime import datetime

# ==============================================================================
# 1. CONFIGURAÇÃO E TEMAS
# ==============================================================================
st.set_page_config(page_title="Calculadora Jurídica Integrada", layout="wide")

THEMES = {
    "Salmão": {
        "th_bg": (255, 197, 153),
        "header_bg": (255, 236, 217),
        "divider": (190, 80, 20),
        "css": """
        <style>
            :root {
                --primary: #4d2916;
                --th-bg: #FFC599;
                --divider-color: #BE5014;
                --info: #692a08;
                --header-bg: #ffecd9;
            }
            th { color: #000 !important; border-color: #dca377 !important; background-color: var(--th-bg) !important; }
            .header-row { color: #000 !important; border-color: #FFC599 !important; background-color: var(--header-bg) !important; }
        </style>
        """
    },
    "Clássico (Azul/Cinza)": {
        "th_bg": (245, 245, 245),
        "header_bg": (208, 211, 212),
        "divider": (127, 140, 141),
        "css": """
        <style>
            :root {
                --primary: #585a5a;
                --th-bg: #f5f5f5;
                --divider-color: #7f8c8d;
                --info: #585a5a;
                --header-bg: #d0d3d4;
            }
            th { color: #000 !important; border-color: #7f8c8d !important; background-color: var(--th-bg) !important; }
            .header-row { color: #000 !important; border-color: #7f8c8d !important; background-color: var(--header-bg) !important; }
        </style>
        """
    }
}

# ==============================================================================
# 2. FUNÇÕES AUXILIARES COMUNS
# ==============================================================================
def parse_valor(v_str):
    v_str = str(v_str).strip().replace('R$', '').strip()
    if not v_str:
        return 0.0
    if ',' in v_str:
        v_str = v_str.replace('.', '')
        v_str = v_str.replace(',', '.')
    try:
        return float(v_str)
    except ValueError:
        return 0.0

def formatar_moeda(valor):
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def sanitize_text(text):
    if not text:
        return ""
    replacements = {
        '\u201c': '"', '\u201d': '"',
        '\u2018': "'", '\u2019': "'",
        '\u2013': '-', '\u2014': '-',
        '\u2026': '...',
    }
    for k, v in replacements.items():
        text = text.replace(k, v)
    return text.encode('latin1', 'replace').decode('latin1')

def clean_dict_keys(obj):
    """Remove espaços no final das chaves do JSON do Abono."""
    if isinstance(obj, dict):
        return {k.strip(): clean_dict_keys(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [clean_dict_keys(i) for i in obj]
    return obj

# ==============================================================================
# 3. TABELAS DE CONTRIBUIÇÃO DO RPPS – 2020 a 2026
# ==============================================================================
TABLES = {
    2020: [(0.00, 1045.00, 0.075), (1045.01, 2000.00, 0.09), (2000.01, 3000.00, 0.12), (3000.01, 5839.45, 0.14), (5839.46, 10000.00, 0.145), (10000.01, 20000.00, 0.165), (20000.01, 39000.00, 0.19), (39000.01, float('inf'), 0.22)],
    2021: [(0.00, 1100.00, 0.075), (1100.01, 2203.48, 0.09), (2203.49, 3305.22, 0.12), (3305.23, 6433.57, 0.14), (6433.58, 11017.42, 0.145), (11017.43, 22034.83, 0.165), (22034.84, 42967.92, 0.19), (42967.93, float('inf'), 0.22)],
    2022: [(0.00, 1212.00, 0.075), (1212.01, 2427.35, 0.09), (2427.36, 3641.03, 0.12), (3641.04, 7087.22, 0.14), (7087.23, 12136.79, 0.145), (12136.80, 24273.57, 0.165), (24273.58, 47333.46, 0.19), (47333.47, float('inf'), 0.22)],
    2023: [(0.00, 1302.00, 0.075), (1302.01, 2571.29, 0.09), (2571.30, 3856.94, 0.12), (3856.95, 7507.49, 0.14), (7507.50, 12856.50, 0.145), (12856.51, 25712.99, 0.165), (25713.00, 50140.33, 0.19), (50140.34, float('inf'), 0.22)],
    2024: [(0.00, 1412.00, 0.075), (1412.01, 2666.68, 0.09), (2666.69, 4000.03, 0.12), (4000.04, 7786.02, 0.14), (7786.03, 13333.48, 0.145), (13333.49, 26666.94, 0.165), (26666.95, 52000.54, 0.19), (52000.55, float('inf'), 0.22)],
    2025: [(0.00, 1518.00, 0.075), (1518.01, 2793.88, 0.09), (2793.89, 4190.83, 0.12), (4190.84, 8157.41, 0.14), (8157.42, 13969.49, 0.145), (13969.50, 27938.95, 0.165), (27938.96, 54480.97, 0.19), (54480.98, float('inf'), 0.22)],
    2026: [(0.00, 1621.00, 0.075), (1621.01, 2902.84, 0.09), (2902.85, 4354.27, 0.12), (4354.28, 8475.55, 0.14), (8475.56, 14514.30, 0.145), (14514.31, 29028.57, 0.165), (29028.58, 56605.73, 0.19), (56605.74, float('inf'), 0.22)],
}

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

# ==============================================================================
# 4. INICIALIZAÇÃO DO SESSION STATE
# ==============================================================================
# --- PSS ---
if 'processo_input' not in st.session_state: st.session_state.processo_input = ""
if 'autor_input' not in st.session_state: st.session_state.autor_input = ""
if 'observacao_input' not in st.session_state: st.session_state.observacao_input = ""

for ano in AVAILABLE_YEARS:
    if f"valor_{ano}" not in st.session_state: st.session_state[f"valor_{ano}"] = "0,00"
    if f"comp_base1_{ano}" not in st.session_state: st.session_state[f"comp_base1_{ano}"] = "0,00"
    if f"comp_base2_{ano}" not in st.session_state: st.session_state[f"comp_base2_{ano}"] = "0,00"

# --- Abono de Permanência ---
if 'abono_data_loaded' not in st.session_state:
    st.session_state.abono_data_loaded = False
if 'abono_meta' not in st.session_state:
    st.session_state.abono_meta = {}
if 'abono_dados' not in st.session_state:
    st.session_state.abono_dados = []
if 'abono_idx' not in st.session_state:
    st.session_state.abono_idx = {}
if 'abono_edited_df' not in st.session_state:
    st.session_state.abono_edited_df = None

# ==============================================================================
# 5. LÓGICA DE CÁLCULO PSS
# ==============================================================================
def calcular_contribuicao_progressiva(salario, tabela):
    if salario <= 0: return 0.0, []
    restante = salario
    total = 0.0
    detalhamento = []
    for i, (lim_inf, lim_sup, aliquota) in enumerate(tabela):
        if restante <= 0: break
        if i == 0:
            tributavel = min(restante, lim_sup)
        else:
            if lim_sup == float('inf'): tributavel = restante
            else: tributavel = min(restante, lim_sup - lim_inf)
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

# ==============================================================================
# 6. SIDEBAR COMUM
# ==============================================================================
with st.sidebar:
    st.header("🎨 Tema Visual")
    tema_selecionado = st.radio("Escolha o esquema de cores:", ["Salmão", "Clássico (Azul/Cinza)"])
    tema_ativo = THEMES[tema_selecionado]

    st.markdown("---")

    # IMPORTAÇÃO DE DADOS PSS -----------------------------------------------
    st.header("📂 Importar Dados PSS")
    arquivo_importado = st.file_uploader("Carregar arquivo .json (PSS)", type=["json"], key="import_pss")
    if arquivo_importado is not None:
        if st.button("Restaurar Dados PSS"):
            try:
                dados_json = json.load(arquivo_importado)
                info = dados_json.get("informacoes_processo", {})
                st.session_state.processo_input = info.get("processo", "")
                st.session_state.autor_input = info.get("autor", "")
                st.session_state.observacao_input = info.get("observacoes", "")

                val_anuais = dados_json.get("valores_relatorio_anual", {})
                for ano, valor in val_anuais.items():
                    if f"valor_{ano}" in st.session_state:
                        st.session_state[f"valor_{ano}"] = valor

                val_comp = dados_json.get("valores_comparacao", {})
                base1 = val_comp.get("base_1", {})
                base2 = val_comp.get("base_2", {})

                for ano, valor in base1.items():
                    if f"comp_base1_{ano}" in st.session_state:
                        st.session_state[f"comp_base1_{ano}"] = valor
                for ano, valor in base2.items():
                    if f"comp_base2_{ano}" in st.session_state:
                        st.session_state[f"comp_base2_{ano}"] = valor

                st.success("Dados PSS restaurados com sucesso!")
                st.rerun()
            except Exception as e:
                st.error(f"Erro ao ler o arquivo: {e}")

    st.markdown("---")

    # INFORMAÇÕES DO PROCESSO -------------------------------------------------
    st.header("📋 Informações do Processo")
    st.text_input("Número do Processo", key="processo_input")
    st.text_input("Nome do Autor da Ação", key="autor_input")
    st.text_area("Observações (opcional)", height=100, key="observacao_input")

    # EXPORTAÇÃO DE DADOS PSS -------------------------------------------------
    st.markdown("---")
    st.header("💾 Exportar Dados PSS")

    autor_raw = st.session_state.autor_input.strip()
    if autor_raw:
        partes_nome = autor_raw.split()
        dois_primeiros_nomes = " ".join(partes_nome[:2]).upper()
    else:
        dois_primeiros_nomes = "SEM_NOME"

    timestamp = datetime.now().strftime("%d%m%Y%H%M%S")
    nome_arquivo_json = f"CALC_PSS_OS {dois_primeiros_nomes} {timestamp}.json"

    dados_para_exportar = {
        "informacoes_processo": {
            "processo": st.session_state.processo_input,
            "autor": st.session_state.autor_input,
            "observacoes": st.session_state.observacao_input
        },
        "valores_relatorio_anual": {
            str(ano): st.session_state[f"valor_{ano}"] for ano in AVAILABLE_YEARS
        },
        "valores_comparacao": {
            "base_1": {str(ano): st.session_state[f"comp_base1_{ano}"] for ano in AVAILABLE_YEARS},
            "base_2": {str(ano): st.session_state[f"comp_base2_{ano}"] for ano in AVAILABLE_YEARS}
        }
    }

    json_string = json.dumps(dados_para_exportar, ensure_ascii=False, indent=4)

    st.download_button(
        label="📥 Baixar arquivo .json PSS",
        data=json_string,
        file_name=nome_arquivo_json,
        mime="application/json",
        use_container_width=True
    )

# Injetar o CSS dinâmico
st.markdown(tema_ativo["css"], unsafe_allow_html=True)

# ==============================================================================
# 7. CLASSES E FUNÇÕES DE GERAÇÃO DE PDF (PSS)
# ==============================================================================
class PDFComp(FPDF):
    def header(self):
        if self.page_no() == 1:
            self.set_font('Arial', 'B', 12)
            self.cell(0, 10, 'Relatório Comparativo PSS - RPPS', ln=True, align='C')
            self.ln(5)
            self.set_font('Arial', '', 10)
            if hasattr(self, 'theme_colors'):
                self.set_fill_color(*self.theme_colors["header_bg"]) 
            if st.session_state.processo_input:
                proc = sanitize_text(st.session_state.processo_input)
                self.cell(0, 8, f" Processo: {proc}", ln=True, fill=True)
                self.ln(1)
            if st.session_state.autor_input:
                aut = sanitize_text(st.session_state.autor_input)
                self.cell(0, 8, f" Autor: {aut}", ln=True, fill=True)
                self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Página {self.page_no()}', align='C')

def gerar_pdf_comparacao(dados_comparacao, observacao_texto, tema):
    pdf = PDFComp()
    pdf.theme_colors = tema
    pdf.add_page()

    dados_sintese = []
    pdf.set_fill_color(*tema["th_bg"])

    for idx, ano_data in enumerate(dados_comparacao):
        ano = ano_data['ano']
        sal1 = ano_data['sal1']
        sal2 = ano_data['sal2']
        contrib1 = ano_data['contrib1']
        contrib2 = ano_data['contrib2']
        breakdown1 = ano_data['breakdown1']
        breakdown2 = ano_data['breakdown2']

        if idx > 0: pdf.add_page()

        pdf.set_font('Arial', 'B', 11)
        pdf.cell(0, 10, f" Ano {ano}", ln=True, align='C', fill=True)
        pdf.ln(5)

        # Base 1
        pdf.set_font('Arial', 'B', 10)
        pdf.cell(0, 8, f" Base 1 - Valor: {formatar_moeda(sal1)}", ln=True)
        pdf.set_font('Arial', 'B', 9)
        pdf.cell(50, 8, 'Faixa de Valor', border=1, fill=True)
        pdf.cell(40, 8, 'Base (R$)', border=1, fill=True)
        pdf.cell(30, 8, 'Alíquota', border=1, fill=True)
        pdf.cell(50, 8, 'Contribuição (R$)', border=1, fill=True)
        pdf.ln()
        pdf.set_font('Arial', '', 9)
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
        pdf.cell(0, 8, f" Base 2 - Valor: {formatar_moeda(sal2)}", ln=True)
        pdf.set_font('Arial', 'B', 9)
        pdf.cell(50, 8, 'Faixa de Valor', border=1, fill=True)
        pdf.cell(40, 8, 'Base (R$)', border=1, fill=True)
        pdf.cell(30, 8, 'Alíquota', border=1, fill=True)
        pdf.cell(50, 8, 'Contribuição (R$)', border=1, fill=True)
        pdf.ln()
        pdf.set_font('Arial', '', 9)
        for det in breakdown2:
            pdf.cell(50, 8, det['faixa'], border=1)
            pdf.cell(40, 8, formatar_moeda(det['base']), border=1)
            pdf.cell(30, 8, det['aliquota'], border=1)
            pdf.cell(50, 8, formatar_moeda(det['contribuicao']), border=1)
            pdf.ln()
        pdf.set_font('Arial', 'B', 9)
        pdf.cell(120, 8, "Total Contribuição Base 2:", border=1)
        pdf.cell(50, 8, formatar_moeda(contrib2), border=1, ln=True)

        diff_valor = sal2 - sal1
        diff_contrib = contrib2 - contrib1
        pdf.ln(5)
        pdf.set_font('Arial', 'B', 10)
        pdf.cell(0, 8, "Diferenças:", ln=True)
        pdf.set_font('Arial', '', 9)
        pdf.cell(80, 8, "Diferença entre valores_base (Base2 - Base1):", border=1)
        pdf.cell(50, 8, formatar_moeda(diff_valor), border=1, ln=True)
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
        pdf.cell(0, 6, f"Fonte: {sanitize_text(PORTARIAS.get(ano, 'Portaria não especificada'))}", ln=True)
        pdf.ln(10)

        dados_sintese.append({
            "Ano": ano, "Valor Base 1": formatar_moeda(sal1), "Valor Base 2": formatar_moeda(sal2),
            "Contribuição Base 1": formatar_moeda(contrib1), "Contribuição Base 2": formatar_moeda(contrib2),
            "Diferença entre valores_base": formatar_moeda(diff_valor), "Diferença Contribuição": formatar_moeda(diff_contrib),
            "diff_contrib_raw": diff_contrib,
        })

    # Página de síntese
    if dados_sintese:
        pdf.add_page()
        pdf.set_font('Arial', 'B', 11)
        pdf.cell(0, 10, 'Síntese Comparativa', ln=True, align='C')
        pdf.ln(5)

        pdf.set_font('Arial', 'B', 8)
        margem_esquerda = pdf.get_x()
        pdf.cell(15, 8, 'Ano', border=1, fill=True)
        pdf.cell(30, 8, 'Valor Base 1', border=1, fill=True)
        pdf.cell(30, 8, 'Valor Base 2', border=1, fill=True)
        pdf.cell(30, 8, 'Contrib. Base 1', border=1, fill=True) 
        pdf.cell(30, 8, 'Contrib. Base 2', border=1, fill=True)

        x = pdf.get_x()
        y = pdf.get_y()
        pdf.multi_cell(28, 4, 'Diferença entre\nvalores_base', border=1, align='C', fill=True)
        pdf.set_xy(x + 28, y)
        pdf.multi_cell(32, 4, 'Diferença\nContribuição', border=1, align='C', fill=True)
        pdf.set_xy(margem_esquerda, y + 8)
        pdf.set_font('Arial', '', 8)

        total_diff_contrib = 0.0
        for linha in dados_sintese:
            pdf.cell(15, 8, str(linha['Ano']), border=1)
            pdf.cell(30, 8, linha['Valor Base 1'], border=1)
            pdf.cell(30, 8, linha['Valor Base 2'], border=1)
            pdf.cell(30, 8, linha['Contribuição Base 1'], border=1)
            pdf.cell(30, 8, linha['Contribuição Base 2'], border=1)
            pdf.cell(28, 8, linha['Diferença entre valores_base'], border=1)
            pdf.cell(32, 8, linha['Diferença Contribuição'], border=1)
            pdf.ln()
            total_diff_contrib += linha['diff_contrib_raw']

        pdf.set_font('Arial', 'B', 8)
        pdf.cell(15, 8, 'Total', border=1)
        pdf.cell(30, 8, '', border=1)
        pdf.cell(30, 8, '', border=1)
        pdf.cell(30, 8, '', border=1)
        pdf.cell(30, 8, '', border=1)
        pdf.cell(28, 8, '-', border=1, align='C')
        pdf.cell(32, 8, formatar_moeda(total_diff_contrib), border=1)
        pdf.ln()

    if observacao_texto:
        obs_sanitizada = sanitize_text(observacao_texto)
        pdf.ln(5)
        pdf.set_draw_color(*tema["divider"])
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(5)
        pdf.set_font('Arial', 'B', 11)
        pdf.cell(0, 10, 'Observações:', ln=True)
        pdf.set_font('Arial', '', 10)
        pdf.multi_cell(0, 6, obs_sanitizada)

    out = pdf.output(dest='S')
    if isinstance(out, str): return out.encode('latin1')
    return out

# ==============================================================================
# 8. INTERFACE PRINCIPAL (ABAS)
# ==============================================================================
st.title("📊 Calculadora Jurídica Integrada")
st.markdown("PSS - Servidores Públicos Federais (2020-2026) | Abono de Permanência")

tab1, tab2, tab3, tab4 = st.tabs([
    "🔍 Cálculo Detalhado PSS", 
    "📅 Relatório Anual PSS", 
    "⚖️ Comparação de Bases PSS",
    "🧮 Abono de Permanência"
])

# ------------------------------------------------------------------------------
# TAB 1: Cálculo detalhado por faixa
# ------------------------------------------------------------------------------
with tab1:
    col1, col2 = st.columns(2)
    with col1:
        ano_detalhe = st.selectbox("Selecione o ano", options=AVAILABLE_YEARS, key="detail_year")
        salario_detalhe_str = st.text_input(f"Valor (R$) – base de contribuição ({ano_detalhe})", value="0,00", key="detail_salary")
        salario_detalhe = parse_valor(salario_detalhe_str)

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

# ------------------------------------------------------------------------------
# TAB 2: Relatório anual (PDF detalhado)
# ------------------------------------------------------------------------------
with tab2:
    st.subheader("📅 Informe os valores para cada ano (2020 a 2026)")
    valores_anuais = {}
    for ano in AVAILABLE_YEARS:
        val_str = st.text_input(f"Valor para {ano} (R$)", key=f"valor_{ano}")
        valores_anuais[ano] = parse_valor(val_str)

    if st.button("📄 Gerar Relatório PDF Detalhado", key="gerar_pdf"):
        dados_relatorio = []
        for ano in AVAILABLE_YEARS:
            val = valores_anuais[ano]
            if val > 0:
                contrib, detalhes = calcular_contribuicao_progressiva(val, TABLES[ano])
                efetiva = (contrib / val * 100) if val > 0 else 0.0
                dados_relatorio.append({
                    "ano": ano, "valor": formatar_moeda(val), "contribuicao": formatar_moeda(contrib),
                    "aliquota": f"{efetiva:.2f}%", "contrib_raw": contrib, "detalhes": detalhes
                })
        if not dados_relatorio:
            st.warning("Nenhum dado para gerar relatório. Informe pelo menos um valor positivo.")
        else:
            class PDFDet(FPDF):
                def header(self):
                    if self.page_no() == 1:
                        self.set_font('Arial', 'B', 12)
                        self.cell(0, 10, 'Relatório de Cálculo PSS - RPPS', ln=True, align='C')
                        self.ln(5)
                        self.set_font('Arial', '', 10)
                        if hasattr(self, 'theme_colors'):
                            self.set_fill_color(*self.theme_colors["header_bg"])
                        if st.session_state.processo_input:
                            self.cell(0, 8, f" Processo: {sanitize_text(st.session_state.processo_input)}", ln=True, fill=True)
                            self.ln(1)
                        if st.session_state.autor_input:
                            self.cell(0, 8, f" Autor: {sanitize_text(st.session_state.autor_input)}", ln=True, fill=True)
                            self.ln(5)
                def footer(self):
                    self.set_y(-15)
                    self.set_font('Arial', 'I', 8)
                    self.cell(0, 10, f'Página {self.page_no()}', align='C')

            def gerar_pdf_detalhado(dados_anos, obs_texto, tema):
                pdf = PDFDet()
                pdf.theme_colors = tema
                pdf.add_page()
                pdf.set_fill_color(*tema["th_bg"])
                pdf.set_font('Arial', 'B', 11)
                pdf.cell(0, 10, ' Resumo por Ano', ln=True, fill=True)
                pdf.set_font('Arial', 'B', 10)
                pdf.cell(30, 8, 'Ano', border=1, fill=True)
                pdf.cell(50, 8, 'Valor (R$)', border=1, fill=True)
                pdf.cell(60, 8, 'Contribuição Total (R$)', border=1, fill=True)
                pdf.cell(40, 8, 'Alíquota Efetiva', border=1, fill=True)
                pdf.ln()
                pdf.set_font('Arial', '', 10)
                for linha in dados_anos:
                    pdf.cell(30, 8, str(linha['ano']), border=1)
                    pdf.cell(50, 8, linha['valor'], border=1)
                    pdf.cell(60, 8, linha['contribuicao'], border=1)
                    pdf.cell(40, 8, linha['aliquota'], border=1)
                    pdf.ln()
                for linha in dados_anos:
                    if not linha.get('detalhes'): continue
                    pdf.add_page()
                    pdf.set_font('Arial', 'B', 11)
                    pdf.cell(0, 10, f" Detalhamento Progressivo - Ano {linha['ano']}", ln=True, fill=True)
                    pdf.set_font('Arial', 'B', 10)
                    pdf.cell(60, 8, 'Faixa de Valor', border=1, fill=True)
                    pdf.cell(50, 8, 'Base (R$)', border=1, fill=True)
                    pdf.cell(40, 8, 'Alíquota', border=1, fill=True)
                    pdf.cell(50, 8, 'Contribuição (R$)', border=1, fill=True)
                    pdf.ln()
                    pdf.set_font('Arial', '', 10)
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
                    pdf.cell(0, 6, f"Fonte: {sanitize_text(PORTARIAS.get(linha['ano'], 'Portaria não especificada'))}", ln=True)
                if obs_texto:
                    pdf.add_page()
                    pdf.set_draw_color(*tema["divider"])
                    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
                    pdf.ln(5)
                    pdf.set_font('Arial', 'B', 11)
                    pdf.cell(0, 10, 'Observações:', ln=True)
                    pdf.set_font('Arial', '', 10)
                    pdf.multi_cell(0, 6, sanitize_text(obs_texto))
                out = pdf.output(dest='S')
                if isinstance(out, str): return out.encode('latin1')
                return out

            pdf_bytes = gerar_pdf_detalhado(dados_relatorio, st.session_state.observacao_input, tema_ativo)
            b64 = base64.b64encode(pdf_bytes).decode()
            href = f'<a href="data:application/octet-stream;base64,{b64}" download="relatorio_pss_detalhado.pdf">📥 Clique aqui para baixar o relatório PDF</a>'
            st.markdown(href, unsafe_allow_html=True)
            st.success("Relatório detalhado gerado com sucesso!")

# ------------------------------------------------------------------------------
# TAB 3: Comparação de Bases
# ------------------------------------------------------------------------------
with tab3:
    st.subheader("⚖️ Comparação entre duas bases de cálculo por ano")
    st.markdown("Informe dois valores para cada ano. A diferença na contribuição será calculada.")

    cols = st.columns(2)
    bases = {}
    with cols[0]:
        st.markdown("**Base 1 (Valor)**")
        for ano in AVAILABLE_YEARS:
            val_str = st.text_input(f"{ano} (R$)", key=f"comp_base1_{ano}")
            bases[f"base1_{ano}"] = parse_valor(val_str)
    with cols[1]:
        st.markdown("**Base 2 (Valor)**")
        for ano in AVAILABLE_YEARS:
            val_str = st.text_input(f"{ano} (R$)", key=f"comp_base2_{ano}")
            bases[f"base2_{ano}"] = parse_valor(val_str)

    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        if st.button("Calcular Diferenças", key="calcular_comparacao"):
            comparacao = []
            for ano in AVAILABLE_YEARS:
                val1 = bases[f"base1_{ano}"]
                val2 = bases[f"base2_{ano}"]
                if val1 > 0 or val2 > 0:
                    contrib1, _ = calcular_contribuicao_progressiva(val1, TABLES[ano])
                    contrib2, _ = calcular_contribuicao_progressiva(val2, TABLES[ano])
                    diff_contrib = contrib2 - contrib1
                    diff_val = val2 - val1
                    comparacao.append({
                        "Ano": ano, "Valor 1 (R$)": formatar_moeda(val1), "Contribuição 1 (R$)": formatar_moeda(contrib1),
                        "Valor 2 (R$)": formatar_moeda(val2), "Contribuição 2 (R$)": formatar_moeda(contrib2),
                        "Diferença entre valores_base (R$)": formatar_moeda(diff_val), "Diferença Contribuição (R$)": formatar_moeda(diff_contrib),
                    })
            if comparacao:
                df_comp = pd.DataFrame(comparacao)
                st.dataframe(df_comp, use_container_width=True, hide_index=True)
            else:
                st.warning("Nenhum ano com valores positivos informados.")

    with col_btn2:
        if st.button("📄 Gerar Relatório Comparativo PDF", key="gerar_pdf_comparacao"):
            dados_comparacao = []
            for ano in AVAILABLE_YEARS:
                val1 = bases[f"base1_{ano}"]
                val2 = bases[f"base2_{ano}"]
                if val1 > 0 or val2 > 0:
                    contrib1, breakdown1 = calcular_contribuicao_progressiva(val1, TABLES[ano])
                    contrib2, breakdown2 = calcular_contribuicao_progressiva(val2, TABLES[ano])
                    dados_comparacao.append({
                        "ano": ano, "sal1": val1, "sal2": val2, "contrib1": contrib1, "contrib2": contrib2,
                        "breakdown1": breakdown1, "breakdown2": breakdown2,
                    })
            if not dados_comparacao:
                st.warning("Nenhum dado para gerar relatório. Informe pelo menos um valor positivo em algum ano.")
            else:
                pdf_bytes = gerar_pdf_comparacao(dados_comparacao, st.session_state.observacao_input, tema_ativo)
                b64 = base64.b64encode(pdf_bytes).decode()
                href = f'<a href="data:application/octet-stream;base64,{b64}" download="relatorio_comparativo_pss.pdf">📥 Clique aqui para baixar o relatório comparativo PDF</a>'
                st.markdown(href, unsafe_allow_html=True)
                st.success("Relatório comparativo gerado com sucesso!")

    with st.expander("📋 Ver Tabelas de Contribuição (por ano)"):
        ano_tabela = st.selectbox("Selecione o ano para visualizar a tabela", options=AVAILABLE_YEARS, key="table_year")
        tabela_exibir = TABLES[ano_tabela]
        df_tabela = pd.DataFrame(tabela_exibir, columns=["Faixa inferior", "Faixa superior", "Alíquota"])
        df_tabela["Faixa inferior"] = df_tabela["Faixa inferior"].apply(formatar_moeda)
        df_tabela["Faixa superior"] = df_tabela["Faixa superior"].replace(float('inf'), "acima")
        df_tabela["Faixa superior"] = df_tabela["Faixa superior"].apply(lambda x: formatar_moeda(x) if x != "acima" else "acima")
        df_tabela["Alíquota"] = df_tabela["Alíquota"].apply(lambda x: f"{x*100:.2f}%")
        st.dataframe(df_tabela, use_container_width=True, hide_index=True)

# ------------------------------------------------------------------------------
# TAB 4: Abono de Permanência
# ------------------------------------------------------------------------------
with tab4:
    st.title("🧮 Calculadora de Reflexos do Abono de Permanência")
    st.markdown("Faça o upload do arquivo JSON gerado pelo sistema externo para preencher as bases de cálculo automaticamente.")

    uploaded_file = st.file_uploader("📂 Selecione o arquivo JSON (Abono)", type=["json"], key="upload_abono")

    if uploaded_file is not None:
        try:
            raw_data = json.load(uploaded_file)
            clean_data = clean_dict_keys(raw_data)

            st.session_state.abono_meta = clean_data.get('meta', {})
            st.session_state.abono_dados = clean_data.get('d', [])
            st.session_state.abono_idx = clean_data.get('idx', {})
            st.session_state.abono_data_loaded = True

            # Sincroniza com o sidebar se os campos estiverem vazios
            meta = st.session_state.abono_meta
            if meta.get('proc') and not st.session_state.processo_input:
                st.session_state.processo_input = meta.get('proc', '')
            if meta.get('aut') and not st.session_state.autor_input:
                st.session_state.autor_input = meta.get('aut', '')

            st.success(f"✅ Arquivo carregado com sucesso! Processo: `{st.session_state.abono_meta.get('proc', 'N/A')}`")
            st.rerun()

        except Exception as e:
            st.error(f"❌ Erro ao processar o arquivo JSON. Verifique o formato. Detalhe: {e}")
            st.session_state.abono_data_loaded = False

    st.divider()
    st.subheader("📋 Dados do Processo (Abono)")

    col1, col2, col3, col4 = st.columns(4)
    meta = st.session_state.abono_meta

    with col1:
        num_processo = st.text_input("Número do Processo", value=meta.get('proc', st.session_state.processo_input), key="abono_proc")
    with col2:
        nome_autor = st.text_input("Nome do Autor(a)", value=meta.get('aut', st.session_state.autor_input), key="abono_aut")
    with col3:
        data_aju = meta.get('aju', '2025-09-17')
        try:
            data_aju_dt = pd.to_datetime(data_aju).date()
        except:
            data_aju_dt = None
        data_aju_input = st.date_input("Data do Ajuizamento", value=data_aju_dt, key="abono_aju")
    with col4:
        st.text_input("Citação (Mês/Ano)", value=meta.get('cit', ''), disabled=True, key="abono_cit")

    st.divider()
    st.subheader("📊 Bases de Cálculo Mensais")

    if st.session_state.abono_data_loaded:
        st.info("💡 Os valores de **Base 1 (gratP)** e **Base 2 (gratD)** foram preenchidos pelo JSON. Você pode editá-los diretamente nas células abaixo, se necessário, antes de calcular.")

        df_list = []
        for item in st.session_state.abono_dados:
            df_list.append({
                "Competência": item.get('c', ''),
                "Abono": float(item.get('abono', 0)),
                "Base 1 (gratP - Pago)": float(item.get('gratP', 0)),
                "Base 2 (gratD - Devido)": float(item.get('gratD', 0)),
                "Férias Pagas (ferP)": float(item.get('ferP', 0)),
                "Férias Devidas (ferD)": float(item.get('ferD', 0)),
                "Habilitado": item.get('hab', False)
            })

        df = pd.DataFrame(df_list)

        column_config = {
            "Competência": st.column_config.TextColumn("Mês/Ano", disabled=True, width="small"),
            "Abono": st.column_config.NumberColumn("Abono", format="%.2f", disabled=True, width="small"),
            "Base 1 (gratP - Pago)": st.column_config.NumberColumn("Base 1 (gratP)", format="%.2f"),
            "Base 2 (gratD - Devido)": st.column_config.NumberColumn("Base 2 (gratD)", format="%.2f"),
            "Férias Pagas (ferP)": st.column_config.NumberColumn("Férias Pagas", format="%.2f", disabled=True),
            "Férias Devidas (ferD)": st.column_config.NumberColumn("Férias Devidas", format="%.2f", disabled=True),
            "Habilitado": st.column_config.CheckboxColumn("Habilitado", disabled=True, width="small")
        }

        edited_df = st.data_editor(
            df,
            column_config=column_config,
            use_container_width=True,
            hide_index=True,
            num_rows="fixed",
            key="abono_editor"
        )
        st.session_state.abono_edited_df = edited_df

    else:
        st.warning("⚠️ Nenhum dado carregado. Faça o upload do arquivo JSON acima.")
        edited_df = pd.DataFrame()

    st.divider()
    if st.button("🚀 EXECUTAR CÁLCULOS ABONO", type="primary", use_container_width=True, key="btn_calc_abono"):

        if not st.session_state.abono_data_loaded:
            st.warning("Por favor, carregue um arquivo JSON primeiro.")
        else:
            st.subheader("📈 Resultados do Cálculo")

            # =================================================================
            # 👉 ÁREA RESERVADA PARA A SUA LÓGICA MATEMÁTICA EXISTENTE 👈
            # =================================================================
            # Aqui você chama a sua função de cálculo. 
            # Ela receberá o 'edited_df' (que contém os valores do JSON, 
            # mesmo que você os tenha ajustado manualmente na tabela) 
            # e os índices em 'st.session_state.abono_idx'.
            #
            # EXEMPLO DE COMO INTEGRAR:
            # resultado_final = sua_funcao_de_calculo_existente(
            #     df=edited_df,
            #     indices=st.session_state.abono_idx,
            #     processo=num_processo,
            #     autor=nome_autor
            # )
            # st.write(resultado_final)
            # =================================================================

            # --- Demonstração Visual (substitua pela sua lógica) ---
            total_base1 = edited_df["Base 1 (gratP - Pago)"].sum()
            total_base2 = edited_df["Base 2 (gratD - Devido)"].sum()
            diferenca = total_base2 - total_base1

            col_res1, col_res2, col_res3 = st.columns(3)
            col_res1.metric("Soma Total Base 1 (Pago)", f"R$ {total_base1:,.2f}")
            col_res2.metric("Soma Total Base 2 (Devido)", f"R$ {total_base2:,.2f}")
            col_res3.metric("Diferença Bruta", f"R$ {diferenca:,.2f}", delta_color="normal")

            st.success("✅ Cálculo executado com sucesso utilizando os dados importados!")

st.markdown("---")
st.caption("Fonte: Portarias Interministeriais MPS/MF dos respectivos anos. Cálculo progressivo por faixas. | Módulo Abono de Permanência v1.0")
