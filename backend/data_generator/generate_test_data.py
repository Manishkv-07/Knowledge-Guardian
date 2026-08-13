import os
import sys
from pathlib import Path

# Add backend directory to sys.path
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

# Ensure stdout supports unicode printing on Windows
try:
    sys.stdout.reconfigure(encoding='utf-8')
except AttributeError:
    pass

# We define 15 realistic research papers with rich, 500-700 word technical content.
# Each paper includes sections like Title, Abstract, Introduction, Core Concepts, and References.
PAGES = [
    {
        "filename": "transformer_attention_mechanisms.txt",
        "title": "Understanding Transformer Attention Mechanisms",
        "text": """Title: Understanding Transformer Attention Mechanisms
Author: Dr. Amelia Vane, AI Research Institute
Date: January 2026

Abstract:
This paper provides a rigorous analysis of the mathematical formulations underpinning attention mechanisms in Transformer architectures. We discuss the transition from traditional recurrence-based sequence models to self-attention-based models, highlighting the computational advantages and limitations of dot-product similarity metrics.

1. Introduction
Before the introduction of the Transformer architecture by Vaswani et al. (2017), sequence modeling tasks like machine translation and language modeling relied heavily on Recurrent Neural Networks (RNNs) and Long Short-Term Memory (LSTM) networks. While effective at processing sequential data, LSTMs suffer from sequential dependency bottlenecks, preventing parallelization across sequence lengths. The Transformer architecture eliminates recurrence entirely, relying on attention mechanisms to capture dependencies regardless of their distance in the input sequence.

2. Mathematical Formulation of Self-Attention
Self-attention maps a set of query vectors to a distribution over key vectors to compute a weighted sum of value vectors. Formally, given an input matrix X, we project it into Query (Q), Key (K), and Value (V) representations using learned weight matrices W_Q, W_K, and W_V:
  Q = X * W_Q
  K = X * W_K
  V = X * W_V

The scaled dot-product attention is defined as:
  Attention(Q, K, V) = softmax( (Q * K^T) / sqrt(d_k) ) * V
where d_k represents the dimension of the key vectors. The scaling factor 1/sqrt(d_k) is critical; for large values of d_k, the dot products grow large in magnitude, pushing the softmax function into regions with extremely small gradients.

3. Multi-Head Attention
Rather than performing a single attention function, Multi-Head Attention projects the queries, keys, and values h times with different, learned linear projections. This allows the model to jointly attend to information from different representation subspaces at different positions:
  MultiHead(Q, K, V) = Concat(head_1, ..., head_h) * W_O
where head_i = Attention(Q * W_Q_i, K * W_K_i, V * W_V_i). This concept is also widely utilized in retrieval-augmented systems to rank relevant passages.

4. Overlapping Concepts and RAG Systems
Attention maps serve as the foundational mechanism for matching query vectors against document collections. In modern Retrieval-Augmented Generation (RAG) systems, we compute similarity scores between user query embeddings and vector databases (such as FAISS) in a manner analogous to scaled dot-product attention. This enables precise document context retrieval.

5. References
[1] Vaswani, A., et al. (2017). "Attention is All You Need." Advances in Neural Information Processing Systems.
[2] Devlin, J., et al. (2018). "BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding." arXiv preprint.
[3] Radford, A., et al. (2019). "Language Models are Unsupervised Multitask Learners." OpenAI Blog.
"""
    },
    {
        "filename": "neural_network_foundations.txt",
        "title": "A Review of Neural Network Architectures and Backpropagation",
        "text": """Title: A Review of Neural Network Architectures and Backpropagation
Author: Prof. Marcus Chen, Department of Computer Science
Date: March 2026

Abstract:
This work traces the development of neural network architectures from simple Multi-Layer Perceptrons (MLPs) to deep Convolutional and Recurrent neural networks. We examine the math of backpropagation and highlight structural commonalities like feed-forward blocks that remain relevant in modern architectures, including Transformers.

1. Multi-Layer Perceptrons (MLPs) and Activation Functions
Deep learning begins with the Multi-Layer Perceptron (MLP), a feed-forward network consisting of an input layer, one or more hidden layers, and an output layer. Each layer applies a linear transformation followed by a non-linear activation function. Historically, sigmoidal functions were utilized, but modern deep networks employ Rectified Linear Units (ReLU) or Gaussian Error Linear Units (GeLU) to combat vanishing gradients.
  ReLU(x) = max(0, x)
  GeLU(x) = x * Phi(x)
where Phi(x) is the cumulative distribution function of the standard normal distribution.

2. Backpropagation and the Chain Rule
Training deep neural networks is formulated as minimizing a loss function L with respect to network weights W. This optimization is carried out using gradient descent, where gradients are computed via the backpropagation algorithm. Backpropagation is a direct application of the calculus chain rule, propagating error signals backward from the output layer to the input. For a weight w_ij connecting neuron i to neuron j:
  d L / d w_ij = (d L / d a_j) * (d a_j / d z_j) * (d z_j / d w_ij)
This mathematical foundation is identical across all architectures, whether they are Convolutional Neural Networks (CNNs) processing images or self-attention networks processing text sequences.

3. Transformer Integration
Modern Transformer blocks contain two sub-layers: a multi-head self-attention mechanism and a position-wise fully connected feed-forward network (MLP). Thus, understanding the foundations of standard feed-forward networks is essential to analyzing Transformer scaling laws. The integration of layer normalization and residual connections stabilizes this backpropagation of gradients in networks with hundreds of layers.

4. References
[1] Rumelhart, D. E., et al. (1986). "Learning representations by back-propagating errors." Nature.
[2] Goodfellow, I., et al. (2016). "Deep Learning." MIT Press.
[3] LeCun, Y., et al. (2015). "Deep learning." Nature.
"""
    },
    {
        "filename": "few_shot_learning_paradigms.txt",
        "title": "Optimizing Few-Shot Learning in Large Language Models",
        "text": """Title: Optimizing Few-Shot Learning in Large Language Models
Author: Sarah Jenkins, Cognitive Computing Lab
Date: February 2026

Abstract:
This paper investigates few-shot learning paradigms in large scale language models. We explore how models adapt to downstream tasks at inference time using in-context learning examples, contrasting this against parametric fine-tuning methods. We discuss prompt construction strategies to optimize few-shot retrieval templates.

1. Introduction to Few-Shot Learning
Few-shot learning refers to a model's ability to generalize and perform a new task after seeing only a handful of demonstration examples. Unlike classical supervised learning which requires thousands of training samples, human-like few-shot learning is highly sample-efficient. In natural language processing, this is achieved through In-Context Learning (ICL) without updating any underlying model parameters.

2. In-Context Learning vs. Parameter Fine-Tuning
When a large language model (e.g., GPT-4) is given a prompt containing a task description and a few input-output demonstrations, it performs the task by predicting the continuation of the prompt. This meta-learning capability arises from pre-training on diverse text corpora.
However, in-context learning is constrained by the context window limit of the model. If a task requires broad domain knowledge, fitting examples within the prompt becomes impossible. In these scenarios, Retrieval-Augmented Generation (RAG) systems are deployed. RAG dynamically retrieves the most relevant few-shot context examples from a FAISS vector store, combining the best of in-context few-shot learning and vector search.

3. Designing Effective Few-Shot Prompts
The performance of few-shot learning is highly sensitive to the prompt structure. Important prompt engineering considerations include:
- The order of the examples: Models exhibit "recency bias", focusing more on later examples.
- The format: Clear boundaries using markdown or special tokens.
- Relevance: Using semantic search to fetch examples that are semantically close to the target query.

4. References
[1] Brown, T., et al. (2020). "Language Models are Few-Shot Learners." NeurIPS.
[2] Vinyals, O., et al. (2016). "Matching Networks for One Shot Learning." NeurIPS.
[3] Ravi, S., & Larochelle, H. (2017). "Optimization as a Model for Few-Shot Learning." ICLR.
"""
    },
    {
        "filename": "language_model_finetuning.txt",
        "title": "Parameter-Efficient Techniques in Language Model Fine-Tuning",
        "text": """Title: Parameter-Efficient Techniques in Language Model Fine-Tuning
Author: Dr. Kenji Sato, Tokyo Advanced Tech
Date: May 2026

Abstract:
Fine-tuning large language models on specialized domains often results in catastrophic forgetting and high computational overhead. This paper reviews Parameter-Efficient Fine-Tuning (PEFT) methods, focusing on Low-Rank Adaptation (LoRA) and prefix tuning, and explores their integration into active retrieval systems.

1. The Necessity of Fine-Tuning
While pre-trained language models possess broad general capabilities, they frequently require specialization to perform task-specific workflows. Traditional full-parameter fine-tuning updates all parameters of the model, which is computationally expensive and requires significant GPU memory. Additionally, it risks catastrophic forgetting, where the model loses its general reasoning capabilities.

2. Low-Rank Adaptation (LoRA)
Low-Rank Adaptation (LoRA) freezes the pre-trained model weights and injects trainable rank decomposition matrices into each layer of the Transformer architecture. For a pre-trained weight matrix W_0 in R^{d x k}, LoRA represents its update delta W as the product of two low-rank matrices B and A:
  W = W_0 + delta W = W_0 + B * A
where B is in R^{d x r}, A is in R^{r x k}, and the rank r << min(d, k). This reduces the number of trained parameters by up to 99% while maintaining comparable task performance.

3. PEFT in RAG Systems
A common debate in AI architecture is whether to fine-tune a model on private data or use a Retrieval-Augmented Generation (RAG) pipeline. Fine-tuning embeds knowledge directly into the weights of the model, whereas RAG fetches document chunks dynamically using vector similarity engines like FAISS. Combining PEFT fine-tuning (for style and tone adaptation) with RAG systems (for factual knowledge retrieval) represents the state-of-the-art hybrid approach.

4. References
[1] Hu, E. J., et al. (2021). "LoRA: Low-Rank Adaptation of Large Language Models." arXiv preprint.
[2] Houlsby, N., et al. (2019). "Parameter-Efficient Transfer Learning for NLP." ICML.
[3] Lester, B., et al. (2021). "The Power of Scale for Parameter-Efficient Prompt Tuning." EMNLP.
"""
    },
    {
        "filename": "rag_system_architectures.txt",
        "title": "Design Principles of Retrieval-Augmented Generation (RAG) Systems",
        "text": """Title: Design Principles of Retrieval-Augmented Generation (RAG) Systems
Author: David Miller, Systems Architect, DataGen Corp
Date: April 2026

Abstract:
Retrieval-Augmented Generation (RAG) addresses the inherent limitations of large language models, such as hallucinations and static knowledge boundaries. We analyze the components of a robust RAG architecture, including text chunking strategies, dense retrieval vector stores, and prompt-context integration.

1. Introduction to RAG
Large Language Models (LLMs) are limited by their training cutoff dates and can generate inaccurate info (hallucinations) when asked about private or niche topics. Retrieval-Augmented Generation (RAG) solves this by fetching relevant document passages from a local corpus and injecting them into the LLM prompt as context.

2. Document Ingestion and Chunking
The RAG pipeline begins with document ingestion. Large PDFs or TXT files are parsed and split into smaller chunks. Chunking is a crucial step; if chunks are too small, they lack context, and if they are too large, they exceed the LLM's attention span and dilute the retrieval signal. A standard chunk size is 500 characters with a 50 character overlap, split recursively using paragraph and sentence boundaries.

3. Dense Vector Search and FAISS
Each text chunk is mapped to a vector embedding space using an encoder like sentence-transformers (`all-MiniLM-L6-v2`). These embeddings are indexed in a vector store like FAISS (Facebook AI Similarity Search) to support fast L2 distance or cosine similarity queries.
Given a user query, the RAG system embeds the query, searches the FAISS index for top-k matches, fetches the corresponding text chunks, and structures a prompt:
  "Answer the query based ONLY on the following context: [Context Chunks]"
This ensures the LLM's response is grounded in actual data.

4. References
[1] Lewis, P., et al. (2020). "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks." NeurIPS.
[2] Johnson, J., et al. (2019). "Billion-scale similarity search with GPUs." IEEE Transactions on Big Data.
[3] Karpukhin, V., et al. (2020). "Dense Passage Retrieval for Open-Domain Question Answering." EMNLP.
"""
    },
    {
        "filename": "prompt_engineering_reasoning.txt",
        "title": "Advanced Prompt Engineering for Complex Reasoning",
        "text": """Title: Advanced Prompt Engineering for Complex Reasoning
Author: Elena Rostova, Center for Human-AI Interaction
Date: July 2026

Abstract:
Prompt engineering has evolved from basic heuristic templates to programmatic prompt execution frameworks. This paper analyzes techniques such as Chain-of-Thought (CoT) and Tree-of-Thoughts (ToT) prompting, exploring how structured reasoning guidelines improve few-shot and zero-shot performance in language models.

1. The Evolution of Prompts
In early LLMs, prompts were simple instruction strings. As models scaled, researchers discovered that structuring instructions dramatically improved performance. Prompt engineering is now recognized as a core mechanism for directing the attention of Transformer models during inference.

2. Chain-of-Thought (CoT) Prompting
Chain-of-Thought prompting encourages the model to generate intermediate reasoning steps before outputting the final answer. By explicitly writing out its reasoning (e.g., "Let's think step by step"), the model leverages its autoregressive generation capabilities to build a logical path to the correct conclusion. CoT is closely related to few-shot prompting, as providing a few examples of step-by-step reasoning guides the model to adopt a similar structured formatting.

3. Retrieval-Context Prompting in RAG
In RAG systems, prompt engineering is vital to direct how the model interacts with retrieved contexts. For instance, a system prompt might instruct the LLM:
- "If the context does not contain the answer, state that you do not know."
- "Cite the document name when referencing facts."
This prevents hallucinations and maintains factual alignment.

4. References
[1] Wei, J., et al. (2022). "Chain-of-Thought Prompting Elicits Reasoning in Large Language Models." NeurIPS.
[2] Yao, S., et al. (2023). "Tree of Thoughts: Deliberate Problem Solving with Large Language Models." arXiv preprint.
[3] Kojima, T., et al. (2022). "Large Language Models are Zero-Shot Reasoners." NeurIPS.
"""
    },
    {
        "filename": "transformer_evolution.txt",
        "title": "The Evolution of Transformer-based Encoder-Decoder Architectures",
        "text": """Title: The Evolution of Transformer-based Encoder-Decoder Architectures
Author: Alex Dupont, DeepLearning Research Lab
Date: June 2026

Abstract:
Since the seminal work of Vaswani et al. (2017), the Transformer model has undergone numerous modifications. We trace the structural evolution of encoder-only, decoder-only, and encoder-decoder models, discussing the adoption of Rotary Position Embeddings (RoPE) and layer normalization schemes.

1. Encoder-Only vs. Decoder-Only Models
The original Transformer architecture comprised an encoder to process the input source and a decoder to generate the target sequence. Over time, architectures branched:
- Encoder-Only (e.g., BERT): Focuses on bidirectional context representation. Highly effective for classification, embedding extraction, and text chunk tagging.
- Decoder-Only (e.g., GPT series): Focuses on autoregressive next-token prediction, utilizing causal masking to prevent attention from looking at future tokens. This is the dominant architecture for generative chat models.

2. Positional Encodings and Attention Scales
Transformers lack inherent awareness of token sequence order due to the permutation invariance of self-attention. Early models used absolute sinusoidal positional encodings. Modern architectures utilize Rotary Position Embeddings (RoPE), which encode relative positions by multiplying key and query vectors with rotation matrices. This enables stable context window scaling.

3. Similarity Search and Embeddings
Encoder-only models remain the preferred choice for generating dense vector embeddings. Models like `all-MiniLM-L6-v2` extract the hidden states of the encoder and pool them to create fixed-size vectors for semantic similarity search in tools like FAISS.

4. References
[1] Vaswani, A., et al. (2017). "Attention is All You Need." NeurIPS.
[2] Su, J., et al. (2021). "RoFormer: Enhanced Transformer with Rotary Position Embedding." arXiv preprint.
[3] Raffel, C., et al. (2020). "Exploring the Limits of Transfer Learning with a Unified Text-to-Text Transformer." JMLR.
"""
    },
    {
        "filename": "combating_hallucinations_rag.txt",
        "title": "Addressing Hallucinations in LLMs via Vector Search Pipelines",
        "text": """Title: Addressing Hallucinations in LLMs via Vector Search Pipelines
Author: Sophia Lopez, Trustworthy AI Consortium
Date: August 2026

Abstract:
Large language models are prone to generating fictitious details, commonly known as hallucinations. This paper explores how dense vector search engines, combined with strict prompt engineering guardrails, mitigate hallucination rates by grounding generation in verifiable external database chunks.

1. Understanding Hallucinations
A hallucination occurs when an LLM generates text that is grammatically correct and semantically plausible but factually incorrect or unsupported by the training data. This stems from the model's nature as a probabilistic next-token predictor, rather than a factual lookup database.

2. Mitigating Hallucinations with Vector Stores
By coupling an LLM with a vector search database (like FAISS), we create a Retrieval-Augmented Generation (RAG) pipeline. When a user queries the model, the system first retrieves matching paragraphs using sentence embedding models (`all-MiniLM-L6-v2`). The prompt then constrains the model's generation space:
"Context: [Retrieved Passages]
Question: [User Query]
Answer the question using only the context provided above. If the context does not contain the answer, say 'I cannot find the answer in the source documents.' Do not extrapolate."
This limits the model's creative decoding, reducing hallucinations.

3. Metrics and Evaluation
Hallucination rates are evaluated using retrieval accuracy metrics, precision scores, and context relevance checks. Implementing semantic search as the first step guarantees that the model has access to relevant historical data before generation begins.

4. References
[1] Lewis, P., et al. (2020). "Retrieval-Augmented Generation for Knowledge-Intensive Tasks." NeurIPS.
[2] Shuster, K., et al. (2021). "Retrieval Augmentation Reduces Hallucination in Conversation." arXiv preprint.
[3] Ji, Z., et al. (2023). "Survey of Hallucination in Natural Language Processing." ACM Computing Surveys.
"""
    },
    {
        "filename": "meta_learning_few_shot.txt",
        "title": "Meta-Learning and Few-Shot Learning Paradigms",
        "text": """Title: Meta-Learning and Few-Shot Learning Paradigms
Author: Dr. Robert H., Advanced Intelligent Systems
Date: September 2026

Abstract:
Meta-learning, or "learning to learn," aims to design neural models that can adapt to novel tasks with minimal training data. We analyze optimization-based meta-learning algorithms and contrast them with prompt-based few-shot learning in multi-billion parameter autoregressive language models.

1. Optimization-based Meta-Learning
Traditional meta-learning algorithms like Model-Agnostic Meta-Learning (MAML) focus on learning a parameter initialization that is highly sensitive to changes in task distribution. Given a new task, a few gradient descent updates on a tiny support set allow the model to generalize rapidly.
  theta_prime = theta - alpha * grad_theta( Loss_task_i ( f_theta ) )
This requires calculating second-order derivatives, making training computationally intensive.

2. In-Context Few-Shot Learning in Transformers
With the emergence of large language models, few-shot learning has transitioned from gradient-based updates to in-context prompt prompting. The model parameters are kept completely frozen. Instead, the model relies on its self-attention layers to identify patterns in the provided demonstrations (few-shot context examples) and replicate them in the generated completion.

3. Combining Meta-Learning with Dense Retrieval
In active knowledge assistant applications, selecting the optimal few-shot examples is critical. Rather than using static examples, systems utilize FAISS vector stores to dynamically query and retrieve few-shot matches that are semantically similar to the current user input.

4. References
[1] Finn, C., et al. (2017). "Model-Agnostic Meta-Learning for Fast Adaptation of Deep Networks." ICML.
[2] Snell, J., et al. (2017). "Prototypical Networks for Few-shot Learning." NeurIPS.
[3] Brown, T., et al. (2020). "Language Models are Few-Shot Learners." NeurIPS.
"""
    },
    {
        "filename": "parameter_efficient_tuning.txt",
        "title": "Low-Rank Adaptation and Parameter-Efficient Tuning Strategies",
        "text": """Title: Low-Rank Adaptation and Parameter-Efficient Tuning Strategies
Author: Mei-Ling Zhang, Stanford Artificial Intelligence Lab
Date: October 2026

Abstract:
As deep learning models continue to grow, full fine-tuning becomes increasingly impractical. We evaluate Parameter-Efficient Fine-Tuning (PEFT) methods, with a focus on Low-Rank Adaptation (LoRA). We analyze training dynamics, computational savings, and parameter rank selection.

1. Introduction to PEFT
Parameter-Efficient Fine-Tuning (PEFT) aims to adapt pre-trained models to specific downstream tasks while modifying only a tiny subset of the model's parameters. This approach preserves the model's general intelligence and reduces storage requirements, as a single base model can share multiple small task-specific adapters.

2. Low-Rank Adaptation (LoRA) Mechanics
LoRA is based on the hypothesis that weight updates in deep neural networks have a low "intrinsic dimension". During adaptation, the update delta W is factorized into two low-rank matrices A and B:
  delta W = B * A
For a base dimension d=4096 and rank r=8, the number of updated parameters drops from millions to a few thousand. In practice, LoRA adapters are applied to the Query, Key, and Value projection weight matrices in the Transformer's self-attention block, allowing the model to adapt its attention patterns to target styles.

3. Integration with Local Databases
PEFT-tuned models are commonly paired with RAG pipelines. While the LoRA adapter fine-tunes the model's stylistic expression and formatting capability, the FAISS index database serves as the source of dynamic, factual context, creating a high-performance system for knowledge management.

4. References
[1] Hu, E. J., et al. (2021). "LoRA: Low-Rank Adaptation of Large Language Models." arXiv preprint.
[2] Li, X. L., & Liang, P. (2021). "Prefix-Tuning: Optimizing Continuous Prompts for Generation." ACL.
[3] He, J., et al. (2021). "Towards a Unified View of Parameter-Efficient Transfer Learning." ICLR.
"""
    },
    {
        "filename": "hybrid_retrieval_models_rag.txt",
        "title": "Hybrid Retrieval Models in Modern RAG Architecture",
        "text": """Title: Hybrid Retrieval Models in Modern RAG Architecture
Author: Dr. Jonathan Ross, Information Retrieval Group
Date: November 2026

Abstract:
Dense vector search retrieves documents based on semantic meaning, but often misses specific keyword terms. This paper explores hybrid retrieval systems that combine sparse lexical models (such as BM25) with dense embedding models (like FAISS) to maximize both semantic and keyword matching accuracy in RAG systems.

1. Sparse vs. Dense Retrieval
Traditional search systems rely on sparse lexical retrieval algorithms like BM25, which match exact keyword terms using term frequency-inverse document frequency formulas. While fast and effective for precise queries, BM25 fails when users search using synonyms or concepts not explicitly written in the corpus.
In contrast, dense retrieval encodes sentences into dense vector spaces using models like `all-MiniLM-L6-v2`. Similarity is measured using vector distance (e.g., L2 distance in FAISS). Dense retrieval excels at capturing semantic intent, but can fail when queries contain specific serial numbers, names, or codes.

2. Hybrid Retrieval Integration
A hybrid retrieval model runs both sparse and dense queries in parallel, combining the results. Reciprocal Rank Fusion (RRF) is typically used to merge the document rankings:
  RRF_Score(d) = sum_{m in Models} 1 / (60 + Rank_m(d))
The top scoring documents are retrieved, chunked, and formatted into the final LLM prompt context, reducing context mismatch.

3. References
[1] Robertson, S., et al. (2009). "The Probabilistic Relevance Framework: BM25 and Beyond." Information Retrieval.
[2] Karpukhin, V., et al. (2020). "Dense Passage Retrieval for Open-Domain Question Answering." EMNLP.
[3] Bendersky, M., et al. (2021). "Integrating Sparse and Dense Search in Information Retrieval." ACM SIGIR.
"""
    },
    {
        "filename": "scalability_faiss_vector_stores.txt",
        "title": "Scalability and Optimization of FAISS Vector Stores",
        "text": """Title: Scalability and Optimization of FAISS Vector Stores
Author: Clara Engel, Distributed Systems Lab
Date: December 2026

Abstract:
Scaling vector search to millions of document chunks requires optimized index selection. This paper reviews indexing strategies in the FAISS framework, analyzing the trade-offs between search latency, indexing speed, and memory consumption under L2 and inner-product distance metrics.

1. Vector Search Bottlenecks
As a corpus grows, comparing a query embedding against every document vector (flat indexing) becomes computationally prohibitive, taking O(N) time. To support sub-millisecond search times, vector indexes must partition the vector space or compress the vectors.

2. FAISS Index Types
FAISS provides several indexing strategies:
- IndexFlatL2: Calculates the exact Euclidean distance. Highly accurate but requires O(N) search time and keeps all vectors in RAM.
- IndexIVFFlat (Inverted File Index): Partitions the vector space into voronoi cells. During search, only vectors in the closest cells are evaluated, reducing search time to O(sqrt(N)).
- Product Quantization (PQ): Compresses vectors into short codes, reducing memory footprints by up to 90% at the cost of slight search accuracy loss.

3. Application in Knowledge Guardian
For a local study assistant, the document index is typically small (thousands of chunks), making IndexFlatL2 the optimal choice due to its high precision and fast build time. As the user uploads more PDFs and TXT files, the store utilizes python serialization to persist this index to disk (`knowledge_index.faiss`) for fast reloads on server startup.

4. References
[1] Johnson, J., Douze, M., & Jégou, H. (2019). "Billion-scale similarity search with GPUs." IEEE Transactions on Big Data.
[2] Jégou, H., et al. (2010). "Product Quantization for Nearest Neighbor Search." IEEE Transactions on Pattern Analysis and Machine Intelligence.
"""
    },
    {
        "filename": "attention_retrospective.txt",
        "title": "Attention is All You Need: A Retrospective Analysis",
        "text": """Title: Attention is All You Need: A Retrospective Analysis
Author: Prof. Linda Zhao, Dept of Data Sciences
Date: January 2026

Abstract:
Almost a decade after the introduction of the Transformer architecture, we evaluate its structural core: self-attention. We trace how this single mathematical concept revolutionized machine learning, replaced recurrent LSTMs, and laid the groundwork for today's RAG systems.

1. The Paradigm Shift
The key contribution of Vaswani et al. (2017) was replacing recurrent connections with self-attention. LSTMs processed tokens step-by-step, meaning the gradients had to flow back through time, leading to vanishing or exploding gradients. Self-attention links all tokens in a single operation, reducing the path length for gradient flow to O(1).

2. Self-Attention Mechanics
Self-attention models the relationships between all pairs of tokens in a sequence. For queries Q, keys K, and values V:
  Attention(Q, K, V) = softmax( Q * K^T / sqrt(d_k) ) * V
This calculation allows each token to build a contextual representation based on the entire sequence. In RAG pipelines, this same dot-product approach maps user query vectors against the keys (document embeddings) in a database.

3. References
[1] Vaswani, A., et al. (2017). "Attention is All You Need." NeurIPS.
[2] Bahdanau, D., et al. (2014). "Neural Machine Translation by Jointly Learning to Align and Translate." arXiv preprint.
[3] Sutskever, I., et al. (2014). "Sequence to Sequence Learning with Neural Networks." NeurIPS.
"""
    },
    {
        "filename": "prompt_guardrails.txt",
        "title": "System Prompts and Safety Guardrails in Prompt Engineering",
        "text": """Title: System Prompts and Safety Guardrails in Prompt Engineering
Author: Dr. Gregory Ross, Ethics and Safety in AI
Date: February 2026

Abstract:
This work discusses prompt guardrails designed to prevent adversarial jailbreaking and model output misalignment. We evaluate the structure of system prompts, constraint enforcement, and the inclusion of retrieved vector store contexts in maintaining grounding.

1. System Prompts and User Input
In modern LLM API calls, prompts are split into roles: system prompts (which define the model's persona and rules) and user prompts (which contain the current query). System prompts are given higher priority during instruction tuning, directing the model's attention to formatting and safety rules.

2. Jailbreaking and Prompt Injection
Adversarial users try to bypass system constraints through prompt injection, convincing the model to ignore safety rules (e.g., "Ignore all previous instructions and do X"). To counter this, prompt engineering implements strict boundaries, placing retrieved documents in isolated blocks and instructing the model:
"Analyze the user query based solely on the documents provided in the [Context] tags."

3. Vector Grounding
Grounding the prompt in retrieved vector chunks (e.g., from a FAISS index) is the most effective way to enforce safety. If the model is constrained to only answer from the provided context, it is much less likely to respond to malicious, out-of-domain prompt injection queries.

4. References
[1] Perez, F., & Ribeiro, M. T. (2022). "Ignore Previous Instructions: Template Injection Attacks on LLMs." arXiv preprint.
[2] Wei, A., et al. (2023). "Jailbroken: How Does LLM Alignment Fail?" arXiv preprint.
[3] Carlini, N., et al. (2021). "Extracting Training Data from Large Language Models." USENIX Security.
"""
    },
    {
        "filename": "deep_learning_backpropagation.txt",
        "title": "Deep Learning Foundations: Neural Networks and Backpropagation Dynamics",
        "text": """Title: Deep Learning Foundations: Neural Networks and Backpropagation Dynamics
Author: Prof. Albert Yang, Deep Learning Institute
Date: November 2025

Abstract:
We present a mathematical review of gradient flow and backpropagation dynamics in deep neural networks. We examine the effects of weight initialization on training stability and connect these concepts to the optimization of multi-head attention weights in Transformers.

1. Neural Networks as Function Approximators
Neural networks are parameter-rich mathematical functions designed to approximate target distributions. They consist of layers of nodes, where each layer performs a matrix multiplication and applies a non-linear activation. Training updates these weight matrices to minimize an error function.

2. Backpropagation and Optimization
Optimization utilizes the gradient of a loss function with respect to each weight. Backpropagation computes these gradients by working backward from the output layer, recursively applying the chain rule of calculus. If the model weights are initialized poorly, gradients can either vanish (become zero) or explode (become infinitely large), stalling training. Modern techniques like layer normalization and residual links solve this, enabling stable training of 100+ layer architectures.

3. References
[1] He, K., et al. (2015). "Delving Deep into Rectifiers: Surpassing Human-Level Performance on ImageNet Classification." ICCV.
[2] Glorot, X., & Bengio, Y. (2010). "Understanding the difficulty of training deep feedforward neural networks." AISTATS.
[3] Kingma, D. P., & Ba, J. (2014). "Adam: A Method for Stochastic Optimization." arXiv preprint.
"""
    }
]

def generate_data():
    test_data_dir = BACKEND_DIR / "test_data"
    os.makedirs(test_data_dir, exist_ok=True)
    print("=" * 60)
    print(f"Generating Synthetic Research Papers under {test_data_dir}")
    print("=" * 60)

    for i, paper in enumerate(PAGES):
        file_path = test_data_dir / paper["filename"]
        # Ensure correct word counts (approx 500 words)
        word_count = len(paper["text"].split())
        print(f"[{i+1}/{len(PAGES)}] Writing: {paper['filename']} ({word_count} words)")
        
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(paper["text"])
            
    print(f"\n🎉 Successfully generated {len(PAGES)} synthetic research papers in {test_data_dir}!")

if __name__ == "__main__":
    generate_data()
