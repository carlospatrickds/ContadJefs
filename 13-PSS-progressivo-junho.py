import streamlit as st
import pandas as pd
from fpdf import FPDF
import base64
import json
from datetime import datetime

# -----------------------------------------------------------------------------
# CONFIGURAÇÕES E TEMAS
# -----------------------------------------------------------------------------
THEMES = {
    "Salmão": {
        "th_bg": (255, 197, 153),
        "header_bg": (255, 236, 217),
        "divider": (190, 80, 20),
        "css": """<style>:root {--primary: #4d2916; --th-bg: #FFC599; --divider-color: #BE5014; --info: #692a08; --header-bg: #ffecd9;} th { color: #000 !important; border-color: #dca377 !important; background-color: var(--th-bg) !important; } .header-row { color: #000 !important; border-color: #FFC599 !important; background-color: var(--header-bg) !important; }</style>"""
    },
    "Clássico (Azul/Cinza)": {
        "th_bg": (245, 245, 245),
        "header_bg": (208, 211, 212),
        "divider": (127, 140, 141),
        "css": """<style>:root {--primary: #585a5a; --th-bg: #f5f5f5; --divider-color: #7f8c8d; --info: #585a5a; --header-bg: #d0d3d4;} th { color: #000 !important; border-color: #7f8c8d !important; background-color: var(--th-bg) !important; } .header-row { color: #000 !important; border-color: #7f8c8d !important; background-color: var(--header-bg) !important; }</style>"""
    }
}

TABLES = {
    2020: [(0.00, 1045.00, 0.075), (1045.01, 2000.00, 0.09), (2000.01, 3000.00, 0.12), (3000.01, 5839.45, 0.14), (5839.46, 10000.00, 0.145), (10000.01, 20000.00, 0.165), (20000.01, 39000.00, 0.19), (39000.01, float('inf'), 0.22)],
    2021: [(0.00, 1100.00, 0.075), (1100.01, 2203.48, 0.09), (2203.49, 3305.22, 0.12), (3305.23, 6433.57, 0.14), (6433.58, 11017.42, 0.145), (11017.43, 22034.83, 0.165), (22034.84, 42967.92, 0.19), (42967.93, float('inf'), 0.22)],
    2022: [(0.00, 1212.00, 0.075), (1212.01, 2427.35, 0.09), (2427.36, 3641.03, 0.12), (3641.04, 7087.22, 0.14), (7087.23, 12136.79, 0.145), (12136.80, 24273.57, 0.165), (24273.58, 47333.46, 0.19), (47333.47, float('inf'), 0.22)],
    2023: [(0.00, 1302.00, 0.075), (1302.01, 2571.29, 0.09), (2571.30, 3856.94, 0.12), (3856.95, 7507.49, 0.14), (7507.50, 12856.50, 0.145), (12856.51, 25712.99, 0.165), (25713.00, 50140.33, 0.19), (50140.34, float('inf'), 0.22)],
    2024: [(0.00, 1412.00, 0.075), (1412.01, 2666.68, 0.09), (2666.69, 4000.03, 0.12), (4000.04, 7786.02, 0.14), (7786.03, 13333.48, 0.145), (13333.49, 26666.94, 0.165), (26666.95, 52000.54, 0.19), (52000.55, float('inf'), 0.22)],
    2025: [(0.00, 1518.00, 0.075), (1518.01, 2793.88, 0.09), (2793.89, 4190.83, 0.12), (4190.84, 8157.41, 0.14), (8157.42, 13969.49, 0.145), (13969.50, 27938.95, 0.165), (27938.96, 54480.97, 0.19), (54480.98, float('inf'), 0.22)],
    2026: [(0.00, 1621.00, 0.075), (1621.01, 2902.84, 0.09), (2902.85, 4354.27, 0.12), (4354.28, 8475.55, 0.14), (8475.56, 14514.30, 0.145), (14514.31, 29028.57, 0.165), (29028.58, 56605.73, 0.19), (56605.74, float('inf'), 0.22)],
}
AVAILABLE_YEARS = sorted(TABLES.keys())

# -----------------------------------------------------------------------------
# FUNÇÕES AUXILIARES
# -----------------------------------------------------------------------------
def parse_valor(v_str):
    if isinstance(v_str, float): return v_str
    v_str = str(v_str).strip().replace('R$', '').strip()
    if ',' in v_str: v_str = v_str.replace('.', '').replace(',', '.')
    try: return float(v_str)
    except: return 0.0

