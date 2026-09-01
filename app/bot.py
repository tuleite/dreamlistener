import os
import logging
import tempfile
import time
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, CommandHandler, filters
from groq import Groq
from google import genai
from google.genai.errors import APIError

from app import export_docs

# Configuração de Logs
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Carrega variáveis do .env
load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not TELEGRAM_BOT_TOKEN or not GROQ_API_KEY or not GEMINI_API_KEY:
    raise ValueError("❌ Verifique se TELEGRAM_BOT_TOKEN, GROQ_API_KEY e GEMINI_API_KEY estão no .env!")

# Clientes das APIs
groq_client = Groq(api_key=GROQ_API_KEY)
gemini_client = genai.Client(api_key=GEMINI_API_KEY)

# Lista priorizada de modelos (da maior qualidade para maior disponibilidade no Free Tier)
MODELOS_GEMINI_FALLBACK = [
    "gemini-3.6-flash",       # Primário: Maior precisão gramatical/narrativa
    "gemini-3.1-flash-lite",  # Secundário: Ultra-rápido, cota separada
    "gemini-1.5-flash"        # Terciário: Fallback estável de alta disponibilidade
]


def transcrever_audio_groq(caminho_audio: str) -> str:
    """Envia o arquivo de áudio para a API da Groq (Whisper Large-V3)."""
    with open(caminho_audio, "rb") as file:
        transcription = groq_client.audio.transcriptions.create(
            file=(os.path.basename(caminho_audio), file.read()),
            model="whisper-large-v3",
            language="pt",
            response_format="text",
            temperature=0.0
        )
    return transcription.strip()


def refinar_texto_com_gemini(texto_bruto: str) -> str:
    """
    Envia a transcrição para a API do Gemini com suporte a Fallback em Cascata
    entre diferentes modelos e Retry automático contra erros 503 e 429.
    """
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

    for modelo in MODELOS_GEMINI_FALLBACK:
        for tentativa in range(1, 3):
            try:
                logger.info(f"⏳ Tentando refinamento com '{modelo}' (tentativa {tentativa})...")
                response = gemini_client.models.generate_content(
                    model=modelo,
                    contents=prompt,
                )
                if response and response.text:
                    return response.text.strip()

            except APIError as e:
                codigo_erro = getattr(e, "code", None)
                
                # Trata indisponibilidade (503) ou cota estourada (429)
                if codigo_erro in [429, 503] or "RESOURCE_EXHAUSTED" in str(e) or "UNAVAILABLE" in str(e):
                    tempo_espera = tentativa * 2  # Espera 2s na 1ª tentativa, 4s na 2ª
                    logger.warning(f"⚠️ Modelo '{modelo}' indisponível/cota estourada ({codigo_erro}). Aguardando {tempo_espera}s...")
                    time.sleep(tempo_espera)
                else:
                    logger.error(f"❌ Erro não recuperável no modelo '{modelo}': {e}")
                    break  # Sai das tentativas e pula para o próximo modelo

            except Exception as e:
                logger.error(f"❌ Erro inesperado ao chamar '{modelo}': {e}")
                break

    raise RuntimeError("❌ Todos os modelos do Gemini falharam ou estão indisponíveis no momento.")


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Responde ao comando /start com instruções de uso."""
    mensagem = (
        "🌙 **Bem-vindo ao Dreamlistener!**\n\n"
        "Envie uma mensagem de voz ou áudio contando o seu sonho.\n"
        "Eu irei transcrever, organizar e publicar automaticamente no seu Diário de Sonhos no Google Docs!"
    )
    await update.message.reply_text(mensagem, parse_mode="Markdown")


async def processar_mensagem_de_voz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handler principal do Telegram:
    1. Baixa o áudio enviado
    2. Transcreve via Groq (Whisper Large-V3)
    3. Refina via Gemini LLM (com Fallback)
    4. Publica na aba correta do Google Docs
    5. Responde ao usuário com o link do documento
    """
    mensagem_status = await update.message.reply_text("🎧 Recebi seu áudio! Processando transcrição...")

    try:
        # Pega a mensagem de áudio ou voz
        audio_file = update.message.voice or update.message.audio
        if not audio_file:
            await mensagem_status.edit_text("❌ Por favor, envie um arquivo de áudio ou mensagem de voz válido.")
            return

        # 1. Download do áudio para um arquivo temporário no sistema
        file_info = await context.bot.get_file(audio_file.file_id)
        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as temp_audio:
            temp_audio_path = temp_audio.name

        await file_info.download_to_drive(temp_audio_path)

        # 2. Transcrição ASR via Groq (Whisper)
        await mensagem_status.edit_text("⚡ Transcrevendo áudio em alta velocidade (Groq)...")
        texto_bruto = transcrever_audio_groq(temp_audio_path)

        # Remove o arquivo temporário de áudio da memória/disco
        if os.path.exists(temp_audio_path):
            os.remove(temp_audio_path)

        if not texto_bruto:
            await mensagem_status.edit_text("⚠️ Não consegui identificar nenhuma fala no áudio enviado.")
            return

        # 3. Refinamento via Gemini LLM (com resiliência de modelos)
        await mensagem_status.edit_text("✍️ Refinando e formatando o relato (Gemini)...")
        texto_refinado = refinar_texto_com_gemini(texto_bruto)

        # 4. Publicação no Google Docs
        await mensagem_status.edit_text("📄 Registrando no seu Diário de Sonhos no Google Docs...")
        doc_url = export_docs.publicar_sonho_no_docs(
            texto_refinado=texto_refinado,
            nome_identificador=f"Voz_{update.message.message_id}"
        )

        # 5. Resposta final para o usuário
        resposta_final = (
            "✨ **Sonho registrado com sucesso!**\n\n"
            f"📝 **Relato:**\n_{texto_refinado}_\n\n"
            f"🔗 [Clique aqui para abrir no Google Docs]({doc_url})"
        )
        await mensagem_status.edit_text(resposta_final, parse_mode="Markdown", disable_web_page_preview=True)

    except Exception as e:
        logger.error(f"Erro ao processar mensagem de voz: {e}", exc_info=True)
        await mensagem_status.edit_text(
            "❌ Ocorreu um erro ao processar seu relato. Por favor, tente enviar novamente em instantes."
        )


def main():
    """Inicia a aplicação do Bot do Telegram."""
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    # Handlers
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, processar_mensagem_de_voz))

    logger.info("🚀 Bot do Dreamlistener iniciado e escutando mensagens...")
    app.run_polling()


if __name__ == "__main__":
    main()