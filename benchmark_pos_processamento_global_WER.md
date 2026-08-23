# Comparativo Global do Pós-Processamento (Whisper + Gemini)

**Modelo Refinador:** `gemini-3.6-flash`  
**Data da Execução:** 23/08/2026 19:53:48

## 1. Resumo Comparativo Agregado

| Modelo Whisper   |   WER Bruto (%) |   WER Pós-LLM (%) |   Ganho WER (%) |   CER Bruto (%) |   CER Pós-LLM (%) |   Acurácia Final (%) |
|:-----------------|----------------:|------------------:|----------------:|----------------:|------------------:|---------------------:|
| medium           |           50.22 |             46.02 |            4.2  |           21.64 |             21.53 |                53.98 |
| large-v3-turbo   |           46.57 |             41.81 |            4.76 |           23.94 |             18.46 |                58.19 |
| large-v3         |           10.95 |             34.62 |          -23.67 |            8.04 |             15.8  |                65.38 |

---

## 2. Detalhamento por Item de Teste

| Modelo         | Arquivo                                 |   WER Bruto (%) |   WER Refinado (%) |   Ganho WER (%) |
|:---------------|:----------------------------------------|----------------:|-------------------:|----------------:|
| medium         | WhatsApp Ptt 2026-08-08 at 09.35.37.ogg |           45.04 |              39.95 |            5.09 |
| medium         | WhatsApp Ptt 2026-08-10 at 08.13.18.ogg |           54.21 |              50.68 |            3.53 |
| large-v3-turbo | WhatsApp Ptt 2026-08-08 at 09.35.37.ogg |           58.52 |              34.35 |           24.17 |
| large-v3-turbo | WhatsApp Ptt 2026-08-10 at 08.13.18.ogg |           37.38 |              47.55 |          -10.17 |
| large-v3       | WhatsApp Ptt 2026-08-08 at 09.35.37.ogg |            1.53 |              21.12 |          -19.59 |
| large-v3       | WhatsApp Ptt 2026-08-10 at 08.13.18.ogg |           18.2  |              45.01 |          -26.81 |
