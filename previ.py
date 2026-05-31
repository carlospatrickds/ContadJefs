import pandas as pd
import numpy as np
from datetime import datetime

# ============================================
# CONFIGURAÇÕES INICIAIS
# ============================================

# Dados do processo
PARTICIPACAO_AUTORA = 0.80  # 80%
VALOR_QUOTA_RESGATE = 13.695656  # Valor da quota em 10/2006
DATA_RESGATE = "2006-10-20"
VALOR_JA_PAGO = 112163.52  # 80% de R$ 141.546,63

# Expurgos inflacionários conforme julgado
# Formato: (ano, mês): percentual
EXPURGOS = {
    (1987, 6): 0.2606,    # Bresser
    (1989, 1): 0.4272,    # Verão
    (1990, 3): 0.8432,    # Collor I
    (1990, 4): 0.4480,
    (1990, 5): 0.0787,
    (1990, 6): 0.1292,
    (1991, 1): 0.2187,    # Collor II
    (1991, 2): 0.1390,
}

# ============================================
# FUNÇÃO PRINCIPAL DE CÁLCULO
# ============================================

def calcular_liquidação_com_expurgos(df_previ, taxa_juros_mensal=0.01):
    """
    Calcula a liquidação aplicando os expurgos inflacionários
    
    Parâmetros:
    - df_previ: DataFrame com a planilha original da PREVI
    - taxa_juros_mensal: taxa de juros de mora (padrão 1% a.m.)
    
    Retorna:
    - dict com resultados detalhados
    """
    
    # Criar cópia para não modificar o original
    df = df_previ.copy()
    
    # Converter coluna de data se necessário
    if 'Data' not in df.columns:
        df['Data'] = pd.to_datetime(df['Competencia'].astype(str) + '-01', 
                                     format='%m/%Y-%d', errors='coerce')
        df['Ano'] = df['Data'].dt.year
        df['Mes'] = df['Data'].dt.month
    else:
        df['Ano'] = df['Data'].dt.year
        df['Mes'] = df['Data'].dt.month
    
    # Calcular saldo acumulado corrigido mês a mês (reproduzindo a PREVI)
    df['Saldo_Acumulado_Corrigido'] = df['Acumulado']  # Já vem corrigido na planilha original
    
    # ========================================
    # APLICAÇÃO DOS EXPURGOS
    # ========================================
    
    df['Diferenca_Expurgo_Bruta'] = 0.0
    df['Mes_Expurgo'] = None
    df['Percentual_Expurgo'] = 0.0
    
    for idx, row in df.iterrows():
        chave = (row['Ano'], row['Mes'])
        if chave in EXPURGOS:
            # O expurgo incide sobre o saldo acumulado do MÊS ANTERIOR
            if idx > 0:
                saldo_anterior = df.loc[idx-1, 'Acumulado']
                df.loc[idx, 'Diferenca_Expurgo_Bruta'] = saldo_anterior * EXPURGOS[chave]
                df.loc[idx, 'Mes_Expurgo'] = f"{row['Mes']:02d}/{row['Ano']}"
                df.loc[idx, 'Percentual_Expurgo'] = EXPURGOS[chave] * 100
    
    # ========================================
    # ATUALIZAÇÃO DAS DIFERENÇAS ATÉ O RESGATE
    # ========================================
    # Nota: Para precisão total, seria necessário usar os índices oficiais
    # ORTN/OTN/BTN/TR de cada período. Aqui usamos uma aproximação.
    
    # Fator de atualização simplificado (substituir por índices reais)
    # Este é um placeholder - em produção, usar tabela de índices do BACEN/IBGE
    
    def fator_atualizacao_simplificado(ano_mes_origem, ano_mes_destino=(2006, 10)):
        """
        Calcula fator de atualização monetária aproximado
        Substituir por cálculo com índices oficiais para precisão pericial
        """
        from dateutil.relativedelta import relativedelta
        
        data_origem = datetime(ano_mes_origem[0], ano_mes_origem[1], 1)
        data_destino = datetime(ano_mes_destino[0], ano_mes_destino[1], 1)
        
        meses = (data_destino.year - data_origem.year) * 12 + \
                (data_destino.month - data_origem.month)
        
        # Taxa média de inflação histórica aproximada: 0.8% a.m.
        # (substituir por índice oficial do período)
        return (1 + 0.008) ** meses if meses > 0 else 1.0
    
    df['Fator_Atualizacao'] = df.apply(
        lambda row: fator_atualizacao_simplificado((row['Ano'], row['Mes'])) 
        if row['Diferenca_Expurgo_Bruta'] > 0 else 1.0, 
        axis=1
    )
    
    df['Diferenca_Atualizada'] = df['Diferenca_Expurgo_Bruta'] * df['Fator_Atualizacao']
    
    # ========================================
    # CÁLCULO FINAL
    # ========================================
    
    total_diferencas_brutas = df['Diferenca_Expurgo_Bruta'].sum()
    total_diferencas_atualizadas = df['Diferenca_Atualizada'].sum()
    
    participacao_autora_expurgos = total_diferencas_atualizadas * PARTICIPACAO_AUTORA
    
    # Valor devido antes de juros
    saldo_devedor_base = participacao_autora_expurgos - VALOR_JA_PAGO
    
    # Juros de mora desde o resgate até hoje (aproximado)
    data_hoje = datetime.now()
    data_resgate_dt = datetime.strptime(DATA_RESGATE, "%Y-%m-%d")
    meses_atraso = (data_hoje.year - data_resgate_dt.year) * 12 + \
                   (data_hoje.month - data_resgate_dt.month)
    
    fator_juros = (1 + taxa_juros_mensal) ** meses_atraso
    saldo_com_juros = saldo_devedor_base * fator_juros if saldo_devedor_base > 0 else 0
    
    # Honorários sucumbenciais (15%)
    honorarios = saldo_com_juros * 0.15 if saldo_com_juros > 0 else 0
    
    # Total final
    total_devido = saldo_com_juros + honorarios
    
    return {
        'df_detalhado': df[df['Diferenca_Expurgo_Bruta'] > 0],
        'total_diferencas_brutas': total_diferencas_brutas,
        'total_diferencas_atualizadas': total_diferencas_atualizadas,
        'participacao_autora_expurgos': participacao_autora_expurgos,
        'valor_ja_pago': VALOR_JA_PAGO,
        'saldo_devedor_base': saldo_devedor_base,
        'meses_atraso': meses_atraso,
        'fator_juros': fator_juros,
        'saldo_com_juros': saldo_com_juros,
        'honorarios_sucumbenciais': honorarios,
        'total_final_devido': total_devido,
        'data_calculo': data_hoje.strftime("%d/%m/%Y")
    }


