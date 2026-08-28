import os
import re
import json
from datetime import datetime
from faster_whisper import WhisperModel

# Configurações do Projeto
DIRETORIO_AUDIOS = "audios"
MODELO_WHISPER = "large-v3"  # Altere aqui para "small", "large-v3", etc.
ARQUIVO_JSON_BRUTO = f"sonhos_brutos_{MODELO_WHISPER}.json"
EXTENSOES_SUPORTADAS = (".ogg", ".opus", ".mp3", ".m4a", ".wav")


def carregar_dados_brutos() -> list:
    if os.path.exists(ARQUIVO_JSON_BRUTO):
        with open(ARQUIVO_JSON_BRUTO, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def salvar_dados_brutos(dados: list) -> None:
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

    print(f"🔎 Transcrevendo {len(novos_audios)} novo(s) áudio(s) usando o modelo '{MODELO_WHISPER}'...")
    
    # Instancia o modelo dinamicamente usando a variável
    model = WhisperModel(MODELO_WHISPER, device="cpu", compute_type="int8")

    for i, nome_arquivo in enumerate(novos_audios, 1):
        caminho_completo = os.path.join(DIRETORIO_AUDIOS, nome_arquivo)
        print(f"\n--- [{i}/{len(novos_audios)}] Transcrevendo: {nome_arquivo} ---")

        try:
            data_sonho = extrair_data_do_nome(caminho_completo)
            segments, _ = model.transcribe(
                caminho_completo, 
                language="pt", 
                beam_size=5, 
                vad_filter=True, 
                temperature=0.0
            )
            texto_bruto = " ".join([seg.text.strip() for seg in list(segments)])

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