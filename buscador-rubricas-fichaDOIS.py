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
            '2023-12': 4.62, '2024-12': 3.50
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
        if df.empty:
            return df
        
        df_corrigido = df.copy()
        
        # Converte valores para numérico
        df_corrigido['Valor_Numerico'] = df_corrigido['Valor'].apply(
            lambda x: self.converter_valor_string_siape(x) or 0
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
    
    def converter_valor_string_siape(self, valor_str: str) -> Optional[float]:
        """Converte string de valor brasileiro para float (específico para Siape)"""
        try:
            if not valor_str or str(valor_str).strip() == '':
                return None
            
            # Remove espaços e caracteres não numéricos exceto pontos e vírgulas
            valor_str = str(valor_str).strip()
            valor_str = re.sub(r'[^\d,\.]', '', valor_str)
            
            # Se terminar com vírgula, pode ser formato brasileiro incompleto
            if valor_str.endswith(','):
                valor_str = valor_str[:-1]
            
            # Verifica se tem ponto como separador de milhar e vírgula como decimal
            if ',' in valor_str and '.' in valor_str:
                # Formato: 1.234,56
                valor_str = valor_str.replace('.', '').replace(',', '.')
            elif ',' in valor_str:
                # Formato: 1234,56
                valor_str = valor_str.replace(',', '.')
            
            return float(valor_str)
        except Exception as e:
            return None

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
        if df.empty:
            return pd.DataFrame()
        
        # Converte valores para numérico
        df_numeric = df.copy()
        df_numeric['Valor_Numerico'] = df_numeric['Valor'].apply(
            lambda x: converter_valor_string_siape(x) or 0
        )
        
        # Filtra pela rubrica
        df_rubrica = df_numeric[df_numeric['Discriminacao'] == rubrica].copy()
        
        if df_rubrica.empty:
            return pd.DataFrame()
        
        # Agrupa por ano e mês
        try:
            df_rubrica['Mes'] = df_rubrica['Competencia'].apply(lambda x: int(x.split('/')[0]))
            df_rubrica['Ano'] = df_rubrica['Competencia'].apply(lambda x: int(x.split('/')[1]))
        except:
            return pd.DataFrame()
        
        # Cria tabela pivô (anos x meses)
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
        
        # Calcula variações
        resultado = pivot.copy()
        anos = sorted(pivot.columns)
        
        for i in range(1, len(anos)):
            ano_atual = anos[i]
            ano_anterior = anos[i-1]
            if ano_anterior in pivot.columns:
                resultado[f'Var_{ano_anterior}_{ano_atual}'] = (
                    (pivot[ano_atual] - pivot[ano_anterior]) / pivot[ano_anterior].replace(0, np.nan) * 100
                ).round(2)
        
        # Adiciona totais anuais
        resultado.loc['Total_Anual'] = pivot.sum()
        
        return resultado
    
    @staticmethod
    def analisar_composicao_descontos(df: pd.DataFrame, ano: str) -> Dict:
        """
        Analisa composição dos descontos em um ano específico
        """
        if df.empty:
            return {}
        
        df_ano = df[(df['Ano'] == str(ano)) & (df['Tipo'] == 'DESCONTO')].copy()
        
        if df_ano.empty:
            return {}
        
        # Converte valores
        df_ano['Valor_Numerico'] = df_ano['Valor'].apply(
            lambda x: converter_valor_string_siape(x) or 0
        )
        
        # Agrupa por rubrica
        composicao = df_ano.groupby('Discriminacao')['Valor_Numerico'].sum().sort_values(ascending=False)
        
        # Calcula percentuais
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
# MÓDULO 4: TEMPLATES DE RELATÓRIOS
# ============================================

class TemplateRelatorios:
    """Gerencia templates de relatórios personalizados"""
    
    def __init__(self):
        self.templates = {
            'analise_simplificada': {
                'nome': 'Análise Simplificada',
                'descricao': 'Visão geral dos principais dados',
                'colunas': ['Codigo_Rubrica', 'Discriminacao', 'Valor', 'Competencia', 'Ano', 'Tipo', 'Pagina'],
                'agrupamento': ['Ano', 'Tipo'],
                'filtros_padrao': {'Tipo': ['RECEITA', 'DESPESA']},
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
                'filtros_padrao': {'Tipo': ['DESPESA']},
                'graficos': ['pie_descontos', 'treemap']
            }
        }
    
    def aplicar_template(self, df: pd.DataFrame, template_id: str) -> pd.DataFrame:
        """
        Aplica um template ao DataFrame
        """
        if df.empty or template_id not in self.templates:
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
        
        return df_resultado

# ============================================
# MÓDULO PRINCIPAL: EXTRATOR FICHA FINANCEIRA SIAPE
# ============================================

def converter_valor_string_siape(valor_str: str) -> Optional[float]:
    """Converte string de valor brasileiro para float (específico para Siape)"""
    try:
        if not valor_str or str(valor_str).strip() == '':
            return None
        
        # Remove espaços e caracteres não numéricos exceto pontos e vírgulas
        valor_str = str(valor_str).strip()
        valor_str = re.sub(r'[^\d,\.]', '', valor_str)
        
        # Se terminar com vírgula, pode ser formato brasileiro incompleto
        if valor_str.endswith(','):
            valor_str = valor_str[:-1]
        
        # Verifica se tem ponto como separador de milhar e vírgula como decimal
        if ',' in valor_str and '.' in valor_str:
            # Formato: 1.234,56
            valor_str = valor_str.replace('.', '').replace(',', '.')
        elif ',' in valor_str:
            # Formato: 1234,56
            valor_str = valor_str.replace(',', '.')
        
        return float(valor_str)
    except Exception as e:
        return None

class ExtratorFichaFinanceiraSiape:
    """Classe para extrair dados de fichas financeiras Siape em PDF"""
    
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
        
        # Padrões de regex para detectar receitas e despesas
        self.padroes_receitas = [
            r'VENCIMENTO',
            r'PROVENTO',
            r'AUX[ÍI]LIO',
            r'GRATIFICAÇÃO',
            r'ABONO',
            r'PER CAPITA',
            r'IQ',
            r'DECISÃO JUDICIAL',
            r'ANUÊNIO'
        ]
        
        self.padroes_despesas = [
            r'IMPOSTO',
            r'DESCONTO',
            r'CONTRIB',
            r'EMPREST',
            r'CONT\.',
            r'AMORT',
            r'MENSALIDADE',
            r'CO-PARTIC',
            r'CAPESESP'
        ]
    
    def formatar_valor_brasileiro(self, valor: float) -> str:
        """Formata valor float para string no padrão brasileiro 1.234,56"""
        try:
            if valor is None or valor == 0:
                return "0,00"
            
            # Arredonda para 2 casas decimais
            valor = round(float(valor), 2)
            
            # Formata com separador de milhar e decimal
            valor_str = f"{valor:,.2f}"
            
            # Substitui ponto por vírgula e vírgula por ponto
            valor_str = valor_str.replace(',', 'X').replace('.', ',').replace('X', '.')
            
            return valor_str
        except:
            return "0,00"
    
    def extrair_ano_semestre_referencia(self, texto: str) -> Dict[str, str]:
        """Extrai ano e semestre de referência da ficha financeira"""
        resultado = {'ano': None, 'semestre': None}
        
        if not texto:
            return resultado
        
        # Padrão: "Ficha Financeira referente a: 2016 - 1º Semestre"
        padrao = re.search(r'Ficha Financeira referente a:\s*(\d{4})\s*-\s*(\d+)º\s*Semestre', texto, re.IGNORECASE)
        
        if padrao:
            resultado['ano'] = padrao.group(1)
            resultado['semestre'] = padrao.group(2)
        else:
            # Tenta outro padrão
            padrao_alt = re.search(r'(\d{4})\s*-\s*(\d+)º\s*Semestre', texto)
            if padrao_alt:
                resultado['ano'] = padrao_alt.group(1)
                resultado['semestre'] = padrao_alt.group(2)
        
        return resultado
    
    def determinar_tipo_rubrica(self, nome_rubrica: str) -> str:
        """Determina se a rubrica é RECEITA ou DESPESA baseada no nome"""
        nome_upper = nome_rubrica.upper()
        
        # Verifica padrões de receitas
        for padrao in self.padroes_receitas:
            if re.search(padrao, nome_upper, re.IGNORECASE):
                return 'RECEITA'
        
        # Verifica padrões de despesas
        for padrao in self.padroes_despesas:
            if re.search(padrao, nome_upper, re.IGNORECASE):
                return 'DESPESA'
        
        # Se não encontrou, tenta pelo código (se começar com R/D)
        if nome_rubrica.startswith('R'):
            return 'RECEITA'
        elif nome_rubrica.startswith('D'):
            return 'DESPESA'
        else:
            return 'DESPESA'  # Padrão
    
    def processar_pdf(self, pdf_file, extrair_receitas: bool = True, extrair_despesas: bool = True) -> pd.DataFrame:
        """Processa o PDF e extrai dados da ficha financeira Siape"""
        
        dados = []
        
        with pdfplumber.open(pdf_file) as pdf:
            for pagina_num, pagina in enumerate(pdf.pages, 1):
                texto = pagina.extract_text()
                
                if not texto or 'Ficha Financeira' not in texto:
                    continue
                
                # Extrai ano e semestre de referência
                referencia = self.extrair_ano_semestre_referencia(texto)
                ano = referencia['ano']
                semestre = referencia['semestre']
                
                if not ano:
                    continue
                
                # Determina meses do semestre
                meses_semestre = self.obter_meses_semestre(int(semestre) if semestre else 1)
                
                # Extrai tabelas
                tabelas = pagina.extract_tables()
                
                for tabela_num, tabela in enumerate(tabelas):
                    if not tabela or len(tabela) < 2:
                        continue
                    
                    # Encontra linha de cabeçalho com meses
                    linha_cabecalho_idx = -1
                    meses_colunas = {}  # Mapeia coluna -> mês
                    
                    for i, linha in enumerate(tabela):
                        if not linha:
                            continue
                        
                        linha_str = ' '.join([str(cell) for cell in linha if cell])
                        
                        # Procura por meses na linha
                        for col_idx, cell in enumerate(linha):
                            if cell:
                                cell_str = str(cell).strip().upper()
                                for mes_abrev, mes_num in self.meses_map.items():
                                    if mes_abrev in cell_str:
                                        meses_colunas[col_idx] = mes_num
                                        linha_cabecalho_idx = i
                                        break
                        
                        if meses_colunas:
                            break
                    
                    if not meses_colunas:
                        continue
                    
                    # Processa linhas após o cabeçalho
                    for i in range(linha_cabecalho_idx + 1, len(tabela)):
                        linha = tabela[i]
                        
                        if not linha or not any(linha):
                            continue
                        
                        # Pula linhas que são totais
                        linha_str = ' '.join([str(cell) for cell in linha if cell])
                        if 'TOTAL' in linha_str.upper() or '*****' in linha_str:
                            continue
                        
                        # Pula linhas vazias ou com apenas espaços
                        if all(not cell or str(cell).strip() == '' for cell in linha):
                            continue
                        
                        # Encontra código e nome da rubrica
                        codigo_rubrica = None
                        nome_rubrica = None
                        
                        # Procura por código numérico (padrão: 00001, 00013, etc.)
                        for cell in linha:
                            if cell and str(cell).strip():
                                cell_str = str(cell).strip()
                                # Código geralmente tem 5 dígitos
                                if re.match(r'^\d{5,}$', cell_str):
                                    codigo_rubrica = cell_str
                                # Nome da rubrica geralmente tem texto
                                elif (not re.match(r'^[\d\.,]+$', cell_str) and 
                                      not any(mes in cell_str.upper() for mes in self.meses_map.keys())):
                                    nome_rubrica = cell_str
                        
                        if not nome_rubrica:
                            continue
                        
                        # Determina tipo da rubrica
                        tipo = self.determinar_tipo_rubrica(nome_rubrica)
                        
                        # Filtra por tipo se necessário
                        if (tipo == 'RECEITA' and not extrair_receitas) or (tipo == 'DESPESA' and not extrair_despesas):
                            continue
                        
                        # Extrai valores dos meses
                        for col_idx, mes_num in meses_colunas.items():
                            if col_idx < len(linha) and linha[col_idx]:
                                valor_str = str(linha[col_idx]).strip()
                                
                                # Converte valor
                                valor_float = converter_valor_string_siape(valor_str)
                                
                                if valor_float is not None and valor_float != 0:
                                    # Formata competência
                                    competencia = f"{mes_num:02d}/{ano}"
                                    
                                    # Formata valor
                                    valor_formatado = self.formatar_valor_brasileiro(valor_float)
                                    
                                    # Adiciona aos dados
                                    dados.append({
                                        'Codigo_Rubrica': codigo_rubrica or 'N/A',
                                        'Discriminacao': nome_rubrica,
                                        'Valor': valor_formatado,
                                        'Competencia': competencia,
                                        'Pagina': pagina_num,
                                        'Ano': ano,
                                        'Semestre': semestre or 'N/A',
                                        'Tipo': tipo,
                                        'Tabela': tabela_num
                                    })
        
        # Cria DataFrame
        if dados:
            df = pd.DataFrame(dados)
            df = df.drop_duplicates()
            if not df.empty:
                df = df.sort_values(['Ano', 'Semestre', 'Pagina', 'Tipo', 'Discriminacao'])
            return df
        else:
            return pd.DataFrame(columns=[
                'Codigo_Rubrica', 'Discriminacao', 'Valor', 'Competencia', 
                'Pagina', 'Ano', 'Semestre', 'Tipo', 'Tabela'
            ])
    
    def obter_meses_semestre(self, semestre: int) -> List[int]:
        """Retorna lista de meses com base no semestre"""
        if semestre == 1:
            return [1, 2, 3, 4, 5, 6]  # Janeiro a Junho
        elif semestre == 2:
            return [7, 8, 9, 10, 11, 12]  # Julho a Dezembro
        else:
            return list(range(1, 13))  # Todos os meses

# ============================================
# INTERFACE STREAMLIT - VERSÃO PARA FICHA FINANCEIRA SIAPE
# ============================================

def inicializar_sessao():
    """Inicializa as variáveis de sessão"""
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
    """Formata o valor total para exibição"""
    if df.empty:
        return "R$ 0,00"
    
    valores = df['Valor'].apply(lambda x: converter_valor_string_siape(x) or 0)
    total = valores.sum()
    return f"R$ {total:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')

def formatar_valor_brasileiro(valor):
    """Formata valor para padrão brasileiro"""
    try:
        if valor is None:
            return "0,00"
        valor_float = float(valor)
        return f"{valor_float:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
    except:
        return "0,00"

def exportar_dados(df, formato, nome_arquivo):
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
            file_name=f"ficha_financeira_{timestamp}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    
    elif formato == "CSV":
        # CSV com ponto e vírgula e encoding UTF-8
        csv = df.to_csv(index=False, sep=';', encoding='utf-8-sig')
        st.download_button(
            label="⬇️ Baixar CSV",
            data=csv,
            file_name=f"ficha_financeira_{timestamp}.csv",
            mime="text/csv"
        )

def main():
    st.set_page_config(
        page_title="Extrator de Ficha Financeira Siape",
        page_icon="📊",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Inicializar sessão
    inicializar_sessao()
    
    # Barra lateral com configurações
    with st.sidebar:
        st.title("⚙️ Configurações Ficha Financeira")
        
        # Modo de operação
        st.session_state.modo_avancado = st.checkbox(
            "Modo Avançado",
            value=st.session_state.modo_avancado,
            help="Ativa funcionalidades avançadas"
        )
        
        # Configurações salvas
        config_salvas = st.session_state.configurador.carregar_configuracao()
        
        st.subheader("📊 Extração")
        extrair_receitas = st.checkbox(
            "Extrair RECEITAS",
            value=config_salvas.get('extrair_receitas', True)
        )
        extrair_despesas = st.checkbox(
            "Extrair DESPESAS", 
            value=config_salvas.get('extrair_despesas', True)
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
                'extrair_receitas': extrair_receitas,
                'extrair_despesas': extrair_despesas,
                'modo_avancado': st.session_state.modo_avancado,
                'indice_preferido': st.session_state.indice_correcao or 'IPCA'
            }
            st.session_state.configurador.salvar_configuracao(nova_config)
            st.success("Configurações salvas!")
    
    # Área principal
    st.title("📊 Extrator de Ficha Financeira Siape")
    st.markdown("### Extraia dados de fichas financeiras no formato Siape (PDF)")
    
    # Upload do arquivo
    st.subheader("📁 Upload do Arquivo PDF")
    uploaded_file = st.file_uploader(
        "Faça upload da ficha financeira em PDF",
        type="pdf",
        key="uploader_ficha_financeira",
        help="Formato esperado: Ficha Financeira referente a: ANO - SEMESTRE"
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
            if st.button("🔍 Processar Ficha Financeira", type="primary", use_container_width=True):
                with st.spinner("Processando PDF..."):
                    try:
                        extrator = ExtratorFichaFinanceiraSiape()
                        df = extrator.processar_pdf(
                            uploaded_file,
                            extrair_receitas=extrair_receitas,
                            extrair_despesas=extrair_despesas
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
                            st.error("⚠️ Nenhum dado extraído. Verifique o formato do arquivo.")
                            
                    except Exception as e:
                        st.error(f"❌ Erro: {str(e)}")
        
        # Interface com dados processados
        if st.session_state.dados_extraidos is not None:
            # Usar dados filtrados se disponíveis, caso contrário usar os originais
            df = st.session_state.df_filtrado if st.session_state.df_filtrado is not None else st.session_state.dados_extraidos
            
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
                    st.metric("Valor Total", formatar_valor_total(df))
                
                # Tipos de rubricas
                col5, col6 = st.columns(2)
                with col5:
                    receitas_count = len(df[df['Tipo'] == 'RECEITA'])
                    st.metric("Receitas", receitas_count)
                with col6:
                    despesas_count = len(df[df['Tipo'] == 'DESPESA'])
                    st.metric("Despesas", despesas_count)
                
                # Dados principais
                st.subheader("📋 Dados Extraídos")
                st.dataframe(
                    df[['Codigo_Rubrica', 'Discriminacao', 'Valor', 'Competencia', 'Ano', 'Semestre', 'Tipo', 'Pagina']].head(50),
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
                
                # Semestres
                semestres = st.multiselect(
                    "Semestre:",
                    sorted(df['Semestre'].unique()),
                    default=sorted(df['Semestre'].unique())
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
                        if st.button("❌ Remover", key="remover_fav"):
                            st.session_state.configurador.remover_rubrica_favorita(rubrica_selecionada)
                            st.rerun()
                    else:
                        if st.button("⭐ Favoritar", key="adicionar_fav"):
                            st.session_state.configurador.adicionar_rubrica_favorita(rubrica_selecionada)
                            st.rerun()
                
                # Seleção de rubricas (favoritas primeiro)
                todas_rubricas = rubricas_favoritas + outras_rubricas
                rubricas_selecionadas = st.multiselect(
                    "Selecionar rubricas para análise:",
                    todas_rubricas,
                    default=todas_rubricas[:min(10, len(todas_rubricas))]
                )
                
                # Filtro por valor mínimo
                valor_minimo = st.number_input(
                    "Valor mínimo (R$):",
                    min_value=0.0,
                    value=0.0,
                    step=100.0
                )
                
                # Botões de ação
                col_btn1, col_btn2 = st.columns(2)
                with col_btn1:
                    if st.button("✅ Aplicar Filtros", type="primary", use_container_width=True, key="aplicar_filtros"):
                        df_filtrado = st.session_state.dados_extraidos.copy()
                        
                        if tipos:
                            df_filtrado = df_filtrado[df_filtrado['Tipo'].isin(tipos)]
                        if anos:
                            df_filtrado = df_filtrado[df_filtrado['Ano'].isin(anos)]
                        if semestres:
                            df_filtrado = df_filtrado[df_filtrado['Semestre'].isin(semestres)]
                        if rubricas_selecionadas:
                            df_filtrado = df_filtrado[df_filtrado['Discriminacao'].isin(rubricas_selecionadas)]
                        
                        # Filtro por valor mínimo
                        if valor_minimo > 0:
                            df_filtrado['Valor_Numerico'] = df_filtrado['Valor'].apply(
                                lambda x: converter_valor_string_siape(x) or 0
                            )
                            df_filtrado = df_filtrado[df_filtrado['Valor_Numerico'] >= valor_minimo]
                            df_filtrado = df_filtrado.drop(columns=['Valor_Numerico'])
                        
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
                    # Análise comparativa
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
                            
                            # Gráfico de evolução (se houver dados suficientes)
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
                    
                    # Composição de despesas
                    st.write("### 🧩 Composição de Despesas")
                    
                    ano_analise = st.selectbox(
                        "Selecione o ano para análise:",
                        sorted(df['Ano'].unique()),
                        key="ano_analise"
                    )
                    
                    if st.button("Analisar Composição", key="analise_comp"):
                        composicao = st.session_state.analisador.analisar_composicao_descontos(df, ano_analise)
                        
                        if composicao and composicao['total_ano'] > 0:
                            # Gráfico de pizza para top 10
                            df_composicao = pd.DataFrame({
                                'Rubrica': list(composicao['percentuais'].keys()),
                                'Percentual': list(composicao['percentuais'].values())
                            }).head(10)
                            
                            if not df_composicao.empty:
                                fig = px.pie(
                                    df_composicao,
                                    values='Percentual',
                                    names='Rubrica',
                                    title=f"Composição das Despesas - {ano_analise}"
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
                        
                        if st.button("🔄 Gerar Relatório", type="primary", key="gerar_relatorio"):
                            with st.spinner("Gerando relatório..."):
                                # Aplica template
                                df_template = st.session_state.template_manager.aplicar_template(
                                    df, 
                                    st.session_state.template_selecionado
                                )
                                
                                # Mostrar dados
                                st.write("#### 📊 Dados do Relatório")
                                st.dataframe(
                                    df_template,
                                    use_container_width=True,
                                    height=300
                                )
                                
                                # Estatísticas básicas
                                if not df_template.empty and 'Valor' in df_template.columns:
                                    df_template['Valor_Numerico'] = df_template['Valor'].apply(
                                        lambda x: converter_valor_string_siape(x) or 0
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
            
            with tab5:
                st.subheader("📥 Exportação de Dados")
                
                st.info("📝 Todos os dados exportados incluem o número da página de origem para total transparência.")
                
                # Opções de exportação
                formato = st.radio(
                    "Formato de exportação:",
                    ["Excel (XLSX)", "CSV"],
                    horizontal=True,
                    key="formato_export"
                )
                
                # Seleção de colunas para exportação
                colunas_disponiveis = [
                    'Codigo_Rubrica', 'Discriminacao', 'Valor', 'Competencia',
                    'Ano', 'Semestre', 'Tipo', 'Pagina', 'Tabela'
                ]
                
                colunas_selecionadas = st.multiselect(
                    "Selecionar colunas para exportar:",
                    colunas_disponiveis,
                    default=colunas_disponiveis
                )
                
                # Botões de exportação
                col_e1, col_e2, col_e3 = st.columns(3)
                
                with col_e1:
                    if st.button("💾 Exportar Dados", use_container_width=True, key="exportar_dados"):
                        if colunas_selecionadas:
                            df_export = df[colunas_selecionadas]
                            exportar_dados(df_export, formato, uploaded_file.name)
                        else:
                            st.warning("Selecione pelo menos uma coluna para exportar.")
                
                with col_e2:
                    if st.button("📊 Exportar + Análises", use_container_width=True, key="exportar_analises"):
                        # Exporta com análises básicas
                        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                        buffer = io.BytesIO()
                        
                        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                            # Dados principais
                            df.to_excel(writer, index=False, sheet_name='Dados')
                            
                            # Análise de composição (se houver despesas)
                            if 'DESPESA' in df['Tipo'].unique():
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
                            
                            # Estatísticas por tipo
                            stats_tipo = df.groupby(['Ano', 'Tipo']).size().reset_index(name='Contagem')
                            stats_tipo.to_excel(writer, index=False, sheet_name='Stats_Tipo')
                        
                        buffer.seek(0)
                        st.download_button(
                            label="⬇️ Baixar Excel com Análises",
                            data=buffer,
                            file_name=f"ficha_financeira_analises_{timestamp}.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                        )
                
                with col_e3:
                    if st.button("🔄 Novo Arquivo", type="secondary", use_container_width=True, key="novo_arquivo"):
                        st.session_state.dados_extraidos = None
                        st.session_state.df_filtrado = None
                        st.session_state.arquivo_processado = None
                        st.rerun()
    
    else:
        # Tela inicial
        st.info("👆 Faça upload de um arquivo PDF da Ficha Financeira Siape para começar.")
        
        with st.expander("ℹ️ Sobre o formato da Ficha Financeira Siape"):
            st.markdown("""
            ### 📋 **FORMATO ESPERADO:**
            
            O extrator foi desenvolvido para processar fichas financeiras no formato **Siape**, como o exemplo `GER.pdf`.
            
            **Características do formato:**
            1. **Cabeçalho**: "Ficha Financeira referente a: 2016 - 1º Semestre"
            2. **Ano de referência**: Extraído automaticamente do cabeçalho
            3. **Meses**: JAN, FEV, MAR, ABR, MAI, JUN (1º semestre) ou JUL, AGO, SET, OUT, NOV, DEZ (2º semestre)
            4. **Rubricas**: Código (ex: 00001) e Nome (ex: VENCIMENTO BASICO)
            5. **Valores**: No formato brasileiro (ex: 4.100,61)
            
            **Colunas extraídas:**
            - `Codigo_Rubrica`: Código da rubrica (ex: 00001)
            - `Discriminacao`: Nome da rubrica (ex: VENCIMENTO BASICO)
            - `Valor`: Valor formatado (ex: 4.100,61)
            - `Competencia`: Mês/Ano (ex: 01/2016)
            - `Ano`: Ano de referência
            - `Semestre`: 1 ou 2
            - `Tipo`: RECEITA ou DESPESA (classificado automaticamente)
            - `Pagina`: Número da página no PDF
            - `Tabela`: Número da tabela na página
            """)
        
        with st.expander("🚀 Funcionalidades Avançadas"):
            st.markdown("""
            ### 🌟 **FUNCIONALIDADES INCLUÍDAS:**
            
            1. **⭐ Rubricas Favoritas** - Salve suas rubricas mais usadas
            2. **💰 Correção Monetária** - Corrija valores com IPCA, INPC, IGPM, SELIC
            3. **📊 Análise Comparativa** - Compare evolução ano a ano
            4. **📋 Templates de Relatórios** - Relatórios pré-formatados
            5. **🎯 Filtros Avançados** - Filtre por tipo, ano, semestre, valor mínimo
            6. **📈 Visualizações Gráficas** - Gráficos interativos com Plotly
            7. **📥 Exportação Completa** - Excel e CSV com metadados (incluindo página de origem)
            
            ### 🔧 **Como usar:**
            1. Faça upload do PDF da ficha financeira
            2. Ative o **Modo Avançado** na barra lateral (opcional)
            3. Configure filtros e preferências
            4. Explore os dados nas diferentes abas
            5. Exporte no formato desejado
            """)

if __name__ == "__main__":
    main()
