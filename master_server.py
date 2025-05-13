from flask import Flask, render_template, request, redirect, url_for, flash, session
import xmlrpc.client
import docker
import os  # noqa: F401
import random
import string
import logging

app = Flask(__name__, template_folder='./templates')
app.secret_key = "supersecretkey"  # For flash messages and sessions

# Configure logging
logging.basicConfig(filename='/var/log/master.log', level=logging.INFO,
                    format='%(asctime)s - %(message)s')

# Docker client
docker_client = docker.from_env()

# Port registry (room_key -> port, container_id)
port_registry = {}
available_ports = list(range(8001, 8100))  # Available ports


def generate_room_key():
    chars = string.ascii_uppercase + string.digits
    return ''.join(random.choice(chars) for _ in range(6))


def generate_player_id():
    existing_ids = [pid for room in port_registry.values() for pid in room.get('player_ids', [])]
    i = 1
    while f"player{i}" in existing_ids:
        i += 1
    return f"player{i}"


@app.route('/')
def home():
    return render_template('home.html')


@app.route('/create', methods=['GET', 'POST'])
def create_room():
    if request.method == 'POST':
        player_name = request.form['player_name'].strip()
        # Validate name (a-z, A-Z, 0-9, _, max 20 chars)
        if not (1 <= len(player_name) <= 20 and all(c.isalnum() or c == '_' for c in player_name)):
            flash("Invalid name. Use a-z, A-Z, 0-9, _, max 20 characters.")
            return redirect(url_for('create_room'))
        room_key = generate_room_key()
        player_id = generate_player_id()
        # Start container
        port = available_ports.pop(0) if available_ports else None
        if not port:
            flash("No available ports. Try again later.")
            return redirect(url_for('create_room'))
        try:
            container = docker_client.containers.run(
                'game-server',
                detach=True,
                ports={'8000/tcp': port},
                environment=[f"ROOM_KEY={room_key}"],
                volumes={'/game/logs': {'bind': '/game/logs', 'mode': 'rw'}}
            )
            port_registry[room_key] = {
                'port': port,
                'container_id': container.id,
                'player_ids': [player_id],
                'player_names': [player_name]
            }
            logging.info(f"Created room {room_key} on port {port} for {player_id}:{player_name}")
            session['player_id'] = player_id
            session['player_name'] = player_name
            session['room_key'] = room_key
            flash(f"Room {room_key} created! Share this key with friends.")
            return redirect(url_for('room', room_key=room_key))
        except Exception as e:
            logging.error(f"Failed to create room {room_key}: {e}")
            flash("Failed to create room. Try again.")
            available_ports.append(port)
            return redirect(url_for('create_room'))
    return render_template('create.html')


@app.route('/join', methods=['GET', 'POST'])
def join_room():
    if request.method == 'POST':
        room_key = request.form['room_key'].strip().upper()
        player_name = request.form['player_name'].strip()
        # Validate name
        if not (1 <= len(player_name) <= 20 and all(c.isalnum() or c == '_' for c in player_name)):
            flash("Invalid name. Use a-z, A-Z, 0-9, _, max 20 characters.")
            return redirect(url_for('join_room'))
        if room_key not in port_registry:
            flash("Room does not exist.")
            return redirect(url_for('join_room'))
        # Check name uniqueness
        if player_name in port_registry[room_key]['player_names']:
            flash("Name already taken in this room.")
            return redirect(url_for('join_room'))
        player_id = generate_player_id()
        # Connect to room server
        try:
            server = xmlrpc.client.ServerProxy(f"http://localhost:{port_registry[room_key]['port']}/")
            response = server.join_room(room_key, player_id, player_name)
            if "Game starting" in response:
                port_registry[room_key]['player_ids'].append(player_id)
                port_registry[room_key]['player_names'].append(player_name)
                logging.info(f"{player_id}:{player_name} joined room {room_key}")
                session['player_id'] = player_id
                session['player_name'] = player_name
                session['room_key'] = room_key
                flash(response)
                return redirect(url_for('room', room_key=room_key))
            else:
                flash(response)
                return redirect(url_for('join_room'))
        except Exception as e:
            logging.error(f"Failed to join room {room_key}: {e}")
            flash("Failed to join room. Try again.")
            return redirect(url_for('join_room'))
    return render_template('join.html')


@app.route('/room/<room_key>')
def room(room_key):
    if 'room_key' not in session or session['room_key'] != room_key:
        flash("Please join the room first.")
        return redirect(url_for('join_room'))
    server = xmlrpc.client.ServerProxy(f"http://localhost:{port_registry[room_key]['port']}/")
    state = server.get_game_state(room_key, session['player_id'])
    if not state:
        flash("Invalid room or player.")
        return redirect(url_for('home'))
    return render_template('room.html', state=state)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
