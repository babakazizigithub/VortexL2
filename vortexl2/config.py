"""
VortexL2 Configuration Management

Handles loading/saving multiple tunnel configurations from /etc/vortexl2/tunnels/
Each tunnel has its own YAML config file.
"""

import os
import yaml
from pathlib import Path
from typing import Optional, List, Dict, Any


CONFIG_DIR = Path("/etc/vortexl2")
TUNNELS_DIR = CONFIG_DIR / "tunnels"


class TunnelConfig:
    """Configuration for a single tunnel."""
    
    # Default values for new tunnels
    DEFAULTS = {
        "name": "tunnel1",
        "local_ip": None,
        "remote_ip": None,
        "interface_ip": "10.30.30.1/30",
        "remote_forward_ip": "10.30.30.2",
        "tunnel_id": 1000,
        "peer_tunnel_id": 2000,
        "session_id": 10,
        "peer_session_id": 20,
        "interface_index": 0,
        "forwarded_ports": [],
        "use_udp2raw": False,      # Toggle for add-on
        "udp2raw_port": 4096,      # Port to fake-tcp listen/connect
        "udp2raw_secret": "vortex", # Shared secret
        "udp_encap_port": 1701,    # Local UDP port for L2TP
    }
    
    def __init__(self, name: str, config_data: Dict[str, Any] = None, auto_save: bool = True):
        self._name = name
        self._config: Dict[str, Any] = {}
        self._file_path = TUNNELS_DIR / f"{name}.yaml"
        self._auto_save = auto_save
        
        if config_data:
            self._config = config_data
        else:
            self._load()
        
        # Apply defaults for missing keys
        for key, default in self.DEFAULTS.items():
            if key not in self._config:
                self._config[key] = default
        
        # Ensure name matches
        self._config["name"] = name
    
    def _load(self) -> None:
        """Load configuration from file."""
        if self._file_path.exists():
            try:
                with open(self._file_path, 'r') as f:
                    self._config = yaml.safe_load(f) or {}
            except Exception:
                self._config = {}
    
    def _save(self) -> None:
        """Save configuration to file if auto_save is enabled."""
        if not self._auto_save:
            return
        TUNNELS_DIR.mkdir(parents=True, exist_ok=True)
        
        with open(self._file_path, 'w') as f:
            yaml.dump(self._config, f, default_flow_style=False)
        
        os.chmod(self._file_path, 0o600)
    
    def save(self) -> None:
        """Public method to force save configuration (ignores auto_save)."""
        TUNNELS_DIR.mkdir(parents=True, exist_ok=True)
        
        with open(self._file_path, 'w') as f:
            yaml.dump(self._config, f, default_flow_style=False)
        
        os.chmod(self._file_path, 0o600)
        self._auto_save = True  # Enable auto_save after manual save
    
    def delete(self) -> bool:
        """Delete this tunnel's config file."""
        if self._file_path.exists():
            self._file_path.unlink()
            return True
        return False
    
    @property
    def name(self) -> str:
        return self._config.get("name", self._name)
    
    @name.setter
    def name(self, value: str) -> None:
        self._config["name"] = value
        self._save()
    
    @property
    def local_ip(self) -> Optional[str]:
        return self._config.get("local_ip")
    
    @local_ip.setter
    def local_ip(self, value: str) -> None:
        self._config["local_ip"] = value
        self._save()
    
    @property
    def remote_ip(self) -> Optional[str]:
        return self._config.get("remote_ip")
    
    @remote_ip.setter
    def remote_ip(self, value: str) -> None:
        self._config["remote_ip"] = value
        self._save()
    
    @property
    def interface_ip(self) -> str:
        return self._config.get("interface_ip", "10.30.30.1/24")
    
    @interface_ip.setter
    def interface_ip(self, value: str) -> None:
        self._config["interface_ip"] = value
        self._save()
    
    @property
    def remote_forward_ip(self) -> str:
        return self._config.get("remote_forward_ip", "10.30.30.2")
    
    @remote_forward_ip.setter
    def remote_forward_ip(self, value: str) -> None:
        self._config["remote_forward_ip"] = value
        self._save()
    
    @property
    def tunnel_id(self) -> int:
        return self._config.get("tunnel_id", 1000)
    
    @tunnel_id.setter
    def tunnel_id(self, value: int) -> None:
        self._config["tunnel_id"] = value
        self._save()
    
    @property
    def peer_tunnel_id(self) -> int:
        return self._config.get("peer_tunnel_id", 2000)
    
    @peer_tunnel_id.setter
    def peer_tunnel_id(self, value: int) -> None:
        self._config["peer_tunnel_id"] = value
        self._save()
    
    @property
    def session_id(self) -> int:
        return self._config.get("session_id", 10)
    
    @session_id.setter
    def session_id(self, value: int) -> None:
        self._config["session_id"] = value
        self._save()
    
    @property
    def peer_session_id(self) -> int:
        return self._config.get("peer_session_id", 20)
    
    @peer_session_id.setter
    def peer_session_id(self, value: int) -> None:
        self._config["peer_session_id"] = value
        self._save()
    
    @property
    def interface_index(self) -> int:
        return self._config.get("interface_index", 0)
    
    @interface_index.setter
    def interface_index(self, value: int) -> None:
        self._config["interface_index"] = value
        self._save()
    
    @property
    def interface_name(self) -> str:
        """Get the interface name for this tunnel (l2tpeth0, l2tpeth1, etc.)"""
        return f"l2tpeth{self.interface_index}"
    
    @property
    def forwarded_ports(self) -> List[int]:
        return self._config.get("forwarded_ports", [])
    
    @forwarded_ports.setter
    def forwarded_ports(self, value: List[int]) -> None:
        self._config["forwarded_ports"] = value
        self._save()
    
    def get_tunnel_ids(self) -> Dict[str, int]:
        """Get all tunnel IDs as a dictionary."""
        return {
            "tunnel_id": self.tunnel_id,
            "peer_tunnel_id": self.peer_tunnel_id,
            "session_id": self.session_id,
            "peer_session_id": self.peer_session_id,
        }
    
    def add_port(self, port: int) -> None:
        """Add a port to forwarded ports list."""
        ports = self.forwarded_ports
        if port not in ports:
            ports.append(port)
            self.forwarded_ports = ports
    
    def remove_port(self, port: int) -> None:
        """Remove a port from forwarded ports list."""
        ports = self.forwarded_ports
        if port in ports:
            ports.remove(port)
            self.forwarded_ports = ports
    
    def is_configured(self) -> bool:
        """Check if basic configuration is complete."""
        return bool(self.local_ip and self.remote_ip)
    
    def to_dict(self) -> Dict[str, Any]:
        """Return configuration as dictionary."""
        return self._config.copy()

    @property
    def use_udp2raw(self) -> bool:
        return self._config.get("use_udp2raw", False)

    @use_udp2raw.setter
    def use_udp2raw(self, value: bool) -> None:
        self._config["use_udp2raw"] = value
        self._save()

    @property
    def udp2raw_port(self) -> int:
        return self._config.get("udp2raw_port", 4096)
    
    @udp2raw_port.setter
    def udp2raw_port(self, value: int) -> None:
        self._config["udp2raw_port"] = value
        self._save()

    @property
    def udp2raw_secret(self) -> str:
        return self._config.get("udp2raw_secret", "vortex")
    
    @udp2raw_secret.setter
    def udp2raw_secret(self, value: str) -> None:
        self._config["udp2raw_secret"] = value
        self._save()

