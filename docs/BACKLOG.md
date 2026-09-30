# Backlog e trilha de estudo — Dreamlistener

> **Como usar:** este é o plano vivo do projeto. A cada entrega, atualize o
> status, registre a decisão tomada e crie uma entrada breve em
> `docs/HISTORY_LOG.md`. Itens em `Proposto` não devem ser iniciados sem uma
> decisão explícita. A ordem abaixo privilegia fundamentos verificáveis antes
> de recursos agentic.

## Visão de produto

```text
Telegram/áudio → transcrição → revisão fiel → registro estruturado
                                      ├→ Google Docs (leitura humana)
                                      └→ busca → RAG com fontes licenciadas → rascunho aprovado
```

**Fonte de verdade:** banco estruturado local no início (SQLite). O Google
Docs permanece como diário navegável e publicação humana, não como banco de
dados operacional.

## Princípios e guardrails

- Um sonho é dado pessoal sensível: minimizar retenção, registrar o motivo de
  cada acesso e não enviar conteúdo a serviços além dos configurados.
- O refinamento preserva o relato; análises são artefatos separados, com
  versão, fontes e data.
- O sistema oferece reflexão simbólica, não diagnóstico, orientação clínica ou
  afirmações sobre a pessoa.
- Nenhuma análise é salva no Docs ou enviada pelo Telegram sem aprovação
  explícita enquanto o recurso estiver em experimentação.
- Todo trecho do RAG precisa de proveniência: obra/artigo, edição, página ou
  seção, licença e URL estável quando houver.

## Roteiro priorizado

| ID | Status | Entrega | Critério de conclusão | Conceitos para estudar |
| --- | --- | --- | --- | --- |
| F0 | Concluído | Pipeline Telegram → Groq → Gemini → Google Docs | Fluxo persiste o estado e recupera uma publicação interrompida por consentimento OAuth renovado | workflow determinístico, integração por API, recuperação de falha |
| F1 | Concluído | Registro estruturado em SQLite | Cada entrada tem UUID, `telegram_message_id`, timestamps, data do sonho, texto bruto/refinado, status, erro e URL do Docs; reprocessar a mesma mensagem não duplica o sonho | modelagem de dados, idempotência, máquina de estados |
| F1.1 | Concluído | Retenção e ciclo de vida de áudio | O Dreamlistener descarta sempre o arquivo temporário após o processamento; não mantém cópia local persistente de áudio. A mensagem original continua sob as configurações do Telegram | privacidade, minimização de dados, limpeza de recursos |
| F1.2 | Concluído | Testes e observabilidade mínimos | Testes cobrem data, idempotência, transições de status e falhas; logs usam UUID correlacionável sem expor relato integral | testes unitários, logs estruturados, testes de contrato |
| F1.3 | Concluído | Data do sonho com confirmação | Data de recebimento é o padrão; referências narradas simples divergentes pedem confirmação por botões e a decisão persistida define a publicação | extração estruturada, confiança, interação humano-no-loop |
| F1.4 | Concluído | Retomada após consentimento Google | Uma falha de renovação OAuth mantém o texto em `refined`; após consentimento local, `/retomar_publicacoes` tenta apenas as publicações pendentes | OAuth, falhas recuperáveis, retomada idempotente |
| F2 | Concluído | Integração Docs como projeção do banco | Publicação registra o ID do documento; retentativas não inserem entrada duplicada; página inicial é atualizada por dados estruturados | CQRS leve, projeções, consistência eventual |
| F2.1 | Concluído | Índice e tags factuais | Filtros por tags que descrevem conteúdo observável; não inferir diagnóstico ou simbolismo nesta etapa | taxonomia, extração estruturada, avaliação humana |
| F3 | Concluído | Busca no histórico | `/buscar` consulta por período, palavra e tags nos sonhos publicados; informa o total e permite exibir todos em mensagens paginadas, apenas a chats da allowlist | recuperação de informação, autorização por ferramenta |
| F3.1 | Concluído | Importação assistida do diário legado | Dry run validado; `--apply` criou backup e importou 22 relatos sem duplicação, gerando tags factuais | migração de dados, parsing tolerante, idempotência, revisão humana |
| F3.2 | Concluído | Descoberta de comandos | `/start` e `/ajuda` explicam as opções; o menu nativo do Telegram exibe os comandos registrados | UX conversacional, affordance, divulgação progressiva |
| F4 | Proposto | Catálogo de fontes para RAG | Cada fonte aprovada tem licença verificada, escopo, metadados e pequenos trechos indexáveis; não ingerir PDFs aleatórios ou traduções sem autorização | direitos autorais, proveniência, chunking, embeddings |
| F4.1 | Proposto | Avaliação de recuperação | Conjunto de consultas e fontes esperadas; medir se os resultados são pertinentes e citáveis antes de gerar análise | recall@k, precisão, conjunto dourado, evals |
| F5 | Proposto | Rascunho de reflexão simbólica fundamentada | Resumo factual + símbolos observáveis + fontes recuperadas + hipóteses probabilísticas + perguntas; sem salvar/enviar automaticamente | RAG, grounding, instruções, limites de escopo |
| F5.1 | Proposto | Aprovação humana | Telegram apresenta rascunho e opções de aprovar, editar ou descartar; somente aprovação aciona escrita/envio | human-in-the-loop, permissões, estado persistente |
| F6 | Proposto | Relatório longitudinal | Relatório por período com sonhos usados, datas e fontes; validação humana antes de persistir | composição multi-etapa, citações, evals qualitativos |
| F7 | Posterior | Visualização histórica | Relatório HTML navegável, estatísticas e nuvem de palavras apenas sobre dados consentidos; métricas não são interpretação | visualização, agregação, privacidade |
| F8 | Posterior | Operação e alternativas locais | Deploy 24/7 com monitoramento; avaliar SLM/ASR no celular ou local como opção de privacidade, com benchmark próprio | deploy, custo, ameaças, trade-offs local/nuvem |

