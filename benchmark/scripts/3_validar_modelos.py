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
    Quando o processo termina, o SO libera toda a RAM alocada.
    """
    print(f"\n🚀 [Processo Isolado] Iniciando modelo: {modelo_nome}...")
    
    lista_ground_truths = []
    lista_transcricoes = []
    tempo_total = 0.0

    try:
        # cpu_threads=2 e num_workers=1 mantêm o uso de RAM no limite mínimo absoluto
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
                beam_size=1,        # reduz uso de memória durante a busca
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

    # Lê o que já foi salvo anteriormente
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

        # Cria uma fila IPC para recuperar o resultado do processo filho
        fila = multiprocessing.Queue()
        
        # Cria e inicia o processo filho estritamente ISOLADO
        p = multiprocessing.Process(
            target=avaliar_unico_modelo, 
            args=(modelo, casos_de_teste, fila)
        )
        p.start()
        p.join()  # Aguarda o término do modelo atual antes de pensar em ir pro próximo

        # Coleta o resultado e salva imediatamente
        if not fila.empty():
            res = fila.get()
            resultados.append(res)
            atualizar_relatorios(resultados)
            print(f"💾 Checkpoint salvo para {modelo}!")

        # Coleta de lixo no processo pai
        gc.collect()

    print("\n=== FINALIZADO COM SUCESSO ===")


if __name__ == "__main__":
    main()