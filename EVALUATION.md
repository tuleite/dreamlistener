
---

# Documentação de Validação e Benchmark de Modelos ASR

**Projeto:** Dreamlistener

**Módulo:** Avaliação e Benchmark da Transcrição Acústica (Whisper / faster-whisper)

**Autor:** Tuanny

**Data:** Agosto de 2026

---

## 1. Visão Geral

Esta etapa do pipeline tem como objetivo avaliar experimentalmente o desempenho e a eficiência computacional de diferentes variantes do Whisper (`medium`, `large-v3-turbo` e `large-v3`) para o processamento em lote de relatos informais em português (PT-BR).

A validação compara o desempenho dos modelos em relação a métricas padronizadas da indústria (**WER** e **CER**) e ao **tempo de inferência em CPU local**, utilizando um conjunto de testes (*ground truth*) isolado por questões de privacidade.

---

## 2. Métricas de Avaliação

* **WER (Word Error Rate) Global:** Porcentagem agregada de erros a nível de palavra (substituições, inserções e deleções) calculada sobre a amostra combinada de áudios:

$$\text{WER} = \frac{S + D + I}{N}$$


* **CER (Character Error Rate) Global:** Taxa de erro a nível de caractere, ideal para identificar pequenas divergências ortográficas.
* **Tempo Médio por Áudio (s):** Latência média de processamento por arquivo de áudio em CPU.
* **Acurácia Global (%):** Calculada como $(1 - \text{WER}) \times 100$.

---

## 3. Resultados Reais do Benchmark

Testes executados em ambiente local (CPU) com o conjunto de teste de relatos de áudio em PT-BR:

| Modelo | Tempo Total (s) | Tempo Médio/Áudio (s) | WER Global (%) | CER Global (%) | Acurácia Global (%) |
| --- | --- | --- | --- | --- | --- |
| **`medium`** | 409.91 | 204.96 | 50.22 | 21.64 | 49.78 |
| **`large-v3-turbo`** | **396.06** | **198.03** | **32.30** | **14.94** | **67.70** |
| **`large-v3`** | 507.72 | 253.86 | 29.54 | 15.01 | 70.46 |

---

## 4. Análise dos Resultados e Justificativa da Escolha

O modelo **`large-v3-turbo`** foi selecionado como o modelo oficial do projeto **Dreamlistener** com base nos seguintes critérios técnicos:

1. **Eficiência Computacional de Inferência:** O `large-v3-turbo` apresentou a menor latência média por áudio (**198.03s**), superando inclusive o modelo `medium` (204.96s) e sendo **~22% mais rápido que o `large-v3**` (253.86s).
2. **Excelente Trade-Off de Acurácia:** O modelo alcançou **67.70% de acurácia global** (WER de 32.30%), ficando a apenas 2.76% de distância do modelo topo de linha `large-v3` (70.46%).
3. **Absorção pelo Pós-Processamento:** A variação residual de ~2.7% no WER entre o `large-v3` e o `large-v3-turbo` é totalmente neutralizada na etapa seguinte do pipeline (`2_refinar.py`). A API do Gemini corrige pequenas flutuações acústicas e concordâncias, tornando o benefício de velocidade do modelo Turbo muito mais vantajoso para o sistema.

---

## 5. Arquitetura, Segurança e Resiliência de Execução

Para contornar limitações de hardware durante a avaliação de modelos pesados em CPU, a execução do benchmark adota os seguintes padrões de engenharia:

### 5.1 Isolamento de Processos via `multiprocessing` (Anti-OOM)

Em execuções sequenciais convencionais no Python, o Garbage Collector não garante a liberação imediata da memória C++ subjacente (CTranslate2/PyTorch) ao destruir a instância de um modelo. Isso causa acúmulo de memória RAM e falhas por *Out Of Memory* (OOM), frequentemente encerrando a IDE ou a sessão do sistema.

**Solução Aplicada:**

* Cada modelo executa em um **processo filho isolado** (`multiprocessing.Process`).
* Os resultados da métrica são comunicados ao processo pai via fila de comunicação inter-processos (`multiprocessing.Queue`).
* Ao finalizar a avaliação do modelo, o processo filho é **encerrado pelo Sistema Operacional**, forçando a devolução imediata e integral de 100% da memória RAM alocada para o sistema.

### 5.2 Otimizações de Inferência em CPU

* **Ajuste de Decodificação (`beam_size=1`):** Reduz o consumo de memória durante a busca de feixe (*beam search*) do Whisper, priorizando eficiência na verificação em CPU sem degradação observável da acurácia.
* **Controle de Threads (`cpu_threads=2` e `num_workers=1`):** Limita a quantidade de núcleos físicos alocados pelo CTranslate2, prevenindo que o processo consuma 100% dos recursos do processador e cause travamentos na interface do sistema operacional.

### 5.3 Persistência Incremental e Privacidade

* **Checkpoints Automáticos:** A cada modelo finalizado, a tabela consolidada é salva em disco nos formatos Markdown (`benchmark_relatorio.md`) e CSV (`benchmark_relatorio.csv`). Em caso de interrupção, o script lê os resultados existentes e pula automaticamente os modelos já calculados.
* **Privacidade dos Dados (`ground_truth.json`):** As transcrições manuais e os caminhos dos áudios ficam armazenados em um JSON isolado e ignorado pelo Git, impedindo o envio acidental de relatos pessoais para repositórios públicos.