def formatar_moeda(valor):
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def calcular_contribuicao_progressiva(salario, tabela):
    if salario <= 0: return 0.0, []
    restante, total, detalhamento = salario, 0.0, []
    for i, (lim_inf, lim_sup, aliquota) in enumerate(tabela):
        if restante <= 0: break
        tributavel = min(restante, lim_sup - lim_inf) if i > 0 and lim_sup != float('inf') else min(restante, lim_sup)
        if i > 0 and lim_sup == float('inf'): tributavel = restante
        if tributavel > 0:
            contrib = tributavel * aliquota
            total += contrib
            detalhamento.append({"faixa": f"{formatar_moeda(lim_inf)} - {formatar_moeda(lim_sup) if lim_sup != float('inf') else 'acima'}", "base": tributavel, "aliquota": f"{aliquota*100:.2f}%", "contribuicao": contrib})
            restante -= tributavel
    return total, detalhamento

# -----------------------------------------------------------------------------
# INTERFACE E LÓGICA PRINCIPAL
# -----------------------------------------------------------------------------
st.set_page_config(page_title="Calculadora PSS", layout="wide")

# Inicialização do estado
if 'processo_input' not in st.session_state: st.session_state.processo_input = ""
if 'autor_input' not in st.session_state: st.session_state.autor_input = ""
if 'observacao_input' not in st.session_state: st.session_state.observacao_input = ""

with st.sidebar:
    st.header("🎨 Tema Visual")
    tema_ativo = THEMES[st.radio("Escolha o tema:", ["Salmão", "Clássico (Azul/Cinza)"])]
    st.markdown(tema_ativo["css"], unsafe_allow_html=True)
    
    st.header("Informações")
    st.text_input("Processo", key="processo_input")
    st.text_input("Autor", key="autor_input")
    st.text_area("Observações", key="observacao_input")

    st.header("📂 Importar/Exportar")
    # Importar estado do programa
    up_state = st.file_uploader("Restaurar sessão (.json)", type=["json"], key="up_state")
    if up_state and st.button("Restaurar"):
        d = json.load(up_state)
        for k, v in d.items(): st.session_state[k] = v
        st.rerun()
    
    # Exportar estado do programa
    nome_exp = f"CALC_PSS_{datetime.now().strftime('%d%m%Y%H%M%S')}.json"
    st.download_button("📥 Exportar Sessão", data=json.dumps(dict(st.session_state)), file_name=nome_exp)

st.title("📊 Calculadora PSS")

# TAB 3 (Onde entra sua lógica de importação do JSON externo)
tab1, tab2, tab3 = st.tabs(["Cálculo", "Relatório", "Comparação"])
with tab3:
    st.subheader("Comparação de Bases")
    ext_json = st.file_uploader("Carregar JSON de cálculo externo", type=["json"])
    if ext_json and st.button("Processar JSON de Cálculo"):
        dados = json.load(ext_json)
        st.session_state.processo_input = dados.get("meta", {}).get("proc", "")
        st.session_state.autor_input = dados.get("meta", {}).get("aut", "")
        
        mapa = {}
        for item in dados.get("d", []):
            ano = item.get("c", "").split("/")[1]
            mapa.setdefault(ano, {"p": 0.0, "d": 0.0})
            mapa[ano]["p"] += float(item.get("gratP", 0))
            mapa[ano]["d"] += float(item.get("gratD", 0))
        
        for ano in AVAILABLE_YEARS:
            if str(ano) in mapa:
                st.session_state[f"comp_base1_{ano}"] = f"{mapa[str(ano)]['p']:,.2f}"
                st.session_state[f"comp_base2_{ano}"] = f"{mapa[str(ano)]['d']:,.2f}"
        st.success("Dados preenchidos!")

    cols = st.columns(2)
    bases = {}
    for i, ano in enumerate(AVAILABLE_YEARS):
        bases[f"base1_{ano}"] = parse_valor(st.text_input(f"{ano} (Base 1)", key=f"comp_base1_{ano}"))
        bases[f"base2_{ano}"] = parse_valor(st.text_input(f"{ano} (Base 2)", key=f"comp_base2_{ano}"))
