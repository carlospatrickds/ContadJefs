import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from io import StringIO

# Configuração da página
st.set_page_config(
    page_title="Análise de Planilha",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Título da aplicação
st.title("📊 Análise de Planilha - Streamlit App")
st.markdown("---")

# Upload do arquivo
uploaded_file = st.sidebar.file_uploader(
    "📂 Faça upload da sua planilha",
    type=['xlsx', 'xls', 'csv'],
    help="Suporta arquivos Excel (.xlsx, .xls) e CSV (.csv)"
)

# Inicializar o dataframe
df = None

if uploaded_file is not None:
    try:
        # Verificar o tipo de arquivo
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file)
        else:
            df = pd.read_excel(uploaded_file)
        
        st.sidebar.success("✅ Arquivo carregado com sucesso!")
        
        # Mostrar informações básicas
        st.sidebar.subheader("📋 Informações do Dataset")
        st.sidebar.write(f"**Linhas:** {df.shape[0]}")
        st.sidebar.write(f"**Colunas:** {df.shape[1]}")
        
        # Mostrar tipos de dados
        st.sidebar.subheader("🔍 Tipos de Dados")
        for col in df.columns:
            st.sidebar.write(f"**{col}:** {df[col].dtype}")
        
    except Exception as e:
        st.sidebar.error(f"❌ Erro ao carregar arquivo: {str(e)}")
else:
    st.info("👆 Por favor, faça upload de uma planilha para começar")
    st.stop()

# Sidebar - Filtros
st.sidebar.markdown("---")
st.sidebar.subheader("🎛️ Filtros")

# Filtro por colunas categóricas
categorical_cols = df.select_dtypes(include=['object']).columns.tolist()
for col in categorical_cols:
    if df[col].nunique() < 20:  # Só mostra filtro se tiver poucas categorias
        selected_values = st.sidebar.multiselect(
            f"Filtrar {col}",
            options=df[col].unique(),
            default=df[col].unique()
        )
        df = df[df[col].isin(selected_values)]

# Filtro por colunas numéricas
numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
for col in numeric_cols:
    min_val = float(df[col].min())
    max_val = float(df[col].max())
    selected_range = st.sidebar.slider(
        f"Intervalo {col}",
        min_val, max_val, (min_val, max_val)
    )
    df = df[(df[col] >= selected_range[0]) & (df[col] <= selected_range[1])]

# Layout principal
tab1, tab2, tab3, tab4 = st.tabs(["📊 Visualização", "📈 Gráficos", "📋 Dados", "⚙️ Análise"])

with tab1:
    st.header("Visualização dos Dados")
    
    # Mostrar dataframe com opções
    st.subheader("Tabela de Dados")
    rows_to_show = st.slider("Número de linhas para mostrar", 5, 100, 20)
    st.dataframe(df.head(rows_to_show), use_container_width=True)
    
    # Estatísticas descritivas
    st.subheader("Estatísticas Descritivas")
    st.dataframe(df.describe(), use_container_width=True)

with tab2:
    st.header("Gráficos e Visualizações")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Gráfico de barras
        if categorical_cols:
            st.subheader("Gráfico de Barras")
            x_axis = st.selectbox("Eixo X (Categórico)", categorical_cols)
            if numeric_cols:
                y_axis = st.selectbox("Eixo Y (Numérico)", numeric_cols)
                fig = px.bar(df, x=x_axis, y=y_axis, title=f"{y_axis} por {x_axis}")
                st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        # Gráfico de pizza
        if categorical_cols:
            st.subheader("Gráfico de Pizza")
            pie_col = st.selectbox("Selecionar coluna para pizza", categorical_cols)
            if df[pie_col].nunique() < 10:
                pie_data = df[pie_col].value_counts()
                fig = px.pie(values=pie_data.values, names=pie_data.index, title=f"Distribuição de {pie_col}")
                st.plotly_chart(fig, use_container_width=True)
    
    # Scatter plot
    if len(numeric_cols) >= 2:
        st.subheader("Scatter Plot")
        col1, col2, col3 = st.columns(3)
        with col1:
            scatter_x = st.selectbox("Eixo X", numeric_cols)
        with col2:
            scatter_y = st.selectbox("Eixo Y", numeric_cols)
        with col3:
            color_by = st.selectbox("Colorir por", [None] + categorical_cols)
        
        fig = px.scatter(df, x=scatter_x, y=scatter_y, color=color_by, 
                        title=f"{scatter_y} vs {scatter_x}")
        st.plotly_chart(fig, use_container_width=True)

with tab3:
    st.header("Dados Completos")
    
    # Pesquisa e filtros rápidos
    st.subheader("Pesquisar Dados")
    search_term = st.text_input("Digite o termo de pesquisa:")
    if search_term:
        search_df = df[df.astype(str).apply(lambda x: x.str.contains(search_term, case=False)).any(axis=1)]
        st.dataframe(search_df, use_container_width=True)
    else:
        st.dataframe(df, use_container_width=True)
    
    # Download dos dados filtrados
    st.subheader("Exportar Dados")
    csv = df.to_csv(index=False)
    st.download_button(
        label="📥 Download CSV",
        data=csv,
        file_name="dados_filtrados.csv",
        mime="text/csv"
    )

with tab4:
    st.header("Análise Avançada")
    
    # Correlação
    if len(numeric_cols) > 1:
        st.subheader("Matriz de Correlação")
        corr_matrix = df[numeric_cols].corr()
        fig = px.imshow(corr_matrix, text_auto=True, aspect="auto", 
                       title="Matriz de Correlação")
        st.plotly_chart(fig, use_container_width=True)
    
    # Análise de valores missing
    st.subheader("Valores Faltantes")
    missing_data = df.isnull().sum()
    if missing_data.sum() > 0:
        fig = px.bar(x=missing_data.index, y=missing_data.values, 
                    title="Valores Faltantes por Coluna")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.success("✅ Não há valores faltantes no dataset!")

# Footer
st.markdown("---")
st.markdown("📊 **App desenvolvido com Streamlit** | 🚀 **Versão 1.0**")
