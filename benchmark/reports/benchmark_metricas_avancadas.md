# Relatório de Impacto do Pós-Processamento (Pré-LLM vs. Pós-LLM)

**Modelo Refinador:** `gemini-3.6-flash`  
**Modelo BERT Base:** `bert-base-multilingual-cased`  
**Data da Execução:** 24/08/2026 15:45:44  

---

## 1. Comparativo Agregado por Modelo (Evolução Antes/Depois)

| Modelo Whisper   |   WER Bruto (Pré-LLM) % |   WER Norm (Pós-LLM) % |   Ganho WER % |   BERTScore (Pré-LLM) % |   BERTScore (Pós-LLM) % |   Ganho BERTScore % |
|:-----------------|------------------------:|-----------------------:|--------------:|------------------------:|------------------------:|--------------------:|
| medium           |                   50.22 |                  21.81 |         28.41 |                   85.07 |                   85.07 |                   0 |
| large-v3-turbo   |                   46.57 |                  26.87 |         19.7  |                   85.51 |                   85.51 |                   0 |
| large-v3         |                   10.95 |                   9.03 |          1.92 |                   94.51 |                   94.51 |                   0 |

* **WER Bruto (Pré-LLM):** Taxa de erro de palavras da transcrição acústica pura do Whisper (inclui penalizações por falta de pontuação).
* **WER Norm (Pós-LLM):** Taxa de erro das palavras após o refinamento e limpeza da LLM (sem ruidos de pontuação).
* **BERTScore (Pré vs. Pós):** Mede o ganho ou preservação de significado semântico do texto após o pós-processamento (0 a 100%).

---

## 2. Detalhamento por Item de Teste

| Modelo         | Identificador                    |   WER Bruto (Pré-LLM) % |   WER Norm (Pós-LLM) % |   Ganho WER % |   BERTScore (Pré-LLM) % |   BERTScore (Pós-LLM) % |   Ganho BERTScore % |
|:---------------|:---------------------------------|------------------------:|-----------------------:|--------------:|------------------------:|------------------------:|--------------------:|
| medium         | Áudio 1 (Sonho 1 (Natura))       |                   45.04 |                  19.85 |         25.19 |                   85.43 |                   85.43 |                   0 |
| medium         | Áudio 2 (Sonho 2 (Casa Redonda)) |                   54.21 |                  23.3  |         30.91 |                   84.71 |                   84.71 |                   0 |
| large-v3-turbo | Áudio 1 (Sonho 1 (Natura))       |                   58.52 |                  32.82 |         25.7  |                   91.47 |                   91.47 |                   0 |
| large-v3-turbo | Áudio 2 (Sonho 2 (Casa Redonda)) |                   37.38 |                  22.33 |         15.05 |                   79.54 |                   79.54 |                   0 |
| large-v3       | Áudio 1 (Sonho 1 (Natura))       |                    1.53 |                   1.53 |          0    |                   99.76 |                   99.76 |                   0 |
| large-v3       | Áudio 2 (Sonho 2 (Casa Redonda)) |                   18.2  |                  14.76 |          3.44 |                   89.25 |                   89.25 |                   0 |
