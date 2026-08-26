import os
import json
import time
from dotenv import load_dotenv
from google import genai
from importlib import import_module

# Importa o módulo do Google Docs
exportar_docs = import_module("6_exportar_google_docs")

load_dotenv()

ARQUIVO_JSON_BRUTO = "sonhos_brutos_large-v3-turbo.json"
ARQUIVO_BACKUP_MD = "meus_sonhos.md"


def carregar_dados_brutos() -> list:
    """Carrega o cache JSON das transcrições do Whisper."""
    if os.path.exists(ARQUIVO_JSON_BRUTO):
        with open(ARQUIVO_JSON_BRUTO, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def salvar_dados_brutos(dados: list) -> None:
    """Salva as atualizações das flags de status no cache JSON."""
    with open(ARQUIVO_JSON_BRUTO, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)


def refinar_texto_com_gemini(texto_bruto: str) -> str:
    """Envia a transcrição do Whisper para formatação e limpeza com o Gemini LLM."""
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
        model='gemini-3.6-flash',
        contents=prompt,
    )
    return response.text.strip()


def processar_e_publicar_sonhos(forcar_todos: bool = False):
    """
    Função principal: Lê as transcrições do Whisper, refina via Gemini, 
    gera backup local no .md e publica na aba do dia correto no Google Docs.
    """
    dados = carregar_dados_brutos()
    if not dados:
        print(f"❌ Nenhuma transcrição encontrada em '{ARQUIVO_JSON_BRUTO}'. Rode o '1_transcrever.py' primeiro.")
        return

    # Filtra apenas áudios que ainda não foram refinados
    pendentes = [item for item in dados if not item.get("status_refinado") or forcar_todos]

    if not pendentes:
        print("✨ Todos os sonhos do arquivo JSON já foram refinados e publicados!")
        return

    print(f"🚀 Iniciando refinamento e publicação de {len(pendentes)} áudio(s)...")

    for item in pendentes:
        nome_arquivo = os.path.basename(item.get("arquivo", "Audio"))
        texto_bruto = item.get("texto_bruto", "")
        data_relato = item.get("data", time.strftime("%d/%m/%Y"))

        print(f"\n⚡ Refinando com Gemini LLM: {nome_arquivo}...")

        try:
            # 1. Refinamento pela LLM
            texto_refinado = refinar_texto_com_gemini(texto_bruto)

            # 2. Backup local em Markdown (opcional)
            conteudo_md = f"\n## Sonho registrado em: {data_relato}\n\n{texto_refinado}\n\n---\n"
            with open(ARQUIVO_BACKUP_MD, "a", encoding="utf-8") as f:
                f.write(conteudo_md)

            # 3. Publicação no Google Docs (Aba por data)
            print(f"📄 Publicando '{nome_arquivo}' no Google Docs...")
            doc_url = exportar_docs.publicar_sonho_no_docs(
                texto_refinado=texto_refinado,
                nome_identificador=nome_arquivo
            )

            # 4. Atualiza flag de controle para evitar re-envio duplicado
            item["status_refinado"] = True
            salvar_dados_brutos(dados)

            print(f"✅ Sucesso! Visualizar no diário: {doc_url}")
            time.sleep(3)  # Pausa para respeitar limite de cota da API

        except Exception as e:
            print(f"❌ Erro ao processar o áudio '{nome_arquivo}': {e}")


if __name__ == "__main__":
    processar_e_publicar_sonhos()