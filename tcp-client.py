import socket

s = socket.socket()
port = 1234
s.connect(('127.0.0.1', port))

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

while True:
    message = input("Enter a command (e.g., 'help' for options):")

    if message.strip() == "help":
        print_help()
        continue  # don't send this to the server, just handle it locally

    if message == "exit":
        break

    s.send(message.encode())
    data = s.recv(1024)
    print(data.decode())

s.close()