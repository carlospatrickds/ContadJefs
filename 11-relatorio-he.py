import streamlit as st
import pdfplumber
import pandas as pd
import re
import os
import shutil
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER

# ------------------------------------------------------------
# Configurações do app
# ------------------------------------------------------------
st.set_page_config(page_title="Relatório Serviço Extraordinário", layout="wide")

# REGEX ATUALIZADA para aceitar uma letra maiúscula opcional ([A-Z]?) no final do processo
REGEX = re.compile(
    r"(\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4}[A-Z]?)\s+(\d{2}\/\d{2}\/\d{4})\s+(\d+)"
)

PASTA_MENSAL = "base_mensal"
os.makedirs(PASTA_MENSAL, exist_ok=True)

MESES_ANUAL = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
               "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]

# ------------------------------------------------------------
# Funções de Processamento
# ------------------------------------------------------------
def extrair_processos(pdf_file):
    dados = []
    with pdfplumber.open(pdf_file) as pdf:
        for page in pdf.pages:
            texto = page.extract_text()
            if not texto:
                continue
            encontrados = REGEX.findall(texto)
            for processo_bruto, data, seq in encontrados:
                
                # LIMPEZA: Remove a letra no final do processo (T, S, etc.), se existir.
                processo_limpo = re.sub(r'[A-Z]$', '', processo_bruto)
                
                dados.append({
                    "processo": processo_limpo,  # Usa o processo limpo
                    "data": pd.to_datetime(data, dayfirst=True),
                    "sequencial": int(seq)
                })
    return dados


# ------------------------------------------------------------
# Funções para salvar e carregar
# ------------------------------------------------------------
def salvar_mensal(mes_ano, df):
    caminho = os.path.join(PASTA_MENSAL, f"{mes_ano}.xlsx")
    df.to_excel(caminho, index=False)


def carregar_mensal(mes_ano):
    caminho = os.path.join(PASTA_MENSAL, f"{mes_ano}.xlsx")
    return pd.read_excel(caminho)


# ------------------------------------------------------------
# Função para gerar PDF (Melhorado com ReportLab Platypus/Table)
# ------------------------------------------------------------
def gerar_pdf(titulo, df, observacoes=""):
    buffer = BytesIO()
    styles = getSampleStyleSheet()
    
    # Estilo para parágrafos
    styles.add(ParagraphStyle(name='NormalLeft', alignment=TA_LEFT, fontSize=11, leading=14))
    styles.add(ParagraphStyle(name='TitleCenter', parent=styles['Heading1'], alignment=TA_CENTER, fontSize=16, spaceAfter=18))
    styles.add(ParagraphStyle(name='SubHeader', parent=styles['Heading2'], fontSize=12, spaceBefore=10, spaceAfter=5))
    
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=1.5*cm, rightMargin=1.5*cm, topMargin=1.5*cm, bottomMargin=1.5*cm)
    Story = []

    # 1. Título
    Story.append(Paragraph(titulo, styles['TitleCenter']))

    # 2. Observações (Acima das tabelas)
    if observacoes:
        Story.append(Paragraph("<b>Observações:</b>", styles['SubHeader']))
        for linha in observacoes.split('\n'):
            Story.append(Paragraph(linha, styles['NormalLeft']))
        Story.append(Paragraph("<br/>", styles['NormalLeft']))

    # 3. Tabela de Totais por Mês
    if 'mes' in df.columns:
        totais_mes = df.groupby("mes").size().reset_index(name='Total')
        
        # Ordena os meses para exibição
        meses_ordem = {m: i for i, m in enumerate(MESES_ANUAL)}
        totais_mes['order'] = totais_mes['mes'].map(meses_ordem)
        totais_mes = totais_mes.sort_values(by='order').drop(columns='order')
        
        dados_tabela = [["Mês", "Total de Processos"]]
        for _, row in totais_mes.iterrows():
            dados_tabela.append([row['mes'], str(row['Total'])])

        # Total Geral
        dados_tabela.append(['<b>Total Geral</b>', f'<b>{len(df)}</b>'])
        
        Story.append(Paragraph("<b>Totais de Processos por Mês:</b>", styles['SubHeader']))
        
        t = Table(dados_tabela, colWidths=[6.5*cm, 6.5*cm])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('BACKGROUND', (0, -1), (-1, -1), colors.lightgrey),
        ]))
        Story.append(t)
        Story.append(Paragraph("<br/>", styles['NormalLeft']))

    # 4. Lista de Processos (Ordenada Cronologicamente)
    Story.append(Paragraph("<b>Lista detalhada de processos (Ordem Cronológica):</b>", styles['SubHeader']))
    
    # Garante a ordem cronológica
    df['data_dt'] = pd.to_datetime(df['data'], format='%d/%m/%Y')
    df = df.sort_values(by=['data_dt', 'processo'])
    df = df.drop(columns='data_dt')
    
    # Recria o sequencial (1 a N) após a ordenação
    df.insert(0, "nº", (df.reset_index(drop=True).index + 1).astype(str))
    
    for index, row in df.iterrows():
        # Retira o nº sequencial do dataframe se for 'Relatório Mensal'
        n_sequencial = f"{row['nº']}."
        
        # Novo formato: 1. PROCESSO — 08/11/2025
        texto = f"{n_sequencial} {row['processo']} — {row['data']}"
        Story.append(Paragraph(texto, styles['NormalLeft']))
        
    doc.build(Story)
    buffer.seek(0)
    return buffer


# ============================================================
#                         INTERFACE DO APP
# ============================================================
aba = st.sidebar.radio("Menu", ["Upload de Múltiplos Meses", "Relatório mensal", "Consolidado geral"])

