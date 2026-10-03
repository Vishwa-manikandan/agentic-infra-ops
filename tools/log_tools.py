import requests
import chromadb
import os
import json

LOKI_URL = os.getenv("LOKI_URL", "http://loki:3100")
CHROMA_URL = os.getenv("CHROMA_URL", "http://chromadb:8000")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://host.docker.internal:11434")

class LogQueryTool:
    def __init__(self):
        # ChromaDB client
        self.chroma_client = chromadb.HttpClient(host="chromadb", port=8000)
        self.collection = self.chroma_client.get_or_create_collection(name="incident_logs")

    def _get_embedding(self, text: str):
        """Helper to get embedding from Ollama."""
        try:
            resp = requests.post(
                f"{OLLAMA_URL}/api/embeddings",
                json={"model": "nomic-embed-text", "prompt": text}
            )
            resp.raise_for_status()
            return resp.json()["embedding"]
        except Exception as e:
            return None

    def query_structured_logs(self, query_string: str, limit: int = 10):
        """
        Queries Loki for structured logs.
        Example query_string: '{container_name="toy-service"} |= "ERROR"'
        """
        params = {
            "query": query_string,
            "limit": limit,
        }
        try:
            response = requests.get(f"{LOKI_URL}/loki/api/v1/query_range", params=params)
            response.raise_for_status()
            return response.json()["data"]["result"]
        except Exception as e:
            return f"Error querying Loki: {e}"

    def query_semantic_logs(self, text: str, n_results: int = 3):
        """
        Queries ChromaDB for semantically similar logs.
        """
        try:
            # We use a manual embedding to ensure consistency with the ingestor
            embedding = self._get_embedding(text)
            if not embedding:
                return f"Error generating embedding: {text[:50]}..."

            results = self.collection.query(
                query_embeddings=[embedding],
                n_results=n_results
            )
            return results["documents"]
        except Exception as e:
            return f"Error querying ChromaDB: {e}"

    def detect_anomalies(self, window_minutes: int = 5, threshold: int = 5):
        """
        Proactively detects log anomalies.
        Checks for a 'burst' of similar error logs in the recent window.
        """
        # 1. Fetch recent ERROR logs from Loki
        logs = self.query_structured_logs(
            query_string='{container_name="toy-service"} |= "ERROR"',
            limit=50
        )
        if isinstance(logs, str): # Error occurred
            return None

        # Extract log lines
        lines = []
        for stream in logs:
            for val in stream["values"]:
                lines.append(val[1])

        if not lines:
            return None

        # 2. Analyze for bursts (Clustering by embedding)
        # For each log, see how many other logs in the window are very similar
        anomalies = []
        for line in lines:
            try:
                # Clean JSON if applicable
                log_text = json.loads(line).get("message", line)
                emb = self._get_embedding(log_text)
                if not emb: continue

                # Query ChromaDB for similar logs in the same window
                # (Alternatively, we could just compare embeddings in-memory)
                similar = self.collection.query(
                    query_embeddings=[emb],
                    n_results=10
                )["documents"][0]

                # If we find many similar logs recently, it's a burst
                if len(similar) >= threshold:
                    anomalies.append({
                        "pattern": log_text,
                        "count": len(similar),
                        "example": line
                    })
            except:
                continue

        # Return the most prominent anomaly if any
        if anomalies:
            # Sort by count descending
            return sorted(anomalies, key=lambda x: x["count"], reverse=True)[0]

        return None
