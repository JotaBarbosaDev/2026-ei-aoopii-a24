from __future__ import annotations

import asyncio
from pathlib import Path

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
        await update.message.reply_text(
            "Envia um artigo, link ou texto. Eu gero o documento e devolvo o PDF."
        )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message:
        await update.message.reply_text(
            "Inputs suportados agora: texto e links enviados em mensagem.\n"
            "O bot gera blog, LinkedIn, thread, newsletter e devolve o PDF."
        )


async def handle_text_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.text:
        return

    await update.message.chat.send_action(ChatAction.TYPING)
    agent = context.application.bot_data["agent"]

    try:
        result = await asyncio.to_thread(agent.run, update.message.text)
    except Exception as exc:
        await update.message.reply_text(f"Erro a processar o pedido: {exc}")
        return

    await send_pipeline_result(update, result)


async def handle_unsupported_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message:
        await update.message.reply_text(
            "Por agora aceita texto ou links enviados na mensagem. "
            "Audio, video e ficheiros ainda nao estao ligados."
        )


async def send_pipeline_result(update: Update, result: PipelineResult) -> None:
    if not update.message:
        return

    await update.message.chat.send_action(ChatAction.UPLOAD_DOCUMENT)

    caption = build_result_caption(result)
    with Path(result.document.path).open("rb") as document_file:
        await update.message.reply_document(
            document=document_file,
            filename=Path(result.document.path).name,
            caption=caption,
        )


def build_result_caption(result: PipelineResult) -> str:
    lines = [
        f"Score: {result.evaluation.overall}/10",
        f"Melhorias: {result.iterations}",
    ]
    if result.upload.url.startswith(("http://", "https://")):
        lines.append(f"Link: {result.upload.url}")
    return "\n".join(lines)
