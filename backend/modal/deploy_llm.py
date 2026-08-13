import os
import modal

# Define the Modal App (formerly Stub)
app = modal.App("personal-knowledge-guardian-llm")

# Select a lightweight instruction-tuned LLM
MODEL_NAME = "Qwen/Qwen2.5-1.5B-Instruct"

# Build container image with CUDA and HuggingFace dependencies
image = (
    modal.Image.debian_slim()
    .pip_install(
        "transformers>=4.37.0",
        "torch>=2.1.2",
        "accelerate>=0.26.0",
        "huggingface_hub>=0.20.0",
        "fastapi[standard]"
    )
)

@app.cls(
    image=image,
    gpu="T4",  # Use an affordable T4 GPU (or A10G for faster speeds)
    timeout=600,
    scaledown_window=120
)
class LLMServer:
    @modal.enter()
    def load_model(self):
        """Runs once when container starts to cache the LLM weight into memory."""
        import torch
        from transformers import AutoTokenizer, AutoModelForCausalLM, pipeline

        print(f"Loading tokenizer and model: {MODEL_NAME}...")
        self.tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
        self.model = AutoModelForCausalLM.from_pretrained(
            MODEL_NAME,
            torch_dtype=torch.float16,
            device_map="auto"
        )
        self.generator = pipeline(
            "text-generation",
            model=self.model,
            tokenizer=self.tokenizer
        )
        print("Model loaded successfully.")

    @modal.fastapi_endpoint(method="POST")
    def generate(self, data: dict):
        """
        API Endpoint exposed via Modal Web Server.
        Accepts: {"prompt": "...", "max_tokens": 256}
        """
        prompt = data.get("prompt", "")
        max_tokens = int(data.get("max_tokens", 256))

        if not prompt:
            return {"error": "Prompt cannot be empty"}

        # Format prompt according to Chat template
        messages = [
            {"role": "system", "content": "You are a Personal Knowledge Guardian. Help researchers extract insights, summarize concepts, and index documents accurately and concisely."},
            {"role": "user", "content": prompt}
        ]
        
        # Apply the chat template
        formatted_prompt = self.tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True
        )

        print(f"Generating for prompt: {prompt[:100]}...")
        outputs = self.generator(
            formatted_prompt,
            max_new_tokens=max_tokens,
            do_sample=True,
            temperature=0.7,
            top_p=0.9
        )
        
        generated_text = outputs[0]["generated_text"]
        
        # Extract assistant response (text after the generation prompt)
        assistant_marker = "<|im_start|>assistant\n"
        if assistant_marker in generated_text:
            generated_text = generated_text.split(assistant_marker)[-1]
        
        # Strip trailing markers if any
        if "<|im_end|>" in generated_text:
            generated_text = generated_text.split("<|im_end|>")[0]

        return {
            "text": generated_text.strip(),
            "model": MODEL_NAME
        }

# Instruction for Deployment:
# Run: modal deploy backend/modal/deploy_llm.py
# After deployment, Modal will output a URL like: https://<username>-personal-knowledge-guardian-llm-generate.modal.run
# Copy this URL and save it as MODAL_LLM_URL in your backend's .env file.
