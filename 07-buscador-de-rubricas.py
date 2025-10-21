import streamlit as st
import pdfplumber
import re
import pandas as pd

# Configuração da página
st.set_page_config(
    page_title="Buscador de rubricas do HISCRE",
    layout="centered",
    initial_sidebar_state="expanded"
)

# --- VERIFICAÇÃO DE SENHA ---
SENHA_CORRETA = "23"
senha_digitada = st.text_input("Digite a senha para acessar o BUSCADOR:", type="password")

if senha_digitada != SENHA_CORRETA:
    if senha_digitada:  # Só mostra erro se o usuário já digitou algo
        st.error("Senha incorreta! Acesso negado.")
    st.stop()  # Para aqui se a senha estiver errada ou vazia

# --- SE CHEGOU AQUI, SENHA ESTÁ CORRETA ---
## 🔒 Aviso de segurança
st.info("🔒 Este sistema **não salva arquivos ou dados na nuvem**. "
        "Todas as informações do HISCRE são processadas apenas localmente, "
        "garantindo confidencialidade e segurança.")

# ________________________________________________________
    
# Dicionário completo de rubricas (ordenado por código)
descricoes_rubricas = {
    "101": "VALOR TOTAL DE MR DO PERÍODO",
    "103": "Abono do Governo Federal",
    "104": "VALOR DO DÉCIMO-TERCEIRO SALÁRIO",
    "105": "SALARIO FAMILIA",
    "106": "Parcela de diferença de revisão da RMI",
    "107": "Complemento positivo",
    "110": "Correção monetária",
    "111": "Parcela de gratificação de ex-combatente",
    "115": "Abono anual de ex-combatente (14º salário)",
    "121": "COMPLEMENTO A TITULO DE CPMF",
    "125": "CP – Decisão judicial",
    "131": "CP - REVISAO BENEFICIO SISTEMA CENTRAL",
    "135": "Gratificação de qualidade e produtividade",
    "137": "ADIANTAMENTO P/ARREDONDAMENTO DO CRÉDITO",
    "145": "Adicional Talidomida",
    "146": "Indenização por ação judicial específica",
    "156": "CP – Revisão de teto",
    "159": "CORRECAO MONETARIA COMPLEMENTAR DE RENDA",
    "201": "IMPOSTO DE RENDA RETIDO NA FONTE",
    "202": "Pensão Alimentícia – Débito",
    "203": "CONSIGNAÇÃO",
    "204": "Imposto de Renda no Exterior",
    "205": "Diferença de Imposto de Renda – Débito",
    "206": "Desconto do INSS",
    "207": "DESCONTO DE I.R. SOBRE 13º SALÁRIO",
    "208": "Contribuição Previdenciária sobre 13º Salário",
    "209": "Diferença de IR sobre 13º Salário – Débito",
    "210": "Pensão Alimentícia sobre 13º Salário",
    "211": "Desconto de IR sobre 14º Salário",
    "212": "Contribuição Previdenciária sobre 14º Salário",
    "213": "Pensão Alimentícia sobre 14º Salário",
    "214": "CONSIGNAÇÃO SOBRE 13 SAL.",
    "215": "AJUSTE DO ARREDONDAMENTO DE CRÉDITOS",
    "216": "CONSIGNAÇÃO EMPRÉSTIMO BANCÁRIO",
    "217": "EMPRÉSTIMO SOBRE A RMC",
    "218": "13. SALÁRIO PAGO COMPETÊNCIAS ANTERIORES",
    "227": "DEVOLUCAO DE CPMF",
#"219-250": "Diversas contribuições sindicais e associativas",
    
    "233": "Desconto para Verificação de Teto",
    "236": "Décimo Terceiro Salário – Débito",
    "242": "CONTRIBUICAO SINDIAPI 0800 777 5767",
    "251": "Décimo Terceiro Salário Pago a Maior",
    "252": "Desconto por Acumulação de Benefício Já Concedido",
    "253": "Desconto por Acumulação de Benefício – 13º Salário",
    "254": "Consignacao CONTRIBUICAO UNIBAP",
    "268": "CONSIGNACAO - CARTAO",
    "288": "CONTRIB. AASAP 0800 202 0177",  # Nova rubrica
    "302": "Abatimento IR por Dependente",
    "303": "Abatimento a Beneficiário Maior de 65 Anos",
    "304": "Desconto por Dependente sobre 13º Salário",
    "305": "Desconto Maior 65 Anos – IR 13º Salário",
    "308": "Desconto por Dependente sobre 14º Salário",
    "309": "Desconto Maior 65 Anos – IR 14º Salário",
    "310": "Desconto de Consignação no IR",
    "312": "Desconto de Consignação no IR – 13º Salário",
    "313": "IR Não Recolhido por Ordem Judicial",
    "314": "IR Não Recolhido por Ordem Judicial – 13º Salário",
    "316": "SALDO DEVEDOR ARREDONDAMENTO DE CREDITOS",  # Nova rubrica
    "320": "IR sobre Décimo Terceiro Devolvido",
    "323": "ADIANTAMENTO DE 13 COMPETENCIA ANTERIOR",  # Nova rubrica
    "365": "Indenização Talidomida – Lei 12.190/2010",
    "373": "CP – Artigo 29 ACP-MP242",
    "375": "CP – Indenização seringueiros",
    "383": "RESERVA CARTÃO CONSIGNADO",  # Nova rubrica
    "384": "DESCONTO SIMPLIFICADO DE IR",  # Nova rubrica
    "385": "DESCONTO SIMPLIFICADO DE IR SOBRE 13",  # Nova rubrica
    "903": "Saldo de Imposto de Renda – Positivo",
    "904": "Saldo de Imposto de Renda – Negativo",
    "916": "CONSIGNAÇÃO IR NA FONTE",
    "917": "Consignação IR no Exterior",
    "920": "Consignação empréstimo da CEF"
}

