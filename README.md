# VortexL2

**L2TPv3 Ethernet Tunnel Manager for Ubuntu/Debian**

A modular, production-quality CLI tool for managing multiple L2TPv3 tunnels and TCP port forwarding via socat.

```
 __      __        _            _     ___  
 \ \    / /       | |          | |   |__ \ 
  \ \  / /__  _ __| |_ _____  _| |      ) |
   \ \/ / _ \| '__| __/ _ \ \/ / |     / / 
    \  / (_) | |  | ||  __/>  <| |____/ /_ 
     \/ \___/|_|   \__\___/_/\_\______|____|
```

## ✨ Features

- 🔧 Interactive TUI management panel with Rich
- 🌐 **Multiple L2TPv3 tunnels** on a single server
- 🔀 TCP port forwarding via socat
- 🔄 Systemd integration for persistence
- 📦 One-liner installation
- 🛡️ Secure configuration with 0600 permissions
- 🎯 Fully configurable tunnel IDs

## 📦 Quick Install

```bash
bash <(curl -Ls https://raw.githubusercontent.com/babakazizigithub/VortexL2/main/install.sh)
```

## 🚀 First Run

### 1. Open the Management Panel

```bash
sudo vortexl2
```

### 2. Create Tunnels (Manage Tunnels → Add New Tunnel)

Each tunnel needs:
- **Tunnel Name**: A unique identifier (e.g., `server1`, `kharej-hetzner`)
- **Local IP**: This server's public IP
- **Remote IP**: The other server's public IP
- **Interface IP**: Tunnel interface IP (e.g., `10.30.30.1/24`)
- **Tunnel IDs**: Unique IDs for the L2TP connection

### 3. Configure Both Sides

Both servers need matching tunnel configurations with swapped values:

| Parameter | Server A | Server B |
|-----------|----------|----------|
| Local IP | 1.2.3.4 | 5.6.7.8 |
| Remote IP | 5.6.7.8 | 1.2.3.4 |
| Interface IP | 10.30.30.1/24 | 10.30.30.2/24 |
| Tunnel ID | 1000 | 2000 |
| Peer Tunnel ID | 2000 | 1000 |
| Session ID | 10 | 20 |
| Peer Session ID | 20 | 10 |

### 4. Start Tunnel

Select "Start Current Tunnel" from the menu on both servers.

### 5. Add Port Forwards

Select "Port Forwards" and add ports like: `443,80,2053`

## 🎯 Usage Examples

### Server A Setup

```bash
sudo vortexl2

# 1. Install prerequisites (option 1)
# 2. Manage Tunnels (option 2) → Add New Tunnel
#    - Name: tunnel1
# 3. Configure Current Tunnel (option 3)
#    - Local IP: 1.2.3.4
#    - Remote IP: 5.6.7.8
#    - Interface IP: 10.30.30.1/30
#    - Remote Forward Target: 10.30.30.2
#    - Tunnel ID: 1000
#    - Peer Tunnel ID: 2000
#    - Session ID: 10
#    - Peer Session ID: 20
# 4. Start Tunnel (option 4)
# 5. Port Forwards (option 6) → Add ports
```

### Server B Setup

```bash
sudo vortexl2

# Same steps but with swapped values:
#    - Local IP: 5.6.7.8
#    - Remote IP: 1.2.3.4
#    - Interface IP: 10.30.30.2/30
#    - Tunnel ID: 2000
#    - Peer Tunnel ID: 1000
#    - Session ID: 20
#    - Peer Session ID: 10
```

## 📋 Commands

| Command | Description |
|---------|-------------|
| `sudo vortexl2` | Open management panel |
| `sudo vortexl2 apply` | Apply all tunnels (for systemd boot) |
| `sudo vortexl2 --version` | Show version |

## 🔍 Troubleshooting

### Check Tunnel Status

```bash
# Show L2TP tunnels
ip l2tp show tunnel

# Show L2TP sessions
ip l2tp show session

# Check interface (l2tpeth0, l2tpeth1, etc.)
ip addr show l2tpeth0
```

### Check Port Forwards

```bash
# List listening ports
ss -ltnp | grep socat

# Check service status
systemctl status vortexl2-forward@443
```

### View Logs

```bash
# Tunnel service logs
journalctl -u vortexl2-tunnel -f

# Forward service logs
journalctl -u vortexl2-forward@443 -f
```

