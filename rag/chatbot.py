import re
import base64
import logging
from typing import Dict, Any, Optional, List

from config.settings import settings
from rag.retriever import SurfacesRetriever
from rag.prompt import SURFACES_TILES_SYSTEM_PROMPT, build_rag_prompt, WELCOME_MESSAGE
from rag.product_catalog import catalog

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

    def _parse_attachment_data(self, attachment: Any) -> tuple[Optional[bytes], str, str]:
        """Parse filename, mime_type, and raw bytes from attachment payload."""
        if not attachment:
            return None, "", ""

        if isinstance(attachment, dict):
            filename = attachment.get("filename") or "attachment"
            mime_type = attachment.get("mime_type") or ""
            raw_data = attachment.get("data") or ""
        else:
            filename = getattr(attachment, "filename", None) or "attachment"
            mime_type = getattr(attachment, "mime_type", None) or ""
            raw_data = getattr(attachment, "data", None) or ""

        if not raw_data:
            return None, filename, mime_type

        # Handle data URI: data:<mime_type>;base64,<data>
        if "," in raw_data and "base64" in raw_data.split(",", 1)[0]:
            header, encoded = raw_data.split(",", 1)
            if not mime_type and ":" in header and ";" in header:
                mime_type = header.split(":", 1)[1].split(";", 1)[0].strip()
        else:
            encoded = raw_data

        # Detect mime_type from filename extension if still missing
        if not mime_type and "." in filename:
            ext = filename.rsplit(".", 1)[-1].lower()
            ext_map = {
                "jpg": "image/jpeg",
                "jpeg": "image/jpeg",
                "png": "image/png",
                "webp": "image/webp",
                "gif": "image/gif",
                "heic": "image/heic",
                "pdf": "application/pdf",
                "txt": "text/plain",
                "csv": "text/csv"
            }
            mime_type = ext_map.get(ext, "application/octet-stream")

        try:
            data_bytes = base64.b64decode(encoded)
            return data_bytes, filename, mime_type
        except Exception as e:
            logger.warning(f"Failed to decode base64 attachment data: {e}")
            return None, filename, mime_type

    def _extract_visual_context(self, image_part: Any, user_message: str) -> str:
        """Analyze tile image with Gemini to extract visual properties and search keywords."""
        if self.mock_mode or not self.client:
            return "grey outdoor textured porcelain tile patio stone effect"

        try:
            from google.genai import types
            analysis_prompt = (
                "You are an expert tile specialist for Surfaces Tiles UK. "
                "Analyze this tile or surface image for product catalog matching. "
                "In 1-2 concise sentences, state the primary colour, pattern/veining, "
                "surface finish (matt, polished, textured, anti-slip), material (porcelain, ceramic, marble, wood effect SPC), "
                "and whether it is suitable for indoor walls/floors or outdoor patio paving slabs. "
                "End with 3-5 search keywords to search in a tile catalog."
            )
            resp = self.client.models.generate_content(
                model=self.model_name,
                contents=[analysis_prompt, image_part],
                config=types.GenerateContentConfig(
                    max_output_tokens=120,
                    temperature=0.2,
                    automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True)
                )
            )
            if resp and resp.text:
                return resp.text.strip()
        except Exception as e:
            logger.warning(f"Error extracting visual context from image: {e}")
        return ""


    def _build_retrieval_query(self, message: str, history: Optional[List[Any]] = None) -> str:
        """
        If the current message appears to be a follow-up referring to prior items,
        enrich the retrieval query with recent customer or product context from history.
        """
        clean_msg = (message or "").strip()
        if not clean_msg or not history:
            return clean_msg

        lower_msg = clean_msg.lower()
        words = lower_msg.split()

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

    def _is_general_info_or_policy_query(self, message: str) -> bool:
        """Check if message is an informational, store location, or policy question.
        
        Such questions must NOT display product cards or shopping carousels.
        """
        clean_msg = (message or "").lower().strip()
        if not clean_msg:
            return False

        # If user explicitly uses buy or show phrases, it is not purely informational
        has_buy_phrase = any(p in clean_msg for p in [
            "buy", "purchase", "order", "checkout", "add to cart", "add to basket",
            "how much is", "price of", "cost of"
        ])
        has_show_phrase = any(p in clean_msg for p in [
            "show tiles", "show me tiles", "browse tiles", "view tiles", "see tiles", "display tiles",
            "show outdoor", "show porcelain", "show marble", "show bathroom", "show floor", "show wall"
        ])
        if has_buy_phrase or has_show_phrase:
            return False

        info_indicators = [
            # Location, address & store
            "where are you", "where is", "where's", "location", "address", "showroom", "directions",
            "postcode", "based", "situated", "store located", "shop located", "find you", "visit you",
            "store address", "london store", "harrow", "shop address", "where can i visit",
            # Contact
            "phone", "telephone", "email", "contact", "call you", "reach you", "customer service",
            # Hours & opening
            "opening hours", "open hours", "what time do you open", "what time do you close",
            "when are you open", "closing time", "open on sunday", "open today",
            # Shipping & delivery policies (general)
            "how does delivery work", "how long does delivery take", "delivery times", "delivery cost",
            "how much is delivery", "free delivery", "deliver to scotland", "deliver nationwide",
            # Returns & refunds (general)
            "return policy", "returns policy", "refund policy", "can i return", "return tiles",
            "how do i return", "exchange policy", "cancellation", "cancel order",
            # About company
            "who are you", "about surfaces tiles", "who owns", "about your company", "about us",
            # General installation/methods without tile product request
            "how to tile", "how to install", "how much wastage", "calculate wastage", "what is wastage"
        ]

        return any(ind in clean_msg for ind in info_indicators)

    def _resolve_product_cards(
        self,
        message: str,
        sources: List[Dict[str, Any]],
        answer: str = "",
        has_attachment: bool = False,
        visual_query: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Extract and resolve standardized tile product cards for rich display.
        
        Cards are returned when the user expresses product shopping intent or attaches a file:
        - Wants to buy/purchase/order a tile
        - Asks to show/browse/view tiles or tile recommendations
        - Inquires about a specific tile product or style
        - Uploaded an attachment (tile image or spec)
        
        Basic informational queries (location, store address, hours, contact, general
        delivery/return policies) return NO product cards unless an attachment is provided.
        """
        # 0. If the model response is or contains the static welcome message, do not display product cards
        clean_ans = (answer or "").strip()
        if WELCOME_MESSAGE in clean_ans or clean_ans == WELCOME_MESSAGE:
            return []

        # 1. If basic informational / store / policy query, do not show product cards (unless attachment provided)
        if not has_attachment and self._is_general_info_or_policy_query(message):
            return []

        lower_msg = (message or "").lower()

        # 2. Detect explicit shopping/browsing/buying intent
        is_buy_intent = any(w in lower_msg for w in [
            "buy", "purchase", "order", "want to buy", "i want to buy", "i'll take",
            "checkout", "add to cart", "add to basket", "how much is", "can i buy"
        ])
        is_show_intent = any(w in lower_msg for w in [
            "show", "browse", "view", "see", "recommend", "options", "display",
            "range", "collection", "looking for", "suggest", "find me", "similar", "match", "which tile", "what tile"
        ])
        is_tile_query = any(w in lower_msg for w in [
            "tile", "tiles", "porcelain", "marble", "ceramic", "slab", "slabs",
            "paver", "pavers", "flooring", "wood effect", "stone effect"
        ])

        # If user did NOT express buy intent, show intent, tile query, or attach a file, do not show cards
        if not (is_buy_intent or is_show_intent or is_tile_query or has_attachment):
            # Check if user mentioned a specific product title or handle directly
            direct_check = catalog.find(lower_msg)
            if not direct_check:
                return []

        cards: List[Dict[str, Any]] = []
        seen_ids = set()

        def add_card(c: Optional[Dict[str, Any]]):
            if c and c.get("id") and c["id"] not in seen_ids:
                seen_ids.add(c["id"])
                cards.append(c)

        # 3. Direct match in product catalog from the user query
        cleaned_query = re.sub(
            r"^(i\s+want\s+to\s+buy|show\s+me|show\s+tiles|show|can\s+i\s+get|i\s+would\s+like\s+to\s+buy|buy\s+the|buy|looking\s+for)\s+",
            "",
            lower_msg
        ).strip()
        if cleaned_query and len(cleaned_query) >= 3:
            direct_match = catalog.find(cleaned_query)
            if direct_match:
                add_card(catalog.get_product_card(direct_match))

        # 4. Extract products referenced in the model's generated answer (markdown links)
        # e.g. [Snow Sheen ...](https://surfacestiles.co.uk/products/...)
        answer_links = re.findall(r"\[(.*?)\]\((https?://[^\s)]+)\)", answer or "")
        for link_title, link_url in answer_links:
            if "/products/" in link_url or "surfacestiles.co.uk" in link_url:
                p = catalog.find(link_url) or catalog.find(link_title)
                if p:
                    add_card(catalog.get_product_card(p))

        # 5. Extract products from retrieved sources
        for s in sources:
            ctype = (s.get("content_type") or "").lower()
            url = s.get("url") or ""
            title = s.get("title") or ""
            if ctype == "product" or "/products/" in url:
                p = catalog.find(url) or catalog.find(title)
                if p:
                    add_card(catalog.get_product_card(p))

        # 6. If user asked to "show tiles", "buy", or attached an image and we still have fewer than 3 cards, search catalog
        if (is_show_intent or is_buy_intent or has_attachment) and len(cards) < 3:
            search_query = visual_query if (visual_query and len(visual_query) > 3) else (cleaned_query if (cleaned_query and len(cleaned_query) > 3) else message)
            if search_query:
                query_cards = catalog.search(search_query, top_k=4)
                for qc in query_cards:
                    add_card(qc)

        # Pin specific requested product at the beginning if buy intent
        if is_buy_intent and cards:
            for i, c in enumerate(cards):
                c_words = [w for w in c["title"].lower().split() if len(w) > 3]
                if any(w in lower_msg for w in c_words):
                    cards.insert(0, cards.pop(i))
                    break

        return cards[:4]

    def answer_question(
        self,
        message: str,
        history: Optional[List[Any]] = None,
        category: Optional[str] = None,
        top_k: Optional[int] = None,
        attachment: Optional[Any] = None
    ) -> Dict[str, Any]:
        """Execute full RAG generation: retrieve website context -> call Gemini LLM -> return response."""
        # Ensure history is clamped to max configured limit (default: 10)
        max_hist = getattr(settings, "max_chat_history", 10)
        active_history = history[-max_hist:] if history else []

        # Attachment processing
        gemini_part = None
        attachment_info = None
        visual_summary = ""
        has_attachment = False

        if attachment:
            data_bytes, filename, mime_type = self._parse_attachment_data(attachment)
            if data_bytes:
                has_attachment = True
                if mime_type.startswith("image/"):
                    if not self.mock_mode and self.client:
                        try:
                            from google.genai import types
                            gemini_part = types.Part.from_bytes(data=data_bytes, mime_type=mime_type)
                            visual_summary = self._extract_visual_context(gemini_part, message)
                        except Exception as e:
                            logger.warning(f"Failed to create Gemini image Part: {e}")
                    else:
                        visual_summary = "grey outdoor textured porcelain floor tiles patio"

                    attachment_info = (
                        f"Customer attached an image: '{filename}' ({mime_type}).\n"
                        f"Visual description & properties: {visual_summary}"
                    )
                elif mime_type == "application/pdf":
                    if not self.mock_mode and self.client:
                        try:
                            from google.genai import types
                            gemini_part = types.Part.from_bytes(data=data_bytes, mime_type="application/pdf")
                        except Exception as e:
                            logger.warning(f"Failed to create Gemini PDF Part: {e}")
                    attachment_info = f"Customer attached a PDF document: '{filename}'."
                elif mime_type.startswith("text/"):
                    text_snippet = data_bytes.decode("utf-8", errors="ignore")[:3000]
                    attachment_info = f"Customer attached text file '{filename}' with content:\n{text_snippet}"
                else:
                    return {
                        "answer": (
                            f"I received your file '{filename}', but I am currently only able to analyze image files (JPEG, PNG, WebP) "
                            f"and PDF documents. Please upload a photo of the tile or room, and I'll gladly identify it and recommend matching options!"
                        ),
                        "sources": [],
                        "products": []
                    }

        # If user only uploaded an attachment without query text, default to a helpful identification prompt
        effective_message = (message or "").strip()
        if not effective_message and has_attachment:
            effective_message = "What tile is this, and can you recommend matching options from your catalogue?"

        # 1. Retrieve relevant website context (contextualized if follow-up or multimodal)
        retrieval_query = self._build_retrieval_query(effective_message, active_history)
        if visual_summary:
            retrieval_query = f"{retrieval_query} {visual_summary}".strip()

        retrieval_result = self.retriever.retrieve(
            query=retrieval_query,
            top_k=top_k,
            category_filter=category
        )
        context = retrieval_result.get("context", "")
        sources = retrieval_result.get("sources", [])

        # 2. Build prompt including prior history messages, attachment details, and dynamic intent instructions
        prompt = build_rag_prompt(
            user_question=effective_message,
            context=context,
            history=active_history,
            attachment_info=attachment_info
        )

        # 3. Generate response using Gemini
        if self.mock_mode or not self.client:
            answer = self._generate_mock_response(effective_message, retrieval_result, active_history)
        else:
            from google.genai import types
            contents = [prompt, gemini_part] if gemini_part is not None else prompt
            for attempt in range(2):
                try:
                    response = self.client.models.generate_content(
                        model=self.model_name,
                        contents=contents,
                        config=types.GenerateContentConfig(
                            system_instruction=SURFACES_TILES_SYSTEM_PROMPT,
                            temperature=0.3,
                            max_output_tokens=280,
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
                                f"You can add it directly to your cart or purchase using the card below. Would you like me to help calculate the area for your room?"
                            )
                        else:
                            answer = (
                                f"You can find detailed information on our website here:\n\n"
                                f"- **[{top_source['title']}]({top_source['url']})**\n\n"
                                f"Please feel free to ask if you need further help!"
                            )
                    else:
                        answer = "I'm sorry, I couldn't find that in our catalogue. Could you let me know the colour, size, or room you're looking to tile?"
                    break

        clean_answer = (answer or "").strip()
        if (
            WELCOME_MESSAGE in clean_answer
            or clean_answer == WELCOME_MESSAGE
            or "Sophie, the AI assistant for Surfaces Tiles UK" in clean_answer
            or "You're very welcome" in clean_answer
        ):
            sources = []

        products = self._resolve_product_cards(
            effective_message,
            sources,
            answer,
            has_attachment=has_attachment,
            visual_query=visual_summary
        )

        return {
            "answer": answer,
            "sources": sources,
            "products": products
        }

    def stream_answer_question(
        self,
        message: str,
        history: Optional[List[Any]] = None,
        category: Optional[str] = None,
        top_k: Optional[int] = None,
        attachment: Optional[Any] = None
    ):
        """Streaming generator that yields chunks for Server-Sent Events (SSE).
        Yields:
            {"event": "token", "delta": "..."}
            {"event": "sources", "sources": [...]}
            {"event": "products", "products": [...]}
            {"event": "done", "answer": "..."}
        """
        max_hist = getattr(settings, "max_chat_history", 10)
        active_history = history[-max_hist:] if history else []

        # Attachment processing
        gemini_part = None
        attachment_info = None
        visual_summary = ""
        has_attachment = False

        if attachment:
            data_bytes, filename, mime_type = self._parse_attachment_data(attachment)
            if data_bytes:
                has_attachment = True
                if mime_type.startswith("image/"):
                    if not self.mock_mode and self.client:
                        try:
                            from google.genai import types
                            gemini_part = types.Part.from_bytes(data=data_bytes, mime_type=mime_type)
                            visual_summary = self._extract_visual_context(gemini_part, message)
                        except Exception as e:
                            logger.warning(f"Failed to create Gemini image Part: {e}")
                    else:
                        visual_summary = "grey outdoor textured porcelain floor tiles patio"

                    attachment_info = (
                        f"Customer attached an image: '{filename}' ({mime_type}).\n"
                        f"Visual description & properties: {visual_summary}"
                    )
                elif mime_type == "application/pdf":
                    if not self.mock_mode and self.client:
                        try:
                            from google.genai import types
                            gemini_part = types.Part.from_bytes(data=data_bytes, mime_type="application/pdf")
                        except Exception as e:
                            logger.warning(f"Failed to create Gemini PDF Part: {e}")
                    attachment_info = f"Customer attached a PDF document: '{filename}'."
                elif mime_type.startswith("text/"):
                    text_snippet = data_bytes.decode("utf-8", errors="ignore")[:3000]
                    attachment_info = f"Customer attached text file '{filename}' with content:\n{text_snippet}"
                else:
                    unsupported_msg = (
                        f"I received your file '{filename}', but I am currently only able to analyze image files (JPEG, PNG, WebP) "
                        f"and PDF documents. Please upload a photo of the tile or room, and I'll gladly identify it and recommend matching options!"
                    )
                    yield {"event": "sources", "sources": []}
                    yield {"event": "products", "products": []}
                    yield {"event": "token", "delta": unsupported_msg}
                    yield {"event": "done", "answer": unsupported_msg}
                    return

        effective_message = (message or "").strip()
        if not effective_message and has_attachment:
            effective_message = "What tile is this, and can you recommend matching options from your catalogue?"

        retrieval_query = self._build_retrieval_query(effective_message, active_history)
        if visual_summary:
            retrieval_query = f"{retrieval_query} {visual_summary}".strip()

        retrieval_result = self.retriever.retrieve(
            query=retrieval_query,
            top_k=top_k,
            category_filter=category
        )
        context = retrieval_result.get("context", "")
        sources = retrieval_result.get("sources", [])

        prompt = build_rag_prompt(
            user_question=effective_message,
            context=context,
            history=active_history,
            attachment_info=attachment_info
        )

        if self.mock_mode or not self.client:
            answer = self._generate_mock_response(effective_message, retrieval_result, active_history)
            final_sources = [] if (
                WELCOME_MESSAGE in answer
                or "Sophie, the AI assistant for Surfaces Tiles UK" in answer
                or "You're very welcome" in answer
            ) else sources
            final_products = self._resolve_product_cards(
                effective_message,
                final_sources,
                answer,
                has_attachment=has_attachment,
                visual_query=visual_summary
            )
            yield {"event": "sources", "sources": final_sources}
            yield {"event": "products", "products": final_products}
            yield {"event": "token", "delta": answer}
            yield {"event": "done", "answer": answer}
            return

        from google.genai import types
        contents = [prompt, gemini_part] if gemini_part is not None else prompt
        accumulated_text = []
        for attempt in range(2):
            try:
                stream = self.client.models.generate_content_stream(
                    model=self.model_name,
                    contents=contents,
                    config=types.GenerateContentConfig(
                        system_instruction=SURFACES_TILES_SYSTEM_PROMPT,
                        temperature=0.3,
                        max_output_tokens=280,
                        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True)
                    )
                )
                for chunk in stream:
                    if chunk and chunk.text:
                        accumulated_text.append(chunk.text)
                        yield {"event": "token", "delta": chunk.text}

                full_answer = "".join(accumulated_text)
                final_sources = [] if (
                    WELCOME_MESSAGE in full_answer
                    or "Sophie, the AI assistant for Surfaces Tiles UK" in full_answer
                    or "You're very welcome" in full_answer
                ) else sources
                final_products = self._resolve_product_cards(
                    effective_message,
                    final_sources,
                    full_answer,
                    has_attachment=has_attachment,
                    visual_query=visual_summary
                )
                yield {"event": "sources", "sources": final_sources}
                yield {"event": "products", "products": final_products}
                yield {"event": "done", "answer": full_answer}
                return
            except Exception as e:
                err_str = str(e)
                is_transient = "429" in err_str or "RESOURCE_EXHAUSTED" in err_str or "503" in err_str or "UNAVAILABLE" in err_str or "timeout" in err_str.lower()
                if is_transient and attempt == 0:
                    logger.warning(f"Transient error streaming from Gemini API ({e}). Retrying once...")
                    import time
                    time.sleep(2.0)
                    continue

                logger.error(f"Error streaming from Gemini API: {e}")
                fallback = "I'm sorry, I couldn't find that information right now. Please reach out to our customer support team for help."
                yield {"event": "sources", "sources": []}
                yield {"event": "products", "products": []}
                yield {"event": "token", "delta": fallback}
                yield {"event": "done", "answer": fallback}
                return


    def _generate_mock_response(
        self,
        message: str,
        retrieval_result: Dict[str, Any],
        history: Optional[List[Any]] = None
    ) -> str:
        """Generate a grounded mock response when running in demo/offline mode without API key."""
        sources = retrieval_result.get("sources", [])
        lower_msg = (message or "").strip().lower()

        # Handle direct name inquiries and greetings in mock/offline mode
        if any(nq in lower_msg for nq in ["what is your name", "what's your name", "who are you"]):
            return "Hello! I'm Sophie, the AI assistant for Surfaces Tiles UK. How can I help you find the right tiles today?"
        if lower_msg in ["hi", "hello", "hey", "good morning", "good afternoon", "good evening", "hiya", "howdy"]:
            return WELCOME_MESSAGE

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


