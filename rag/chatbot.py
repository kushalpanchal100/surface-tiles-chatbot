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
        self.api_key = api_key if api_key is not None else settings.gemini_api_key
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

        clean_msg = message.strip()
        lower_msg = clean_msg.lower()
        words = lower_msg.split()

        # Ignore greetings, closings, and name queries from follow-up enrichment
        greetings_and_closings = {
            "hi", "hello", "hey", "good morning", "good afternoon", "good evening",
            "thanks", "thank you", "cheers", "bye", "goodbye", "ok", "okay"
        }
        name_queries = {
            "what is your name", "what's your name", "whats your name",
            "who are you", "what is your name?", "what's your name?",
            "whats your name?", "who are you?", "your name"
        }
        if (
            lower_msg in greetings_and_closings
            or lower_msg in name_queries
            or (len(words) <= 2 and any(g in lower_msg for g in greetings_and_closings))
            or any(nq in lower_msg for nq in ["what is your name", "what's your name", "who are you"])
        ):
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
                cue_words = content_str.split()[:12]
                context_cues.append(" ".join(cue_words))
            elif role_str in ("assistant", "model"):
                # Extract markdown product titles: [Product Name]
                links = re.findall(r"\[(.*?)\]", content_str)
                if links:
                    context_cues.extend(links[:2])

        if context_cues:
            follow_up_cues = [
                "they", "these", "those", "it", "them", "both", "all",
                "sample", "samples", "size", "sizes", "slip", "price",
                "cost", "delivery", "stock", "outdoor", "indoor", "wall", "floor",
                "which", "what", "how much", "how many", "colours", "colors", "finish"
            ]
            is_explicit_follow_up = any(cue in words or cue in lower_msg for cue in follow_up_cues)
            is_short_refinement = len(words) <= 5 and any(w.endswith("?") or w in ["in", "with", "for", "more", "other"] for w in words)

            if is_explicit_follow_up or is_short_refinement:
                seen = set()
                clean_cues = []
                for c in context_cues:
                    if c.lower() not in seen:
                        seen.add(c.lower())
                        clean_cues.append(c)
                recent_context = " ".join(clean_cues[-2:])
                return f"{clean_msg} {recent_context}".strip()

        return clean_msg

    def _check_fast_path(self, message: str) -> Optional[str]:
        """Detect standard conversational greetings, identity questions, or closings.
        
        Returns an instant, pre-defined natural response in < 1ms, completely bypassing
        vector retrieval and remote LLM execution.
        """
        clean_msg = (message or "").strip().lower()
        clean_msg_nopunct = re.sub(r"[!?,.]+$", "", clean_msg).strip()

        # 1. Name & identity inquiries
        name_queries = {
            "what is your name", "what's your name", "whats your name",
            "who are you", "tell me your name", "your name", "who are u"
        }
        if clean_msg_nopunct in name_queries or any(clean_msg_nopunct.startswith(nq) for nq in ["what is your name", "what's your name", "whats your name", "who are you"]):
            return "Hello! I'm Sophie, the AI assistant for Surfaces Tiles UK. How can I help you find the right tiles today?"

        # 2. Greetings
        greetings = {
            "hi", "hello", "hey", "good morning", "good afternoon", "good evening",
            "hello sophie", "hi sophie", "hey sophie", "greetings"
        }
        if clean_msg_nopunct in greetings or any(clean_msg_nopunct == g or clean_msg_nopunct.startswith(f"{g} ") for g in ["hi", "hello", "hey", "good morning", "good afternoon", "good evening"]):
            return "Hello! I'm Sophie from Surfaces Tiles UK. How can I help you find the right tiles today?"

        # 3. Closings & Gratitude
        closings = {
            "thanks", "thank you", "thank you so much", "thanks a lot", "thanks sophie",
            "thank you sophie", "cheers", "bye", "goodbye", "see you", "have a good day"
        }
        if clean_msg_nopunct in closings or any(clean_msg_nopunct.startswith(c) for c in ["thank you", "thanks", "cheers", "goodbye"]):
            return "You're very welcome! If you have any further questions about our tiles, delivery, or free samples, feel free to ask. Have a great day!"

        return None

    def answer_question(
        self,
        message: str,
        history: Optional[List[Any]] = None,
        category: Optional[str] = None,
        top_k: Optional[int] = None
    ) -> Dict[str, Any]:
        """Execute full RAG generation: retrieve website context -> call Gemini LLM -> return response."""
        # 0. Fast-path check for greetings, name inquiries, and pleasantries (< 5ms response)
        fast_answer = self._check_fast_path(message)
        if fast_answer:
            return {
                "answer": fast_answer,
                "sources": []
            }

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
            from google.genai import types
            for attempt in range(2):
                try:
                    response = self.client.models.generate_content(
                        model=self.model_name,
                        contents=prompt,
                        config=types.GenerateContentConfig(
                            system_instruction=SURFACES_TILES_SYSTEM_PROMPT,
                            temperature=0.3,
                            max_output_tokens=250,
                            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True)
                        )
                    )
                    answer = response.text if response and response.text else "I'm sorry, I couldn't find that information right now. Please reach out to our customer support team for help."
                    break
                except Exception as e:
                    err_str = str(e)
                    is_transient = "429" in err_str or "RESOURCE_EXHAUSTED" in err_str or "503" in err_str or "UNAVAILABLE" in err_str or "timeout" in err_str.lower()
                    if is_transient and attempt == 0:
                        logger.warning(f"Transient error calling Gemini API ({e}). Retrying once...")
                        import time
                        time.sleep(2.0)
                        continue

                    logger.error(f"Error calling Gemini API: {e}")
                    # Provide grounded fallback from retrieved context if available
                    if sources:
                        top_source = sources[0]
                        ctype = (top_source.get("content_type") or "").lower()
                        if ctype == "product":
                            price_str = f" — {top_source['price']}" if top_source.get('price') else ""
                            size_str = f" — {top_source['size']}" if top_source.get('size') else ""
                            answer = (
                                f"Here is the best matching option:\n\n"
                                f"1. **[{top_source['title']}]({top_source['url']})**{price_str}{size_str}\n\n"
                                f"Would you like me to recommend the best one for your room?"
                            )
                        else:
                            answer = (
                                f"You can find detailed information on our website here:\n\n"
                                f"- **[{top_source['title']}]({top_source['url']})**\n\n"
                                f"Please feel free to ask if you need further help!"
                            )
                    else:
                        lower_m = message.strip().lower()
                        if any(nq in lower_m for nq in ["what is your name", "what's your name", "whats your name", "who are you", "your name"]):
                            answer = "Hello! I'm Sophie, the AI assistant for Surfaces Tiles UK. How can I help you find the right tiles today?"
                        elif any(lower_m == g or lower_m.startswith(f"{g} ") or lower_m.startswith(f"{g}!") or lower_m.startswith(f"{g},") for g in ["hi", "hello", "hey", "good morning", "good afternoon", "good evening"]):
                            answer = "Hello! I'm Sophie from Surfaces Tiles UK. How can I help you today?"
                        else:
                            answer = "I'm sorry, I couldn't find that in our catalogue. Could you let me know the colour, size, or room you're looking to tile?"
                    break

        return {
            "answer": answer,
            "sources": sources
        }

    def stream_answer_question(
        self,
        message: str,
        history: Optional[List[Any]] = None,
        category: Optional[str] = None,
        top_k: Optional[int] = None
    ):
        """Streaming generator that yields chunks for Server-Sent Events (SSE).
        Yields:
            {"event": "sources", "sources": [...]}
            {"event": "token", "delta": "..."}
            {"event": "done", "answer": "..."}
        """
        # Fast-path check
        fast_answer = self._check_fast_path(message)
        if fast_answer:
            yield {"event": "sources", "sources": []}
            yield {"event": "token", "delta": fast_answer}
            yield {"event": "done", "answer": fast_answer}
            return

        max_hist = getattr(settings, "max_chat_history", 10)
        active_history = history[-max_hist:] if history else []

        retrieval_query = self._build_retrieval_query(message, active_history)
        retrieval_result = self.retriever.retrieve(
            query=retrieval_query,
            top_k=top_k,
            category_filter=category
        )
        context = retrieval_result.get("context", "")
        sources = retrieval_result.get("sources", [])

        yield {"event": "sources", "sources": sources}

        prompt = build_rag_prompt(user_question=message, context=context, history=active_history)

        if self.mock_mode or not self.client:
            answer = self._generate_mock_response(message, retrieval_result, active_history)
            yield {"event": "token", "delta": answer}
            yield {"event": "done", "answer": answer}
            return

        from google.genai import types
        accumulated_text = []
        try:
            stream = self.client.models.generate_content_stream(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=SURFACES_TILES_SYSTEM_PROMPT,
                    temperature=0.3,
                    max_output_tokens=250,
                    automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True)
                )
            )
            for chunk in stream:
                if chunk and chunk.text:
                    accumulated_text.append(chunk.text)
                    yield {"event": "token", "delta": chunk.text}

            full_answer = "".join(accumulated_text)
            yield {"event": "done", "answer": full_answer}
        except Exception as e:
            logger.error(f"Error streaming from Gemini API: {e}")
            fallback = "I'm sorry, I couldn't find that information right now. Please reach out to our customer support team for help."
            yield {"event": "token", "delta": fallback}
            yield {"event": "done", "answer": fallback}

    def _generate_mock_response(
        self,
        message: str,
        retrieval_result: Dict[str, Any],
        history: Optional[List[Any]] = None
    ) -> str:
        """Generate a grounded mock response when running in demo/offline mode."""
        sources = retrieval_result.get("sources", [])

        lower_msg = (message or "").strip().lower()

        # Handle direct name inquiries and greetings in mock/offline mode
        if any(nq in lower_msg for nq in ["what is your name", "what's your name", "whats your name", "who are you", "your name"]):
            return "Hello! I'm Sophie, the AI assistant for Surfaces Tiles UK. How can I help you find the right tiles today?"
        if any(lower_msg == g or lower_msg.startswith(f"{g} ") or lower_msg.startswith(f"{g}!") or lower_msg.startswith(f"{g},") for g in ["hi", "hello", "hey", "good morning", "good afternoon", "good evening"]):
            return "Hello! I'm Sophie from Surfaces Tiles UK. How can I help you today?"

        if not sources:
            if history:
                return (
                    "I don't have that specific item in our online catalogue, but our team can help source it. "
                    "Would you like to explore similar styles or contact our sales team directly?"
                )
            return (
                "I'm sorry, I couldn't find matching tiles in our online catalogue. "
                "Could you tell me what room or colour you are looking for so I can suggest the best options?"
            )

        # Extract top 2-3 matching items
        items = []
        has_products = False
        for s in sources[:3]:
            title = s.get("title", "Product")
            url = s.get("url", "")
            ctype = (s.get("content_type") or "").lower()
            if ctype == "product":
                has_products = True
                price = f" — {s['price']}" if s.get("price") else ""
                size = f" — {s['size']}" if s.get("size") else ""
                items.append(f"{len(items) + 1}. **[{title}]({url})**{price}{size}")
            else:
                items.append(f"- **[{title}]({url})**")

        if has_products:
            intro = "Here are the best matching options:" if not history else "Following on from our conversation, here are the best matching options:"
            closing = "Would you like me to recommend the best one for your room?"
        else:
            intro = "Here is the relevant information from our website:"
            closing = "Please let me know if you would like any further details or assistance!"

        return f"{intro}\n\n" + "\n".join(items) + f"\n\n{closing}"


