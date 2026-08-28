import os
import sys
import time
import json
import logging
from dotenv import load_dotenv

from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters
from google import genai
from groq import Groq
from app import export_docs

load_dotenv()

# Configuração de Logs
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", 
    level=logging.INFO
)

PASTA_AUDIOS_TEMP = "audios_telegram"
os.makedirs(PASTA_AUDIOS_TEMP, exist_ok=True)

# Validando Chaves de API no .env
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not TELEGRAM_BOT_TOKEN:
    raise ValueError("❌ 'TELEGRAM_BOT_TOKEN' não encontrado no arquivo .env!")
if not GROQ_API_KEY:
    raise ValueError("❌ 'GROQ_API_KEY' não encontrada no arquivo .env!")
if not GEMINI_API_KEY:
    raise ValueError("❌ 'GEMINI_API_KEY' não encontrada no arquivo .env!")

# Instancia o cliente da Groq
groq_client = Groq(api_key=GROQ_API_KEY)


def transcrever_audio_groq(caminho_audio: str) -> str:
    """
    Envia o arquivo de áudio para a API da Groq executando whisper-large-v3 em alta velocidade.
    """
    with open(caminho_audio, "rb") as file:
        transcription = groq_client.audio.transcriptions.create(
            file=(os.path.basename(caminho_audio), file.read()),
            model="whisper-large-v3",
            language="pt",
            response_format="text"
        )
    return transcription.strip()


def refinar_texto_com_gemini(texto_bruto: str) -> str:
    """Formata e pontua o texto bruto usando o Gemini LLM."""
    client = genai.Client(api_key=GEMINI_API_KEY)

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
    caminho_local_audio = None
    try:
        user = update.effective_user
        logging.info(f"🎤 Novo áudio recebido de {user.first_name}!")

        msg_status = await update.message.reply_text("📥 Áudio recebido! Baixando...")

        # 1. Baixa o arquivo de áudio do Telegram
        voice = update.message.voice or update.message.audio
        arquivo_telegram = await context.bot.get_file(voice.file_id)
        
        timestamp_str = time.strftime("%Y%m%d_%H%M%S")
        caminho_local_audio = os.path.join(PASTA_AUDIOS_TEMP, f"sonho_{timestamp_str}.ogg")
        await arquivo_telegram.download_to_drive(caminho_local_audio)

        # 2. Transcrição Ultra-Rápida com Groq Whisper Large-V3
        await msg_status.edit_text("⚡ Transcrevendo áudio em alta velocidade com Groq (Whisper Large-V3)...")
        texto_bruto = transcrever_audio_groq(caminho_local_audio)

        if not texto_bruto:
            await msg_status.edit_text("⚠️ Não foi possível identificar nenhuma fala no áudio enviado.")
            return

        # 3. Refinamento com Gemini
        await msg_status.edit_text("✨ Refinando pontuação e estrutura com o Gemini LLM...")
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
            f"📝 **Resumo do Relato:**\n_{texto_refinado[:250]}..._\n\n"
            f"🔗 [Clique aqui para abrir no Google Docs]({doc_url})"
        )
        await msg_status.edit_text(resposta_final, parse_mode="Markdown", disable_web_page_preview=True)

    except Exception as e:
        logging.error(f"Erro ao processar mensagem de voz: {e}")
        if 'msg_status' in locals():
            await msg_status.edit_text(f"❌ Ocorreu um erro ao processar seu relato: {e}")

    finally:
        # Garante a remoção do arquivo local temporário
        if caminho_local_audio and os.path.exists(caminho_local_audio):
            os.remove(caminho_local_audio)


def main():
    """Inicia o Bot do Telegram e mantém o listener ativo."""
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, processar_mensagem_de_voz))

    print("\n🤖 ==================================================")
    print("🤖 DREAMLISTENER BOT ATIVO (API GROQ WHISPER LARGE-V3)!")
    print("🤖 Envie um áudio no Telegram e veja a resposta em poucos segundos.")
    print("🤖 Pressione Ctrl + C no terminal para encerrar.")
    print("🤖 ==================================================\n")

    app.run_polling()


if __name__ == "__main__":
    main()