import streamlit as st
import pdfplumber
import pandas as pd
import re
import io

# --- Configuração da Página ---
st.set_page_config(page_title="Extrator Financeiro SIAPE", layout="wide")

st.title("📂 Extrator de Fichas Financeiras (SIAPE)")
st.markdown("""
    Faça upload do seu PDF (mesmo com várias páginas/anos). 
    O sistema identificará o **Ano de Referência** correto e permitirá filtrar Proventos/Descontos.
""")

# --- Função de Extração ---
def extract_data_from_pdf(file):
    all_data = []
    
    with pdfplumber.open(file) as pdf:
        for page_num, page in enumerate(pdf.pages):
            text = page.extract_text()
            
            # 1. BUSCA INTELIGENTE DO ANO DE REFERÊNCIA
            # Procura por "ANO REFERENCIA" seguido de possíveis espaços/quebras e 4 dígitos
            # Ignora totalmente o campo "EMITIDO EM"
            match_ano = re.search(r'ANO REFER[ÊE]NCIA\s*[\n\r]*\s*(\d{4})', text, re.IGNORECASE)
            
            if match_ano:
                ano_referencia = match_ano.group(1)
            else:
                # Fallback: Tenta achar 4 dígitos isolados perto do final do cabeçalho se o padrão falhar
                # Mas a regex acima é bem robusta para o padrão SIAPE
                ano_referencia = f"Desconhecido (Pág {page_num+1})"

            # 2. EXTRAÇÃO DA TABELA
            # As fichas financeiras geralmente têm linhas ocultas. Vamos tentar extrair a estrutura de tabela.
            tables = page.extract_tables()
            
            for table in tables:
                # Cria um DataFrame temporário para a tabela encontrada
                df_page = pd.DataFrame(table)
                
                # Limpeza básica: remove linhas que sejam totalmente vazias
                df_page = df_page.dropna(how='all')
                
                # Se a tabela for muito pequena ou não parecer ter dados mensais, pular
                if df_page.shape[1] < 5: 
                    continue
                
                # Definir a primeira linha como cabeçalho se contiver "DISCRIMINAÇÃO" ou "JAN"
                # O SIAPE costuma ter cabeçalhos complexos, vamos normalizar pelo conteúdo
                
                # Procurar a linha de cabeçalho
                header_index = -1
                for idx, row in df_page.iterrows():
                    row_str = " ".join([str(x) for x in row]).upper()
                    if "DISCRIMINAÇÃO" in row_str or "DISCRIMINACAO" in row_str:
                        header_index = idx
                        break
                
                if header_index != -1:
                    # Ajustar cabeçalho
                    new_header = df_page.iloc[header_index].values
                    df_page = df_page.iloc[header_index+1:].copy()
                    df_page.columns = new_header
                    
                    # Normalizar nomes das colunas (remover None, espaços extras)
                    df_page.columns = [str(c).strip().upper() for c in df_page.columns]
                    
                    # 3. TRATAMENTO DE TIPO (PROVENTO vs DESCONTO)
                    # A coluna "TIPO" (geralmente a primeira) costuma vir preenchida só na 1ª linha do grupo
                    # Ex: "RENDIMENTOS" na linha 1, vazio na linha 2, 3...
                    # Usamos 'ffill' para propagar o valor para baixo
                    if "TIPO" in df_page.columns:
                        df_page["TIPO"] = df_page["TIPO"].replace("", None).ffill()
                    
                    # Adicionar coluna do Ano
                    df_page.insert(0, "ANO_REF", ano_referencia)
                    
                    # Renomear colunas para garantir consistência
                    # As vezes vem JAN, FEV... as vezes JANEIRO... vamos manter como vem, mas garantir a chave 'DISCRIMINAÇÃO'
                    col_map = {c: c for c in df_page.columns}
                    for c in df_page.columns:
                        if "DISCRIMINA" in c:
                            col_map[c] = "RUBRICA"
                    df_page.rename(columns=col_map, inplace=True)
                    
                    # Filtrar apenas linhas que tenham uma Rubrica válida (ignorar rodapés/totais soltos)
                    if "RUBRICA" in df_page.columns:
                        df_page = df_page[df_page["RUBRICA"].notna() & (df_page["RUBRICA"] != "")]
                        # Remove linhas que sejam apenas repetições de cabeçalho
                        df_page = df_page[df_page["RUBRICA"] != "DISCRIMINAÇÃO"]
                        
                        all_data.append(df_page)

    if all_data:
        return pd.concat(all_data, ignore_index=True)
    else:
        return pd.DataFrame()