### Common Issues

**❌ Tunnel not working**
1. Ensure both sides have matching tunnel IDs (swapped peer values)
2. Check firewall allows IP protocol 115 (L2TPv3)
3. Verify kernel modules are loaded: `lsmod | grep l2tp`

**❌ Port forward not working**
1. Check socat is installed: `which socat`
2. Verify tunnel is up: `ping 10.30.30.2` (from one side)
3. Check service status: `systemctl status vortexl2-forward@PORT`

**❌ Interface l2tpeth0 not found**
1. Ensure session is created (not just tunnel)
2. Check kernel modules: `modprobe l2tp_eth`
3. Recreate tunnel from panel

## 🔧 Configuration

Tunnels are stored in `/etc/vortexl2/tunnels/`:

```yaml
# /etc/vortexl2/tunnels/tunnel1.yaml
name: tunnel1
local_ip: "1.2.3.4"
remote_ip: "5.6.7.8"
interface_ip: "10.30.30.1/30"
remote_forward_ip: "10.30.30.2"
tunnel_id: 1000
peer_tunnel_id: 2000
session_id: 10
peer_session_id: 20
interface_index: 0
forwarded_ports:
  - 443
  - 80
  - 2053
```

## 🏗️ Architecture

### Multiple Tunnels

```
                    ┌─────────────────┐
                    │   Server A      │
                    │   1.2.3.4       │
                    │                 │
                    │  l2tpeth0 ──────┼──── L2TPv3 ──── Server B (5.6.7.8)
                    │  10.30.30.1     │
                    │                 │
                    │  l2tpeth1 ──────┼──── L2TPv3 ──── Server C (9.10.11.12)
                    │  10.40.40.1     │
                    │                 │
                    └─────────────────┘
```

### Port Forwarding

```
                    ┌─────────────────┐
                    │   Server A      │
                    │                 │
                    │  ┌───────────┐  │
 Users ──────────►  │  │  socat    │  │
 (443,80,2053)      │  │  forwards │  │
                    │  └─────┬─────┘  │
                    │        │        │
                    │  ┌─────▼─────┐  │
                    │  │ l2tpeth0  │  │
                    │  │10.30.30.1 │  │
                    │  └─────┬─────┘  │
                    └────────┼────────┘
                             │
                      L2TPv3 Tunnel
                      (encap ip)
                             │
                    ┌────────┼────────┐
                    │  ┌─────▼─────┐  │
                    │  │ l2tpeth0  │  │
                    │  │10.30.30.2 │  │
                    │  └───────────┘  │
                    │                 │
                    │   Server B      │
                    │   5.6.7.8       │
                    └─────────────────┘
```

## 📁 Project Structure

```
VortexL2/
├── vortexl2/
│   ├── __init__.py     # Package info
│   ├── main.py         # CLI entry point
│   ├── config.py       # Multi-tunnel configuration
│   ├── tunnel.py       # L2TPv3 tunnel operations
│   ├── forward.py      # Port forward management
│   └── ui.py           # Rich TUI interface
├── systemd/
│   ├── vortexl2-tunnel.service      # Tunnel boot service
│   └── vortexl2-forward@.service    # Template for forwards
├── install.sh          # Installation script
└── README.md           # This file
```

## ⚠️ Security Notice

**L2TPv3 provides NO encryption!**

The tunnel transports raw Ethernet frames over IP without any encryption. This is suitable for:
- ✅ Bypassing network restrictions
- ✅ Creating L2 connectivity
- ❌ NOT secure for sensitive data in transit

For encrypted traffic, consider:
- Adding IPsec on top of L2TPv3
- Using WireGuard as an alternative
- Encrypting application-level traffic (TLS/HTTPS)

## 🔄 Uninstall

```bash
# Stop services
sudo systemctl stop vortexl2-tunnel
sudo systemctl disable vortexl2-tunnel

# Remove files
sudo rm -rf /opt/vortexl2
sudo rm /usr/local/bin/vortexl2
sudo rm /etc/systemd/system/vortexl2-*
sudo rm -rf /etc/vortexl2

# Reload systemd
sudo systemctl daemon-reload
```

## 📄 License

MIT License

## 👤 Author

Telegram: @iliyadevsh
