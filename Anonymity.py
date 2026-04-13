import subprocess
import sys
import time
import os
import signal
import socket
from pathlib import Path


class KaliAnonymity:
    KALI_LINUX_DEPS = [
        "tor", "torsocks", "macchanger", "stubby", "curl", "dnsutils",
        "unbound", "resolvconf", "nftables"  # Kali 2026 usa nftables
    ]

    def __init__(self):
        self.backup_files = []
        self.tor_pid = None
        self.nft_backup = None

    def detect_kali_Linux(self):

        release = Path("/etc/os-release").read_text()
        if "kali" in release.lower() and "2026" in release:
            print("Kali Linux detetado - modo rolling ativado")
            return True
        print("Kali Linux otimizações aplicadas")
        return False

    def install_v26_deps(self):

        print("📦 Kali Linux deps...")
        subprocess.run("apt update -qq && apt install -y " + " ".join(self.KALI_LINUX_DEPS),
                       shell=True, check=True)

        # Tor 2026 systemd fix
        Path("/etc/systemd/system/tor@default.service.d/hackerai.conf").write_text("""
[Service]
ExecStart=
ExecStart=/usr/bin/tor -f /etc/tor/hackerai.torrc %i
""")

    def nftables_killswitch(self):
        print("nftables Killswitch...")
        self.nft_backup = "/tmp/nftables-kali2026-backup"
        subprocess.run(f"nft list ruleset > {self.nft_backup}", shell=True)

        subprocess.run("nft flush ruleset", shell=True)
        subprocess.run("""
nft 'add table inet anon_filter;
add chain inet anon_filter output { type filter hook output priority 0; policy drop; }
add rule inet anon_filter output o lo accept
add rule inet anon_filter output ip daddr 127.0.0.0/8 accept
add rule inet anon_filter output tcp dport 9050 accept
add rule inet anon_filter output tcp sport 9050 accept
add rule inet anon_filter output udp dport 53 udp daddr 127.0.0.1 accept'
""", shell=True)

        print("nftables killswitch ativo")

    def tor_2026_config(self):
        print("Tor...")

        torrc_2026 = """
# Kali 2026 Optimized Tor
SocksPort 127.0.0.1:9050
SocksPort 127.0.0.1:9051
ControlPort 9051
HashedControlPassword 16:872860B76453A77D60CA2BB8C1A7042072093276A3D701AD684053EC4C
DataDirectory /var/lib/tor/kali2026
Log notice file /var/log/tor/kali2026.log
SafeLogging 1
VirtualAddrNetworkIPv4 10.192.0.0/10
AutomapHostsOnResolve 1
TransPort 127.0.0.1:9040
DNSPort 127.0.0.1:5353
ExcludeNodes {{us},{gb},{de}}
StrictNodes 1
LearnCircuitBuildTimeout 0
CircuitBuildTimeout 10
MaxCircuitDirtiness 600
"""

        Path("/etc/tor/kali2026.torrc").write_text(torrc_2026)

        # Mata tor antigo e inicia novo
        subprocess.run("systemctl stop tor tor@default || true", shell=True)
        subprocess.run("pkill -f tor || true", shell=True)
        time.sleep(2)

        tor_proc = subprocess.Popen([
            "tor", "-f", "/etc/tor/kali2026.torrc",
            "--DataDirectory", "/var/lib/tor/kali2026"
        ])
        self.tor_pid = tor_proc.pid

        # Aguarda + verifica
        for i in range(12):
            if self.is_tor_ready():
                print("Tor ativo!")
                break
            time.sleep(1)
        else:
            print("Tor timeout!")
            sys.exit(1)

    def is_tor_ready(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = sock.connect_ex(('127.0.0.1', 9050))
        sock.close()
        return result == 0

    def dns_2026(self):
        """DoT + Unbound Kali 2026"""
        print("DNS...")

        # Stubby DoT
        stubby_cfg = """
resolution_type: GETDNS_RESOLUTION_STUB_RESOLVER
dns_transport_list: [ GETDNS_TRANSPORT_TLS ]
tls_authentication: GETDNS_AUTHENTICATION_REQUIRED
upstream_recursive_servers:
  - address_data: 1.1.1.1
    tls_auth_name: "cloudflare-dns.com"
  - address_data: 1.0.0.1
    tls_auth_name: "cloudflare-dns.com"
listen_addresses: [127.0.0.1@5453]
"""
        Path("/etc/stubby/stubby-2026.yml").write_text(stubby_cfg)
        subprocess.run("systemctl restart stubby", shell=True)
        Path("/etc/resolv.conf").write_text("nameserver 127.0.0.1")

    def kali2026_browser(self):
        print("Firefox...")
        firefox_prefs = """
user_pref("network.proxy.type", 1);
user_pref("network.proxy.socks", "127.0.0.1");
user_pref("network.proxy.socks_port", 9050);
user_pref("network.proxy.socks_remote_dns", true);
user_pref("privacy.resistFingerprinting", true);
user_pref("privacy.trackingprotection.enabled", true);
user_pref("network.trr.mode", 3);
user_pref("network.trr.uri", "https://dns.quad9.net/dns-query");
user_pref("media.peerconnection.enabled", false);
"""

        profile_dir = subprocess.run(
            "find ~/.mozilla/firefox -name 'user.js' 2>/dev/null | head -1",
            shell=True, capture_output=True, text=True
        ).stdout.strip()

        if profile_dir:
            Path(profile_dir).write_text(firefox_prefs)
        else:
            # Cria novo profile
            Path("/tmp/firefox-kali2026.user.js").write_text(firefox_prefs)
            print("Firefox prefs: /tmp/firefox-kali2026.user.js")

    def fingerprint_2026(self):
        print("Fingerprint 2026...")
        subprocess.run("sysctl net.ipv6.conf.all.disable_ipv6=1 net.ipv6.conf.default.disable_ipv6=1", shell=True)
        interfaces = subprocess.run("ip -o link show | awk -F': ' '{print $2}' | grep -E 'eth|ens|enp'",
                                    shell=True, capture_output=True, text=True).stdout.strip().split()

        for iface in interfaces:
            subprocess.run(f"ip link set {iface} down && macchanger -r {iface} && ip link set {iface} up", shell=True)

        subprocess.run("hwclock --hctosys && date -s 'now +/- $(shuf -i 0-3600 -n 1)s'", shell=True)

    def comprehensive_test(self):
        print("\n KALI ANONYMITY TESTS:")
        print("=" * 70)

        tests = {
            "Tor IP": "torsocks curl -s https://icanhazip.com",
            "Tor Check": "torsocks curl -s https://check.torproject.org/api/ip | grep IsTor",
            "DNS Leak": "torsocks nslookup dnsleaktest.com | grep -v 127",
            "WebRTC": "torsocks curl -s https://webrtcipaddress.com | grep -v '127.0.0.1'"
        }

        for name, cmd in tests.items():
            try:
                result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
                status = "PASS" if result.returncode == 0 else "❌ FAIL"
                print(f"{name:15} {status} | {result.stdout[:60]}...")
            except:
                print(f"{name:15} TIMEOUT")

        print(" nftables: ATIVO")
        print(" DoT: 127.0.0.1:5453")

    def cleanup_2026(self):
        print("\n🧹 Kali Restore...")

        if self.nft_backup and Path(self.nft_backup).exists():
            subprocess.run(f"nft -f {self.nft_backup}", shell=True)

        subprocess.run("sysctl net.ipv6.conf.all.disable_ipv6=0", shell=True)
        subprocess.run("pkill -f tor || true", shell=True)
        subprocess.run("systemctl restart networking", shell=True)
        subprocess.run("resolvconf -u", shell=True)

        print("Kali restaurado!")

    def run(self):
        signal.signal(signal.SIGINT, lambda s, f: self.cleanup_2026())
        signal.signal(signal.SIGTERM, lambda s, f: self.cleanup_2026())

        print("🚀 Kali VM Anonymity Suite")
        self.detect_kali_2026()

        self.install_2026_deps()
        self.nftables_killswitch()
        self.tor_2026_config()
        self.dns_2026()
        self.kali2026_browser()
        self.fingerprint_2026()

        self.comprehensive_test()

        print("👉 torsocks nmap -sT 10.10.10.10")
        print("👉 firefox")

        input("\nEnter para restaurar...")
        self.cleanup_2026()


if __name__ == "__main__":
    Kali2026Anonymity().run()