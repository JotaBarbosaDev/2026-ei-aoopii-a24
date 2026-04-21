from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from content_pipeline.__main__ import _build_public_base_url, _find_available_port
from content_pipeline.agent import ContentPipelineAgent
from content_pipeline.config import AgentConfig
from content_pipeline.models import BrandingProfile, ContentBundle, EvaluationResult
from content_pipeline.telegram_bot import (
    build_help_message,
    build_result_caption,
    build_welcome_message,
)
from content_pipeline.tools import (
    create_document,
    evaluate_content,
    extract_input,
    generate_content,
    improve_content,
    normalize_bundle_for_portuguese,
    translate_bundle_to_portuguese,
)
from content_pipeline.tools.content_tools import resolve_output_language
from content_pipeline.tools.llm_provider import (
    OpenAICompatibleLLMProvider,
    _content_bundle_from_json,
    select_llm_provider,
)
from content_pipeline.tools.translation_tools import translate_source_to_portuguese


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
        self.assertEqual(source.language, "english")

    def test_content_generation_uses_distinct_formats(self) -> None:
        source = extract_input(SAMPLE_INPUT)
        content = generate_content(source, _branding())

        self.assertNotEqual(content.blog_post, content.linkedin_post)
        self.assertTrue(content.newsletter.startswith(("Subject:", "Assunto:")))
        self.assertGreaterEqual(len(content.twitter_thread), 4)
        self.assertTrue(all(len(tweet) <= 280 for tweet in content.twitter_thread))

    def test_improvement_increases_evaluation_score(self) -> None:
        source = extract_input(SAMPLE_INPUT)
        branding = _branding()
        content = generate_content(source, branding)
        first_score = evaluate_content(content, branding).overall

        improved = improve_content(content, evaluate_content(content, branding), branding, source=source)
        second_score = evaluate_content(improved, branding).overall

        self.assertGreater(second_score, first_score)

    def test_improvement_keeps_portuguese_when_source_is_english(self) -> None:
        source = extract_input(SAMPLE_INPUT)
        branding = _branding()
        content = generate_content(source, branding)

        improved = improve_content(content, evaluate_content(content, branding), branding, source=source)

        self.assertIn("Nota de branding:", improved.blog_post)
        self.assertIn("Proximo passo:", improved.blog_post)
        self.assertNotIn("Branding note:", improved.blog_post)
        self.assertIn("Agenda uma breve conversa estrategica com BrightWave Labs.", improved.blog_post)

        improved_twice = improve_content(
            improved,
            evaluate_content(improved, branding),
            branding,
            source=source,
        )
        self.assertEqual(improved_twice.blog_post.count("Nota de branding:"), 1)

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
            self.assertTrue(artifact.download_name and artifact.download_name.endswith(".pdf"))

    def test_document_name_prefers_content_topic(self) -> None:
        content = ContentBundle(
            blog_post=(
                "# Missao Artemis II rumo a Lua\n\n"
                "A NASA confirmou uma manobra critica e o documento final resume o tema em portugues."
            ),
            linkedin_post="Resumo curto",
            twitter_thread=["1/2 Resumo", "2/2 Fecho"],
            newsletter="Assunto: Missao Artemis II",
        )
        evaluation = EvaluationResult(clarity=9.0, engagement=8.5, branding=8.8)

        with tempfile.TemporaryDirectory() as tmp:
            artifact = create_document(
                content,
                evaluation,
                Path(tmp),
                "test-run",
                title_hint="Titulo generico",
            )

        self.assertEqual(artifact.download_name, "missao-artemis-ii-rumo-a-lua.pdf")

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

            with patch("content_pipeline.agent.translate_source_to_portuguese", side_effect=lambda value: value):
                result = agent.run(SAMPLE_INPUT)

            self.assertGreaterEqual(result.evaluation.overall, 7.5)
            self.assertGreaterEqual(result.iterations, 1)
            self.assertTrue(result.document.path.exists())
            self.assertTrue(result.upload.public_path.exists())
            self.assertEqual(agent.memory.recent(1)[0]["run_id"], result.run_id)

    def test_agent_reports_progress_messages(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = AgentConfig(
                branding=_branding(),
                generated_dir=root / "generated",
                public_dir=root / "public",
                memory_path=root / "memory" / "executions.jsonl",
            )
            agent = ContentPipelineAgent(config)
            updates: list[str] = []

            with patch("content_pipeline.agent.translate_source_to_portuguese", side_effect=lambda value: value):
                agent.run(SAMPLE_INPUT, status_callback=updates.append)

        self.assertGreaterEqual(len(updates), 6)
        self.assertEqual(updates[0], "A analisar o input recebido.")
        self.assertEqual(updates[-1], "Concluido. Vou enviar o PDF.")

    def test_select_llm_provider_supports_groq(self) -> None:
        with patch("content_pipeline.tools.llm_provider.load_local_env"):
            with patch.dict(
                os.environ,
                {
                    "LLM_PROVIDER": "groq",
                    "GROQ_API_KEY": "test-key",
                },
                clear=True,
            ):
                provider = select_llm_provider()

        self.assertIsInstance(provider, OpenAICompatibleLLMProvider)
        self.assertEqual(provider.base_url, "https://api.groq.com/openai/v1")
        self.assertEqual(provider.model, "llama-3.1-8b-instant")

    def test_openai_compatible_provider_falls_back_on_llm_failure(self) -> None:
        provider = OpenAICompatibleLLMProvider(
            base_url="https://api.example.com/v1",
            api_key="test-key",
            model="test-model",
        )
        source = extract_input(SAMPLE_INPUT)

        with patch.object(provider, "_complete_json", side_effect=ValueError("rate limit")):
            content = provider.generate_content(source, _branding())
            evaluation = provider.evaluate_content(content, _branding())
            improved = provider.improve_content(content, evaluation, _branding(), source=source)

        self.assertTrue(content.blog_post)
        self.assertGreaterEqual(evaluation.overall, 0)
        self.assertIn("Proximo passo:", improved.blog_post)

    def test_english_source_targets_portuguese_output(self) -> None:
        source = extract_input(SAMPLE_INPUT)
        self.assertEqual(resolve_output_language(source, _branding()), "Portuguese")

    def test_portuguese_source_also_targets_portuguese_output(self) -> None:
        source = extract_input("Dieta saudavel e importante para manter o bem-estar geral e prevenir doencas.")
        self.assertEqual(source.language, "portuguese")
        self.assertEqual(resolve_output_language(source, _branding()), "Portuguese")

    def test_portuguese_normalization_rewrites_known_english_branding_lines(self) -> None:
        content = ContentBundle(
            blog_post="Book a short strategy call with BrightWave Labs.",
            linkedin_post="BrightWave Labs takeaway: Book a short strategy call with BrightWave Labs.",
            twitter_thread=["Takeaway: Book a short strategy call with BrightWave Labs."],
            newsletter="Book a short strategy call with BrightWave Labs.",
        )

        normalized = normalize_bundle_for_portuguese(content, _branding())

        self.assertIn("Agenda uma breve conversa estrategica com BrightWave Labs.", normalized.blog_post)
        self.assertIn("Conclusao da BrightWave Labs:", normalized.linkedin_post)
        self.assertIn("Ponto-chave:", normalized.twitter_thread[0])

    def test_translation_tool_translates_english_source_fields(self) -> None:
        source = extract_input(SAMPLE_INPUT)

        class FakeTranslator:
            def __init__(self, source: str, target: str) -> None:
                self.source = source
                self.target = target

            def translate(self, text: str) -> str:
                return f"PT::{text}"

        with patch("content_pipeline.tools.translation_tools.GoogleTranslator", FakeTranslator):
            translated = translate_source_to_portuguese(source)

        self.assertTrue(translated.title.startswith("PT::"))
        self.assertTrue(translated.summary.startswith("PT::"))
        self.assertTrue(all(point.startswith("PT::") for point in translated.key_points))

    def test_bundle_translation_rewrites_english_content_to_portuguese(self) -> None:
        bundle = ContentBundle(
            blog_post="The Importance of a Healthy Diet",
            linkedin_post="Read the full article on the Portuguese Pharmacists' Order website.",
            twitter_thread=["Did you know that a healthy diet is essential?"],
            newsletter="Next step: Book a short strategy call with BrightWave Labs.",
        )

        class FakeTranslator:
            def __init__(self, source: str, target: str) -> None:
                self.source = source
                self.target = target

            def translate(self, text: str) -> str:
                return f"PT::{text}"

        with patch("content_pipeline.tools.translation_tools.GoogleTranslator", FakeTranslator):
            translated = translate_bundle_to_portuguese(bundle)

        self.assertTrue(translated.blog_post.startswith("PT::"))
        self.assertTrue(translated.linkedin_post.startswith("PT::"))
        self.assertTrue(translated.twitter_thread[0].startswith("PT::"))
        self.assertTrue(translated.newsletter.startswith("PT::"))

    def test_structured_llm_content_is_normalized_to_text(self) -> None:
        bundle = _content_bundle_from_json(
            {
                "blog_post": {
                    "title": "Missao Artemis II rumo a Lua",
                    "summary": "Resumo em portugues.",
                    "content": "Conteudo final organizado.",
                },
                "linkedin_post": {
                    "title": "Resumo curto",
                    "content": "Versao para LinkedIn.",
                },
                "twitter_thread": [
                    {"text": "Primeiro ponto"},
                    "Segundo ponto",
                ],
                "newsletter": {
                    "subject": "Assunto",
                    "content": "Versao newsletter.",
                },
            }
        )

        self.assertTrue(bundle.blog_post.startswith("# Missao Artemis II rumo a Lua"))
        self.assertIn("Conteudo final organizado.", bundle.blog_post)
        self.assertEqual(bundle.twitter_thread[0], "Primeiro ponto")
        self.assertEqual(bundle.twitter_thread[1], "Segundo ponto")
        self.assertIn("Versao newsletter.", bundle.newsletter)

    def test_telegram_caption_skips_local_file_url(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = AgentConfig(
                branding=_branding(),
                generated_dir=root / "generated",
                public_dir=root / "public",
                memory_path=root / "memory" / "executions.jsonl",
            )
            agent = ContentPipelineAgent(config)
            with patch("content_pipeline.agent.translate_source_to_portuguese", side_effect=lambda value: value):
                result = agent.run(SAMPLE_INPUT)

        caption = build_result_caption(result)

        self.assertIn("<b>✅ Documento gerado com sucesso</b>", caption)
        self.assertIn("📰 <b>Tema:</b>", caption)
        self.assertIn("📊 <b>Score de qualidade:</b>", caption)
        self.assertIn("🔁 <b>Melhorias automaticas:</b>", caption)
        self.assertIn("🌍 <b>Idioma:</b>", caption)
        self.assertNotIn("🔗 <b>Link:</b>", caption)

    def test_telegram_messages_explain_capabilities(self) -> None:
        welcome = build_welcome_message()
        help_text = build_help_message()

        self.assertIn("🤖", welcome)
        self.assertIn("/start", welcome)
        self.assertIn("/help", welcome)
        self.assertIn("texto ou link", welcome)
        self.assertIn("📘", help_text)
        self.assertIn("Inputs suportados agora", help_text)
        self.assertIn("audio, video e ficheiros", help_text.lower())

    def test_build_public_base_url(self) -> None:
        self.assertEqual(_build_public_base_url("127.0.0.1", 8000), "http://127.0.0.1:8000")

    def test_find_available_port_returns_requested_port_when_free(self) -> None:
        port = _find_available_port("127.0.0.1", 8765)
        self.assertEqual(port, 8765)


if __name__ == "__main__":
    unittest.main()
