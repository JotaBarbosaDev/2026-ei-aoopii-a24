# 🤖 Agent: Content Pipeline
**Project 24 – Agent Systems**  
**João Barbosa – 32536**  
**Pedro Sousa – 31390**

---

## 🧾 Descrição

Este projeto implementa um **agente de pipeline de conteúdo** que recebe um único input, interpreta-o, adapta-o ao branding de uma empresa, gera vários formatos de conteúdo, avalia a qualidade, melhora o resultado se necessário e cria um documento final.

O foco do projeto é demonstrar:

- objetivo claro
- uso de ferramentas
- pipeline multi-step
- avaliação e melhoria automática
- comportamento persistente
- integração com um canal real de entrada

---

## 🚦 Estado Atual

O projeto está funcional com a seguinte arquitetura:

```text
Telegram Bot -> Python Agent -> Groq API -> PDF -> resposta no Telegram
```

Neste momento o sistema:

- recebe **texto ou link**
- extrai e resume o conteúdo
- traduz para **português** quando a fonte original está em inglês
- aplica branding a partir de um ficheiro local
- gera:
  - blog post
  - LinkedIn post
  - Twitter/X thread
  - newsletter
- gera imagens para:
  - blog
  - LinkedIn
  - X/Twitter
  - newsletter
- avalia clareza, engagement e branding
- melhora automaticamente o conteúdo se o score for baixo
- cria documento Markdown e PDF
- guarda histórico simples das execuções
- devolve o PDF ao utilizador no Telegram
- apresenta feedback intermédio e uma resposta final formatada no Telegram

---

## 🏗️ Arquitetura Atual

Durante o desenvolvimento, a arquitetura foi estabilizada para:

- **bot Telegram em Python** como camada de entrada
- **Groq** como provider LLM via API
- **pipeline Python local** como motor principal de processamento

### ✅ Justificação da Arquitetura Atual

Esta arquitetura foi escolhida por razões práticas e técnicas:

1. O ambiente disponível é um **MacBook Pro 2017 Intel**, por isso faz sentido usar um provider remoto.
2. O objetivo da cadeira é demonstrar **tool orchestration, multi-step reasoning e pipeline autónomo**.
3. **Groq** permite usar modelos remotos no plano gratuito, evitando correr modelos localmente.
4. A integração com Groq é simples porque a API é **OpenAI-compatible**.
5. Para uma demo académica, a combinação **Telegram + Python + Groq** reduz risco, setup e tempo de integração.

```text
Telegram -> bot Python -> pipeline Python -> Groq
```

---

## 🔄 Pipeline Atual

```text
Utilizador envia texto ou link no Telegram
        ↓
Bot Telegram recebe a mensagem
        ↓
Agent pipeline processa o input
        ↓
Tradução para português quando necessário
        ↓
Geração multi-formato com Groq
        ↓
Geração de imagens via Cloudflare Workers AI
        ↓
Avaliação de qualidade
        ↓
Melhoria automática se necessário
        ↓
Criação de Markdown e PDF
        ↓
Resposta no Telegram com o PDF
```

---

## ⚙️ Funcionalidades Implementadas

### 📥 Entrada

- Texto livre
- Link para artigo/página

### 🧠 Processamento

- Extração e normalização de input
- Identificação de título
- Resumo e key points
- Deteção simples de idioma
- Tradução automática para português quando a fonte está em inglês

### 🎨 Branding

- Branding local através de [`config/branding.json`](config/branding.json)
- Ajuste de:
  - voz
  - audiência
  - palavras proibidas
  - call to action

### ✍️ Geração de Conteúdo

- Blog post
- LinkedIn post
- Twitter/X thread
- Newsletter

Cada formato é gerado com diferenças estruturais e de tom. Não existe simples copy-paste entre outputs.

### 🖼️ Geração de Imagens

- imagem para blog
- imagem para LinkedIn
- imagem para X/Twitter
- imagem para newsletter
- geração remota via Cloudflare Workers AI
- tema visual alinhado com a notícia e com o branding da empresa

