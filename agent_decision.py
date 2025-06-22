import re
import time
import paramiko

# --- Paramètres SSH - Router 1---
ROUTER_IP = "192.168.1.1"
USERNAME = "root"
PASSWORD = "XXXXXXXX"

# --- Seuils ---
#For manual test CPU=7%
CPU_THRESHOLD = 90
#For manual test 50%
MEMORY_THRESHOLD = 90
TEMP_THRESHOLD = 70.0  # en °C
LATENCY_AVG_THRESHOLD = 40  # ms
LATENCY_MAX_THRESHOLD = 40  # ms
# --- Fonction SSH ---

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
            time.sleep(1.5)  # attend un peu pour la sortie
            while shell.recv_ready():
                output += shell.recv(65535).decode()
        client.close()
        return output
    except Exception as e:
        return f"[ERREUR SSH] {e}"

def handle_high_cpu(cpu_value):
    print(f"[ALERTE] CPU saturée : {cpu_value}%")
    print("[ACTION] Désactivation de toutes les interfaces sauf la management...")
    interfaces = ssh_exec(["show interface brief"])
    print("Showing status of interfaces (UP) : \n " , interfaces)
    interfaces_to_shutdown = []
    for line in interfaces.splitlines():
        stripped = line.strip()
        if stripped.startswith("Gi") and "up" in stripped:
            iface = stripped.split()[0]
            if iface != "Gi0/0/0/0":  # L'interface management à exclure
                interfaces_to_shutdown.append(iface)
    print("interfaces to shutdown : " , interfaces_to_shutdown)
    for interface in interfaces_to_shutdown:
        print(f"[ACTION] Désactivation de l'interface {interface}")
        ssh_exec([
          "configure terminal",
          f"interface {interface}",
          "shutdown",
          "commit",
          "exit"])
    print("Showing status of interfaces (After shutting them down) :\n " , ssh_exec(["show interface brief"]))

def handle_high_memory(memory_value):
    print(f"[ALERTE] Mémoire saturée : {memory_value}%")
    print("[ACTION 0] Suppression des logs")
    ssh_exec("clear logging")
    output = ssh_exec([
        "clear logging",
        "y"
    ])
    print("[INFO] Résultat clear logging :")
    print(output)
    print("Fin [ACTION 0]")
    print("[ACTION 1] Redémarrage du routeur")
    ssh_exec([
      "reload",
      "",
      ""])
    print("Fin [ACTION 1]")

def handle_high_temperature(temp_value):
    print(f"[ALERTE] Température élevée : {temp_value}°C")
    print("[ACTION] Notification admin et extinction du routeur...")
    ssh_exec(f"echo 'ALERTE: Température critique détectée {temp_value} degree")
    print("Envoyer un message au NOC ou  l'administrateur")
    #ssh_exec("shutdown now") 

def handle_power_supply(status):
    if status.strip().upper() != "OK":
        print(f"[ALERTE] Anomalie alimentation : statut = '{status}'")
    else:
        print(f"[OK] Alimentation : statut = {status}")

def extract_neighbor_latencies(file_path):
    latencies = {}
    with open(file_path, "r") as f:
        for line in f:
            match = re.search(r"Latency to (\d+\.\d+\.\d+\.\d+) : avg (\d+)", line)
            if match:
                ip = match.group(1)
                avg_val = int(match.group(2))
                latencies[ip] = avg_val
    return latencies

def get_interface_from_ip(ip):
    print("--------IP------", ip)
    ospf_output = ssh_exec(["show ip ospf neighbor"])
    print("--------ospf_output------", ospf_output)
    lines = ospf_output.splitlines()
    print("--------lines------", lines)
    for line in lines:
        if ip in line:
            match = re.search(r"(GigabitEthernet\S+)", line)
            if match:
                return match.group(1)
    return None

def shutdown_interface(interface):
    print(f"[ACTION] Désactivation de l'interface {interface} pour reroutage...")
    ssh_exec([
        "configure terminal",
        f"interface {interface}",
        "shutdown",
        "commit",
        "exit"
    ])

