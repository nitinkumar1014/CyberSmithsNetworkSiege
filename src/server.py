from xmlrpc.server import SimpleXMLRPCServer
import threading
import random
import string
import os
import logging
from enum import Enum


class Role(Enum):
    HACKER = "Hacker"
    FIREWALL = "Firewall"
    AUDITOR = "Auditor"


class GameState:
    def __init__(self, room_key):
        self.room_key = room_key
        self.players = {}  # {player_id: name}
        self.roles = {}  # {player_id: role}
        self.alive = set()  # Set of alive players IDs
        self.phase = "setup"
        self.lock = threading.Lock()
        self.MAX_PLAYERS = 3
        self.instructions = """
        Welcome to CyberSmith's Network Siege!
        - Hacker: Attack other players to disrupt their system.
        - Firewall: Block attacks to protect a player each night.
        - Auditor: Investigate players to deduce their roles.
        - Game alternates between night (secret actions) and day (voting to ban).
        - Use restricted terminal commands (e.g., curl, who) to act (coming soon).
        """
        self.log_file = "/game/logs/activity.log"
        os.makedirs(os.path.dirname(self.log_file), exist_ok=True)
        logging.basicConfig(filename=self.log_file, level=logging.INFO, format='%(asctime)s - %(message)s')
        logging.info(f"Room {self.room_key} initialized")

    def join_room(self, player_id, player_name):
        with self.lock:
            if self.phase != "setup":
                return "Game has started. Cannot join."
            if len(self.players) >= self.MAX_PLAYERS:
                return "Room is full."
            if player_id in self.players:
                return f"Player ID {player_id} already in use."
            self.players[player_id] = player_name
            self.alive.add(player_id)
            logging.info(f"{player_id}:{player_name} joined room {self.room_key}")
            if len(self.players) >= self.MAX_PLAYERS:
                self.phase = "night"
                self.assign_roles()
                logging.info(f"Room {self.room_key} filled, starting night phase")
                return f"Joined room {self.room_key} as {player_name}. Game Starting.\n{self.instructions}"
            return (f"Joined room {self.room_key} as {player_name}. Waiting for {self.MAX_PLAYERS - len(self.players)}"
                    f" more players.")

    def assign_roles(self):
        roles = [Role.HACKER, Role.FIREWALL, Role.AUDITOR]
        random.shuffle(roles)
        for player_id, role in zip(self.players.keys(), roles):
            self.roles[player_id] = role
        logging.info(f"Roles assigned: {', '.join(f'{pid}:{r.value}' for pid, r in self.roles.items())}")

    def get_game_state(self, player_id):
        with self.lock:
            if player_id not in self.players:
                return None
            role = self.roles.get(player_id, None)
            is_hacker = role == Role.HACKER
            hacker_ids = [pid for pid, r in self.roles.items() if
                          r == Role.HACKER and pid in self.alive] if is_hacker else []
            return {
                "room_key": self.room_key,
                "phase": self.phase,
                "role": role.value if role else "Not assigned",
                "name": self.players.get(player_id, "Unknown"),
                "alive": list(self.alive),
                "player_count": len(self.players),
                "hacker_count": hacker_ids,
                "instructions": self.instructions if self.phase != "setup" else ""
            }


def generate_room_key():
    length = 6
    chars = string.ascii_uppercase + string.digits
    return ''.join(random.choice(chars) for _ in range(length))


rooms = {}


def create_room():
    room_key = os.getenv("ROOM_KEY", generate_room_key())
    if room_key in rooms:
        return "Room key already exists.", 8000
    game = GameState(room_key)
    rooms[room_key] = game
    return room_key, 8000


def join_room(room_key, player_id, player_name):
    if room_key not in rooms:
        return "Room does not exist."
    return rooms[room_key].join_room(player_id, player_name)


server = SimpleXMLRPCServer(("0.0.0.0", 8000), allow_none=True)
server.register_function(create_room, "create_room")
server.register_function(join_room, "join_room")
server.register_function(
    lambda room_key, player_id: rooms[room_key].get_game_state(player_id) if room_key in rooms else None,
    "get_game_state")
print("Server running on port 8000...")
server.serve_forever()
