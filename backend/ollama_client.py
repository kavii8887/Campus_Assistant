import requests


class OllamaClient:
    def __init__(self, embedding_model="nomic-embed-text", llm_model="mistral:7b-instruct"):
        self.embedding_model = embedding_model
        self.llm_model = llm_model
        self.embed_endpoint = "http://localhost:11434/api/embeddings"
        self.generate_endpoint = "http://localhost:11434/api/generate"

    def embed_single(self, text: str):
        r = requests.post(
            self.embed_endpoint,
            json={"model": self.embedding_model, "prompt": text}
        )
        r.raise_for_status()
        return r.json()["embedding"]

    def embed_batch(self, texts):
        embeddings = []
        for t in texts:
            embeddings.append(self.embed_single(t))
        return embeddings

    def get_embedding_dim(self):
        return len(self.embed_single("test"))

    def generate(self, prompt: str) -> str:
        r = requests.post(
            self.generate_endpoint,
            json={
                "model": self.llm_model,
                "prompt": prompt,
                "stream": False
            },
            timeout=180
        )
        r.raise_for_status()
        return r.json()["response"]
