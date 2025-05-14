import time
from flask import Flask, render_template, request, redirect, url_for, flash, session
import xmlrpc.client
import docker
import os  # noqa: F401
import random
import string
import logging

app = Flask(__name__, template_folder='./templates')
app.secret_key = "supersecretkey"

logging.basicConfig(filename='/var/log/master.log', level=logging.INFO,
                    format='%(asctime)s - %(message)s')

docker_client = docker.from_env()

port_registry = {}


def initialize_available_ports():
    used_ports = [c.attrs['HostConfig']['PortBindings']['8000/tcp'][0]['HostPort'] for c in
                  docker_client.containers.list() if
                  c.attrs['HostConfig']['PortBindings'] and '8000/tcp' in c.attrs['HostConfig']['PortBindings']]
    used_ports = [int(p) for p in used_ports if p]
    return [p for p in range(8001, 8100) if p not in used_ports]


available_ports = initialize_available_ports()


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
        logging.info(f"Received create room request with player_name: {player_name}")
        if not (1 <= len(player_name) <= 20 and all(c.isalnum() or c == '_' for c in player_name)):
            logging.warning(f"Invalid player_name: {player_name}")
            flash("Invalid name. Use a-z, A-Z, 0-9, _, max 20 characters.")
            return redirect(url_for('create_room'))
        room_key = generate_room_key()
        player_id = generate_player_id()
        logging.info(f"Generated room_key: {room_key}, player_id: {player_id}")
        port = available_ports.pop(0) if available_ports else None
        if not port:
            logging.error("No available ports.")
            flash("No available ports. Try again later.")
            return redirect(url_for('create_room'))
        logging.info(f"Selected port: {port}")
        try:
            logging.info(f"Attempting to create container for room {room_key} on port {port}")
            container = docker_client.containers.run(
                'game-server',
                detach=True,
                ports={'8000/tcp': port},
                environment=[f"ROOM_KEY={room_key}"],
                volumes={'/game/logs': {'bind': '/game/logs', 'mode': 'rw'}}
            )
            logging.info(f"Container created: {container.id} for room {room_key} on port {port}")
            time.sleep(5)
            for attempt in range(3):
                try:
                    server = xmlrpc.client.ServerProxy(f"http://localhost:{port}/")
                    result = server.create_room(player_id, player_name)
                    logging.info(f"Container create_room result: {result}")
                    break
                except Exception as e:
                    logging.error(f"Attempt {attempt + 1} to call create_room failed: {str(e)}")
                    if attempt < 2:
                        time.sleep(2)
                    else:
                        raise Exception(f"Failed to initialize room {room_key}: {str(e)}")
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
            logging.info(
                f"Session set: player_id={player_id}, player_name={player_name}, room_key={room_key}, "
                f"session: {session}")
            flash(f"Room {room_key} created! Share this key with friends.")
            logging.info(f"Redirecting to room page: /room/{room_key}")
            return redirect(url_for('room', room_key=room_key))
        except Exception as e:
            logging.error(f"Failed to create room {room_key} on port {port}: {str(e)}")
            flash("Failed to create room. Try again.")
            available_ports.append(port)
            return redirect(url_for('create_room'))
    return render_template('create.html')


@app.route('/join', methods=['GET', 'POST'])
def join_room():
    if request.method == 'POST':
        room_key = request.form['room_key'].strip().upper()
        player_name = request.form['player_name'].strip()
        logging.info(f"Received join room request with room_key: {room_key}, player_name: {player_name}")
        if not (1 <= len(player_name) <= 20 and all(c.isalnum() or c == '_' for c in player_name)):
            logging.warning(f"Invalid player_name: {player_name}")
            flash("Invalid name. Use a-z, A-Z, 0-9, _, max 20 characters.")
            return redirect(url_for('join_room'))
        if room_key not in port_registry:
            logging.error(f"Room {room_key} not in port_registry: {port_registry}")
            flash("Room does not exist.")
            return redirect(url_for('join_room'))
        if player_name in port_registry[room_key]['player_names']:
            logging.warning(f"Player name {player_name} already taken in room {room_key}")
            flash("Name already taken in this room.")
            return redirect(url_for('join_room'))
        player_id = generate_player_id()
        logging.info(f"Generated player_id: {player_id} for joining room {room_key}")
        try:
            server = xmlrpc.client.ServerProxy(f"http://localhost:{port_registry[room_key]['port']}/")
            response = server.join_room(room_key, player_id, player_name)
            logging.info(f"Join room response: {response}")
            if "Cannot join" in response or "already in use" in response or "Room is full" in response:
                flash(response)
                return redirect(url_for('join_room'))
            port_registry[room_key]['player_ids'].append(player_id)
            port_registry[room_key]['player_names'].append(player_name)
            logging.info(f"{player_id}:{player_name} joined room {room_key}")
            session['player_id'] = player_id
            session['player_name'] = player_name
            session['room_key'] = room_key
            logging.info(f"Session set for join: player_id={player_id}, player_name={player_name}, room_key={room_key},"
                         f"session: {session}")
            flash(response)
            return redirect(url_for('room', room_key=room_key))
        except Exception as e:
            logging.error(f"Failed to join room {room_key}: {str(e)}")
            flash("Failed to join room. Try again.")
            return redirect(url_for('join_room'))
    return render_template('join.html')


@app.route('/room/<room_key>')
def room(room_key):
    logging.info(f"Accessing room page for room_key: {room_key}, session: {session}")
    if 'room_key' not in session or session['room_key'] != room_key:
        logging.warning(f"Session validation failed: room_key={room_key}, session_room_key={session.get('room_key')}")
        flash("Please join the room first.")
        return redirect(url_for('join_room'))
    if room_key not in port_registry:
        logging.error(f"Room {room_key} not in port_registry: {port_registry}")
        flash("Room does not exist.")
        return redirect(url_for('home'))
    port = port_registry[room_key]['port']
    logging.info(f"Connecting to container for room {room_key} on port {port}")
    for attempt in range(5):
        try:
            server = xmlrpc.client.ServerProxy(f"http://localhost:{port}/")
            state = server.get_game_state(room_key, session['player_id'])
            logging.info(f"Game state retrieved for room {room_key}: {state}")
            if not state:
                logging.error(f"Invalid room or player for room_key: {room_key}, player_id: {session.get('player_id')}")
                flash("Invalid room or player.")
                return redirect(url_for('home'))
            logging.info(f"Rendering room.html for room {room_key}")
            return render_template('room.html', state=state)
        except Exception as e:
            logging.error(f"Attempt {attempt + 1} failed for room {room_key} on port {port}: {str(e)}")
            if attempt < 4:
                time.sleep(2)
            else:
                flash("Failed to load room. Try again.")
                return redirect(url_for('home'))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
