# 📦 Agent: Content Pipeline  
**Project 24 – Agent Systems**  
**João Barbosa – 32536**  
**Pedro Sousa – 31390**

---

## 📌 Descrição

Este projeto consiste no desenvolvimento de um **agente de Inteligência Artificial** capaz de receber um único input (notícia, artigo, vídeo, pesquisa ou áudio) e gerar automaticamente conteúdo adaptado a múltiplas plataformas, respeitando o **branding de uma empresa**.

O agente atua de forma autónoma, utilizando ferramentas, avaliando os seus resultados e melhorando continuamente o seu desempenho.

---

## 🎯 Objetivo

Criar um agente que:

- Recebe conteúdo como input (texto, link ou media)
- Adapta o conteúdo ao branding da empresa (baseado em Figma)
- Gera múltiplos formatos de conteúdo:
  - Blog post
  - LinkedIn post
  - Tweet thread
  - Newsletter section
- Insere o conteúdo num documento (Google Docs)
- Hospeda o documento remotamente
- Envia ao utilizador um link para acesso

---

## ⚙️ Funcionalidades do Agente

### 🤖 Interação
- Comunicação via:
  - Telegram  
  - WhatsApp (opcional)  
  - Discord (opcional)

---

### 🧠 Processamento

- O agente é orquestrado através do **OpenClaw**
- O OpenClaw gere:
  - execução de tarefas  
  - utilização de ferramentas (tool calling)  
  - ciclo de decisão do agente  

- Integração com LLMs:
  - OpenAI GPT  
  - OpenRouter  

---

### 🎨 Branding
- Adaptação de conteúdo com base em guidelines definidas no **Figma**
- Ajuste de:
  - Tom  
  - Estrutura  
  - Estilo de comunicação  

---

### 📝 Geração de Conteúdo

A partir de um único input, o agente gera:

- Blog post (long-form)  
- LinkedIn post (profissional)  
- Tweet thread (mais informal)  
- Secção de newsletter  

⚠️ Cada formato é adaptado — não existe simples reescrita.

---

### 📄 Exportação
- Criação automática de documentos:
  - Google Docs  
  - PDF (opcional)

---

### ☁️ Hosting
- Upload do documento para servidor remoto ou Google Drive  
- Geração de link público  

---

### 🔁 Envio ao Utilizador
- O agente devolve o link através da plataforma de origem  

---

## 🧠 Características de Agente

O sistema cumpre os princípios de um agente autónomo:

- Atua com um objetivo definido  
- Utiliza ferramentas externas  
- Executa tarefas de forma autónoma  
- Mantém um ciclo de execução contínuo (loop persistente)  
- Mede a qualidade dos resultados  
- Melhora outputs através de auto-avaliação  
- Aprende com execuções anteriores (histórico)  

Estas capacidades são suportadas pelo OpenClaw, que permite a execução de agentes com comportamento autónomo e iterativo.

---

## 🔄 Pipeline do Sistema

- Input (Telegram / WhatsApp / Discord)  
  ↓  
- Processamento (OpenClaw + LLM)  
  ↓  
- Adaptação ao Branding (Figma-based)  
  ↓  
- Geração Multi-Formato  
  ↓  
- Criação de Documento (Google Docs)  
  ↓  
- Upload / Partilha (Google Drive)  
  ↓  
- Envio de link ao utilizador  

---

## 🏗️ Arquitetura

- SSH → VM  
  ↓  
- OpenClaw Agent Runtime  
  ↓  
- Tools:
  - LLM (OpenAI / OpenRouter)  
  - Google Docs / Drive API  
  - File Upload  
  ↓  
- Outputs:
  - Telegram  
  - WhatsApp  
  - Discord  

---

## 🧪 Tecnologias

- Python (backend)  
- OpenClaw  
- LLM APIs (OpenAI, OpenRouter)  
- Telegram Bot API  
- Google Docs API / Google Drive API  
- VM para hosting remoto  

---

## ⚡ Framework de Agente

### OpenClaw

O OpenClaw é utilizado como framework principal para implementação do agente.

Responsabilidades:
- Orquestração do fluxo do agente  
- Gestão de ferramentas  
- Execução de tarefas iterativas  
- Suporte a loops persistentes  

Comandos principais:
- `openclaw onboard`  
- `openclaw tui`  

---

### Alternativa (não utilizada)

AI Agentic Harnesses:
- Hermes  
- Codex  
- Claude Code  
- Gemini  

---

## 📊 Requisitos do Projeto

- Pelo menos **3 formatos de output**  
- Adaptação específica por plataforma  
- Uso de LLM  
- Demonstração de comportamento de agente  
- Sem rephrasing genérico  

---

## 🚀 Execução (exemplo)

1. Enviar conteúdo para o bot (Telegram)  
2. O agente processa o input  
3. Gera conteúdos multi-plataforma  
4. Cria documento (Google Docs)  
5. Partilha documento (link público)  
6. Devolve link ao utilizador  

---

## 📁 Estrutura do Repositório

