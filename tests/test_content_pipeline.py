from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from content_pipeline.agent import ContentPipelineAgent
from content_pipeline.config import AgentConfig
from content_pipeline.models import BrandingProfile
from content_pipeline.tools import (
    create_document,
    evaluate_content,
    extract_input,
    generate_content,
    improve_content,
)


SAMPLE_INPUT = (
    "AI adoption is changing how marketing teams turn research into campaign assets. "
    "Instead of producing one long article and manually adapting it for every channel, "
    "companies are now using agent systems to summarize inputs, preserve brand voice, "
    "create platform-specific copy, review quality, and publish packaged outputs. "
    "The biggest challenge is not model training. It is orchestration: connecting input "
    "capture, content generation, evaluation, document creation, and distribution into "
    "one reliable workflow."
)


def _branding() -> BrandingProfile:
    return BrandingProfile(
        company_name="BrightWave Labs",
        audience="marketing and product teams",
        voice="clear, practical, and confident",
        tone_keywords=["clear", "practical", "confident", "human"],
        forbidden_phrases=["revolutionary", "game changer", "synergy"],
        call_to_action="Book a short strategy call with BrightWave Labs.",
    )


class ContentPipelineTests(unittest.TestCase):
    def test_extract_input_turns_text_into_source_content(self) -> None:
        source = extract_input(SAMPLE_INPUT)

        self.assertEqual(source.source_type, "text")
        self.assertTrue(source.summary)
        self.assertGreaterEqual(len(source.key_points), 1)

    def test_content_generation_uses_distinct_formats(self) -> None:
        source = extract_input(SAMPLE_INPUT)
        content = generate_content(source, _branding())

        self.assertNotEqual(content.blog_post, content.linkedin_post)
        self.assertTrue(content.newsletter.startswith("Subject:"))
        self.assertGreaterEqual(len(content.twitter_thread), 4)
        self.assertTrue(all(len(tweet) <= 280 for tweet in content.twitter_thread))

    def test_improvement_increases_evaluation_score(self) -> None:
        source = extract_input(SAMPLE_INPUT)
        branding = _branding()
        content = generate_content(source, branding)
        first_score = evaluate_content(content, branding).overall

        improved = improve_content(content, evaluate_content(content, branding), branding)
        second_score = evaluate_content(improved, branding).overall

        self.assertGreater(second_score, first_score)

    def test_document_creation_writes_markdown_and_pdf(self) -> None:
        source = extract_input(SAMPLE_INPUT)
        branding = _branding()
        content = generate_content(source, branding)
        evaluation = evaluate_content(content, branding)

        with tempfile.TemporaryDirectory() as tmp:
            artifact = create_document(content, evaluation, Path(tmp), "test-run")

            self.assertTrue(artifact.path.exists())
            self.assertTrue(artifact.markdown_path and artifact.markdown_path.exists())
            self.assertEqual(artifact.path.read_bytes()[:5], b"%PDF-")

    def test_agent_runs_full_pipeline_and_logs_memory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = AgentConfig(
                branding=_branding(),
                quality_threshold=9.0,
                max_improvement_rounds=2,
                generated_dir=root / "generated",
                public_dir=root / "public",
                memory_path=root / "memory" / "executions.jsonl",
            )
            agent = ContentPipelineAgent(config)

            result = agent.run(SAMPLE_INPUT)

            self.assertGreaterEqual(result.evaluation.overall, 9.0)
            self.assertGreaterEqual(result.iterations, 1)
            self.assertTrue(result.document.path.exists())
            self.assertTrue(result.upload.public_path.exists())
            self.assertEqual(agent.memory.recent(1)[0]["run_id"], result.run_id)


if __name__ == "__main__":
    unittest.main()
