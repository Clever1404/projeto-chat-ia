import re
from playwright.sync_api import Page, expect

def test_fluxo_fale_conosco_e_video(page: Page):
    # 1. Acessa o sistema local
    page.goto("http://localhost:8501/")
    
    # 2. Fluxo de Login
    page.get_by_role("textbox", name="Usuário").click()
    page.get_by_role("textbox", name="Usuário").fill("Gabriel")
    page.get_by_role("textbox", name="Usuário").press("Tab")
    page.get_by_role("textbox", name="Senha").fill("405167")
    page.get_by_test_id("stBaseButton-primaryFormSubmit").click()
    
    # 3. Navegação para o Fale Conosco
    page.get_by_role("button", name="✉️ Fale Conosco").click()
    
    # 4. Preenchimento do Formulário
    page.get_by_role("textbox", name="Seu E-mail de Contato:").click()
    page.get_by_role("textbox", name="Seu E-mail de Contato:").fill("gabriel@gmail.com")
    page.get_by_role("textbox", name="Seu E-mail de Contato:").press("Tab")
    page.get_by_role("textbox", name="Escreva sua Mensagem / Sugest").fill("melhoria no layout")
    page.get_by_test_id("stBaseButton-primaryFormSubmit").click()
    
    # --- Correção do fluxo do Chat e Vídeo ---
    
    # 5. Clica para voltar ao Chat Principal onde o botão de vídeo está disponível
    page.get_by_role("button", name="← Voltar para o Chat Principal").click()
    page.wait_for_timeout(1000) # Aguarda a transição de tela
    
    # 6. Clica no botão usando o texto exato e o emoji conforme declarado no app_streamlit.py
    page.get_by_role("button", name="🎥 Iniciar Videochamada Privada").click()
    
    # 7. Aguarda o carregamento do Iframe do Jitsi e valida
    page.wait_for_timeout(2000) 
    expect(page.locator("iframe")).to_be_visible()

      # 7. Aguarda o carregamento do Iframe do Jitsi e valida
    page.wait_for_timeout(2000)
    expect(page.locator("iframe")).to_be_visible()
    
    # LINHA NOVA: Força o navegador a ficar aberto por 15 segundos antes de fechar
    page.wait_for_timeout(15000)