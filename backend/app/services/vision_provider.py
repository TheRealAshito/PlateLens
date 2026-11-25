"""Adaptadores multimodais para análise visual de pratos (Gemini / Ollama / Mock)."""

from __future__ import annotations

import base64
import json
from typing import Protocol

import httpx
from pydantic import BaseModel, Field

from backend.app.schemas import ModelMode, Per100gSchema
from backend.app.services.settings_service import EffectiveAiConfig


class VisionNotConfiguredError(RuntimeError):
    """Lançada quando nenhuma API key/provedor de visão foi configurado ainda."""


class VisionProviderError(RuntimeError):
    """Lançada quando ocorre falha ao consultar o provedor de visão."""


class DetectedFoodItem(BaseModel):
    name: str = Field(min_length=1)
    search_query: str = Field(min_length=1)
    estimated_grams: float = Field(gt=0, le=3000)
    portion_label: str = Field(default="1 porção")
    confidence: float = Field(default=0.75, ge=0.0, le=1.0)
    fallback_per_100g: Per100gSchema


class VisionAnalysisResult(BaseModel):
    plate_summary: str
    overall_confidence: str = "medium"
    warnings: list[str] = Field(default_factory=list)
    items: list[DetectedFoodItem] = Field(min_length=1)
    provider_used: str = ""
    model_used: str = ""
    used_fallback_model: bool = False


GEMINI_RESPONSE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "plate_summary": {"type": "STRING"},
        "overall_confidence": {"type": "STRING", "enum": ["high", "medium", "low"]},
        "warnings": {"type": "ARRAY", "items": {"type": "STRING"}},
        "items": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "name": {"type": "STRING"},
                    "search_query": {"type": "STRING"},
                    "estimated_grams": {"type": "NUMBER"},
                    "portion_label": {"type": "STRING"},
                    "confidence": {"type": "NUMBER"},
                    "fallback_per_100g": {
                        "type": "OBJECT",
                        "properties": {
                            "kcal": {"type": "NUMBER"},
                            "protein_g": {"type": "NUMBER"},
                            "carbs_g": {"type": "NUMBER"},
                            "fat_g": {"type": "NUMBER"},
                            "fiber_g": {"type": "NUMBER"},
                        },
                        "required": ["kcal", "protein_g", "carbs_g", "fat_g", "fiber_g"],
                    },
                },
                "required": [
                    "name",
                    "search_query",
                    "estimated_grams",
                    "portion_label",
                    "confidence",
                    "fallback_per_100g",
                ],
            },
        },
    },
    "required": ["plate_summary", "overall_confidence", "warnings", "items"],
}


def build_plate_prompt(user_context: str = "", plate_size: str = "normal") -> str:
    context_line = f"Contexto informado pelo usuário: {user_context.strip()}." if user_context.strip() else "Sem contexto extra do usuário."
    return (
        "Você é um assistente especialista em análise visual de refeições brasileiras e tabela nutricional TACO.\n"
        "Analise a foto do prato e identifique cada alimento visível separadamente.\n"
        f"Tamanho de prato indicado: {plate_size}.\n"
        f"{context_line}\n\n"
        "Regras:\n"
        "1. Escreva 'name', 'search_query', 'portion_label', 'plate_summary' e 'warnings' em Português do Brasil.\n"
        "2. Em 'search_query', use termos simples da Tabela TACO (ex: 'arroz branco cozido', 'feijao carioca cozido', 'peito de frango grelhado').\n"
        "3. Estime 'estimated_grams' de forma realista para a porção visível no prato.\n"
        "4. Em 'warnings', alerte sobre possíveis calorias ocultas (óleo de preparo, azeite, manteiga, molho, açúcar).\n"
        "5. Preencha 'fallback_per_100g' com valores nutricionais plausíveis por 100g caso não haja match exato na TACO.\n"
        "Responda SOMENTE com JSON válido seguindo o schema solicitado."
    )


class VisionProvider(Protocol):
    async def analyze_plate(
        self,
        image_bytes: bytes,
        user_context: str = "",
        plate_size: str = "normal",
        model_mode: ModelMode = "precise",
    ) -> VisionAnalysisResult: ...


