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

Install all required system packages:

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install software-properties-common -y
sudo add-apt-repository ppa:deadsnakes/ppa -y
sudo apt update
sudo apt install python3.11 python3.11-venv python3.11-dev python3.11-distutils python3-pip git nginx -y
python3.11 --version
```

### 2. Prepare Project Directory


Create the project directory:

```bash
sudo mkdir -p /opt/research-copilot-agent
sudo chown $USER:$USER /opt/research-copilot-agent
cd /opt/research-copilot-agent
```

Clone the repository into this directory:

```bash
git clone https://github.com/kasnadoona5/Sentient-research-copilot-agent.git .
```

**⚠️ IMPORTANT:** All code files (`app.py`, `requirements.txt`, etc.) should be directly inside `/opt/research-copilot-agent`. 

If they end up in a subfolder (`/opt/research-copilot-agent/Sentient-research-copilot-agent`), fix it with:

```bash
mv Sentient-research-copilot-agent/* Sentient-research-copilot-agent/.[!.]* .
rm -rf Sentient-research-copilot-agent
```

### 3. Python Virtual Environment & Install Complete Dependencies

```bash
python3.11 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install sentient-agent-framework httpx python-dotenv arxiv pdfplumber trafilatura
pip freeze > requirements.txt

```

### 4. Configure Environment Variables Securely


```bash
cp .env.example .env
nano .env  # Fill in your actual API keys (local only)
```

### 5. Test Local Run

```bash
source venv/bin/activate
python3 app.py
```

**Expected:** Should start with no errors.

**⚠️ Troubleshooting:** If you see "can't open file": your `app.py` is in the wrong folder. Move it and all other files directly to `/opt/research-copilot-agent`.

### 6. Configure nginx

Edit the nginx configuration:

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
    proxy_http_version 1.1;
    proxy_buffering off;
    proxy_request_buffering off;
    chunked_transfer_encoding on;
    proxy_read_timeout 360s;
}
}
```

Test and reload nginx:

```bash
sudo nginx -t
sudo systemctl reload nginx
```

**If you see a 403 Forbidden error:**

```bash
sudo chown -R www-data:www-data /opt/research-copilot-agent
sudo chmod -R 755 /opt/research-copilot-agent
sudo systemctl reload nginx
```

### 7. Deploy as systemd Service (Production)

Create the systemd unit file:

```bash
sudo nano /etc/systemd/system/copilot-agent.service
```

Paste this configuration (**with absolutely no comments on the User line**):

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
**User=root** can be different on your system. use **whoami** to find your user.

Enable and start the service:

```bash
sudo systemctl daemon-reload
sudo systemctl enable copilot-agent
sudo systemctl start copilot-agent
sudo systemctl status copilot-agent
```


### 8. Access and Verify

Open your browser and navigate to:

```
http://YOUR_SERVER_IP/
```

✅ UI should appear  
✅ Chat/API will work

---

### API Call Example
You can also call the agent directly via API (for use in scripts, other apps, etc):

```bash
curl -i -X POST http://YOUR_SERVER_IP:8000/assist \
-H "Content-Type: application/json" \
-d '{
  "session": {
    "user_id": "01K77K1HZE3BCDDS2MKBK7DKZ8",
    "session_id": "01K77K1HZE3BCDDS2MKBK7DKZ8",
    "processor_id": "01K77K1HZE3BCDDS2MKBK7DKZ8",
    "activity_id": "01K77K1HZE3BCDDS2MKBK7DKZ8",
    "request_id": "01K77K1HZE3BCDDS2MKBK7DKZ8",
    "interactions": []
  },
  "query": {
    "id": "01K77K1HZE3BCDDS2MKBK7DKZ8",
    "prompt": "https://en.wikipedia.org/wiki/Artificial_intelligence"
  }
}'
```
Replace YOUR_SERVER_IP with your actual server IP address.
All session fields require a valid ULID (unique string per request).

You can set "prompt" to any question or research link.


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
# Sentient Research Copilot Agent — Complete Secure Installation

A battle-tested, zero-error deployment guide for production environments. Follow each step carefully for a 100% clean installation.

---

## Prerequisites

- Ubuntu/Debian Linux
- Root or sudo access
- Basic familiarity with terminal commands

---






