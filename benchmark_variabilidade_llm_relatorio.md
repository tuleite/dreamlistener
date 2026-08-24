# Relatório de Variabilidade e Estabilidade da LLM (Gemini)

**Modelo Refinador:** `gemini-3.6-flash`  
**Repetições por Áudio:** 3  
**Data:** 23/08/2026 20:49:53  

## 1. Resumo da Flutuação por Modelo Whisper Base

| Modelo Whisper   |   WER Médio Global (%) |   Desvio Padrão WER (%) |   Menor WER Obtido (%) |   Maior WER Obtido (%) |
|:-----------------|-----------------------:|------------------------:|-----------------------:|-----------------------:|
| medium           |                  46.42 |                    0.55 |                  45.66 |                  46.91 |
| large-v3-turbo   |                  40.3  |                    0.92 |                  39.55 |                  41.6  |
| large-v3         |                  22.99 |                    7.36 |                  15.78 |                  33.09 |

---

## 2. Interpretação Técnica

* **Desvio Padrão Baixo ($\le 1.0\%$):** Indica alta estabilidade/determinismo do prompt.
* **Desvio Padrão Alto ($> 3.0\%$):** Indica sensibilidade da LLM a variações estocásticas de amostragem na geração das frases.