## Decisões pendentes

| Decisão | Opções | Quando decidir |
| --- | --- | --- |
| Retenção de áudio | **Decidido:** apagar arquivo temporário após processamento; não manter cópia local persistente. O Telegram é responsável pela mensagem original | F1.1, decidido em 29/09/2026 |
| Data do sonho | **Decidido:** data de recebimento é o padrão; referências narradas divergentes exigem confirmação antes de substituir a data | F1.3, decidido em 29/09/2026 |
| Fonte para RAG | artigos abertos/licenciados; notas próprias; conteúdo com licença obtida | F4 |
| Vetores | busca textual primeiro; SQLite + extensão/local depois; serviço externo somente se necessário | após F3 |
| Hospedagem | máquina local; Render/PythonAnywhere/outro | F8, após fluxo recuperável |
| Renovação OAuth Google | **Decidido:** pedir consentimento no navegador do computador que executa o bot; jamais por Telegram. Depois, usar `/retomar_publicacoes` | F1.4, decidido em 30/09/2026 |
| Reenvio de áudio | Tratar a mesma mensagem do Telegram como idempotente; um novo envio é nova entrada. Futuramente, sinalizar possível duplicata por fingerprint e pedir confirmação | após F3 |

## Fontes candidatas para F4

| Fonte | Uso permitido no projeto | Limite importante |
| --- | --- | --- |
| Artigos open access com licença explícita (por exemplo, CC BY) em PMC, DOAJ ou periódicos open access | Indexar texto e metadados conforme os termos específicos da licença | Não tratar artigo como confirmação clínica de uma interpretação individual |
| DreamBank, CC BY-NC-SA 4.0 | Referência de frequência/padrões em relatos anonimizados, atribuindo a fonte | Não usar comercialmente; não é uma base de interpretações e não deve ser misturada a sonhos privados sem política clara |
| Notas próprias, com bibliografia de origem | Indexar integralmente; excelente para iniciar e auditar | Distinguir a nota da obra original e não reproduzir trechos protegidos longos |
| Obras/edições licenciadas expressamente | Indexar nos limites da licença contratada | Exigir registro da autorização, edição e escopo antes da ingestão |

## Protocolo de estudo em cada entrega

1. **Antes:** explicar objetivo, fronteira do problema e conceito novo; apontar uma ou duas referências primárias.
2. **Durante:** implementar em pequenos passos e mostrar a decisão de design antes de cada mudança material.
3. **Depois:** executar uma verificação, interpretar seu resultado e registrar o que foi aprendido em `HISTORY_LOG.md`.
4. **Prática guiada:** propor um exercício curto que possa ser feito pela pessoa usuária; avançar somente após ela decidir se quer tentar sozinha, em dupla ou delegar a implementação.

## Definition of done para qualquer item

- Implementação pequena e revisável.
- Teste ou verificação reproduzível proporcional ao risco.
- Dados sensíveis não entram em logs, fixtures ou Git.
- Documentação e decisão atualizadas.
- Mudanças externas (Docs/Telegram) realizadas somente com a autorização prevista.
