import streamlit as st
import pandas as pd
import pdfplumber
import re
from datetime import datetime, timedelta
import io
import json
import pickle
from pathlib import Path
import numpy as np
from typing import Optional, Dict, List
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ============================================
# MÓDULO 1: CONFIGURAÇÕES E PREFERÊNCIAS
# ============================================

class ConfiguradorUsuario:
    """Gerencia as configurações e preferências do usuário"""
    
    def __init__(self):
        self.config_file = "user_config.json"
        self.rubricas_favoritas_file = "rubricas_favoritas.pkl"
        self.indices_file = "indices_correcao.json"
        self.templates_file = "templates_relatorios.json"
    
    def salvar_configuracao(self, config: Dict):
        """Salva configurações do usuário"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            return True
        except:
            return False
    
    def carregar_configuracao(self) -> Dict:
        """Carrega configurações do usuário"""
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
        """Salva rubricas favoritas do usuário"""
        try:
            with open(self.rubricas_favoritas_file, 'wb') as f:
                pickle.dump(rubricas, f)
            return True
        except:
            return False
    
    def carregar_rubricas_favoritas(self) -> List[str]:
        """Carrega rubricas favoritas do usuário"""
        try:
            with open(self.rubricas_favoritas_file, 'rb') as f:
                return pickle.load(f)
        except:
            return []
    
    def adicionar_rubrica_favorita(self, rubrica: str):
        """Adiciona uma rubrica à lista de favoritos"""
        favoritas = self.carregar_rubricas_favoritas()
        if rubrica not in favoritas:
            favoritas.append(rubrica)
            self.salvar_rubricas_favoritas(favoritas)
    
    def remover_rubrica_favorita(self, rubrica: str):
        """Remove uma rubrica da lista de favoritos"""
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
        """Carrega dados históricos do IPCA (exemplo simplificado)"""
        # Em produção, carregaria de API ou banco de dados
        return {
            '2020-01': 0.21, '2020-02': 0.25, '2020-03': 0.07,
            '2020-12': 4.52, '2021-12': 10.06, '2022-12': 5.79,
            '2023-12': 4.62, '2024-12': 3.50  # exemplos
        }
    
    def carregar_indice_inpc(self) -> Dict[str, float]:
        """Carrega dados históricos do INPC"""
        return {
            '2020-12': 4.23, '2021-12': 10.16, '2022-12': 5.93,
            '2023-12': 4.48, '2024-12': 3.30
        }
    
    def carregar_indice_igpm(self) -> Dict[str, float]:
        """Carrega dados históricos do IGP-M"""
        return {
            '2020-12': 23.14, '2021-12': 17.78, '2022-12': -5.20,
            '2023-12': 3.74, '2024-12': 2.50
        }
    
    def carregar_indice_selic(self) -> Dict[str, float]:
        """Carrega dados históricos da SELIC"""
        return {
            '2020-12': 2.00, '2021-12': 9.25, '2022-12': 13.75,
            '2023-12': 11.75, '2024-12': 10.50
        }
    
    def corrigir_valor(self, valor: float, data_original: str, data_correcao: str, 
                      indice: str = 'IPCA') -> float:
        """
        Corrige um valor monetário usando índice escolhido
        
        Args:
            valor: Valor original
            data_original: Data no formato 'MM/AAAA'
            data_correcao: Data para correção no formato 'MM/AAAA'
            indice: Índice a ser usado ('IPCA', 'INPC', 'IGPM', 'SELIC')
            
        Returns:
            Valor corrigido
        """
        try:
            if indice not in self.indices:
                return valor
            
            # Converte datas para formato YYYY-MM
            mes_ano_orig = data_original.split('/')[1] + '-' + data_original.split('/')[0]
            mes_ano_corr = data_correcao.split('/')[1] + '-' + data_correcao.split('/')[0]
            
            # Busca acumulado do índice
            if mes_ano_corr in self.indices[indice] and mes_ano_orig in self.indices[indice]:
                fator_correcao = (1 + self.indices[indice][mes_ano_corr]/100) / \
                                (1 + self.indices[indice][mes_ano_orig]/100)
                return valor * fator_correcao
            
            return valor
        except:
            return valor
    
    def aplicar_correcao_dataframe(self, df: pd.DataFrame, data_correcao: str, 
                                  indice: str = 'IPCA') -> pd.DataFrame:
        """
        Aplica correção monetária a um DataFrame completo
        """
        df_corrigido = df.copy()
        
        # Converte valores para numérico
        extrator = ExtratorDemonstrativos()
        df_corrigido['Valor_Numerico'] = df_corrigido['Valor'].apply(
            lambda x: extrator.converter_valor_string(x) or 0
        )
        
        # Aplica correção
        df_corrigido['Valor_Corrigido'] = df_corrigido.apply(
            lambda row: self.corrigir_valor(
                row['Valor_Numerico'],
                row['Competencia'],
                data_correcao,
                indice
            ),
            axis=1
        )
        
        # Formata valores corrigidos
        df_corrigido['Valor_Corrigido_Formatado'] = df_corrigido['Valor_Corrigido'].apply(
            lambda x: f"{x:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
        )
        
        return df_corrigido

# ============================================
# MÓDULO 3: ANÁLISE COMPARATIVA
# ============================================

class AnalisadorComparativo:
    """Realiza análises comparativas entre anos e rubricas"""
    
    @staticmethod
    def comparar_evolucao_anual(df: pd.DataFrame, rubrica: str) -> pd.DataFrame:
        """
        Analisa evolução anual de uma rubrica específica
        """
        # Converte valores para numérico
        extrator = ExtratorDemonstrativos()
        df_numeric = df.copy()
        df_numeric['Valor_Numerico'] = df_numeric['Valor'].apply(
            lambda x: extrator.converter_valor_string(x) or 0
        )
        
        # Filtra pela rubrica
        df_rubrica = df_numeric[df_numeric['Discriminacao'] == rubrica].copy()
        
        if df_rubrica.empty:
            return pd.DataFrame()
        
        # Agrupa por ano e mês
        df_rubrica['Mes'] = df_rubrica['Competencia'].apply(lambda x: int(x.split('/')[0]))
        df_rubrica['Ano'] = df_rubrica['Competencia'].apply(lambda x: int(x.split('/')[1]))
        
        # Cria tabela pivô (anos x meses)
        pivot = df_rubrica.pivot_table(
            values='Valor_Numerico',
            index='Mes',
            columns='Ano',
            aggfunc='sum',
            fill_value=0
        )
        
        # Calcula variações
        resultado = pivot.copy()
        anos = sorted(pivot.columns)
        
        for i in range(1, len(anos)):
            ano_atual = anos[i]
            ano_anterior = anos[i-1]
            if ano_anterior in pivot.columns:
                resultado[f'Var_{ano_anterior}_{ano_atual}'] = (
                    (pivot[ano_atual] - pivot[ano_anterior]) / pivot[ano_anterior] * 100
                ).round(2)
        
        # Adiciona totais anuais
        resultado.loc['Total_Anual'] = pivot.sum()
        
        return resultado
    
    @staticmethod
    def analisar_composicao_descontos(df: pd.DataFrame, ano: str) -> Dict:
        """
        Analisa composição dos descontos em um ano específico
        """
        df_ano = df[(df['Ano'] == ano) & (df['Tipo'] == 'DESCONTO')].copy()
        
        if df_ano.empty:
            return {}
        
        # Converte valores
        extrator = ExtratorDemonstrativos()
        df_ano['Valor_Numerico'] = df_ano['Valor'].apply(
            lambda x: extrator.converter_valor_string(x) or 0
        )
        
        # Agrupa por rubrica
        composicao = df_ano.groupby('Discriminacao')['Valor_Numerico'].sum().sort_values(ascending=False)
        
        # Calcula percentuais
        total = composicao.sum()
        percentuais = (composicao / total * 100).round(2)
        
        return {
            'composicao': composicao.to_dict(),
            'percentuais': percentuais.to_dict(),
            'total_ano': total,
            'top_5': composicao.head(5).to_dict()
        }
    
    @staticmethod
    def criar_relatorio_comparativo(df: pd.DataFrame, rubricas_selecionadas: List[str]) -> Dict:
        """
        Cria relatório comparativo para múltiplas rubricas
        """
        relatorio = {}
        
        for rubrica in rubricas_selecionadas:
            df_rubrica = df[df['Discriminacao'] == rubrica].copy()
            
            if not df_rubrica.empty:
                # Converte valores
                extrator = ExtratorDemonstrativos()
                df_rubrica['Valor_Numerico'] = df_rubrica['Valor'].apply(
                    lambda x: extrator.converter_valor_string(x) or 0
                )
                
                # Agrupa por ano
                dados_anuais = df_rubrica.groupby('Ano')['Valor_Numerico'].agg(['sum', 'mean', 'count'])
                
                relatorio[rubrica] = {
                    'total_por_ano': dados_anuais['sum'].to_dict(),
                    'media_mensal': dados_anuais['mean'].to_dict(),
                    'ocorrencias': dados_anuais['count'].to_dict()
                }
        
        return relatorio

# ============================================
# MÓDULO 4: TEMPLATES DE RELATÓRIOS
# ============================================

class TemplateRelatorios:
    """Gerencia templates de relatórios personalizados"""
    
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
            },
            'auditoria_financeira': {
                'nome': 'Auditoria Financeira',
                'descricao': 'Relatório completo para auditoria',
                'colunas': ['Discriminacao', 'Valor', 'Competencia', 'Ano', 'Tipo', 'Pagina'],
                'agrupamento': [],
                'filtros_padrao': {},
                'graficos': ['todos']
            }
        }
    
    def aplicar_template(self, df: pd.DataFrame, template_id: str) -> pd.DataFrame:
        """
        Aplica um template ao DataFrame
        """
        if template_id not in self.templates:
            return df
        
        template = self.templates[template_id]
        df_resultado = df.copy()
        
        # Aplica filtros padrão
        for coluna, valores in template.get('filtros_padrao', {}).items():
            if coluna in df_resultado.columns and valores:
                df_resultado = df_resultado[df_resultado[coluna].isin(valores)]
        
        # Seleciona colunas
        colunas_template = template.get('colunas', [])
        colunas_disponiveis = [c for c in colunas_template if c in df_resultado.columns]
        
        if colunas_disponiveis:
            df_resultado = df_resultado[colunas_disponiveis]
        
        # Aplica agrupamento se especificado
        agrupamento = template.get('agrupamento', [])
        if agrupamento and 'Valor' in df_resultado.columns:
            # Converte valores para numérico
            extrator = ExtratorDemonstrativos()
            df_resultado['Valor_Numerico'] = df_resultado['Valor'].apply(
                lambda x: extrator.converter_valor_string(x) or 0
            )
            
            df_agrupado = df_resultado.groupby(agrupamento)['Valor_Numerico'].sum().reset_index()
            df_agrupado['Valor'] = df_agrupado['Valor_Numerico'].apply(
                lambda x: f"{x:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
            )
            
            df_resultado = df_agrupado.drop(columns=['Valor_Numerico'])
        
        return df_resultado
    
    def gerar_relatorio_template(self, df: pd.DataFrame, template_id: str) -> Dict:
        """
        Gera relatório completo baseado em template
        """
        resultado = {
            'template': self.templates.get(template_id, {}),
            'dados': None,
            'estatisticas': {},
            'recomendacoes': []
        }
        
        # Aplica template
        df_template = self.aplicar_template(df, template_id)
        resultado['dados'] = df_template
        
        # Calcula estatísticas
        if not df_template.empty and 'Valor' in df_template.columns:
            extrator = ExtratorDemonstrativos()
            df_template['Valor_Numerico'] = df_template['Valor'].apply(
                lambda x: extrator.converter_valor_string(x) or 0
            )
            
            resultado['estatisticas'] = {
                'total_registros': len(df_template),
                'valor_total': df_template['Valor_Numerico'].sum(),
                'valor_medio': df_template['Valor_Numerico'].mean(),
                'valor_maximo': df_template['Valor_Numerico'].max(),
                'valor_minimo': df_template['Valor_Numerico'].min(),
                'rubricas_unicas': df_template['Discriminacao'].nunique() if 'Discriminacao' in df_template.columns else 0
            }
            
            # Gera recomendações baseadas nos dados
            resultado['recomendacoes'] = self.gerar_recomendacoes(df_template)
        
        return resultado
    
    def gerar_recomendacoes(self, df: pd.DataFrame) -> List[str]:
        """
        Gera recomendações automáticas baseadas nos dados
        """
        recomendacoes = []
        
        if df.empty:
            return recomendacoes
        
        # Exemplo de recomendações simples
        if 'Tipo' in df.columns:
            tipos = df['Tipo'].unique()
            if len(tipos) == 1:
                recomendacoes.append(f"Foco em {tipos[0]} - considere analisar o outro tipo para visão completa")
        
        if 'Ano' in df.columns:
            anos = df['Ano'].unique()
            if len(anos) > 1:
                recomendacoes.append(f"Dados de {len(anos)} anos disponíveis para análise comparativa")
        
        return recomendacoes

# ============================================
# MÓDULO PRINCIPAL (CÓDIGO ORIGINAL MODIFICADO)
# ============================================

class ExtratorDemonstrativos:
    """Classe para extrair dados de demonstrativos financeiros em PDF"""
    
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
    
    def formatar_valor_brasileiro(self, valor: float) -> str:
        """Formata valor float para string no padrão brasileiro 1.234,56"""
        return f"{valor:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
    
    def converter_valor_string(self, valor_str: str) -> Optional[float]:
        """Converte string de valor brasileiro para float"""
        try:
            valor_str = re.sub(r'[^\d,\.]', '', str(valor_str))
            
            if re.match(r'^\d+,\d{1,2}$', valor_str):
                return float(valor_str.replace('.', '').replace(',', '.'))
            
            if re.match(r'^\d{1,3}(?:\.\d{3})*,\d{2}$', valor_str):
                return float(valor_str.replace('.', '').replace(',', '.'))
            
            return float(valor_str.replace(',', '.'))
        except:
            return None
    
    def extrair_ano_referencia_robusto(self, texto: str, pagina_num: int) -> Optional[str]:
        """Extrai o ano de referência do texto do demonstrativo"""
        if not texto:
            return None
        
        linhas = texto.split('\n')
        
        for i, linha in enumerate(linhas):
            linha_limpa = linha.strip()
            
            padrao_exato = re.search(r'ANO\s+REFER[EÊ]NCIA\s*[:\s]*(\d{4})\b', linha_limpa, re.IGNORECASE)
            if padrao_exato:
                return padrao_exato.group(1)
            
            if 'ANO REFER' in linha_limpa.upper():
                if i + 1 < len(linhas):
                    prox_linha = linhas[i + 1].strip()
                    ano_match = re.search(r'\b(\d{4})\b', prox_linha)
                    if ano_match:
                        return ano_match.group(1)
        
        return None
    
    def processar_pdf(self, pdf_file, extrair_proventos: bool = True, extrair_descontos: bool = True) -> pd.DataFrame:
        """Processa o PDF e extrai dados"""
        
        dados = []
        
        with pdfplumber.open(pdf_file) as pdf:
            for pagina_num, pagina in enumerate(pdf.pages, 1):
                texto = pagina.extract_text()
                
                if not texto or 'DEMONSTRATIVO' not in texto.upper():
                    continue
                
                ano = self.extrair_ano_referencia_robusto(texto, pagina_num)
                if not ano:
                    continue
                
                tabelas = pagina.extract_tables()
                
                if not tabelas:
                    continue
                
                for tabela in tabelas:
                    if not tabela or len(tabela) < 3:
                        continue
                    
                    meses_colunas = {}
                    
                    for linha in tabela:
                        if not linha:
                            continue
                        
                        linha_str = ' '.join([str(cell) for cell in linha if cell])
                        
                        for mes_nome, mes_num in self.meses_map.items():
                            if mes_nome in linha_str.upper():
                                for col_idx, cell in enumerate(linha):
                                    if cell:
                                        cell_str = str(cell).strip().upper()
                                        for mn, mn_num in self.meses_map.items():
                                            if mn in cell_str:
                                                meses_colunas[col_idx] = mn_num
                                break
                        
                        if meses_colunas:
                            break
                    
                    if not meses_colunas:
                        continue
                    
                    inicio_rendimentos = None
                    inicio_descontos = None
                    
                    for linha_idx, linha in enumerate(tabela):
                        if not linha:
                            continue
                        
                        linha_str = ' '.join([str(cell) for cell in linha if cell])
                        
                        if 'RENDIMENTOS' in linha_str.upper() and inicio_rendimentos is None:
                            inicio_rendimentos = linha_idx
                        elif 'DESCONTOS' in linha_str.upper() and inicio_descontos is None:
                            inicio_descontos = linha_idx
                    
                    if extrair_proventos and inicio_rendimentos is not None:
                        dados.extend(
                            self.processar_secao_tabela(
                                tabela, inicio_rendimentos, inicio_descontos,
                                meses_colunas, ano, pagina_num, 'RENDIMENTO'
                            )
                        )
                    
                    if extrair_descontos and inicio_descontos is not None:
                        fim_descontos = len(tabela)
                        for linha_idx in range(inicio_descontos + 1, len(tabela)):
                            linha_str = ' '.join([str(cell) for cell in tabela[linha_idx] if cell])
                            if 'TOTAL' in linha_str.upper() or 'RENDIMENTOS' in linha_str.upper():
                                fim_descontos = linha_idx
                                break
                        
                        dados.extend(
                            self.processar_secao_tabela(
                                tabela, inicio_descontos, fim_descontos,
                                meses_colunas, ano, pagina_num, 'DESCONTO'
                            )
                        )
        
        if dados:
            df = pd.DataFrame(dados)
            df = df.drop_duplicates()
            df = df.sort_values(['Ano', 'Pagina', 'Tipo', 'Discriminacao'])
            return df
        else:
            return pd.DataFrame(columns=['Discriminacao', 'Valor', 'Competencia', 'Pagina', 'Ano', 'Tipo'])
    
    def processar_secao_tabela(self, tabela, inicio_secao, fim_secao, meses_colunas, ano, pagina_num, tipo):
        """Processa uma seção específica da tabela"""
        dados_secao = []
        
        for linha_idx in range(inicio_secao + 1, fim_secao):
            linha = tabela[linha_idx]
            
            if not linha or not any(linha):
                continue
            
            linha_str = ' '.join([str(cell) for cell in linha if cell])
            if 'RENDIMENTOS' in linha_str.upper() or 'DESCONTOS' in linha_str.upper() or 'TOTAL' in linha_str.upper():
                break
            
            discriminacao = None
            for cell in linha:
                if cell and cell.strip():
                    cell_str = str(cell).strip()
                    if (not re.match(r'^[\d\.,]+$', cell_str) and 
                        not any(mes in cell_str.upper() for mes in self.meses_map.keys()) and
                        cell_str not in ['RENDIMENTOS', 'DESCONTOS']):
                        discriminacao = cell_str
                        break
            
            if not discriminacao:
                continue
            
            for col_idx, mes_num in meses_colunas.items():
                if col_idx < len(linha) and linha[col_idx]:
                    valor_str = str(linha[col_idx]).strip()
                    
                    if re.match(r'^[\d\.,\s]+$', valor_str):
                        valor_float = self.converter_valor_string(valor_str)
                        
                        if valor_float is not None and valor_float != 0:
                            valor_formatado = self.formatar_valor_brasileiro(valor_float)
                            competencia = f"{mes_num:02d}/{ano}"
                            
                            dados_secao.append({
                                'Discriminacao': discriminacao,
                                'Valor': valor_formatado,
                                'Competencia': competencia,
                                'Pagina': pagina_num,
                                'Ano': ano,
                                'Tipo': tipo
                            })
        
        return dados_secao

# ============================================
# INTERFACE STREAMLOT - VERSÃO SUPER POTENTE
# ============================================

def inicializar_sessao():
    """Inicializa as variáveis de sessão"""
    sessao_vars = [
        'dados_extraidos', 'df_filtrado', 'arquivo_processado',
        'configurador', 'corretor', 'analisador', 'template_manager',
        'modo_avancado', 'indice_correcao', 'data_correcao',
        'template_selecionado', 'rubricas_analise_comparativa'
    ]
    
    for var in sessao_vars:
        if var not in st.session_state:
            st.session_state[var] = None
    
    # Inicializa módulos
    if st.session_state.configurador is None:
        st.session_state.configurador = ConfiguradorUsuario()
    if st.session_state.corretor is None:
        st.session_state.corretor = CorrecaoMonetaria()
    if st.session_state.analisador is None:
        st.session_state.analisador = AnalisadorComparativo()
    if st.session_state.template_manager is None:
        st.session_state.template_manager = TemplateRelatorios()

def main():
    st.set_page_config(
        page_title="Extrator Avançado de Demonstrativos",
        page_icon="🚀",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Inicializar sessão
    inicializar_sessao()
    
    # Barra lateral com configurações
    with st.sidebar:
        st.title("⚙️ Configurações")
        
        # Modo de operação
        st.session_state.modo_avancado = st.checkbox(
            "Modo Avançado",
            value=st.session_state.modo_avancado or False,
            help="Ativa funcionalidades avançadas"
        )
        
        # Configurações salvas
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
        
        # Salvar configurações
        if st.button("💾 Salvar Configurações", use_container_width=True):
            nova_config = {
                'extrair_proventos': extrair_proventos,
                'extrair_descontos': extrair_descontos,
                'modo_avancado': st.session_state.modo_avancado,
                'indice_preferido': st.session_state.indice_correcao or 'IPCA'
            }
            st.session_state.configurador.salvar_configuracao(nova_config)
            st.success("Configurações salvas!")
    
    # Área principal
    st.title("🚀 Extrator Avançado de Demonstrativos Financeiros")
    
    # Upload do arquivo
    st.subheader("📁 Upload do Arquivo")
    uploaded_file = st.file_uploader(
        "Faça upload do PDF com os demonstrativos",
        type="pdf",
        key="uploader_principal"
    )
    
    # Processamento do arquivo
    if uploaded_file is not None:
        if (st.session_state.arquivo_processado is None or 
            st.session_state.arquivo_processado.name != uploaded_file.name):
            st.session_state.arquivo_processado = uploaded_file
            st.session_state.dados_extraidos = None
            st.session_state.df_filtrado = None
        
        st.success(f"✅ Arquivo carregado: {uploaded_file.name}")
        
        # Processamento inicial
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
                            
                            # Aplica correção monetária se solicitado
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
                            
                            st.success(f"✅ {len(df)} registros extraídos!")
                            st.rerun()
                        else:
                            st.error("⚠️ Nenhum dado extraído.")
                            
                    except Exception as e:
                        st.error(f"❌ Erro: {str(e)}")
        
        # Interface com dados processados
        if st.session_state.dados_extraidos is not None:
            df = st.session_state.df_filtrado or st.session_state.dados_extraidos
            
            # Criar abas principais
            tab1, tab2, tab3, tab4, tab5 = st.tabs([
                "📊 Dashboard", 
                "🎯 Filtros", 
                "📈 Análises", 
                "📋 Relatórios",
                "📥 Exportar"
            ])
            
            with tab1:
                # Estatísticas rápidas
                st.subheader("📊 Visão Geral")
                
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Total Registros", len(df))
                with col2:
                    st.metric("Anos", df['Ano'].nunique())
                with col3:
                    st.metric("Rubricas", df['Discriminacao'].nunique())
                with col4:
                    st.metric("Valor Total", self.formatar_valor_total(df))
                
                # Dados principais
                st.subheader("📋 Dados Extraídos")
                st.dataframe(
                    df[['Discriminacao', 'Valor', 'Competencia', 'Ano', 'Tipo']].head(50),
                    use_container_width=True,
                    hide_index=True,
                    height=300
                )
            
            with tab2:
                st.subheader("🎯 Filtros Avançados")
                
                # Filtros básicos
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
                
                # Rubricas com favoritos
                st.write("**Rubricas:**")
                rubricas_disponiveis = sorted(df['Discriminacao'].unique())
                favoritas = st.session_state.configurador.carregar_rubricas_favoritas()
                
                # Separar favoritas das demais
                rubricas_favoritas = [r for r in rubricas_disponiveis if r in favoritas]
                outras_rubricas = [r for r in rubricas_disponiveis if r not in favoritas]
                
                # Interface para gerenciar favoritos
                col_fav1, col_fav2 = st.columns([3, 1])
                with col_fav1:
                    rubrica_selecionada = st.selectbox(
                        "Selecionar rubrica:",
                        rubricas_disponiveis
                    )
                
                with col_fav2:
                    st.write("⠀")  # Espaçamento
                    if rubrica_selecionada in favoritas:
                        if st.button("❌ Remover"):
                            st.session_state.configurador.remover_rubrica_favorita(rubrica_selecionada)
                            st.rerun()
                    else:
                        if st.button("⭐ Favoritar"):
                            st.session_state.configurador.adicionar_rubrica_favorita(rubrica_selecionada)
                            st.rerun()
                
                # Seleção de rubricas (favoritas primeiro)
                todas_rubricas = rubricas_favoritas + outras_rubricas
                rubricas_selecionadas = st.multiselect(
                    "Selecionar rubricas para análise:",
                    todas_rubricas,
                    default=todas_rubricas[:min(10, len(todas_rubricas))]
                )
                
                # Botões de ação
                col_btn1, col_btn2 = st.columns(2)
                with col_btn1:
                    if st.button("✅ Aplicar Filtros", type="primary", use_container_width=True):
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
                    if st.button("🗑️ Limpar Filtros", use_container_width=True):
                        st.session_state.df_filtrado = st.session_state.dados_extraidos.copy()
                        st.success("✅ Filtros removidos!")
                        st.rerun()
            
            with tab3:
                st.subheader("📈 Análises Avançadas")
                
                if st.session_state.modo_avancado:
                    # Análise comparativa
                    st.write("### 🔄 Análise Comparativa")
                    
                    rubrica_comparar = st.selectbox(
                        "Selecione uma rubrica para análise de evolução:",
                        sorted(df['Discriminacao'].unique())
                    )
                    
                    if rubrica_comparar:
                        analise = st.session_state.analisador.comparar_evolucao_anual(df, rubrica_comparar)
                        
                        if not analise.empty:
                            st.write(f"**Evolução de {rubrica_comparar}:**")
                            st.dataframe(analise, use_container_width=True)
                            
                            # Gráfico de evolução
                            fig = px.line(
                                analise.drop('Total_Anual', errors='ignore'),
                                title=f"Evolução Mensal - {rubrica_comparar}",
                                labels={'value': 'Valor', 'variable': 'Ano'}
                            )
                            st.plotly_chart(fig, use_container_width=True)
                    
                    # Composição de descontos
                    st.write("### 🧩 Composição de Descontos")
                    
                    ano_analise = st.selectbox(
                        "Selecione o ano para análise:",
                        sorted(df['Ano'].unique())
                    )
                    
                    if st.button("Analisar Composição", key="analise_comp"):
                        composicao = st.session_state.analisador.analisar_composicao_descontos(df, ano_analise)
                        
                        if composicao:
                            # Gráfico de pizza
                            df_composicao = pd.DataFrame({
                                'Rubrica': list(composicao['percentuais'].keys()),
                                'Percentual': list(composicao['percentuais'].values())
                            })
                            
                            fig = px.pie(
                                df_composicao.head(10),
                                values='Percentual',
                                names='Rubrica',
                                title=f"Composição dos Descontos - {ano_analise}"
                            )
                            st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("🔓 Ative o Modo Avançado na barra lateral para acessar estas análises.")
            
            with tab4:
                st.subheader("📋 Relatórios Personalizados")
                
                if st.session_state.modo_avancado:
                    # Template selecionado
                    if st.session_state.template_selecionado:
                        template = st.session_state.template_manager.templates[
                            st.session_state.template_selecionado
                        ]
                        
                        st.write(f"### 📄 {template['nome']}")
                        st.write(template['descricao'])
                        
                        if st.button("🔄 Gerar Relatório", type="primary"):
                            with st.spinner("Gerando relatório..."):
                                relatorio = st.session_state.template_manager.gerar_relatorio_template(
                                    df, 
                                    st.session_state.template_selecionado
                                )
                                
                                # Mostrar dados
                                st.write("#### 📊 Dados do Relatório")
                                st.dataframe(
                                    relatorio['dados'],
                                    use_container_width=True,
                                    height=300
                                )
                                
                                # Estatísticas
                                st.write("#### 📈 Estatísticas")
                                stats = relatorio['estatisticas']
                                col_s1, col_s2, col_s3 = st.columns(3)
                                with col_s1:
                                    st.metric("Total Registros", stats.get('total_registros', 0))
                                with col_s2:
                                    st.metric("Valor Total", self.formatar_valor_brasileiro(stats.get('valor_total', 0)))
                                with col_s3:
                                    st.metric("Rubricas Únicas", stats.get('rubricas_unicas', 0))
                                
                                # Recomendações
                                if relatorio['recomendacoes']:
                                    st.write("#### 💡 Recomendações")
                                    for rec in relatorio['recomendacoes']:
                                        st.info(f"• {rec}")
                else:
                    st.info("🔓 Ative o Modo Avançado para acessar templates de relatórios.")
            
            with tab5:
                st.subheader("📥 Exportação de Dados")
                
                # Opções de exportação
                formato = st.radio(
                    "Formato:",
                    ["Excel (XLSX)", "CSV", "JSON"],
                    horizontal=True
                )
                
                # Dados extras para exportação
                incluir_analises = st.checkbox("Incluir análises comparativas", value=True)
                incluir_correcao = st.checkbox("Incluir valores corrigidos", 
                                             value=st.session_state.indice_correcao != 'Nenhum')
                
                # Botões de exportação
                col_e1, col_e2, col_e3 = st.columns(3)
                
                with col_e1:
                    if st.button("💾 Exportar Dados", use_container_width=True):
                        self.exportar_dados(df, formato, uploaded_file.name)
                
                with col_e2:
                    if st.button("📊 Exportar + Análises", use_container_width=True):
                        self.exportar_com_analises(df, formato, uploaded_file.name)
                
                with col_e3:
                    if st.button("🔄 Novo Arquivo", type="secondary", use_container_width=True):
                        st.session_state.dados_extraidos = None
                        st.session_state.df_filtrado = None
                        st.session_state.arquivo_processado = None
                        st.rerun()
    
    else:
        # Tela inicial
        st.info("👆 Faça upload de um arquivo PDF para começar.")
        
        with st.expander("🚀 Funcionalidades Avançadas"):
            st.markdown("""
            ### 🌟 **NOVAS FUNCIONALIDADES:**
            
            1. **⭐ Rubricas Favoritas** - Salve suas rubricas mais usadas
            2. **💰 Correção Monetária** - Corrija valores com IPCA, INPC, IGPM, SELIC
            3. **📊 Análise Comparativa** - Compare evolução ano a ano
            4. **📋 Templates de Relatórios** - Relatórios pré-formatados
            5. **📈 Dashboard Interativo** - Visualizações avançadas
            
            ### 🔧 **Como usar:**
            1. Ative o **Modo Avançado** na barra lateral
            2. Configure seus índices preferidos
            3. Selecione templates de relatórios
            4. Filtre por rubricas favoritas
            5. Exporte com análises incluídas
            """)

    # Helper methods
    def formatar_valor_total(self, df):
        """Formata o valor total para exibição"""
        extrator = ExtratorDemonstrativos()
        valores = df['Valor'].apply(lambda x: extrator.converter_valor_string(x) or 0)
        total = valores.sum()
        return f"R$ {total:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')

    def formatar_valor_brasileiro(self, valor):
        """Formata valor para padrão brasileiro"""
        return f"{valor:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')

    def exportar_dados(self, df, formato, nome_arquivo):
        """Exporta dados no formato selecionado"""
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
        
        elif formato == "JSON":
            json_data = df.to_json(orient='records', force_ascii=False)
            st.download_button(
                label="⬇️ Baixar JSON",
                data=json_data,
                file_name=f"demonstrativos_{timestamp}.json",
                mime="application/json"
            )

    def exportar_com_analises(self, df, formato, nome_arquivo):
        """Exporta dados com análises incluídas"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        if formato == "Excel (XLSX)":
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                # Dados principais
                df.to_excel(writer, index=False, sheet_name='Dados')
                
                # Análises comparativas (se houver dados)
                if 'Discriminacao' in df.columns:
                    # Top 10 rubricas para análise
                    top_rubricas = df['Discriminacao'].value_counts().head(10).index.tolist()
                    
                    for rubrica in top_rubricas[:3]:  # Limita a 3 análises
                        analise = st.session_state.analisador.comparar_evolucao_anual(df, rubrica)
                        if not analise.empty:
                            analise.to_excel(writer, sheet_name=f"Análise_{rubrica[:20]}")
                
                # Composição por ano
                anos = sorted(df['Ano'].unique())
                composicoes = []
                for ano in anos:
                    comp = st.session_state.analisador.analisar_composicao_descontos(df, ano)
                    if comp:
                        df_comp = pd.DataFrame({
                            'Rubrica': list(comp['composicao'].keys()),
                            'Valor': list(comp['composicao'].values()),
                            'Percentual': list(comp['percentuais'].values())
                        })
                        df_comp.to_excel(writer, index=False, sheet_name=f"Comp_{ano}")
            
            buffer.seek(0)
            st.download_button(
                label="⬇️ Baixar Excel com Análises",
                data=buffer,
                file_name=f"demonstrativos_analises_{timestamp}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

if __name__ == "__main__":
    main()
