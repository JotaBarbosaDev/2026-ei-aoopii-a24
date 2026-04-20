from __future__ import annotations

import sys
import uuid
from datetime import datetime, timezone

from .config import AgentConfig
from .memory import ExecutionMemory
from .models import PipelineResult
from .tools import (
    DemoLLMProvider,
    create_document,
    evaluate_content,
    extract_input,
    generate_content,
    improve_content,
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

    def run(self, payload: str) -> PipelineResult:
        run_id = self._new_run_id()

        source = extract_input(payload)
        content = generate_content(source, self.config.branding, self.llm)
        evaluation = evaluate_content(content, self.config.branding)

        iterations = 0
        while (
            not evaluation.passed(self.config.quality_threshold)
            and iterations < self.config.max_improvement_rounds
        ):
            content = improve_content(content, evaluation, self.config.branding)
            evaluation = evaluate_content(content, self.config.branding)
            iterations += 1

        document = create_document(
            content=content,
            evaluation=evaluation,
            output_dir=self.config.generated_dir,
            run_id=run_id,
        )
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
    def _new_run_id() -> str:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        suffix = uuid.uuid4().hex[:8]
        return f"content-pipeline-{timestamp}-{suffix}"
