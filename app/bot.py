import os
import logging
import tempfile
import time
from datetime import date
from dotenv import load_dotenv
from telegram import BotCommand, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ApplicationBuilder, CallbackQueryHandler, ContextTypes, MessageHandler, CommandHandler, filters
from groq import Groq
from google import genai
from google.genai.errors import APIError

from app import export_docs
from app.access_control import is_allowed_chat, parse_allowed_chat_ids
from app.bot_help import COMMANDS, render_help
from app.dream_dates import extract_narrated_dream_date, received_date_in_application_timezone
from app.dream_search import parse_search_criteria
from app.dream_store import GOOGLE_PUBLICATION_FAILURE, Dream, DreamStore
from app.dream_tags import extract_factual_tags

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
DATABASE_PATH = os.getenv("DREAMLISTENER_DB_PATH", "data/dreamlistener.db")
ALLOWED_TELEGRAM_CHAT_IDS = parse_allowed_chat_ids(os.getenv("ALLOWED_TELEGRAM_CHAT_IDS"))

if not TELEGRAM_BOT_TOKEN or not GROQ_API_KEY or not GEMINI_API_KEY:
    raise ValueError("❌ Verifique se TELEGRAM_BOT_TOKEN, GROQ_API_KEY e GEMINI_API_KEY estão no .env!")

# Clientes das APIs
groq_client = Groq(api_key=GROQ_API_KEY)
gemini_client = genai.Client(api_key=GEMINI_API_KEY)
dream_store = DreamStore(DATABASE_PATH)

# Lista priorizada de modelos (da maior qualidade para maior disponibilidade no Free Tier)
MODELOS_GEMINI_FALLBACK = [
    "gemini-3.6-flash",       # Primário: Maior precisão gramatical/narrativa
    "gemini-3.1-flash-lite",  # Secundário: Ultra-rápido, cota separada
    "gemini-1.5-flash"        # Terciário: Fallback estável de alta disponibilidade
]


async def chat_autorizado(update: Update) -> bool:
    chat_id = update.effective_chat.id if update.effective_chat else None
    if is_allowed_chat(chat_id, ALLOWED_TELEGRAM_CHAT_IDS):
        return True

    logger.warning("Tentativa de acesso não autorizado pelo chat %s", chat_id)
    if update.callback_query:
        await update.callback_query.answer("Acesso não autorizado.", show_alert=True)
    elif update.message:
        await update.message.reply_text("⛔ Este bot não está disponível neste chat.")
    return False


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
    if not await chat_autorizado(update):
        return
    mensagem = "🌙 Bem-vinda ao Dreamlistener!\n\nEnvie um áudio para registrar um sonho.\n\n" + render_help()
    await update.message.reply_text(mensagem)


