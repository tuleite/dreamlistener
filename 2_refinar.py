import os
import json
from dotenv import load_dotenv
from google import genai

load_dotenv()

ARQUIVO_JSON_BRUTO = "sonhos_brutos_large-v3-turbo.json"
ARQUIVO_SAIDA = "meus_sonhos.md"


def carregar_dados_brutos() -> list:
    if os.path.exists(ARQUIVO_JSON_BRUTO):
        with open(ARQUIVO_JSON_BRUTO, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def salvar_dados_brutos(dados: list) -> None:
    with open(ARQUIVO_JSON_BRUTO, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)


def refinar_texto_com_gemini(texto_bruto: str) -> str:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("Chave GEMINI_API_KEY não encontrada no arquivo .env!")

    client = genai.Client(api_key=api_key)

    # AJUSTE O PROMPT AQUI QUANTAS VEZES QUISER
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


def refinar_sonhos(forcar_todos=False):
    dados = carregar_dados_brutos()
    if not dados:
        print(" Nenhuma transcrição encontrada em 'sonhos_brutos.json'. Rode o '1_transcrever.py' primeiro.")
        return

    pendentes = [item for item in dados if not item.get("status_refinado") or forcar_todos]

    if not pendentes:
        print("✨ Todos os sonhos do arquivo JSON já foram refinados!")
        return

    print(f"🔎 Refinando {len(pendentes)} sonho(s) com a LLM...")

    for item in pendentes:
        print(f"\n--- Processando relato de: {item['data']} ---")
        print(f"📝 Texto Bruto: {item['texto_bruto'][:80]}...")  # Exibe os primeiros 80 caracteres

        try:
            texto_refinado = refinar_texto_com_gemini(item["texto_bruto"])

            # Anexa ao Markdown
            conteudo = f"\n## Sonho registrado em: {item['data']}\n\n{texto_refinado}\n\n---\n"
            with open(ARQUIVO_SAIDA, "a", encoding="utf-8") as f:
                f.write(conteudo)

            # Atualiza a flag no JSON
            item["status_refinado"] = True
            salvar_dados_brutos(dados)
            print("✅ Refinado e salvo no Markdown!")

        except Exception as e:
            print(f"❌ Erro ao refinar com a LLM: {e}")


if __name__ == "__main__":
    # Se quiser reprocessar TUDO testando um prompt novo, mude para: refinar_sonhos(forcar_todos=True)
    refinar_sonhos(forcar_todos=False)