# Inicializar session state
if 'uploaded_file' not in st.session_state:
    st.session_state.uploaded_file = None
if 'dados_extracao' not in st.session_state:
    st.session_state.dados_extracao = None
if 'rubricas_analise' not in st.session_state:
    st.session_state.rubricas_analise = None

# Função para extrair dados da busca
def extrair_dados_pdf(file, rubricas_filtrar):
    dados = []
    nome = ""
    nbs = set()
    competencia_atual = None
    status_atual = None

    with pdfplumber.open(file) as pdf:
        for num_pagina, pagina in enumerate(pdf.pages, start=1):
            texto = pagina.extract_text()
            if texto:
                linhas = texto.split('\n')
                for linha in linhas:
                    # Capturar Nome
                    nome_match = re.search(r'Nome:\s*([A-Z\s\.\-ÇÃÁÉÍÓÚÂÊÔ]+)', linha)
                    if nome_match:
                        nome = nome_match.group(1).strip()

                    # Capturar NB
                    nb_match = re.findall(r'NB:\s*([\d\.\-]+)', linha)
                    if nb_match:
                        nbs.update(nb_match)

                    # Ignorar linhas irrelevantes
                    if (
                        re.search(r'Compet\.\s*Inicial', linha, re.IGNORECASE)
                        or re.search(r'Compet\.\s*Final', linha, re.IGNORECASE)
                        or re.search(r'Nasc', linha, re.IGNORECASE)
                        or re.search(r'Data de Nascimento', linha, re.IGNORECASE)
                        or re.search(r'\d{2}/[A-Za-z]{3}/\d{4}\s+\d{2}:\d{2}:\d{2}', linha)
                    ):
                        continue

                    # Atualizar competência
                    comp_match = re.match(r'^(\d{2}/\d{4})', linha.strip())
                    if comp_match and not re.match(r'^\d{3}\s', linha.strip()):
                        competencia_atual = comp_match.group(1)

                    # Status
                    if "Pago" in linha:
                        status_atual = "Pago"
                    elif "Não Pago" in linha:
                        status_atual = "Não Pago"

                    # Rubrica
                    rubrica_match = re.match(r'^(\d{3})\s+([A-Z0-9\s\.\-ÇÃÁÉÍÓÚÂÊÔ\/]+)\s+R\$[\s]*([\d\.,]+)', linha)
                    if rubrica_match:
                        rubrica = rubrica_match.group(1)
                        descricao = rubrica_match.group(2).strip()
                        valor_texto = rubrica_match.group(3).replace('.', '').replace(',', '.')
                        valor_float = float(valor_texto)
                        if not rubricas_filtrar or rubrica in rubricas_filtrar:
                            dados.append({
                                'p.p HISCRE': num_pagina,
                                'Comp.': competencia_atual if competencia_atual else "Não encontrada",
                                'Rubrica': rubrica,
                                'Descrição': descricao,
                                'Valor (R$)': valor_float,
                                'Status': status_atual if status_atual else "Não encontrado"
                            })

    df = pd.DataFrame(dados)
    if not df.empty:
        # Ordenar por competência
        df['Ordenar'] = pd.to_datetime(df['Comp.'].str.extract(r'(\d{2})/(\d{4})').apply(
            lambda x: f"{x[1]}-{x[0]}-01", axis=1), errors='coerce')
        df = df.sort_values(by='Ordenar').drop(columns=['Ordenar'])

        # Formatar valor para Real
        df['Valor (R$)'] = df['Valor (R$)'].map(lambda x: f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))

        df = df.reset_index(drop=True)

    return nome, list(nbs), df