class GeminiVisionProvider:
    """Provedor Google AI Studio (Gemini) com fallback automático 429 para Flash-Lite."""

    API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"

    def __init__(
        self,
        api_key: str,
        primary_model: str,
        fallback_model: str,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.api_key = api_key
        self.primary_model = primary_model
        self.fallback_model = fallback_model
        self.transport = transport

    async def _call_model(self, model: str, image_bytes: bytes, prompt: str) -> dict:
        url = f"{self.API_BASE}/{model}:generateContent"
        b64_img = base64.b64encode(image_bytes).decode("ascii")
        body = {
            "contents": [
                {
                    "parts": [
                        {"text": prompt},
                        {"inline_data": {"mime_type": "image/jpeg", "data": b64_img}},
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.2,
                "responseMimeType": "application/json",
                "responseSchema": GEMINI_RESPONSE_SCHEMA,
            },
        }
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": self.api_key,
        }

        async with httpx.AsyncClient(timeout=45.0, transport=self.transport) as client:
            resp = await client.post(url, headers=headers, json=body)
        if resp.status_code == 429:
            raise _QuotaExceededError(f"Cota atingida no modelo {model}")
        if resp.status_code in (401, 403):
            raise VisionProviderError("Chave da Gemini API inválida ou sem permissão. Verifique em Configurações.")
        if resp.status_code >= 400:
            raise VisionProviderError(f"Erro na Gemini API ({resp.status_code}): {resp.text[:240]}")

        data = resp.json()
        try:
            text_payload = data["candidates"][0]["content"]["parts"][0]["text"]
            return json.loads(text_payload)
        except (KeyError, IndexError, json.JSONDecodeError) as exc:
            raise VisionProviderError("Resposta inesperada da Gemini API ao interpretar o prato.") from exc

    async def analyze_plate(
        self,
        image_bytes: bytes,
        user_context: str = "",
        plate_size: str = "normal",
        model_mode: ModelMode = "precise",
    ) -> VisionAnalysisResult:
        if not self.api_key:
            raise VisionNotConfiguredError("Configure sua chave da Gemini API para analisar fotos.")

        prompt = build_plate_prompt(user_context, plate_size)
        chosen_model = self.fallback_model if model_mode == "lite" else self.primary_model
        used_fallback = False

        try:
            raw_json = await self._call_model(chosen_model, image_bytes, prompt)
        except _QuotaExceededError:
            if chosen_model != self.fallback_model and self.fallback_model:
                chosen_model = self.fallback_model
                used_fallback = True
                raw_json = await self._call_model(chosen_model, image_bytes, prompt)
            else:
                raise VisionProviderError(
                    "Limite de requisições da Gemini API atingido no momento. Tente novamente em instantes ou registre manualmente."
                )

        result = VisionAnalysisResult.model_validate(raw_json)
        result.provider_used = "gemini"
        result.model_used = chosen_model
        result.used_fallback_model = used_fallback
        if used_fallback:
            result.warnings.append(
                f"Cota do modelo principal atingida; análise realizada automaticamente com {chosen_model}."
            )
        return result


class OllamaVisionProvider:
    """Provedor opcional para servidor Ollama rodando em máquina da rede local."""

    def __init__(self, base_url: str, model: str, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.transport = transport

    async def analyze_plate(
        self,
        image_bytes: bytes,
        user_context: str = "",
        plate_size: str = "normal",
        model_mode: ModelMode = "precise",
    ) -> VisionAnalysisResult:
        if not self.base_url:
            raise VisionNotConfiguredError("Configure a URL do Ollama na rede local em Configurações.")

        b64_img = base64.b64encode(image_bytes).decode("ascii")
        prompt = (
            build_plate_prompt(user_context, plate_size)
            + "\nFormato JSON obrigatório: {plate_summary, overall_confidence, warnings, items: [{name, search_query, estimated_grams, portion_label, confidence, fallback_per_100g: {kcal, protein_g, carbs_g, fat_g, fiber_g}}]}"
        )
        payload = {
            "model": self.model,
            "stream": False,
            "format": "json",
            "messages": [{"role": "user", "content": prompt, "images": [b64_img]}],
        }
        async with httpx.AsyncClient(timeout=90.0, transport=self.transport) as client:
            resp = await client.post(f"{self.base_url}/api/chat", json=payload)
        if resp.status_code >= 400:
            raise VisionProviderError(f"Erro ao consultar Ollama ({resp.status_code}): {resp.text[:200]}")

        content = resp.json().get("message", {}).get("content", "")
        try:
            raw_json = json.loads(content)
        except json.JSONDecodeError as exc:
            raise VisionProviderError("O modelo local não retornou JSON válido.") from exc

        result = VisionAnalysisResult.model_validate(raw_json)
        result.provider_used = "ollama"
        result.model_used = self.model
        return result


class MockVisionProvider:
    """Provedor determinístico usado exclusivamente em testes automatizados."""

    async def analyze_plate(
        self,
        image_bytes: bytes,
        user_context: str = "",
        plate_size: str = "normal",
        model_mode: ModelMode = "precise",
    ) -> VisionAnalysisResult:
        model_name = "mock-lite" if model_mode == "lite" else "mock-precise"
        return VisionAnalysisResult(
            plate_summary="Prato feito brasileiro com arroz, feijão e frango grelhado",
            overall_confidence="high",
            warnings=["Estimativa visual: considere incluir azeite ou molhos adicionados."],
            provider_used="mock",
            model_used=model_name,
            items=[
                DetectedFoodItem(
                    name="Arroz branco cozido",
                    search_query="arroz branco cozido",
                    estimated_grams=150.0,
                    portion_label="6 colheres de sopa",
                    confidence=0.9,
                    fallback_per_100g=Per100gSchema(kcal=128, protein_g=2.5, carbs_g=28.1, fat_g=0.2, fiber_g=1.6),
                ),
                DetectedFoodItem(
                    name="Feijão carioca cozido",
                    search_query="feijao carioca cozido",
                    estimated_grams=100.0,
                    portion_label="1 concha média",
                    confidence=0.85,
                    fallback_per_100g=Per100gSchema(kcal=76, protein_g=4.8, carbs_g=13.6, fat_g=0.5, fiber_g=8.5),
                ),
                DetectedFoodItem(
                    name="Peito de frango grelhado",
                    search_query="peito de frango grelhado",
                    estimated_grams=120.0,
                    portion_label="1 filé médio",
                    confidence=0.88,
                    fallback_per_100g=Per100gSchema(kcal=159, protein_g=32.0, carbs_g=0.0, fat_g=2.5, fiber_g=0.0),
                ),
            ],
        )


class _QuotaExceededError(Exception):
    pass


def build_vision_provider(cfg: EffectiveAiConfig) -> VisionProvider:
    """Constrói o provedor de visão conforme configuração efetiva."""
    if cfg.vision_provider == "gemini":
        if not cfg.gemini_api_key:
            raise VisionNotConfiguredError(
                "Nenhuma chave da Gemini API configurada. Informe sua chave para analisar fotos."
            )
        return GeminiVisionProvider(
            api_key=cfg.gemini_api_key,
            primary_model=cfg.gemini_model,
            fallback_model=cfg.gemini_fallback_model,
        )
    if cfg.vision_provider == "ollama":
        if not cfg.ollama_base_url:
            raise VisionNotConfiguredError("Configure o endereço do Ollama em Configurações.")
        return OllamaVisionProvider(base_url=cfg.ollama_base_url, model=cfg.ollama_model)
    if cfg.vision_provider == "mock":
        return MockVisionProvider()
    raise VisionNotConfiguredError("Análise por IA desativada. Use o registro manual ou ative um provedor em Configurações.")


async def test_gemini_api_key(api_key: str) -> tuple[bool, str]:
    """Valida a chave Gemini consultando a listagem gratuita de modelos."""
    if not api_key.strip():
        return False, "Informe uma chave de API."
    url = "https://generativelanguage.googleapis.com/v1beta/models"
    try:
        async with httpx.AsyncClient(timeout=12.0) as client:
            resp = await client.get(url, headers={"x-goog-api-key": api_key.strip()})
        if resp.status_code == 200:
            return True, "Chave validada com sucesso no Google AI Studio!"
        if resp.status_code in (400, 401, 403):
            return False, "Chave inválida ou sem autorização."
        return False, f"Google AI Studio retornou status {resp.status_code}."
    except httpx.HTTPError as exc:
        return False, f"Falha de rede ao validar chave: {exc}"
