import os
import re
import json
from datetime import datetime
from dotenv import load_dotenv
from groq import Groq

# Carrega chaves de API do arquivo .env na raiz
load_dotenv()

# Configurações do Projeto
# Observação: Se moveu os arquivos na reestruturação, os áudios estão em "data/raw_audios"
DIRETORIO_AUDIOS = os.path.join("data", "raw_audios") if os.path.exists(os.path.join("data", "raw_audios")) else "audios"
MODELO_WHISPER = "whisper-large-v3"
ARQUIVO_JSON_BRUTO = os.path.join("data", "json_caches", f"sonhos_brutos_{MODELO_WHISPER}.json")
EXTENSOES_SUPORTADAS = (".ogg", ".opus", ".mp3", ".m4a", ".wav")

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    raise ValueError("❌ 'GROQ_API_KEY' não encontrada no arquivo .env!")

# Instancia o cliente da Groq
groq_client = Groq(api_key=GROQ_API_KEY)


def carregar_dados_brutos() -> list:
    if os.path.exists(ARQUIVO_JSON_BRUTO):
        with open(ARQUIVO_JSON_BRUTO, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def salvar_dados_brutos(dados: list) -> None:
    # Garante que a pasta do JSON exista
    os.makedirs(os.path.dirname(ARQUIVO_JSON_BRUTO), exist_ok=True)
    with open(ARQUIVO_JSON_BRUTO, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)


def extrair_data_do_nome(caminho_arquivo: str) -> str:
    nome_arquivo = os.path.basename(caminho_arquivo)
    padrao_whatsapp = r"(\d{4}-\d{2}-\d{2})\s+at\s+(\d{2}\.\d{2}\.\d{2})"
    match = re.search(padrao_whatsapp, nome_arquivo)

    if match:
        data_str, hora_str = match.groups()
        data_obj = datetime.strptime(f"{data_str} {hora_str}", "%Y-%m-%d %H.%M.%S")
        return data_obj.strftime("%d/%m/%Y às %H:%M:%S")

    timestamp_arquivo = os.path.getmtime(caminho_arquivo)
    return datetime.fromtimestamp(timestamp_arquivo).strftime("%d/%m/%Y às %H:%M:%S")


def transcrever_audio_groq(caminho_audio: str) -> str:
    """Envia o arquivo para a API da Groq para transcrição ASR via Whisper Large-V3."""
    with open(caminho_audio, "rb") as file:
        transcription = groq_client.audio.transcriptions.create(
            file=(os.path.basename(caminho_audio), file.read()),
            model=MODELO_WHISPER,
            language="pt",
            response_format="text",
            temperature=0.0
        )
    return transcription.strip()


def transcrever_audios():
    if not os.path.exists(DIRETORIO_AUDIOS):
        os.makedirs(DIRETORIO_AUDIOS)
        print(f"📁 Pasta '{DIRETORIO_AUDIOS}' criada.")
        return

    dados_existentes = carregar_dados_brutos()
    arquivos_ja_transcritos = {item["arquivo"] for item in dados_existentes}

    todos_arquivos = sorted(os.listdir(DIRETORIO_AUDIOS))
    novos_audios = [
        f for f in todos_arquivos 
        if f.lower().endswith(EXTENSOES_SUPORTADAS) and f not in arquivos_ja_transcritos
    ]

    if not novos_audios:
        print(f"✨ Nenhum áudio novo para transcrever em '{ARQUIVO_JSON_BRUTO}'.")
        return

    print(f"⚡ Transcrevendo {len(novos_audios)} novo(s) áudio(s) via Groq API ('{MODELO_WHISPER}')...")

    for i, nome_arquivo in enumerate(novos_audios, 1):
        caminho_completo = os.path.join(DIRETORIO_AUDIOS, nome_arquivo)
        print(f"\n--- [{i}/{len(novos_audios)}] Transcrevendo: {nome_arquivo} ---")

        try:
            data_sonho = extrair_data_do_nome(caminho_completo)
            
            # Chamada à API da Groq
            texto_bruto = transcrever_audio_groq(caminho_completo)

            if texto_bruto:
                dados_existentes.append({
                    "arquivo": nome_arquivo,
                    "modelo": MODELO_WHISPER,
                    "data": data_sonho,
                    "texto_bruto": texto_bruto,
                    "status_refinado": False
                })
                salvar_dados_brutos(dados_existentes)
                print(f"✅ Transcrição salva em '{ARQUIVO_JSON_BRUTO}'")
            else:
                print("⚠️ Sem fala detectada.")

        except Exception as e:
            print(f"❌ Erro ao processar '{nome_arquivo}': {e}")


if __name__ == "__main__":
    transcrever_audios()