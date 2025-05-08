from xmlrpc.server import SimpleXMLRPCServer
import threading


class GameState:
    def __init__(self):
        self.players = []
        self.lock = threading.Lock()

    def register_player(self, player_id):
        with self.lock:
            if player_id not in self.players:
                self.players.append(player_id)
                return f"Player {player_id} registered successfully. Current players: {self.players}"
            return f"Player {player_id} already registered."


game = GameState()

server = SimpleXMLRPCServer(("192.168.12.157", 8000), allow_none=True)
server.register_instance(game)
print("Server running on port 8000...")
server.serve_forever()
