import socket       # lets us make network connections
import threading    # lets us run tasks at the same time
import sys          # lets us read the port number typed on the command line

# The assignment allows at most 3 connections at once.
MAX_CONNECTIONS = 3

# The assignment allows messages of up to 100 characters (spaces count).
MAX_MESSAGE_LENGTH = 100

# How many seconds 'connect' waits for the other peer's greeting.
HANDSHAKE_TIMEOUT = 3

# Our list of connections. Each connection is a dictionary with: id, socket, ip, and port
connections = []

# Several threads use the list above, so we take this lock before we read
# or change it. That keeps two threads from changing it at the same time.
connections_lock = threading.Lock()

# The id given to the next new connection. It only goes up, so an id never
# gets reused while the program is running.
next_connection_id = 1

# The port THIS program listens on. main() fills it in when the program
# starts so we can tell each peer which port we are listening on.
my_listening_port = None

# Close a connection and remove it from our list.
def close_connection(peer, closed_by_remote=False):
    with connections_lock:
        if peer not in connections:
            return  # it was already closed, so there is nothing to do
        connections.remove(peer)

    # This wakes up the thread that is waiting for messages from this peer
    # so that thread can finish.
    try:
        peer["socket"].shutdown(socket.SHUT_RDWR)
    except OSError:
        pass  # the other side may have already disconnected
    peer["socket"].close()

    if closed_by_remote:
        port = peer["port"] if peer["port"] is not None else "?"
        print(f"\nConnection {peer['id']} ({peer['ip']}:{port}) was closed by the remote peer.")


# Receiving messages (one thread for each connection)
def handle_connection(peer):
    # A peer that connected TO us starts with port = None, because we don't
    # know its listening port yet. Its first line should be the greeting
    # "PORT <number>". A peer that WE connected to already sent its greeting
    # (connection() read it), so every line from it is a real message.
    expecting_handshake = peer["port"] is None

    try:
        # makefile() lets us read one whole line at a time. Each message
        # ends with a new line character, so that is how we know where
        # one message stops and the next one starts.
        with peer["socket"].makefile("rb") as incoming:
            for data in incoming:
                text = data.rstrip(b"\r\n").decode("utf-8", errors="replace")

                # The greeting: save the peer's port so 'list' can show it.
                # It is not a chat message, so we don't print it.
                if expecting_handshake:
                    expecting_handshake = False
                    if text.startswith("PORT "):
                        try:
                            listening_port = int(text.split()[1])
                        except (IndexError, ValueError):
                            listening_port = None
                        if listening_port is not None:
                            with connections_lock:
                                peer["port"] = listening_port
                        continue

                # A real chat message. Print it in the format the
                # assignment asks for.
                print(f"\nMessage received from {peer['ip']}")
                print(f"Sender's Port: {peer['port']}")
                print(f'Message: "{text}"')
    except OSError:
        pass  # the peer disconnected, or we closed it with terminate
    finally:
        # If the peer is still in our list at this point, then the OTHER
        # side hung up. (When we close a connection ourselves, it is
        # removed from the list first.)
        close_connection(peer, closed_by_remote=True)

# Adding new connections
def register_connection(peer_socket, ip, port):

    global next_connection_id

    with connections_lock:
        is_full = len(connections) >= MAX_CONNECTIONS
        if not is_full:
            peer = {
                "id": next_connection_id,
                "socket": peer_socket,
                "ip": ip,
                "port": port,
            }
            next_connection_id += 1
            connections.append(peer)

    # We are full. Tell the other side, so it can show an error instead of
    # thinking the connection worked.
    if is_full:
        try:
            peer_socket.sendall(b"FULL\n")
        except OSError:
            pass
        peer_socket.close()
        return None

    # Send our greeting: the port we are listening on.
    try:
        peer_socket.sendall(f"PORT {my_listening_port}\n".encode("utf-8"))
    except OSError:
        close_connection(peer)
        return None

    threading.Thread(target=handle_connection, args=(peer,), daemon=True).start()
    return peer