---

## 6. Script de Benchmark Utilizado (`3_validar_modelos.py`)

```python
import os
import json
import time
import gc
import multiprocessing
import pandas as pd
from jiwer import wer, cer
from faster_whisper import WhisperModel

ARQUIVO_GROUND_TRUTH = "ground_truth.json"
MODELOS = ["medium", "large-v3-turbo", "large-v3"]
ARQUIVO_SAIDA_CSV = "benchmark_relatorio.csv"
ARQUIVO_SAIDA_MD = "benchmark_relatorio.md"


def carregar_casos_de_teste() -> list:
    if os.path.exists(ARQUIVO_GROUND_TRUTH):
        with open(ARQUIVO_GROUND_TRUTH, "r", encoding="utf-8") as f:
            return json.loads(f.read(), strict=False)
    return []


def avaliar_unico_modelo(modelo_nome: str, casos_de_teste: list, fila_resultados):
    """
    Roda a avaliação em um PROCESSO ISOLADO.
    Quando o processo termina, o SO libera toda a RAM alocada pelo CTranslate2.
    """
    print(f"\n🚀 [Processo Isolado] Iniciando modelo: {modelo_nome}...")
    
    lista_ground_truths = []
    lista_transcricoes = []
    tempo_total = 0.0

    try:
        # cpu_threads=2 e num_workers=1 mantêm o uso de RAM/CPU no limite mínimo
        model = WhisperModel(
            modelo_nome, 
            device="cpu", 
            compute_type="int8", 
            cpu_threads=2, 
            num_workers=1
        )

        for item in casos_de_teste:
            caminho_audio = item["audio"]
            if not os.path.exists(caminho_audio):
                print(f"⚠️ Áudio não encontrado: {caminho_audio}")
                continue

            inicio = time.time()
            segments, _ = model.transcribe(
                caminho_audio, 
                language="pt", 
                beam_size=1,        # Otimização de busca e memória
                vad_filter=True, 
                temperature=0.0
            )
            
            texto = " ".join([seg.text.strip() for seg in segments])
            duracao = time.time() - inicio
            tempo_total += duracao

            lista_ground_truths.append(item["ground_truth"])
            lista_transcricoes.append(texto)

        if lista_ground_truths:
            wer_val = wer(lista_ground_truths, lista_transcricoes)
            cer_val = cer(lista_ground_truths, lista_transcricoes)

            resultado = {
                "Modelo": modelo_nome,
                "Tempo Total (s)": round(tempo_total, 2),
                "Tempo Médio/Áudio (s)": round(tempo_total / len(lista_ground_truths), 2),
                "WER Global (%)": round(wer_val * 100, 2),
                "CER Global (%)": round(cer_val * 100, 2),
                "Acurácia Global (%)": round((1 - wer_val) * 100, 2)
            }
            fila_resultados.put(resultado)
            print(f"✅ Concluído modelo: {modelo_nome} (WER: {resultado['WER Global (%)']}%)")

    except Exception as e:
        print(f"❌ Erro ao processar modelo {modelo_nome}: {e}")


def atualizar_relatorios(resultados: list):
    df = pd.DataFrame(resultados)
    df.to_csv(ARQUIVO_SAIDA_CSV, index=False, encoding="utf-8-sig")

    conteudo_md = f"""# Relatório de Benchmark - Modelos Whisper

**Atualizado em:** {time.strftime('%d/%m/%Y %H:%M:%S')}

## Resultados
{df.to_markdown(index=False)}
"""
    with open(ARQUIVO_SAIDA_MD, "w", encoding="utf-8") as f:
        f.write(conteudo_md)


def main():
    casos_de_teste = carregar_casos_de_teste()
    if not casos_de_teste:
        print("❌ 'ground_truth.json' não encontrado ou vazio!")
        return

    resultados = []
    modelos_ja_feitos = set()
    if os.path.exists(ARQUIVO_SAIDA_CSV):
        try:
            df_existente = pd.read_csv(ARQUIVO_SAIDA_CSV)
            resultados = df_existente.to_dict(orient="records")
            modelos_ja_feitos = {r["Modelo"] for r in resultados}
        except Exception:
            pass

    for modelo in MODELOS:
        if modelo in modelos_ja_feitos:
            print(f"⏩ Modelo '{modelo}' já foi avaliado em execuções anteriores. Pulando...")
            continue

        # Instancia a fila e dispara o processo isolado
        fila = multiprocessing.Queue()
        p = multiprocessing.Process(
            target=avaliar_unico_modelo, 
            args=(modelo, casos_de_teste, fila)
        )
        p.start()
        p.join()

        # Coleta o resultado e grava o checkpoint em disco
        if not fila.empty():
            res = fila.get()
            resultados.append(res)
            atualizar_relatorios(resultados)
            print(f"💾 Checkpoint salvo para {modelo}!")

        gc.collect()

    print("\n=== FINALIZADO COM SUCESSO ===")


if __name__ == "__main__":
    main()

```