# Função para extrair todas as rubricas para análise
def extrair_todas_rubricas(file):
    rubricas_encontradas = {}
    
    with pdfplumber.open(file) as pdf:
        for num_pagina, pagina in enumerate(pdf.pages, start=1):
            texto = pagina.extract_text()
            if texto:
                linhas = texto.split('\n')
                for linha in linhas:
                    # Padrão para identificar rubricas
                    rubrica_match = re.match(r'^(\d{3})\s+([A-Z0-9\s\.\-ÇÃÁÉÍÓÚÂÊÔ\/]+)\s+R\$[\s]*([\d\.,]+)', linha)
                    if rubrica_match:
                        rubrica = rubrica_match.group(1)
                        descricao = rubrica_match.group(2).strip()
                        
                        if rubrica in rubricas_encontradas:
                            rubricas_encontradas[rubrica]["ocorrencias"] += 1
                        else:
                            descricao_ref = descricoes_rubricas.get(rubrica, "Não encontrada na referência")
                            rubricas_encontradas[rubrica] = {
                                "descricao_doc": descricao,
                                "descricao_ref": descricao_ref,
                                "ocorrencias": 1
                            }
    
    return rubricas_encontradas

# Upload de arquivo na sidebar
with st.sidebar:
    st.header("📁 Upload do Documento HISCRE")
    
    # incluído 25/08/2025
    st.warning("⚠️ Atenção: Os arquivos não são salvos na nuvem. "
               "Todo processamento ocorre localmente no seu dispositivo.")

    
    uploaded_file = st.file_uploader("Selecione o arquivo PDF", type="pdf", key="global_uploader")
    
    if uploaded_file is not None:
        st.session_state.uploaded_file = uploaded_file
        st.success("✅ Arquivo carregado com sucesso!")
        
        # Botões de processamento
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔄 Processar para Análise", use_container_width=True):
                with st.spinner("Processando para análise..."):
                    st.session_state.rubricas_analise = extrair_todas_rubricas(uploaded_file)
                    st.success("Documento processado para análise!")
        
        with col2:
            if st.button("🗑️ Limpar Arquivo", use_container_width=True):
                st.session_state.uploaded_file = None
                st.session_state.dados_extracao = None
                st.session_state.rubricas_analise = None
                st.rerun()

