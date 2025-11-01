#!/bin/bash

# Complete Setup Script for Grafana IRM Webhook
# This script sets up the webhook server on Raspberry Pi and optionally configures ngrok

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_header() {
    echo -e "${BLUE}================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}================================${NC}"
}

# Check if running on Raspberry Pi
check_raspberry_pi() {
    print_header "Checking Raspberry Pi Environment"

    if [ ! -f /proc/device-tree/model ]; then
        print_warning "This doesn't appear to be a Raspberry Pi"
        read -p "Continue anyway? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    else
        MODEL=$(cat /proc/device-tree/model)
        print_success "Detected: $MODEL"
    fi
}

# Update system packages
update_system() {
    print_header "Updating System Packages"

    print_status "Updating package lists..."
    sudo apt update

    print_status "Upgrading packages..."
    sudo apt upgrade -y

    print_success "System updated successfully"
}

# Install required packages
install_packages() {
    print_header "Installing Required Packages"

    print_status "Installing Python and development tools..."
    sudo apt install -y python3 python3-pip python3-venv python3-dev

    print_status "Installing system dependencies..."
    sudo apt install -y git curl jq

    print_success "Packages installed successfully"
}

# Enable GPIO
enable_gpio() {
    print_header "Enabling GPIO"

    print_status "GPIO is usually enabled by default on Raspberry Pi OS"
    print_status "If you need to enable it manually, run: sudo raspi-config"
    print_status "Navigate to: Advanced Options → GPIO → Enable"

    print_success "GPIO configuration complete"
}

# Install Python dependencies
install_python_deps() {
    print_header "Installing Python Dependencies"

    python3 -m venv .venv
    source .venv/bin/activate

    print_status "Installing other dependencies..."
    pip3 install -r requirements.txt

    print_success "Python dependencies installed successfully"
}

# Configure environment
configure_environment() {
    print_header "Configuring Environment"

    if [ ! -f "api/.env" ]; then
        print_status "Creating api/.env file from template..."
        cp api/config.env.example api/.env
        print_success "api/.env file created"
    else
        print_warning "api/.env file already exists, skipping creation"
    fi

    print_status "Current configuration:"
    print_status "  LIGHTBULB_TYPE=raspberry_pi"
    print_status "  GPIO_PIN=17"
    print_status "  PORT=5000"
    print_status "  DEBUG=false"

    read -p "Edit api/.env file now? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        nano api/.env
    fi
}

# Test GPIO functionality
test_gpio() {
    print_header "Testing GPIO Functionality"

    print_status "Running GPIO test..."
    if python3 test_led_blink.py; then
        print_success "GPIO test passed"
    else
        print_error "GPIO test failed"
        print_warning "Make sure you have proper permissions and GPIO is enabled"
    fi
}

# Install ngrok
install_ngrok() {
    print_header "Installing ngrok"

    # Check if ngrok is already installed
    if command -v ngrok &> /dev/null; then
        print_warning "ngrok is already installed"
        ngrok version
        read -p "Reinstall ngrok? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            return 0
        fi
    fi

    print_status "Installing ngrok..."

    # Detect architecture
    ARCH=$(uname -m)
    case $ARCH in
        x86_64)
            ARCH="amd64"
            ;;
        aarch64|arm64)
            ARCH="arm64"
            ;;
        armv7l)
            ARCH="arm"
            ;;
        *)
            print_error "Unsupported architecture: $ARCH"
            exit 1
            ;;
    esac

    print_status "Detected architecture: $ARCH"

    # Download ngrok
    NGROK_VERSION="v3-stable"
    NGROK_URL="https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-${NGROK_VERSION}-linux-${ARCH}.tgz"

    print_status "Downloading ngrok from: $NGROK_URL"
    wget -O ngrok.tgz "$NGROK_URL"

    # Extract and install
    print_status "Extracting ngrok..."
    tar xvzf ngrok.tgz
    sudo mv ngrok /usr/local/bin/
    rm ngrok.tgz

    # Make executable
    sudo chmod +x /usr/local/bin/ngrok

    print_success "ngrok installed successfully"
    ngrok version
}