### 📊 Avaliação e Melhoria

- Scoring por:
  - clareza
  - engagement
  - branding
- auto-correction loop até ao threshold configurado

### 📄 Exportação

- Markdown
- PDF

### 💬 Resposta no Telegram

- feedback de progresso
- PDF enviado diretamente no chat
- caption formatado com destaque para:
  - tema
  - resumo
  - ficheiro
  - score
  - melhorias
  - link, quando disponível

### 🗂️ Memória

- histórico simples em JSONL
- loop persistente local

### 🌐 Integração Externa

- Groq via API
- Bot Telegram funcional
- Cloudflare Workers AI para geração de imagens

---

## 🚧 O Que Ainda Falta

Para o projeto ficar mais próximo da versão completa descrita no enunciado, ainda faltam estas partes:

1. **Figma**
   - neste momento não há integração direta com Figma
   - o branding está fixo em JSON local

2. **Google Docs / Google Drive**
   - o documento final é PDF local
   - ainda não há criação de Google Doc nem upload para Drive

3. **Link público real**
   - o projeto pode devolver `file://` ou HTTP local
   - `telegram-stack` já consegue servir localmente os PDFs e escolher uma porta livre
   - ainda não há hosting público real

4. **Inputs multimédia**
   - áudio, vídeo e ficheiros ainda não são processados
   - o bot responde que esses formatos ainda não estão ligados

5. **Documentação residual**
   - ainda existe documentação histórica em `docs/OPENCLAW.md`
   - a arquitetura principal atual é Telegram + Groq + pipeline Python

---

## 🗃️ Estrutura do Repositório

```text
.
├── config/branding.json          # Branding local usado pelo pipeline
├── data/generated/               # Markdown/PDF gerados localmente
├── data/memory/                  # Histórico JSONL das execuções
├── data/public/                  # Pasta simulada de upload público
├── docs/OPENCLAW.md              # Notas históricas de uma abordagem anterior
├── examples/sample_input.txt     # Input de demonstração
├── src/content_pipeline/         # Código principal
│   ├── agent.py                  # Orquestra o pipeline
│   ├── env.py                    # Leitura de .env / .env.local
│   ├── telegram_bot.py           # Integração com Telegram
│   └── tools/                    # Ferramentas do pipeline
└── tests/                        # Testes automatizados
```

---

## 🔐 Configuração

O projeto lê automaticamente `.env` e `.env.local`.

Exemplo mínimo:

```bash
LLM_PROVIDER=groq
GROQ_API_KEY=your-groq-api-key
GROQ_MODEL=llama-3.1-8b-instant
TELEGRAM_BOT_TOKEN=your-telegram-bot-token
CLOUDFLARE_API_TOKEN=your-cloudflare-api-token
CLOUDFLARE_ACCOUNT_ID=your-cloudflare-account-id
CLOUDFLARE_IMAGE_MODEL=@cf/bytedance/stable-diffusion-xl-lightning
```

Variáveis opcionais:

```bash
PUBLIC_BASE_URL=http://127.0.0.1:8000
```

Isto permite gerar links HTTP quando estiveres a servir a pasta `data/public`.

---

## 🚀 Guia de Utilização

### 1. 📥 Clonar o projeto

Com SSH:

```bash
git clone git@github.com:JotaBarbosaDev/2026-ei-aoopii-a18.git
cd 2026-ei-aoopii-a18
```

Se preferires HTTPS:

```bash
git clone https://github.com/JotaBarbosaDev/2026-ei-aoopii-a18.git
cd 2026-ei-aoopii-a18
```

### 2. 🧪 Criar ambiente virtual

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. 📦 Instalar dependências

Como neste Mac o caminho do projeto contém `º`, o `pip install -e .` pode falhar em modo editable.  
Por isso, a forma mais estável aqui é instalar apenas as dependências necessárias:

