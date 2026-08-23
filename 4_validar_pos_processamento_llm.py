import os
import json
import time
import pandas as pd
from dotenv import load_dotenv
from jiwer import wer, cer
from google import genai

load_dotenv()

ARQUIVO_GROUND_TRUTH = "ground_truth.json"
MODELOS_PARA_AVALIAR = ["medium", "large-v3-turbo", "large-v3"]
ARQUIVO_SAIDA_CSV = "benchmark_pos_processamento_global.csv"
ARQUIVO_SAIDA_MD = "benchmark_pos_processamento_global.md"


def carregar_json(caminho: str) -> list:
    """Carrega arquivos JSON permitindo caracteres de controle não escapados."""
    if os.path.exists(caminho):
        with open(caminho, "r", encoding="utf-8") as f:
            return json.loads(f.read(), strict=False)
    return []


def refinar_texto_com_gemini(texto_bruto: str) -> str:
    """Envia o texto bruto do Whisper para o Gemini aplicar pontuação e formatação."""
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


def avaliar_todos_os_modelos():
    casos_de_teste = carregar_json(ARQUIVO_GROUND_TRUTH)
    if not casos_de_teste:
        print("❌ Ground Truth não encontrado.")
        return

    resumo_global = []
    detalhes_por_item = []

    for modelo_nome in MODELOS_PARA_AVALIAR:
        caminho_cache = f"sonhos_brutos_{modelo_nome}.json"
        
        if not os.path.exists(caminho_cache):
            print(f"⚠️ Cache '{caminho_cache}' não encontrado. Pulando modelo {modelo_nome}...")
            continue

        print(f"\n⚡ Lendo cache '{caminho_cache}' para o modelo: {modelo_nome}...")

        transcricoes_brutas = carregar_json(caminho_cache)
        
        # Mapeamento unívoco para evitar duplicatas dentro do cache do Whisper
        mapa_whisper = {}
        for item in transcricoes_brutas:
            nome = os.path.basename(item["arquivo"])
            mapa_whisper[nome] = item["texto_bruto"]

        gt_lista = []
        bruto_lista = []
        refinado_lista = []
        arquivos_processados_no_loop = set()

        for item in casos_de_teste:
            nome_arquivo = os.path.basename(item["audio"])

            # Evita duplicação se o mesmo áudio constar repetido no Ground Truth
            if nome_arquivo in arquivos_processados_no_loop:
                print(f"⚠️ Áudio '{nome_arquivo}' duplicado na lista de testes. Pulando...")
                continue
            
            if nome_arquivo not in mapa_whisper:
                print(f"⚠️ Áudio '{nome_arquivo}' ausente no cache do modelo '{modelo_nome}'.")
                continue

            texto_bruto = mapa_whisper[nome_arquivo]
            ground_truth = item["ground_truth"]

            print(f"  ↪ Refinando via Gemini LLM: {nome_arquivo}...")
            try:
                texto_refinado = refinar_texto_com_gemini(texto_bruto)

                wer_b = round(wer(ground_truth, texto_bruto) * 100, 2)
                wer_r = round(wer(ground_truth, texto_refinado) * 100, 2)

                gt_lista.append(ground_truth)
                bruto_lista.append(texto_bruto)
                refinado_lista.append(texto_refinado)
                arquivos_processados_no_loop.add(nome_arquivo)

                # Registro individual do item
                detalhes_por_item.append({
                    "Modelo": modelo_nome,
                    "Arquivo": nome_arquivo,
                    "WER Bruto (%)": wer_b,
                    "WER Refinado (%)": wer_r,
                    "Ganho WER (%)": round(wer_b - wer_r, 2)
                })

                time.sleep(1)

            except Exception as e:
                print(f"❌ Erro ao refinar o áudio '{nome_arquivo}' com Gemini: {e}")

        # Métricas agregadas do modelo atual
        if gt_lista:
            wer_b_global = round(wer(gt_lista, bruto_lista) * 100, 2)
            wer_r_global = round(wer(gt_lista, refinado_lista) * 100, 2)
            cer_b_global = round(cer(gt_lista, bruto_lista) * 100, 2)
            cer_r_global = round(cer(gt_lista, refinado_lista) * 100, 2)

            resumo_global.append({
                "Modelo Whisper": modelo_nome,
                "WER Bruto (%)": wer_b_global,
                "WER Pós-LLM (%)": wer_r_global,
                "Ganho WER (%)": round(wer_b_global - wer_r_global, 2),
                "CER Bruto (%)": cer_b_global,
                "CER Pós-LLM (%)": cer_r_global,
                "Acurácia Final (%)": round(100 - wer_r_global, 2)
            })

    if resumo_global:
        df_resumo = pd.DataFrame(resumo_global)
        df_detalhes = pd.DataFrame(detalhes_por_item)

        # Exporta dados brutos
        df_detalhes.to_csv(ARQUIVO_SAIDA_CSV, index=False, encoding="utf-8-sig")

        # Exporta Markdown estruturado com ambas as tabelas
        conteudo_md = f"""# Comparativo Global do Pós-Processamento (Whisper + Gemini)

**Modelo Refinador:** `gemini-3.6-flash`  
**Data da Execução:** {time.strftime('%d/%m/%Y %H:%M:%S')}

## 1. Resumo Comparativo Agregado

{df_resumo.to_markdown(index=False)}

---

## 2. Detalhamento por Item de Teste

{df_detalhes.to_markdown(index=False)}
"""
        with open(ARQUIVO_SAIDA_MD, "w", encoding="utf-8") as f:
            f.write(conteudo_md)

        print("\n=== COMPARAÇÃO CONCLUÍDA ===")
        print(f"📄 Relatório Markdown salvo em: {ARQUIVO_SAIDA_MD}")
        print(f"📄 Dados em CSV salvos em: {ARQUIVO_SAIDA_CSV}")


if __name__ == "__main__":
    avaliar_todos_os_modelos()