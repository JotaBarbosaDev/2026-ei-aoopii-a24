from __future__ import annotations

import argparse
import json
import os
import socket
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .agent import ContentPipelineAgent
from .config import PROJECT_ROOT, load_config
from .tools import select_llm_provider


def main() -> int:
    parser = argparse.ArgumentParser(description="Agent: Content Pipeline")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Process one input and return a document link.")
    _add_common_config_args(run_parser)
    input_group = run_parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument("--input", help="Raw text or URL to process.")
    input_group.add_argument("--file", type=Path, help="File containing the input text.")
    run_parser.add_argument("--json", action="store_true", help="Print the full pipeline result as JSON.")

    loop_parser = subparsers.add_parser("loop", help="Run a persistent local stdin loop.")
    _add_common_config_args(loop_parser)

    history_parser = subparsers.add_parser("history", help="Show recent execution memory.")
    _add_common_config_args(history_parser)
    history_parser.add_argument("--limit", type=int, default=5)

    serve_parser = subparsers.add_parser("serve", help="Serve uploaded demo documents locally.")
    serve_parser.add_argument("--directory", type=Path, default=PROJECT_ROOT / "data" / "public")
    serve_parser.add_argument("--host", default="127.0.0.1")
    serve_parser.add_argument("--port", type=int, default=8000)

    bot_parser = subparsers.add_parser("telegram-bot", help="Run the Telegram bot.")
    _add_common_config_args(bot_parser)

    stack_parser = subparsers.add_parser(
        "telegram-stack",
        help="Run the local document server and the Telegram bot together.",
    )
    _add_common_config_args(stack_parser)
    stack_parser.add_argument("--host", default="127.0.0.1")
    stack_parser.add_argument("--port", type=int, default=8000)

    args = parser.parse_args()

    if args.command == "serve":
        return _serve(args.directory, args.host, args.port)

    if args.command == "telegram-stack":
        resolved_port = _find_available_port(args.host, args.port)
        args.port = resolved_port
        os.environ.setdefault("PUBLIC_BASE_URL", _build_public_base_url(args.host, args.port))

    config = load_config(
        branding_path=args.branding,
        quality_threshold=args.threshold,
        max_improvement_rounds=args.max_rounds,
        generated_dir=args.generated_dir,
        public_dir=args.public_dir,
        memory_path=args.memory_path,
    )
    agent = ContentPipelineAgent(config, llm=select_llm_provider())

    if args.command == "telegram-bot":
        from .telegram_bot import run_telegram_bot

        run_telegram_bot(agent)
        return 0

    if args.command == "telegram-stack":
        from .telegram_bot import run_telegram_bot

        return _run_telegram_stack(
            agent=agent,
            public_dir=args.public_dir,
            host=args.host,
            port=args.port,
        )

    if args.command == "run":
        payload = args.input if args.input is not None else args.file.read_text(encoding="utf-8")
        result = agent.run(payload)
        if args.json:
            print(json.dumps(result.as_dict(), ensure_ascii=False, indent=2))
        else:
            print(f"Run ID: {result.run_id}")
            print(f"Title: {result.source.title}")
            print(f"Score: {result.evaluation.overall}/10")
            print(f"Improvement rounds: {result.iterations}")
            print(f"Document: {result.upload.url}")
        return 0

    if args.command == "loop":
        agent.run_forever()
        return 0

    if args.command == "history":
        records = agent.memory.recent(args.limit)
        print(json.dumps(records, ensure_ascii=False, indent=2))
        return 0

    parser.error("Unknown command.")
    return 2


def _add_common_config_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--branding", type=Path, default=PROJECT_ROOT / "config" / "branding.json")
    parser.add_argument("--threshold", type=float, default=8.5)
    parser.add_argument("--max-rounds", type=int, default=2)
    parser.add_argument("--generated-dir", type=Path, default=PROJECT_ROOT / "data" / "generated")
    parser.add_argument("--public-dir", type=Path, default=PROJECT_ROOT / "data" / "public")
    parser.add_argument("--memory-path", type=Path, default=PROJECT_ROOT / "data" / "memory" / "executions.jsonl")


def _serve(directory: Path, host: str, port: int) -> int:
    directory.mkdir(parents=True, exist_ok=True)
    handler = partial(SimpleHTTPRequestHandler, directory=str(directory))
    server = ThreadingHTTPServer((host, port), handler)
    print(f"Serving {directory.resolve()} at http://{host}:{port}/")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping document server.")
    finally:
        server.server_close()
    return 0


def _run_telegram_stack(
    agent: ContentPipelineAgent,
    public_dir: Path,
    host: str,
    port: int,
) -> int:
    from .telegram_bot import run_telegram_bot

    server = _build_server(public_dir, host, port)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    print(f"Serving {public_dir.resolve()} at {_build_public_base_url(host, port)}/")
    print("Starting Telegram bot.")
    try:
        run_telegram_bot(agent)
    finally:
        server.shutdown()
        server.server_close()
        server_thread.join(timeout=2)
    return 0


def _build_server(directory: Path, host: str, port: int) -> ThreadingHTTPServer:
    directory.mkdir(parents=True, exist_ok=True)
    handler = partial(SimpleHTTPRequestHandler, directory=str(directory))
    return ThreadingHTTPServer((host, port), handler)


def _build_public_base_url(host: str, port: int) -> str:
    return f"http://{host}:{port}"


def _find_available_port(host: str, preferred_port: int, attempts: int = 20) -> int:
    for offset in range(attempts):
        candidate = preferred_port + offset
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind((host, candidate))
            except OSError:
                continue
        return candidate
    raise OSError(f"Could not find a free port starting at {preferred_port}.")


if __name__ == "__main__":
    raise SystemExit(main())