def listen_for_connections(listening_socket):
    
    while True:
        try:
            # The program waits on this line until a peer connects to us.
            peer_socket, address = listening_socket.accept()
        except OSError:
            return  # the listening socket was closed because we are exiting

        # address[1] is a random port the other computer used to reach us.
        # It is not useful, so we only keep the IP address. The peer's real
        # listening port comes in its greeting.
        peer = register_connection(peer_socket, address[0], None)
        if peer is None:
            print(f"\nConnection rejected: maximum {MAX_CONNECTIONS} connections allowed.")
        else:
            print(f"\nGot connection {peer['id']} from {address[0]}")

# The commands you can type
def print_help():
    """'help' -- show the list of commands."""
    print("""
Available commands:
  help                          - Show this help message
  myip                          - Display this process's IP address
  myport                        - Display the listening port
  connect <destination> <port>  - Connect to a peer's IPv4 address and port
  list                          - List connection IDs, IP addresses, and ports
  terminate <connection id>     - Close the specified connection
  send <connection id> <msg>    - Send a message (up to 100 characters)
  message <connection id> <msg> - Alias for send
  exit                          - Close all connections and quit
""")

def get_my_ip():
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as temp_socket:
        try:
            temp_socket.connect(("8.8.8.8", 80))
            return temp_socket.getsockname()[0]
        except OSError:
            return "127.0.0.1"  # no network, so use this to still allow local testing


def list_connections():
    # Copy the list while we hold the lock, then print after we let go of
    # it, so printing never makes the other threads wait.
    with connections_lock:
        peers = list(connections)
    if not peers:
        print("No active connections.")
        return
    print(f"{'ID':<6}{'IP address':<18}Port")
    for peer in peers:
        # "?" only shows for a split second, before the peer's greeting arrives
        port = peer["port"] if peer["port"] is not None else "?"
        print(f"{peer['id']:<6}{peer['ip']:<18}{port}")


def find_connection(connection_id):
    try:
        connection_id = int(connection_id)
    except ValueError:
        return None  # what the user typed is not a number
    with connections_lock:
        return next((peer for peer in connections if peer["id"] == connection_id), None)


def send_message(connection_id, message):
    peer = find_connection(connection_id)
    if peer is None:
        return "Invalid connection ID. Use 'list' to see active connections."
    if not message.strip():
        return "Message cannot be empty."
    if len(message) > MAX_MESSAGE_LENGTH:
        return f"Message too long: {len(message)} characters (maximum {MAX_MESSAGE_LENGTH})."
    try:
        # The new line at the end tells the receiver where the message ends.
        peer["socket"].sendall((message + "\n").encode("utf-8"))
    except OSError as error:
        close_connection(peer)  # the connection is broken, so remove it
        return f"Message failed: {error}"
    return f"Message sent to {peer['id']}"


def terminate_connection(connection_id):
    peer = find_connection(connection_id)
    if peer is None:
        return "Invalid connection ID. Use 'list' to see active connections."
    close_connection(peer)
    return f"Terminated connection {peer['id']}."


def read_first_line(sock):
    sock.settimeout(HANDSHAKE_TIMEOUT)
    data = b""
    try:
        while not data.endswith(b"\n") and len(data) < 64:
            chunk = sock.recv(1)
            if not chunk:
                return ""   # the peer hung up
            data += chunk
    except socket.timeout:
        return None         # nothing arrived in time
    except OSError:
        return ""           # the connection broke
    finally:
        try:
            sock.settimeout(None)   # go back to waiting as long as it takes
        except OSError:
            pass
    return data.decode("utf-8", errors="replace").strip()


