# Research Copilot Agent

A full-featured research and knowledge assistant that provides summarization, Q&A, PDF/Arxiv/web extraction, dynamic routing between [Wikipedia](https://en.wikipedia.org/wiki/Main_Page) and [OpenDeepSearch](https://github.com/sentient-agi/OpenDeepSearch), and includes a modern UI for ease of use.

**Easily integrates into sentient chat and other agent orchestration tools.**

---

## Features

- 🔍 Intelligent query routing (Wikipedia for facts, OpenDeepSearch for real-time data)
- 📄 PDF and ArXiv paper extraction
- 🌐 Web scraping and content extraction
- 💬 Chat-based UI for easy interaction
- 🤖 Built on [Sentient Agent Framework](https://github.com/sentient-agi/Sentient-Agent-Framework)

---

## Core Dependencies

- [OpenDeepSearch](https://github.com/sentient-agi/OpenDeepSearch)
  - My setup: [opnsrchsentient](https://github.com/kasnadoona5/opnsrchsentient)
- [Sentient Agent Framework](https://github.com/sentient-agi/Sentient-Agent-Framework)
- Python 3.11+
- `httpx`, `python-dotenv`, `arxiv`, `pdfplumber`, `trafilatura`

---

## Installation Steps

### 1. System Preparation

Install required system packages:

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install software-properties-common -y
sudo add-apt-repository ppa:deadsnakes/ppa -y
sudo apt update
sudo apt install python3.11 python3.11-venv python3.11-dev python3.11-distutils python3-pip git nginx -y
python3.11 --version
```

### 2. Prepare Project Directory

Clone this repository directly into `/opt/research-copilot-agent` (folder name can be different locally):

```bash
sudo mkdir -p /opt/research-copilot-agent
sudo chown $USER:$USER /opt/research-copilot-agent
cd /opt/research-copilot-agent
python3.11 -m venv venv
source venv/bin/activate
git clone https://github.com/kasnadoona5/Sentient-research-copilot-agent.git .
ls
```

**Verify:** Files like `app.py`, `index.html`, `requirements.txt`, `document_loader.py`, etc. should be directly inside `/opt/research-copilot-agent`.

### 3. Install Python Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

**Fallback:** If `requirements.txt` is missing (shouldn't be):

```bash
pip install sentient-agent-framework httpx python-dotenv arxiv pdfplumber trafilatura
```

### 4. Configure Environment Variables Securely

**⚠️ Never upload your `.env` to GitHub!**

Copy the provided template and fill in your secrets:

```bash
cp .env.example .env
nano .env  # Fill in your real API credentials on your own server ONLY
```

Sample for `.env.example` (already in the repo):

```env
OPENROUTER_API_KEY=your_api_key_here
ODP_API_URL=http://localhost:8000/search-alt
ODP_API_KEY=your_odp_key
ODP_SERPER_KEY=your_serper_key
```

**Important:** Do not upload `.env` to the repo!

### 5. Test Local Run

Verify the application starts correctly:

```bash
source venv/bin/activate
python3 app.py
```

Application should start without errors. Press Ctrl+C to stop after verification.

### 6. Configure nginx

Set up nginx to serve the UI and proxy API requests:

```bash
sudo nano /etc/nginx/sites-available/default
```

Replace the entire server block with:

```nginx
server {
    listen 80;
    server_name _;
    
    root /opt/research-copilot-agent;
    index index.html;
    
    location / {
        try_files $uri $uri/ /index.html;
    }
    
    location /assist {
        proxy_pass http://127.0.0.1:8000/assist;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Test and reload nginx:

```bash
sudo nginx -t
sudo systemctl reload nginx
```

### 7. Deploy as systemd Service (Production)

Create the systemd service file:

```bash
sudo nano /etc/systemd/system/copilot-agent.service
```

Paste the following configuration:

```ini
[Unit]
Description=Research Copilot Agent
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/research-copilot-agent
ExecStart=/bin/bash -c 'source /opt/research-copilot-agent/venv/bin/activate && python3 app.py'
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

> **Note:** Change `User=root` to your username if preferred (use `whoami` to find it).

Enable and start the service:

```bash
sudo systemctl daemon-reload
sudo systemctl enable copilot-agent
sudo systemctl start copilot-agent
sudo systemctl status copilot-agent
```

### 8. Access Your Application

Open your browser and navigate to:

```
http://YOUR_SERVER_IP/
```

✅ Copilot UI loads  
✅ All API/chat works via `/assist` proxied through nginx

---

## Viewing Logs

Monitor the service in real-time:

```bash
sudo journalctl -u copilot-agent -f
```

View recent logs:

```bash
sudo journalctl -u copilot-agent -n 100
```

---

## Stopping/Restarting the Service

```bash
# Stop the service
sudo systemctl stop copilot-agent

# Restart the service
sudo systemctl restart copilot-agent

# Check status
sudo systemctl status copilot-agent
```


---
### View Logs

```bash
sudo journalctl -u copilot-agent -f
```

---

## Architecture

The agent uses an LLM to intelligently route queries:

- **Wikipedia**: Factual queries like "Who is...?" or "What is...?"
- **OpenDeepSearch**: Real-time data like "BTC price now", "Latest news", "Product reviews"

Built on the [Sentient Agent Framework](https://github.com/sentient-agi/Sentient-Agent-Framework) for async agent operations, with a chat-like UI that can plug into any agent framework.

---

## Related Projects

- **This repo**: [kasnadoona5/research-copilot-agent](https://github.com/kasnadoona5/sentient-research-copilot-agent)
- **OpenDeepSearch**: [sentient-agi/OpenDeepSearch](https://github.com/sentient-agi/OpenDeepSearch)
- **ODP Deployment Example**: [kasnadoona5/opnsrchsentient](https://github.com/kasnadoona5/opnsrchsentient)
- **Sentient Agent Framework**: [sentient-agi/Sentient-Agent-Framework](https://github.com/sentient-agi/Sentient-Agent-Framework)

---


