# Página de síntese (Corrigida)
    if dados_sintese:
        pdf.add_page()
        pdf.set_font('Arial', 'B', 11)
        pdf.cell(0, 10, 'Síntese Comparativa', ln=True, align='C')
        pdf.ln(5)

        # Cabeçalho com larguras ajustadas (total 195mm)
        pdf.set_font('Arial', 'B', 8)
        
        # Salva a margem esquerda original (geralmente é 10)
        margem_esquerda = pdf.get_x()
        
        pdf.cell(15, 8, 'Ano', border=1)
        pdf.cell(30, 8, 'Valor Base 1', border=1)
        pdf.cell(30, 8, 'Valor Base 2', border=1)
        pdf.cell(30, 8, 'Contrib. Base 1', border=1) 
        pdf.cell(30, 8, 'Contrib. Base 2', border=1)
        
        # 1. Salva as coordenadas atuais (X e Y) antes das células problemáticas
        x = pdf.get_x()
        y = pdf.get_y()
        
        # 2. Usa multi_cell para permitir a quebra de linha (altura 4 por linha = 8 no total)
        pdf.multi_cell(28, 4, 'Diferença entre\nvalores_base', border=1, align='C')
        
        # 3. Restaura o cursor para o lado direito da célula anterior e imprime a última coluna
        pdf.set_xy(x + 28, y)
        pdf.multi_cell(32, 4, 'Diferença\nContribuição', border=1, align='C')

        # ---------------------------------------------------------------------
        # CORREÇÃO: Força o cursor a voltar para o começo e pular a linha inteira do cabeçalho
        pdf.set_xy(margem_esquerda, y + 8)
        # ---------------------------------------------------------------------

        pdf.set_font('Arial', '', 8)
        
        total_diff_contrib = 0.0
        
        for linha in dados_sintese:
            pdf.cell(15, 8, str(linha['Ano']), border=1)
            pdf.cell(30, 8, linha['Valor Base 1'], border=1)
            pdf.cell(30, 8, linha['Valor Base 2'], border=1)
            pdf.cell(30, 8, linha['Contribuição Base 1'], border=1)
            pdf.cell(30, 8, linha['Contribuição Base 2'], border=1)
            pdf.cell(28, 8, linha['Diferença entre valores_base'], border=1)
            pdf.cell(32, 8, linha['Diferença Contribuição'], border=1)
            pdf.ln()
            total_diff_contrib += linha['diff_contrib_raw']

        # Linha de total (Somando apenas a diferença de contribuição)
        pdf.set_font('Arial', 'B', 8)
        pdf.cell(15, 8, 'Total', border=1)
        pdf.cell(30, 8, '', border=1)
        pdf.cell(30, 8, '', border=1)
        pdf.cell(30, 8, '', border=1)
        pdf.cell(30, 8, '', border=1)
        pdf.cell(28, 8, '-', border=1, align='C') # Retirada a soma da base
        pdf.cell(32, 8, formatar_moeda(total_diff_contrib), border=1)
        pdf.ln()