```bash
python3 -m pip install --upgrade pip
python3 -m pip install certifi deep-translator reportlab "python-telegram-bot>=22,<23"
```

### 4. ⚙️ Configurar o `.env`

Cria o ficheiro `.env` a partir do exemplo:

```bash
cp .env.example .env
```

Depois preenche:

```bash
LLM_PROVIDER=groq
GROQ_API_KEY=your-groq-api-key
GROQ_MODEL=llama-3.1-8b-instant
TELEGRAM_BOT_TOKEN=your-telegram-bot-token
```

Opcional:

```bash
PUBLIC_BASE_URL=http://127.0.0.1:8000
```

### 5. ▶️ Arrancar a pipeline completa

O comando mais simples para demo é:

```bash
PYTHONPATH=src python3 -m content_pipeline telegram-stack
```

Este comando arranca:

- servidor HTTP local para a pasta `data/public`
- bot Telegram
- configuração automática do link local para os PDFs
- envio dos assets visuais gerados por plataforma

Se a porta `8000` já estiver ocupada, o projeto tenta usar a próxima porta livre.

### 6. 📱 Encontrar o bot no Telegram

No Telegram, procura por:

```text
@NewPostAOOPBot
```

Abre o chat e envia:

```text
/start
```

Se quiseres ver a ajuda disponível:

```text
/help
```

### 7. ✅ Testar o fluxo completo

Podes testar de duas formas:

1. Enviar texto diretamente
2. Enviar um link para uma notícia ou artigo

Exemplos:

```text
https://www.publico.pt/...
```

ou

```text
A inteligência artificial está a mudar a forma como as equipas de marketing transformam pesquisa em conteúdo...
```

Resultado esperado:

- o bot mostra progresso no chat
- processa o input
- gera o documento
- envia o PDF diretamente no Telegram
- inclui tema, resumo, ficheiro, score, melhorias e link, quando disponível

### 8. 🛑 Parar a execução

No terminal onde arrancaste a stack:

```bash
Ctrl+C
```

---

## ▶️ Como Executar

### ⚠️ Nota sobre este repositório

Neste Mac, o caminho do projeto contém o carácter `º`, e em algumas instalações isso faz o `pip install -e .` falhar em modo editable.  
Por esse motivo, a forma mais estável de correr o projeto aqui é:

```bash
PYTHONPATH=src python3 -m content_pipeline ...
```

### 🧪 Executar uma demo local

```bash
PYTHONPATH=src python3 -m content_pipeline run --file examples/sample_input.txt
```

Ou com texto direto:

```bash
PYTHONPATH=src python3 -m content_pipeline run --input "cola aqui o artigo ou link"
```

JSON completo:

```bash
PYTHONPATH=src python3 -m content_pipeline run --file examples/sample_input.txt --json
```

### ♻️ Loop persistente local

```bash
PYTHONPATH=src python3 -m content_pipeline loop
```

### 🗃️ Histórico

```bash
PYTHONPATH=src python3 -m content_pipeline history --limit 5
```

### 🌍 Servir PDFs localmente por HTTP

```bash
PYTHONPATH=src python3 -m content_pipeline serve --directory data/public --port 8000
```

### 🤖 Arrancar o bot Telegram

```bash
PYTHONPATH=src python3 -m content_pipeline telegram-bot
```

### 🚀 Arrancar a stack completa

Este é o comando mais útil para demo, porque arranca:

- servidor HTTP local para os PDFs
- bot Telegram
- configuração automática de `PUBLIC_BASE_URL`

```bash
PYTHONPATH=src python3 -m content_pipeline telegram-stack
```

Se a porta `8000` já estiver ocupada, o projeto tenta usar a seguinte porta livre.

---

## 📱 Bot Telegram

O bot Telegram já está integrado no projeto.

Bot atual:

```text
@NewPostAOOPBot
```

Comportamento atual:

