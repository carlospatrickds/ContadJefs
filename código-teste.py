# app_streamlit_melhorado.py
import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta
import io
import altair as alt
from fpdf import FPDF
import base64
import tempfile
import os

# ReportLab para o PDF de filtros (tabelas com destaque)
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm

# --- CONFIGURAÇÕES E CSS ---

st.set_page_config(
    page_title="Gestão de Processos Judiciais Unificada",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    .main-header {
        text-align: center;
        padding: 1rem 0;
        border-bottom: 2px solid #e0e0e0;
        margin-bottom: 2rem;
    }
    .stat-card {
        background-color: #f8f9fa;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #007bff;
        margin-bottom: 1rem;
    }
    .upload-section {
        border: 2px dashed #dee2e6;
        border-radius: 0.5rem;
        padding: 2rem;
        text-align: center;
        margin-bottom: 2rem;
    }
    .assunto-completo {
        white-space: normal !important;
        max-width: 300px;
    }
</style>
""", unsafe_allow_html=True)

# --- LISTA FIXA DE SERVIDORES ---
SERVIDORES_DISPONIVEIS = [
    "Servidor 01",
    "Servidor 02",
    "Servidor 03",
    "Servidor 04",
    "Servidor 05",
    "Servidor 06",
    "Servidor 07 - ES",
    "Servidor 09 - ES",
    "Supervisão 08"
]

# --- MAPA DE COLUNAS UNIFICADO ---
COLUNA_MAP = {
    'NUMERO_PROCESSO': ['Número do Processo', 'numeroProcesso', 'Nº Processo'], 
    'POLO_ATIVO': ['Polo Ativo', 'poloAtivo'],
    'POLO_PASSIVO': ['Polo Passivo', 'poloPassivo'],
    'ORGAO_JULGADOR': ['Órgão Julgador', 'orgaoJulgador', 'Vara'], 
    'ASSUNTO_PRINCIPAL': ['Assunto', 'assuntoPrincipal', 'Assunto Principal'], 
    'TAREFA': ['Tarefa', 'nomeTarefa'],
    'ETIQUETAS': ['Etiquetas', 'tagsProcessoList'],
    'DIAS_TRANSCORRIDOS': ['Dias'],
    'DATA_ULTIMO_MOVIMENTO_RAW': ['Data Último Movimento'], 
    'DATA_CHEGADA_RAW': ['dataChegada'], 
    'DATA_CHEGADA_FORMATADA_INPUT': ['Data Chegada'] 
}

# --- FUNÇÕES AUXILIARES ---

def get_local_time():
    """Obtém o horário local do Brasil (UTC-3)"""
    utc_now = datetime.now(timezone.utc)
    brasil_tz = timezone(timedelta(hours=-3))
    return utc_now.astimezone(brasil_tz)

def mapear_e_padronizar_colunas(df: pd.DataFrame) -> pd.DataFrame:
    """Renomeia as colunas do DataFrame para um padrão único."""
    colunas_padronizadas = {}
    for padrao, possiveis in COLUNA_MAP.items():
        coluna_encontrada = next((col for col in possiveis if col in df.columns), None)
        if coluna_encontrada:
            colunas_padronizadas[coluna_encontrada] = padrao
    df.rename(columns=colunas_padronizadas, inplace=True)
    return df

def processar_dados(df):
    """Processa os dados do CSV, usando APENAS nomes de colunas padronizados."""
    processed_df = df.copy()

    # Garante que NUMERO_PROCESSO seja string (evita truncamento/transformação)
    if 'NUMERO_PROCESSO' in processed_df.columns:
        processed_df['NUMERO_PROCESSO'] = processed_df['NUMERO_PROCESSO'].astype(str).str.strip().fillna('')

    if 'ETIQUETAS' not in processed_df.columns:
        processed_df['ETIQUETAS'] = "Sem etiqueta"

    # --- Extrair servidor / vara de etiquetas ---
    def extrair_servidor(tags):
        if pd.isna(tags):
            return "Sem etiqueta"
        tags_list = str(tags).split(', ')
        for tag in tags_list:
            if tag in SERVIDORES_DISPONIVEIS:
                return tag
            if 'Servidor' in tag or 'Supervisão' in tag:
                return tag
        return "Não atribuído"

    def extrair_vara(tags):
        if pd.isna(tags):
            return "Vara não identificada"
        tags_list = str(tags).split(', ')
        for tag in tags_list:
            if 'Vara Federal' in tag or 'Vara' in tag:
                return tag
        return "Vara não identificada"

    processed_df['servidor'] = processed_df['ETIQUETAS'].apply(extrair_servidor)
    if 'ORGAO_JULGADOR' in processed_df.columns:
        processed_df['vara'] = processed_df['ETIQUETAS'].apply(extrair_vara)
        processed_df.loc[processed_df['vara'] == "Vara não identificada", 'vara'] = processed_df['ORGAO_JULGADOR']
    else:
        processed_df['vara'] = processed_df['ETIQUETAS'].apply(extrair_vara)

    # --- Datas ---
    processed_df['data_chegada_obj'] = pd.NaT
    data_referencia = pd.to_datetime(get_local_time().date())

    # Prioridade 1: DATA_CHEGADA_FORMATADA_INPUT (DD/MM/YYYY)
    if 'DATA_CHEGADA_FORMATADA_INPUT' in processed_df.columns:
        processed_df['data_chegada_obj'] = pd.to_datetime(
            processed_df['DATA_CHEGADA_FORMATADA_INPUT'], 
            errors='coerce',
            dayfirst=True
        )

    # Prioridade 2: DATA_CHEGADA_RAW (pode conter hora; ajusta)
    if processed_df['data_chegada_obj'].isna().any() and 'DATA_CHEGADA_RAW' in processed_df.columns:
        def extrair_data_chegada_raw(data_str):
            if pd.isna(data_str):
                return pd.NaT
            data_str = str(data_str).split(',')[0].strip()
            return pd.to_datetime(data_str, errors='coerce', dayfirst=True)
        data_series = processed_df['DATA_CHEGADA_RAW'].apply(extrair_data_chegada_raw)
        processed_df.loc[processed_df['data_chegada_obj'].isna(), 'data_chegada_obj'] = data_series.dt.normalize()

    # Prioridade 3: DIAS_TRANSCORRIDOS -> (HOJE()-1)-DIAS
    if processed_df['data_chegada_obj'].isna().any() and 'DIAS_TRANSCORRIDOS' in processed_df.columns:
        def calcular_data_chegada_painel_gerencial(row):
            dias_transcorridos = row['DIAS_TRANSCORRIDOS']
            if pd.isna(dias_transcorridos):
                return pd.NaT
            try:
                dias = int(dias_transcorridos)
                data_referencia_painel = data_referencia - timedelta(days=1)
                return data_referencia_painel - timedelta(days=dias)
            except Exception:
                return pd.NaT
        processed_df.loc[processed_df['data_chegada_obj'].isna(), 'data_chegada_obj'] = processed_df.apply(
            calcular_data_chegada_painel_gerencial, axis=1
        )
        processed_df['DIAS'] = processed_df['DIAS_TRANSCORRIDOS'].fillna(0).astype(int)

    # Remove linhas sem data
    processed_df.dropna(subset=['data_chegada_obj'], inplace=True)

    if not processed_df.empty:
        processed_df['mes'] = processed_df['data_chegada_obj'].dt.month
        processed_df['dia'] = processed_df['data_chegada_obj'].dt.day
        processed_df['data_chegada_formatada_final'] = processed_df['data_chegada_obj'].dt.strftime('%d/%m/%Y')
        if 'DIAS' not in processed_df.columns:
            processed_df['DIAS'] = (data_referencia - processed_df['data_chegada_obj']).dt.days
            processed_df['DIAS'] = processed_df['DIAS'].fillna(0).astype(int)
        processed_df = processed_df.sort_values('data_chegada_obj', ascending=False)

    # Seleciona colunas para saída (mantendo nomes padronizados)
    cols_to_remove = ['DATA_ULTIMO_MOVIMENTO_RAW', 'DATA_CHEGADA_RAW', 'DATA_CHEGADA_FORMATADA_INPUT', 'DIAS_TRANSCORRIDOS']
    cols_to_keep = [col for col in list(COLUNA_MAP.keys()) + ['servidor', 'vara', 'data_chegada_obj', 'mes', 'dia', 'data_chegada_formatada_final', 'DIAS'] if col not in cols_to_remove]
    cols_to_keep = list(dict.fromkeys(cols_to_keep))
    processed_df = processed_df.filter(items=[c for c in cols_to_keep if c in processed_df.columns])
    if 'data_chegada_formatada_final' in processed_df.columns:
        processed_df.rename(columns={'data_chegada_formatada_final': 'data_chegada_formatada'}, inplace=True)

    return processed_df

# --- Estatísticas e gráficos (mantidos) ---

def criar_estatisticas(df):
    stats = {}
    stats['polo_passivo'] = df['POLO_PASSIVO'].value_counts().head(10) if 'POLO_PASSIVO' in df.columns else pd.Series(dtype='int64')
    stats['mes'] = df['mes'].value_counts().sort_index() if 'mes' in df.columns else pd.Series(dtype='int64')

    if 'servidor' in df.columns:
        servidor_stats = df[~df['servidor'].isin(['Sem etiqueta', 'Não atribuído'])]['servidor'].value_counts()
        nao_atribuidos_count = df[df['servidor'].isin(['Sem etiqueta', 'Não atribuído'])].shape[0]
        if nao_atribuidos_count > 0:
            servidor_stats['Sem ou Não Atribuído'] = nao_atribuidos_count
        stats['servidor'] = servidor_stats
    else:
        stats['servidor'] = pd.Series(dtype='int64')

    stats['vara'] = df['vara'].value_counts().head(10) if 'vara' in df.columns else pd.Series(dtype='int64')
    stats['assunto'] = df['ASSUNTO_PRINCIPAL'].value_counts().head(10) if 'ASSUNTO_PRINCIPAL' in df.columns else pd.Series(dtype='int64')
    return stats

def criar_grafico_barras(dados, titulo, eixo_x, eixo_y):
    df_plot = pd.DataFrame({
        eixo_x: dados.index,
        eixo_y: dados.values
    })
    if eixo_x.lower() == 'mês' or eixo_x.lower() == 'mes':
        mes_map = {1: 'Jan', 2: 'Fev', 3: 'Mar', 4: 'Abr', 5: 'Mai', 6: 'Jun', 7: 'Jul', 8: 'Ago', 9: 'Set', 10: 'Out', 11: 'Nov', 12: 'Dez'}
        df_plot['Mês Nome'] = df_plot[eixo_x].map(mes_map).fillna(df_plot[eixo_x].astype(str))
        eixo_x_display = 'Mês Nome'
    else:
        eixo_x_display = eixo_x
    chart = alt.Chart(df_plot).mark_bar().encode(
        x=alt.X(f'{eixo_x_display}:N', title=eixo_x, axis=alt.Axis(labelAngle=-45), sort='-y'),
        y=alt.Y(f'{eixo_y}:Q', title=eixo_y),
        tooltip=[eixo_x_display, eixo_y]
    ).properties(title=titulo, width=600, height=400)
    return chart

def criar_grafico_pizza_com_legenda(dados, titulo):
    df_plot = pd.DataFrame({
        'categoria': dados.index,
        'valor': dados.values,
        'percentual': (dados.values / dados.values.sum() * 100).round(1)
    })
    df_plot['label'] = df_plot['categoria'] + ' (' + df_plot['valor'].astype(str) + ' - ' + df_plot['percentual'].astype(str) + '%)'
    chart = alt.Chart(df_plot).mark_arc().encode(
        theta=alt.Theta(field="valor", type="quantitative"),
        color=alt.Color(field="label", type="nominal", legend=alt.Legend(title="Servidores")),
        tooltip=['categoria', 'valor', 'percentual']
    ).properties(title=titulo, width=500, height=400)
    return chart

# --- Funções de geração de PDF e utilitários ---

def gerar_link_download_pdf_bytes(pdf_bytes, nome_arquivo):
    """Gera um link de download (HTML) para o conteúdo em bytes do PDF."""
    try:
        b64 = base64.b64encode(pdf_bytes).decode('latin-1')
        href = f'<a href="data:application/pdf;base64,{b64}" download="{nome_arquivo}">📄 Baixar Relatório PDF</a>'
        return href
    except Exception as e:
        st.error(f"Erro ao gerar link de download: {e}")
        return ""

def criar_relatorio_filtros_reportlab(df_filtrado, filtros_aplicados):
    """Gera um PDF (bytes) com os processos filtrados usando ReportLab.
       Ordena do mais antigo ao mais recente e destaca linhas com DIAS > 90."""
    try:
        if df_filtrado.empty:
            st.warning("Nenhum processo para gerar relatório.")
            return None

        # Copia e prepara dataframe exibido (garante colunas presentes)
        df = df_filtrado.copy()
        # Força número do processo como string
        if 'NUMERO_PROCESSO' in df.columns:
            df['NUMERO_PROCESSO'] = df['NUMERO_PROCESSO'].astype(str)
        # Ordena do mais antigo para o mais recente (data_chegada_obj)
        if 'data_chegada_obj' in df.columns:
            df = df.sort_values(by='data_chegada_obj', ascending=True)
        else:
            df = df.sort_values(by=df.columns.tolist()[0])  # fallback seguro

        # Monta tabela para o PDF
        colunas = ['NUMERO_PROCESSO', 'POLO_ATIVO', 'POLO_PASSIVO', 'data_chegada_formatada', 'DIAS', 'servidor', 'ASSUNTO_PRINCIPAL']
        colunas_existentes = [c for c in colunas if c in df.columns]
        # Rótulos amigáveis
        rotulos = {
            'NUMERO_PROCESSO': 'Nº Processo',
            'POLO_ATIVO': 'Polo Ativo',
            'POLO_PASSIVO': 'Polo Passivo',
            'data_chegada_formatada': 'Data Chegada',
            'DIAS': 'Dias',
            'servidor': 'Servidor',
            'ASSUNTO_PRINCIPAL': 'Assunto'
        }
        header = [rotulos.get(c, c) for c in colunas_existentes]

        data_table = [header]
        highlight_rows = set()
        for idx, row in df.iterrows():
            linha = []
            for c in colunas_existentes:
                valor = row.get(c, '')
                if pd.isna(valor):
                    valor = ''
                linha.append(str(valor))
            data_table.append(linha)
        # Detectar linhas com DIAS > 90 (considerando a coluna DIAS)
        for i, row in enumerate(df.itertuples(), start=1):  # start=1 because header é 0
            dias = None
            if 'DIAS' in df.columns:
                try:
                    dias = int(getattr(row, 'DIAS'))
                except Exception:
                    dias = None
            if dias is not None and dias > 90:
                highlight_rows.add(i)  # índice dentro da tabela (considerando header)

        # Cria PDF em memória
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), leftMargin=15*mm, rightMargin=15*mm, topMargin=15*mm, bottomMargin=15*mm)
        styles = getSampleStyleSheet()
        story = []

        # Cabeçalho
        story.append(Paragraph("PODER JUDICIÁRIO - JUSTIÇA FEDERAL EM PERNAMBUCO", styles['Title']))
        story.append(Spacer(1, 6))
        story.append(Paragraph("CONTADORIA DOS JUIZADOS ESPECIAIS FEDERAIS", styles['Heading2']))
        story.append(Spacer(1, 8))
        story.append(Paragraph("RELATÓRIO - FILTROS APLICADOS", styles['Heading3']))
        story.append(Spacer(1, 6))
        story.append(Paragraph(f"Filtros: {filtros_aplicados}", styles['Normal']))
        story.append(Paragraph(f"Data de geração: {get_local_time().strftime('%d/%m/%Y %H:%M:%S')}", styles['Normal']))
        story.append(Spacer(1, 10))

        # Construir tabela ReportLab
        table = Table(data_table, repeatRows=1)
        # Estilos básicos
        style = TableStyle([
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,0), 9),
            ('BOTTOMPADDING', (0,0), (-1,0), 6),
            ('ALIGN', (0,0), (-1,0), 'CENTER'),
            ('GRID', (0,0), (-1,-1), 0.25, colors.grey),
            ('FONTSIZE', (0,1), (-1,-1), 8),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ])

        # Destacar linhas com >90 dias (fundo amarelado claro) e tornar a fonte em negrito
        for r in highlight_rows:
            style.add('BACKGROUND', (0, r), (-1, r), colors.HexColor("#FFF3BF"))  # amarelo claro
            style.add('TEXTCOLOR', (0, r), (-1, r), colors.black)
            style.add('FONTNAME', (0, r), (-1, r), 'Helvetica-Bold')

        # Alternância de cores para linhas normais (melhora legibilidade)
        num_rows = len(data_table)
        for r in range(1, num_rows):
            if r not in highlight_rows:
                if r % 2 == 0:
                    style.add('BACKGROUND', (0, r), (-1, r), colors.whitesmoke)

        table.setStyle(style)
        story.append(table)
        story.append(Spacer(1, 6))
        story.append(Paragraph(f"Total de processos no relatório: {len(df)}", styles['Normal']))
        story.append(Spacer(1, 12))
        story.append(Paragraph("Legenda: linhas em destaque possuem mais de 90 dias.", styles['Italic']))

        doc.build(story)
        pdf_bytes = buffer.getvalue()
        buffer.close()
        return pdf_bytes
    except Exception as e:
        st.error(f"Erro durante a geração do PDF de filtros: {e}")
        return None

def gerar_csv_atribuicoes(df):
    """Gera o conteúdo CSV das atribuições manuais."""
    if df.empty:
        return ""
    df_temp = df.copy()
    cols_for_csv = [
        'NUMERO_PROCESSO', 
        'vara', 
        'ORGAO_JULGADOR', 
        'servidor', 
        'data_atribuicao',
        'POLO_ATIVO',
        'POLO_PASSIVO',
        'ASSUNTO_PRINCIPAL'
    ]
    cols_for_csv = [c for c in cols_for_csv if c in df_temp.columns]
    df_temp = df_temp[cols_for_csv]
    rename_map = {
        'NUMERO_PROCESSO': 'Numero do Processo',
        'vara': 'Vara (Tag)',
        'ORGAO_JULGADOR': 'Orgao Julgador (Original)',
        'servidor': 'Servidor Atribuido',
        'data_atribuicao': 'Data e Hora da Atribuicao',
        'POLO_ATIVO': 'Polo Ativo',
        'POLO_PASSIVO': 'Polo Passivo',
        'ASSUNTO_PRINCIPAL': 'Assunto Principal'
    }
    df_temp = df_temp.rename(columns={k: v for k, v in rename_map.items() if k in df_temp.columns})
    csv_output = df_temp.to_csv(index=False, sep=';', encoding='latin-1')
    return csv_output

# --- FUNÇÃO PRINCIPAL (MAIN) ---

def main():
    # Inicialização da Session State
    if 'atribuicoes_servidores' not in st.session_state:
        st.session_state.atribuicoes_servidores = pd.DataFrame(columns=[
            'NUMERO_PROCESSO', 'vara', 'ORGAO_JULGADOR', 'servidor', 'data_atribuicao', 'POLO_ATIVO', 'ASSUNTO_PRINCIPAL'
        ])

    # Header
    st.markdown("""
    <div class="main-header">
        <h1>PODER JUDICIÁRIO</h1>
        <h3>JUSTIÇA FEDERAL EM PERNAMBUCO</h3>
        <h4>CONTADORIA DOS JUIZADOS ESPECIAIS FEDERAIS</h4>
    </div>
    """, unsafe_allow_html=True)

    # Upload de arquivos CSV (múltiplos)
    st.markdown("### 📁 Upload dos Arquivos CSV do PJE")
    uploaded_files = st.file_uploader(
        "Selecione um ou mais arquivos CSV exportados do PJE (separador: ponto e vírgula)",
        type=['csv'],
        accept_multiple_files=True
    )

    if uploaded_files:
        all_dfs = []
        leitura_falhas = []
        for uploaded_file in uploaded_files:
            try:
                # Lê forçando NUMERO_PROCESSO como string e dayfirst para datas
                # Tenta UTF-8 primeiro
                try:
                    df = pd.read_csv(uploaded_file, delimiter=';', encoding='utf-8', dtype=str)
                except UnicodeDecodeError:
                    df = pd.read_csv(uploaded_file, delimiter=';', encoding='latin-1', dtype=str)
                except Exception as e:
                    # última tentativa com inferência de engine
                    df = pd.read_csv(uploaded_file, delimiter=';', encoding='latin-1', dtype=str, engine='python')
                # Padroniza
                df_padronizado = mapear_e_padronizar_colunas(df.copy())
                if 'NUMERO_PROCESSO' in df_padronizado.columns:
                    all_dfs.append(df_padronizado)
                else:
                    leitura_falhas.append((uploaded_file.name, "Coluna 'Número do Processo' não encontrada"))
            except pd.errors.EmptyDataError:
                leitura_falhas.append((uploaded_file.name, "Arquivo vazio"))
            except pd.errors.ParserError:
                leitura_falhas.append((uploaded_file.name, "Erro de parser - verifique delimitador"))
            except Exception as e:
                leitura_falhas.append((uploaded_file.name, str(e)))

        if leitura_falhas:
            for nome, motivo in leitura_falhas:
                st.warning(f"Arquivo '{nome}' não importado: {motivo}")

        if not all_dfs:
            st.error("Nenhum arquivo válido pôde ser lido para a análise. Verifique os arquivos e o formato (ponto e vírgula).")
            return

        with st.spinner(f'Unificando dados de {len(all_dfs)} arquivo(s) e removendo duplicatas...'):
            try:
                df_unificado = pd.concat(all_dfs, ignore_index=True)
                # garantir NUMERO_PROCESSO como string sem truncar zeros à esquerda
                if 'NUMERO_PROCESSO' in df_unificado.columns:
                    df_unificado['NUMERO_PROCESSO'] = df_unificado['NUMERO_PROCESSO'].astype(str).str.strip().fillna('')
                df_final = df_unificado.drop_duplicates(subset=['NUMERO_PROCESSO'], keep='first')
            except Exception as e:
                st.error(f"Falha ao unificar arquivos: {e}")
                return

        st.success(f"✅ Análise unificada de **{len(uploaded_files)}** arquivo(s). **{len(df_final)}** processos únicos encontrados.")

        painel_gerencial_detectado = any('DIAS_TRANSCORRIDOS' in df.columns for df in all_dfs)
        if painel_gerencial_detectado:
            st.warning(
                "Observação sobre arquivos do Painel Gerencial:\n"
                "- Esses CSVs podem conter apenas a coluna 'Dias' (DIAS_TRANSCORRIDOS). O sistema usa a regra (HOJE()-1)-DIAS para estimar a data."
            )

        # Processar dados
        with st.spinner('Processando dados...'):
            try:
                processed_df = processar_dados(df_final)
            except Exception as e:
                st.error(f"Erro durante o processamento dos dados: {e}")
                return

        # Aplicar atribuições manuais existentes
        if not st.session_state.atribuicoes_servidores.empty:
            df_atribuicoes = st.session_state.atribuicoes_servidores[['NUMERO_PROCESSO', 'servidor']].copy()
            for index, row in df_atribuicoes.iterrows():
                match_index = processed_df.index[processed_df['NUMERO_PROCESSO'] == row['NUMERO_PROCESSO']]
                if not match_index.empty:
                    processed_df.loc[match_index, 'servidor'] = row['servidor']

        stats = criar_estatisticas(processed_df)

        tab1, tab2, tab3, tab4 = st.tabs(["📊 Visão Geral", "📈 Estatísticas", "🔍 Filtros Avançados", "✍️ Atribuição Manual"])

        # --- Tab 1: Visão Geral ---
        with tab1:
            st.markdown("### 📊 Dashboard - Visão Geral")
            col1, col2, col3, col4 = st.columns(4)
            with col4:
                if st.button("📄 Gerar Relatório - Visão Geral", key="relatorio_visao"):
                    try:
                        pdf = criar_relatorio_visao_geral(stats, len(processed_df))
                        nome_arquivo = f"relatorio_visao_geral_{get_local_time().strftime('%Y%m%d_%H%M')}.pdf"
                        href = gerar_link_download_pdf(pdf.output(dest='S').encode('latin-1'), nome_arquivo)
                        if href:
                            st.markdown(href, unsafe_allow_html=True)
                    except Exception as e:
                        st.error(f"Erro ao gerar relatório: {e}")

            with col1:
                st.metric("Total de Processos Únicos", len(processed_df))
            with col2:
                servidores_reais = processed_df[~processed_df['servidor'].isin(['Sem etiqueta', 'Não atribuído'])]['servidor'].nunique()
                st.metric("Servidores Atribuídos", servidores_reais)
            with col3:
                varas_unicas = processed_df['vara'].nunique() if 'vara' in processed_df.columns else 0
                st.metric("Varas Federais", varas_unicas)
            with col4:
                st.metric("Processos Sem Atribuição", len(processed_df[processed_df['servidor'].isin(['Sem etiqueta', 'Não atribuído'])]))

            col1, col2 = st.columns(2)
            with col1:
                if not stats['polo_passivo'].empty:
                    st.altair_chart(criar_grafico_barras(stats['polo_passivo'], "Distribuição por Polo Passivo (Top 10)", "Polo Passivo", "Quantidade"), use_container_width=True)
                    with st.expander("📊 Ver dados - Polo Passivo"):
                        st.dataframe(stats['polo_passivo'])
            with col2:
                if not stats['mes'].empty:
                    st.altair_chart(criar_grafico_barras(stats['mes'], "Distribuição por Mês (Data de Chegada)", "Mês", "Quantidade"), use_container_width=True)
                    with st.expander("📊 Ver dados - Distribuição por Mês"):
                        st.dataframe(stats['mes'])

            col3, col4 = st.columns(2)
            with col3:
                if not stats['servidor'].empty:
                    st.altair_chart(criar_grafico_pizza_com_legenda(stats['servidor'], "Distribuição por Servidor"), use_container_width=True)
                    with st.expander("📊 Ver dados - Distribuição por Servidor"):
                        st.dataframe(stats['servidor'])
            with col4:
                if not stats['assunto'].empty:
                    df_assunto = pd.DataFrame({'Assunto': stats['assunto'].index, 'Quantidade': stats['assunto'].values})
                    chart_assunto = alt.Chart(df_assunto).mark_bar().encode(x='Quantidade:Q', y=alt.Y('Assunto:N', sort='-x', title='Assunto'), tooltip=['Assunto', 'Quantidade']).properties(title="Principais Assuntos (Top 10)", width=600, height=400)
                    st.altair_chart(chart_assunto, use_container_width=True)
                    with st.expander("📊 Ver dados - Principais Assuntos"):
                        st.dataframe(stats['assunto'])

        # --- Tab 2: Estatísticas ---
        with tab2:
            st.markdown("### 📈 Estatísticas Detalhadas")
            col1, col2 = st.columns([3, 1])
            with col2:
                if st.button("📄 Gerar Relatório - Estatísticas", key="relatorio_estatisticas"):
                    try:
                        pdf = criar_relatorio_estatisticas(stats)
                        nome_arquivo = f"relatorio_estatisticas_{get_local_time().strftime('%Y%m%d_%H%M')}.pdf"
                        href = gerar_link_download_pdf(pdf.output(dest='S').encode('latin-1'), nome_arquivo)
                        if href:
                            st.markdown(href, unsafe_allow_html=True)
                    except Exception as e:
                        st.error(f"Erro ao gerar relatório: {e}")
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("#### Por Polo Passivo")
                st.dataframe(stats['polo_passivo'], use_container_width=True)
                st.markdown("#### Por Servidor")
                st.dataframe(stats['servidor'], use_container_width=True)
            with col2:
                st.markdown("#### Por Mês (Data de Chegada)")
                st.dataframe(stats['mes'], use_container_width=True)
                st.markdown("#### Por Vara")
                st.dataframe(stats['vara'], use_container_width=True)

        # --- Tab 3: Filtros Avançados ---
        with tab3:
            st.markdown("### 🔍 Filtros Avançados")
            if processed_df.empty or 'servidor' not in processed_df.columns:
                st.warning("Não há dados válidos ou a coluna de Servidor não foi encontrada. Filtros indisponíveis.")
                return

            col1, col2, col3 = st.columns(3)
            servidor_options = sorted(processed_df['servidor'].unique())
            mes_options = sorted(processed_df['mes'].dropna().unique()) if 'mes' in processed_df.columns else []
            assunto_options = sorted(processed_df['ASSUNTO_PRINCIPAL'].dropna().unique()) if 'ASSUNTO_PRINCIPAL' in processed_df.columns else []
            polo_passivo_options = sorted(processed_df['POLO_PASSIVO'].dropna().unique()) if 'POLO_PASSIVO' in processed_df.columns else []
            vara_options = sorted(processed_df['vara'].unique()) if 'vara' in processed_df.columns else []

            with col1:
                servidor_filter = st.multiselect("Filtrar por Servidor", options=servidor_options, default=None)
                mes_filter = st.multiselect("Filtrar por Mês (Chegada)", options=mes_options, default=None)
            with col2:
                polo_passivo_filter = st.multiselect("Filtrar por Polo Passivo", options=polo_passivo_options, default=None)
                assunto_filter = st.multiselect("Filtrar por Assunto", options=assunto_options, default=None)
            with col3:
                vara_filter = st.multiselect("Filtrar por Vara", options=vara_options, default=None)

            filtered_df = processed_df.copy()
            filtros_aplicados = []
            if servidor_filter:
                filtered_df = filtered_df[filtered_df['servidor'].isin(servidor_filter)]
                filtros_aplicados.append(f"Servidor: {', '.join(servidor_filter)}")
            if mes_filter and 'mes' in filtered_df.columns:
                filtered_df = filtered_df[filtered_df['mes'].isin(mes_filter)]
                filtros_aplicados.append(f"Mês (Chegada): {', '.join(map(str, mes_filter))}")
            if polo_passivo_filter and 'POLO_PASSIVO' in filtered_df.columns:
                filtered_df = filtered_df[filtered_df['POLO_PASSIVO'].isin(polo_passivo_filter)]
                filtros_aplicados.append(f"Polo Passivo: {', '.join(polo_passivo_filter)}")
            if assunto_filter and 'ASSUNTO_PRINCIPAL' in filtered_df.columns:
                filtered_df = filtered_df[filtered_df['ASSUNTO_PRINCIPAL'].isin(assunto_filter)]
                filtros_aplicados.append(f"Assunto: {', '.join(assunto_filter)}")
            if vara_filter and 'vara' in filtered_df.columns:
                filtered_df = filtered_df[filtered_df['vara'].isin(vara_filter)]
                filtros_aplicados.append(f"Vara: {', '.join(vara_filter)}")

            filtros_texto = " | ".join(filtros_aplicados) if filtros_aplicados else "Nenhum filtro aplicado"
            st.metric("Processos Filtrados", len(filtered_df))

            if len(filtered_df) > 0:
                colunas_filtro = [
                    'NUMERO_PROCESSO', 'POLO_ATIVO', 'POLO_PASSIVO', 'data_chegada_formatada',
                    'mes', 'DIAS', 'servidor', 'vara', 'ASSUNTO_PRINCIPAL'
                ]
                colunas_existentes = [col for col in colunas_filtro if col in filtered_df.columns]
                display_filtered = filtered_df[colunas_existentes].copy()
                display_filtered.columns = [
                    'Nº Processo', 'Polo Ativo', 'Polo Passivo', 'Data Chegada',
                    'Mês', 'Dias', 'Servidor', 'Vara', 'Assunto Principal'
                ][:len(display_filtered.columns)]
                st.dataframe(display_filtered, use_container_width=True)

                st.markdown("---")
                st.markdown("### 📄 Gerar Relatório com Filtros")

                if st.button("🖨️ Gerar Relatório PDF com Filtros Atuais", key="relatorio_filtros"):
                    with st.spinner("Gerando relatório em PDF..."):
                        try:
                            pdf_bytes = criar_relatorio_filtros_reportlab(filtered_df, filtros_texto)
                            if pdf_bytes:
                                nome_arquivo = f"relatorio_filtros_{get_local_time().strftime('%Y%m%d_%H%M')}.pdf"
                                href = gerar_link_download_pdf_bytes(pdf_bytes, nome_arquivo)
                                if href:
                                    st.markdown(href, unsafe_allow_html=True)
                                else:
                                    st.error("Erro ao gerar o link de download do PDF.")
                            else:
                                st.error("Erro ao gerar o PDF.")
                        except Exception as e:
                            st.error(f"Erro inesperado ao gerar PDF: {e}")
            else:
                st.warning("Nenhum processo encontrado com os filtros aplicados.")

        # --- Tab 4: Atribuição Manual ---
        with tab4:
            st.markdown("### ✍️ Atribuição Manual de Servidores")
            todos_processos = processed_df.copy()
            col1, col2 = st.columns([2, 1])
            with col1:
                assuntos_disponiveis = sorted(todos_processos['ASSUNTO_PRINCIPAL'].dropna().unique()) if 'ASSUNTO_PRINCIPAL' in todos_processos.columns else []
                assunto_filtro = st.selectbox("Filtrar por Assunto para Agrupar:", options=["Todos"] + assuntos_disponiveis, key='filtro_assunto_atribuicao')
                if assunto_filtro != "Todos":
                    processos_filtrados = todos_processos[todos_processos['ASSUNTO_PRINCIPAL'] == assunto_filtro].copy()
                    st.info(f"**{len(processos_filtrados)}** processos encontrados com assunto: **{assunto_filtro}**")
                else:
                    processos_filtrados = todos_processos.copy()
                    st.info(f"Mostrando **{len(processos_filtrados)}** processos (todos os assuntos)")
            with col2:
                status_filtro = st.selectbox("Filtrar por Status:", options=["Todos", "Sem Atribuição", "Com Atribuição"], key='filtro_status_atribuicao')
                if status_filtro == "Sem Atribuição":
                    processos_filtrados = processos_filtrados[processos_filtrados['servidor'].isin(["Sem etiqueta", "Não atribuído"])]
                elif status_filtro == "Com Atribuição":
                    processos_filtrados = processos_filtrados[~processos_filtrados['servidor'].isin(["Sem etiqueta", "Não atribuído"])]

            st.markdown("---")
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("#### 📋 Processos para Atribuição")
                if not processos_filtrados.empty:
                    processos_para_atribuir = processos_filtrados.sort_values(by=['data_chegada_obj', 'NUMERO_PROCESSO'], ascending=[True, True]).copy()
                    cols_to_show = ['NUMERO_PROCESSO', 'POLO_PASSIVO', 'vara', 'data_chegada_formatada', 'DIAS', 'ASSUNTO_PRINCIPAL', 'servidor']
                    cols_to_show = [c for c in cols_to_show if c in processos_para_atribuir.columns]
                    display_table = processos_para_atribuir[cols_to_show].rename(columns={
                        'NUMERO_PROCESSO': 'Nº Processo',
                        'POLO_PASSIVO': 'Polo Passivo',
                        'vara': 'Vara',
                        'data_chegada_formatada': 'Data Chegada',
                        'DIAS': 'Dias',
                        'ASSUNTO_PRINCIPAL': 'Assunto Principal',
                        'servidor': 'Servidor Atual'
                    })
                    st.dataframe(display_table, use_container_width=True)
                    st.markdown("---")
                    st.markdown("#### Atribuir em Lote")
                    processos_selecionados = st.multiselect("Selecione o(s) N° Processo(s) a serem atribuídos:", options=processos_para_atribuir['NUMERO_PROCESSO'].tolist(), key='multiselect_atribuicao')
                    servidor_selecionado = st.selectbox("Selecione o Servidor:", options=[""] + SERVIDORES_DISPONIVEIS, key='selectbox_servidor')
                    if st.button("✅ Confirmar Atribuição em Lote"):
                        if processos_selecionados and servidor_selecionado:
                            novas_atribuicoes_list = []
                            for num_processo in processos_selecionados:
                                row_data = processed_df[processed_df['NUMERO_PROCESSO'] == num_processo].iloc[0].to_dict()
                                novas_atribuicoes_list.append({
                                    'NUMERO_PROCESSO': num_processo,
                                    'vara': row_data.get('vara', ''),
                                    'ORGAO_JULGADOR': row_data.get('ORGAO_JULGADOR', ''),
                                    'servidor': servidor_selecionado,
                                    'data_atribuicao': get_local_time().strftime("%d/%m/%Y %H:%M:%S"),
                                    'POLO_ATIVO': row_data.get('POLO_ATIVO', ''),
                                    'POLO_PASSIVO': row_data.get('POLO_PASSIVO', ''),
                                    'ASSUNTO_PRINCIPAL': row_data.get('ASSUNTO_PRINCIPAL', '')
                                })
                            novas_atribuicoes_df = pd.DataFrame(novas_atribuicoes_list)
                            st.session_state.atribuicoes_servidores = st.session_state.atribuicoes_servidores[~st.session_state.atribuicoes_servidores['NUMERO_PROCESSO'].isin(processos_selecionados)]
                            st.session_state.atribuicoes_servidores = pd.concat([st.session_state.atribuicoes_servidores, novas_atribuicoes_df], ignore_index=True)
                            st.success(f"**{len(processos_selecionados)}** processos atribuídos a **{servidor_selecionado}**.")
                            st.rerun()
                        else:
                            st.warning("Selecione os processos e o servidor.")
                else:
                    st.info("Nenhum processo encontrado com os filtros aplicados.")
            with col2:
                st.markdown("#### Histórico de Atribuições Manuais")
                st.markdown(f"**Total de Atribuições Manuais:** {len(st.session_state.atribuicoes_servidores)}")
                if not st.session_state.atribuicoes_servidores.empty:
                    df_historico = st.session_state.atribuicoes_servidores.copy()
                    cols_to_display = ['NUMERO_PROCESSO', 'servidor', 'data_atribuicao']
                    df_historico = df_historico.filter(items=cols_to_display)
                    if not df_historico.empty:
                        df_historico.columns = ['Nº Processo', 'Servidor', 'Data Atribuição']
                        st.dataframe(df_historico, use_container_width=True)
                        st.markdown("---")
                        csv_atribuicoes = gerar_csv_atribuicoes(st.session_state.atribuicoes_servidores)
                        if csv_atribuicoes:
                            st.download_button("📥 Baixar Atribuições Manuais (CSV)", data=csv_atribuicoes, file_name=f"atribuicoes_manuais_{get_local_time().strftime('%Y%m%d_%H%M')}.csv", mime='text/csv')
                        if st.button("🗑️ Limpar todas Atribuições Manuais", help="Isso apagará todas as atribuições salvas na sessão."):
                            st.session_state.atribuicoes_servidores = pd.DataFrame(columns=[
                                'NUMERO_PROCESSO', 'vara', 'ORGAO_JULGADOR', 'servidor', 'data_atribuicao', 'POLO_ATIVO', 'ASSUNTO_PRINCIPAL'
                            ])
                            st.success("Atribuições manuais limpas. Recarregando...")
                            st.rerun()
                else:
                    st.info("Nenhuma atribuição manual realizada ainda.")

    else:
        st.info("Envie um ou mais arquivos CSV exportados do PJE para iniciar a análise.")

# --- Funções de criação de relatórios originais com FPDF (mantive para compatibilidade) ---

def criar_relatorio_visao_geral(stats, total_processos):
    class PDF(FPDF):
        def header(self):
            self.set_font('Arial', 'B', 16)
            self.cell(0, 10, 'PODER JUDICIÁRIO', 0, 1, 'C')
            self.set_font('Arial', 'B', 14)
            self.cell(0, 10, 'JUSTIÇA FEDERAL EM PERNAMBUCO', 0, 1, 'C')
            self.set_font('Arial', 'B', 12)
            self.cell(0, 10, 'CONTADORIA DOS JUIZADOS ESPECIAIS FEDERAIS', 0, 1, 'C')
            self.ln(5)
    pdf = PDF()
    pdf.add_page()
    pdf.set_font('Arial', 'B', 14)
    pdf.cell(0, 10, 'RELATÓRIO - VISÃO GERAL', 0, 1, 'C')
    pdf.ln(5)
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 8, 'INFORMAÇÕES GERAIS', 0, 1)
    pdf.set_font('Arial', '', 10)
    pdf.cell(0, 6, f'Total de Processos: {total_processos}', 0, 1)
    pdf.cell(0, 6, f'Data de geração: {get_local_time().strftime("%d/%m/%Y %H:%M")}', 0, 1)
    pdf.ln(10)
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 8, 'DISTRIBUIÇÃO POR POLO PASSIVO (Top 10)', 0, 1)
    pdf.set_font('Arial', '', 10)
    for polo, quantidade in stats['polo_passivo'].items():
        pdf.cell(0, 6, f'{polo}: {quantidade}', 0, 1)
    pdf.ln(5)
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 8, 'DISTRIBUIÇÃO POR MÊS', 0, 1)
    pdf.set_font('Arial', '', 10)
    mes_map = {1: 'Janeiro', 2: 'Fevereiro', 3: 'Março', 4: 'Abril', 5: 'Maio', 6: 'Junho', 7: 'Julho', 8: 'Agosto', 9: 'Setembro', 10: 'Outubro', 11: 'Novembro', 12: 'Dezembro'}
    for mes, quantidade in stats['mes'].items():
        pdf.cell(0, 6, f'{mes_map.get(mes, f"Mês {mes}")}: {quantidade}', 0, 1)
    pdf.ln(5)
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 8, 'DISTRIBUIÇÃO POR SERVIDOR', 0, 1)
    pdf.set_font('Arial', '', 10)
    for servidor, quantidade in stats['servidor'].items():
        pdf.cell(0, 6, f'{servidor}: {quantidade}', 0, 1)
    pdf.ln(5)
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 8, 'PRINCIPAIS ASSUNTOS (Top 10)', 0, 1)
    pdf.set_font('Arial', '', 10)
    for assunto, quantidade in stats['assunto'].items():
        pdf.cell(0, 6, f'{assunto}: {quantidade}', 0, 1)
    pdf.ln(10)
    pdf.set_font('Arial', 'I', 8)
    pdf.cell(0, 6, f'Relatório gerado em: {get_local_time().strftime("%d/%m/%Y às %H:%M:%S")}', 0, 1)
    return pdf

def criar_relatorio_estatisticas(stats):
    class PDF(FPDF):
        def header(self):
            self.set_font('Arial', 'B', 16)
            self.cell(0, 10, 'PODER JUDICIÁRIO', 0, 1, 'C')
            self.set_font('Arial', 'B', 14)
            self.cell(0, 10, 'JUSTIÇA FEDERAL EM PERNAMBUCO', 0, 1, 'C')
            self.set_font('Arial', 'B', 12)
            self.cell(0, 10, 'CONTADORIA DOS JUIZADOS ESPECIAIS FEDERAIS', 0, 1, 'C')
            self.ln(5)
    pdf = PDF()
    pdf.add_page()
    pdf.set_font('Arial', 'B', 14)
    pdf.cell(0, 10, 'RELATÓRIO - ESTATÍSTICAS DETALHADAS', 0, 1, 'C')
    pdf.ln(5)
    pdf.set_font('Arial', '', 10)
    pdf.cell(0, 6, f'Data de geração: {get_local_time().strftime("%d/%m/%Y %H:%M")}', 0, 1)
    pdf.ln(10)
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 8, 'POR POLO PASSIVO (Top 10)', 0, 1)
    pdf.set_font('Arial', '', 10)
    for polo, quantidade in stats['polo_passivo'].items():
        pdf.cell(0, 6, f'{polo}: {quantidade}', 0, 1)
    pdf.ln(5)
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 8, 'POR MÊS', 0, 1)
    pdf.set_font('Arial', '', 10)
    mes_map = {1: 'Janeiro', 2: 'Fevereiro', 3: 'Março', 4: 'Abril', 5: 'Maio', 6: 'Junho', 7: 'Julho', 8: 'Agosto', 9: 'Setembro', 10: 'Outubro', 11: 'Novembro', 12: 'Dezembro'}
    for mes, quantidade in stats['mes'].items():
        pdf.cell(0, 6, f'{mes_map.get(mes, f"Mês {mes}")}: {quantidade}', 0, 1)
    pdf.ln(5)
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 8, 'POR SERVIDOR', 0, 1)
    pdf.set_font('Arial', '', 10)
    for servidor, quantidade in stats['servidor'].items():
        pdf.cell(0, 6, f'{servidor}: {quantidade}', 0, 1)
    pdf.ln(5)
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 8, 'POR VARA (Top 10)', 0, 1)
    pdf.set_font('Arial', '', 10)
    for vara, quantidade in stats['vara'].items():
        pdf.cell(0, 6, f'{vara}: {quantidade}', 0, 1)
    pdf.ln(5)
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 8, 'POR ASSUNTO (Top 10)', 0, 1)
    pdf.set_font('Arial', '', 10)
    for assunto, quantidade in stats['assunto'].items():
        pdf.cell(0, 6, f'{assunto}: {quantidade}', 0, 1)
    pdf.ln(10)
    pdf.set_font('Arial', 'I', 8)
    pdf.cell(0, 6, f'Relatório gerado em: {get_local_time().strftime("%d/%m/%Y às %H:%M:%S")}', 0, 1)
    return pdf

if __name__ == "__main__":
    main()
