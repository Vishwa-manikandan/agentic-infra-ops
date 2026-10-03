from chromadb import Client
import requests
import time
import os
import json
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("log-ingestor")

# Environment variables
LOKI_URL = os.getenv("LOKI_URL", "http://loki:3100")
CHROMA_URL = os.getenv("CHROMA_URL", "http://chromadb:8000")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://host.docker.internal:11434")

# Initialize ChromaDB client
import chromadb
chroma_client = chromadb.HttpClient(host=os.getenv("CHROMA_HOST", "chromadb"), port=8000)
collection = chroma_client.get_or_create_collection(name="incident_logs")

def get_ollama_embedding(text):
    """Get embedding for text using Ollama nomic-embed-text model."""
    try:
        response = requests.post(
            f"{OLLAMA_URL}/api/embeddings",
            json={"model": "nomic-embed-text", "prompt": text}
        )
        response.raise_for_status()
        return response.json()["embedding"]
    except Exception as e:
        logger.error(f"Error getting embedding: {e}")
        return None

def fetch_error_logs_from_loki():
    """Fetch ERROR logs from Loki since the last check."""
    # Simplified query for demonstration: fetch logs from last 5 minutes with 'ERROR'
    query = '{container_name="toy-service"} |= "ERROR"'
    params = {
        "query": query,
        "limit": 100,
    }
    try:
        response = requests.get(f"{LOKI_URL}/loki/api/v1/query_range", params=params)
        response.raise_for_status()
        return response.json()["data"]["result"]
    except Exception as e:
        logger.error(f"Error fetching logs from Loki: {e}")
        return []

def main():
    logger.info("Starting log ingestor...")
    while True:
        logger.info("Checking for new error logs...")
        logs = fetch_error_logs_from_loki()

        for log_entry in logs:
            # Loki results are a list of streams, each stream is a list of [timestamp, line]
            for stream in log_entry["values"]:
                timestamp, line = stream
                # Parse the JSON log line
                try:
                    log_data = json.loads(line)
                    if log_data.get("level") == "ERROR":
                        msg = log_data.get("message", "")
                        # Generate embedding
                        embedding = get_ollama_embedding(msg)
                        if embedding:
                            # Store in ChromaDB
                            collection.add(
                                ids=[f"{timestamp}_{random.randint(0,1000)}"],
                                embeddings=[embedding],
                                documents=[line],
                                metadatas=[{"timestamp": timestamp, "level": "ERROR"}]
                            )
                            logger.info(f"Ingested error log: {msg[:50]}...")
                except json.JSONDecodeError:
                    continue

        time.sleep(60) # Poll every minute

if __name__ == "__main__":
    import random
    main()