- aceita texto e links enviados em mensagem
- chama o pipeline internamente
- traduz conteúdo para português quando necessário
- gera imagens por plataforma quando a Cloudflare está configurada
- gera o PDF
- devolve o PDF diretamente no chat
- envia as imagens geradas antes do PDF
- mostra feedback de progresso durante o processamento
- mostra score e número de melhorias no caption
- destaca os campos fixos no caption para facilitar leitura
- inclui link apenas se existir URL HTTP/HTTPS pública

Limitações atuais:

- ainda não processa áudio
- ainda não processa vídeo
- ainda não processa documentos anexos como input

---

## 🛠️ Ferramentas Implementadas

| Ferramenta | Implementação atual |
| --- | --- |
| `generate_content(input)` | Gera blog post, LinkedIn post, Twitter/X thread e newsletter |
| `evaluate_content(content)` | Calcula score de clareza, engagement e branding |
| `improve_content(content)` | Corrige outputs abaixo do threshold |
| `create_document(content)` | Cria Markdown e PDF |
| `upload_document(file)` | Copia o PDF para pasta pública e devolve URL |

---

## 🧰 Tecnologias

- Python
- Groq API
- Telegram Bot API
- Cloudflare Workers AI
- deep-translator
- reportlab
- JSONL para memória simples
- PDF gerado localmente

Tecnologias planeadas mas ainda não integradas:

- Figma
- Google Docs API
- Google Drive API

---

## ✅ Testes

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
```

---

## 🧭 Histórico e Decisões

### 1. 💡 Ideia inicial

- arquitetura pensada como agente com canal de mensagens
- Telegram como canal principal
- pipeline multi-step desde o início

**Motivo:** definir primeiro o fluxo end-to-end do agente.

### 2. 🧱 Implementação do núcleo do pipeline

- criação do agente em Python
- geração multi-formato
- avaliação de qualidade
- melhoria iterativa
- exportação para PDF
- memória em JSONL

**Motivo:** garantir primeiro a parte central do projeto antes das integrações externas.

### 3. 🧠 Integração real com Groq

- suporte explícito a `LLM_PROVIDER=groq`
- leitura automática de `.env`
- correção de SSL e compatibilidade de requests

**Motivo:** usar um LLM remoto gratuito e estável sem correr modelos localmente.

### 4. 📲 Integração do bot Telegram

- criação do módulo `telegram_bot.py`
- comando CLI `telegram-bot`
- comando CLI `telegram-stack`
- envio do PDF diretamente no chat

**Motivo:** cumprir o requisito de interação por mensagem e permitir uma demo end-to-end.

### 5. 🌍 Tradução automática e normalização de idioma

- deteção simples de idioma na fonte
- tradução da fonte em inglês para português
- normalização do conteúdo final quando o modelo devolve partes em inglês

**Motivo:** manter o documento final coerente para demonstração em português, independentemente do idioma original da notícia.

### 6. ✨ Melhoria da experiência no Telegram

- mensagens de progresso
- caption final com destaque visual
- arranque simplificado com `telegram-stack`
- escolha automática de porta livre para o servidor local

**Motivo:** tornar a demo mais estável e mais legível durante a apresentação.

### 7. 🖼️ Geração remota de imagens

- integração com Cloudflare Workers AI
- geração de imagens com dimensões próprias por canal
- envio das imagens no Telegram antes do PDF

**Motivo:** complementar cada saída textual com assets visuais específicos para blog e redes sociais.

---

## 📌 Resumo

O projeto já demonstra um agente funcional com:

- objetivo definido
- uso de ferramentas
- pipeline multi-step
- avaliação e melhoria automática
- memória simples
- integração com Telegram
- uso de LLM real via Groq
- tradução automática para português
- geração remota de imagens por plataforma
- geração e entrega de PDF com feedback no Telegram

O que falta para a versão mais completa é sobretudo:

- branding ligado ao Figma
- publicação real do documento em Google Docs / Drive ou outro hosting público
- suporte multimédia além de texto e links
