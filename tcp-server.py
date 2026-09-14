import socket  # for socket programming 
import threading  # for each connection thread


def handle_connection(connection_socket, address):
	"""
	actions for each connection
	"""
	while True:
		# receive data in bytes
		data = connection_socket.recv(1024)

		# decode the received data to string and print out
		message = data.decode()
		print("Got message from", address, ":", message)

		# convert it to uppercase and send back
		connection_socket.send(message.upper().encode())

		# stop checking messages and break
		if message == "close":
			break
			
	connection_socket.close()


def main():
	# create a listening socket
	s = socket.socket()

	# bind it to a port
	port = 1234
	s.bind(("", port))  # input is a tuple with address and port as elements

	# keep listening
	s.listen(10)
	while True:
		# accept connection request
		connection_socket, address = s.accept()
		print("Got connection from", address)

		# create a thread to handle the accepted client
		thread = threading.Thread(target=handle_connection, args=(connection_socket, address), daemon=True)
		thread.start()  # start the thread

main()