def connection(destination, port, my_port):
    # Is the destination a valid IPv4 address?
    try:
        socket.inet_pton(socket.AF_INET, destination)
    except OSError:
        return "Connection Failed: invalid IP address"

    # Is the port a number between 1 and 65535?
    try:
        port = int(port)
        if not 1 <= port <= 65535:
            raise ValueError
    except ValueError:
        return "Connection Failed: port must be between 1 and 65535"

    # Are we trying to connect to ourselves? That means our own port, using
    # either 127.x.x.x or our real IP address.
    if port == my_port and (destination.startswith("127.") or destination == get_my_ip()):
        return "Can't connect to yourself"

    with connections_lock:
        # Are we already connected to this peer? This also catches a peer
        # that connected to us first, because we save its real port.
        if any(peer["ip"] == destination and peer["port"] == port for peer in connections):
            return "Connection Failed: Already connected to this address."
        if len(connections) >= MAX_CONNECTIONS:
            return f"Connection Failed: maximum {MAX_CONNECTIONS} connections allowed."

    # Open the connection. The 5 second timeout stops us from waiting
    # forever if the other computer can't be reached.
    peer_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        peer_socket.settimeout(5)
        peer_socket.connect((destination, port))
        peer_socket.settimeout(None)
    except OSError as error:
        peer_socket.close()
        return f"Connection Failed: {error}"

    # The connection can open and then be refused right away if the other
    # peer is full. So we wait for its greeting before saying it worked.
    reply = read_first_line(peer_socket)
    if reply == "FULL":
        peer_socket.close()
        return "Connection Failed: that peer already has the maximum number of connections."
    if reply == "":
        peer_socket.close()
        return "Connection Failed: the peer closed the connection right away."
    # A normal peer replies "PORT <number>". If reply is None, no greeting
    # arrived in time, so the peer is probably an older version of this
    # program. We connect anyway instead of refusing.

    peer = register_connection(peer_socket, destination, port)
    if peer is None:
        return f"Connection Failed: maximum {MAX_CONNECTIONS} connections allowed."
    return f"Successfully connected to {destination} on port {port}. Connection ID: {peer['id']}."

# Where the program starts
def main():
    global my_listening_port

    # The only thing typed after the program name is the port to listen on:
    #     python3 chat.py 4545
    # sys.argv is the list of words typed on the command line.
    # sys.argv[0] is "chat.py", so the port is sys.argv[1].
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
    my_listening_port = my_port

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listening_socket:
        # On Linux and Mac, a port stays reserved for a short time after a
        # program using it closes. Without this setting, starting the program
        # again right away fails with "Address already in use". We skip this
        # on Windows, where the same setting would let two programs share
        # one port.
        if sys.platform != "win32":
            listening_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        # Start using our port. This fails if another program already uses it.
        try:
            listening_socket.bind(("", my_port))   # "" means accept connections from any network
            listening_socket.listen(10)            # allow up to 10 peers to wait their turn
        except OSError as error:
            print(f"Could not listen on port {my_port}: {error}")
            return 1

        # Wait for new peers in the background, so the main part of the
        # program is free to read what you type. daemon=True makes this
        # thread stop automatically when the program ends.
        threading.Thread(target=listen_for_connections, args=(listening_socket,), daemon=True).start()
        print(f"Listening on port {my_port}. Type 'help' for commands or 'exit' to quit.")

        try:
            # The command loop. Each line you type is split into at most 3
            # parts, so the spaces inside a message are kept:
            #     "send 1 hello there"  ->  ["send", "1", "hello there"]
            while True:
                parts = input("Enter a command: ").strip().split(maxsplit=2)
                if not parts:
                    continue  # you pressed Enter on an empty line, so ask again
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
            pass  # Ctrl+C or Ctrl+D also quits the program cleanly
        finally:
            # No matter how we leave the loop, close every connection. The
            # other peers will see that we left and remove us from their lists.
            with connections_lock:
                peers = list(connections)
            for peer in peers:
                close_connection(peer)
    print("Goodbye.")
    return 0

if __name__ == "__main__":
    sys.exit(main())