# Dreamlistener

Um diário de sonhos por áudio, construído como projeto de estudo de automação,
agentes e sistemas confiáveis.

O Dreamlistener recebe uma mensagem de voz no Telegram, transcreve o relato,
preserva sua redação ao formatá-lo e o registra em um diário no Google Docs.
Ao mesmo tempo, guarda um registro estruturado local em SQLite para permitir
busca, retomada após falhas e evolução futura para RAG com fontes rastreáveis.

> O projeto oferece registro e reflexão pessoal. Ele não faz diagnóstico,
> aconselhamento clínico nem afirmações psicológicas sobre quem relata o sonho.

## O problema

Relatos de sonhos são fáceis de perder: normalmente são gravados rapidamente,
ficam espalhados em mensagens ou exigem transcrição e organização manuais. Um
Google Docs é agradável para leitura, mas não é uma fonte de dados robusta para
buscar, deduplicar ou recuperar um processamento interrompido.

Por isso, o projeto separa duas responsabilidades:

- **SQLite** é a fonte de verdade operacional: identidade, estado, data,
  transcrição, texto refinado, tags e URL de publicação.
- **Google Docs** é a projeção legível do diário: organizado por data e com um
  índice reconstruído a partir do banco.

## Como funciona hoje

```text
Telegram (áudio)
  → arquivo temporário
  → Groq / Whisper (transcrição)
  → confirmação de data, quando necessária
  → Gemini (pontuação e formatação fiel)
  → SQLite (estado e histórico)
  → Google Docs (diário de leitura)
```

O fluxo é majoritariamente determinístico. O Gemini é usado somente para
formatação do texto, não para interpretar o sonho.

### Recursos atuais

- Transcrição de áudio e mensagem de voz em português.
- Refinamento com fallback de modelos Gemini, preservando vocabulário e fatos
  narrados.
- Registro idempotente por conversa e ID da mensagem do Telegram.
- Máquina de estados: `received → transcribed → refined → published`.
- Confirmação humana quando uma data narrada diverge da data de recebimento.
- Descarte do áudio temporário após cada processamento.
- Recuperação de publicação interrompida por reautorização do Google, sem
  reenviar áudio ou texto ao Gemini.
- Busca no histórico publicado por palavra, período e tags factuais.
- Allowlist explícita de chats autorizados.

## Uso pelo Telegram

Depois de iniciar o bot, envie uma mensagem de voz para registrar um sonho.
Os comandos podem ser vistos ao digitar `/` no chat ou por `/ajuda`.

```text
/buscar rio
/buscar tag:casa
/buscar de:2026-09-01 ate:2026-09-30 tag:agua
/retomar_publicacoes
```

`/buscar` recupera somente sonhos publicados e não usa LLM, embeddings ou RAG.
As tags atuais descrevem elementos explícitos, como `casa`, `agua`, `familia`
e `trabalho`; elas não são interpretações simbólicas.

## Instalação e execução

### 1. Criar o ambiente Python

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

No Windows, ative o ambiente com `.venv\Scripts\activate`.

### 2. Configurar segredos e acesso

Crie um arquivo `.env` na raiz do projeto. Nunca versione esse arquivo.

```dotenv
TELEGRAM_BOT_TOKEN=...
GROQ_API_KEY=...
GEMINI_API_KEY=...
ALLOWED_TELEGRAM_CHAT_IDS=123456789
```

Para publicar no Google Docs, coloque `credentials.json` na raiz. Na primeira
execução, o OAuth abre o navegador e gera `token.json`; ambos contêm dados de
acesso e permanecem fora do Git.

### 3. Executar

```bash
python -m app.bot
```

Se a autorização Google expirar, execute localmente:

```bash
python -c "from app.export_docs import reautorizar_google; reautorizar_google(); print('Autorização concluída.')"
```

Depois reinicie o bot e envie `/retomar_publicacoes` no Telegram.

## Testes

```bash
python -m unittest discover -s tests -v
```

Os testes cobrem regras de persistência, transições de estado, data, tags,
busca, controles de acesso, projeção no Docs e atalhos de ajuda. Eles não fazem
chamadas às APIs externas.

## Privacidade e limites atuais

- O áudio baixado pelo bot é temporário e apagado ao final do processamento.
- Transcrições e textos refinados ficam no SQLite local e no Google Docs
  configurado pela pessoa usuária.
- O bot recusa chats que não estejam em `ALLOWED_TELEGRAM_CHAT_IDS`.
- Não inclua relatos, tokens, `credentials.json`, `token.json` ou bancos locais
  em commits, issues ou fixtures de teste.

## Próximas etapas

O roteiro vivo está em [docs/BACKLOG.md](docs/BACKLOG.md). Os próximos itens
planejados incluem:

1. importação assistida de relatos já existentes no Google Docs;
2. catálogo de fontes abertas e licenciadas para RAG;
3. avaliação da recuperação antes de gerar qualquer reflexão simbólica;
4. rascunhos com citações, hipóteses probabilísticas e aprovação humana antes
   de salvar ou enviar.

## Documentação relacionada

- [Documentação técnica e funcional](docs/DOCUMENTACAO_TECNICA_FUNCIONAL.md)
- [Backlog e trilha de estudo](docs/BACKLOG.md)
- [Histórico de evolução](docs/HISTORY_LOG.md)
- [Avaliação de modelos](docs/EVALUATION.md)

## Licença

Este projeto é distribuído sob a [Apache License 2.0](LICENSE).
