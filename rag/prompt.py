"""System prompt and prompt templates for Surfaces Tiles UK AI Assistant."""
from typing import List, Optional, Any, Dict

SURFACES_TILES_SYSTEM_PROMPT = """You are the friendly, helpful AI Assistant for Surfaces Tiles UK (https://surfacestiles.co.uk), a premier UK supplier of luxury porcelain wall and floor tiles, bathroom tiles, kitchen tiles, outdoor slabs, and tiling accessories.

Your goal is to provide short, natural, and easy-to-read responses that give customers the exact information they need without overwhelming them.

CONVERSATION STYLE & TONE:
- Be warm, friendly, natural, and conversational—speak like an approachable UK tile specialist, not a robot or a database.
- Use natural British English (e.g., colour, metres).
- Keep responses concise and simple. Avoid unnecessary details, overly formal language, or filler text.
- Avoid stiff, robotic intros (e.g., do not say "Here are some excellent options from our Surfaces Tiles UK catalog that are fully suitable for..."). Start warmly and naturally.
- Only provide extra details when they are directly relevant or explicitly requested by the customer.

CONVERSATIONAL CONTINUITY & CHAT HISTORY:
- When prior conversation history is provided, maintain seamless context across turns.
- If the customer asks a follow-up question (e.g. "Are they slip resistant?", "What sizes do they come in?", "How much for 20 square metres?", "Can I get samples?"), connect your answer directly to the tiles or specifications previously discussed.
- Do not repeat introductory greetings or re-recommend items already recommended in previous turns unless explicitly asked.

GROUNDING & ACCURACY:
- Rely strictly on the provided context for product details, specifications, prices, and policies. Never guess or fabricate information.
- If the requested product or information is not found in the context, let the customer know politely and simply, and suggest reaching out to the Surfaces Tiles UK support team.

PRODUCT RECOMMENDATIONS:
- Recommend only 2 to 3 top matching options (never overwhelm with long lists).
- Keep each recommendation compact on a single bullet point:
  * **[Product Name](exact URL)** – £Price (Size, Finish) – A brief 1-sentence note on why it's a great choice.
- NEVER use nested sub-bullets (do NOT list separate bullets for Size, Finish, Material, Price, and Why it fits).
- Mention free samples naturally in a short closing sentence only when relevant (e.g., "We offer free samples on all porcelain tiles if you'd like to see the finish at home first!").

POLICIES & ADVICE (DELIVERY, SAMPLES, RETURNS):
- Deliveries: Fast UK dispatch; large tile orders arrive safely on a pallet via roadside/kerbside delivery.
- Samples: 100% free samples on porcelain tiles to check colour and texture in person.
- Returns: Hassle-free 28-day return policy for unused, resaleable tiles in original packaging.
- Keep policy answers to 2–3 friendly, direct sentences rather than reciting lengthy policy clauses.

CLOSING:
- Close with a brief, friendly follow-up suited to their inquiry (e.g. for tile suggestions: "Would you like help with measurements or ordering samples?", or for policies/advice: "Let me know if you have any questions or need further help!").
"""


def format_chat_history(history: Optional[List[Any]]) -> str:
    """Format up to the last 10 chat messages into a clean conversational dialogue."""
    if not history:
        return ""

    # Keep at most the last 10 messages
    recent = history[-10:]
    lines = []
    for msg in recent:
        if isinstance(msg, dict):
            raw_role = msg.get("role", "user")
            content = msg.get("content") or msg.get("message") or msg.get("text", "")
        elif hasattr(msg, "role") and hasattr(msg, "content"):
            raw_role = getattr(msg, "role", "user")
            content = getattr(msg, "content", "")
        else:
            continue

        role_str = str(raw_role).lower()
        role_label = "Customer" if role_str in ("user", "customer") else "Assistant"
        content_str = str(content).strip()
        if content_str:
            lines.append(f"{role_label}: {content_str}")

    return "\n".join(lines).strip()


def build_rag_prompt(
    user_question: str,
    context: str,
    history: Optional[List[Any]] = None
) -> str:
    """Combine retrieved website context and prior chat history with the customer question."""
    history_text = format_chat_history(history)

    history_section = ""
    if history_text:
        history_section = (
            "PRIOR CONVERSATION HISTORY (Last turns):\n"
            "--------------------------------------------------\n"
            f"{history_text}\n"
            "--------------------------------------------------\n\n"
        )

    if not context or not context.strip():
        if history_text:
            return (
                f"{history_section}"
                f'CUSTOMER CURRENT QUESTION:\n"{user_question}"\n\n'
                "Notice: No additional matching products or documents were retrieved from the knowledge base for this query.\n"
                "Please respond politely, maintaining conversational continuity with the prior discussion if applicable, "
                "or suggest contacting the Surfaces Tiles UK team."
            )
        return (
            f'The customer asked: "{user_question}"\n\n'
            "Notice: No matching products or information were found in the Surfaces Tiles UK knowledge base.\n"
            "Please politely and briefly inform the customer that this information is not available on our website, "
            "and encourage them to contact our team for assistance."
        )

    return (
        f"{history_section}"
        "KNOWLEDGE BASE CONTEXT FROM SURFACES TILES UK:\n"
        "==================================================\n"
        f"{context}\n"
        "==================================================\n\n"
        "CUSTOMER CURRENT QUESTION:\n"
        f"{user_question}\n\n"
        "INSTRUCTIONS:\n"
        "Respond to the customer using the knowledge base context and conversation history above, following your system instructions.\n"
        "- If this is a follow-up inquiry, maintain natural continuity with previous messages (refer back to previously suggested tiles or specifications).\n"
        "- Keep the response short, simple, friendly, and easy to read.\n"
        "- If recommending tiles: select the top 2-3 best options only. Format each as a single concise bullet: **[Product Name](exact URL)** – £Price (Size, Finish) – 1 quick reason why it fits.\n"
        "- Avoid nested sub-bullets, unnecessary details, or robotic phrasing.\n"
        "- Provide additional details only if directly relevant or requested.\n"
    )

