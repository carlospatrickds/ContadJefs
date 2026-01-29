# app.py
# Extrator de Rubricas – Ficha Financeira SIAPE
import streamlit as st
import pdfplumber
import pandas as pd
import re
from io import BytesIO
import unicodedata

MESES = {
    "JAN": "01", "FEV": "02", "MAR": "03", "ABR": "04",
    "MAI": "05", "JUN": "06", "JUL": "07", "AGO": "08",
    "SET": "09", "OUT": "10", "NOV": "11", "DEZ": "12"
}

VALOR_RE = re.compile(r"\d{1,3}(?:\.\d{3})*,\d{2}")
INICIO_FICHA_RE = re.compile(r"Siape - Sistema Integrado de Administracao de Recursos Humanos", re.IGNORECASE)
FIM_FICHA_RE = re.compile(r"TOTAL\s+L[IÍ]QUIDO", re.IGNORECASE)
ANO_RE = re.compile(r"Ficha Financeira referente a:\s*(\d{4})", re.IGNORECASE)

st.set_page_config(page_title="Extrator de Rubricas – SIAPE", layout="wide")
st.title("📊 Extrator de Rubricas – Ficha Financeira SIAPE")

pdf_file = st.file_uploader("Envie o PDF da Ficha Financeira", type="pdf")

def fix_mojibake(s: str) -> str:
    """
    Tenta corrigir casos comuns de 'mojibake' onde bytes UTF-8 foram
    interpretados como Latin1/CP1252 (por exemplo 'é' -> 'Ã©').

    Estratégia:
    - Tenta s.encode('latin1').decode('utf-8') (corrige o caso clássico).
    - Normaliza com Unicode NFC.
    - Como fallback retorna a string original.
    """
    if not isinstance(s, str) or not s:
        return s
    fixed = s
    try:
        # Caso comum: bytes UTF-8 interpretados como latin1 -> string com 'Ã©'
        candidate = s.encode("latin1").decode("utf-8")
        # Heurística simples: se a versão corrigida contém mais caracteres acentuados plausíveis,
        # usamos a corrigida. (Evita aplicar quando não era necessário)
        if sum(1 for ch in candidate if ord(ch) > 127) >= sum(1 for ch in s if ord(ch) > 127):
            fixed = candidate
    except Exception:
        fixed = s

    try:
        fixed = unicodedata.normalize("NFC", fixed)
    except Exception:
        pass

    return fixed

@st.cache_data(show_spinner=False)
def extrair_dados(pdf_bytes):
    registros = []

    with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            texto = page.extract_text() or ""
            linhas = texto.split("\n")

            i = 0
            while i < len(linhas):
                if not INICIO_FICHA_RE.search(linhas[i]):
                    i += 1
                    continue

                bloco = []
                i += 1
                while i < len(linhas) and not FIM_FICHA_RE.search(linhas[i]):
                    bloco.append(linhas[i])
                    i += 1

                bloco_texto = "\n".join(bloco)
                ano_match = ANO_RE.search(bloco_texto)
                if not ano_match:
                    continue
                ano = ano_match.group(1)

                linhas_bloco = bloco_texto.split("\n")
                cabecalho_idx = None
                for idx, linha in enumerate(linhas_bloco):
                    if linha.strip().startswith("Rubrica|"):
                        cabecalho_idx = idx
                        break
                
                if cabecalho_idx is None:
                    continue

                cabecalho_cols = [c.strip() for c in linhas_bloco[cabecalho_idx].split("|")]
                meses_encontrados = [c for c in cabecalho_cols if c in MESES]
                
                if not meses_encontrados:
                    continue
                    
                primeira_col_mes = cabecalho_cols.index(meses_encontrados[0])

                for linha in linhas_bloco[cabecalho_idx + 1:]:
                    if FIM_FICHA_RE.search(linha):
                        break

                    colunas = [c.strip() for c in linha.split("|")]
                    if len(colunas) <= primeira_col_mes:
                        continue

                    codigo = colunas[0]
                    rubrica = colunas[1]
                    
                    # Corrige possíveis mojibakes/encoding problems de forma segura
                    rubrica = fix_mojibake(rubrica)
                    
                    tipo_rd = colunas[2]
                    valores_mes = colunas[primeira_col_mes:primeira_col_mes + len(meses_encontrados)]

                    for mes, celula in zip(meses_encontrados, valores_mes):
                        m = VALOR_RE.search(celula)
                        if not m:
                            continue

                        competencia = f"{MESES[mes]}/{ano}"

                        registros.append({
                            "Codigo": codigo,
                            "Rubrica": rubrica,
                            "Tipo": "Receita" if "R" in tipo_rd.upper() else "Despesa",
                            "Competencia": competencia,
                            "Valor": f"R$ {m.group(0)}",
                            "Pagina": page_num
                        })
                i += 1

    return pd.DataFrame(registros)

if pdf_file:
    with st.spinner("Processando PDF..."):
        df = extrair_dados(pdf_file.read())

    if df.empty:
        st.warning("Nenhum dado encontrado.")
    else:
        st.success(f"{len(df)} registros extraídos.")

        st.subheader("🔎 Filtros")
        col1, col2 = st.columns(2)
        with col1:
            tipos = st.multiselect(
                "Tipo de rubrica",
                ["Receita", "Despesa"],
                default=["Receita", "Despesa"]
            )
        with col2:
            rubricas_disponiveis = sorted(df["Rubrica"].unique())
            rubricas_sel = st.multiselect(
                "Selecione as rubricas",
                rubricas_disponiveis,
                default=rubricas_disponiveis
            )

        df_filtro = df[df["Tipo"].isin(tipos)]
        df_filtro = df_filtro[df_filtro["Rubrica"].isin(rubricas_sel)]

        st.dataframe(df_filtro, use_container_width=True)

        st.subheader("📤 Exportação")
        # Usar CP1252 (Windows-1252) para melhor compatibilidade ao abrir no Excel no Windows.
        # Alternativa: manter utf-8-sig e importar explicitamente no Excel como UTF-8.
        csv = df_filtro.to_csv(index=False, sep=";", encoding="cp1252")

        st.download_button(
            "📥 Baixar CSV filtrado",
            data=csv,
            file_name="rubricas_siape_filtradas.csv",
            mime="text/csv; charset=cp1252"
        )
