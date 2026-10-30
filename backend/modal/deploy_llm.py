import os
import modal

# Define the Modal App
app = modal.App("personal-knowledge-guardian-llm")

# Model configuration
DEFAULT_GROQ_MODEL = "openai/gpt-oss-120b"
FALLBACK_MODEL_NAME = "Qwen/Qwen2.5-1.5B-Instruct"

# Build container image with Groq, LangChain, and HuggingFace dependencies
image = (
    modal.Image.debian_slim()
    .pip_install(
        "transformers>=4.37.0",
        "torch>=2.1.2",
        "accelerate>=0.26.0",
        "huggingface_hub>=0.20.0",
        "fastapi[standard]",
        "langchain-groq>=1.1.0",
        "groq>=0.30.0",
        "python-dotenv>=1.0.0"
    )
)

# Attach Groq secret if present in Modal environment
# Create via: modal secret create groq-secret GROQ_API_KEY=your_key GROQ_MODEL=openai/gpt-oss-120b
groq_secret = modal.Secret.from_name("groq-secret")

@app.cls(
    image=image,
    secrets=[groq_secret],
    gpu="T4",
    timeout=600,
    scaledown_window=120
)
class LLMServer:
    @modal.enter()
    def load_model(self):
        """Initializes Groq client if key is present, otherwise falls back to local HuggingFace weights."""
        self.groq_api_key = os.environ.get("GROQ_API_KEY", "").strip()
        self.groq_model = os.environ.get("GROQ_MODEL", DEFAULT_GROQ_MODEL)

        if self.groq_api_key and self.groq_api_key != "replace_with_my_actual_key":
            print(f"Configuring Groq LLM client for model: {self.groq_model}...")
            from langchain_groq import ChatGroq
            self.groq_client = ChatGroq(
                groq_api_key=self.groq_api_key,
                model_name=self.groq_model,
                temperature=0.2,
                max_tokens=1200,
                max_retries=2
            )
            self.generator = None
            print("Groq client initialized successfully on Modal.")
        else:
            print(f"GROQ_API_KEY not found in Modal Secret. Falling back to local {FALLBACK_MODEL_NAME}...")
            import torch
            from transformers import AutoTokenizer, AutoModelForCausalLM, pipeline
            self.groq_client = None
            self.tokenizer = AutoTokenizer.from_pretrained(FALLBACK_MODEL_NAME)
            self.model = AutoModelForCausalLM.from_pretrained(
                FALLBACK_MODEL_NAME,
                torch_dtype=torch.float16,
                device_map="auto"
            )
            self.generator = pipeline(
                "text-generation",
                model=self.model,
                tokenizer=self.tokenizer
            )
            print("Fallback local model loaded.")

    @modal.fastapi_endpoint(method="POST")
    def generate(self, data: dict):
        """
        API Endpoint exposed via Modal Web Server.
        Accepts: {"prompt": "...", "max_tokens": 1200}
        """
        prompt = data.get("prompt", "")
        max_tokens = int(data.get("max_tokens", 1200))

        if not prompt:
            return {"error": "Prompt cannot be empty"}

        # Route to Groq if active
        if getattr(self, "groq_client", None) is not None:
            from langchain_core.messages import SystemMessage, HumanMessage
            messages = [
                SystemMessage(content="You are a Personal Knowledge Guardian. Help researchers extract insights, summarize concepts, and answer accurately based on document context. Cite sources using [S1], [S2], etc."),
                HumanMessage(content=prompt)
            ]
            response = self.groq_client.invoke(messages)
            text_output = response.content if hasattr(response, "content") else str(response)
            return {
                "text": text_output.strip(),
                "model": self.groq_model,
                "provider": "groq"
            }

        # Fallback to local HuggingFace generator
        messages = [
            {"role": "system", "content": "You are a Personal Knowledge Guardian. Help researchers extract insights, summarize concepts, and index documents accurately and concisely."},
            {"role": "user", "content": prompt}
        ]
        formatted_prompt = self.tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True
        )

        outputs = self.generator(
            formatted_prompt,
            max_new_tokens=max_tokens,
            do_sample=True,
            temperature=0.7,
            top_p=0.9
        )
        generated_text = outputs[0]["generated_text"]
        assistant_marker = "<|im_start|>assistant\n"
        if assistant_marker in generated_text:
            generated_text = generated_text.split(assistant_marker)[-1]
        if "<|im_end|>" in generated_text:
            generated_text = generated_text.split("<|im_end|>")[0]

        return {
            "text": generated_text.strip(),
            "model": FALLBACK_MODEL_NAME,
            "provider": "modal_local"
        }

# Instructions for Modal Deployment (REQUIRES EXPLICIT USER APPROVAL):
# 1. Create Modal Secret:
#    modal secret create groq-secret GROQ_API_KEY=<your_groq_api_key> GROQ_MODEL=openai/gpt-oss-120b
# 2. Deploy only when approved:
#    modal deploy backend/modal/deploy_llm.py