# CATEGORIAS DE REFERÊNCIA DE RUBRICAS
rubrica_exemplos_mais_comuns = """
**Exemplos de rubrica:**
- **101**: VALOR TOTAL DE MR DO PERÍODO  
- **104**: VALOR DO DÉCIMO-TERCEIRO SALÁRIO
- **105**: SALARIO FAMILIA
- **137**: ADIANTAMENTO P/ARREDONDAMENTO DO CRÉDITO  
- **201**: IMPOSTO DE RENDA RETIDO NA FONTE  
- **203**: CONSIGNAÇÃO  
- **207**: DESCONTO DE I.R. SOBRE 13º SALÁRIO  
- **214**: CONSIGNAÇÃO SOBRE 13 SAL.  
- **215**: AJUSTE DO ARREDONDAMENTO DE CRÉDITOS  
- **216**: CONSIGNAÇÃO EMPRÉSTIMO BANCÁRIO  
- **217**: EMPRÉSTIMO SOBRE A RMC  
- **218**: 13. SALÁRIO PAGO COMPETÊNCIAS ANTERIORES
"""

rubrica_tributacao_ir = """
**Rubricas de Tributação – Imposto de Renda**
| Código | Nomenclatura                           | Descrição                                                        |
|--------|----------------------------------------|------------------------------------------------------------------|
| 201    | Imposto de Renda Retido na Fonte       | Valor do IR retido diretamente na fonte sobre rendimentos pagos. |
| 204    | Imposto de Renda no Exterior           | IR incidente sobre rendimentos recebidos fora do Brasil.         |
| 205    | Diferença de Imposto de Renda – Débito | Ajuste de débito por diferença de IR a ser recolhido.            |
| 207    | Desconto de IR sobre 13º Salário       | Retenção de IR especificamente sobre o valor do 13º salário.     |
| 209    | Diferença de IR sobre 13º Salário – Débito | Correção ou ajuste de débito referente ao IR do 13º salário. |
| 211    | Desconto de IR sobre 14º Salário       | Retenção de IR sobre o valor do 14º salário (quando aplicável).  |
"""

rubrica_informativas_ir = """
**Rubricas Informativas – Imposto de Renda**
| Código | Nomenclatura                                | Descrição                                                              |
|--------|---------------------------------------------|------------------------------------------------------------------------|
| 302    | Abatimento IR por Dependente                | Redução do IR devido com base no número de dependentes.                |
| 303    | Abatimento a Beneficiário Maior de 65 Anos  | Isenção parcial de IR para beneficiários com mais de 65 anos.          |
| 304    | Desconto por Dependente sobre 13º Salário   | Redução do IR sobre o 13º salário considerando dependentes.            |
| 305    | Desconto Maior 65 Anos – IR 13º Salário     | Isenção parcial de IR sobre o 13º salário para maiores de 65 anos.     |
| 308    | Desconto por Dependente sobre 14º Salário   | Redução do IR sobre o 14º salário considerando dependentes.            |
| 309    | Desconto Maior 65 Anos – IR 14º Salário     | Isenção parcial de IR sobre o 14º salário para maiores de 65 anos.     |
| 310    | Desconto de Consignação no IR               | Valores consignados que afetam o cálculo do IR.                        |
| 312    | Desconto de Consignação no IR – 13º Salário | Consignações que impactam o IR sobre o 13º salário.                    |
| 313    | IR Não Recolhido por Ordem Judicial         | Suspensão do recolhimento do IR por decisão judicial.                  |
| 314    | IR Não Recolhido por Ordem Judicial – 13º Salário | Suspensão do IR sobre o 13º salário por decisão judicial.        |
| 320    | IR sobre Décimo Terceiro Devolvido          | Ajuste do IR referente a valores de 13º salário devolvidos.            |
| 903    | Saldo de Imposto de Renda – Positivo        | Indica que há IR a recolher (saldo devedor).                           |
| 904    | Saldo de Imposto de Renda – Negativo        | Indica que houve retenção excessiva (saldo credor).                    |
| 916    | Consignação IR na Fonte                     | Valor consignado diretamente na fonte para IR.                         |
| 917    | Consignação IR no Exterior                  | Valor consignado para IR sobre rendimentos recebidos no exterior.      |
"""

