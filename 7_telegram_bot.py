import os
import sys
import time
import json
import logging
from dotenv import load_dotenv

from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters
from google import genai
from importlib import import_module

# Importa o módulo do Google Docs
exportar_docs = import_module("6_exportar_google_docs")

# Importa o modelo Whisper (usando faster-whisper)
from faster_whisper import WhisperModel

load_dotenv()

# Configuração de Logs no Terminal
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", 
    level=logging.INFO
)

PASTA_AUDIOS_TEMP = "audios_telegram"
MODELO_WHISPER_NOME = "large-v3-turbo"

# Carrega a chave do Bot no .env
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not TELEGRAM_BOT_TOKEN:
    raise ValueError("❌ 'TELEGRAM_BOT_TOKEN' não encontrado no arquivo .env!")

# Cria pasta temporária para salvar as notas de voz recebidas
os.makedirs(PASTA_AUDIOS_TEMP, exist_ok=True)

# Carrega o modelo Whisper em memória (CPU com suporte a FP32/INT8)
print(f"⚡ Carregando modelo Whisper '{MODELO_WHISPER_NOME}'...")
whisper_model = WhisperModel(MODELO_WHISPER_NOME, device="cpu", compute_type="int8")


def transcrever_audio_local(caminho_audio: str) -> str:
    """Transcreve o arquivo de áudio usando o Whisper localmente."""
    segments, info = whisper_model.transcribe(
        caminho_audio, 
        language="pt", 
        beam_size=1, 
        vad_filter=True
    )
    texto_transcrito = " ".join([segment.text for segment in segments]).strip()
    return texto_transcrito


def refinar_texto_com_gemini(texto_bruto: str) -> str:
    """Formata e pontua o texto bruto usando o Gemini LLM."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("Chave GEMINI_API_KEY não encontrada no arquivo .env!")

    client = genai.Client(api_key=api_key)

    prompt = f"""
    Você é um editor de texto especializado em transcrições de áudio.
    Sua única função é aplicar pontuação e formatação para tornar a leitura fluida, sem alterar o vocabulário ou o estilo do autor.

    DIRETRIZES RÍGIDAS DE EDIÇÃO:
    1. FIDELIDADE LITERAL (SEM PARÁFRASE): Mantenha exatamente as mesmas palavras, termos e estrutura das frases. É PROIBIDO substituir palavras por sinônimos ou reescrever trechos com suas próprias palavras.
    2. PONTUAÇÃO E PARÁGRAFOS: Adicione vírgulas, pontos finais e quebras de parágrafo lógicas onde houver pausas na narrativa para facilitar a leitura.
    3. REMOÇÃO EXCLUSIVA DE RUÍDOS DE FALA: Remova apenas vícios de linguagem e hesitações vazias que prejudiquem a fluidez (ex: "né", "tipo assim", "eh", "hum", repetições acidentais de palavras). 
       - ATENÇÃO: Preserve marcas de dúvida ou opinião do relator (ex: "eu acho que", "não sei", "sei lá"), pois elas fazem parte do conteúdo do sonho.
    4. PRESERVAÇÃO DE CONTEÚDO: Mantenha a narrativa estritamente em primeira pessoa e preserve 100% dos detalhes, lugares, nomes e ordem dos acontecimentos.

    Texto bruto transcrito do áudio:
    \"\"\"{texto_bruto}\"\"\"

    Retorne APENAS o texto formatado, sem introduções, saudações ou explicações.
    """

    response = client.models.generate_content(
        model="gemini-3.6-flash",
        contents=prompt,
    )
    return response.text.strip()


async def processar_mensagem_de_voz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Função executada automaticamente toda vez que você envia um áudio no Telegram."""
    try:
        user = update.effective_user
        logging.info(f"🎤 Novo áudio recebido de {user.first_name}!")

        # Envia feedback imediato no chat
        msg_status = await update.message.reply_text("📥 Áudio recebido! Baixando e iniciando transcrição...")

        # 1. Baixa a nota de voz do Telegram (.ogg)
        voice = update.message.voice or update.message.audio
        arquivo_telegram = await context.bot.get_file(voice.file_id)
        
        timestamp_str = time.strftime("%Y%m%d_%H%M%S")
        caminho_local_audio = os.path.join(PASTA_AUDIOS_TEMP, f"sonho_{timestamp_str}.ogg")
        await arquivo_telegram.download_to_drive(caminho_local_audio)

        # 2. Transcrição com Whisper
        await msg_status.edit_text("⚡ Transcrevendo áudio com Whisper local...")
        texto_bruto = transcrever_audio_local(caminho_local_audio)

        if not texto_bruto:
            await msg_status.edit_text("⚠️ Não foi possível identificar nenhuma fala no áudio enviado.")
            return

        # 3. Refinamento com Gemini
        await msg_status.edit_text("✨ Refinando pontuação e estilo com o Gemini LLM...")
        texto_refinado = refinar_texto_com_gemini(texto_bruto)

        # 4. Publicação no Google Docs
        await msg_status.edit_text("📄 Publicando no seu diário no Google Docs...")
        doc_url = exportar_docs.publicar_sonho_no_docs(
            texto_refinado=texto_refinado,
            nome_identificador=f"Sonho ({time.strftime('%H:%M')})"
        )

        # 5. Resposta final no Telegram
        resposta_final = (
            f"🎉 **Sonho registrado com sucesso!**\n\n"
            f"📝 **Resumo do Relato:**\n_{texto_refinado[:200]}..._\n\n"
            f"🔗 [Clique aqui para abrir no Google Docs]({doc_url})"
        )
        await msg_status.edit_text(resposta_final, parse_mode="Markdown", disable_web_page_preview=True)

        # Limpeza do arquivo de áudio temporário
        if os.path.exists(caminho_local_audio):
            os.remove(caminho_local_audio)

    except Exception as e:
        logging.error(f"Erro ao processar mensagem de voz: {e}")
        if 'msg_status' in locals():
            await msg_status.edit_text(f"❌ Ocorreu um erro ao processar seu relato: {e}")


def main():
    """Inicia o Bot do Telegram e mantém o escutador ativo."""
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    # Registra o manipulador de mensagens de voz e áudios
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, processar_mensagem_de_voz))

    print("\n🤖 ==================================================")
    print("🤖 DREAMLISTENER BOT ESTÁ RODANDO E PRONTO PARA RECEBER ÁUDIOS!")
    print("🤖 Abra seu Telegram, grave uma nota de voz e confira a mágica.")
    print("🤖 Pressione Ctrl + C no terminal para encerrar.")
    print("🤖 ==================================================\n")

    app.run_polling()


if __name__ == "__main__":
    main()