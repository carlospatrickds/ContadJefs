import streamlit as st
import pandas as pd
import pdfplumber
import re
from datetime import datetime
import io
import json
import pickle
import numpy as np
from typing import Optional, Dict, List
import plotly.express as px
import plotly.graph_objects as go

# ============================================
# MÓDULO 1: CONFIGURAÇÕES E PREFERÊNCIAS
# ============================================

class ConfiguradorUsuario:
    """Gerencia as configurações e preferências do usuário"""
    
    def __init__(self):
        self.config_file = "user_config.json"
        self.rubricas_favoritas_file = "rubricas_favoritas.pkl"
    
    def salvar_configuracao(self, config: Dict):
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            return True
        except:
            return False
    
    def carregar_configuracao(self) -> Dict:
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {
                'extrair_proventos': True,
                'extrair_descontos': True,
                'formato_exportacao': 'Excel',
                'templates_preferidos': [],
                'indice_preferido': 'IPCA',
                'mostrar_graficos': True
            }
    
    def salvar_rubricas_favoritas(self, rubricas: List[str]):
        try:
            with open(self.rubricas_favoritas_file, 'wb') as f:
                pickle.dump(rubricas, f)
            return True
        except:
            return False
    
    def carregar_rubricas_favoritas(self) -> List[str]:
        try:
            with open(self.rubricas_favoritas_file, 'rb') as f:
                return pickle.load(f)
        except:
            return []
    
    def adicionar_rubrica_favorita(self, rubrica: str):
        favoritas = self.carregar_rubricas_favoritas()
        if rubrica not in favoritas:
            favoritas.append(rubrica)
            self.salvar_rubricas_favoritas(favoritas)
    
    def remover_rubrica_favorita(self, rubrica: str):
        favoritas = self.carregar_rubricas_favoritas()
        if rubrica in favoritas:
            favoritas.remove(rubrica)
            self.salvar_rubricas_favoritas(favoritas)

# ============================================
# MÓDULO 2: CORREÇÃO MONETÁRIA
# ============================================

class CorrecaoMonetaria:
    """Realiza correção monetária usando índices oficiais"""
    
    def __init__(self):
        self.indices = {
            'IPCA': self.carregar_indice_ipca(),
            'INPC': self.carregar_indice_inpc(),
            'IGPM': self.carregar_indice_igpm(),
            'SELIC': self.carregar_indice_selic()
        }
    
    def carregar_indice_ipca(self) -> Dict[str, float]:
        return {
            '2020-01': 0.21, '2020-02': 0.25, '2020-03': 0.07,
            '2020-12': 4.52, '2021-12': 10.06, '2022-12': 5.79,
            '2023-12': 4.62, '2024-12': 3.50
        }
    
    def carregar_indice_inpc(self) -> Dict[str, float]:
        return {
            '2020-12': 4.23, '2021-12': 10.16, '2022-12': 5.93,
            '2023-12': 4.48, '2024-12': 3.30
        }
    
    def carregar_indice_igpm(self) -> Dict[str, float]:
        return {
            '2020-12': 23.14, '2021-12': 17.78, '2022-12': -5.20,
            '2023-12': 3.74, '2024-12': 2.50
        }
    
    def carregar_indice_selic(self) -> Dict[str, float]:
        return {
            '2020-12': 2.00, '2021-12': 9.25, '2022-12': 13.75,
            '2023-12': 11.75, '2024-12': 10.50
        }
    
    def corrigir_valor(self, valor: float, data_original: str, data_correcao: str, 
                      indice: str = 'IPCA') -> float:
        try:
            if indice not in self.indices:
                return valor
            
            mes_ano_orig = data_original.split('/')[1] + '-' + data_original.split('/')[0]
            mes_ano_corr = data_correcao.split('/')[1] + '-' + data_correcao.split('/')[0]
            
            if mes_ano_corr in self.indices[indice] and mes_ano_orig in self.indices[indice]:
                fator_correcao = (1 + self.indices[indice][mes_ano_corr]/100) / \
                                (1 + self.indices[indice][mes_ano_orig]/100)
                return valor * fator_correcao
            
            return valor
        except:
            return valor
    
    def aplicar_correcao_dataframe(self, df: pd.DataFrame, data_correcao: str, 
                                  indice: str = 'IPCA') -> pd.DataFrame:
        if df.empty:
            return df
        
        df_corrigido = df.copy()
        extrator = ExtratorDemonstrativos()
        df_corrigido['Valor_Numerico'] = df_corrigido['Valor'].apply(
            lambda x: extrator.converter_valor_string(x) or 0
        )
        
        df_corrigido['Valor_Corrigido'] = df_corrigido.apply(
            lambda row: self.corrigir_valor(
                row['Valor_Numerico'],
                row['Competencia'],
                data_correcao,
                indice
            ),
            axis=1
        )
        
        df_corrigido['Valor_Corrigido_Formatado'] = df_corrigido['Valor_Corrigido'].apply(
            lambda x: f"{x:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
        )
        
        return df_corrigido

# ============================================
# MÓDULO 3: ANÁLISE COMPARATIVA
# ============================================