rubrica_base_tributacao_ir = """
**Rubricas da Base de Tributação – IR**
| Código | Nomenclatura                                   | Descrição                                                               |
|--------|-----------------------------------------------|-------------------------------------------------------------------------|
| 202    | Pensão Alimentícia – Débito                   | Valor pago como pensão alimentícia, dedutível da base de IR.             |
| 203    | Consignacao                                   | Descontos consignados que afetam a base de cálculo do IR.                |
| 206    | Desconto do INSS                              | Contribuições previdenciárias obrigatórias, dedutíveis do IR.            |
| 208    | Contribuição Previdenciária sobre 13º Salário | INSS incidente sobre o 13º salário, também dedutível.                    |
| 210    | Pensão Alimentícia sobre 13º Salário          | Parte do 13º salário destinada à pensão, dedutível.                      |
| 212    | Contribuição Previdenciária sobre 14º Salário | INSS incidente sobre o 14º salário, quando aplicável.                    |
| 213    | Pensão Alimentícia sobre 14º Salário          | Parte do 14º salário destinada à pensão, dedutível.                      |
| 214    | Consignacao sobre 13º Salário                 | Descontos consignados que afetam o 13º salário e a base de IR.           |
| 233    | Desconto para Verificação de Teto             | Ajuste para verificar se o valor ultrapassa o teto de contribuição.      |
| 236    | Décimo Terceiro Salário – Débito              | Valor do 13º salário que entra como débito na base de cálculo.           |
| 242    | CONTRIBUICAO SINDIAPI 0800 777 5767"          | Descontos consignados - associação                                       | 
| 251    | Décimo Terceiro Salário Pago a Maior          | Correção por pagamento excedente de 13º salário.                         |
| 252    | Desconto por Acumulação de Benefício Já Concedido | Ajuste por benefícios acumulados que já foram considerados.         |
| 253    | Desconto por Acumulação de Benefício – 13º Salário | Mesma lógica do anterior, mas aplicado ao 13º salário.           |
"""

rubrica_pagamentos_regulares = """
🟢 **Pagamentos Regulares e Complementares**
| Código | Descrição                                            |
|--------|------------------------------------------------------|
| 101    | Valor total de mensalidade reajustada (MR) do período|
| 104    | Valor do décimo terceiro salário                     |
| 105    | Salário-família                                      |
| 107    | Complemento positivo                                 |
| 110    | Correção monetária                                   |
| 121    | Complemento a título de CPMF                         |
| 159    |CORRECAO MONETARIA COMPLEMENTAR DE RENDA              |  
"""

rubrica_abonos_gratificacoes = """
🟡 **Abonos e Gratificações**
| Código | Descrição                                        |
|--------|--------------------------------------------------|
| 103    | Abono do Governo Federal                         |
| 115    | Abono anual de ex-combatente (14º salário)       |
| 111    | Parcela de gratificação de ex-combatente         |
| 135    | Gratificação de qualidade e produtividade        |
"""

rubrica_revisoes_judiciais = """
🔵 **Revisões e Decisões Judiciais**
| Código | Descrição                                        |
|--------|--------------------------------------------------|
| 106    | Parcela de diferença de revisão da RMI           |
| 125    | CP – Decisão judicial                            |
| 156    | CP – Revisão de teto                             |
| 373    | CP – Artigo 29 ACP-MP242                         |
"""

