import streamlit as st
import pandas as pd
import pdfplumber
import re
from datetime import datetime
import io
import unicodedata
from unidecode import unidecode

# PDF relatório
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors

# =========================
# CLASSE PRINCIPAL
# =========================
class ExtratorDemonstrativos:

    def __init__(self):
        self.meses_map = {
            'JAN': 1, 'JANEIRO': 1,
            'FEV': 2, 'FEVEREIRO': 2,
            'MAR': 3, 'MARÇO': 3,
            'ABR': 4, 'ABRIL': 4,
            'MAI': 5, 'MAIO': 5,
            'JUN': 6, 'JUNHO': 6,
            'JUL': 7, 'JULHO': 7,
            'AGO': 8, 'AGOSTO': 8,
            'SET': 9, 'SETEMBRO': 9,
            'OUT': 10, 'OUTUBRO': 10,
            'NOV': 11, 'NOVEMBRO': 11,
            'DEZ': 12, 'DEZEMBRO': 12
        }

    # -------------------------
    # CORREÇÃO DE TEXTO PDF
    # -------------------------
    def corrigir_texto_pdf(self, texto: str) -> str:
        if not texto:
            return texto

        texto = str(texto).strip()

        try:
            texto = texto.encode("latin1").decode("utf-8")
        except:
            pass

        texto = unicodedata.normalize("NFKC", texto)

        if re.search(r"[Ã�]", texto):
            texto = unidecode(texto)

        texto = re.sub(r"\s+", " ", texto)

        return texto.upper()

    # -------------------------
    # AGRUPAMENTO INTELIGENTE
    # -------------------------
    def mapear_grupo_rubrica(self, descricao: str) -> str:
        desc = descricao.upper()

        grupos = {
            "EMPRÉSTIMOS / CARTÕES": [
                "EMPREST", "EMPRÉST", "CARTAO", "CARTÃO", "CREDITO", "CRÉDITO", "BCO", "BANCO"
            ],
            "IMPOSTOS": [
                "IR", "IMPOSTO"
            ],
            "CONTRIBUIÇÕES": [
                "INSS", "PREVID", "FUNPRESP", "PENSÃO"
            ],
            "ASSISTÊNCIA / PLANOS": [
                "PLANO", "SAUDE", "ODONTO", "SEGURO"
            ],
            "PROVENTOS": [
                "VENC", "SALARIO", "SALÁRIO", "REMUN", "PROVENTO"
            ]
        }

        for grupo, chaves in grupos.items():
            if any(ch in desc for ch in chaves):
                return grupo

        return "OUTROS"

    # -------------------------
    # VALORES
    # -------------------------
    def converter_valor_string(self, valor_str):
        try:
            valor_str = re.sub(r"[^\d,\.]", "", str(valor_str))
            return float(valor_str.replace(".", "").replace(",", "."))
        except:
            return None

    def formatar_valor(self, valor):
        return f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    # -------------------------
    # PROCESSAMENTO PDF
    # -------------------------
    def processar_pdf(self, pdf_file):
        dados = []

        with pdfplumber.open(pdf_file) as pdf:
            for pagina_num, pagina in enumerate(pdf.pages, 1):
                texto = pagina.extract_text()
                if not texto or "DEMONSTRATIVO" not in texto.upper():
                    continue

                tabelas = pagina.extract_tables()
                if not tabelas:
                    continue

                for tabela in tabelas:
                    for linha in tabela:
                        if not linha:
                            continue

                        descricao = linha[0]
                        if not descricao:
                            continue

                        descricao = self.corrigir_texto_pdf(descricao)
                        grupo = self.mapear_grupo_rubrica(descricao)

                        for i, cell in enumerate(linha[1:], 1):
                            valor = self.converter_valor_string(cell)
                            if valor and valor != 0:
                                dados.append({
                                    "Grupo": grupo,
                                    "Discriminacao": descricao,
                                    "Valor": self.formatar_valor(valor),
                                    "Valor_Numerico": valor,
                                    "Pagina": pagina_num
                                })

        return pd.DataFrame(dados)


# =========================
# PDF RELATÓRIO
# =========================
def gerar_relatorio_pdf(df, caminho):
    doc = SimpleDocTemplate(caminho, pagesize=A4)
    styles = getSampleStyleSheet()
    elementos = []

    elementos.append(Paragraph("<b>RELATÓRIO FINANCEIRO</b>", styles["Title"]))
    elementos.append(Spacer(1, 12))

    resumo = df.groupby("Grupo")["Valor_Numerico"].sum().reset_index()

    for _, row in resumo.iterrows():
        elementos.append(Paragraph(
            f"<b>{row['Grupo']}</b>: R$ {row['Valor_Numerico']:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
            styles["Normal"]
        ))
        elementos.append(Spacer(1, 8))

    doc.build(elementos)


# =========================
# STREAMLIT APP
# =========================
def main():
    st.set_page_config(page_title="Extrator Financeiro", layout="wide")

    st.markdown("""
    <style>
    .stApp { background-color: #F4F6F7; }
    h1 { color: #1F618D; }
    .stButton>button {
        background-color: #1F618D;
        color: white;
        border-radius: 8px;
        font-weight: bold;
    }
    </style>
    """, unsafe_allow_html=True)

    st.title("📊 Extrator de Demonstrativos Financeiros")

    uploaded = st.file_uploader("📁 Envie o PDF", type="pdf")

    if uploaded:
        extrator = ExtratorDemonstrativos()
        df = extrator.processar_pdf(uploaded)

        if df.empty:
            st.error("Nenhum dado encontrado.")
            return

        st.success(f"{len(df)} registros extraídos")

        st.dataframe(df, use_container_width=True)

        st.subheader("📥 Exportações")

        csv = df.to_csv(index=False, sep=";", encoding="utf-8-sig")
        st.download_button("⬇️ Baixar CSV", csv, "dados.csv", "text/csv")

        excel = io.BytesIO()
        with pd.ExcelWriter(excel, engine="openpyxl") as writer:
            df.to_excel(writer, index=False)
        excel.seek(0)
        st.download_button("⬇️ Baixar Excel", excel, "dados.xlsx")

        if st.button("📄 Gerar Relatório PDF"):
            caminho = "relatorio.pdf"
            gerar_relatorio_pdf(df, caminho)
            with open(caminho, "rb") as f:
                st.download_button("⬇️ Baixar PDF", f, "relatorio.pdf", "application/pdf")


if __name__ == "__main__":
    main()