# ------------------------------------------------------------
# 1) UPLOAD MENSAL MELHORADO
# ------------------------------------------------------------
if aba == "Upload de Múltiplos Meses":
    st.header("📁 Upload dos PDFs por Mês/Ano")
    st.info("Selecione o ano e, em seguida, arraste o PDF de cada mês para a caixa correspondente. Apenas os meses com arquivos enviados serão processados.")
    
    ano = st.number_input("Ano dos relatórios:", min_value=2020, max_value=2035, value=2025)

    colunas = st.columns(3)
    arquivos_enviados = {}

    for i, mes in enumerate(MESES_ANUAL):
        with colunas[i % 3]:
            st.markdown(f"**{mes}**")
            arquivo = st.file_uploader(f"PDF de {mes}/{ano}", type=["pdf"], accept_multiple_files=False, key=mes)
            if arquivo:
                arquivos_enviados[mes] = arquivo

    if arquivos_enviados:
        st.subheader("Processando Arquivos...")
        
        # Botão único para processar
        if st.button("Processar e Salvar Meses"):
            total_processado = 0
            for mes, arq in arquivos_enviados.items():
                mes_ano = f"{mes}_{ano}"
                lista = []
                
                dados = extrair_processos(arq)
                if dados:
                    for d in dados:
                        d["arquivo_origem"] = arq.name
                        lista.append(d)

                    if lista:
                        df = pd.DataFrame(lista)
                        df["data"] = df["data"].dt.strftime("%d/%m/%Y")
                        df = df.drop(columns=["sequencial"])

                        # Cria a coluna 'nº' apenas para fins internos, não é usada no PDF final
                        df.insert(0, "nº", (df.reset_index().index + 1).astype(str).str.zfill(2))

                        salvar_mensal(mes_ano, df)
                        st.success(f"✅ {mes_ano} salvo: {len(df)} processos.")
                        total_processado += len(df)
                    else:
                        st.warning(f"⚠️ {mes_ano}: Nenhum processo encontrado no PDF.")
            
            if total_processado > 0:
                 st.balloons()
                 st.success(f"Processamento concluído! Total de {total_processado} processos salvos.")
            else:
                 st.warning("Nenhum processo foi salvo.")


# ------------------------------------------------------------
# 2) RELATÓRIO MENSAL
# ------------------------------------------------------------
elif aba == "Relatório mensal":
    st.header("📊 Relatório mensal")

    arquivos_mensais = sorted([f.replace(".xlsx", "") for f in os.listdir(PASTA_MENSAL)])

    if not arquivos_mensais:
        st.warning("Nenhum mês encontrado. Utilize o 'Upload de Múltiplos Meses' primeiro.")
    else:
        mes_ano = st.selectbox("Selecione o mês:", arquivos_mensais)
        df = carregar_mensal(mes_ano)

        st.subheader(f"📌 Resumo de {mes_ano}")
        st.write(f"**Total:** {len(df)} processos")

        total_por_data = df.groupby("data").size().reset_index(name='Quantidade')
        st.table(total_por_data)
        
        st.subheader("Observações")
        observacoes = st.text_area("Digite informações adicionais para o relatório mensal:")

        pdf_buffer = gerar_pdf(f"Relatório Mensal — {mes_ano}", df, observacoes)
        
        st.download_button(
            "📄 Baixar PDF",
            data=pdf_buffer,
            file_name=f"Relatorio_{mes_ano}.pdf",
            mime="application/pdf"
        )
        
        st.subheader("Tabela completa")
        st.dataframe(df, height=300)

        st.subheader("🧹 Ferramentas de limpeza")
        col1, col2 = st.columns(2)

        if col1.button(f"Apagar {mes_ano}"):
            caminho = os.path.join(PASTA_MENSAL, f"{mes_ano}.xlsx")
            os.remove(caminho)
            st.success(f"{mes_ano} apagado. Recarregue a página.")
            st.stop()

        if col2.button("Apagar TODOS os meses"):
            shutil.rmtree(PASTA_MENSAL)
            os.makedirs(PASTA_MENSAL, exist_ok=True)
            st.success("Todos os meses foram apagados. Recarregue a página.")
            st.stop()


# ------------------------------------------------------------
# 3) CONSOLIDADO GERAL
# ------------------------------------------------------------
elif aba == "Consolidado geral":
    st.header("📑 Relatório Consolidado")

    arquivos = os.listdir(PASTA_MENSAL)
    if not arquivos:
        st.warning("Nenhum mês encontrado. Utilize o 'Upload de Múltiplos Meses' primeiro.")
    else:
        lista = []
        for arquivo in arquivos:
            mes_ano = arquivo.replace(".xlsx", "")
            df = carregar_mensal(mes_ano)
            df["mes"] = mes_ano
            lista.append(df)

        df_final = pd.concat(lista)
        
        st.subheader("Observações")
        obs_geral = st.text_area("Digite observações gerais para o consolidado:")

        pdf_buffer = gerar_pdf("Relatório Consolidado", df_final, obs_geral)
        
        st.download_button(
            "📄 Baixar PDF Consolidado",
            data=pdf_buffer,
            file_name="Relatorio_Consolidado.pdf",
            mime="application/pdf"
        )

        st.subheader("Totais por mês")
        st.table(df_final.groupby("mes").size())

        st.subheader("Total geral")
        st.write(f"**{len(df_final)} processos**")

        st.subheader("Tabela completa")
        st.dataframe(df_final, height=400)

        st.subheader("🧹 Limpeza")
        if st.button("Apagar TODOS os meses"):
            shutil.rmtree(PASTA_MENSAL)
            os.makedirs(PASTA_MENSAL, exist_ok=True)
            st.success("Todos os meses foram apagados. Recarregue a página.")
            st.stop()