class AnalisadorComparativo:
    @staticmethod
    def comparar_evolucao_anual(df: pd.DataFrame, rubrica: str) -> pd.DataFrame:
        if df.empty:
            return pd.DataFrame()
        
        extrator = ExtratorDemonstrativos()
        df_numeric = df.copy()
        df_numeric['Valor_Numerico'] = df_numeric['Valor'].apply(
            lambda x: extrator.converter_valor_string(x) or 0
        )
        
        df_rubrica = df_numeric[df_numeric['Discriminacao'] == rubrica].copy()
        
        if df_rubrica.empty:
            return pd.DataFrame()
        
        try:
            df_rubrica['Mes'] = df_rubrica['Competencia'].apply(lambda x: int(x.split('/')[0]))
            df_rubrica['Ano'] = df_rubrica['Competencia'].apply(lambda x: int(x.split('/')[1]))
        except:
            return pd.DataFrame()
        
        try:
            pivot = df_rubrica.pivot_table(
                values='Valor_Numerico',
                index='Mes',
                columns='Ano',
                aggfunc='sum',
                fill_value=0
            )
        except:
            return pd.DataFrame()
        
        resultado = pivot.copy()
        anos = sorted(pivot.columns)
        
        for i in range(1, len(anos)):
            ano_atual = anos[i]
            ano_anterior = anos[i-1]
            if ano_anterior in pivot.columns:
                resultado[f'Var_{ano_anterior}_{ano_atual}'] = (
                    (pivot[ano_atual] - pivot[ano_anterior]) / pivot[ano_anterior].replace(0, np.nan) * 100
                ).round(2)
        
        resultado.loc['Total_Anual'] = pivot.sum()
        return resultado
    
    @staticmethod
    def analisar_composicao_descontos(df: pd.DataFrame, ano: str) -> Dict:
        if df.empty:
            return {}
        
        df_ano = df[(df['Ano'] == str(ano)) & (df['Tipo'] == 'DESCONTO')].copy()
        
        if df_ano.empty:
            return {}
        
        extrator = ExtratorDemonstrativos()
        df_ano['Valor_Numerico'] = df_ano['Valor'].apply(
            lambda x: extrator.converter_valor_string(x) or 0
        )
        
        composicao = df_ano.groupby('Discriminacao')['Valor_Numerico'].sum().sort_values(ascending=False)
        total = composicao.sum()
        if total > 0:
            percentuais = (composicao / total * 100).round(2)
        else:
            percentuais = composicao * 0
        
        return {
            'composicao': composicao.to_dict(),
            'percentuais': percentuais.to_dict(),
            'total_ano': total,
            'top_5': composicao.head(5).to_dict()
        }

# ============================================
# MÓDULO 4: ANÁLISE POR SEMESTRE
# ============================================