# Configure ngrok
configure_ngrok() {
    print_header "Configuring ngrok"

    print_status "You need to create a free ngrok account at https://ngrok.com"
    print_status "After creating an account, get your authtoken from the dashboard"

    read -p "Enter your ngrok authtoken (or press Enter to skip): " NGROK_TOKEN

    if [ -z "$NGROK_TOKEN" ]; then
        print_warning "Skipping ngrok configuration"
        print_status "You can configure ngrok later with: ngrok config add-authtoken YOUR_TOKEN"
        return 0
    fi

    print_status "Configuring ngrok with authtoken..."
    ngrok config add-authtoken "$NGROK_TOKEN"

    print_success "ngrok configured successfully"
}

# Create systemd services
create_services() {
    print_header "Creating Systemd Services"

    # Get current directory and user
    CURRENT_DIR=$(pwd)
    USER=$(whoami)

    # Create webhook service
    read -p "Create systemd service for webhook auto-start? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        print_status "Creating webhook service..."

        sudo tee /etc/systemd/system/grafana-webhook.service > /dev/null << EOF
[Unit]
Description=Grafana IRM Webhook Server
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$CURRENT_DIR
Environment=PATH=$CURRENT_DIR/venv/bin
ExecStart=$CURRENT_DIR/venv/bin/python -m api.app
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

        print_success "Webhook systemd service created"

        # Enable and start service
        print_status "Enabling webhook service..."
        sudo systemctl daemon-reload
        sudo systemctl enable grafana-webhook.service

        print_status "Starting webhook service..."
        sudo systemctl start grafana-webhook.service

        print_success "Webhook service started successfully"
    fi

    # Create ngrok service
    if command -v ngrok &> /dev/null; then
        read -p "Create systemd service for ngrok auto-start? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            print_status "Creating ngrok service..."

            sudo tee /etc/systemd/system/ngrok.service > /dev/null << EOF
[Unit]
Description=ngrok tunnel for Grafana IRM Webhook
After=network.target grafana-webhook.service
Requires=grafana-webhook.service

[Service]
Type=simple
User=$USER
WorkingDirectory=$CURRENT_DIR
ExecStart=/usr/local/bin/ngrok http 5000
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

            print_success "ngrok systemd service created"

            # Enable and start service
            print_status "Enabling ngrok service..."
            sudo systemctl daemon-reload
            sudo systemctl enable ngrok.service

            print_status "Starting ngrok service..."
            sudo systemctl start ngrok.service

            print_success "ngrok service started successfully"
        fi
    fi
}