class ConfigManager:
    """Manages multiple tunnel configurations."""
    
    def __init__(self):
        self._ensure_dirs()
    
    def _ensure_dirs(self) -> None:
        """Ensure config directories exist."""
        TUNNELS_DIR.mkdir(parents=True, exist_ok=True)
    
    def list_tunnels(self) -> List[str]:
        """List all configured tunnel names."""
        if not TUNNELS_DIR.exists():
            return []
        
        tunnels = []
        for f in TUNNELS_DIR.glob("*.yaml"):
            tunnels.append(f.stem)  # filename without extension
        return sorted(tunnels)
    
    def get_tunnel(self, name: str) -> Optional[TunnelConfig]:
        """Get a tunnel config by name."""
        file_path = TUNNELS_DIR / f"{name}.yaml"
        if file_path.exists():
            return TunnelConfig(name)
        return None
    
    def get_all_tunnels(self) -> List[TunnelConfig]:
        """Get all tunnel configurations."""
        return [TunnelConfig(name) for name in self.list_tunnels()]
    
    def create_tunnel(self, name: str) -> TunnelConfig:
        """Create a new tunnel config in memory (not saved until explicitly called)."""
        # Find next available interface index
        used_indices = set()
        for tunnel in self.get_all_tunnels():
            used_indices.add(tunnel.interface_index)
        
        # Find first available index
        new_index = 0
        while new_index in used_indices:
            new_index += 1
        
        # Create new tunnel config (auto_save=False means no file created yet)
        tunnel = TunnelConfig(name, auto_save=False)
        tunnel._config["interface_index"] = new_index
        tunnel._config["name"] = name
        
        # Set unique default tunnel IDs based on index
        # This helps avoid ID conflicts between tunnels
        base_tunnel_id = 1000 + (new_index * 100)
        tunnel._config["tunnel_id"] = base_tunnel_id
        tunnel._config["peer_tunnel_id"] = base_tunnel_id + 1000
        tunnel._config["session_id"] = 10 + new_index
        tunnel._config["peer_session_id"] = 20 + new_index
        
        # Don't save here - config file will be created only after successful tunnel setup
        return tunnel
    
    def delete_tunnel(self, name: str) -> bool:
        """Delete a tunnel configuration."""
        tunnel = self.get_tunnel(name)
        if tunnel:
            return tunnel.delete()
        return False
    
    def tunnel_exists(self, name: str) -> bool:
        """Check if a tunnel with this name exists."""
        return (TUNNELS_DIR / f"{name}.yaml").exists()