# ============================================
# FUNÇÃO PARA EXPORTAR PARA EXCEL
# ============================================

def exportar_planilha_completa(df_previ, nome_arquivo="Liquidação_Marta_Veiga_Damaso.xlsx"):
    """
    Gera arquivo Excel com todas as abas necessárias
    """
    resultado = calcular_liquidação_com_expurgos(df_previ)
    
    with pd.ExcelWriter(nome_arquivo, engine='openpyxl') as writer:
        
        # Aba 1: Planilha original da PREVI (reprodução)
        df_previ.to_excel(writer, sheet_name='Original_PREVI', index=False)
        
        # Aba 2: Cálculo dos expurgos (apenas meses impactados)
        resultado['df_detalhado'].to_excel(
            writer, 
            sheet_name='Expurgos_Aplicados', 
            index=False,
            columns=['Competencia', 'Acumulado', 'Mes_Expurgo', 'Percentual_Expurgo',
                    'Diferenca_Expurgo_Bruta', 'Fator_Atualizacao', 'Diferenca_Atualizada']
        )
        
        # Aba 3: Resumo do cálculo
        resumo = pd.DataFrame([
            ['Item', 'Valor (R$)', 'Observação'],
            ['Total Diferenças Brutas dos Expurgos', f"{resultado['total_diferencas_brutas']:,.2f}", ''],
            ['Total Diferenças Atualizadas', f"{resultado['total_diferencas_atualizadas']:,.2f}", 'Até 10/2006'],
            ['Participação da Autora (80%)', f"{resultado['participacao_autora_expurgos']:,.2f}", ''],
            ['(-) Valor já pago administrativamente', f"-{VALOR_JA_PAGO:,.2f}", '80% de R$ 141.546,63'],
            ['Saldo Devedor Base', f"{resultado['saldo_devedor_base']:,.2f}", ''],
            ['Juros de Mora (1% a.m.)', f"{resultado['saldo_com_juros'] - resultado['saldo_devedor_base']:,.2f}", 
             f"{resultado['meses_atraso']} meses desde 10/2006"],
            ['Saldo com Juros', f"{resultado['saldo_com_juros']:,.2f}", ''],
            ['Honorários Sucumbenciais (15%)', f"{resultado['honorarios_sucumbenciais']:,.2f}", ''],
            ['TOTAL FINAL DEVIDO', f"{resultado['total_final_devido']:,.2f}", f"Data cálculo: {resultado['data_calculo']}"]
        ])
        resumo.to_excel(writer, sheet_name='Resumo_Calculo', index=False)
        
        # Aba 4: Memorial descritivo
        memorial = pd.DataFrame([
            ['MEMORIAL DE CÁLCULO - LIQUIDAÇÃO DE SENTENÇA'],
            [''],
            ['Processo:', '0060263-06.2007.8.17.0001'],
            ['Autora:', 'Marta Veiga Damaso'],
            ['Réu:', 'PREVI - Caixa de Previdência dos Funcionários do Banco do Brasil'],
            [''],
            ['OBJETO:', 'Diferenças de correção monetária sobre reserva de poupança'],
            [''],
            ['PERÍODO CONTRIBUTIVO:', '24/01/1983 a 13/09/2006'],
            ['DATA DO RESGATE:', '20/10/2006'],
            ['VALOR DA QUOTA NO RESGATE:', 'R$ 13,695656'],
            [''],
            ['EXPURGOS APLICADOS CONFORME JULGADO:'],
            ['• Plano Bresser (06/1987): 26,06%'],
            ['• Plano Verão (01/1989): 42,72%'],
            ['• Plano Collor I (03-06/1990): 84,32%, 44,80%, 7,87%, 12,92%'],
            ['• Plano Collor II (01-02/1991): 21,87%, 13,90%'],
            [''],
            ['METODOLOGIA:'],
            ['1. Cada expurgo incide sobre o saldo acumulado corrigido do mês ANTERIOR'],
            ['2. As diferenças são atualizadas monetariamente até 10/2006'],
            ['3. Aplica-se participação de 80% da autora'],
            ['4. Subtrai-se valor já pago: R$ 112.163,52'],
            ['5. Acrescem-se juros de mora de 1% a.m. desde 10/2006'],
            ['6. Incluem-se honorários sucumbenciais de 15%'],
            [''],
            ['OBSERVAÇÃO:'],
            ['Os fatores de atualização monetária utilizados são aproximados.',
             'Para cálculo pericial definitivo, utilizar índices oficiais ORTN/OTN/BTN/TR',
             'do Banco Central/IBGE para cada período específico.']
        ])
        memorial.to_excel(writer, sheet_name='Memorial', index=False, header=False)
    
    return resultado


# ============================================
# EXECUÇÃO PRINCIPAL
# ============================================

if __name__ == "__main__":
    # Carregar sua planilha da PREVI (ajustar caminho)
    # df_previ = pd.read_excel("sua_planilha_previ.xlsx")
    
    # Para demonstração, criar estrutura mínima esperada:
    # (substituir pelo carregamento real do seu arquivo)
    
    print("✅ Script pronto para processar sua planilha da PREVI")
    print("✅ Expurgos configurados conforme julgado")
    print("✅ Saída: arquivo Excel com 4 abas organizadas")
    print("\nPróximos passos:")
    print("1. Carregue seu arquivo Excel com pd.read_excel()")
    print("2. Execute exportar_planilha_completa(df_previ)")
    print("3. Confira a aba 'Resumo_Calculo' para o valor final")
