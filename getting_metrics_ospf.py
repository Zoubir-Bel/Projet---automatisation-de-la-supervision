import paramiko
import re
import time
import random

ROUTER_IP = "192.168.1.1"
USERNAME = "root"
PASSWORD = "XXXXXXXX"

def ssh_exec(command):
    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(
            ROUTER_IP,
            username=USERNAME,
            password=PASSWORD,
            look_for_keys=False,
            timeout=20,
            banner_timeout=20
        )

        time.sleep(0.5)
        stdin, stdout, stderr = client.exec_command(command)
        time.sleep(1)
        output = stdout.read().decode()
        client.close()
        return output
    except Exception as e:
        return f"[ERREUR SSH] {e}"

def get_cpu():
    output = ssh_exec("show processes cpu")
    match = re.search(r"CPU utilization for one minute: (\d+)%", output)
    return f"CPU : {match.group(1)}%" if match else "CPU : non trouvé"

def get_memory():
    output = ssh_exec("show watchdog memory-state")
    match_total = re.search(r"Physical Memory\s+:\s+([\d.]+)", output)
    match_free = re.search(r"Free Memory\s+:\s+([\d.]+)", output)
    if match_total and match_free:
        total = float(match_total.group(1))
        free = float(match_free.group(1))
        usage = round(((total - free) / total) * 100, 2)
        return f"Memory : {usage}%"
    else:
        return "Memory : non trouvée"

def get_latency():
    output = ssh_exec("ping ipv4 192.168.1.1 repeat 5")
    match = re.search(r"round-trip min/avg/max = (\d+)/(\d+)/(\d+)", output)
    if match:
        min_ = match.group(1)
        avg_ = match.group(2)
        max_ = match.group(3)
        return f"Latency : avg {avg_} ms | min {min_} ms | max {max_} ms"
    else:
        return "Latency : non trouvée"

def get_temperature():
    # Simulation réaliste température (entre 30 et 55 °C)
    temp = round(random.uniform(30.0, 55.0), 1)
    return f"Temperature : {temp} °C"

def get_power_status():
    # Toujours OK
    return "Power Supply Status : OK"

def extract_percentage(text):
    match = re.search(r"(\d+\.?\d*)", text)
    return float(match.group(1)) if match else None

def extract_latency_avg(text):
    match = re.search(r"avg (\d+\.?\d*)", text)
    return float(match.group(1)) if match else None

def extract_temperature(text):
    match = re.search(r"Temperature : (\d+\.?\d*)", text)
    return float(match.group(1)) if match else None

def calculate_healthscore(cpu_str, mem_str, latency_str, temp_str):
    cpu = extract_percentage(cpu_str)
    mem = extract_percentage(mem_str)
#    lat = extract_latency_avg(latency_str)
    lat = latency_str
    temp = extract_temperature(temp_str)

    if cpu is None or mem is None or lat is None or temp is None:
        return None

    # Poids (somme 1.0)
    w_cpu, w_mem, w_lat, w_temp = 0.35, 0.35, 0.2, 0.1
    
    # Normaliser latence et température (supposons max 100ms et 70°C)
    lat_norm = min(lat / 100.0, 1.0)
    temp_norm = min(temp / 70.0, 1.0)

    score = 100 - (w_cpu * cpu) - (w_mem * mem) - (w_lat * lat_norm * 100) - (w_temp * temp_norm * 100)
    return round(max(0, min(100, score)), 2)

def get_ospf_neighbors():
    output = ssh_exec("show ip ospf neighbor")
    ip_matches = re.findall(r"\d+\.\d+\.\d+\.\d+", output)
    link_ips = [ip for ip in ip_matches if ip.startswith("10.")]
    #return list(set(neighbors))
    return list(set(link_ips))  # en cas de doublons
def get_latency_all_intf(ip):
    output = ssh_exec(f"ping ipv4 {ip} repeat 5")
    match = re.search(r"min/avg/max = (\d+)/(\d+)/(\d+)", output)
    if match:
        return {
            "ip": ip,
            "min": int(match.group(1)),
            "avg": int(match.group(2)),
            "max": int(match.group(3)),
            "raw": f"Latency to {ip} : avg {match.group(2)} ms | min {match.group(1)} ms | max {match.group(3)} ms"
        }
    else:
        return {
            "ip": ip,
            "error": True,
            "raw": f"Latency to {ip} : non trouvée"
        }

if __name__ == "__main__":
    print("Collecte des métriques (CPU, mémoire, latence réelles; température et power simulés)...")

    cpu_str = get_cpu()
    print(cpu_str)
    time.sleep(1)

    mem_str = get_memory()
    print(mem_str)
    time.sleep(1)

    temp_str = get_temperature()
    print(temp_str)
    time.sleep(1)

    power_str = get_power_status()
    print(power_str)
    time.sleep(1)

    print("Détection des voisins OSPF...")
    neighbors = get_ospf_neighbors()
    neighbors_latencies = []
    avg_latencies = []

    for neighbor_ip in neighbors:
        latency = get_latency_all_intf(neighbor_ip)
        print(latency["raw"])
        neighbors_latencies.append(latency["raw"])
        if latency["avg"] is not None:
            avg_latencies.append(latency["avg"])

    if avg_latencies:
        avg_latency_val = sum(avg_latencies) / len(avg_latencies)
    else:
        avg_latency_val = 0

    healthscore = calculate_healthscore(cpu_str, mem_str, avg_latency_val, temp_str)
    print(healthscore)
    with open("metrics_output.txt", "w") as f:
        f.write(cpu_str + "\n")
        f.write(mem_str + "\n")
        #f.write(lat_str + "\n")
        f.write(temp_str + "\n")
        f.write(power_str + "\n")
        #f.write(healthscore + "\n")
        f.write(f"HealthScore : {healthscore}\n")
        f.write("\nLatence vers les voisins OSPF :\n")
        for line in neighbors_latencies:
            f.write(line + "\n")
    print("Toutes les métriques sont enregistrées (avec HealthScore) dans metrics_output.txt")


