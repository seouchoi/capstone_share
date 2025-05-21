import socket
import cv2
import numpy as np
import threading
import pickle

def send_message(client_socket, address):
    while True:
        try:
            message=input()
            data =pickle.dumps(message)
            client_socket.sendall(data)
            
        except Exception as e:
            print(e)
            print(type(e))
            break
        
def close_wait(server_socket):
    image = np.ones((10, 10, 3), dtype=np.uint8) * 255
    cv2.imshow("", image)
    key=cv2.waitKey(0) & 0xFF
    if key==ord('q'):
        server_socket.close()
    
if __name__ == "__main__":
    server_ip = socket.gethostbyname(socket.gethostname())
    print(f'server_ip: {server_ip}')
    server_port = 5270
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind((server_ip, server_port))
    server_socket.listen(10)
    
    end_thread = threading.Thread(target=close_wait, args=(server_socket,))
    end_thread.daemon=True
    end_thread.start()
    
    while True:
        print('Waiting')
        try:
            client_socket, address = server_socket.accept()
            send_thread = threading.Thread(target=send_message, args=(client_socket, address))
            send_thread.daemon=True
            send_thread.start()
            
        except Exception as e:
            print(e)
            print(type(e))
            break
        
