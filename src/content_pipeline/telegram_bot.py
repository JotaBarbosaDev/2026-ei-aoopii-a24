from __future__ import annotations

import asyncio
from html import escape
from pathlib import Path
from textwrap import shorten
from typing import Callable

from .agent import ContentPipelineAgent
from .config import load_config
from .env import load_local_env, required_env
from .models import PipelineResult
from .tools import select_llm_provider

try:
    from telegram import Update
    from telegram.constants import ChatAction
    from telegram.ext import (
        Application,
        ApplicationBuilder,
        CommandHandler,
        ContextTypes,
        MessageHandler,
        filters,
    )
except ImportError as exc:  # pragma: no cover - runtime dependency
    raise ImportError(
        "python-telegram-bot is required to run the Telegram bot. "
        "Install dependencies with `python3 -m pip install -e .`."
    ) from exc


def main() -> int:
    run_telegram_bot()
    return 0


def run_telegram_bot(agent: ContentPipelineAgent | None = None) -> None:
    application = build_application(agent)
    application.run_polling(allowed_updates=Update.ALL_TYPES)


def build_application(agent: ContentPipelineAgent | None = None) -> Application:
    load_local_env()
    token = required_env("TELEGRAM_BOT_TOKEN")
    pipeline_agent = agent or ContentPipelineAgent(load_config(), llm=select_llm_provider())

    application = ApplicationBuilder().token(token).build()
    application.bot_data["agent"] = pipeline_agent

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_input))
    application.add_handler(
        MessageHandler(
            filters.ATTACHMENT | filters.PHOTO | filters.VIDEO | filters.AUDIO | filters.VOICE,
            handle_unsupported_input,
        )
    )
    return application


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message:
        await update.message.reply_text(build_welcome_message())


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message:
        await update.message.reply_text(build_help_message())


async def handle_text_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.text:
        return

    await update.message.chat.send_action(ChatAction.TYPING)
    agent = context.application.bot_data["agent"]
    progress_message = await update.message.reply_text(
        "📥 Pedido recebido. Vou começar a processar agora."
    )
    progress_reporter = build_progress_reporter(progress_message)

    try:
        result = await asyncio.to_thread(agent.run, update.message.text, progress_reporter)
    except Exception as exc:
        await safe_edit_message(
            progress_message,
            "⚠️ O processamento falhou. Verifica o link ou tenta enviar o texto diretamente.",
        )
        await update.message.reply_text(f"Erro a processar o pedido: {exc}")
        return

    await safe_edit_message(progress_message, "✅ Processamento concluido. Vou enviar o PDF.")
    await send_pipeline_result(update, result)


async def handle_unsupported_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message:
        await update.message.reply_text(
            "📎 Por agora aceito texto ou links enviados na mensagem.\n"
            "Comandos: /start e /help\n"
            "🎙️ Audio, video e ficheiros ainda nao estao ligados."
        )


async def send_pipeline_result(update: Update, result: PipelineResult) -> None:
    if not update.message:
        return

    await update.message.chat.send_action(ChatAction.UPLOAD_DOCUMENT)

    caption = build_result_caption(result)
    with Path(result.document.path).open("rb") as document_file:
        await update.message.reply_document(
            document=document_file,
            filename=result.document.download_name or Path(result.document.path).name,
            caption=caption,
            parse_mode="HTML",
        )


def build_result_caption(result: PipelineResult) -> str:
    topic = _best_topic_title(result)
    description = _best_description(result)
    lines = [
        "<b>✅ Documento gerado com sucesso</b>",
        f"📰 <b>Tema:</b> {escape(topic)}",
        f"📝 <b>Resumo:</b> {escape(description)}",
        f"📄 <b>Ficheiro:</b> {escape(result.document.download_name or Path(result.document.path).name)}",
        f"📊 <b>Score de qualidade:</b> {result.evaluation.overall}/10",
        f"🔁 <b>Melhorias automaticas:</b> {result.iterations}",
    ]
    if result.source.language == "english":
        lines.append("🌍 <b>Idioma:</b> Fonte original em ingles. O documento final foi preparado em portugues.")
    if result.upload.url.startswith(("http://", "https://")):
        lines.append(f"🔗 <b>Link:</b> {escape(result.upload.url)}")
    return "\n".join(lines)


