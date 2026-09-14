import socket  # for socket programming

# create a socket
s = socket.socket()

# connect to the server using the known listening port
port = 1234
s.connect(('127.0.0.1', port))

# keep getting user input
while True:
	message = input(">")

	# encode the message to bytes and send using the socket
	s.send(message.encode())

	# print replies from server
	data = s.recv(1024)
	print(data.decode())
	
	if message == "close":
		break

s.close()
	