def handle_latency(latencies):
    worst_ip = max(latencies, key=latencies.get)
    worst_avg = latencies[worst_ip]

    print(f"[ALERTE] Latence élevée détectée.")
    print(f"[INFO] Voisin OSPF le plus lent : {worst_ip} ({worst_avg}ms)")

    iface = get_interface_from_ip(worst_ip)
    if not iface:
        print(f"[ERREUR] Impossible de trouver l'interface liée à {worst_ip}")
        return

    shutdown_interface(iface)

def handle_low_healthscore(score):
    print(f"[ALERTE CRITIQUE] HealthScore très faible : {score}")
    print("[ACTION] Désactivation immédiate de toutes les interfaces sauf management")
    interfaces = ssh_exec(["show interface brief"])
    interfaces_to_shutdown = []
    for line in interfaces.splitlines():
        stripped = line.strip()
        if stripped.startswith("Gi") and "up" in stripped:
            iface = stripped.split()[0]
            if iface != "Gi0/0/0/0":  # Management non coupée
                interfaces_to_shutdown.append(iface)

    for interface in interfaces_to_shutdown:
        print(f"[ACTION] Shutdown {interface}")
        shutdown_interface(interface)
#        ssh_exec([
#            "configure terminal",
#            f"interface {interface}",
#            "shutdown",
#            "commit",
#            "exit"
#        ])
    
    print("[ALERTE ENVOYÉE] HealthScore critique. Interfaces désactivées.")

def handle_normal(label, value, unit="%"):
    print(f"[OK] {label} dans les normes : {value}{unit}")

def analyze_metrics(file_path):
    with open(file_path, 'r') as file:
        content = file.read()
    cpu_match = re.search(r'CPU\s*:\s*([\d.]+)%', content)
    memory_match = re.search(r'Memory\s*:\s*([\d.]+)%', content)
    temp_match = re.search(r'Temperature\s*:\s*([\d.]+)\s*°?C', content)
    power_match = re.search(r'Power Supply Status\s*:\s*(.+)', content)
    healthscore_match = re.search(r'HealthScore\s*:\s*([\d.]+)', content)
    if cpu_match and memory_match and temp_match : #and latency_match:
        cpu = float(cpu_match.group(1))
        memory = float(memory_match.group(1))
        temperature = float(temp_match.group(1))
        print(f"-------- Analyse des métriques --------")
        print(f"CPU : {cpu}%")
        print(f"Memory : {memory}%")
        print(f"Température : {temperature}°C")
        print(f"---------------------------------------")

        if cpu > CPU_THRESHOLD:
            handle_high_cpu(cpu)
        else:
            handle_normal("CPU", cpu)

        if memory > MEMORY_THRESHOLD:
            handle_high_memory(memory)
        else:
            handle_normal("Mémoire", memory)

        if temperature > TEMP_THRESHOLD:
            handle_high_temperature(temperature)
        else:
            handle_normal("Température", temperature, "°C")

        if power_match:
            power_status = power_match.group(1).strip()
            handle_power_supply(power_status)
        else:
            print("[ERREUR] Statut de l'alimentation non trouvé.")

        latencies = extract_neighbor_latencies(file_path)
        if not latencies:
            print("[INFO] Aucune latence vers voisins détectée.")
            return

        worst_avg = max(latencies.values())
        if worst_avg > LATENCY_AVG_THRESHOLD:
            handle_latency(latencies)
        else:
            print(f"[OK] Latences vers voisins OSPF dans les normes. Max avg = {worst_avg}ms")

        if healthscore_match:
            healthscore = float(healthscore_match.group(1))
            print(f"HealthScore : {healthscore}")
            if healthscore < 40:
                handle_low_healthscore(healthscore)
            else:
                handle_normal("HealthScore", healthscore)
        else:
            print("[ERREUR] HealthScore manquant.")

    else:
        print("[ERREUR] Certaines métriques sont manquantes ou mal formatées !")

analyze_metrics("metrics_output.txt")
