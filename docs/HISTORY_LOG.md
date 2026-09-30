# LOG DE EVOLUÇÃO E APRENDIZADOS DO PROJETO (Dreamlistener)

**Projeto:** Dreamlistener
**Arquivo:** `HISTORY_LOG.md`
**Última Atualização:** Agosto de 2026

---

## 1. Contexto e Objetivos Iniciais

* **Objetivo do Projeto:** Automatizar a ingestão, transcrição acústica (ASR local) e refinamento gramatical/narrativo (LLM) de relatos informais em áudio (mensagens de voz de sonhos) em português do Brasil (PT-BR).
* **Premissa de Arquitetura Inicial:** Execução local do ASR para evitar custos recorrentes e garantia rigorosa de privacidade de dados sensíveis e relatos pessoais.

---

## 2. Linha do Tempo e Etapas Realizadas

### Etapa 8: Fundação de persistência estruturada (F1)

* **Ação:** Criação de `app/dream_store.py`, uma camada SQLite independente
  das APIs externas, e de testes de contrato em `tests/test_dream_store.py`.
* **Modelo:** cada relato recebe UUID, conserva a identidade da mensagem de
  origem (`source`, `chat_id`, `message_id`) e armazena separadamente texto
  bruto, texto refinado, URL de publicação, status e erro resumido.
* **Decisão de idempotência:** a chave única é
  `(source, source_chat_id, source_message_id)`, pois IDs de mensagens do
  Telegram não são globalmente únicos entre conversas.
* **Máquina de estados:** `received → transcribed → refined → published`, com
  saída controlada para `failed`. Transições que pulam uma etapa são rejeitadas.
* **Verificação:** testes cobrem criação idempotente, caminho de sucesso,
  transição inválida e falha registrada. A integração ao handler do Telegram
  permanece como próxima unidade da F1.
* **Integração subsequente:** o handler agora cria o registro antes das APIs,
  avança o status após transcrição, refinamento e publicação, e grava a etapa
  controlada da falha. O áudio temporário passou a ser removido em `finally`.
* **Decisão de retenção:** o Dreamlistener não arquivará áudio localmente. O
  arquivo temporário será descartado ao final do processamento; a retenção da
  mensagem original permanece submetida às configurações do Telegram.
* **Testes e observabilidade:** a suíte ganhou verificações de normalização de
  horário para UTC e de transcrição não vazia. Os logs do bot passaram a usar o
  UUID do sonho como identificador de correlação, sem incluir conteúdo do relato.
* **Decisão de data do sonho:** a data de recebimento será o valor padrão. Se
  uma referência narrada indicar outra data, o bot deverá solicitar confirmação
  antes de alterar o registro. A interface dessa confirmação será implementada
  como uma entrega separada para preservar estado e evitar inferências silenciosas.
* **Base para confirmação:** referências inequívocas (`hoje`, `ontem`,
  `anteontem` e `DD/MM/AAAA`) passaram a ser extraídas de forma determinística,
  sem LLM. O banco persiste a data padrão do diário em São Paulo e a origem
  `received_at`; a nova coluna é aplicada também a bancos já existentes por uma
  migração aditiva testada.
* **Confirmação humana de data:** uma candidata divergente fica registrada em
  `pending_date_confirmations`. O Telegram apresenta as opções de usar a data
  candidata ou manter a data de recebimento; somente após a decisão o fluxo
  retoma do texto bruto persistido e publica no Docs com a data registrada.
* **Projeção do Docs (F2):** cada publicação contém um marcador estável
  `dreamlistener:<UUID>`, evitando duplicação entre SQLite e Google Docs. A
  primeira aba tem um placeholder reservado que é substituído por um índice
  factual dos sonhos publicados; a fonte continua sendo o SQLite, não a leitura
  ou interpretação das abas do documento.
* **Tags factuais (F2.1):** foi criada uma taxonomia pequena de termos
  observáveis e normalizados, persistida na relação `dream_tags`. O sistema
  distingue explicitamente essa classificação de qualquer interpretação e só
  retorna sonhos publicados ao filtrar por tag.
* **Allowlist do diário pessoal (F3):** o acesso ao bot passou a exigir a
  variável `ALLOWED_TELEGRAM_CHAT_IDS`. A política é de bloqueio por padrão:
  comandos, áudios e confirmações são recusados fora dos chats configurados.
* **Retomada de consentimento Google (F1.4):** o erro de OAuth que ocorre na
  publicação deixou de encerrar o sonho como uma falha definitiva. O texto
  refinado permanece preservado, o bot instrui o novo consentimento no navegador
  local e `/retomar_publicacoes` continua somente as publicações pendentes. A
  retomada é limitada à falha conhecida de Google Docs; transcrição e refinamento
  não são repetidos sem uma decisão explícita.
