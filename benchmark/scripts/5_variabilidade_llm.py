import os
import json
import time
import pandas as pd
import numpy as np
from dotenv import load_dotenv
from jiwer import wer, cer
from google import genai

load_dotenv()

ARQUIVO_GROUND_TRUTH = "ground_truth.json"
MODELOS_WHISPER = ["medium", "large-v3-turbo", "large-v3"]
NUM_REPETICOES = 3  # Quantidade de execuções idênticas por áudio

ARQUIVO_SAIDA_CSV = "benchmark_variabilidade_llm_detalhado.csv"
ARQUIVO_SAIDA_MD = "benchmark_variabilidade_llm_relatorio.md"


def carregar_json(caminho: str) -> list:
    if os.path.exists(caminho):
        with open(caminho, "r", encoding="utf-8") as f:
            return json.loads(f.read(), strict=False)
    return []


def refinar_texto_com_gemini(texto_bruto: str) -> str:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("Chave GEMINI_API_KEY não encontrada no .env!")

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


def executar_teste_variabilidade():
    casos_de_teste = carregar_json(ARQUIVO_GROUND_TRUTH)
    if not casos_de_teste:
        print("❌ 'ground_truth.json' não encontrado.")
        return

    registros_execucao = []
    resumo_modelos = []

    for modelo_nome in MODELOS_WHISPER:
        caminho_cache = f"sonhos_brutos_{modelo_nome}.json"
        if not os.path.exists(caminho_cache):
            print(f"⚠️ Cache '{caminho_cache}' não encontrado. Pulando modelo {modelo_nome}...")
            continue

        print(f"\n🔬 Avaliando variabilidade da LLM sobre o modelo Whisper: {modelo_nome}")
        transcricoes_brutas = carregar_json(caminho_cache)
        mapa_whisper = {os.path.basename(i["arquivo"]): i["texto_bruto"] for i in transcricoes_brutas}

        wers_por_rodada = {rodada: [] for rodada in range(1, NUM_REPETICOES + 1)}
        gt_todas_rodadas = []

        for item in casos_de_teste:
            nome_arquivo = os.path.basename(item["audio"])
            if nome_arquivo not in mapa_whisper:
                continue

            texto_bruto = mapa_whisper[nome_arquivo]
            ground_truth = item["ground_truth"]

            respostas_audio = []

            for rodada in range(1, NUM_REPETICOES + 1):
                print(f"  ↪ [Modelo: {modelo_nome} | Áudio: {nome_arquivo} | Rodada {rodada}/{NUM_REPETICOES}] Chamando Gemini...")
                try:
                    texto_refinado = refinar_texto_com_gemini(texto_bruto)
                    wer_val = round(wer(ground_truth, texto_refinado) * 100, 2)
                    cer_val = round(cer(ground_truth, texto_refinado) * 100, 2)

                    respostas_audio.append(texto_refinado)
                    wers_por_rodada[rodada].append(wer_val)

                    registros_execucao.append({
                        "Modelo Whisper": modelo_nome,
                        "Arquivo": nome_arquivo,
                        "Rodada": rodada,
                        "WER vs GroundTruth (%)": wer_val,
                        "CER vs GroundTruth (%)": cer_val,
                        "Texto Refinado": texto_refinado
                    })

                    time.sleep(5)
                except Exception as e:
                    print(f"❌ Erro na rodada {rodada} para {nome_arquivo}: {e}")

        # Estatísticas do modelo
        wers_globais = [np.mean(wers_por_rodada[r]) for r in wers_por_rodada if wers_por_rodada[r]]
        if wers_globais:
            resumo_modelos.append({
                "Modelo Whisper": modelo_nome,
                "WER Médio Global (%)": round(float(np.mean(wers_globais)), 2),
                "Desvio Padrão WER (%)": round(float(np.std(wers_globais)), 2),
                "Menor WER Obtido (%)": round(float(np.min(wers_globais)), 2),
                "Maior WER Obtido (%)": round(float(np.max(wers_globais)), 2)
            })

    # Exportação dos Resultados
    if registros_execucao:
        df_detalhes = pd.DataFrame(registros_execucao)
        df_detalhes.to_csv(ARQUIVO_SAIDA_CSV, index=False, encoding="utf-8-sig")

        df_resumo = pd.DataFrame(resumo_modelos)
        
        conteudo_md = f"""# Relatório de Variabilidade e Estabilidade da LLM (Gemini)

**Modelo Refinador:** `gemini-3.6-flash`  
**Repetições por Áudio:** {NUM_REPETICOES}  
**Data:** {time.strftime('%d/%m/%Y %H:%M:%S')}  

## 1. Resumo da Flutuação por Modelo Whisper Base

{df_resumo.to_markdown(index=False)}

---

## 2. Interpretação Técnica

* **Desvio Padrão Baixo ($\le 1.0\%$):** Indica alta estabilidade/determinismo do prompt.
* **Desvio Padrão Alto ($> 3.0\%$):** Indica sensibilidade da LLM a variações estocásticas de amostragem na geração das frases.
"""

        with open(ARQUIVO_SAIDA_MD, "w", encoding="utf-8") as f:
            f.write(conteudo_md)

        print("\n=== EXPERIMENTO DE VARIABILIDADE CONCLUÍDO ===")
        print(f"📄 CSV detalhado: {ARQUIVO_SAIDA_CSV}")
        print(f"📄 Relatório Markdown: {ARQUIVO_SAIDA_MD}")


if __name__ == "__main__":
    executar_teste_variabilidade()