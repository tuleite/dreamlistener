import os
import re
from datetime import datetime
from dotenv import load_dotenv
from faster_whisper import WhisperModel
from google import genai

# Carrega variáveis do arquivo .env (chave da API)
load_dotenv()

# Configurações do Projeto
DIRETORIO_AUDIOS = "audios"
ARQUIVO_SAIDA = "meus_sonhos_processado.md"
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


def refinar_texto_com_gemini(texto_bruto: str) -> str:
    """
    Envia o texto bruto transcrito pelo Whisper para a LLM refinar,
    pontuar e formatar o relato em parágrafos.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("Chave GEMINI_API_KEY não encontrada no arquivo .env!")

    client = genai.Client(api_key=api_key)

    prompt = f"""
    Você é um assistente especializado em organizar relatos de sonhos.
    
    Sua tarefa:
    1. Formatar o texto abaixo aplicando pontuação correta e divisão lógica em parágrafos.
    2. Remover vícios de linguagem, hesitações e repetições excessivas (ex: "tipo", "sei lá", "eu acho que", "né").
    # 3. Manter a narrativa estritamente em primeira pessoa.
    # 4. PRESERVAR 100% das informações originais, lugares, nomes de pessoas e detalhes (NÃO invente e NÃO omita fatos).

    Texto bruto transcrito do áudio:
    \"\"\"{texto_bruto}\"\"\"
    
    Retorne APENAS o texto formatado, sem introduções ou explicações.
    """

    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=prompt,
    )
    return response.text.strip()


def processar_pasta_de_audios():
    if not os.path.exists(DIRETORIO_AUDIOS):
        os.makedirs(DIRETORIO_AUDIOS)
        print(f"📁 Pasta '{DIRETORIO_AUDIOS}' criada. Coloque seus arquivos de áudio nela.")
        return

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

    # Usando 'medium' para evitar travamentos da CPU e delegando a lapidação do texto à LLM
    print("Carregando modelo Whisper 'medium'...")
    model = WhisperModel("medium", device="cpu", compute_type="int8")

    for i, nome_arquivo in enumerate(novos_audios, 1):
        caminho_completo = os.path.join(DIRETORIO_AUDIOS, nome_arquivo)
        print(f"\n--- [{i}/{len(novos_audios)}] Transcrevendo: {nome_arquivo} ---")

        try:
            data_sonho = extrair_data_do_nome(caminho_completo)
            
            # 1. Transcrição pelo Whisper
            segments, info = model.transcribe(
                caminho_completo, 
                language="pt", 
                beam_size=5, 
                vad_filter=True,
                temperature=0.0
            )
            
            texto_bruto = " ".join([segment.text.strip() for segment in list(segments)])

            if texto_bruto:
                print("✨ Refinando e formatando texto com o Gemini...")
                
                # 2. Pós-processamento com LLM
                texto_refinado = refinar_texto_com_gemini(texto_bruto)

                # 3. Escrita no Markdown
                conteudo = f"\n## Sonho registrado em: {data_sonho}\n\n{texto_refinado}\n\n---\n"
                with open(ARQUIVO_SAIDA, "a", encoding="utf-8") as f:
                    f.write(conteudo)

                # Marca como processado
                registrar_processado(nome_arquivo)
                print(f"✅ Processado, refinado e salvo: {data_sonho}")
            else:
                print("⚠️ Áudio sem fala detectada.")

        except Exception as e:
            print(f"❌ Erro ao processar '{nome_arquivo}': {e}")


if __name__ == "__main__":
    processar_pasta_de_audios()