import socket       # for TCP/UDP network communication
import threading     # lets us run the listener and the input loop at the same time
import sys           # lets us read command-line arguments (like the port number)


def handle_connection(connection_socket, address):
    """
    Runs in its own thread for EACH connected peer.
    Keeps listening for messages from that one peer until they disconnect.
    """
    while True:
        # wait here until data arrives (or the peer disconnects)
        data = connection_socket.recv(1024)

        # recv() returns empty bytes (b'') when the other side has closed
        # the connection -- this is how we detect a disconnect, NOT by
        # looking for a special word like "exit" or "close"
        if not data:
            print("Connection closed by", address)
            break

        # convert the received bytes into a readable string
        message = data.decode()
        print("\nGot message from", address, ":", message)

        # send a reply back (just uppercasing it for now, like before)
        connection_socket.send(message.upper().encode())

    # once the loop ends (peer disconnected), clean up this socket
    connection_socket.close()


def listen_for_connections(my_port):
    """
    Runs in a background thread for the ENTIRE lifetime of the program.
    Sits and waits for new incoming connections, and spins up a new
    handle_connection thread for each one that connects.
    This is basically your old server.py's main(), just renamed.
    """
    listening_socket = socket.socket()

    # lets you restart the program quickly without "port already in use"
    # errors (useful while testing/restarting often)
    listening_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    # "" means "listen on all available network interfaces"
    listening_socket.bind(("", my_port))

    # 10 = how many pending connections can queue up before being accepted
    listening_socket.listen(10)

    while True:
        # blocks here until someone connects to us
        connection_socket, address = listening_socket.accept()
        print("\nGot connection from", address)

        # hand this specific peer off to its own thread, so we can go
        # right back to accept()-ing the NEXT incoming connection
        # without waiting on this one
        t = threading.Thread(
            target=handle_connection,
            args=(connection_socket, address),
            daemon=True  # dies automatically when the main program exits
        )
        t.start()

def print_help():
    print("""
Available commands:
  help                          - Show this help message
  myip                          - Display this process's IP address
  myport                        - Display the port this process is listening on
  connect <destination> <port>  - Connect to a peer at the given IP and port
  list                          - List all current connections
  terminate <connection id>     - Terminate the specified connection
  send <connection id> <msg>    - Send a message to the specified connection
  exit                          - Close all connections and terminate
""")

def get_my_ip():
    # Open a throwaway UDP socket and "connect" to an external address.
    # No data is actually sent -- this just asks the OS which real
    # network interface it would use, so we get the actual local IP
    # instead of 127.0.0.1.
    temp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        temp_socket.connect(("8.8.8.8", 80))
        ip = temp_socket.getsockname()[0]
    finally:
        temp_socket.close()
    return ip

def main():
    # sys.argv is the list of words typed on the command line.
    # sys.argv[0] is always the script name itself (e.g. "chat.py"),
    # so sys.argv[1] is the FIRST actual argument -- our port number.
    # Example: running `python3 chat.py 4545` means sys.argv == ["chat.py", "4545"]
    if len(sys.argv) != 2:
        print("Usage: python3 chat.py <port>")
        sys.exit(1)  # stop the program immediately with an error status

    # command-line arguments always arrive as strings, so convert to int
    my_port = int(sys.argv[1])

    # start the listening loop in the BACKGROUND, so it runs at the same
    # time as the input loop below, instead of blocking everything else.
    # Without this thread, the program would get stuck inside
    # listen_for_connections() forever and never reach the input loop.
    listener_thread = threading.Thread(
        target=listen_for_connections,
        args=(my_port,),
        daemon=True
    )
    listener_thread.start()

    print(f"Listening on port {my_port}. Type 'exit' to quit.")

    while True:
        message = input("Enter a command (e.g., 'help' for options):")

        if message.strip() == "help":
            print_help()
            continue

        if message.strip() == "myip":
            print("My IP address:", get_my_ip())
            continue

        if message.strip() == "myport":
            # now this is CORRECT -- my_port is the real port
            # THIS process is listening on
            print("My listening port:", my_port)
            continue

        if message.strip() == "exit":
            break

        print("(connect/list/terminate/send not implemented yet)")

    print("Goodbye.")

main()