async def ajuda_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Apresenta os atalhos disponíveis no bot."""
    if not await chat_autorizado(update):
        return
    await update.message.reply_text(render_help())


async def configurar_menu_de_comandos(application) -> None:
    """Registra atalhos no menu nativo do Telegram, sem afetar o processamento."""
    try:
        await application.bot.set_my_commands([
            BotCommand(item.command, item.description) for item in COMMANDS
        ])
    except Exception:
        logger.exception("Não foi possível atualizar o menu de comandos do Telegram")


async def publicar_sonho_refinado(dream: Dream, mensagem_status) -> str:
    """Publica um texto já refinado; OAuth inválido fica pronto para retomada."""
    try:
        await mensagem_status.edit_text("📄 Registrando no seu Diário de Sonhos no Google Docs...")
        doc_url = export_docs.publicar_sonho_no_docs(
            texto_refinado=dream.refined_transcript,
            nome_identificador=f"Voz_{dream.source_message_id}",
            data_sonho=date.fromisoformat(dream.dream_date),
            id_sonho=dream.id,
        )
        dream = dream_store.advance(dream.id, status="published", document_url=doc_url)
        logger.info("Sonho %s publicado com sucesso", dream.id)
        try:
            export_docs.atualizar_indice_no_docs(dream_store.list_published())
        except Exception:
            logger.exception("Índice do Docs não pôde ser atualizado para o sonho %s", dream.id)

        resposta_final = (
            "✨ **Sonho registrado com sucesso!**\n\n"
            f"📝 **Relato:**\n_{dream.refined_transcript}_\n\n"
            f"🔗 [Clique aqui para abrir no Google Docs]({doc_url})"
        )
        await mensagem_status.edit_text(resposta_final, parse_mode="Markdown", disable_web_page_preview=True)
        return "published"
    except export_docs.GoogleReauthorizationRequired:
        logger.warning("Reautorização Google necessária para o sonho %s", dream.id)
        await mensagem_status.edit_text(
            "🔐 A conexão com o Google Docs precisa de novo consentimento.\n\n"
            "No computador onde o bot está rodando, pare-o e execute:\n"
            "`python -c \"from app.export_docs import reautorizar_google; reautorizar_google(); print('Autorização concluída.')\"`\n\n"
            "Conclua a autorização no navegador, inicie o bot novamente e envie "
            "/retomar_publicacoes. Seu relato foi preservado e não será reenviado ao Gemini."
        )
        return "reauthorization_required"
    except Exception as error:
        logger.error("Erro ao publicar o sonho %s: %s", dream.id, error, exc_info=True)
        try:
            dream_store.mark_failed(dream.id, GOOGLE_PUBLICATION_FAILURE)
        except ValueError:
            logger.exception("Não foi possível registrar a falha do sonho %s", dream.id)
        await mensagem_status.edit_text(
            "❌ Ocorreu um erro ao processar seu relato. Por favor, tente enviar novamente em instantes."
        )
        return "failed"


async def refinar_e_publicar_sonho(dream: Dream, mensagem_status) -> None:
    """Refina uma transcrição persistida e então tenta publicá-la."""
    try:
        await mensagem_status.edit_text("✍️ Refinando e formatando o relato (Gemini)...")
        texto_refinado = refinar_texto_com_gemini(dream.raw_transcript)
        dream = dream_store.advance(dream.id, status="refined", refined_transcript=texto_refinado)
        dream_store.replace_factual_tags(dream.id, extract_factual_tags(texto_refinado))
    except Exception as error:
        logger.error("Erro ao refinar o sonho %s: %s", dream.id, error, exc_info=True)
        try:
            dream_store.mark_failed(dream.id, "Falha na etapa: refinamento")
        except ValueError:
            logger.exception("Não foi possível registrar a falha do sonho %s", dream.id)
        await mensagem_status.edit_text(
            "❌ Ocorreu um erro ao processar seu relato. Por favor, tente enviar novamente em instantes."
        )
        return

    await publicar_sonho_refinado(dream, mensagem_status)


async def retomar_publicacoes_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Retoma somente publicações já refinadas, após OAuth ser reautorizado."""
    if not await chat_autorizado(update):
        return

    pending = dream_store.list_pending_publications()
    if not pending:
        await update.message.reply_text("ℹ️ Não há publicações pendentes para retomar.")
        return

    mensagem_status = await update.message.reply_text(
        f"📄 Encontrei {len(pending)} publicação(ões) pendente(s). Retomando..."
    )
    published = 0
    for pending_dream in pending:
        dream = dream_store.prepare_publication_retry(pending_dream.id)
        result = await publicar_sonho_refinado(dream, mensagem_status)
        if result == "reauthorization_required":
            return
        if result == "published":
            published += 1

    if published > 1:
        await update.message.reply_text(f"✅ {published} publicações pendentes foram retomadas.")


