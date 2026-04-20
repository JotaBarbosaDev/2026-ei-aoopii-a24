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
- Insere o conteúdo num documento (Word ou PDF)
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
- Utilização de LLMs:
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
  - Microsoft Word  
  - PDF  

---

### ☁️ Hosting
- Upload do documento para servidor remoto  
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

---

## 🔄 Pipeline do Sistema

- Input (Telegram / WhatsApp / Discord)  
  ↓  
- Processamento (LLM)  
  ↓  
- Adaptação ao Branding (Figma-based)  
  ↓  
- Geração Multi-Formato  
  ↓  
- Criação de Documento (Word/PDF)  
  ↓  
- Upload para servidor  
  ↓  
- Envio de link ao utilizador  

---

## 🏗️ Arquitetura

- SSH → VM  
  ↓  
- Backend (Python)  
  ↓  
- LLM Processing  
  - OpenAI  
  - OpenRouter  
  ↓  
- Outputs:
  - Telegram  
  - WhatsApp  
  - Discord  

---

## 🧪 Tecnologias

- Python (backend)  
- LLM APIs (OpenAI, OpenRouter)  
- Telegram Bot API  
- python-docx / ferramentas PDF  
- VM para hosting remoto  

---

## ⚡ Frameworks de Agente

O agente pode ser implementado utilizando uma das seguintes abordagens:

### OpenClaw
- `openclaw onboard`  
- `openclaw tui`  

### Alternativa: AI Agentic Harnesses
- Hermes  
- Codex  
- Claude Code  
- Gemini  

👉 Apenas uma abordagem será utilizada na implementação.

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
4. Cria documento (Word/PDF)  
5. Faz upload para servidor  
6. Devolve link ao utilizador  

---

## 📁 Estrutura do Repositório

Inclui `.gitkeep` para garantir que diretórios vazios são versionados.

---

## 🧾 Resumo

O projeto implementa um agente de IA capaz de transformar um único input em múltiplos conteúdos adaptados a diferentes plataformas, respeitando o branding de uma empresa, com geração automática de documentos e distribuição remota.

O agente apresenta comportamento autónomo, com capacidade de avaliação, melhoria contínua e execução persistente.
