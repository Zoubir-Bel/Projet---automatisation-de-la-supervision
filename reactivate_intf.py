import re
import time
import paramiko

ROUTER_IP = "192.168.1.1"
USERNAME = "root"
PASSWORD = "XXXXXXXX"

LATENCY_THRESHOLD_MS = 10  # seuil de latence
CHECK_INTERVAL = 30  # secondes entre chaque cycle

def ssh_exec(commands):
    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(
            ROUTER_IP,
            username=USERNAME,
            password=PASSWORD,
            look_for_keys=False,
            timeout=10,
            banner_timeout=10
        )

        shell = client.invoke_shell()
        time.sleep(1)
        output = ""

        if shell.recv_ready():
            output += shell.recv(65535).decode()

        for cmd in commands:
            shell.send(cmd + "\n")
            time.sleep(1.5)
            while shell.recv_ready():
                output += shell.recv(65535).decode()

        client.close()
        return output

    except Exception as e:
        return f"[ERREUR SSH] {e}"

def get_shut_interfaces():
    output = ssh_exec(["show interfaces brief"])
    print("---------int brief------------\n", output)
    shut_interfaces = []
    for line in output.splitlines():
        if "admin-down" in line:
            match = re.search(r"(Gi\d+/\d+/\d+/\d+)", line)
            if match:
                shut_interfaces.append(match.group(1))
    print("---------shut_interfaces------------\n", shut_interfaces)
    return shut_interfaces

def get_neighbor_ip_from_interface(interface):
    output = ssh_exec(["show ip ospf neighbor"])
    for line in output.splitlines():
        if interface in line:
            parts = line.split()
            if len(parts) >= 6:
                return parts[4]
    return None

def get_ping_latency(ip):
    print(f"[PING] Test vers {ip}...")
    output = ssh_exec([f"ping {ip} repeat 5"])
    print("--------ping output--------\n", output)

    match = re.search(r"Success rate is \d+ percent \((\d+)/\d+\), round-trip min/avg/max = [\d\.]+/([\d\.]+)/", output)
    if match:
        avg_latency = float(match.group(2))
        print(f"[RESULTAT] Moyenne latence : {avg_latency}ms")
        return avg_latency
    else:
        print("[ERREUR] Impossible de récupérer la latence.")
        return None

def reactivate_and_test(interface):
    print(f"[ACTION] Tentative de réactivation de {interface}")

    ssh_exec([
        "configure terminal",
        f"interface {interface}",
        "no shutdown",
        "commit",
        "exit"
    ])

    print("[INFO] Attente 30s...")
    time.sleep(30)

    neighbor_ip = get_neighbor_ip_from_interface(interface)
    if not neighbor_ip:
        print(f"[WARNING] Aucun voisin détecté sur {interface}")
        return

    latency = get_ping_latency(neighbor_ip)
    if latency is None or latency > LATENCY_THRESHOLD_MS:
        print(f"[ALERTE] Latence {latency}ms trop élevée. On remet {interface} en shutdown.")
        ssh_exec([
            "configure terminal",
            f"interface {interface}",
            "shutdown",
            "commit",
            "exit"
        ])
    else:
        print(f"[OK] Latence correcte ({latency}ms). Interface {interface} reste active.")

# ===============================
# BOUCLE PRINCIPALE
# ===============================
print("[START] Lancement du monitoring...")

while True:
    print("\n[LOOP] Vérification des interfaces down...")
    shut_ifs = get_shut_interfaces()

    for iface in shut_ifs:
        reactivate_and_test(iface)

    print(f"[SLEEP] En attente de {CHECK_INTERVAL} secondes...\n")
    time.sleep(CHECK_INTERVAL)
