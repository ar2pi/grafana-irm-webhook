# Grafana IRM Webhook - Raspberry Pi LED Controller

A webhook server that receives alerts from Grafana IRM and controls a Raspberry Pi LED to provide visual alerting. When an alert fires, the LED turns on with blinking patterns based on alert severity. When the alert resolves, the LED turns off.

## Features

- **Grafana IRM Integration**: Receives webhook payloads from Grafana IRM alert groups
- **Raspberry Pi GPIO Control**: Controls LEDs connected to GPIO pins
- **Severity-based Visual Alerts**: Different blinking patterns based on alert severity
- **Alert Resolution**: Automatically turns off LED when alerts are resolved
- **FastAPI Framework**: Modern, fast, and automatically documented API
- **Docker Support**: Easy deployment with Docker and Docker Compose
- **Health Monitoring**: Built-in health check endpoints
- **Configurable**: Environment-based configuration for different setups
- **Auto Documentation**: Interactive API docs at `/docs` and `/redoc`

## Raspberry Pi GPIO LED Control

- Controls LEDs connected to GPIO pins
- Blinking patterns based on alert severity
- Perfect for Raspberry Pi setups
- No external hardware required (uses built-in LED or external LED)

## Quick Start

### 1. Clone and Setup

```bash
git clone <repository-url>
cd grafana-irm-webhook
cp config.env.example .env
```

### 2. Configure Environment

Edit `.env` file with your settings:

```bash
# Raspberry Pi GPIO Configuration
LIGHTBULB_TYPE=raspberry_pi
GPIO_PIN=18

# Webhook Configuration
WEBHOOK_SECRET=your-webhook-secret
PORT=5000
DEBUG=false
```

### 3. Run with Docker Compose

```bash
docker-compose up -d
```

### 4. Test the Webhook

```bash
curl -X POST http://localhost:5000/webhook/test
```

### 5. Complete Setup (Recommended)

For a complete setup including internet access:

```bash
# Run the complete setup script
chmod +x setup.sh
./setup.sh

# Choose option 2 for webhook + ngrok setup
# This will install everything and configure ngrok automatically
```

### 6. Expose to Internet (Manual)

To manually expose your Raspberry Pi:

```bash
# Quick ngrok setup
ngrok http 5000
# Use the https URL in Grafana IRM: https://abc123.ngrok.io/webhook/grafana-irm
```

## Grafana IRM Configuration

### 1. Create Outgoing Webhook

1. Navigate to **Alerts & IRM** > **IRM** > **Integrations** in Grafana Cloud
2. Select **Outgoing Webhooks** tab
3. Click **+ Create an Outgoing Webhook**
4. Choose **Advanced webhook for alert groups**

### 2. Configure Webhook

- **Name**: `Raspberry Pi LED Alert`
- **Enabled**: `true`
- **Assign to team**: Select your team
- **Trigger type**: `Alert group created`
- **HTTP method**: `POST`
- **Webhook URL**: `http://your-raspberry-pi-ip:5000/webhook/grafana-irm`
- **Headers**: 
  ```json
  {
    "Content-Type": "application/json"
  }
  ```
- **Customize forwarded data**: `true`
- **Data template**: Use default (no changes needed)

### 3. Test Integration

Create a test alert in Grafana to verify the LED responds correctly.

## Exposing Raspberry Pi to Internet

To receive webhooks from Grafana Cloud, your Raspberry Pi needs to be accessible from the internet. 


Here are the main options:

### Option 1: ngrok (Recommended)

ngrok is the most popular and reliable tunneling service.

#### 1. Install ngrok

```bash
# Download and install ngrok
curl -s https://ngrok-agent.s3.amazonaws.com/ngrok.asc | sudo tee /etc/apt/trusted.gpg.d/ngrok.asc >/dev/null
echo "deb https://ngrok-agent.s3.amazonaws.com buster main" | sudo tee /etc/apt/sources.list.d/ngrok.list
sudo apt update && sudo apt install ngrok

# Or download directly
wget https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-linux-arm64.tgz
tar xvzf ngrok-v3-stable-linux-arm64.tgz
sudo mv ngrok /usr/local/bin/
```

#### 2. Create ngrok Account and Get Token

