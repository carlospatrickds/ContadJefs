import streamlit as st
import os
import zipfile
import shutil
from datetime import datetime

def desbloquear_vba(path_arquivo_xlsm, destino):
    try:
        if not zipfile.is_zipfile(path_arquivo_xlsm):
            return False, "❌ O arquivo não parece ser um .xlsm válido."

        # Criar uma cópia temporária
        temp_dir = "xlsm_temp"
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
        os.makedirs(temp_dir)

        with zipfile.ZipFile(path_arquivo_xlsm, 'r') as zip_ref:
            zip_ref.extractall(temp_dir)

        vba_path = os.path.join(temp_dir, "xl", "vbaProject.bin")
        if not os.path.exists(vba_path):
            return False, "❌ Nenhum projeto VBA encontrado no arquivo."

        # Lê o conteúdo binário
        with open(vba_path, "rb") as file:
            content = file.read()

        # Remove os bytes típicos da proteção de senha
        patched = content.replace(b'DPB=', b'DPx=')

        # Salva o conteúdo editado
        with open(vba_path, "wb") as file:
            file.write(patched)

        # Nome único para o arquivo de saída
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        nome_arquivo = f"arquivo_desbloqueado_{timestamp}.xlsm"
        novo_arquivo = os.path.join(destino, nome_arquivo)
        
        # Cria novo arquivo desbloqueado
        with zipfile.ZipFile(novo_arquivo, 'w', zipfile.ZIP_DEFLATED) as new_zip:
            for root, dirs, files in os.walk(temp_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    zip_name = os.path.relpath(file_path, temp_dir)
                    new_zip.write(file_path, zip_name)

        # Limpeza
        shutil.rmtree(temp_dir)
        
        return True, nome_arquivo
        
    except Exception as e:
        return False, f"❌ Erro: {str(e)}"

# Interface Streamlit
st.set_page_config(page_title="Desbloqueador VBA", page_icon="🔓")

st.title("🔓 Desbloqueador de Projetos VBA Excel")
st.markdown("Remova a proteção de senha de arquivos .xlsm")

# Upload do arquivo
arquivo = st.file_uploader(
    "Selecione o arquivo .xlsm protegido",
    type=["xlsm"],
    help="Arquivo Excel com macros protegidas por senha"
)

if arquivo:
    # Salva o arquivo temporariamente
    with open("temp_file.xlsm", "wb") as f:
        f.write(arquivo.getbuffer())
    
    if st.button("🚀 Desbloquear VBA", type="primary"):
        with st.spinner("Processando arquivo..."):
            sucesso, mensagem = desbloquear_vba("temp_file.xlsm", ".")
            
            if sucesso:
                st.success("✅ Projeto VBA desbloqueado com sucesso!")
                
                # Disponibiliza download
                with open(mensagem, "rb") as file:
                    st.download_button(
                        label="📥 Baixar arquivo desbloqueado",
                        data=file,
                        file_name=mensagem,
                        mime="application/vnd.ms-excel.sheet.macroEnabled.12"
                    )
                
                # Limpa arquivo temporário
                os.remove("temp_file.xlsm")
                
            else:
                st.error(mensagem)

# Sidebar com informações
with st.sidebar:
    st.header("ℹ️ Informações")
    st.markdown("""
    **Como usar:**
    1. Faça upload do arquivo .xlsm
    2. Clique em 'Desbloquear VBA'
    3. Baixe o arquivo desbloqueado
    
    **⚠️ Aviso Legal:**
    Use apenas para arquivos dos quais você é o proprietário legítimo.
    
    **Funcionalidades:**
    - Remove proteção de senha do VBA
    - Mantém todas as macros funcionando
    - Não altera o arquivo original
    """)

# Rodapé
st.markdown("---")
st.caption("Ferramenta para recuperação de arquivos próprios com senha esquecida")