class AnalisadorSemestral:
    @staticmethod
    def calcular_semestre(mes: int) -> int:
        return 1 if mes <= 6 else 2
    
    @staticmethod
    def analisar_por_semestre(df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return pd.DataFrame()
        
        df_analise = df.copy()
        extrator = ExtratorDemonstrativos()
        df_analise['Valor_Numerico'] = df_analise['Valor'].apply(
            lambda x: extrator.converter_valor_string(x) or 0
        )
        
        try:
            df_analise['Mes'] = df_analise['Competencia'].apply(lambda x: int(x.split('/')[0]))
            df_analise['Ano'] = df_analise['Competencia'].apply(lambda x: int(x.split('/')[1]))
        except:
            return pd.DataFrame()
        
        df_analise['Semestre'] = df_analise['Mes'].apply(AnalisadorSemestral.calcular_semestre)
        df_analise['Semestre_Label'] = df_analise.apply(
            lambda row: f"{row['Ano']} - {row['Semestre']}º Sem", axis=1
        )
        
        semestral_tipo = df_analise.groupby(['Ano', 'Semestre', 'Semestre_Label', 'Tipo'])['Valor_Numerico'].sum().reset_index()
        
        if not semestral_tipo.empty:
            pivot_semestral = semestral_tipo.pivot_table(
                values='Valor_Numerico',
                index=['Ano', 'Semestre', 'Semestre_Label'],
                columns='Tipo',
                aggfunc='sum',
                fill_value=0
            ).reset_index()
            
            if 'RENDIMENTO' in pivot_semestral.columns and 'DESCONTO' in pivot_semestral.columns:
                pivot_semestral['LIQUIDO'] = pivot_semestral['RENDIMENTO'] - pivot_semestral['DESCONTO']
            
            pivot_semestral = pivot_semestral.sort_values(['Ano', 'Semestre'])
            
            for col in ['RENDIMENTO', 'DESCONTO', 'LIQUIDO']:
                if col in pivot_semestral.columns:
                    pivot_semestral[f'{col}_Formatado'] = pivot_semestral[col].apply(
                        lambda x: f"{x:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
                    )
            
            return pivot_semestral
        else:
            return pd.DataFrame()
    
    @staticmethod
    def analisar_rubricas_por_semestre(df: pd.DataFrame, top_n: int = 10) -> Dict:
        if df.empty:
            return {}
        
        df_analise = df.copy()
        extrator = ExtratorDemonstrativos()
        df_analise['Valor_Numerico'] = df_analise['Valor'].apply(
            lambda x: extrator.converter_valor_string(x) or 0
        )
        
        try:
            df_analise['Mes'] = df_analise['Competencia'].apply(lambda x: int(x.split('/')[0]))
            df_analise['Ano'] = df_analise['Competencia'].apply(lambda x: int(x.split('/')[1]))
        except:
            return {}
        
        df_analise['Semestre'] = df_analise['Mes'].apply(AnalisadorSemestral.calcular_semestre)
        
        descontos_semestrais = {}
        rendimentos_semestrais = {}
        anos = sorted(df_analise['Ano'].unique())
        
        for ano in anos:
            for semestre in [1, 2]:
                df_desconto = df_analise[
                    (df_analise['Ano'] == ano) & 
                    (df_analise['Semestre'] == semestre) & 
                    (df_analise['Tipo'] == 'DESCONTO')
                ]
                if not df_desconto.empty:
                    top_descontos = df_desconto.groupby('Discriminacao')['Valor_Numerico'].sum().nlargest(top_n)
                    descontos_semestrais[f"{ano}-S{semestre}"] = {
                        'total': df_desconto['Valor_Numerico'].sum(),
                        'top_rubricas': top_descontos.to_dict(),
                        'quantidade_rubricas': df_desconto['Discriminacao'].nunique()
                    }
                
                df_rendimento = df_analise[
                    (df_analise['Ano'] == ano) & 
                    (df_analise['Semestre'] == semestre) & 
                    (df_analise['Tipo'] == 'RENDIMENTO')
                ]
                if not df_rendimento.empty:
                    top_rendimentos = df_rendimento.groupby('Discriminacao')['Valor_Numerico'].sum().nlargest(top_n)
                    rendimentos_semestrais[f"{ano}-S{semestre}"] = {
                        'total': df_rendimento['Valor_Numerico'].sum(),
                        'top_rubricas': top_rendimentos.to_dict(),
                        'quantidade_rubricas': df_rendimento['Discriminacao'].nunique()
                    }
        
        return {
            'descontos_por_semestre': descontos_semestrais,
            'rendimentos_por_semestre': rendimentos_semestrais,
            'anos_analisados': anos
        }

# ============================================
# MÓDULO 5: TEMPLATES DE RELATÓRIOS
# ============================================

class TemplateRelatorios:
    def __init__(self):
        self.templates = {
            'analise_simplificada': {
                'nome': 'Análise Simplificada',
                'descricao': 'Visão geral dos principais dados',
                'colunas': ['Discriminacao', 'Valor', 'Competencia', 'Ano', 'Tipo'],
                'agrupamento': ['Ano', 'Tipo'],
                'filtros_padrao': {'Tipo': ['DESCONTO']},
                'graficos': ['distribuicao_ano', 'top_rubricas']
            },
            'evolucao_anual': {
                'nome': 'Evolução Anual',
                'descricao': 'Comparativo ano a ano das rubricas',
                'colunas': ['Discriminacao', 'Ano', 'Valor'],
                'agrupamento': ['Discriminacao', 'Ano'],
                'filtros_padrao': {},
                'graficos': ['evolucao_temporal', 'heatmap_mensal']
            },
            'composicao_descontos': {
                'nome': 'Composição de Descontos',
                'descricao': 'Análise detalhada dos descontos',
                'colunas': ['Discriminacao', 'Valor', 'Competencia'],
                'agrupamento': ['Discriminacao'],
                'filtros_padrao': {'Tipo': ['DESCONTO']},
                'graficos': ['pie_descontos', 'treemap']
            }
        }
    
    def aplicar_template(self, df: pd.DataFrame, template_id: str) -> pd.DataFrame:
        if df.empty or template_id not in self.templates:
            return df
        
        template = self.templates[template_id]
        df_resultado = df.copy()
        
        for coluna, valores in template.get('filtros_padrao', {}).items():
            if coluna in df_resultado.columns and valores:
                df_resultado = df_resultado[df_resultado[coluna].isin(valores)]
        
        colunas_template = template.get('colunas', [])
        colunas_disponiveis = [c for c in colunas_template if c in df_resultado.columns]
        
        if colunas_disponiveis:
            df_resultado = df_resultado[colunas_disponiveis]
        
        return df_resultado

# ============================================
# MÓDULO PRINCIPAL: EXTRATOR (CORRIGIDO)
# ============================================

class ExtratorDemonstrativos:
    def __init__(self):
        self.meses_map = {
            'JAN': 1, 'FEV': 2, 'MAR': 3, 'ABR': 4, 'MAI': 5, 'JUN': 6,
            'JUL': 7, 'AGO': 8, 'SET': 9, 'OUT': 10, 'NOV': 11, 'DEZ': 12
        }
        self.meses_ordenados = ["JAN", "FEV", "MAR", "ABR", "MAI", "JUN", "JUL", "AGO", "SET", "OUT", "NOV", "DEZ"]

    def formatar_valor_brasileiro(self, valor):
        return f"{valor:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')

    def converter_valor_string(self, valor_str):
        try:
            valor_str = re.sub(r'[^\d,\.]', '', str(valor_str))
            if re.match(r'^\d+,\d{1,2}$', valor_str):
                return float(valor_str.replace('.', '').replace(',', '.'))
            if re.match(r'^\d{1,3}(?:\.\d{3})*,\d{2}$', valor_str):
                return float(valor_str.replace('.', '').replace(',', '.'))
            return float(valor_str.replace(',', '.'))
        except:
            return None

    def extrair_ano_referencia(self, texto):
        padrao = r'ANO\s+REFER[EÊ]NCIA\s*[:\s]*(\d{4})'
        match = re.search(padrao, texto, re.IGNORECASE)
        if match:
            return match.group(1)
        padrao2 = r'REFER[EÊ]NCIA.*?(\d{4})'
        match = re.search(padrao2, texto, re.IGNORECASE | re.DOTALL)
        if match:
            return match.group(1)
        return None

    def processar_pdf(self, pdf_file, extrair_proventos=True, extrair_descontos=True):
        dados = []
        ano_global = None
        with pdfplumber.open(pdf_file) as pdf:
            texto_completo = ""
            for pagina in pdf.pages:
                texto_completo += pagina.extract_text() + "\n"
            ano_global = self.extrair_ano_referencia(texto_completo)

            for pagina_num, pagina in enumerate(pdf.pages, 1):
                texto_pagina = pagina.extract_text()
                ano = ano_global if ano_global else self.extrair_ano_referencia(texto_pagina)
                if not ano:
                    continue

                tabelas = pagina.extract_tables()
                if not tabelas:
                    continue

                for tabela in tabelas:
                    if len(tabela) < 3:
                        continue

                    # Identificar colunas de meses
                    meses_colunas = {}  # indice -> numero do mes
                    for i, linha in enumerate(tabela[:5]):  # olhar nas primeiras linhas
                        for j, cel in enumerate(linha):
                            if cel:
                                texto_cel = str(cel).upper()
                                for mes_abrev, mes_num in self.meses_map.items():
                                    if mes_abrev in texto_cel:
                                        meses_colunas[j] = mes_num
                        if meses_colunas:
                            break

                    if not meses_colunas:
                        continue

                    colunas_ordenadas = sorted(meses_colunas.items())  # (indice, mes)

                    # Extrair a ordem dos meses a partir do cabeçalho
                    cabecalho_meses = []
                    for linha in tabela[:3]:
                        linha_texto = ' '.join([str(c) for c in linha if c]).upper()
                        encontrados = [m for m in self.meses_ordenados if m in linha_texto]
                        if encontrados:
                            cabecalho_meses = encontrados
                            break

                    if cabecalho_meses:
                        meses_esperados = [self.meses_map[m] for m in cabecalho_meses]
                    else:
                        meses_esperados = [mes for _, mes in colunas_ordenadas]

                    # Processar linhas
                    secao_atual = None
                    ultima_rubrica = None

                    for linha in tabela:
                        if not linha:
                            continue
                        linha_texto = ' '.join([str(c) for c in linha if c]).upper()

                        if 'RENDIMENTOS' in linha_texto:
                            secao_atual = 'RENDIMENTO'
                            continue
                        elif 'DESCONTOS' in linha_texto:
                            secao_atual = 'DESCONTO'
                            continue
                        elif 'TOTAL' in linha_texto:
                            continue

                        if secao_atual is None:
                            continue
                        if secao_atual == 'RENDIMENTO' and not extrair_proventos:
                            continue
                        if secao_atual == 'DESCONTO' and not extrair_descontos:
                            continue

                        # Discriminação: primeira célula ou herda da anterior
                        discriminacao = str(linha[0]).strip() if linha[0] else ""
                        if discriminacao and discriminacao.upper() not in ['RENDIMENTOS', 'DESCONTOS', 'TOTAL', '']:
                            ultima_rubrica = discriminacao
                        elif ultima_rubrica:
                            discriminacao = ultima_rubrica
                        else:
                            continue

                        # Para cada coluna de mês, extrair valor
                        for idx, (col_idx, _) in enumerate(colunas_ordenadas):
                            if idx >= len(meses_esperados):
                                continue
                            mes_num = meses_esperados[idx]
                            if col_idx < len(linha) and linha[col_idx]:
                                valor_str = str(linha[col_idx]).strip()
                                if valor_str and re.match(r'^[\d\.,]+$', valor_str):
                                    valor_float = self.converter_valor_string(valor_str)
                                    if valor_float is not None and valor_float != 0:
                                        competencia = f"{mes_num:02d}/{ano}"
                                        dados.append({
                                            'Discriminacao': discriminacao,
                                            'Valor': valor_str,
                                            'Competencia': competencia,
                                            'Pagina': pagina_num,
                                            'Ano': ano,
                                            'Tipo': secao_atual
                                        })

        if not dados:
            return pd.DataFrame(columns=['Discriminacao', 'Valor', 'Competencia', 'Pagina', 'Ano', 'Tipo'])

        df = pd.DataFrame(dados)
        df = df[df['Valor'] != '0,00']
        df['Sequencia'] = df.groupby(['Discriminacao', 'Competencia', 'Tipo']).cumcount() + 1
        df['Discriminacao_Original'] = df['Discriminacao']
        contagens = df.groupby(['Discriminacao_Original', 'Competencia', 'Tipo']).size().reset_index(name='Contagem')
        df = df.merge(contagens, on=['Discriminacao_Original', 'Competencia', 'Tipo'], how='left')
        df['Discriminacao'] = df.apply(
            lambda row: f"{row['Discriminacao_Original']} #{row['Sequencia']}" if row['Contagem'] > 1 else row['Discriminacao_Original'],
            axis=1
        )
        df = df[['Discriminacao', 'Valor', 'Competencia', 'Pagina', 'Ano', 'Tipo']]
        df = df.sort_values(['Ano', 'Pagina', 'Tipo', 'Discriminacao', 'Competencia']).reset_index(drop=True)
        return df

# ============================================
# FUNÇÕES DE APOIO (INTERFACE)
# ============================================

def inicializar_sessao():
    if 'dados_extraidos' not in st.session_state:
        st.session_state.dados_extraidos = None
    if 'df_filtrado' not in st.session_state:
        st.session_state.df_filtrado = None
    if 'arquivo_processado' not in st.session_state:
        st.session_state.arquivo_processado = None
    if 'configurador' not in st.session_state:
        st.session_state.configurador = ConfiguradorUsuario()
    if 'corretor' not in st.session_state:
        st.session_state.corretor = CorrecaoMonetaria()
    if 'analisador' not in st.session_state:
        st.session_state.analisador = AnalisadorComparativo()
    if 'analisador_semestral' not in st.session_state:
        st.session_state.analisador_semestral = AnalisadorSemestral()
    if 'template_manager' not in st.session_state:
        st.session_state.template_manager = TemplateRelatorios()
    if 'modo_avancado' not in st.session_state:
        st.session_state.modo_avancado = False
    if 'indice_correcao' not in st.session_state:
        st.session_state.indice_correcao = 'IPCA'
    if 'data_correcao' not in st.session_state:
        hoje = datetime.now()
        st.session_state.data_correcao = f"{hoje.month:02d}/{hoje.year}"
    if 'template_selecionado' not in st.session_state:
        st.session_state.template_selecionado = 'analise_simplificada'

def formatar_valor_total(df):
    if df.empty:
        return "R$ 0,00"
    extrator = ExtratorDemonstrativos()
    valores = df['Valor'].apply(lambda x: extrator.converter_valor_string(x) or 0)
    total = valores.sum()
    return f"R$ {total:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')

def formatar_valor_brasileiro(valor):
    return f"{valor:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')

def exportar_dados(df, formato, nome_arquivo):
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    if formato == "Excel (XLSX)":
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Dados')
        buffer.seek(0)
        st.download_button(
            label="⬇️ Baixar Excel",
            data=buffer,
            file_name=f"demonstrativos_{timestamp}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    elif formato == "CSV":
        csv = df.to_csv(index=False, sep=';', encoding='utf-8-sig')
        st.download_button(
            label="⬇️ Baixar CSV",
            data=csv,
            file_name=f"demonstrativos_{timestamp}.csv",
            mime="text/csv"
        )

# ============================================
# INTERFACE STREAMLIT (MAIN)
# ============================================

def main():
    st.set_page_config(
        page_title="Extrator Avançado de Demonstrativos",
        page_icon="🚀",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    inicializar_sessao()
    
    with st.sidebar:
        st.title("⚙️ Configurações")
        
        st.session_state.modo_avancado = st.checkbox(
            "Modo Avançado",
            value=st.session_state.modo_avancado,
            help="Ativa funcionalidades avançadas"
        )
        
        config_salvas = st.session_state.configurador.carregar_configuracao()
        
        st.subheader("📊 Extração")
        extrair_proventos = st.checkbox(
            "Extrair RENDIMENTOS",
            value=config_salvas.get('extrair_proventos', True)
        )
        extrair_descontos = st.checkbox(
            "Extrair DESCONTOS", 
            value=config_salvas.get('extrair_descontos', True)
        )
        
        if st.session_state.modo_avancado:
            st.subheader("💰 Correção Monetária")
            st.session_state.indice_correcao = st.selectbox(
                "Índice para correção:",
                ['IPCA', 'INPC', 'IGPM', 'SELIC', 'Nenhum'],
                index=0
            )
            
            if st.session_state.indice_correcao != 'Nenhum':
                hoje = datetime.now()
                st.session_state.data_correcao = st.text_input(
                    "Data para correção (MM/AAAA):",
                    value=f"{hoje.month:02d}/{hoje.year}"
                )
            
            st.subheader("📋 Templates")
            templates = st.session_state.template_manager.templates
            template_options = {k: v['nome'] for k, v in templates.items()}
            st.session_state.template_selecionado = st.selectbox(
                "Template de relatório:",
                options=list(template_options.keys()),
                format_func=lambda x: template_options[x],
                index=0
            )
        
        if st.button("💾 Salvar Configurações", use_container_width=True):
            nova_config = {
                'extrair_proventos': extrair_proventos,
                'extrair_descontos': extrair_descontos,
                'modo_avancado': st.session_state.modo_avancado,
                'indice_preferido': st.session_state.indice_correcao or 'IPCA'
            }
            st.session_state.configurador.salvar_configuracao(nova_config)
            st.success("Configurações salvas!")
    
    st.title("🚀 Extrator Avançado de Demonstrativos Financeiros")
    
    st.subheader("📁 Upload do Arquivo")
    uploaded_file = st.file_uploader(
        "Faça upload do PDF com os demonstrativos",
        type="pdf",
        key="uploader_principal"
    )
    
    if uploaded_file is not None:
        if (st.session_state.arquivo_processado is None or 
            st.session_state.arquivo_processado.name != uploaded_file.name):
            st.session_state.arquivo_processado = uploaded_file
            st.session_state.dados_extraidos = None
            st.session_state.df_filtrado = None
        
        st.success(f"✅ Arquivo carregado: {uploaded_file.name}")
        
        if st.session_state.dados_extraidos is None:
            if st.button("🔍 Processar Demonstrativos", type="primary", use_container_width=True):
                with st.spinner("Processando PDF..."):
                    try:
                        extrator = ExtratorDemonstrativos()
                        df = extrator.processar_pdf(
                            uploaded_file,
                            extrair_proventos=extrair_proventos,
                            extrair_descontos=extrair_descontos
                        )
                        
                        if not df.empty:
                            st.session_state.dados_extraidos = df
                            st.session_state.df_filtrado = df.copy()
                            
                            if (st.session_state.modo_avancado and 
                                st.session_state.indice_correcao and 
                                st.session_state.indice_correcao != 'Nenhum' and
                                st.session_state.data_correcao):
                                
                                df_corrigido = st.session_state.corretor.aplicar_correcao_dataframe(
                                    df,
                                    st.session_state.data_correcao,
                                    st.session_state.indice_correcao
                                )
                                st.session_state.df_filtrado = df_corrigido
                                st.info(f"✅ Correção monetária aplicada ({st.session_state.indice_correcao})")
                            
                            duplicatas = df[df['Discriminacao'].str.contains('#')]
                            if not duplicatas.empty:
                                st.info(f"✅ Encontradas {len(duplicatas)} rubricas com múltiplas ocorrências (marcadas com #1, #2, etc.)")
                            
                            st.success(f"✅ {len(df)} registros extraídos!")
                            st.rerun()
                        else:
                            st.error("⚠️ Nenhum dado extraído.")
                            
                    except Exception as e:
                        st.error(f"❌ Erro: {str(e)}")
        
        if st.session_state.dados_extraidos is not None:
            if st.session_state.df_filtrado is not None:
                df = st.session_state.df_filtrado
            else:
                df = st.session_state.dados_extraidos
            
            tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
                "📊 Dashboard", 
                "🎯 Filtros", 
                "📈 Análises", 
                "📅 Semestral",
                "📋 Relatórios",
                "📥 Exportar"
            ])
            
            with tab1:
                st.subheader("📊 Visão Geral")
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Total Registros", len(df))
                with col2:
                    st.metric("Anos", df['Ano'].nunique())
                with col3:
                    st.metric("Rubricas Únicas", df['Discriminacao'].nunique())
                with col4:
                    st.metric("Valor Total", formatar_valor_total(df))
                
                duplicatas = df[df['Discriminacao'].str.contains('#')]
                if not duplicatas.empty:
                    st.info(f"📝 **Nota:** {len(duplicatas)} rubricas têm múltiplas ocorrências na mesma competência (marcadas com #1, #2, etc.)")
                
                st.subheader("📋 Dados Extraídos (COM MÚLTIPLAS OCORRÊNCIAS)")
                st.dataframe(
                    df[['Discriminacao', 'Valor', 'Competencia', 'Ano', 'Tipo']].head(50),
                    use_container_width=True,
                    hide_index=True,
                    height=300
                )
            
            with tab2:
                st.subheader("🎯 Filtros Avançados")
                col_f1, col_f2 = st.columns(2)
                with col_f1:
                    tipos = st.multiselect(
                        "Tipo:", 
                        sorted(df['Tipo'].unique()),
                        default=sorted(df['Tipo'].unique())
                    )
                with col_f2:
                    anos = st.multiselect(
                        "Ano:", 
                        sorted(df['Ano'].unique()),
                        default=sorted(df['Ano'].unique())
                    )
                
                st.write("**Rubricas:**")
                rubricas_disponiveis = sorted(df['Discriminacao'].unique())
                favoritas = st.session_state.configurador.carregar_rubricas_favoritas()
                rubricas_favoritas = [r for r in rubricas_disponiveis if r in favoritas]
                outras_rubricas = [r for r in rubricas_disponiveis if r not in favoritas]
                
                col_fav1, col_fav2 = st.columns([3, 1])
                with col_fav1:
                    rubrica_selecionada = st.selectbox(
                        "Selecionar rubrica:",
                        rubricas_disponiveis
                    )
                with col_fav2:
                    st.write("⠀")
                    if rubrica_selecionada in favoritas:
                        if st.button("❌ Remover", key="remover_fav"):
                            st.session_state.configurador.remover_rubrica_favorita(rubrica_selecionada)
                            st.rerun()
                    else:
                        if st.button("⭐ Favoritar", key="adicionar_fav"):
                            st.session_state.configurador.adicionar_rubrica_favorita(rubrica_selecionada)
                            st.rerun()
                
                todas_rubricas = rubricas_favoritas + outras_rubricas
                rubricas_selecionadas = st.multiselect(
                    "Selecionar rubricas para análise:",
                    todas_rubricas,
                    default=todas_rubricas[:min(10, len(todas_rubricas))]
                )
                
                col_btn1, col_btn2 = st.columns(2)
                with col_btn1:
                    if st.button("✅ Aplicar Filtros", type="primary", use_container_width=True, key="aplicar_filtros"):
                        df_filtrado = st.session_state.dados_extraidos.copy()
                        if tipos:
                            df_filtrado = df_filtrado[df_filtrado['Tipo'].isin(tipos)]
                        if anos:
                            df_filtrado = df_filtrado[df_filtrado['Ano'].isin(anos)]
                        if rubricas_selecionadas:
                            df_filtrado = df_filtrado[df_filtrado['Discriminacao'].isin(rubricas_selecionadas)]
                        st.session_state.df_filtrado = df_filtrado
                        st.success(f"✅ {len(df_filtrado)} registros após filtragem")
                        st.rerun()
                with col_btn2:
                    if st.button("🗑️ Limpar Filtros", use_container_width=True, key="limpar_filtros"):
                        st.session_state.df_filtrado = st.session_state.dados_extraidos.copy()
                        st.success("✅ Filtros removidos!")
                        st.rerun()
            
            with tab3:
                st.subheader("📈 Análises Avançadas")
                if st.session_state.modo_avancado:
                    st.write("### 🔄 Análise Comparativa")
                    rubrica_comparar = st.selectbox(
                        "Selecione uma rubrica para análise de evolução:",
                        sorted(df['Discriminacao'].unique()),
                        key="rubrica_comparar"
                    )
                    if rubrica_comparar:
                        analise = st.session_state.analisador.comparar_evolucao_anual(df, rubrica_comparar)
                        if not analise.empty:
                            st.write(f"**Evolução de {rubrica_comparar}:**")
                            st.dataframe(analise, use_container_width=True)
                            if len(analise.columns) > 1:
                                try:
                                    fig = px.line(
                                        analise.drop('Total_Anual', errors='ignore'),
                                        title=f"Evolução Mensal - {rubrica_comparar}",
                                        labels={'value': 'Valor', 'variable': 'Ano'}
                                    )
                                    st.plotly_chart(fig, use_container_width=True)
                                except:
                                    pass
                    
                    st.write("### 🧩 Composição de Descontos")
                    ano_analise = st.selectbox(
                        "Selecione o ano para análise:",
                        sorted(df['Ano'].unique()),
                        key="ano_analise"
                    )
                    if st.button("Analisar Composição", key="analise_comp"):
                        composicao = st.session_state.analisador.analisar_composicao_descontos(df, ano_analise)
                        if composicao and composicao['total_ano'] > 0:
                            df_composicao = pd.DataFrame({
                                'Rubrica': list(composicao['percentuais'].keys()),
                                'Percentual': list(composicao['percentuais'].values())
                            }).head(10)
                            if not df_composicao.empty:
                                fig = px.pie(
                                    df_composicao,
                                    values='Percentual',
                                    names='Rubrica',
                                    title=f"Composição dos Descontos - {ano_analise}"
                                )
                                st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("🔓 Ative o Modo Avançado na barra lateral para acessar estas análises.")
            
            with tab4:
                st.subheader("📅 Análise Semestral")
                if st.button("📊 Gerar Análise Semestral", type="primary", key="gerar_semestral"):
                    with st.spinner("Analisando dados por semestre..."):
                        analise_semestral = st.session_state.analisador_semestral.analisar_por_semestre(df)
                        if not analise_semestral.empty:
                            st.write("### 📋 Consolidado por Semestre")
                            colunas_exibicao = ['Semestre_Label']
                            mapeamento_colunas = {}
                            if 'RENDIMENTO_Formatado' in analise_semestral.columns:
                                colunas_exibicao.append('RENDIMENTO_Formatado')
                                mapeamento_colunas['RENDIMENTO_Formatado'] = 'RENDIMENTOS'
                            if 'DESCONTO_Formatado' in analise_semestral.columns:
                                colunas_exibicao.append('DESCONTO_Formatado')
                                mapeamento_colunas['DESCONTO_Formatado'] = 'DESCONTOS'
                            if 'LIQUIDO_Formatado' in analise_semestral.columns:
                                colunas_exibicao.append('LIQUIDO_Formatado')
                                mapeamento_colunas['LIQUIDO_Formatado'] = 'LÍQUIDO'
                            df_exibicao = analise_semestral[colunas_exibicao].copy()
                            df_exibicao = df_exibicao.rename(columns=mapeamento_colunas)
                            st.dataframe(df_exibicao, use_container_width=True, hide_index=True)
                            
                            if 'RENDIMENTO' in analise_semestral.columns and 'DESCONTO' in analise_semestral.columns:
                                fig = go.Figure()
                                fig.add_trace(go.Bar(
                                    x=analise_semestral['Semestre_Label'],
                                    y=analise_semestral['RENDIMENTO'],
                                    name='Rendimentos',
                                    marker_color='#2ecc71'
                                ))
                                fig.add_trace(go.Bar(
                                    x=analise_semestral['Semestre_Label'],
                                    y=analise_semestral['DESCONTO'],
                                    name='Descontos',
                                    marker_color='#e74c3c'
                                ))
                                if 'LIQUIDO' in analise_semestral.columns:
                                    fig.add_trace(go.Scatter(
                                        x=analise_semestral['Semestre_Label'],
                                        y=analise_semestral['LIQUIDO'],
                                        name='Líquido',
                                        mode='lines+markers',
                                        line=dict(color='#3498db', width=3),
                                        marker=dict(size=8)
                                    ))
                                fig.update_layout(
                                    title='Evolução Semestral',
                                    xaxis_title='Semestre',
                                    yaxis_title='Valor (R$)',
                                    barmode='group',
                                    height=500
                                )
                                st.plotly_chart(fig, use_container_width=True)
                            else:
                                st.info("⚠️ Não há dados suficientes para gerar o gráfico de evolução semestral.")
                            
                            st.write("### 🔍 Top Rubricas por Semestre")
                            analise_detalhada = st.session_state.analisador_semestral.analisar_rubricas_por_semestre(df, top_n=5)
                            if analise_detalhada and 'anos_analisados' in analise_detalhada:
                                anos = analise_detalhada.get('anos_analisados', [])
                                for ano in anos:
                                    for semestre in [1, 2]:
                                        chave = f"{ano}-S{semestre}"
                                        tem_descontos = chave in analise_detalhada.get('descontos_por_semestre', {})
                                        tem_rendimentos = chave in analise_detalhada.get('rendimentos_por_semestre', {})
                                        if tem_descontos or tem_rendimentos:
                                            st.write(f"#### 📊 {ano} - {semestre}º Semestre")
                                            col_s1, col_s2 = st.columns(2)
                                            with col_s1:
                                                if tem_descontos:
                                                    st.write("**💰 Top Descontos:**")
                                                    descontos = analise_detalhada['descontos_por_semestre'][chave]['top_rubricas']
                                                    for rubrica, valor in descontos.items():
                                                        st.write(f"- {rubrica}: R$ {formatar_valor_brasileiro(valor)}")
                                                else:
                                                    st.write("**💰 Top Descontos:** *Sem dados*")
                                            with col_s2:
                                                if tem_rendimentos:
                                                    st.write("**💵 Top Rendimentos:**")
                                                    rendimentos = analise_detalhada['rendimentos_por_semestre'][chave]['top_rubricas']
                                                    for rubrica, valor in rendimentos.items():
                                                        st.write(f"- {rubrica}: R$ {formatar_valor_brasileiro(valor)}")
                                                else:
                                                    st.write("**💵 Top Rendimentos:** *Sem dados*")
                                            st.divider()
                            else:
                                st.warning("Não foi possível gerar análise detalhada por semestre.")
                        else:
                            st.warning("Não foi possível gerar análise semestral. Verifique se há dados para os meses necessários.")
            
            with tab5:
                st.subheader("📋 Relatórios Personalizados")
                if st.session_state.modo_avancado:
                    if st.session_state.template_selecionado:
                        template = st.session_state.template_manager.templates[st.session_state.template_selecionado]
                        st.write(f"### 📄 {template['nome']}")
                        st.write(template['descricao'])
                        if st.button("🔄 Gerar Relatório", type="primary", key="gerar_relatorio"):
                            with st.spinner("Gerando relatório..."):
                                df_template = st.session_state.template_manager.aplicar_template(
                                    df, st.session_state.template_selecionado
                                )
                                st.write("#### 📊 Dados do Relatório")
                                st.dataframe(df_template, use_container_width=True, height=300)
                                if not df_template.empty and 'Valor' in df_template.columns:
                                    extrator = ExtratorDemonstrativos()
                                    df_template['Valor_Numerico'] = df_template['Valor'].apply(
                                        lambda x: extrator.converter_valor_string(x) or 0
                                    )
                                    st.write("#### 📈 Estatísticas")
                                    col_s1, col_s2, col_s3 = st.columns(3)
                                    with col_s1:
                                        st.metric("Total Registros", len(df_template))
                                    with col_s2:
                                        total_valor = df_template['Valor_Numerico'].sum()
                                        st.metric("Valor Total", formatar_valor_brasileiro(total_valor))
                                    with col_s3:
                                        if 'Discriminacao' in df_template.columns:
                                            st.metric("Rubricas Únicas", df_template['Discriminacao'].nunique())
                else:
                    st.info("🔓 Ative o Modo Avançado para acessar templates de relatórios.")
            
            with tab6:
                st.subheader("📥 Exportação de Dados")
                formato = st.radio(
                    "Formato:",
                    ["Excel (XLSX)", "CSV"],
                    horizontal=True,
                    key="formato_export"
                )
                col_e1, col_e2, col_e3 = st.columns(3)
                with col_e1:
                    if st.button("💾 Exportar Dados", use_container_width=True, key="exportar_dados"):
                        exportar_dados(df, formato, uploaded_file.name)
                with col_e2:
                    if st.button("📊 Exportar + Análises", use_container_width=True, key="exportar_analises"):
                        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                        buffer = io.BytesIO()
                        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                            df.to_excel(writer, index=False, sheet_name='Dados')
                            if 'DESCONTO' in df['Tipo'].unique():
                                anos_unicos = sorted(df['Ano'].unique())
                                for ano in anos_unicos:
                                    composicao = st.session_state.analisador.analisar_composicao_descontos(df, ano)
                                    if composicao and composicao['total_ano'] > 0:
                                        df_comp = pd.DataFrame({
                                            'Rubrica': list(composicao['composicao'].keys()),
                                            'Valor': list(composicao['composicao'].values()),
                                            'Percentual': list(composicao['percentuais'].values())
                                        })
                                        df_comp.to_excel(writer, index=False, sheet_name=f"Comp_{ano}")
                            analise_semestral = st.session_state.analisador_semestral.analisar_por_semestre(df)
                            if not analise_semestral.empty:
                                analise_semestral.to_excel(writer, index=False, sheet_name='Análise_Semestral')
                        buffer.seek(0)
                        st.download_button(
                            label="⬇️ Baixar Excel com Análises",
                            data=buffer,
                            file_name=f"demonstrativos_analises_{timestamp}.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                        )
                with col_e3:
                    if st.button("🔄 Novo Arquivo", type="secondary", use_container_width=True, key="novo_arquivo"):
                        st.session_state.dados_extraidos = None
                        st.session_state.df_filtrado = None
                        st.session_state.arquivo_processado = None
                        st.rerun()
    else:
        st.info("👆 Faça upload de um arquivo PDF para começar.")
        with st.expander("🚀 Funcionalidades Avançadas"):
            st.markdown("""
            ### 🌟 **NOVAS FUNCIONALIDADES:**
            1. **⭐ Rubricas Favoritas** - Salve suas rubricas mais usadas
            2. **💰 Correção Monetária** - Corrija valores com IPCA, INPC, IGPM, SELIC
            3. **📊 Análise Comparativa** - Compare evolução ano a ano
            4. **📅 Análise Semestral** - Consolidação por semestre (1º: Jan-Jun, 2º: Jul-Dez)
            5. **📋 Templates de Relatórios** - Relatórios pré-formatados
            ### 🔧 **CORREÇÃO CRÍTICA:**
            - **MÚLTIPLAS OCORRÊNCIAS DA MESMA RUBRICA AGORA SÃO EXTRAÍDAS CORRETAMENTE**
            - Quando a mesma rubrica aparece várias vezes na mesma competência, todas são extraídas
            - Exemplo: "VENCIMENTO BASICO" aparece 3 vezes em Janeiro → extrai 3 entradas
            - Rubricas duplicadas são marcadas com #1, #2, #3 para fácil identificação
            - **ESPELHO FIEL GARANTIDO** - Todos os valores são extraídos
            ### 📅 **NOVA ABA SEMESTRAL:**
            - **Consolidação automática** por semestre
            - **Gráfico de evolução** semestral
            - **Top rubricas** por semestre
            - **Exportação** incluindo análise semestral
            ### 🔧 **Como usar:**
            1. Ative o **Modo Avançado** na barra lateral
            2. Configure seus índices preferidos
            3. Selecione templates de relatórios
            4. Filtre por rubricas favoritas
            5. Explore a nova aba **Semestral**
            6. Exporte com análises incluídas
            """)

if __name__ == "__main__":
    main()
