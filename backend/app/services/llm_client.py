import os
import json
import logging
import asyncio
from typing import List, Dict, Any, Optional, AsyncGenerator
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

from app.config import settings, BASE_DIR

# Ensure environment variables are loaded
load_dotenv(dotenv_path=str(BASE_DIR / ".env"))

logger = logging.getLogger(__name__)

# Try importing langchain_groq and groq exceptions
try:
    from langchain_groq import ChatGroq
    from langchain_core.messages import SystemMessage, HumanMessage
    import groq
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False
    logger.warning("langchain-groq or groq package not installed. Groq integration will be disabled.")


class LLMClient:
    """Client for generating grounded answers and insights from retrieved chunks using Groq."""

    def __init__(self):
        self.model = settings.GROQ_MODEL or "openai/gpt-oss-120b"
        self.temperature = getattr(settings, "GROQ_TEMPERATURE", 0.2)
        self.max_tokens = getattr(settings, "GROQ_MAX_TOKENS", 1200)
        self.timeout = 60.0

    def _get_api_key(self) -> str:
        """Securely retrieves the Groq API key from environment, validating against placeholder."""
        if "GROQ_API_KEY" in os.environ:
            api_key = os.environ.get("GROQ_API_KEY", "")
        else:
            load_dotenv(dotenv_path=str(BASE_DIR / ".env"))
            api_key = os.environ.get("GROQ_API_KEY", "") or getattr(settings, "GROQ_API_KEY", "")

        api_key = api_key.strip() if api_key else ""
        
        # Auto-heal accidental leading 'r' from terminal paste error (rgsk_ -> gsk_)
        if api_key.startswith("rgsk_"):
            api_key = api_key[1:]
            
        # Guard against empty or placeholder key
        if not api_key or api_key == "replace_with_my_actual_key" or "my_actual_key" in api_key:
            return ""
        return api_key

    def is_groq_configured(self) -> bool:
        """Returns True if Groq package is installed and a valid API key is present."""
        return GROQ_AVAILABLE and bool(self._get_api_key())

    def _get_chat_model(self) -> Optional["ChatGroq"]:
        """Initializes and returns a LangChain ChatGroq instance with configured model and parameters."""
        api_key = self._get_api_key()
        if not api_key or not GROQ_AVAILABLE:
            return None

        # Resolve latest model setting dynamically
        current_model = os.environ.get("GROQ_MODEL", "") or self.model
        return ChatGroq(
            groq_api_key=api_key,
            model_name=current_model,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            max_retries=2,
            timeout=self.timeout
        )

    def _format_sources(self, chunks: List[Dict]) -> List[Dict[str, Any]]:
        """Maps retrieved chunks to structured source records with stable IDs [S1], [S2], etc."""
        sources = []
        for i, chunk in enumerate(chunks[:5]):
            label = f"[S{i+1}]"
            source_id = f"S{i+1}"
            filename = chunk.get("filename", chunk.get("document_name", f"source_{i+1}"))
            
            # Extract page number if available (from metadata or direct chunk key)
            page_num = chunk.get("page_number")
            if page_num is None and isinstance(chunk.get("metadata"), dict):
                page_num = chunk["metadata"].get("page_number")

            doc_id = str(chunk.get("document_id", ""))
            chunk_id = str(chunk.get("chunk_id", chunk.get("id", "")))
            text_preview = chunk.get("text", chunk.get("chunk", ""))[:250]
            similarity = float(chunk.get("similarity", 0.0))

            sources.append({
                "source_id": source_id,
                "label": label,
                "document_id": doc_id,
                "filename": filename,
                "page_number": page_num,
                "chunk_id": chunk_id,
                "text": text_preview,
                "similarity": round(similarity, 4)
            })
        return sources

    def _build_prompt_messages(self, query: str, chunks: List[Dict]) -> List[Any]:
        """Constructs system and user messages restricting answers strictly to retrieved passages."""
        system_instruction = (
            "You are the Personal Knowledge Guardian assistant, helping researchers understand and query their documents.\n\n"
            "Strict Instructions:\n"
            "1. ONLY use information directly contained in the provided source passages [S1], [S2], etc.\n"
            "2. Whenever you state a fact or reference information, cite the exact source label, for example: [S1] or [S2].\n"
            "3. If the context does not contain enough information to answer the question, state clearly: "
            "'The retrieved documents do not contain enough information to answer this question.' Do not fabricate, assume, or speculate.\n"
            "4. Never invent filenames, quotations, page numbers, or unsupported claims.\n"
            "5. If asked to summarize or identify related concepts across documents, synthesize the facts strictly from the provided passages and cite the respective sources.\n"
            "6. Be concise, clear, and academically rigorous."
        )

        context_parts = []
        for i, chunk in enumerate(chunks[:5]):
            label = f"[S{i+1}]"
            filename = chunk.get("filename", chunk.get("document_name", f"source_{i+1}"))
            page_num = chunk.get("page_number")
            if page_num is None and isinstance(chunk.get("metadata"), dict):
                page_num = chunk["metadata"].get("page_number")
            
            source_header = f"{label} (Document: {filename}"
            if page_num is not None:
                source_header += f", Page: {page_num}"
            source_header += "):"
            
            chunk_text = chunk.get("text", chunk.get("chunk", "")).strip()
            context_parts.append(f"{source_header}\n{chunk_text}")

        context_str = "\n\n".join(context_parts) if context_parts else "No relevant context found."
        user_content = (
            f"Context Passages:\n{context_str}\n\n"
            f"Question:\n{query}\n\n"
            "Answer the question grounded strictly in the context above and cite sources using [S1], [S2], etc.:"
        )

        return [
            SystemMessage(content=system_instruction),
            HumanMessage(content=user_content)
        ]

    def _handle_error(self, e: Exception) -> str:
        """Translates exceptions into safe, user-friendly messages without exposing secrets or stack traces."""
        logger.error(f"Groq API call failed: {type(e).__name__} - {str(e)}")

        # Check direct exception and underlying cause chain
        all_errs = [e]
        if hasattr(e, "__cause__") and e.__cause__:
            all_errs.append(e.__cause__)

        err_str = " ".join([str(x) for x in all_errs]).lower()

        if GROQ_AVAILABLE:
            for err in all_errs:
                if isinstance(err, groq.AuthenticationError):
                    return "⚠️ Authentication error: Invalid Groq API key. Please check your GROQ_API_KEY in the backend .env file."
                elif isinstance(err, groq.RateLimitError):
                    return "⚠️ Groq API rate limit reached (HTTP 429). Please wait a moment before trying again."
                elif isinstance(err, (groq.NotFoundError, groq.BadRequestError)):
                    return f"⚠️ Model access error: '{self.model}' is currently unavailable or unsupported on your Groq plan."
                elif isinstance(err, (groq.APITimeoutError, groq.APIConnectionError)):
                    return "⚠️ Connection to GroqCloud timed out. Please check your network connection."

        if "401" in err_str or "invalid api key" in err_str or "authentication" in err_str:
            return "⚠️ Authentication error: Invalid Groq API key. Please check your GROQ_API_KEY in the backend .env file."
        elif "429" in err_str or "rate limit" in err_str:
            return "⚠️ Groq API rate limit reached (HTTP 429). Please wait a moment before trying again."
        elif "timeout" in err_str or "timed out" in err_str:
            return "⚠️ Connection to GroqCloud timed out. Please check your network connection."

        return "⚠️ An error occurred while communicating with the Groq service. Please try again."

    def generate_answer(self, query: str, chunks: List[Dict]) -> Dict[str, Any]:
        """Synchronously generates a grounded answer using LangChain Groq."""
        sources = self._format_sources(chunks)

        # 1. Check for empty query
        if not query or not query.strip():
            return {
                "answer": "Query cannot be empty.",
                "sources": [],
                "timestamp": datetime.now().isoformat(),
                "model": self.model,
                "provider": "groq"
            }

        # 2. Check for empty chunks
        if not chunks:
            return {
                "answer": "I couldn't find any relevant information in your uploaded documents. Please upload relevant documents or rephrase your question.",
                "sources": [],
                "timestamp": datetime.now().isoformat(),
                "model": self.model,
                "provider": "groq"
            }

        # 3. Check if Groq API key is configured
        if not self.is_groq_configured():
            logger.warning("Groq API key is missing or set to placeholder.")
            return {
                "answer": (
                    "⚠️ Groq API key is not configured.\n\n"
                    "To enable AI answers powered by Groq (`openai/gpt-oss-120b`), please add your API key "
                    "to the `backend/.env` file:\n"
                    "```dotenv\nGROQ_API_KEY=gsk_your_actual_key_here\n```"
                ),
                "sources": sources,
                "timestamp": datetime.now().isoformat(),
                "model": self.model,
                "provider": "groq"
            }

        # 4. Invoke ChatGroq
        try:
            chat_model = self._get_chat_model()
            messages = self._build_prompt_messages(query, chunks)
            
            logger.info(f"Invoking Groq model '{self.model}' with {len(chunks)} context chunks...")
            response = chat_model.invoke(messages)
            
            answer = response.content if hasattr(response, "content") else str(response)
            if not answer or not str(answer).strip():
                answer = "The retrieved documents do not contain enough information to answer this question."

            return {
                "answer": str(answer).strip(),
                "sources": sources,
                "timestamp": datetime.now().isoformat(),
                "model": self.model,
                "provider": "groq"
            }

        except Exception as e:
            safe_error_msg = self._handle_error(e)
            return {
                "answer": safe_error_msg,
                "sources": sources,
                "timestamp": datetime.now().isoformat(),
                "model": self.model,
                "provider": "groq"
            }

    async def generate_answer_stream(self, query: str, chunks: List[Dict]) -> AsyncGenerator[str, None]:
        """Asynchronously streams generated tokens from Groq via LangChain astream."""
        # 1. Empty chunks fallback
        if not chunks:
            fallback = "I couldn't find any relevant information in your uploaded documents. Please upload relevant documents or rephrase your question."
            for word in fallback.split(" "):
                yield word + " "
                await asyncio.sleep(0.03)
            return

        # 2. Check Groq API configuration
        if not self.is_groq_configured():
            msg = (
                "⚠️ Groq API key is not configured. Please set GROQ_API_KEY in backend/.env "
                "to enable Groq (openai/gpt-oss-120b) reasoning."
            )
            for word in msg.split(" "):
                yield word + " "
                await asyncio.sleep(0.03)
            return

        # 3. Stream from ChatGroq
        try:
            chat_model = self._get_chat_model()
            messages = self._build_prompt_messages(query, chunks)
            
            logger.info(f"Starting Groq streaming invocation using model: {self.model}...")
            async for chunk in chat_model.astream(messages):
                token = chunk.content if hasattr(chunk, "content") else str(chunk)
                if token:
                    yield token

        except Exception as e:
            err_msg = self._handle_error(e)
            for word in err_msg.split(" "):
                yield word + " "
                await asyncio.sleep(0.03)

    def generate_summary(self, filename: str, context: str) -> str:
        """Summarizes document content grounded strictly in the provided text."""
        if not self.is_groq_configured():
            return f"[Groq Key Missing] Summary unavailable. Configure GROQ_API_KEY in backend/.env to summarize '{filename}'."

        try:
            chat_model = self._get_chat_model()
            messages = [
                SystemMessage(content=(
                    "You are a research synthesis assistant. Generate a concise, academic summary of the provided text. "
                    "Ground your summary ONLY in the provided text. Do not invent facts."
                )),
                HumanMessage(content=f"Document: {filename}\n\nContent:\n{context}\n\nProvide an executive summary:")
            ]
            res = chat_model.invoke(messages)
            return res.content.strip() if hasattr(res, "content") else str(res).strip()
        except Exception as e:
            return self._handle_error(e)

    def generate_cross_document_concepts(self, context: str) -> str:
        """Extracts and synthesizes cross-document concepts grounded strictly in the context."""
        if not self.is_groq_configured():
            return "Cross-document concept identification requires GROQ_API_KEY configured in backend/.env."

        try:
            chat_model = self._get_chat_model()
            messages = [
                SystemMessage(content=(
                    "You are a knowledge conceptualizer. Identify key concepts and cross-document relationships "
                    "strictly based on the supplied context passages. Cite sources where concepts connect."
                )),
                HumanMessage(content=f"Context Passages:\n{context}\n\nIdentify and explain key connected concepts:")
            ]
            res = chat_model.invoke(messages)
            return res.content.strip() if hasattr(res, "content") else str(res).strip()
        except Exception as e:
            return self._handle_error(e)

    def health_check(self) -> bool:
        """Returns True if Groq is configured and ready."""
        return self.is_groq_configured()


# Global singleton instance
llm_client = LLMClient()