rubrica_indenizacoes_beneficios = """
🔴 **Indenizações e Benefícios Especiais**
| Código | Descrição                                        |
|--------|--------------------------------------------------|
| 131    | CP - REVISAO BENEFICIO SISTEMA CENTRAL           |
| 145    | Adicional Talidomida                             |
| 146    | Indenização por ação judicial específica         |
| 365    | Indenização Talidomida – Lei 12.190/2010         |
| 375    | CP – Indenização seringueiros                    |
"""

rubrica_consignacoes_descontos = """
🟣 **Consignações e Descontos**
| Código | Descrição                                        |
|--------|--------------------------------------------------|
|  203    | Consignacao                                     |
|  216    | Consignado – Empréstimo bancário                |
| 227    | DEVOLUCAO DE CPMF                                |
| 242    | ConsignacaoCONTRIBUICAO SINDIAPI 0800 777 5767   |
| 254    | Consignacao CONTRIBUICAO UNIBAP                  |
| 288    | CONTRIB. AASAP 0800 202 0177                     |
| 916    | Consignacao IR na fonte                          |
| 920    | Consignacao empréstimo da CEF                    |
| 268    | Consignacao - Cartao                             |
| 383    | RESERVA CARTÃO CONSIGNADO                        |
| 384    | DESCONTO SIMPLIFICADO DE IR                      |
| 385    | DESCONTO SIMPLIFICADO DE IR SOBRE 13             |
| 323    | ADIANTAMENTO DE 13 COMPETENCIA ANTERIOR          |
| 316    | SALDO DEVEDOR ARREDONDAMENTO DE CREDITOS         |

"""

rubrica_impostos_contribuicoes = """
⚪ **Impostos e Contribuições**
| Código | Descrição                                        |
|--------|--------------------------------------------------|
| 201    | IR retido na fonte                               |
| 206    | Desconto do INSS                                 |
| 208    | Contribuição previdenciária sobre 13º salário    |
| 219-250| Diversas contribuições sindicais e associativas  |
"""

# Organizar as rubricas em um dicionário para facilitar o acesso
categorias_rubricas = {
    "Pagamentos Regulares": rubrica_pagamentos_regulares,
    "Abonos e Gratificações": rubrica_abonos_gratificacoes,
    "Revisões Judiciais": rubrica_revisoes_judiciais,
    "Indenizações": rubrica_indenizacoes_beneficios,
    "Consignações": rubrica_consignacoes_descontos,
    "Impostos": rubrica_impostos_contribuicoes,
    "Tributação IR": rubrica_tributacao_ir,
    "Informativas IR": rubrica_informativas_ir,
    "Base Tributação": rubrica_base_tributacao_ir,
    "Exemplos": rubrica_exemplos_mais_comuns
}

# NOVA ORDEM DAS ABAS
aba1, aba2, aba3 = st.tabs(["📋 Referência de Rubricas", "📊 Análise de Rubricas", "🔍 Buscador de Rubricas"])

with aba1:
    st.title("📋 Referência de Rubricas do HISCRE")
    
    st.markdown("""
    ---
    ### ℹ️ **Consulta Rápida:**
    - Use a busca abaixo para encontrar rubricas específicas
    - Navegue pelas categorias para explorar todas as rubricas disponíveis
    - Consulte a descrição oficial de cada código
    ---
    """)
    
    # Adicionar campo de busca
    busca_rubrica = st.text_input("🔍 Buscar rubrica por código ou descrição:", placeholder="Ex: 101 ou mensalidade", key="busca_ref")
    
    # Criar abas para as categorias
    tabs = st.tabs(list(categorias_rubricas.keys()))
    
    for i, (categoria, conteudo) in enumerate(categorias_rubricas.items()):
        with tabs[i]:
            # Se houver uma busca, filtrar o conteúdo
            if busca_rubrica:
                linhas = conteudo.split('\n')
                linhas_filtradas = [linha for linha in linhas if busca_rubrica.lower() in linha.lower()]
                if linhas_filtradas:
                    st.markdown("\n".join(linhas_filtradas))
                else:
                    st.info(f"Nenhuma rubrica encontrada com '{busca_rubrica}' na categoria {categoria}")
            else:
                st.markdown(conteudo)