* **Primeira interface de busca (F3):** o comando `/buscar` passou a traduzir
  filtros explícitos de texto, tag e período para a consulta parametrizada do
  SQLite. A resposta é limitada a cinco sonhos publicados, traz data, tags,
  trecho curto e link, e continua protegida pela allowlist do Telegram. Não há
  LLM, embeddings ou interpretação nesta etapa.
* **Descoberta de comandos (F3.2):** o bot passou a registrar atalhos no menu
  nativo do Telegram e a oferecer `/ajuda`, com exemplos de busca e a fronteira
  explícita de que busca não é interpretação.

### Etapa 1: Ingestão e Benchmark de Modelos ASR (`1_transcrever.py` / `3_validar_modelos.py`)

* **Ação:** Avaliação local dos modelos `medium`, `large-v3-turbo` e `large-v3` da biblioteca `faster-whisper`.
* **Problema Encontrado (Erro de RAM / VSCode Fechando):** Durante os testes sequenciais em CPU local, o consumo de memória RAM estourava (*Out Of Memory - OOM*), matando o processo do Python e fechando a IDE.
* **Pivô/Solução de Engenharia:**
  * Reconstrução do script de benchmark utilizando **`multiprocessing.Process`** para isolar a execução de cada modelo em um processo filho estrito.
  * Ao término da avaliação de um modelo, o Sistema Operacional destrói o processo filho e recupera 100% da RAM alocada.
  * Otimizações com `beam_size=1`, `cpu_threads=2` e `num_workers=1`.
* **Métricas Iniciais Obtidas:**
  * `medium`: WER 50.22% | Tempo médio/áudio: ~204s
  * `large-v3-turbo`: WER 32.30% | Tempo médio/áudio: ~198s
  * `large-v3`: WER 29.54% | Tempo médio/áudio: ~253s
* **Decisão Inicial:** Escolha do **`large-v3-turbo`** como modelo base oficial para execuções locais devido ao equilíbrio entre velocidade (~22% mais rápido que o `large-v3`) e taxa de acerto.

---

### Etapa 2: Documentação do Pipeline ASR (`EVALUATION.md`)

* **Ação:** Formalização da documentação técnica no arquivo `EVALUATION.md`.
* **Atualizações Adicionadas:**
  * Registro dos dados empíricos do benchmark ASR.
  * Detalhamento da arquitetura anti-OOM via `multiprocessing`.
  * Justificativa do *trade-off* para a escolha do `large-v3-turbo`.

---

### Etapa 3: Integração do Pós-Processamento com LLM (`2_refinar.py` / `4_validar_pos_processamento.py`)

* **Ação:** Desenvolvimento do pipeline de limpeza e formatação das transcrições brutas utilizando a API do Gemini (`gemini-3.6-flash`).
* **Pivô de Eficiência:** Reutilização dos caches locais (`sonhos_brutos_*.json`) para evitar re-transcrever os áudios no Whisper a cada teste da LLM.
* **Aprimoramentos de Segurança e Usabilidade:**
  * Inclusão de trava contra duplicação de áudios no loop de requisições.
  * Salvamento incremental em checkpoint (CSV/Markdown).
  * Criação de mapa de rótulos amigáveis (`Áudio 1 (Sonho 1 - Natura)`) vinculados ao `ground_truth.json` para evitar a exposição do nome real dos arquivos de áudio nos relatórios.

---

### Etapa 4: Teste de Variabilidade da LLM (`5_validar_variabilidade_llm.py`)

* **Ação:** Avaliação da estocasticidade do Gemini em 3 repetições consecutivas para cada modelo Whisper.
* **Insight:** Os modelos com áudio mais ruidoso (`medium` e `large-v3-turbo`) demonstraram um desvio padrão baixíssimo ($\sigma \le 0.92\%$), provando alta estabilidade e determinismo do prompt.

---

### Etapa 5: Exportação Automatizada para Google Docs com Abas Dinâmicas (`export_docs.py`)

* **Ação:** Integração do pipeline via Google Drive API e Google Docs API v1 para salvar os relatos refinados diretamente no documento oficial do diário.
* **Arquitetura de Navegação por Data:**
  * Implementação da criação/localização de **guias (tabs)** no Google Docs nomeadas pela data do relato (`DD/MM/YYYY`).
  * Múltiplos áudios no mesmo dia são anexados sequencialmente na mesma aba, separados por linhas divisórias.
* **Reserva Estática da 1ª Aba (`📌 Índice & Análises`):**
  * Proteção da primeira aba como um painel/dashboard fixo para o futuro *Agente Analítico de Tags & Temas*, impedindo que a gravação de relatos por data sobrescreva o sumário.

---

