import socket
import threading
import time
import os
from datetime import datetime

AGENT_ID = "agent_1"             
LOCAL_IP = "0.0.0.0"             
LOCAL_PORT = 9999                 

# Liste des voisins (ip, port) à qui envoyer les données
NEIGHBORS = [
    ("192.168.2.100", 9999),    
    ("192.168.3.100", 9999),
]

FILE_TO_SEND = "metrics_output.txt" 
SEND_INTERVAL = 10                   

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind((LOCAL_IP, LOCAL_PORT))

def udp_receiver():
    while True:
        data, addr = sock.recvfrom(65535)  
        text = data.decode('utf-8', errors='ignore')
        agent_id = None
        for line in text.splitlines():
            if line.lower().startswith("agent :"):
                agent_id = line.split(":",1)[1].strip()
                break
        if not agent_id:
            agent_id = addr[0].replace('.', '_')  # fallback IP formatée
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{agent_id}_metrics.txt"

        with open(filename, "w") as f:
            f.write(text)
        print(f"Reçu données de {agent_id} ({addr[0]}) sauvegardées dans {filename}")

def udp_sender():
    while True:
        if os.path.exists(FILE_TO_SEND):
            with open(FILE_TO_SEND, "r") as f:
                data = f.read()
        else:
            data = f"Fichier {FILE_TO_SEND} non trouvé sur agent {AGENT_ID}."

        msg_bytes = data.encode('utf-8')
        max_packet_size = 65507
        if len(msg_bytes) > max_packet_size:
            print("Attention : contenu trop volumineux, tronqué avant envoi.")
            msg_bytes = msg_bytes[:max_packet_size]

        for ip, port in NEIGHBORS:
            sock.sendto(msg_bytes, (ip, port))
            print(f"Envoyé contenu de {FILE_TO_SEND} à {ip}:{port}")
        time.sleep(SEND_INTERVAL)

if __name__ == "__main__":
    print(f"Démarrage agent {AGENT_ID} - écoute sur port {LOCAL_PORT}")
    threading.Thread(target=udp_receiver, daemon=True).start()
    threading.Thread(target=udp_sender, daemon=True).start()
    try:
        while True:
            time.sleep(10)
    except KeyboardInterrupt:
        print(f"Agent {AGENT_ID} arrêté")
        sock.close()
