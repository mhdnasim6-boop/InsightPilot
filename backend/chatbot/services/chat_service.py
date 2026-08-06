"""Conversational BI entry point.

The only object anything should use to answer a chat question — never
the classifier, context builder, validator, prompts, or response builder
directly. Mirrors ``PlannerService``'s role and shape: understands one
request and produces one structured result, calling ``AIService`` for
natural-language generation and nothing else for computation.

``memory_service`` is an optional collaborator, mirroring every other
optional-collaborator pattern in this codebase
(``approval_service``/``observability_service``). When present,
``ask()`` remembers each turn as a CONVERSATION ``MemoryItem`` (question,
answer, referenced datasets/KPIs, suggested follow-ups) and injects an
extractive summary of earlier remembered turns into the prompt —
``ChatContext.conversation_history`` (the frontend's own in-session
transcript) is unchanged and still the primary source for what's *in*
this session; memory only ever adds *earlier* context beyond that.
"""

from backend.ai.models.requests import AIRequest
from backend.ai.prompts.manager import PromptManager
from backend.chatbot.context.models import ChatContext
from backend.chatbot.prompts.templates import (
    prompt_name_for_intent,
    register_chat_prompts,
    render_conversation_history,
    summarize_dataset,
    system_prompt_for_intent,
)
from backend.chatbot.response.builder import ResponseBuilder
from backend.chatbot.response.models import ChatResponse
from backend.chatbot.retrieval.classifier import Intent, QuestionClassifier
from backend.chatbot.retrieval.context_builder import ContextBuilder, RetrievedContext
from backend.chatbot.validation.answerability import ContextValidator
from backend.memory.models.memory_query import MemoryQuery
from backend.memory.models.memory_reference import MemoryReference
from backend.memory.models.memory_scope import MemoryScope
from backend.memory.models.memory_type import MemoryType
from backend.memory.services.memory_service import MemoryService
from backend.services.ai_service import AIService


class ChatService:
    """Answers one question about a dataset's analysis/visualization/plan.

    Never analyzes raw data: every fact it can possibly cite already
    exists in ``context`` before ``ask()`` is ever called.
    """

    def __init__(
        self,
        ai_service: AIService,
        prompt_manager: PromptManager,
        classifier: QuestionClassifier | None = None,
        context_builder: ContextBuilder | None = None,
        validator: ContextValidator | None = None,
        response_builder: ResponseBuilder | None = None,
        memory_service: MemoryService | None = None,
    ) -> None:
        self._ai_service = ai_service
        self._prompt_manager = prompt_manager
        self._classifier = classifier or QuestionClassifier()
        self._context_builder = context_builder or ContextBuilder()
        self._validator = validator or ContextValidator()
        self._response_builder = response_builder or ResponseBuilder()
        self._memory_service = memory_service
        register_chat_prompts(self._prompt_manager)

    async def ask(self, question: str, context: ChatContext) -> ChatResponse:
        """Classify, validate, and (if grounded) answer ``question``.

        Returns a refusal response — no AI call made at all — when the
        classified intent's required data doesn't exist in ``context``.
        """
        intent = self._classifier.classify(question)
        answerability = self._validator.check(context, intent)

        if not answerability.answerable:
            return self._response_builder.build_refusal(intent, answerability)

        retrieved = self._context_builder.build(context, intent)
        user_prompt = self._build_prompt(question, context, intent, retrieved)
        system_prompt = system_prompt_for_intent(intent)
        ai_response = await self._ai_service.generate(AIRequest(system_prompt=system_prompt, prompt=user_prompt))

        response = self._response_builder.build(intent, ai_response, retrieved, answerability)
        self._remember_turn(question, response, context)
        self._remember_preferences(context)
        return response

    def _build_prompt(self, question: str, context: ChatContext, intent: Intent, retrieved: RetrievedContext) -> str:
        prompt_name = prompt_name_for_intent(intent)
        return self._prompt_manager.get(
            prompt_name,
            dataset_summary=summarize_dataset(context.selected_dataset),
            facts=retrieved.facts_text,
            conversation_history=self._render_conversation_with_memory(context),
            question=question,
        )

    def _render_conversation_with_memory(self, context: ChatContext) -> str:
        rendered = render_conversation_history(context.conversation_history)
        memory_summary = self._recall_conversation_summary(context.session_id)
        if memory_summary is None:
            return rendered
        return f"{rendered}\n\nEarlier remembered context: {memory_summary}"

    def _recall_conversation_summary(self, session_id: str) -> str | None:
        if self._memory_service is None:
            return None
        query = MemoryQuery(memory_type=MemoryType.CONVERSATION, session_id=session_id, top_k=10)
        return self._memory_service.summarize(query)

    def _remember_turn(self, question: str, response: ChatResponse, context: ChatContext) -> None:
        if self._memory_service is None:
            return
        self._memory_service.remember(
            title=f"Chat: {question[:60]}",
            summary=response.answer[:300],
            memory_type=MemoryType.CONVERSATION,
            scope=MemoryScope.SESSION,
            content={
                "question": question,
                "answer": response.answer,
                "follow_up_questions": response.suggested_follow_up_questions,
            },
            tags=[response.intent.value, *response.referenced_kpis],
            references=[
                MemoryReference(reference_type="dataset", reference_id=dataset_id)
                for dataset_id in response.referenced_datasets
            ],
            metadata={"session_id": context.session_id},
        )

    def _remember_preferences(self, context: ChatContext) -> None:
        if self._memory_service is None or not context.user_preferences:
            return
        self._memory_service.remember(
            title="User preferences",
            summary="Preferences captured during chat.",
            memory_type=MemoryType.USER_PREFERENCE,
            scope=MemoryScope.SESSION,
            content=dict(context.user_preferences),
            metadata={"session_id": context.session_id},
        )
