from __future__ import annotations

import sys
import uuid
from datetime import datetime, timezone
from typing import Callable

from .config import AgentConfig
from .memory import ExecutionMemory
from .models import PipelineResult
from .tools import (
    DemoLLMProvider,
    create_document,
    extract_input,
    normalize_bundle_for_portuguese,
    translate_bundle_to_portuguese,
    translate_source_to_portuguese,
    upload_document,
)


class ContentPipelineAgent:
    """Autonomous content pipeline with tool use, evaluation, and improvement."""

    def __init__(
        self,
        config: AgentConfig,
        llm: DemoLLMProvider | None = None,
        memory: ExecutionMemory | None = None,
    ) -> None:
        self.config = config
        self.llm = llm or DemoLLMProvider()
        self.memory = memory or ExecutionMemory(config.memory_path)

    def run(
        self,
        payload: str,
        status_callback: Callable[[str], None] | None = None,
    ) -> PipelineResult:
        run_id = self._new_run_id()

        self._notify(status_callback, "A analisar o input recebido.")
        source = extract_input(payload)

        source_label = "link" if source.source_type == "link" else "texto"
        self._notify(status_callback, f"Input identificado como {source_label}.")
        if source.language == "english":
            self._notify(
                status_callback,
                "Fonte em ingles detetada. Vou preparar a versao final em portugues.",
            )
            source = translate_source_to_portuguese(source)

        self._notify(status_callback, "A gerar as varias versoes de conteudo.")
        content = self.llm.generate_content(source, self.config.branding)
        if source.language in {"english", "portuguese"}:
            content = translate_bundle_to_portuguese(content)
            content = normalize_bundle_for_portuguese(content, self.config.branding)

        self._notify(status_callback, "A avaliar qualidade e alinhamento com o branding.")
        evaluation = self.llm.evaluate_content(content, self.config.branding)

        iterations = 0
        while (
            not evaluation.passed(self.config.quality_threshold)
            and iterations < self.config.max_improvement_rounds
        ):
            self._notify(status_callback, "A melhorar o conteudo com base na avaliacao.")
            content = self.llm.improve_content(
                content,
                evaluation,
                self.config.branding,
                source=source,
            )
            if source.language in {"english", "portuguese"}:
                content = translate_bundle_to_portuguese(content)
                content = normalize_bundle_for_portuguese(content, self.config.branding)
            self._notify(status_callback, "A reavaliar depois das melhorias.")
            evaluation = self.llm.evaluate_content(content, self.config.branding)
            iterations += 1

        self._notify(status_callback, "A criar o documento final.")
        document = create_document(
            content=content,
            evaluation=evaluation,
            output_dir=self.config.generated_dir,
            run_id=run_id,
            title_hint=source.title,
            summary_hint=source.summary,
            prefer_title_hint=True,
        )

        self._notify(status_callback, "A preparar o ficheiro para entrega.")
        upload = upload_document(
            document.path,
            public_dir=self.config.public_dir,
            public_base_url=self.config.public_base_url,
        )

        result = PipelineResult(
            run_id=run_id,
            source=source,
            content=content,
            evaluation=evaluation,
            document=document,
            upload=upload,
            iterations=iterations,
        )
        self._remember(result)
        self._notify(status_callback, "Concluido. Vou enviar o PDF.")
        return result

    def run_forever(self) -> None:
        print("Agent: Content Pipeline loop started. Press Ctrl+C to stop.")
        print("Paste one input per line. Use a link or article text.")
        while True:
            try:
                payload = input("> ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nStopping agent loop.")
                return

            if not payload:
                continue
            result = self.run(payload)
            print(f"Score: {result.evaluation.overall}/10")
            print(f"Improvement rounds: {result.iterations}")
            print(f"Document: {result.upload.url}")
            sys.stdout.flush()

    def _remember(self, result: PipelineResult) -> None:
        self.memory.log(
            {
                "run_id": result.run_id,
                "source_type": result.source.source_type,
                "input_preview": result.source.raw_input[:240],
                "title": result.source.title,
                "score": result.evaluation.overall,
                "iterations": result.iterations,
                "document_path": str(result.document.path),
                "public_url": result.upload.url,
            }
        )

    @staticmethod
    def _notify(
        callback: Callable[[str], None] | None,
        message: str,
    ) -> None:
        if callback:
            callback(message)

    @staticmethod
    def _new_run_id() -> str:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        suffix = uuid.uuid4().hex[:8]
        return f"content-pipeline-{timestamp}-{suffix}"
