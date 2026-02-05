"""
VortexL2 L2TPv3 Tunnel Management

Handles L2TPv3 tunnel and session creation/deletion using iproute2.
Also manages UDP2RAW service for anti-censorship mode.
"""

import subprocess
import re
import os
import time
from typing import Optional, Dict, Tuple, List
from dataclasses import dataclass


@dataclass
class CommandResult:
    """Result of a shell command execution."""
    success: bool
    stdout: str
    stderr: str
    returncode: int


def run_command(cmd: str, check: bool = False) -> CommandResult:
    """Execute a shell command and return result."""
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=30
        )
        return CommandResult(
            success=(result.returncode == 0),
            stdout=result.stdout.strip(),
            stderr=result.stderr.strip(),
            returncode=result.returncode
        )
    except subprocess.TimeoutExpired:
        return CommandResult(
            success=False,
            stdout="",
            stderr="Command timed out",
            returncode=-1
        )
    except Exception as e:
        return CommandResult(
            success=False,
            stdout="",
            stderr=str(e),
            returncode=-1
        )


class TunnelManager:
    """Manages L2TPv3 tunnel and session operations for a specific tunnel config."""
    
    def __init__(self, config):
        """
        Initialize with a TunnelConfig instance.
        
        Args:
            config: TunnelConfig instance for the tunnel to manage
        """
        self.config = config
    
    @property
    def interface_name(self) -> str:
        """Get the interface name for this tunnel."""
        return self.config.interface_name
    
    def install_prerequisites(self) -> Tuple[bool, str]:
        """Install required packages and load kernel modules."""
        steps = []
        
        # Get kernel version
        result = run_command("uname -r")
        if not result.success:
            return False, "Failed to get kernel version"
        kernel_version = result.stdout.strip()
        
        # Install linux-modules-extra
        steps.append(f"Installing linux-modules-extra-{kernel_version}...")
        result = run_command(f"apt-get install -y linux-modules-extra-{kernel_version}")
        if not result.success:
            # Try without specific version as fallback
            result = run_command("apt-get install -y linux-modules-extra-$(uname -r)")
            if not result.success:
                steps.append(f"Warning: Could not install modules package: {result.stderr}")
        else:
            steps.append("Package installed successfully")
        
        # Install iproute2 with l2tp support
        result = run_command("apt-get install -y iproute2")
        if not result.success:
            steps.append(f"Warning: Could not install iproute2: {result.stderr}")
        
        # Load kernel modules
        modules = ["l2tp_core", "l2tp_netlink", "l2tp_eth"]
        for module in modules:
            steps.append(f"Loading module {module}...")
            result = run_command(f"modprobe {module}")
            if not result.success:
                return False, f"Failed to load module {module}: {result.stderr}"
            steps.append(f"Module {module} loaded")
        
        # Verify modules are loaded
        result = run_command("lsmod | grep l2tp")
        if "l2tp" not in result.stdout:
            return False, "L2TP modules not found in lsmod"
        
        steps.append("All prerequisites installed successfully!")
        return True, "\n".join(steps)
    
    def check_tunnel_exists(self, tunnel_id: int = None) -> bool:
        """Check if L2TP tunnel exists."""
        if tunnel_id is None:
            tunnel_id = self.config.tunnel_id
        
        result = run_command("ip l2tp show tunnel")
        if not result.success:
            return False
        
        # Parse output for tunnel_id
        pattern = rf"Tunnel\s+{tunnel_id},"
        return bool(re.search(pattern, result.stdout))
    
    def check_session_exists(self, tunnel_id: int = None, session_id: int = None) -> bool:
        """Check if L2TP session exists."""
        if tunnel_id is None:
            tunnel_id = self.config.tunnel_id
        if session_id is None:
            session_id = self.config.session_id
        
        result = run_command("ip l2tp show session")
        if not result.success:
            return False
        
        # Parse output for session_id in tunnel
        pattern = rf"Session\s+{session_id}\s+in\s+tunnel\s+{tunnel_id}"
        return bool(re.search(pattern, result.stdout))
    
    # --- UDP2RAW Service Management ---

    def _get_udp2raw_service_name(self) -> str:
        return f"vortexl2-raw-{self.config.name}.service"

    def setup_udp2raw_service(self) -> Tuple[bool, str]:
        """Create and start udp2raw systemd service."""
        # Check if feature is enabled in config
        if not getattr(self.config, 'use_udp2raw', False):
            return True, "UDP2RAW disabled"

        service_name = self._get_udp2raw_service_name()
        service_path = f"/etc/systemd/system/{service_name}"
        
        # Determine Mode (Client vs Server) based on Tunnel IDs
        # Heuristic: If tunnel_id < peer_tunnel_id => Client (Iran), else Server (Kharej)
        # Iran (1000) -> Kharej (2000)
        is_client = self.config.tunnel_id < self.config.peer_tunnel_id
        
        # Parameters
        raw_port = getattr(self.config, 'udp2raw_port', 4096)
        secret = getattr(self.config, 'udp2raw_secret', 'vortex')
        
        if is_client:
            # CLIENT MODE (Iran)
            # Listen on Localhost:PeerID (where Kernel sends packets)
            # Send to RemoteIP:RawPort
            listen_addr = f"127.0.0.1:{self.config.peer_tunnel_id}"
            remote_addr = f"{self.config.remote_ip}:{raw_port}"
            cmd = f"/usr/local/bin/udp2raw -c -l {listen_addr} -r {remote_addr} -k {secret} --raw-mode faketcp -a"
            desc = f"Client -> {remote_addr}"
        else:
            # SERVER MODE (Kharej)
            # Listen on 0.0.0.0:RawPort (Public Internet)
            # Send to Localhost:TunnelID (Where Kernel is listening)
            listen_addr = f"0.0.0.0:{raw_port}"
            target_addr = f"127.0.0.1:{self.config.tunnel_id}"
            cmd = f"/usr/local/bin/udp2raw -s -l {listen_addr} -r {target_addr} -k {secret} --raw-mode faketcp -a"
            desc = f"Server <- {listen_addr}"

        # Create Service File
        service_content = f"""[Unit]
Description=VortexL2 UDP2RAW Wrapper - {self.config.name} ({desc})
After=network.target

[Service]
Type=simple
ExecStart={cmd}
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
"""
        try:
            with open(service_path, 'w') as f:
                f.write(service_content)
            
            run_command("systemctl daemon-reload")
            run_command(f"systemctl enable --now {service_name}")
            return True, f"UDP2RAW service started ({desc})"
        except Exception as e:
            return False, f"Failed to start UDP2RAW: {e}"

    def remove_udp2raw_service(self):
        """Stop and remove udp2raw service."""
        # Clean up regardless of current config status
        service_name = self._get_udp2raw_service_name()
        run_command(f"systemctl stop {service_name}")
        run_command(f"systemctl disable {service_name}")
        
        if os.path.exists(f"/etc/systemd/system/{service_name}"):
            try:
                os.remove(f"/etc/systemd/system/{service_name}")
                run_command("systemctl daemon-reload")
            except:
                pass

    # --- End UDP2RAW Management ---

    def create_tunnel(self) -> Tuple[bool, str]:
        """Create L2TP tunnel based on configuration."""
        # 1. Validate IPs
        if not self.config.local_ip or not self.config.remote_ip:
            return False, "IPs not configured. Please configure tunnel first."
        
        ids = self.config.get_tunnel_ids()
        
        # 2. Check if already exists
        if self.check_tunnel_exists():
            return False, f"Tunnel {ids['tunnel_id']} already exists. Delete it first."
        
        # 3. Determine Encapsulation Mode
        if getattr(self.config, 'use_udp2raw', False):
            # --- UDP2RAW Enabled ---
            # Kernel talks UDP to localhost
            encap_param = "encap udp"
            # Kernel listens on 127.0.0.1
            local_ip = "127.0.0.1" 
            # Kernel sends to 127.0.0.1
            remote_ip = "127.0.0.1"
            
            # Kernel Ports:
            # udp_sport: Local bind port (must match what UDP2RAW sends TO on Server side)
            # udp_dport: Remote destination port (must match what UDP2RAW listens ON on Client side)
            udp_ports = f"udp_sport {ids['tunnel_id']} udp_dport {ids['peer_tunnel_id']}"
            
        else:
            # --- Standard L2TPv3 ---
            # Direct Raw-IP connection (Protocol 115)
            encap_param = "encap ip"
            local_ip = self.config.local_ip
            remote_ip = self.config.remote_ip
            udp_ports = "" # No UDP ports needed for IP encap

        # 4. Construct Command
        cmd = (
            f"ip l2tp add tunnel "
            f"tunnel_id {ids['tunnel_id']} "
            f"peer_tunnel_id {ids['peer_tunnel_id']} "
            f"{encap_param} "
            f"local {local_ip} "
            f"remote {remote_ip} "
            f"{udp_ports}"
        )
        
        # 5. Execute
        result = run_command(cmd)
        if not result.success:
            return False, f"Failed to create tunnel: {result.stderr}"
        
        return True, f"Tunnel {ids['tunnel_id']} created successfully"
    
    def create_session(self) -> Tuple[bool, str]:
        """Create L2TP session in existing tunnel."""
        ids = self.config.get_tunnel_ids()
        
        if not self.check_tunnel_exists():
            return False, "Tunnel does not exist. Create tunnel first."
        
        if self.check_session_exists():
            return False, f"Session {ids['session_id']} already exists"
        
        cmd = (
            f"ip l2tp add session "
            f"tunnel_id {ids['tunnel_id']} "
            f"session_id {ids['session_id']} "
            f"peer_session_id {ids['peer_session_id']}"
        )
        
        result = run_command(cmd)
        if not result.success:
            return False, f"Failed to create session: {result.stderr}"
        
        return True, f"Session {ids['session_id']} created successfully"
    
    def bring_up_interface(self) -> Tuple[bool, str]:
        """Bring up the tunnel interface."""
        # Wait a moment for interface to appear
        time.sleep(0.5)
        
        result = run_command(f"ip link set {self.interface_name} up")
        if not result.success:
            return False, f"Failed to bring up interface: {result.stderr}"
        
        return True, f"Interface {self.interface_name} is up"
    
    def assign_ip(self) -> Tuple[bool, str]:
        """Assign IP address to tunnel interface."""
        ip_cidr = self.config.interface_ip
        
        # Check if IP already assigned
        result = run_command(f"ip addr show {self.interface_name}")
        if ip_cidr.split('/')[0] in result.stdout:
            return True, f"IP {ip_cidr} already assigned"
        
        result = run_command(f"ip addr add {ip_cidr} dev {self.interface_name}")
        if not result.success:
            # Check if it's because address exists
            if "RTNETLINK answers: File exists" in result.stderr:
                return True, f"IP {ip_cidr} already assigned"
            return False, f"Failed to assign IP: {result.stderr}"
        
        return True, f"IP {ip_cidr} assigned to {self.interface_name}"
    
    def delete_session(self) -> Tuple[bool, str]:
        """Delete L2TP session."""
        ids = self.config.get_tunnel_ids()
        
        if not self.check_session_exists():
            return True, "Session does not exist (already deleted)"
        
        cmd = f"ip l2tp del session tunnel_id {ids['tunnel_id']} session_id {ids['session_id']}"
        result = run_command(cmd)
        if not result.success:
            return False, f"Failed to delete session: {result.stderr}"
        
        return True, f"Session {ids['session_id']} deleted"
    
    def delete_tunnel(self) -> Tuple[bool, str]:
        """Delete L2TP tunnel (must delete session first)."""
        ids = self.config.get_tunnel_ids()
        
        # First delete session if exists
        if self.check_session_exists():
            success, msg = self.delete_session()
            if not success:
                return False, f"Failed to delete session first: {msg}"
        
        if not self.check_tunnel_exists():
            return True, "Tunnel does not exist (already deleted)"
        
        cmd = f"ip l2tp del tunnel tunnel_id {ids['tunnel_id']}"
        result = run_command(cmd)
        if not result.success:
            return False, f"Failed to delete tunnel: {result.stderr}"
        
        return True, f"Tunnel {ids['tunnel_id']} deleted"
    
    def full_setup(self) -> Tuple[bool, str]:
        """Perform full tunnel setup: UDP2RAW -> tunnel -> session -> interface -> IP."""
        steps = []
        tunnel_name = self.config.name
        
        steps.append(f"=== Setting up tunnel: {tunnel_name} ===")
        
        # 1. Start UDP2RAW Service (if enabled)
        if getattr(self.config, 'use_udp2raw', False):
            success, msg = self.setup_udp2raw_service()
            steps.append(msg)
            if not success:
                return False, "\n".join(steps)
            # Give service a moment to start
            time.sleep(1)

        # 2. Create tunnel
        success, msg = self.create_tunnel()
        steps.append(f"Create tunnel: {msg}")
        if not success and "already exists" not in msg:
            return False, "\n".join(steps)
        
        # 3. Create session
        success, msg = self.create_session()
        steps.append(f"Create session: {msg}")
        if not success and "already exists" not in msg:
            return False, "\n".join(steps)
        
        # 4. Bring up interface
        success, msg = self.bring_up_interface()
        steps.append(f"Bring up interface: {msg}")
        if not success:
            return False, "\n".join(steps)
        
        # 5. Assign IP
        success, msg = self.assign_ip()
        steps.append(f"Assign IP: {msg}")
        if not success:
            return False, "\n".join(steps)
        
        steps.append(f"\n✓ Tunnel '{tunnel_name}' setup complete!")
        return True, "\n".join(steps)
    
    def full_teardown(self) -> Tuple[bool, str]:
        """Perform full tunnel teardown."""
        steps = []
        tunnel_name = self.config.name
        
        steps.append(f"=== Tearing down tunnel: {tunnel_name} ===")
        
        # 1. Delete session
        success, msg = self.delete_session()
        steps.append(f"Delete session: {msg}")
        
        # 2. Delete tunnel
        success, msg = self.delete_tunnel()
        steps.append(f"Delete tunnel: {msg}")
        
        # 3. Stop UDP2RAW Service
        if getattr(self.config, 'use_udp2raw', False):
            self.remove_udp2raw_service()
            steps.append("UDP2RAW service removed")
        
        steps.append(f"\n✓ Tunnel '{tunnel_name}' teardown complete!")
        return True, "\n".join(steps)

    def check_ping(self, count: int = 1, timeout: int = 1) -> str:
        """
        Check ping to the remote interface IP.
        Returns formatted string like '45ms' or 'Timeout'.
        """
        target_ip = self.config.interface_ip.split('/')[0]
        ip_parts = target_ip.split('.')
        last_octet = int(ip_parts[-1])
        
        # Simple logic for /30 subnet (assuming .1 and .2 pair)
        if last_octet % 2 == 1: 
            target_ip = f"{ip_parts[0]}.{ip_parts[1]}.{ip_parts[2]}.{last_octet + 1}"
        else: 
            target_ip = f"{ip_parts[0]}.{ip_parts[1]}.{ip_parts[2]}.{last_octet - 1}"
        
        cmd = f"ping -c {count} -W {timeout} {target_ip}"
        result = run_command(cmd)

        if result.success:
            import re
            match = re.search(r'time=([\d.]+)\s*ms', result.stdout)
            if match:
                return f"{match.group(1)}ms"
            return "OK"
        return "Timeout"
        
    def get_status(self) -> Dict[str, any]:
        """Get comprehensive tunnel status."""
        status = {
            "tunnel_name": self.config.name,
            "configured": self.config.is_configured(),
            "local_ip": self.config.local_ip,
            "remote_ip": self.config.remote_ip,
            "interface_name": self.interface_name,
            "tunnel_exists": False,
            "session_exists": False,
            "interface_up": False,
            "interface_ip": None,
            "tunnel_info": "",
            "session_info": "",
            "interface_info": "",
        }
        
        # Check tunnel
        result = run_command("ip l2tp show tunnel")
        status["tunnel_info"] = result.stdout if result.success else result.stderr
        status["tunnel_exists"] = self.check_tunnel_exists()
        
        # Check session
        result = run_command("ip l2tp show session")
        status["session_info"] = result.stdout if result.success else result.stderr
        status["session_exists"] = self.check_session_exists()
        
        # Check interface
        result = run_command(f"ip addr show {self.interface_name} 2>/dev/null")
        if result.success and result.stdout:
            status["interface_info"] = result.stdout
            status["interface_up"] = "UP" in result.stdout
            # Extract IP
            ip_match = re.search(r'inet\s+(\d+\.\d+\.\d+\.\d+/\d+)', result.stdout)
            if ip_match:
                status["interface_ip"] = ip_match.group(1)
        
        return status
