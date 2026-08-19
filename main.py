import os
import re
from datetime import datetime
from faster_whisper import WhisperModel

# Configurações do Projeto
DIRETORIO_AUDIOS = "audios"
ARQUIVO_SAIDA = "meus_sonhos.md"
ARQUIVO_HISTORICO = "processados.txt"
EXTENSOES_SUPORTADAS = (".ogg", ".opus", ".mp3", ".m4a", ".wav")


def carregar_historico() -> set:
    """Lê a lista de arquivos que já foram processados anteriormente."""
    if not os.path.exists(ARQUIVO_HISTORICO):
        return set()
    with open(ARQUIVO_HISTORICO, "r", encoding="utf-8") as f:
        return set(linha.strip() for linha in f if linha.strip())


def registrar_processado(nome_arquivo: str) -> None:
    """Anexa o nome do arquivo processado no histórico."""
    with open(ARQUIVO_HISTORICO, "a", encoding="utf-8") as f:
        f.write(f"{nome_arquivo}\n")


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


def processar_pasta_de_audios():
    if not os.path.exists(DIRETORIO_AUDIOS):
        os.makedirs(DIRETORIO_AUDIOS)
        print(f"📁 Pasta '{DIRETORIO_AUDIOS}' criada. Coloque seus arquivos de áudio nela.")
        return

    # Listar e ordenar arquivos para manter sequência cronológica
    todos_arquivos = sorted(os.listdir(DIRETORIO_AUDIOS))
    audios_para_processar = [
        f for f in todos_arquivos 
        if f.lower().endswith(EXTENSOES_SUPORTADAS)
    ]

    if not audios_para_processar:
        print(f"Nenhum arquivo de áudio encontrado em '{DIRETORIO_AUDIOS}'.")
        return

    historico = carregar_historico()
    novos_audios = [f for f in audios_para_processar if f not in historico]

    if not novos_audios:
        print("✨ Todos os áudios da pasta já foram processados anteriormente!")
        return

    print(f"🔎 Encontrados {len(novos_audios)} novos áudios para transcrição.\n")

    # Carrega o modelo apenas UMA vez para otimizar memória e tempo
    print("Carregando modelo Whisper...")
    model = WhisperModel("large-v3", device="cpu", compute_type="int8")

    for i, nome_arquivo in enumerate(novos_audios, 1):
        caminho_completo = os.path.join(DIRETORIO_AUDIOS, nome_arquivo)
        print(f"\n--- [{i}/{len(novos_audios)}] Processando: {nome_arquivo} ---")

        try:
            data_sonho = extrair_data_do_nome(caminho_completo)
            
            segments, info = model.transcribe(
                caminho_completo, 
                language="pt", 
                beam_size=5, 
                vad_filter=True,
                temperature=0.0
            )
            
            texto = " ".join([segment.text.strip() for segment in list(segments)])

            if texto:
                # Append no Markdown
                conteudo = f"\n## Sonho registrado em: {data_sonho}\n\n{texto}\n\n---\n"
                with open(ARQUIVO_SAIDA, "a", encoding="utf-8") as f:
                    f.write(conteudo)

                # Marca como processado
                registrar_processado(nome_arquivo)
                print(f"✅ Transcreveu e salvou: {data_sonho}")
            else:
                print("⚠️ Áudio sem fala detectada.")

        except Exception as e:
            print(f"❌ Erro ao processar '{nome_arquivo}': {e}")


if __name__ == "__main__":
    processar_pasta_de_audios()