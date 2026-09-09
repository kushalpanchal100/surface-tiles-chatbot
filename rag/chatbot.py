import re
import logging
from typing import Dict, Any, Optional, List

from config.settings import settings
from rag.retriever import SurfacesRetriever
from rag.prompt import SURFACES_TILES_SYSTEM_PROMPT, build_rag_prompt

logger = logging.getLogger(__name__)


class SurfacesChatbot:
    """RAG-powered conversational assistant for Surfaces Tiles UK."""

    def __init__(
        self,
        retriever: Optional[SurfacesRetriever] = None,
        model_name: Optional[str] = None,
        api_key: Optional[str] = None
    ):
        self.retriever = retriever or SurfacesRetriever()
        self.model_name = model_name or settings.gemini_model
        self.api_key = api_key or settings.gemini_api_key
        self.client = None
        self.mock_mode = not bool(self.api_key and self.api_key != "your_gemini_api_key_here")

        if not self.mock_mode:
            try:
                from google import genai
                self.client = genai.Client(api_key=self.api_key)
                logger.info(f"Initialized Gemini LLM Client ({self.model_name})")
            except Exception as e:
                logger.warning(f"Failed to initialize Gemini Client ({e}). Running in mock mode.")
                self.mock_mode = True
        else:
            logger.info("Operating SurfacesChatbot in mock mode (no API key configured).")

    def _build_retrieval_query(self, message: str, history: Optional[List[Any]] = None) -> str:
        """
        If the current message appears to be a follow-up referring to prior items,
        enrich the retrieval query with recent customer or product context from history.
        """
        if not history:
            return message

        recent_turns = history[-4:]
        context_cues = []

        for msg in recent_turns:
            if isinstance(msg, dict):
                role = msg.get("role", "user")
                content = msg.get("content") or msg.get("message") or msg.get("text", "")
            elif hasattr(msg, "role") and hasattr(msg, "content"):
                role = getattr(msg, "role", "user")
                content = getattr(msg, "content", "")
            else:
                continue

            role_str = str(role).lower()
            content_str = str(content).strip()
            if not content_str:
                continue

            if role_str in ("user", "customer"):
                context_cues.append(content_str)
            elif role_str in ("assistant", "model"):
                # Extract any mentioned markdown product titles: [Product Name]
                links = re.findall(r"\[(.*?)\]", content_str)
                if links:
                    context_cues.extend(links[:2])

        if context_cues:
            lower_msg = message.lower()
            follow_up_cues = [
                "they", "these", "those", "it", "them", "both", "all",
                "sample", "samples", "size", "sizes", "slip", "price",
                "cost", "delivery", "stock", "outdoor", "indoor", "wall", "floor"
            ]
            words = lower_msg.split()
            # If the user asks a short question or uses follow-up pronouns
            if any(cue in words or cue in lower_msg for cue in follow_up_cues) or len(words) <= 7:
                recent_context = " ".join(context_cues[-2:])
                return f"{message} {recent_context}"

        return message

    def answer_question(
        self,
        message: str,
        history: Optional[List[Any]] = None,
        category: Optional[str] = None,
        top_k: Optional[int] = None
    ) -> Dict[str, Any]:
        """Execute full RAG generation: retrieve website context -> call Gemini LLM -> return response."""
        # Ensure history is clamped to max configured limit (default: 10)
        max_hist = getattr(settings, "max_chat_history", 10)
        active_history = history[-max_hist:] if history else []

        # 1. Retrieve relevant website context (contextualized if follow-up)
        retrieval_query = self._build_retrieval_query(message, active_history)
        retrieval_result = self.retriever.retrieve(
            query=retrieval_query,
            top_k=top_k,
            category_filter=category
        )
        context = retrieval_result.get("context", "")
        sources = retrieval_result.get("sources", [])

        # 2. Build prompt including up to 10 history messages
        prompt = build_rag_prompt(user_question=message, context=context, history=active_history)

        # 3. Generate response using Gemini
        if self.mock_mode or not self.client:
            answer = self._generate_mock_response(message, retrieval_result, active_history)
        else:
            try:
                from google.genai import types
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=SURFACES_TILES_SYSTEM_PROMPT,
                        temperature=0.3,
                        max_output_tokens=600,
                        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True)
                    )
                )
                answer = response.text if response and response.text else "I'm sorry, I couldn't find that information right now. Please reach out to our customer support team for help."
            except Exception as e:
                logger.error(f"Error calling Gemini API: {e}")
                # Provide grounded fallback from retrieved context if available
                if sources:
                    top_source = sources[0]
                    price_str = f" – {top_source['price']}" if top_source.get('price') else ""
                    answer = (
                        f"Here is a great option from our catalog:\n\n"
                        f"- **[{top_source['title']}]({top_source['url']})**{price_str}\n\n"
                        f"Would you like to know more about this tile or order a free sample?"
                    )
                else:
                    answer = "I'm sorry, I couldn't find that information on our website. Please reach out to our customer support team or visit surfacestiles.co.uk!"

        return {
            "answer": answer,
            "sources": sources
        }

    def _generate_mock_response(
        self,
        message: str,
        retrieval_result: Dict[str, Any],
        history: Optional[List[Any]] = None
    ) -> str:
        """Generate a grounded mock response when running in demo/offline mode."""
        sources = retrieval_result.get("sources", [])

        if not sources:
            if history:
                return (
                    "Thank you for following up! For specific custom specifications or items outside our online catalog, "
                    "our UK tile specialists would be delighted to help directly. Please reach out to contact@surfacestiles.co.uk."
                )
            return (
                "I'm sorry, I couldn't find any matching products or policies on our website. "
                "Please visit surfacestiles.co.uk or contact our support team for assistance!"
            )

        # Extract top 2-3 matching items
        items = []
        for s in sources[:3]:
            title = s.get("title", "Product")
            url = s.get("url", "")
            price = f" – {s['price']}" if s.get("price") else ""
            items.append(f"- **[{title}]({url})**{price}")

        intro = "Following on from our conversation, here are matching options:" if history else "Here are a few popular options that might suit your project:"

        return (
            f"{intro}\n\n"
            + "\n".join(items)
            + "\n\nWe offer free samples across our porcelain range so you can see the colour and texture at home. Would you like any extra details on these?"
        )