with aba2:
    st.title("📊 Análise de Rubricas do HISCRE")
    
    st.markdown("""
    ---
    ### ℹ️ **Como funciona:**
    - Faça upload do PDF do demonstrativo HISCRE na sidebar
    - Clique em **"Processar para Análise"**
    - O sistema identificará TODAS as rubricas únicas presentes no documento
    - Para cada rubrica, mostrará a descrição encontrada e a descrição de referência
    - Você poderá baixar o relatório completo em CSV
    ---
    """)
    
    if st.session_state.uploaded_file is None:
        st.info("ℹ️ Faça upload do documento HISCRE na sidebar para começar a análise.")
    elif st.session_state.rubricas_analise is None:
        st.info("ℹ️ Clique em 'Processar para Análise' na sidebar para analisar as rubricas.")
    else:
        rubricas = st.session_state.rubricas_analise
        
        st.success(f"✅ Foram encontradas {len(rubricas)} rubricas únicas no documento!")
        
        # Criar DataFrame para exibição
        df_rubricas = pd.DataFrame.from_dict(rubricas, orient='index')
        df_rubricas.index.name = 'Rubrica'
        df_rubricas.reset_index(inplace=True)
        df_rubricas = df_rubricas[['Rubrica', 'descricao_doc', 'descricao_ref', 'ocorrencias']]
        df_rubricas.columns = ['Rubrica', 'Descrição no Documento', 'Descrição de Referência', 'Ocorrências']
        
        # Ordenar por código da rubrica
        df_rubricas['Rubrica'] = df_rubricas['Rubrica'].astype(int)
        df_rubricas = df_rubricas.sort_values('Rubrica')
        df_rubricas['Rubrica'] = df_rubricas['Rubrica'].astype(str)
        
        st.dataframe(df_rubricas, use_container_width=True)
        
        # Estatísticas
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total de Rubricas Únicas", len(rubricas))
        with col2:
            st.metric("Total de Ocorrências", df_rubricas['Ocorrências'].sum())
        with col3:
            rubricas_sem_ref = len(df_rubricas[df_rubricas['Descrição de Referência'] == "Não encontrada na referência"])
            st.metric("Rubricas sem Referência", rubricas_sem_ref)
        
        # Download do CSV
        csv = df_rubricas.to_csv(index=False, encoding='utf-8-sig')
        st.download_button(
            label="⬇️ Baixar Relatório de Rubricas",
            data=csv,
            file_name='rubricas_unicas_hiscre.csv',
            mime='text/csv',
            key="download_analise"
        )
        
        # Mostrar rubricas não encontradas na referência
        if rubricas_sem_ref > 0:
            st.warning("⚠️ Algumas rubricas não foram encontradas na referência:")
            rubricas_nao_encontradas = df_rubricas[df_rubricas['Descrição de Referência'] == "Não encontrada na referência"]
            st.dataframe(rubricas_nao_encontradas[['Rubrica', 'Descrição no Documento']], use_container_width=True)