# Test the complete setup
test_setup() {
    print_header "Testing Complete Setup"

    # Wait for services to start
    print_status "Waiting for services to start..."
    sleep 5

    # Test webhook locally
    print_status "Testing webhook locally..."
    if curl -s http://localhost:5000/health > /dev/null; then
        print_success "Webhook is running locally"
    else
        print_warning "Webhook test failed - check if service is running"
    fi

    # Test ngrok if available
    if command -v ngrok &> /dev/null && systemctl is-active --quiet ngrok.service; then
        print_status "Testing ngrok tunnel..."

        # Get the public URL
        if command -v jq &> /dev/null; then
            PUBLIC_URL=$(curl -s http://localhost:4040/api/tunnels | jq -r '.tunnels[0].public_url' 2>/dev/null)
            if [ "$PUBLIC_URL" != "null" ] && [ -n "$PUBLIC_URL" ]; then
                print_success "ngrok tunnel is running!"
                print_status "Public URL: $PUBLIC_URL"
                print_status "Webhook URL: $PUBLIC_URL/webhook/grafana-irm"
                print_status "Health check: $PUBLIC_URL/health"

                # Test public access
                print_status "Testing public access..."
                if curl -s "$PUBLIC_URL/health" > /dev/null; then
                    print_success "Webhook is accessible from the internet!"
                else
                    print_warning "Public access test failed"
                fi
            else
                print_warning "Could not get public URL from ngrok API"
            fi
        else
            print_warning "jq not installed, cannot get public URL automatically"
            print_status "Check ngrok status: sudo systemctl status ngrok.service"
        fi
    else
        print_status "ngrok not running - start manually with: ngrok http 5000"
    fi
}

# Show configuration instructions
show_config_instructions() {
    print_header "Grafana IRM Configuration"

    print_status "To configure Grafana IRM with your webhook:"
    echo
    print_status "1. Go to Grafana Cloud → Alerts & IRM → IRM → Integrations"
    print_status "2. Select 'Outgoing Webhooks' tab"
    print_status "3. Click '+ Create an Outgoing Webhook'"
    print_status "4. Choose 'Advanced webhook for alert groups'"
    print_status "5. Configure with these settings:"
    echo

    if command -v ngrok &> /dev/null && systemctl is-active --quiet ngrok.service; then
        if command -v jq &> /dev/null; then
            PUBLIC_URL=$(curl -s http://localhost:4040/api/tunnels | jq -r '.tunnels[0].public_url' 2>/dev/null)
            if [ "$PUBLIC_URL" != "null" ] && [ -n "$PUBLIC_URL" ]; then
                print_status "   Webhook URL: $PUBLIC_URL/webhook/grafana-irm"
            else
                print_status "   Webhook URL: https://YOUR-NGROK-URL.ngrok.io/webhook/grafana-irm"
            fi
        else
            print_status "   Webhook URL: https://YOUR-NGROK-URL.ngrok.io/webhook/grafana-irm"
        fi
    else
        print_status "   Webhook URL: http://YOUR-RASPBERRY-PI-IP:5000/webhook/grafana-irm"
    fi

    print_status "   Name: Raspberry Pi LED Alert"
    print_status "   Enabled: true"
    print_status "   Trigger type: Alert group created"
    print_status "   HTTP method: POST"
    print_status "   Headers: Content-Type: application/json"
    echo
    print_status "6. Save the webhook"
    echo
    print_warning "Note: Free ngrok URLs change when you restart ngrok"
    print_warning "Consider upgrading to a paid plan for a static URL"
}

# Main setup function
main() {
    print_header "Grafana IRM Webhook - Complete Setup"
    print_status "This script will set up the webhook server and optionally configure ngrok"
    echo

    # Ask what to install
    print_status "What would you like to set up?"
    echo "1) Webhook server only (local access)"
    echo "2) Webhook server + ngrok (internet access)"
    echo "3) ngrok only (if webhook is already set up)"
    echo
    read -p "Choose option (1-3): " -n 1 -r
    echo

    case $REPLY in
        1)
            SETUP_WEBHOOK=true
            SETUP_NGROK=false
            ;;
        2)
            SETUP_WEBHOOK=true
            SETUP_NGROK=true
            ;;
        3)
            SETUP_WEBHOOK=false
            SETUP_NGROK=true
            ;;
        *)
            print_error "Invalid option"
            exit 1
            ;;
    esac

    # Run setup steps
    check_raspberry_pi

    if [ "$SETUP_WEBHOOK" = true ]; then
        update_system
        install_packages
        enable_gpio
        install_python_deps
        configure_environment
        test_gpio
    fi

    if [ "$SETUP_NGROK" = true ]; then
        install_ngrok
        configure_ngrok
    fi

    if [ "$SETUP_WEBHOOK" = true ]; then
        create_services
    fi

    test_setup
    show_config_instructions

    print_header "Setup Complete!"
    print_success "Your Grafana IRM Webhook setup is ready!"
    echo
    print_status "Useful commands:"
    print_status "  Test webhook: curl -X POST http://localhost:5000/webhook/test"
    print_status "  Run tests: python3 -m api.test_webhook"
    print_status "  API docs: http://localhost:5000/docs"
    print_status "  Webhook status: sudo systemctl status grafana-webhook.service"
    print_status "  Webhook logs: sudo journalctl -u grafana-webhook.service -f"

    if command -v ngrok &> /dev/null; then
        print_status "  Start ngrok: ngrok http 5000"
        print_status "  ngrok status: sudo systemctl status ngrok.service"
        print_status "  ngrok logs: sudo journalctl -u ngrok.service -f"
    fi
}

# Run main function
main "$@"
