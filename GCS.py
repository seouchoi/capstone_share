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
        
def recv_message(client_socket, address):
    while True:
        try:
            data_byte = client_socket.recv(1024)
            data : str = pickle.loads(data_byte)
            print(f'recv data : {data}')
        except pickle.UnpicklingError as e:
            # 'invalid load key, '\x00'' 에러일 때만 건너뛰기
            if "invalid load key" in str(e):
                print("invalid load key 조각 건너뛰기")
                continue
            # 다른 UnpicklingError는 루프 종료
            print("언피클 오류:", e)
            break
        except Exception as e:
            print(f'recv_message error : {e}')
            return
        
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
            recv_thread = threading.Thread(target=recv_message, args=(client_socket, address))
            recv_thread.daemon=True
            recv_thread.start()
        except Exception as e:
            print(e)
            print(type(e))
            break
        