with aba3:
    st.title("🔍 Buscador de Rubricas no HISCRE")

    st.markdown("""
    ---
    ### ℹ️ **Como funciona:**
    - Informe até 4 rubricas específicas para buscar (ou deixe em branco para trazer todas)
    - O sistema identifica o **Nome**, os **NBs**, e traz as rubricas com suas **competências, descrição, valor, status e página**
    - Organiza em ordem cronológica por competência
    - Você pode baixar o resultado em CSV
    ---
    """)

    # Seção de entrada de rubricas
    st.subheader("🔎 Rubricas para Busca")

    col1, col2 = st.columns(2)
    with col1:
        rubrica1 = st.text_input("Rubrica 1 (ex.: 101)", key="r1")
        if rubrica1.strip() != "":
            descricao = descricoes_rubricas.get(rubrica1.strip())
            if descricao:
                st.caption(f"Descrição: {descricao}")
            else:
                st.caption("Rubrica não encontrada.")

        rubrica3 = st.text_input("Rubrica 3", key="r3")
        if rubrica3.strip() != "":
            descricao = descricoes_rubricas.get(rubrica3.strip())
            if descricao:
                st.caption(f"Descrição: {descricao}")
            else:
                st.caption("Rubrica não encontrada.")

    with col2:
        rubrica2 = st.text_input("Rubrica 2", key="r2")
        if rubrica2.strip() != "":
            descricao = descricoes_rubricas.get(rubrica2.strip())
            if descricao:
                st.caption(f"Descrição: {descricao}")
            else:
                st.caption("Rubrica não encontrada.")

        rubrica4 = st.text_input("Rubrica 4", key="r4")
        if rubrica4.strip() != "":
            descricao = descricoes_rubricas.get(rubrica4.strip())
            if descricao:
                st.caption(f"Descrição: {descricao}")
            else:
                st.caption("Rubrica não encontrada.")

    rubricas_busca = [r.strip() for r in [rubrica1, rubrica2, rubrica3, rubrica4] if r.strip() != '']

    # Botão de execução da busca
    executar_busca = st.button("🚀 Executar Busca", use_container_width=True, key="exec_busca")
    
    if executar_busca:
        if st.session_state.uploaded_file is None:
            st.warning("⚠️ Por favor, faça upload do PDF primeiro na sidebar.")
        else:
            with st.spinner("⏳ Processando busca..."):
                nome, lista_nbs, df = extrair_dados_pdf(st.session_state.uploaded_file, rubricas_busca)
                st.session_state.dados_extracao = {
                    'nome': nome,
                    'lista_nbs': lista_nbs,
                    'df': df,
                    'mostrar_pagos': False
                }
                st.success("Busca concluída!")
    
    # Exibição dos resultados da busca
    if st.session_state.dados_extracao is not None:
        dados = st.session_state.dados_extracao
        st.success("✅ Dados extraídos com sucesso!")
        st.subheader("🔗 Informações do Beneficiário:")
        st.markdown(f"**Nome:** {dados['nome']}")
        st.markdown(f"**NB:** {', '.join(dados['lista_nbs']) if dados['lista_nbs'] else 'Não encontrado'}")

        col1, col2 = st.columns(2)
        with col1:
            if st.button("Exibir apenas pagos", key="pagos_btn"):
                st.session_state.dados_extracao['mostrar_pagos'] = True
                st.rerun()
        with col2:
            if st.button("Exibir todos", key="todos_btn"):
                st.session_state.dados_extracao['mostrar_pagos'] = False
                st.rerun()

        if st.session_state.dados_extracao.get('mostrar_pagos', False):
            df_filtrado = st.session_state.dados_extracao['df'][st.session_state.dados_extracao['df']["Status"] == "Pago"]
            st.subheader(f"📑 Rubricas com Status 'Pago' (Total: {len(df_filtrado)})")
        else:
            df_filtrado = st.session_state.dados_extracao['df']
            st.subheader("📑 Dados das Rubricas Encontradas:")

        if len(df_filtrado) == 0:
            st.info("Nenhuma rubrica encontrada para o filtro selecionado.")
        else:
            st.dataframe(df_filtrado)
            st.write(f"Quantidade de ocorrências exibidas: **{len(df_filtrado)}**")

            # Exportar o CSV
            csv = df_filtrado.to_csv(index=False, sep=";", encoding='utf-8-sig')
            st.download_button(
                label="⬇️ Baixar CSV",
                data=csv,
                file_name='rubricas_por_competencia.csv',
                mime='text/csv',
            )
