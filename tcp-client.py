import socket

s = socket.socket()
port = 1234
s.connect(('127.0.0.1', port))

# print 'help' message
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

# function to get the IP address of this process
def get_my_ip():
    # create a temporary socket to determine the local IP address
    temp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    # connect to a public DNS server to get the local IP address
    try:
        # connect to a public DNS server (Google's DNS)
        temp_socket.connect(("8.8.8.8", 80))
        # get the local IP address from the socket's own address
        ip = temp_socket.getsockname()[0]
    finally:
        # close the temporary socket
        temp_socket.close()
    return ip

# main loop to send messages to the server
while True:
    message = input("Enter a command (e.g., 'help' for options): ")

    # handle the 'help' command locally
    if message.strip() == "help":
        print_help()
        continue  

    # handle the 'myip' command locally
    if message.strip() == "myip":
        print("My IP address is:", get_my_ip())
        continue  

    # handle the 'myport' command locally
    if message.strip() == "myport":
        print("My port is:", port)
        continue  

    # handle the 'exit' command to break the loop and close the socket
    if message == "exit":
        break

    # send the message to the server and receive a response
    s.send(message.encode())
    data = s.recv(1024)
    print(data.decode())

s.close()