def formatar_resultados_busca(dreams: list[Dream]) -> str:
    """Forma uma resposta curta, factual e limitada para o chat autorizado."""
    if not dreams:
        return "🔎 Nenhum sonho publicado corresponde à busca."

    lines = [f"🔎 {len(dreams)} resultado(s):"]
    for dream in dreams:
        data_sonho = date.fromisoformat(dream.dream_date).strftime("%d/%m/%Y") if dream.dream_date else "sem data"
        tags = ", ".join(dream_store.list_tags(dream.id)) or "sem tags"
        excerpt = " ".join((dream.refined_transcript or "").split())
        if len(excerpt) > 180:
            excerpt = f"{excerpt[:177].rstrip()}..."
        lines.extend([
            "",
            f"• {data_sonho} · tags: {tags}",
            excerpt or "(texto indisponível)",
            dream.document_url or "(link indisponível)",
        ])
    return "\n".join(lines)


async def buscar_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Consulta o histórico publicado do chat autorizado, sem usar LLM."""
    if not await chat_autorizado(update):
        return

    try:
        criteria = parse_search_criteria(context.args)
    except ValueError as error:
        await update.message.reply_text(
            f"⚠️ {error}\n\n"
            "Exemplos:\n"
            "/buscar rio\n"
            "/buscar tag:agua\n"
            "/buscar de:2026-09-01 ate:2026-09-30 tag:casa"
        )
        return

    dreams = dream_store.search_published(
        start_date=criteria.start_date,
        end_date=criteria.end_date,
        tag=criteria.tag,
        text=criteria.text,
    )[:5]
    await update.message.reply_text(formatar_resultados_busca(dreams), disable_web_page_preview=True)


async def confirmar_data_do_sonho(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Resolve a escolha de data e retoma o processamento no estado salvo."""
    if not await chat_autorizado(update):
        return
    query = update.callback_query
    await query.answer()
    _, action, dream_id = query.data.split(":", maxsplit=2)

    try:
        dream = dream_store.get_by_id(dream_id)
        if query.message.chat.id != dream.source_chat_id:
            logger.warning("Tentativa de confirmar data de outro chat para o sonho %s", dream_id)
            return

        updated_dream = dream_store.resolve_date_confirmation(
            dream_id, accept_candidate=action == "accept"
        )
        selected_date = date.fromisoformat(updated_dream.dream_date).strftime("%d/%m/%Y")
        await query.message.edit_text(f"🗓️ Data registrada: {selected_date}. Continuando o processamento...")
        await refinar_e_publicar_sonho(updated_dream, query.message)
    except (LookupError, ValueError):
        await query.message.edit_text(
            "ℹ️ Esta confirmação não está mais disponível; o sonho pode já ter sido processado."
        )


