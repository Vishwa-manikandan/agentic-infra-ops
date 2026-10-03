# Cloud Deployment Guide

This guide outlines how to deploy the Agentic Infra-Ops stack to a cloud provider (AWS/GCP).

## ☁️ AWS Deployment (EC2)

### 1. Instance Setup
- **Instance Type**: `t3.medium` (minimum 4GB RAM for Ollama/ChromaDB).
- **OS**: Ubuntu 22.04 LTS.
- **Security Group**: 
  - Open port `8080` (FastAPI)
  - Open port `3000` (Grafana)
  - Open port `9090` (Prometheus)

### 2. Installation
```bash
# Install Docker
sudo apt-get update
sudo apt-get install docker.io docker-compose -y
sudo systemctl start docker
sudo systemctl enable docker

# Clone the repo
git clone <your-repo-url>
cd agentic-infra-ops

# Run the stack
sudo docker compose up --build -d
```

### 3. Ollama Setup
Since Ollama runs as a separate service, install it on the host:
```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama pull llama3.2
ollama pull nomic-embed-text
```

## ☁️ GCP Deployment (Compute Engine)
Same as AWS, using a `e2-standard-2` instance and allowing the same firewall ports.

## ⚠️ Important Considerations
- **Data Persistence**: Use Docker Volumes to ensure `incidents.jsonl` and ChromaDB data persist across restarts.
- **Security**: In a production environment, wrap the FastAPI port behind an Nginx reverse proxy with Basic Auth or OAuth2.
