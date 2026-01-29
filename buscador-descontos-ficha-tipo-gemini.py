# ===== IMPORTAÇÕES =====
import streamlit as st
import pandas as pd
import pdfplumber
import re
from datetime import datetime
import io
from typing import Optional
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm

# ===== REGRAS DE AGRUPAMENTO =====
GRUPOS_RUBRICAS = {
    "Empréstimos": ["EMPRÉSTIMO", "EMPRESTIMO", "CONSING", "CDC"],
    "Imposto de Renda": ["IMPOSTO DE RENDA", "IRRF", "IR"],
    "Previdência": ["PREVID", "INSS", "PSS"],
    "Plano de Saúde": ["SAÚDE", "UNIMED", "AMIL"]
}

# ===== CLASSE PRINCIPAL =====
class ExtratorDemonstrativos:

    def identificar_grupo(self, descricao: str) -> str:
        desc = descricao.upper()
        for grupo, palavras in GRUPOS_RUBRICAS.items():
            if any(p in desc for p in palavras):
                return grupo
        return "Outros"

    def converter_valor_string(self, valor_str: str) -> Optional[float]:
        try:
            valor_str = re.sub(r'[^\d,\.]', '', str(valor_str))
            return float(valor_str.replace('.', '').replace(',', '.'))
        except:
            return None

    def processar_pdf(self, pdf_file) -> pd.DataFrame:
        dados = []

        with pdfplumber.open(pdf_file) as pdf:
            for pagina_num, pagina in enumerate(pdf.pages, 1):
                texto = pagina.extract_text()
                if not texto:
                    continue

                ano_match = re.search(r'ANO\s+REFER[EÊ]NCIA\s*[:\s]*(\d{4})', texto, re.I)
                if not ano_match:
                    continue
                ano = ano_match.group(1)

                tabelas = pagina.extract_tables()
                for tabela in tabelas:
                    for linha in tabela:
                        if not linha or len(linha) < 2:
                            continue

                        descricao = str(linha[0]).strip()
                        valor = self.converter_valor_string(linha[-1])

                        if descricao and valor:
                            dados.append({
                                "Discriminacao": descricao,
                                "Valor_float": valor,
                                "Ano": ano,
                                "Pagina": pagina_num,
                                "Grupo": self.identificar_grupo(descricao)
                            })

        df = pd.DataFrame(dados)
        return df

# ===== GERADOR DE PDF =====
def gerar_pdf_relatorio(df: pd.DataFrame, nome_arquivo: str) -> bytes:
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    largura, altura = A4

    y = altura - 2 * cm
    c.setFont("Helvetica-Bold", 16)
    c.drawString(2 * cm, y, "RELATÓRIO DE DEMONSTRATIVOS FINANCEIROS")

    y -= 1 * cm
    c.setFont("Helvetica", 10)
    c.drawString(2 * cm, y, f"Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M')}")

    y -= 1.5 * cm
    c.setFont("Helvetica-Bold", 12)
    c.drawString(2 * cm, y, "Resumo por Grupo")

    y -= 0.8 * cm
    c.setFont("Helvetica", 10)

    resumo = df.groupby("Grupo")["Valor_float"].sum().reset_index()

    for _, row in resumo.iterrows():
        c.drawString(2 * cm, y, f"{row['Grupo']}: R$ {row['Valor_float']:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
        y -= 0.6 * cm
        if y < 2 * cm:
            c.showPage()
            y = altura - 2 * cm

    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer.read()

# ===== STREAMLIT =====
def main():
    st.set_page_config("Extrator Financeiro", "📊", layout="wide")
    st.title("📊 Extrator Inteligente de Demonstrativos")

    extrator = ExtratorDemonstrativos()
    pdf = st.file_uploader("Envie o PDF", type="pdf")

    if pdf and st.button("Processar"):
        df = extrator.processar_pdf(pdf)

        if df.empty:
            st.error("Nenhum dado encontrado.")
            return

        st.success("Extração concluída")
        st.dataframe(df, use_container_width=True)

        st.subheader("📌 Totais por Grupo")
        st.dataframe(df.groupby("Grupo")["Valor_float"].sum().reset_index())

        if st.button("📄 Gerar Relatório PDF"):
            pdf_bytes = gerar_pdf_relatorio(df, pdf.name)
            st.download_button(
                "⬇️ Baixar Relatório PDF",
                pdf_bytes,
                file_name="relatorio_demonstrativos.pdf",
                mime="application/pdf"
            )

if __name__ == "__main__":
    main()