```text
.
├── config/branding.json          # Guidelines de branding usadas pelo agente
├── data/generated/               # Markdown/PDF gerados localmente
├── data/memory/                  # Historico JSONL das execucoes
├── data/public/                  # Pasta simulada de upload publico
├── docs/OPENCLAW.md              # Como ligar o pipeline ao OpenClaw
├── examples/sample_input.txt     # Input de demonstracao
├── src/content_pipeline/         # Codigo do agente, ferramentas e CLI
└── tests/                        # Testes do pipeline
```

---

## ▶️ Como Executar

Criar ambiente virtual e instalar o pacote:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

Executar uma demonstracao com o input de exemplo:

```bash
content-pipeline run --file examples/sample_input.txt
```

Tambem e possivel executar sem instalar, usando `PYTHONPATH`:

```bash
PYTHONPATH=src python3 -m content_pipeline run --file examples/sample_input.txt
```

O resultado inclui:

- ID da execucao
- titulo identificado
- score de qualidade
- numero de ciclos de melhoria
- link para o PDF gerado

---

## 🔁 Loop Persistente

Para demonstrar comportamento continuo de agente:

```bash
content-pipeline loop
```

Cada linha enviada no terminal e tratada como um novo input do utilizador. O agente executa o pipeline completo, gera documento, faz upload local e regista a execucao em memoria.

---

## 🤖 Bot Telegram

Depois de adicionares `TELEGRAM_BOT_TOKEN` ao `.env`, arranca o bot com:

```bash
content-pipeline telegram-bot
```

Sem instalacao editable:

```bash
PYTHONPATH=src python3 -m content_pipeline telegram-bot
```

O bot aceita texto e links enviados em mensagem, executa o pipeline com Groq e devolve o PDF diretamente no Telegram.

---

## 🌐 Links Publicos em Demo

Por defeito, o upload devolve um link `file://` para a pasta `data/public`.

Para simular hosting HTTP local:

```bash
content-pipeline serve --directory data/public --port 8000
```

Noutra janela:

```bash
PUBLIC_BASE_URL=http://127.0.0.1:8000 content-pipeline run --file examples/sample_input.txt
```

Num deployment real, este passo pode ser substituido por Google Drive, Google Docs API, S3, servidor da VM ou outro servico de hosting.

---

## 🧩 Ferramentas Implementadas

| Ferramenta | Implementacao |
| --- | --- |
| `generate_content(input)` | Gera blog post, LinkedIn post, Twitter thread e newsletter |
| `evaluate_content(content)` | Calcula score de clareza, engagement e branding |
| `improve_content(content)` | Corrige outputs abaixo do threshold |
| `create_document(content)` | Cria Markdown e PDF |
| `upload_document(file)` | Copia o PDF para pasta publica e devolve URL |

O provider por defeito e `demo`, para a apresentacao funcionar sem chaves de API. Para usar um endpoint real compativel com OpenAI Chat Completions:

```bash
LLM_PROVIDER=openai OPENAI_API_KEY=... OPENAI_MODEL=... content-pipeline run --file examples/sample_input.txt
LLM_PROVIDER=openrouter OPENROUTER_API_KEY=... OPENROUTER_MODEL=... content-pipeline run --file examples/sample_input.txt
```

Para usar Groq diretamente:

```bash
LLM_PROVIDER=groq GROQ_API_KEY=... GROQ_MODEL=llama-3.1-8b-instant content-pipeline run --file examples/sample_input.txt
```

Para o bot Telegram, adiciona tambem:

```bash
TELEGRAM_BOT_TOKEN=...
```

Tambem existe o modo generico:

```bash
LLM_PROVIDER=compatible LLM_BASE_URL=... LLM_API_KEY=... LLM_MODEL=... content-pipeline run --file examples/sample_input.txt
```

O projeto tambem carrega automaticamente um ficheiro `.env` ou `.env.local` na raiz do repositorio, por exemplo:

```bash
LLM_PROVIDER=groq
GROQ_API_KEY=...
GROQ_MODEL=llama-3.1-8b-instant
TELEGRAM_BOT_TOKEN=...
```

---

## 🧪 Testes

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
```

---

## 📎 Integração OpenClaw

Ver instrucoes em [`docs/OPENCLAW.md`](docs/OPENCLAW.md).

Resumo:

1. Configurar OpenClaw com `openclaw onboard`
2. Ligar Telegram no runtime
3. Instruir o agente a executar:

```bash
PYTHONPATH=src python3 -m content_pipeline run --input "<mensagem do utilizador>" --json
```

4. Devolver ao utilizador o link final, score e numero de melhorias

---

## 🧾 Resumo

O projeto implementa um agente de IA capaz de transformar um único input em múltiplos conteúdos adaptados a diferentes plataformas, respeitando o branding de uma empresa, com geração automática de documentos e distribuição remota.

O agente apresenta comportamento autónomo, com capacidade de avaliação, melhoria contínua e execução persistente, suportado pelo framework OpenClaw.