# --- Interface Principal ---
uploaded_file = st.file_uploader("Arraste seu PDF aqui", type=["pdf"])

if uploaded_file:
    with st.spinner("Processando... Lendo Ano de Referência e Rubricas..."):
        try:
            df_final = extract_data_from_pdf(uploaded_file)
            
            if not df_final.empty:
                st.success("Dados extraídos com sucesso!")
                
                # --- FILTROS LATERAIS ---
                st.sidebar.header("Filtros de Exportação")
                
                # 1. Filtro de Ano
                anos_disponiveis = sorted(df_final['ANO_REF'].unique())
                anos_selecionados = st.sidebar.multiselect(
                    "Selecione o Ano de Referência", 
                    options=anos_disponiveis,
                    default=anos_disponiveis
                )
                
                # Filtragem preliminar por ano
                df_filtered = df_final[df_final['ANO_REF'].isin(anos_selecionados)]
                
                # 2. Filtro de Tipo (Proventos/Descontos)
                # Verifica se a coluna TIPO existe (se o PDF foi lido corretamente)
                tipos_unicos = []
                if "TIPO" in df_filtered.columns:
                    # Limpeza extra para garantir que só pegue RENDIMENTOS e DESCONTOS limpos
                    df_filtered["TIPO"] = df_filtered["TIPO"].astype(str).str.strip().str.upper()
                    tipos_unicos = sorted(df_filtered["TIPO"].unique())
                
                tipo_selecionado = st.sidebar.radio(
                    "O que você quer visualizar?",
                    options=["TUDO", "APENAS RENDIMENTOS", "APENAS DESCONTOS"]
                )
                
                # Aplicar filtro de TIPO
                if tipo_selecionado == "APENAS RENDIMENTOS":
                    # Filtra tudo que contenha 'REND' (Rendimentos) ou 'PROV' (Proventos)
                    df_filtered = df_filtered[df_filtered["TIPO"].str.contains("REND|PROV", na=False)]
                elif tipo_selecionado == "APENAS DESCONTOS":
                    # Filtra tudo que contenha 'DESC'
                    df_filtered = df_filtered[df_filtered["TIPO"].str.contains("DESC", na=False)]
                
                # 3. Filtro de Rubricas (Caixa de Seleção)
                # Agora mostramos apenas as rubricas disponíveis após os filtros de Ano e Tipo
                rubricas_disponiveis = sorted(df_filtered["RUBRICA"].unique())
                rubricas_selecionadas = st.sidebar.multiselect(
                    "Selecione as Rubricas Específicas",
                    options=rubricas_disponiveis,
                    default=rubricas_disponiveis, # Por padrão seleciona tudo, usuário desmarca o que não quer
                    help="Desmarque para remover rubricas indesejadas"
                )
                
                # Filtrar DataFrame Final pelas rubricas
                df_view = df_filtered[df_filtered["RUBRICA"].isin(rubricas_selecionadas)]
                
                # --- EXIBIÇÃO ---
                st.subheader(f"Visualizando {len(df_view)} registros")
                st.dataframe(df_view, use_container_width=True)
                
                # Botão de Download
                csv = df_view.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="💾 Baixar CSV Selecionado",
                    data=csv,
                    file_name="extracao_financeira_ajustada.csv",
                    mime="text/csv",
                )
                
            else:
                st.error("Não foi possível identificar tabelas financeiras padrão neste PDF.")
                
        except Exception as e:
            st.error(f"Ocorreu um erro ao processar: {e}")
            st.info("Dica: Verifique se o PDF não é uma imagem digitalizada (scaneada). O arquivo precisa ter texto selecionável.")