1. Go to [ngrok.com](https://ngrok.com) and create a free account
2. Get your authtoken from the dashboard
3. Configure ngrok:

```bash
# Add your authtoken
ngrok config add-authtoken YOUR_AUTHTOKEN_HERE
```

#### 3. Expose the Webhook

```bash
# Expose port 5000 (where your webhook runs)
ngrok http 5000
```

This will give you a public URL like: `https://abc123.ngrok.io`

#### 4. Configure Grafana IRM

Use the ngrok URL in your Grafana IRM webhook configuration:
- **Webhook URL**: `https://abc123.ngrok.io/webhook/grafana-irm`

#### 5. Make ngrok Persistent (Optional)

Create a systemd service for ngrok:

```bash
sudo nano /etc/systemd/system/ngrok.service
```

Add this content:
```ini
[Unit]
Description=ngrok tunnel
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi
ExecStart=/usr/local/bin/ngrok http 5000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable ngrok.service
sudo systemctl start ngrok.service
```

### Option 2: Cloudflare Tunnel (Free & Static)

```bash
# Install cloudflared
wget https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-arm64.deb
sudo dpkg -i cloudflared-linux-arm64.deb

# Authenticate and create tunnel
cloudflared tunnel login
cloudflared tunnel create grafana-webhook

# Configure tunnel
mkdir -p ~/.cloudflared
nano ~/.cloudflared/config.yml
# Add: tunnel: YOUR_TUNNEL_ID, service: http://localhost:5000

# Run tunnel
cloudflared tunnel run grafana-webhook
```

### Option 3: localtunnel (Simple)

```bash
# Install and run
sudo npm install -g localtunnel
lt --port 5000 --subdomain your-webhook-name
# Use: https://your-webhook-name.loca.lt/webhook/grafana-irm
```

## Security & Testing

### Security
```bash
# Add webhook authentication
openssl rand -hex 32
echo "WEBHOOK_SECRET=your-secret" >> .env

# Configure firewall
sudo ufw allow 5000
sudo ufw enable
```

### Testing
```bash
# Test locally
curl http://localhost:5000/health
curl -X POST http://localhost:5000/webhook/test

# Run comprehensive tests
python3 -m api.test_webhook

# Test public access
curl https://your-ngrok-url.ngrok.io/health
```

### Troubleshooting
```bash
# Check services
sudo systemctl status grafana-webhook.service
sudo systemctl status ngrok.service

# View logs
sudo journalctl -u grafana-webhook.service -f
sudo journalctl -u ngrok.service -f
```

## Raspberry Pi Setup

### Quick Setup (Recommended)

Use the automated setup script for complete configuration:

```bash
# Run the complete setup script
chmod +x setup.sh
./setup.sh

# Choose from:
# 1) Webhook server only (local access)
# 2) Webhook server + ngrok (internet access) 
# 3) ngrok only (if webhook is already set up)
```

### Hardware Setup

**Required:**
- Raspberry Pi (any model with GPIO pins)
- LED + 220Ω resistor (optional - can use built-in LED)

**Wiring:**
```
GPIO Pin 18 → 220Ω Resistor → LED Anode (+)
LED Cathode (-) → Ground (GND)
```

### Manual Setup (Advanced)

```bash
# Install dependencies
sudo apt update && sudo apt upgrade -y
sudo apt install python3 python3-pip python3-venv -y
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Configure
cp config.env.example .env
nano .env  # Set LIGHTBULB_TYPE=raspberry_pi, GPIO_PIN=18

# Run
python -m api.app

curl http://localhost:5000/health 
curl -XPOST http://localhost:5000/webhook/test
# Or: uvicorn api.app:app --host 0.0.0.0 --port 5000 --reload
```

### LED Patterns

| Severity | Pattern | Description |
|----------|---------|-------------|
| **Critical** | 5 fast blinks | 100ms on/off, 5 times |
| **High** | 3 medium blinks | 200ms on/off, 3 times |
| **Warning** | 2 slow blinks | 500ms on/off, 2 times |
| **Info** | 1 long blink | 1s on, 0.5s off, 1 time |
| **Low** | 1 short blink | 300ms on/off, 1 time |

After the pattern, LED stays on until alert resolves.

## API Endpoints

### Interactive Documentation
- **Swagger UI**: `http://localhost:5000/docs` - Interactive API documentation
- **ReDoc**: `http://localhost:5000/redoc` - Alternative API documentation

### Health Check
```
GET /health
```
Returns server health status and configuration.

### Main Webhook
```
POST /webhook/grafana-irm
```
Receives Grafana IRM alert webhooks and controls the lightbulb.

### Test Endpoint
```
POST /webhook/test
```
Tests LED control without triggering a real alert.

## Alert Severity Patterns

| Severity | Pattern | Description |
|----------|---------|-------------|
| **Critical** | 5 fast blinks | 100ms on, 100ms off, 5 times |
| **High** | 3 medium blinks | 200ms on, 200ms off, 3 times |
| **Warning** | 2 slow blinks | 500ms on, 500ms off, 2 times |
| **Info** | 1 long blink | 1s on, 0.5s off, 1 time |
| **Low** | 1 short blink | 300ms on, 300ms off, 1 time |

## Development

```bash
# Install and run
pip install -r requirements.txt
uvicorn api.app:app --host 0.0.0.0 --port 5000 --reload

# Or with Docker
docker build -t grafana-irm-webhook .
docker run -p 5000:5000 -e LIGHTBULB_TYPE=raspberry_pi -e GPIO_PIN=18 grafana-irm-webhook
```

## Configuration Options

| Environment Variable | Description | Default | Required |
|---------------------|-------------|---------|----------|
| `LIGHTBULB_TYPE` | Type of lightbulb (raspberry_pi) | raspberry_pi | No |
| `GPIO_PIN` | GPIO pin number for Raspberry Pi | 18 | No |
| `WEBHOOK_SECRET` | Secret for webhook validation | - | No |
| `PORT` | Server port | 5000 | No |
| `DEBUG` | Enable debug mode | false | No |

## @TODO:

[] Use slim image
