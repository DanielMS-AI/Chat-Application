import socket       # TCP network communication
import threading    # listen for peers while accepting keyboard commands
import sys          # command-line arguments

connections = []
connections_lock = threading.Lock()
next_connection_id = 1


def close_connection(peer):
    """Remove a peer once, and wake up its blocked receiving thread."""
    with connections_lock:
        if peer not in connections:
            return
        connections.remove(peer)
    try:
        peer["socket"].shutdown(socket.SHUT_RDWR)
    except OSError:
        pass  # The other end may already have disconnected.
    peer["socket"].close()
    print(f"\nConnection {peer['id']} closed.")


def handle_connection(peer):
    """Receive complete lines, without automatically echoing them back."""
    try:
        # TCP can split or combine sends. A newline marks each whole message.
        with peer["socket"].makefile("rb") as incoming:
            for data in incoming:
                message = data.rstrip(b"\n").decode("utf-8", errors="replace")
                print(f"\nMessage from {peer['id']} ({peer['ip']}:{peer['port']}): {message}")
    except OSError:
        pass  # A disconnect or terminate command ends this receiver.
    finally:
        close_connection(peer)


def register_connection(peer_socket, address):
    """Track incoming and outgoing peers using IDs that never shift."""
    global next_connection_id
    with connections_lock:
        if len(connections) >= 3:
            peer_socket.close()
            return None
        peer = {
            "id": next_connection_id,
            "socket": peer_socket,
            "ip": address[0],
            "port": address[1],
        }
        next_connection_id += 1
        connections.append(peer)
    threading.Thread(target=handle_connection, args=(peer,), daemon=True).start()
    return peer


def listen_for_connections(listening_socket):
    while True:
        try:
            peer_socket, address = listening_socket.accept()
        except OSError:
            return  # The listening socket was closed during shutdown.
        peer = register_connection(peer_socket, address)
        if peer is None:
            print("\nConnection rejected: maximum 3 connections allowed.")
        else:
            print(f"\nGot connection {peer['id']} from {address}")


def list_connections():
    with connections_lock:
        peers = list(connections)
    if not peers:
        print("No active connections.")
        return
    print(f"{'ID':<6}{'IP address':<18}Peer port")
    for peer in peers:
        print(f"{peer['id']:<6}{peer['ip']:<18}{peer['port']}")
    # Incoming peer ports are source ports, not their listening ports.


def find_connection(connection_id):
    try:
        connection_id = int(connection_id)
    except ValueError:
        return None
    with connections_lock:
        return next((peer for peer in connections if peer["id"] == connection_id), None)


def send_message(connection_id, message):
    peer = find_connection(connection_id)
    if peer is None:
        return "Invalid connection ID. Use 'list' to see active connections."
    if not message.strip():
        return "Message cannot be empty."
    try:
        peer["socket"].sendall((message + "\n").encode("utf-8"))
    except OSError as error:
        close_connection(peer)
        return f"Message failed: {error}"
    return f"Message sent to connection {peer['id']}."


def terminate_connection(connection_id):
    peer = find_connection(connection_id)
    if peer is None:
        return "Invalid connection ID. Use 'list' to see active connections."
    close_connection(peer)
    return f"Terminated connection {peer['id']}."


def print_help():
    print("""
Available commands:
  help                          - Show this help message
  myip                          - Display this process's IP address
  myport                        - Display the listening port
  connect <destination> <port>  - Connect to a peer's IPv4 address and port
  list                          - List connection IDs, IP addresses, and peer ports
  terminate <connection id>     - Close the specified connection
  send <connection id> <msg>    - Send a message (spaces allowed)
  message <connection id> <msg> - Alias for send
  exit                          - Close all connections and quit
""")


def get_my_ip():
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as temp_socket:
        try:
            temp_socket.connect(("8.8.8.8", 80))
            return temp_socket.getsockname()[0]
        except OSError:
            return "127.0.0.1"  # Local testing still works without a network.


def connection(destination, port, my_port):
    try:
        socket.inet_pton(socket.AF_INET, destination)
    except OSError:
        return "Connection Failed: invalid IP address"
    try:
        port = int(port)
        if not 1 <= port <= 65535:
            raise ValueError
    except ValueError:
        return "Connection Failed: port must be between 1 and 65535"

    if port == my_port and (destination.startswith("127.") or destination == get_my_ip()):
        return "Can't connect to yourself"
    with connections_lock:
        if any(peer["ip"] == destination and peer["port"] == port for peer in connections):
            return "Connection Failed: Already connected to this address."
        if len(connections) >= 3:
            return "Connection Failed: maximum 3 connections allowed."

    peer_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        peer_socket.settimeout(5)
        peer_socket.connect((destination, port))
        peer_socket.settimeout(None)
    except OSError as error:
        peer_socket.close()
        return f"Connection Failed: {error}"
    peer = register_connection(peer_socket, (destination, port))
    if peer is None:
        return "Connection Failed: maximum 3 connections allowed."
    return f"Successfully connected to {destination} on port {port}. Connection ID: {peer['id']}."


def main():
    if len(sys.argv) != 2:
        print("Usage: python chat.py <port>")
        return 1
    try:
        my_port = int(sys.argv[1])
        if not 1 <= my_port <= 65535:
            raise ValueError
    except ValueError:
        print("Port must be a number between 1 and 65535.")
        return 1

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listening_socket:
        try:
            listening_socket.bind(("", my_port))
            listening_socket.listen(10)
        except OSError as error:
            print(f"Could not listen on port {my_port}: {error}")
            return 1
        threading.Thread(target=listen_for_connections, args=(listening_socket,), daemon=True).start()
        print(f"Listening on port {my_port}. Type 'help' for commands or 'exit' to quit.")
        try:
            while True:
                parts = input("Enter a command: ").strip().split(maxsplit=2)
                if not parts:
                    continue
                command = parts[0]
                if command == "help":
                    print_help()
                elif command == "myip":
                    print("My IP address:", get_my_ip())
                elif command == "myport":
                    print("My listening port:", my_port)
                elif command == "list":
                    list_connections()
                elif command == "connect":
                    if len(parts) != 3:
                        print("Usage: connect <destination> <port>")
                    else:
                        print(connection(parts[1], parts[2], my_port))
                elif command in ("send", "message"):
                    if len(parts) != 3:
                        print(f"Usage: {command} <connection id> <message>")
                    else:
                        print(send_message(parts[1], parts[2]))
                elif command == "terminate":
                    if len(parts) != 2:
                        print("Usage: terminate <connection id>")
                    else:
                        print(terminate_connection(parts[1]))
                elif command == "exit":
                    break
                else:
                    print("Unknown command. Type 'help' for options.")
        except (EOFError, KeyboardInterrupt):
            pass
        finally:
            with connections_lock:
                peers = list(connections)
            for peer in peers:
                close_connection(peer)
    print("Goodbye.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