### Etapa 6: Bot do Telegram & Migração ASR para Groq Cloud (`app/bot.py`)

* **Ação:** Interfaceamento reativo por aplicativo de mensagens e resolução de gargalos de tempo/processamento.
* **Adoção do Bot do Telegram:** Substituição da rotina manual em lote por um bot do Telegram (`python-telegram-bot`) que escuta notas de voz e aciona o fluxo automaticamente.
* **Pivô de ASR (Whisper Local $\rightarrow$ Groq API):**
  * *Gargalo:* O tempo de processamento em CPU local era elevado (~1 a 3 minutos por áudio) e consumia recursos do computador.
  * *Solução:* Migração do Whisper local para a **API da Groq** rodando em chips LPU na nuvem.
  * *Resultado:* Utilização do modelo oficial **`whisper-large-v3`** com tempo de transcrição reduzido para **~0,5 segundos** por áudio.
  * *Viabilidade Financeira:* Custo de **R$ 0,00**, totalmente contido no limite diário gratuito (*Free Tier*) de até 2 horas de áudio por dia.
* **Fluxo Final E2E:**
  `Voz no Telegram` $\rightarrow$ `Groq Whisper Large-V3` $\rightarrow$ `Gemini LLM Refiner` $\rightarrow$ `Google Docs (Aba por Data)` $\rightarrow$ `Resposta com Link no Chat` (Tempo total: **2 a 4 segundos**).

---

### Etapa 7: Reorganização Profissional da Estrutura do Repositório

* **Ação:** Reestruturação das pastas do projeto para separar a aplicação em produção, a suíte de testes/benchmarks, os logs e os dados privados.

---

## 3. Principais Insights e Pivôs de Métricas

### Insight 1: A "Falácia do WER Tradicional" para Avaliar LLMs

* **O Problema:** Na avaliação do `large-v3` pós-LLM, o WER bruto "piorou" de **10.95% para 34.62%**.
* **A Descoberta:** O WER tradicional mede a distância de edição caractere por caractere. Quando a LLM adiciona vírgulas, pontos finais, quebras de parágrafo e remove vícios de linguagem ("né", "tipo assim"), a métrica contabiliza cada adição/remoção como um **erro**, penalizando o texto mesmo quando ele se tornou incomparavelmente mais legível.

### Insight 2: Redefinição do Mapeamento de Métricas

Percebemos que uma única métrica não respondia se o pós-processamento era bom. Dividimos a avaliação em duas frentes:

1. **WER Normalizado (Fidelidade Ortográfica):** Aplicação de uma limpeza profunda (remoção de pontuação, caixa baixa, acentos) antes do cálculo para medir estritamente a acurácia das palavras faladas.
2. **BERTScore F1 (Fidelidade Semântica):** Uso de *embeddings* contextuais para garantir que o significado do sonho não foi alterado pela LLM (mesmo que palavras tenham sido substituídas ou pontuadas).

### Insight 3: Estrutura Visual Pré vs. Pós-LLM

* **Mudança no Relatório:** Reformatação das tabelas de benchmark para exibir as notas pareadas lado a lado (**Pré-LLM vs. Pós-LLM**) com colunas explícitas de **Ganho %**, tornando visualmente óbvio o valor agregado pelo refinamento do Gemini.

---

## 4. Estrutura Atual do Repositório

```text
dreamlistener/
│
├── app/                        # 🤖 MÓDULO DE PRODUÇÃO (E2E)
│   ├── bot.py                  # Bot do Telegram e orquestrador principal
│   └── export_docs.py          # Integração Google Docs (guias dinâmicas + 1ª aba)
│
├── benchmark/                  # 📊 LABORATÓRIO DE MÉTRICAS & PESQUISA
│   ├── reports/                # Relatórios CSV e MD (WER, BERTScore, Estocasticidade)
│   └── scripts/                # Scripts de testes (ASR local, Gemini e Benchmarks 1 a 5)
│
├── data/                       # 📁 DADOS E CACHES
│   ├── json_caches/            # Caches em JSON das transcrições ASR brutas
│   ├── raw_audios/             # Banco de áudios locais de teste
│   └── ground_truth.json       # Transcrições manuais de referência
│
├── docs/                       # 📚 DOCUMENTAÇÃO TÉCNICA
│   ├── BACKLOG.md              # Planejamento das próximas sprints
│   ├── EVALUATION.md           # Formalização matemática e técnica dos testes
│   └── HISTORY_LOG.md          # Log histórico de evolução e arquitetura
│
├── .env                        # Chaves de API (Groq, Gemini, Telegram)
├── credentials.json            # Credenciais OAuth do Google
├── token.json                  # Token de autenticação persistente do Google
├── requirements.txt            # Dependências do ambiente Python
└── README.md                   # Apresentação do projeto
