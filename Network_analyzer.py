#!/usr/bin/env python3
"""
Advanced IP Mass Surveillance Tool
Real-time network monitoring, service fingerprinting, connection tracking
Autorizado para pentest - Executa em sandbox isolado
"""

import socket
import threading
import subprocess
import json
import time
import sys
from datetime import datetime
from scapy.all import sniff, IP, TCP, UDP, sr1, ARP
import nmap
import requests
from concurrent.futures import ThreadPoolExecutor
import psutil


class MassSurveillance:
    def __init__(self, target_ip):
        self.target_ip = target_ip
        self.active_connections = {}
        self.services = {}
        self.packets_captured = 0
        self.session_start = datetime.now()

    def banner_grab(self, port):
        """Realiza banner grabbing em porta específica"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3)
            sock.connect((self.target_ip, port))
            sock.send(b"HEAD / HTTP/1.1\r\nHost: {}\r\n\r\n".format(self.target_ip.encode()))
            response = sock.recv(1024).decode(errors='ignore')
            sock.close()
            return response.strip()
        except:
            return None

    def nmap_scan(self):
        """Scan completo NMAP com scripts NSE"""
        print(f"[+] Executando NMAP completo em {self.target_ip}...")
        nm = nmap.PortScanner()

        # Scan rápido dos top 1000 ports
        nm.scan(self.target_ip, '1-1000', arguments='-sS -sV --top-ports 1000 -T4')

        # Scan UDP básico
        nm.scan(self.target_ip, '1-1000', arguments='-sU --top-ports 100')

        # Scripts NSE para enumeração avançada
        nm.scan(self.target_ip, arguments='-sV -sC --script=default,vuln')

        return nm

    def arp_scan_network(self):
        """Descobre hosts na mesma rede via ARP"""
        print(f"[+] ARP scan na rede local...")
        try:
            result = sr1(ARP(pdst="192.168.1.0/24"), timeout=2, verbose=0)
            if result:
                return [host[1].psrc for host in result[ARP]]
        except:
            pass
        return []

    def monitor_live_connections(self):
        """Monitora conexões TCP/UDP ativas do target em tempo real"""

        def check_connections():
            while True:
                try:
                    for conn in psutil.net_connections(kind='inet'):
                        if conn.raddr and conn.raddr.ip == self.target_ip:
                            key = f"{conn.laddr.ip}:{conn.laddr.port}->{conn.raddr.ip}:{conn.raddr.port}"
                            if key not in self.active_connections:
                                self.active_connections[key] = {
                                    'status': conn.status,
                                    'type': conn.type,
                                    'timestamp': datetime.now().isoformat()
                                }
                                print(f"[LIVE] Nova conexão: {key} (Status: {conn.status})")
                except:
                    pass
                time.sleep(2)

        threading.Thread(target=check_connections, daemon=True).start()

    def packet_sniffer(self, count=1000):
        """Sniffer de pacotes focado no target"""
        print(f"[+] Iniciando packet sniffer (primeiros {count} pacotes)...")

        def packet_handler(pkt):
            self.packets_captured += 1
            if IP in pkt:
                if pkt[IP].src == self.target_ip or pkt[IP].dst == self.target_ip:
                    direction = "OUT" if pkt[IP].src == self.target_ip else "IN"
                    proto = pkt[IP].proto
                    src_port = pkt[TCP].sport if TCP in pkt else (pkt[UDP].sport if UDP in pkt else "N/A")
                    dst_port = pkt[TCP].dport if TCP in pkt else (pkt[UDP].dport if UDP in pkt else "N/A")

                    print(
                        f"[{direction}] {pkt[IP].src}:{src_port} -> {pkt[IP].dst}:{dst_port} | Proto: {proto} | Size: {len(pkt)}")

        sniff(filter=f"host {self.target_ip}", prn=packet_handler, count=count, timeout=30)

    def whois_lookup(self):
        """Consulta WHOIS do IP"""
        try:
            result = subprocess.run(['whois', self.target_ip],
                                    capture_output=True, text=True, timeout=10)
            return result.stdout
        except:
            return "WHOIS não disponível"

    def geolocate_ip(self):
        """Geolocalização do IP"""
        try:
            response = requests.get(f"http://ip-api.com/json/{self.target_ip}", timeout=5)
            return response.json()
        except:
            return None

    def run_full_surveillance(self):
        """Executa surveillance completo"""
        print(f"🚀 Iniciando MASS SURVEILLANCE em {self.target_ip}")
        print(f"📅 Início: {self.session_start}")
        print("-" * 80)

        # 1. WHOIS e Geolocalização
        print("[1] WHOIS & GEOLOCATION")
        whois = self.whois_lookup()
        geo = self.geolocate_ip()
        print(f"   WHOIS: {whois[:200]}...")
        if geo:
            print(
                f"   GEO: {geo.get('country', 'N/A')} - {geo.get('city', 'N/A')} ({geo.get('lat', 0)}, {geo.get('lon', 0)})")

        # 2. NMAP Scan
        print("\n[2] NMAP SERVICE DISCOVERY")
        nm = self.nmap_scan()
        for host in nm.all_hosts():
            print(f"   Host: {host}")
            for proto in nm[host].all_protocols():
                ports = nm[host][proto].keys()
                for port in ports:
                    state = nm[host][proto][port]['state']
                    service = nm[host][proto][port].get('name', 'unknown')
                    version = nm[host][proto][port].get('version', 'N/A')
                    print(f"     {port}/tcp {state} {service} {version}")

        # 3. Banner Grabbing nos ports abertos
        print("\n[3] BANNER GRABBING")
        open_ports = []
        for host in nm.all_hosts():
            for proto in nm[host].all_protocols():
                ports = nm[host][proto].keys()
                open_ports.extend([int(p) for p in ports if nm[host][proto][p]['state'] == 'open'])

        with ThreadPoolExecutor(max_workers=20) as executor:
            banners = list(executor.map(self.banner_grab, open_ports[:20]))  # Top 20

        for port, banner in zip(open_ports[:20], banners):
            if banner:
                print(f"   {port}: {banner[:100]}...")

        # 4. Monitoramento em tempo real
        print("\n[4] LIVE MONITORING (pressione Ctrl+C para parar)")
        self.monitor_live_connections()

        try:
            self.packet_sniffer()
        except KeyboardInterrupt:
            pass

        # Relatório final
        print("\n" + "=" * 80)
        print("📊 RELATÓRIO FINAL")
        print(f"Pacotes capturados: {self.packets_captured}")
        print(f"Conexões ativas detectadas: {len(self.active_connections)}")
        print(f"Serviços abertos: {len(open_ports)}")
        print(f"Duração: {datetime.now() - self.session_start}")
        print("=" * 80)


def main():
    if len(sys.argv) != 2:
        print("Uso: python3 mass_surveillance.py <IP_TARGET>")
        sys.exit(1)

    target = sys.argv[1]

    # Validação básica de IP
    try:
        socket.inet_aton(target)
    except:
        print("❌ IP inválido!")
        sys.exit(1)

    surveillance = MassSurveillance(target)
    surveillance.run_full_surveillance()


if __name__ == "__main__":
    main()