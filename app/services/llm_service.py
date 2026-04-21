from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.services.rag_service import RetrievedChunk


@dataclass
class LLMGenerationResult:
    provider: str
    model: str
    raw_text: str
    parsed_json: dict[str, Any]
    is_fallback: bool = False


class LLMService:
    def __init__(self, db: Session | None = None):
        self.db = db
        self.settings = get_settings()

    def generate_delivery_plan(
        self,
        *,
        requirement_text: str,
        retrieved_chunks: list[RetrievedChunk],
        repo_context: list[str],
        provider: str,
        model_name: str | None,
    ) -> dict[str, Any]:
        prompt = self._build_prompt(requirement_text, retrieved_chunks, repo_context)
        result = self.generate_pipeline_plan(provider=provider, model_name=model_name, prompt=prompt)
        payload = result.parsed_json
        return {
            'summary': payload.get('summary'),
            'plan': payload.get('implementation_plan', []),
            'risks': payload.get('risks', []),
            'acceptance_criteria': payload.get('acceptance_criteria', []),
            'final_output': payload.get('final_output'),
            'provider': result.provider,
            'model_name': result.model,
            'is_fallback': result.is_fallback,
        }

    def generate_pipeline_plan(self, *, provider: str, model_name: str | None, prompt: str) -> LLMGenerationResult:
        provider = (provider or 'openai').lower().strip()
        if provider == 'openai':
            return self._call_openai(model_name or self.settings.openai_model, prompt)
        if provider == 'gemini':
            return self._call_gemini(model_name or self.settings.gemini_model, prompt)
        raise HTTPException(status_code=400, detail='Unsupported provider. Choose openai or gemini.')

    def _call_openai(self, model: str, prompt: str) -> LLMGenerationResult:
        if not self.settings.openai_api_key:
            return self._fallback('openai', model, 'OPENAI_API_KEY is not configured.')
        try:
            from openai import OpenAI

            client = OpenAI(api_key=self.settings.openai_api_key, timeout=self.settings.llm_request_timeout_seconds)
            response = client.responses.create(
                model=model,
                input=prompt,
                text={
                    'format': {
                        'type': 'json_schema',
                        'name': 'pipeline_run',
                        'schema': self._response_schema(),
                        'strict': True,
                    }
                },
            )
            text = response.output_text
            parsed = json.loads(text)
            return LLMGenerationResult(provider='openai', model=model, raw_text=text, parsed_json=parsed)
        except Exception as exc:  # pragma: no cover
            if self.settings.allow_provider_fallback_stub:
                return self._fallback('openai', model, f'OpenAI call failed: {exc}')
            raise HTTPException(status_code=502, detail=f'OpenAI call failed: {exc}') from exc

    def _call_gemini(self, model: str, prompt: str) -> LLMGenerationResult:
        if not self.settings.gemini_api_key:
            return self._fallback('gemini', model, 'GEMINI_API_KEY is not configured.')
        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=self.settings.gemini_api_key)
            response = client.models.generate_content(
                model=model,
                contents=prompt,
                config=types.GenerateContentConfig(response_mime_type='application/json', response_schema=self._response_schema()),
            )
            text = response.text or '{}'
            parsed = json.loads(text)
            return LLMGenerationResult(provider='gemini', model=model, raw_text=text, parsed_json=parsed)
        except Exception as exc:  # pragma: no cover
            if self.settings.allow_provider_fallback_stub:
                return self._fallback('gemini', model, f'Gemini call failed: {exc}')
            raise HTTPException(status_code=502, detail=f'Gemini call failed: {exc}') from exc

    def _fallback(self, provider: str, model: str, reason: str) -> LLMGenerationResult:
        payload = {
            'summary': f'{provider.title()} fallback generated a release-ready implementation plan because the live provider was unavailable.',
            'implementation_plan': [
                'Validate Jira acceptance criteria and repository health before sprint kickoff.',
                'Split the work into backend integration, frontend observability, and CI/CD rollout tracks.',
                'Add staging validation, user authentication hardening, and deployment smoke tests.',
            ],
            'risks': ['External credentials missing or invalid.', 'Deployment environment variables may be incomplete.'],
            'acceptance_criteria': ['Pipeline launches from JSON, Jira, and live repo context.', 'CI passes on every push.', 'Dashboard exposes workflow telemetry and auth state.'],
            'final_output': f'Generated with fallback mode. Reason: {reason}',
        }
        return LLMGenerationResult(provider=provider, model=model, raw_text=json.dumps(payload), parsed_json=payload, is_fallback=True)

    @staticmethod
    def _build_prompt(requirement_text: str, retrieved_chunks: list[RetrievedChunk], repo_context: list[str]) -> str:
        evidence = '\n'.join(f'- {chunk.source}: {chunk.excerpt}' for chunk in retrieved_chunks[:4]) or '- No local evidence found.'
        repo = '\n'.join(f'- {item}' for item in repo_context[:6]) or '- No repo context provided.'
        return (
            'You are generating a delivery plan for an enterprise AI + DevOps platform. '\
            'Return strict JSON with summary, implementation_plan, risks, acceptance_criteria, and final_output.\n\n'
            f'Requirement:\n{requirement_text}\n\n'
            f'Local retrieval evidence:\n{evidence}\n\n'
            f'GitHub context:\n{repo}\n'
        )

    @staticmethod
    def _response_schema() -> dict[str, Any]:
        return {
            'type': 'object',
            'properties': {
                'summary': {'type': 'string'},
                'implementation_plan': {'type': 'array', 'items': {'type': 'string'}},
                'risks': {'type': 'array', 'items': {'type': 'string'}},
                'acceptance_criteria': {'type': 'array', 'items': {'type': 'string'}},
                'final_output': {'type': 'string'},
            },
            'required': ['summary', 'implementation_plan', 'risks', 'acceptance_criteria', 'final_output'],
            'additionalProperties': False,
        }
