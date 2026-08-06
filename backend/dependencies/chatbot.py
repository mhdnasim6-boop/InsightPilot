"""Chatbot providers: classifier, context builder, validator, response builder, chat service."""

from functools import lru_cache

from fastapi import Depends

from backend.ai.prompts.manager import PromptManager
from backend.chatbot.response.builder import ResponseBuilder
from backend.chatbot.retrieval.classifier import QuestionClassifier
from backend.chatbot.retrieval.context_builder import ContextBuilder
from backend.chatbot.services.chat_service import ChatService
from backend.chatbot.validation.answerability import ContextValidator
from backend.dependencies.ai import get_ai_service, get_prompt_manager
from backend.dependencies.memory import get_memory_service
from backend.memory.services.memory_service import MemoryService
from backend.services.ai_service import AIService


@lru_cache
def get_question_classifier() -> QuestionClassifier:
    """Return the process-wide QuestionClassifier singleton (stateless, safe to share)."""
    return QuestionClassifier()


@lru_cache
def get_context_builder() -> ContextBuilder:
    """Return the process-wide ContextBuilder singleton (stateless, safe to share)."""
    return ContextBuilder()


@lru_cache
def get_context_validator() -> ContextValidator:
    """Return the process-wide ContextValidator singleton (stateless, safe to share)."""
    return ContextValidator()


@lru_cache
def get_response_builder() -> ResponseBuilder:
    """Return the process-wide ResponseBuilder singleton (stateless, safe to share)."""
    return ResponseBuilder()


def get_chat_service(
    ai_service: AIService = Depends(get_ai_service),
    prompt_manager: PromptManager = Depends(get_prompt_manager),
    classifier: QuestionClassifier = Depends(get_question_classifier),
    context_builder: ContextBuilder = Depends(get_context_builder),
    validator: ContextValidator = Depends(get_context_validator),
    response_builder: ResponseBuilder = Depends(get_response_builder),
    memory_service: MemoryService = Depends(get_memory_service),
) -> ChatService:
    """Provide the ChatService — the only object that should be used to answer chat questions."""
    return ChatService(
        ai_service, prompt_manager, classifier, context_builder, validator, response_builder, memory_service
    )
