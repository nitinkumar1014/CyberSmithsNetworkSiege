import xmlrpc.client
import time


def main():
    print("Welcome to CyberSmith's Network Siege!")
    print("1. Create a Room - Type CREATE")
    print("2. Join a Room - Type JOIN")
    choice = input("Enter your choice: ").strip().upper()

    server = xmlrpc.client.ServerProxy("http://localhost:8000/")
    player_id = input("Enter your player ID: ").strip()

    try:
        if choice == "CREATE":
            room_key, port = server.createRoom()
            print(f"Room created! Room key: {room_key}, Port: {port}")
            player_name = input("Enter your player name: ").strip()
            response = server.join_room(room_key, player_id, player_name)
            print(response)
        elif choice == "JOIN":
            room_key = input("Enter your room key: ").strip()
            player_name = input("Enter your player name: ").strip()
            response = server.join_room(room_key, player_id, player_name)
            print(response)
        else:
            print("Invalid choice. Use CREATE or JOIN.")
            return

        while True:
            state = server.get_game_state(room_key, player_id)
            if not state:
                print("Invalid player ID or room error.")
                break
            print(f"\n=== Game State ===")
            print(f"Room: {state['room_key']}")
            print(f"Phase: {state['phase']}")
            print(f"Your role: {state['role']}")
            print(f"Your name: {state['name']}")
            print(f"Alive players: {', '.join(state['alive'])}")
            print(f"Total players: {state['player_count']}")
            if state.get("hacker_ids"):
                print(f"Hacker Team: {', '.join(state['hacker_ids'])}")
            if state["instructions"]:
                print(f"Instructions: \n{state['instructions']}")

            if state["phase"] != "setup":
                print("Game started! Use restricted terminal for commands (to be implemented).")
                break
            print("Waiting for more players...")
            time.sleep(2)

    except xmlrpc.client.Fault as e:
        print(f"Server error: {e}")
    except xmlrpc.client.ProtocolError:
        print(f"Failed to connect to server. Ensure server is running.")
    except Exception as e:
        print(f"Unexpected error: {e}")


if __name__ == "__main__":
    main()
