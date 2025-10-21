import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta
import io
import altair as alt
from fpdf import FPDF
import base64

# --- CONFIGURAÇÕES E CSS ---

# Configuração da página
st.set_page_config(
    page_title="Gestão de Processos Judiciais Unificada",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS customizado
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
    /* Estilo para destaque de assunto na aba de atribuição */
    .assunto-destaque {
        background-color: #ffeeb9; /* Amarelo claro */
        border-left: 5px solid #ffcc00;
        padding: 10px;
        margin: 10px 0;
        border-radius: 4px;
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

# Novo Nome (PADRÃO) -> Lista de Nomes Possíveis nos CSVs
COLUNA_MAP = {
    'NUMERO_PROCESSO': ['Número do Processo', 'numeroProcesso', 'Nº Processo'], 
    'POLO_ATIVO': ['Polo Ativo', 'poloAtivo'],
    'POLO_PASSIVO': ['Polo Passivo', 'poloPassivo'],
    'ORGAO_JULGADOR': ['Órgão Julgador', 'orgaoJulgador', 'Vara'], 
    'ASSUNTO_PRINCIPAL': ['Assunto', 'assuntoPrincipal', 'Assunto Principal'], 
    'TAREFA': ['Tarefa', 'nomeTarefa'],
    'ETIQUETAS': ['Etiquetas', 'tagsProcessoList'],
    # 'DIAS_TRANSCORRIDOS' é a coluna 'Dias' do Painel Gerencial
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
        # Encontra o nome da coluna que existe no arquivo atual
        coluna_encontrada = next((col for col in possiveis if col in df.columns), None)
        
        if coluna_encontrada:
            colunas_padronizadas[coluna_encontrada] = padrao
        
    df.rename(columns=colunas_padronizadas, inplace=True)
    return df

def processar_dados(df):
    """Processa os dados do CSV, usando APENAS nomes de colunas padronizados."""
    
    processed_df = df.copy()
    
    # Colunas essenciais que DEVEM existir após a padronização
    if 'ETIQUETAS' not in processed_df.columns:
        processed_df['ETIQUETAS'] = "Sem etiqueta"
    
    # --- 1. Processar Tags ---
    
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
            if 'Vara Federal' in tag:
                return tag
        return "Vara não identificada"
        
    # Aplicar processamento de tags
    processed_df['servidor'] = processed_df['ETIQUETAS'].apply(extrair_servidor)
    if 'ORGAO_JULGADOR' in processed_df.columns:
         processed_df['vara'] = processed_df['ETIQUETAS'].apply(extrair_vara)
         # Se a vara não foi identificada pela etiqueta, tenta usar o Orgão Julgador
         processed_df.loc[processed_df['vara'] == "Vara não identificada", 'vara'] = processed_df['ORGAO_JULGADOR']
    else:
        processed_df['vara'] = processed_df['ETIQUETAS'].apply(extrair_vara)
    
    # --- 2. Processar Datas e Calcular Dias (LÓGICA CORRIGIDA) ---
    
    processed_df['data_chegada_obj'] = pd.NaT
    
    # Data de referência para os cálculos (HOJE, na hora da execução)
    data_referencia = pd.to_datetime(get_local_time().date())
    
    # --- Lógica de Prioridade de Data ---
    
    # A. Prioridade 1: Data Chegada de arquivos já processados/exportados (DD/MM/YYYY)
    if 'DATA_CHEGADA_FORMATADA_INPUT' in processed_df.columns:
        processed_df['data_chegada_obj'] = pd.to_datetime(
            processed_df['DATA_CHEGADA_FORMATADA_INPUT'], 
            errors='coerce',
            dayfirst=True # <--- REFORÇADO: Garante que o formato é Dia/Mês/Ano
        )

    # B. Prioridade 2: Data Chegada de arquivo de tarefa simples (DD/MM/YYYY, HH:MM:SS)
    if processed_df['data_chegada_obj'].isna().all() and 'DATA_CHEGADA_RAW' in processed_df.columns:
        
        def extrair_data_chegada_raw(data_str):
            if pd.isna(data_str):
                return pd.NaT
            
            # Pega apenas a parte da data, ignorando o tempo que vem após a vírgula
            data_str = str(data_str).split(',')[0].strip() 
            
            # CORREÇÃO DA SÉRIE: Usar pd.to_datetime para garantir que o retorno seja um objeto datetimelike
            # Ele inferirá o formato, priorizando DMY (dayfirst=True)
            return pd.to_datetime(data_str, errors='coerce', dayfirst=True)
        
        data_series = processed_df['DATA_CHEGADA_RAW'].apply(extrair_data_chegada_raw)
        
        # O .dt.normalize() agora funcionará, pois data_series é uma Series de Timestamps/NaT
        processed_df.loc[processed_df['data_chegada_obj'].isna(), 'data_chegada_obj'] = data_series.dt.normalize()
    
    
    # C. Prioridade 3: CÁLCULO CORRIGIDO: Data Hoje - Dias Transcorridos (Painel Gerencial)
    if processed_df['data_chegada_obj'].isna().all() and 'DIAS_TRANSCORRIDOS' in processed_df.columns:
        
        def calcular_data_chegada_painel_gerencial(row):
            dias_transcorridos = row['DIAS_TRANSCORRIDOS']
            
            if pd.isna(dias_transcorridos):
                return pd.NaT
            
            try:
                # CORREÇÃO SOLICITADA:
                # Usar a fórmula: (HOJE() - 1) - QUANTIDADE_DE_DIAS_EM_ATRASO
                dias = int(dias_transcorridos)
                data_referencia_painel = data_referencia - timedelta(days=1)  # HOJE() - 1
                return data_referencia_painel - timedelta(days=dias)
            except ValueError:
                return pd.NaT
            except TypeError:
                 return pd.NaT
        
        processed_df.loc[processed_df['data_chegada_obj'].isna(), 'data_chegada_obj'] = processed_df.apply(
            calcular_data_chegada_painel_gerencial, axis=1
        )
        
        processed_df['DIAS'] = processed_df['DIAS_TRANSCORRIDOS'].fillna(0).astype(int)

    # --- Continuação do Processamento de Data ---
    
    # 1. Filtra linhas onde a data não pôde ser extraída para evitar erros (Mantido)
    processed_df.dropna(subset=['data_chegada_obj'], inplace=True)

    if not processed_df.empty:
        
        # FILTRO DE SANIDADE DE DATA (REMOVIDO PARA INCLUIR PROCESSOS MAIS ANTIGOS, COMO OS 3 QUE FALTAVAM)
        # processed_df = processed_df[processed_df['data_chegada_obj'].dt.year >= 2024].copy()
        
        if processed_df.empty:
             return processed_df
        
        # 2. Calcula Mês e Dia a partir da DATA DE CHEGADA CALCULADA
        processed_df['mes'] = processed_df['data_chegada_obj'].dt.month
        processed_df['dia'] = processed_df['data_chegada_obj'].dt.day
        
        # 3. Formatar data de chegada (apenas data)
        processed_df['data_chegada_formatada_final'] = processed_df['data_chegada_obj'].dt.strftime('%d/%m/%Y')
        
        # 4. Se a coluna DIAS não veio do Painel Gerencial (Prioridade 3), calcula o DIAS.
        if 'DIAS' not in processed_df.columns:
            processed_df['DIAS'] = (data_referencia - processed_df['data_chegada_obj']).dt.days
            processed_df['DIAS'] = processed_df['DIAS'].fillna(0).astype(int)
        
        # 5. Ordenar por data de chegada (mais recente primeiro)
        processed_df = processed_df.sort_values('data_chegada_obj', ascending=False)
    
    
    # Colunas de saída (usando os nomes padronizados)
    cols_to_remove = ['DATA_ULTIMO_MOVIMENTO_RAW', 'DATA_CHEGADA_RAW', 'DATA_CHEGADA_FORMATADA_INPUT', 'DIAS_TRANSCORRIDOS']
    cols_to_keep = [col for col in list(COLUNA_MAP.keys()) + ['servidor', 'vara', 'data_chegada_obj', 'mes', 'dia', 'data_chegada_formatada_final', 'DIAS'] if col not in cols_to_remove]
    
    cols_to_keep = list(dict.fromkeys(cols_to_keep))
    
    processed_df = processed_df.filter(items=cols_to_keep)
    
    if 'data_chegada_formatada_final' in processed_df.columns:
        processed_df.rename(columns={'data_chegada_formatada_final': 'data_chegada_formatada'}, inplace=True)
    
    return processed_df

# --- Funções de Estatísticas, Relatórios e Download (Inalteradas) ---

def criar_estatisticas(df):
    """Cria estatísticas usando APENAS nomes de colunas padronizados."""
    
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
    
    if eixo_x.lower() == 'mês':
        mes_map = {
            1: 'Jan', 2: 'Fev', 3: 'Mar', 4: 'Abr', 5: 'Mai', 6: 'Jun', 
            7: 'Jul', 8: 'Ago', 9: 'Set', 10: 'Out', 11: 'Nov', 12: 'Dez'
        }
        df_plot['Mês Nome'] = df_plot[eixo_x].map(mes_map).fillna(df_plot[eixo_x].astype(str))
        eixo_x_display = 'Mês Nome'
    else:
        eixo_x_display = eixo_x
    
    chart = alt.Chart(df_plot).mark_bar().encode(
        x=alt.X(f'{eixo_x_display}:N', title=eixo_x, axis=alt.Axis(labelAngle=-45), sort='-y'),
        y=alt.Y(f'{eixo_y}:Q', title=eixo_y),
        tooltip=[eixo_x_display, eixo_y]
    ).properties(
        title=titulo,
        width=600,
        height=400
    )
    
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
    ).properties(
        title=titulo,
        width=500,
        height=400
    )
    
    return chart

def criar_relatorio_visao_geral(stats, total_processos):
    class PDF(FPDF):
        def header(self):
            self.set_font('Arial', 'B', 16)
            self.cell(0, 10, 'PODER JUDICIÁRIO', 0, 1, 'C')
            self.set_font('Arial', 'B', 14)
            self.cell(0, 10, 'JUSTIÇA FEDERAL EM PERNAMBUCO - JUIZADOS ESPECIAIS FEDERAIS', 0, 1, 'C')
            self.set_font('Arial', 'B', 12)
            self.cell(0, 10, 'PLANILHA DE CONTROLE DE PROCESSOS - PJE2X', 0, 1, 'C')
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
            self.cell(0, 10, 'JUSTIÇA FEDERAL EM PERNAMBUCO - JUIZADOS ESPECIAIS FEDERAIS', 0, 1, 'C')
            self.set_font('Arial', 'B', 12)
            self.cell(0, 10, 'PLANILHA DE CONTROLE DE PROCESSOS - PJE2X', 0, 1, 'C')
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

def criar_relatorio_filtros(df_filtrado, filtros_aplicados):
    class PDF(FPDF):
        def header(self):
            self.set_font('Arial', 'B', 16)
            self.cell(0, 10, 'PODER JUDICIÁRIO', 0, 1, 'C')
            self.set_font('Arial', 'B', 14)
            self.cell(0, 10, 'JUSTIÇA FEDERAL EM PERNAMBUCO - JUIZADOS ESPECIAIS FEDERAIS', 0, 1, 'C')
            self.set_font('Arial', 'B', 12)
            self.cell(0, 10, 'PLANILHA DE CONTROLE DE PROCESSOS - PJE2X', 0, 1, 'C')
            self.ln(5)
    
    pdf = PDF()
    pdf.add_page()
    
    pdf.set_font('Arial', 'B', 14)
    pdf.cell(0, 10, 'RELATÓRIO - FILTROS APLICADOS', 0, 1, 'C')
    pdf.ln(5)
    
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 8, 'FILTROS APLICADOS:', 0, 1)
    pdf.set_font('Arial', '', 10)
    pdf.cell(0, 6, filtros_aplicados, 0, 1)
    pdf.ln(5)
    
    pdf.set_font('Arial', '', 10)
    pdf.cell(0, 6, f'Total de processos filtrados: {len(df_filtrado)}', 0, 1)
    pdf.cell(0, 6, f'Data de geração: {get_local_time().strftime("%d/%m/%Y %H:%M")}', 0, 1)
    pdf.ln(10)
    
    if len(df_filtrado) > 0:
        pdf.set_font('Arial', 'B', 9)
        colunas = ['Nº Processo', 'Polo Ativo', 'Data', 'Servidor', 'Assunto']
        larguras = [35, 45, 20, 30, 60]
        
        for i, coluna in enumerate(colunas):
            pdf.cell(larguras[i], 10, coluna, 1, 0, 'C')
        pdf.ln()
        
        pdf.set_font('Arial', '', 7)
        for _, row in df_filtrado.iterrows():
            n_processo = str(row['Nº Processo']) if pd.notna(row['Nº Processo']) else ''
            polo_ativo = str(row['Polo Ativo']) if pd.notna(row['Polo Ativo']) else ''
            data_chegada = str(row['Data Chegada']) if pd.notna(row['Data Chegada']) else ''
            servidor = str(row['Servidor']) if pd.notna(row['Servidor']) else ''
            assunto = str(row['Assunto Principal']) if pd.notna(row['Assunto Principal']) else ''
            
            pdf.cell(larguras[0], 8, n_processo[:20], 1)
            pdf.cell(larguras[1], 8, polo_ativo[:25], 1)
            pdf.cell(larguras[2], 8, data_chegada[:10], 1)
            pdf.cell(largas[3], 8, servidor[:15], 1)
            pdf.cell(larguras[4], 8, assunto[:40], 1)
            pdf.ln()
    
    pdf.ln(10)
    pdf.set_font('Arial', 'I', 8)
    pdf.cell(0, 6, f'Relatório gerado em: {get_local_time().strftime("%d/%m/%Y às %H:%M:%S")}', 0, 1)
    
    return pdf

def gerar_link_download_pdf(pdf, nome_arquivo):
    """Gera link de download para o PDF"""
    try:
        pdf_output = pdf.output(dest='S').encode('latin-1')
        b64 = base64.b64encode(pdf_output).decode('latin-1')
        href = f'<a href="data:application/octet-stream;base64,{b64}" download="{nome_arquivo}">📄 Baixar Relatório PDF</a>'
        return href
    except Exception as e:
        st.error(f"Erro ao gerar PDF: {e}")
        return ""

def gerar_csv_atribuicoes(df):
    """Gera o conteúdo CSV das atribuições manuais."""
    if df.empty:
        return ""
        
    df_temp = df.copy()
    
    # Inclui POLO_PASSIVO para exportação, caso exista
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
    # Filtra apenas as colunas existentes no DataFrame
    cols_for_csv = [c for c in cols_for_csv if c in df_temp.columns]
    df_temp = df_temp[cols_for_csv]
    
    # Renomeia colunas para uma versão amigável
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
        <h3>JUSTIÇA FEDERAL EM PERNAMBUCO - JUIZADOS ESPECIAIS FEDERAIS</h3>
    </div>
    """, unsafe_allow_html=True)
    
    # Upload de arquivo (AGORA MÚLTIPLOS)
    st.markdown("### 📁 Upload dos Arquivos CSV do PJE")
    
    uploaded_files = st.file_uploader(
        "Selecione um ou mais arquivos CSV exportados do PJE (separador: ponto e vírgula)",
        type=['csv'],
        accept_multiple_files=True
    )
    
    if uploaded_files:
        
        # --- Lógica de Leitura e Unificação de Múltiplos Arquivos ---
        all_dfs = []
        
        for uploaded_file in uploaded_files:
            try:
                # Tenta ler com a codificação padrão e delimitador
                # ** CORREÇÃO REFORÇADA: Força o formato DMY (Dia/Mês/Ano) na leitura inicial **
                df = pd.read_csv(uploaded_file, delimiter=';', encoding='utf-8', dayfirst=True)
            except UnicodeDecodeError:
                # Tenta ler com Latin-1 se o UTF-8 falhar
                try:
                    df = pd.read_csv(uploaded_file, delimiter=';', encoding='latin-1', dayfirst=True)
                except Exception as e:
                    st.warning(f"⚠️ Não foi possível ler o arquivo **{uploaded_file.name}**. Pulando. (Erro: {e})")
                    continue
            except pd.errors.ParserError:
                 st.warning(f"⚠️ Erro de leitura no arquivo **{uploaded_file.name}**. Verifique se o separador é o ponto e vírgula (;). Pulando.")
                 continue
            except Exception as e:
                st.warning(f"⚠️ Erro inesperado ao ler **{uploaded_file.name}**. Pulando. (Erro: {e})")
                continue
                
            df_padronizado = mapear_e_padronizar_colunas(df.copy())
            
            if 'NUMERO_PROCESSO' in df_padronizado.columns:
                all_dfs.append(df_padronizado)
            else:
                st.error(f"❌ O arquivo **{uploaded_file.name}** não possui a coluna de Número do Processo. Não será incluído na análise.")

        if not all_dfs:
            st.error("Nenhum arquivo válido pôde ser lido para a análise.")
            return

        with st.spinner(f'Unificando dados de {len(all_dfs)} arquivo(s) e removendo duplicatas...'):
            df_unificado = pd.concat(all_dfs, ignore_index=True)
            df_final = df_unificado.drop_duplicates(subset=['NUMERO_PROCESSO'], keep='first')
        
        st.success(f"✅ Análise unificada de **{len(uploaded_files)}** arquivo(s). **{len(df_final)}** processos únicos encontrados.")
        
        # -- ADIÇÃO: Detectar se algum arquivo é do Painel Gerencial (apenas coluna DIAS_TRANSCORRIDOS)
        painel_gerencial_detectado = any('DIAS_TRANSCORRIDOS' in df.columns for df in all_dfs)
        if painel_gerencial_detectado:
            st.warning(
                "Observação sobre arquivos do Painel Gerencial:\n"
                "- O Painel Gerencial exporta apenas a coluna 'Dias' (DIAS_TRANSCORRIDOS), que é calculada considerando o horário exato da extração do painel.\n"
                "- Isso pode gerar discrepâncias em relação aos CSVs do tipo \"[JEF] CALCULO - ELABORAR\", que trazem a Data de Chegada (considerando apenas o dia, mês e ano).\n"
                "- Exemplo: se o painel for extraído hoje às 12:15 e um processo chegou ontem às 12:14, o painel indicará 0 dias de atraso; se chegou às 12:16, indicará 1 dia de atraso.\n"
                "- Portanto, é possível que haja diferenças no mês/dia calculados entre as duas fontes. O sistema usa a regra (HOJE()-1)-DIAS para estimar a data a partir do Painel Gerencial.\n"
                "  Considere essa limitação ao interpretar os resultados."
            )
        
        # 3. Processar dados (recalcula mês/dia, extrai servidor, etc.)
        with st.spinner('Processando dados...'):
            processed_df = processar_dados(df_final)
            
        # 4. Aplicar Atribuições Manuais 
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
                    with st.spinner("Gerando relatório..."):
                        pdf = criar_relatorio_visao_geral(stats, len(processed_df))
                        nome_arquivo = f"relatorio_visao_geral_{get_local_time().strftime('%Y%m%d_%H%M')}.pdf"
                        href = gerar_link_download_pdf(pdf, nome_arquivo)
                        if href:
                            st.markdown(href, unsafe_allow_html=True)
            
            col1, col2, col3, col4 = st.columns(4)
            
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
                    st.altair_chart(
                        criar_grafico_barras(
                            stats['polo_passivo'], 
                            "Distribuição por Polo Passivo (Top 10)", 
                            "Polo Passivo", 
                            "Quantidade"
                        ), 
                        use_container_width=True
                    )
                
                with st.expander("📊 Ver dados - Polo Passivo"):
                    st.dataframe(stats['polo_passivo'])
            
            with col2:
                if not stats['mes'].empty:
                    st.altair_chart(
                        criar_grafico_barras(
                            stats['mes'], 
                            "Distribuição por Mês (Data de Chegada)", 
                            "Mês", 
                            "Quantidade"
                        ), 
                        use_container_width=True
                    )
                
                with st.expander("📊 Ver dados - Distribuição por Mês"):
                    st.dataframe(stats['mes'])
            
            col3, col4 = st.columns(2)
            
            with col3:
                if not stats['servidor'].empty:
                    st.altair_chart(
                        criar_grafico_pizza_com_legenda(
                            stats['servidor'],
                            "Distribuição por Servidor"
                        ),
                        use_container_width=True
                    )
                
                with st.expander("📊 Ver dados - Distribuição por Servidor"):
                    st.dataframe(stats['servidor'])
            
            with col4:
                if not stats['assunto'].empty:
                    df_assunto = pd.DataFrame({
                        'Assunto': stats['assunto'].index,
                        'Quantidade': stats['assunto'].values
                    })
                    
                    chart_assunto = alt.Chart(df_assunto).mark_bar().encode(
                        x='Quantidade:Q',
                        y=alt.Y('Assunto:N', sort='-x', title='Assunto'),
                        tooltip=['Assunto', 'Quantidade']
                    ).properties(
                        title="Principais Assuntos (Top 10)",
                        width=600,
                        height=400
                    )
                    st.altair_chart(chart_assunto, use_container_width=True)
                
                with st.expander("📊 Ver dados - Principais Assuntos"):
                    st.dataframe(stats['assunto'])

        # --- Tab 2: Estatísticas ---
        with tab2:
            st.markdown("### 📈 Estatísticas Detalhadas")
            
            col1, col2 = st.columns([3, 1])
            with col2:
                if st.button("📄 Gerar Relatório - Estatísticas", key="relatorio_estatisticas"):
                    with st.spinner("Gerando relatório..."):
                        pdf = criar_relatorio_estatisticas(stats)
                        nome_arquivo = f"relatorio_estatisticas_{get_local_time().strftime('%Y%m%d_%H%M')}.pdf"
                        href = gerar_link_download_pdf(pdf, nome_arquivo)
                        if href:
                            st.markdown(href, unsafe_allow_html=True)
            
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
            
            mes_options = []
            if 'mes' in processed_df.columns:
                mes_options = sorted(processed_df['mes'].dropna().unique())
                
            assunto_options = []
            if 'ASSUNTO_PRINCIPAL' in processed_df.columns:
                assunto_options = sorted(processed_df['ASSUNTO_PRINCIPAL'].dropna().unique())
                
            polo_passivo_options = []
            if 'POLO_PASSIVO' in processed_df.columns:
                polo_passivo_options = sorted(processed_df['POLO_PASSIVO'].dropna().unique())
            
            vara_options = []
            if 'vara' in processed_df.columns:
                vara_options = sorted(processed_df['vara'].unique())
            
            with col1:
                servidor_filter = st.multiselect(
                    "Filtrar por Servidor",
                    options=servidor_options,
                    default=None
                )
                
                mes_filter = st.multiselect(
                    "Filtrar por Mês (Chegada)",
                    options=mes_options, 
                    default=None
                )
            
            with col2:
                polo_passivo_filter = st.multiselect(
                    "Filtrar por Polo Passivo",
                    options=polo_passivo_options,
                    default=None
                )
                
                assunto_filter = st.multiselect(
                    "Filtrar por Assunto",
                    options=assunto_options,
                    default=None
                )
            
            with col3:
                vara_filter = st.multiselect(
                    "Filtrar por Vara",
                    options=vara_options,
                    default=None
                )
            
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
                    with st.spinner("Gerando relatório..."):
                        try:
                            pdf = criar_relatorio_filtros(display_filtered, filtros_texto)
                            nome_arquivo = f"relatorio_filtros_{get_local_time().strftime('%Y%m%d_%H%M')}.pdf"
                            href = gerar_link_download_pdf(pdf, nome_arquivo)
                            if href:
                                st.markdown(href, unsafe_allow_html=True)
                            else:
                                st.error("Erro ao gerar o relatório PDF")
                        except Exception as e:
                            st.error(f"Erro ao gerar PDF: {e}")
            
            else:
                st.warning("Nenhum processo encontrado com os filtros aplicados.")

        # --- Tab 4: Atribuição Manual ---
        with tab4:
            st.markdown("### ✍️ Atribuição Manual de Servidores")
            
            processos_sem_etiqueta = processed_df[
                (processed_df['servidor'].isin(["Sem etiqueta", "Não atribuído"])) 
            ].copy()
            
            processos_ja_atribuidos = st.session_state.atribuicoes_servidores['NUMERO_PROCESSO'].tolist() if not st.session_state.atribuicoes_servidores.empty else []
            processos_disponiveis = processos_sem_etiqueta[
                ~processos_sem_etiqueta['NUMERO_PROCESSO'].isin(processos_ja_atribuidos)
            ]
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("#### 📋 Processos para Atribuição")
                st.markdown(f"**Processos sem servidor atribuído:** {len(processos_disponiveis)}")
                
                
                # ... (Restante da função main para a Tab 4)
                if not processos_disponiveis.empty:
                    # Filtra os 10 mais antigos
                    processos_para_atribuir = processos_disponiveis.sort_values(
                        by=['data_chegada_obj', 'NUMERO_PROCESSO'], 
                        ascending=[True, True]
                    ).head(10).copy()
                    
                    # Exibir agora com Polo Passivo e Vara
                    cols_to_show = [
                        'NUMERO_PROCESSO', 'POLO_PASSIVO', 'vara', 'data_chegada_formatada', 'DIAS', 'ASSUNTO_PRINCIPAL'
                    ]
                    cols_to_show = [c for c in cols_to_show if c in processos_para_atribuir.columns]
                    
                    display_table = processos_para_atribuir[cols_to_show].rename(columns={
                        'NUMERO_PROCESSO': 'Nº Processo',
                        'POLO_PASSIVO': 'Polo Passivo',
                        'vara': 'Vara',
                        'data_chegada_formatada': 'Data Chegada',
                        'DIAS': 'Dias',
                        'ASSUNTO_PRINCIPAL': 'Assunto Principal'
                    })
                    
                    st.dataframe(display_table, use_container_width=True)
                    
                    st.markdown("---")
                    
                    st.markdown("#### Atribuir em Lote")
                    processos_selecionados = st.multiselect(
                        "Selecione o(s) N° Processo(s) a serem atribuídos:",
                        options=processos_para_atribuir['NUMERO_PROCESSO'].tolist(),
                        key='multiselect_atribuicao'
                    )
                    
                    servidor_selecionado = st.selectbox(
                        "Selecione o Servidor:",
                        options=[""] + SERVIDORES_DISPONIVEIS,
                        key='selectbox_servidor'
                    )
                    
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
                            
                            # Remove as atribuições antigas para os processos selecionados, se existirem
                            st.session_state.atribuicoes_servidores = st.session_state.atribuicoes_servidores[
                                ~st.session_state.atribuicoes_servidores['NUMERO_PROCESSO'].isin(processos_selecionados)
                            ]
                            
                            # Adiciona as novas atribuições
                            st.session_state.atribuicoes_servidores = pd.concat([
                                st.session_state.atribuicoes_servidores, 
                                novas_atribuicoes_df
                            ], ignore_index=True)
                            
                            st.success(f"**{len(processos_selecionados)}** processos atribuídos a **{servidor_selecionado}**.")
                            st.rerun()
                        else:
                            st.warning("Selecione os processos e o servidor.")
                else:
                    st.info("Todos os processos sem etiqueta foram atribuídos manualmente ou não há dados.")
                
            with col2:
                st.markdown("#### Histórico de Atribuições Manuais")
                st.markdown(f"**Total de Atribuições Manuais:** {len(st.session_state.atribuicoes_servidores)}")
                
                if not st.session_state.atribuicoes_servidores.empty:
                    df_historico = st.session_state.atribuicoes_servidores.copy()
                    
                    # Garantir que as colunas existem antes de tentar renomear e exibir
                    cols_to_display = ['NUMERO_PROCESSO', 'servidor', 'data_atribuicao']
                    df_historico = df_historico.filter(items=cols_to_display)

                    if not df_historico.empty:
                        df_historico.columns = ['Nº Processo', 'Servidor', 'Data Atribuição']
                        st.dataframe(df_historico, use_container_width=True)
                        
                        st.markdown("---")
                        
                        # Botão de download das atribuições
                        csv_atribuicoes = gerar_csv_atribuicoes(st.session_state.atribuicoes_servidores)
                        if csv_atribuicoes:
                             st.download_button(
                                "📥 Baixar Atribuições Manuais (CSV)",
                                data=csv_atribuicoes,
                                file_name=f"atribuicoes_manuais_{get_local_time().strftime('%Y%m%d_%H%M')}.csv",
                                mime='text/csv'
                            )
                        
                        # Botão para limpar atribuições
                        if st.button("🗑️ Limpar todas Atribuições Manuais", help="Isso apagará todas as atribuições salvas na sessão."):
                            st.session_state.atribuicoes_servidores = pd.DataFrame(columns=[
                                'NUMERO_PROCESSO', 'vara', 'ORGAO_JULGADOR', 'servidor', 'data_atribuicao', 'POLO_ATIVO', 'ASSUNTO_PRINCIPAL'
                            ])
                            st.success("Atribuições manuais limpas. Recarregando...")
                            st.rerun()

main()