def build_welcome_message() -> str:
    return (
        "🤖 Ola. Sou o Agent: Content Pipeline.\n\n"
        "Posso receber um texto ou link, gerar conteudo em varios formatos, "
        "avaliar a qualidade, melhorar o resultado e devolver um PDF final.\n\n"
        "📌 Comandos disponiveis:\n"
        "/start - introducao rapida\n"
        "/help - comandos, inputs suportados e limites\n\n"
        "🚀 O que podes fazer agora:\n"
        "- enviar um artigo em texto\n"
        "- enviar um link para uma noticia ou artigo\n"
        "- testar diferentes temas e ver o PDF final"
    )


def build_help_message() -> str:
    return (
        "📘 Comandos disponiveis:\n"
        "/start - mostra a introducao do bot\n"
        "/help - mostra esta ajuda\n\n"
        "📥 Inputs suportados agora:\n"
        "- texto livre\n"
        "- links enviados em mensagem\n\n"
        "⚙️ O que o bot faz:\n"
        "- extrai o conteudo\n"
        "- aplica branding\n"
        "- gera blog, LinkedIn, thread e newsletter\n"
        "- avalia qualidade\n"
        "- melhora se necessario\n"
        "- cria e envia o PDF\n\n"
        "🧩 Limitacoes atuais:\n"
        "- audio, video e ficheiros ainda nao estao ligados\n"
        "- alguns sites de noticias podem expor apenas parte do artigo"
    )


def build_progress_reporter(progress_message: object) -> Callable[[str], None]:
    loop = asyncio.get_running_loop()
    last_message = {"text": ""}

    def report(text: str) -> None:
        text = _format_progress_message(text)
        if text == last_message["text"]:
            return
        last_message["text"] = text
        loop.call_soon_threadsafe(
            lambda: asyncio.create_task(safe_edit_message(progress_message, text))
        )

    return report


async def safe_edit_message(progress_message: object, text: str) -> None:
    try:
        await progress_message.edit_text(text)
    except Exception:
        return


def _best_topic_title(result: PipelineResult) -> str:
    if result.source.language in {"english", "portuguese"} and result.source.title:
        return result.source.title
    first_line = result.content.blog_post.splitlines()[0].strip()
    if first_line.startswith("#"):
        title = first_line.lstrip("# ").strip()
        if title:
            return title
    return result.source.title


def _best_description(result: PipelineResult) -> str:
    if result.source.language in {"english", "portuguese"} and result.source.summary:
        return shorten(result.source.summary, width=160, placeholder="...")
    lines = [line.strip() for line in result.content.blog_post.splitlines() if line.strip()]
    for line in lines[1:]:
        if line.startswith("#"):
            continue
        if line.startswith("- "):
            continue
        return shorten(line, width=160, placeholder="...")
    return shorten(result.source.summary, width=160, placeholder="...")


def _format_progress_message(text: str) -> str:
    mapping = {
        "A analisar o input recebido.": "🔎 A analisar o input recebido.",
        "Input identificado como link.": "🔗 Input identificado como link.",
        "Input identificado como texto.": "📝 Input identificado como texto.",
        "Fonte em ingles detetada. Vou preparar a versao final em portugues.": "🌍 Fonte em ingles detetada. Vou preparar a versao final em portugues.",
        "A gerar as varias versoes de conteudo.": "🧠 A gerar as varias versoes de conteudo.",
        "A avaliar qualidade e alinhamento com o branding.": "📊 A avaliar qualidade e alinhamento com o branding.",
        "A melhorar o conteudo com base na avaliacao.": "🛠️ A melhorar o conteudo com base na avaliacao.",
        "A reavaliar depois das melhorias.": "📈 A reavaliar depois das melhorias.",
        "A criar o documento final.": "📄 A criar o documento final.",
        "A preparar o ficheiro para entrega.": "📦 A preparar o ficheiro para entrega.",
        "Concluido. Vou enviar o PDF.": "✅ Concluido. Vou enviar o PDF.",
    }
    return mapping.get(text, text)
