# Relatório de Avaliação do Pós-Processamento (LLM)

**Modelo ASR Base:** `large-v3-turbo`  
**Modelo Refinador:** `gemini-3.6-flash`  
**Última Atualização:** 21/08/2026 11:42:56  
**Amostras Únicas Processadas:** 2 áudio(s)  

## 1. Resumo Comparativo Agregado

| Etapa                                   |   WER Global (%) |   CER Global (%) |   Acurácia Global (%) |
|:----------------------------------------|-----------------:|-----------------:|----------------------:|
| 1. Transcrição Bruta (large-v3-turbo)   |            46.57 |            23.94 |                 53.43 |
| 2. Pós-Processamento (Gemini 3.6 Flash) |            41.04 |            18.01 |                 58.96 |

---

## 2. Detalhamento por Item de Teste

| Arquivo                                 |   WER Bruto (%) |   WER Refinado (%) |   Ganho WER (%) |
|:----------------------------------------|----------------:|-------------------:|----------------:|
| WhatsApp Ptt 2026-08-08 at 09.35.37.ogg |           58.52 |              30.28 |           28.24 |
| WhatsApp Ptt 2026-08-10 at 08.13.18.ogg |           37.38 |              49.32 |          -11.94 |