async def processar_mensagem_de_voz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handler principal do Telegram:
    1. Baixa o áudio enviado
    2. Transcreve via Groq (Whisper Large-V3)
    3. Refina via Gemini LLM (com Fallback)
    4. Publica na aba correta do Google Docs
    5. Responde ao usuário com o link do documento
    """
    if not await chat_autorizado(update):
        return

    mensagem_status = None
    temp_audio_path = None
    dream: Dream | None = None
    etapa = "recebimento"

    try:
        # Pega a mensagem de áudio ou voz
        audio_file = update.message.voice or update.message.audio
        if not audio_file:
            await update.message.reply_text("❌ Por favor, envie um arquivo de áudio ou mensagem de voz válido.")
            return

        # Registra a entrada antes de depender de serviços externos. A chave
        # única evita que uma atualização repetida gere um segundo sonho.
        dream, criado_agora = dream_store.create_or_get_received(
            source="telegram",
            source_chat_id=update.effective_chat.id,
            source_message_id=update.message.message_id,
            received_at=update.message.date,
            dream_date=received_date_in_application_timezone(update.message.date),
        )
        if not criado_agora:
            logger.info("Mensagem repetida para o sonho %s (status=%s)", dream.id, dream.status)
            if dream.status == "published" and dream.document_url:
                await update.message.reply_text(
                    "ℹ️ Este áudio já foi registrado anteriormente.\n"
                    f"🔗 {dream.document_url}",
                    disable_web_page_preview=True,
                )
            elif dream.status == "failed":
                await update.message.reply_text(
                    "⚠️ Este áudio já possui uma falha registrada e não será duplicado. "
                    "O reprocessamento será tratado em uma etapa futura."
                )
            else:
                await update.message.reply_text(
                    "ℹ️ Este áudio já está sendo processado ou aguarda retomada; não vou criar outro registro."
                )
            return

        logger.info("Iniciando processamento do sonho %s", dream.id)
        mensagem_status = await update.message.reply_text("🎧 Recebi seu áudio! Processando transcrição...")

        # 1. Download do áudio para um arquivo temporário no sistema
        etapa = "download do áudio"
        file_info = await context.bot.get_file(audio_file.file_id)
        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as temp_audio:
            temp_audio_path = temp_audio.name

        await file_info.download_to_drive(temp_audio_path)

        # 2. Transcrição ASR via Groq (Whisper)
        etapa = "transcrição"
        await mensagem_status.edit_text("⚡ Transcrevendo áudio em alta velocidade (Groq)...")
        texto_bruto = transcrever_audio_groq(temp_audio_path)

        if not texto_bruto:
            await mensagem_status.edit_text("⚠️ Não consegui identificar nenhuma fala no áudio enviado.")
            dream_store.mark_failed(dream.id, "Falha na etapa: transcrição sem fala detectada")
            return
        dream = dream_store.advance(dream.id, status="transcribed", raw_transcript=texto_bruto)

        candidate = extract_narrated_dream_date(texto_bruto, update.message.date)
        if candidate and candidate.value.isoformat() != dream.dream_date:
            dream_store.request_date_confirmation(
                dream.id,
                candidate_date=candidate.value,
                candidate_source=candidate.source,
                matched_text=candidate.matched_text,
            )
            candidate_text = candidate.value.strftime("%d/%m/%Y")
            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("Usar essa data", callback_data=f"date:accept:{dream.id}"),
                    InlineKeyboardButton("Manter data de recebimento", callback_data=f"date:reject:{dream.id}"),
                ]
            ])
            await mensagem_status.edit_text(
                f"🗓️ O relato menciona “{candidate.matched_text}”, que corresponde a {candidate_text}. "
                "Qual data devo registrar?",
                reply_markup=keyboard,
            )
            return

        await refinar_e_publicar_sonho(dream, mensagem_status)

    except Exception as e:
        logger.error(f"Erro ao processar mensagem de voz: {e}", exc_info=True)
        if dream is not None and dream.status != "published":
            try:
                dream_store.mark_failed(dream.id, f"Falha na etapa: {etapa}")
                logger.info("Falha registrada para o sonho %s na etapa %s", dream.id, etapa)
            except ValueError:
                logger.exception("Não foi possível registrar a falha do sonho %s", dream.id)
        mensagem_erro = "❌ Ocorreu um erro ao processar seu relato. Por favor, tente enviar novamente em instantes."
        if mensagem_status is not None:
            await mensagem_status.edit_text(mensagem_erro)
        else:
            await update.message.reply_text(mensagem_erro)
    finally:
        if temp_audio_path and os.path.exists(temp_audio_path):
            os.remove(temp_audio_path)


def main():
    """Inicia a aplicação do Bot do Telegram."""
    dream_store.initialize()
    if not ALLOWED_TELEGRAM_CHAT_IDS:
        logger.warning("Nenhum chat autorizado: o bot recusará todas as mensagens até a configuração da allowlist.")
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).post_init(configurar_menu_de_comandos).build()

    # Handlers
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("ajuda", ajuda_command))
    app.add_handler(CommandHandler("retomar_publicacoes", retomar_publicacoes_command))
    app.add_handler(CommandHandler("buscar", buscar_command))
    app.add_handler(CallbackQueryHandler(confirmar_data_do_sonho, pattern=r"^date:(accept|reject):"))
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, processar_mensagem_de_voz))

    logger.info("🚀 Bot do Dreamlistener iniciado e escutando mensagens...")
    app.run_polling()


if __name__ == "__main__":
    main()
