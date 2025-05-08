import xmlrpc.client


def main():
    server_url = input("Enter server IP (e.g., 192.168.1.100): ").strip()
    server = xmlrpc.client.ServerProxy(f"http://{server_url}:8000/")
    player_id = input("Enter player ID (e.g., user1): ").strip()

    try:
        response = server.register_player(player_id)
        print(response)
    except ConnectionError:
        print(f"Failed to connect to server. Check IP and ensure server is running.")


if __name__ == "__main__":
    main()
