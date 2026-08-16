import os
import json
import httpx
import logging
import asyncio
from typing import List, Dict, AsyncGenerator
from datetime import datetime
from pathlib import Path
from app.config import settings, BASE_DIR

logger = logging.getLogger(__name__)

class LLMClient:
    """Client for generating intelligent answers from retrieved chunks using Ollama or Colab endpoint files."""

    def __init__(self):
        self.model = settings.LLM_MODEL
        self.temperature = settings.LLM_TEMPERATURE
        self.max_tokens = settings.LLM_MAX_TOKENS
        self.timeout = 60.0
        
        # Get the endpoint URL
        self.base_url = self._get_endpoint_url()
        
        # Initialize the sync client
        self.client = httpx.Client(timeout=self.timeout)

    def _get_endpoint_url(self) -> str:
        """Get the LLM endpoint URL, reading from file if Colab is enabled."""
        if settings.USE_COLAB_LLM:
            filepath = settings.COLAB_ENDPOINT_FILE
            # Support absolute paths, or resolve relative to BASE_DIR
            resolved_path = Path(filepath) if Path(filepath).is_absolute() else BASE_DIR / filepath
            if resolved_path.exists():
                try:
                    with open(resolved_path, 'r', encoding='utf-8') as f:
                        url = f.read().strip()
                        if url:
                            logger.info(f"Loaded live Colab endpoint from file: {url}")
                            return url.rstrip("/")
                except Exception as e:
                    logger.error(f"Error reading colab endpoint file {resolved_path}: {e}")

        # Fallback to environment variable or local
        return settings.LLM_ENDPOINT_URL.rstrip("/") if settings.LLM_ENDPOINT_URL else ""

    def _build_prompt(self, query: str, chunks: List[Dict]) -> str:
        """Build a complete prompt with system instruction and context"""
        # System instruction
        system = """You are a knowledge assistant helping a researcher understand their documents.

Instructions:
1. ONLY use information from the provided chunks
2. If the context doesn't contain the answer, say "I don't have enough information about this in your documents"
3. Cite your sources using [Document: filename] at the end of each section
4. Be concise but thorough
5. Use clear, academic language
6. If the question has multiple parts, address each one"""
        
        # Context
        context_parts = []
        for i, chunk in enumerate(chunks):
            filename = chunk.get('filename', chunk.get('document_name', f'source_{i+1}'))
            context_parts.append(f"Source {i+1} ({filename}):\n{chunk.get('text', chunk.get('chunk', ''))}")
        
        context = "\n\n".join(context_parts) if context_parts else "No relevant context found."
        
        # User query
        user_query = f"Question: {query}\n\nAnswer the question using ONLY the information in the context. Cite your sources."
        
        # Combine
        return f"{system}\n\nContext:\n{context}\n\n{user_query}"

    def generate_answer(self, query: str, chunks: List[Dict]) -> Dict:
        """Generate an answer using the LLM via Ollama's OpenAI-compatible API"""
        # Re-resolve base_url in case the file content changed dynamically
        self.base_url = self._get_endpoint_url()
        
        if not chunks:
            return {
                "answer": "I couldn't find any relevant information in your documents. Try uploading more documents or rephrasing your question.",
                "sources": [],
                "timestamp": datetime.now().isoformat()
            }
        
        try:
            # Build the prompt
            prompt = self._build_prompt(query, chunks)
            
            # Prepare the request for Ollama's OpenAI-compatible API
            messages = [
                {"role": "system", "content": "You are a helpful knowledge assistant."},
                {"role": "user", "content": prompt}
            ]
            
            # Call the Ollama endpoint
            url = f"{self.base_url}/chat/completions"
            logger.info(f"Calling LLM: {url} using model {self.model}...")
            
            response = self.client.post(
                url,
                json={
                    "model": self.model,
                    "messages": messages,
                    "temperature": self.temperature,
                    "max_tokens": self.max_tokens,
                    "stream": False
                },
                headers={"ngrok-skip-browser-warning": "any"}
            )
            response.raise_for_status()
            data = response.json()
            
            # Extract the answer
            answer = data.get('choices', [{}])[0].get('message', {}).get('content', 'No response generated.')
            
        except httpx.TimeoutException:
            logger.error("LLM request timed out.")
            answer = "⚠️ The request timed out. The model might be loading or under heavy load. Please try again."
        except Exception as e:
            logger.error(f"LLM request error: {e}")
            answer = f"⚠️ An error occurred: {str(e)}. Please check that the Colab notebook is running."
        
        # Extract sources
        sources = []
        for chunk in chunks[:5]:
            sources.append({
                "document_id": chunk.get("document_id", ""),
                "filename": chunk.get("filename", chunk.get("document_name", "")),
                "chunk_id": chunk.get("chunk_id", ""),
                "text": chunk.get("text", chunk.get("chunk", ""))[:200],
                "similarity": chunk.get("similarity", 0.0)
            })
        
        return {
            "answer": answer,
            "sources": sources,
            "timestamp": datetime.now().isoformat()
        }

    async def generate_answer_stream(self, query: str, chunks: List[Dict]) -> AsyncGenerator[str, None]:
        """Streams LLM generated answer tokens asynchronously, maintaining streaming capabilities."""
        self.base_url = self._get_endpoint_url()
        
        if not chunks:
            fallback = "I couldn't find any relevant information in your documents. Try uploading more documents or rephrasing your question."
            for word in fallback.split(" "):
                yield word + " "
                await asyncio.sleep(0.05)
            return

        try:
            prompt = self._build_prompt(query, chunks)
            messages = [
                {"role": "system", "content": "You are a helpful knowledge assistant."},
                {"role": "user", "content": prompt}
            ]
            
            url = f"{self.base_url}/chat/completions"
            logger.info(f"Starting LLM streaming call to: {url}...")
            
            payload = {
                "model": self.model,
                "messages": messages,
                "temperature": self.temperature,
                "max_tokens": self.max_tokens,
                "stream": True
            }
            
            headers = {
                "ngrok-skip-browser-warning": "any"
            }

            # Configure a robust timeout for streaming: 15s connect limit, infinite read limit
            stream_timeout = httpx.Timeout(120.0, connect=15.0, read=None)

            async with httpx.AsyncClient() as client:
                async with client.stream("POST", url, json=payload, headers=headers, timeout=stream_timeout) as response:
                    if response.status_code != 200:
                        logger.error(f"LLM streaming request failed with status: {response.status_code}")
                        err_msg = f"⚠️ Ollama server returned error {response.status_code}. Please verify Colab status."
                        for word in err_msg.split(" "):
                            yield word + " "
                            await asyncio.sleep(0.05)
                        return

                    buffer = ""
                    async for byte_chunk in response.aiter_bytes():
                        buffer += byte_chunk.decode("utf-8")
                        while "\n" in buffer:
                            line, buffer = buffer.split("\n", 1)
                            line = line.strip()
                            if not line:
                                continue
                            if line.startswith("data:"):
                                data_str = line[5:].strip()
                                if data_str == "[DONE]":
                                    break
                                try:
                                    data_json = json.loads(data_str)
                                    delta = data_json.get("choices", [{}])[0].get("delta", {})
                                    token = delta.get("content", "")
                                    if token:
                                        yield token
                                except Exception:
                                    pass
        except Exception as e:
            logger.error(f"LLM streaming exception: {e}")
            err_msg = f"⚠️ Connection to Colab Ollama failed: {str(e)}"
            for word in err_msg.split(" "):
                yield word + " "
                await asyncio.sleep(0.05)

    def health_check(self) -> bool:
        """Check if the LLM endpoint is reachable"""
        self.base_url = self._get_endpoint_url()
        if not self.base_url:
            return False
            
        try:
            response = self.client.get(f"{self.base_url}/health", timeout=5.0)
            return response.status_code == 200
        except Exception:
            try:
                response = self.client.get(f"{self.base_url}/v1/models", timeout=5.0)
                return response.status_code == 200
            except Exception:
                return False

# Singleton instance
llm_client = LLMClient()
