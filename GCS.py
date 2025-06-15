import socket
import cv2
import numpy as np
import threading
import pickle
from typing import Dict
import Map
import math


def compute_tello_global(init_yaw, drone_loc, tello_loc, x_base):
    drone_lat, drone_lon, drone_yaw_deg, _, _ = drone_loc
    name, dx_cm, dy_cm, dyaw_deg, rel_h = tello_loc
    x = dx_cm / 100.0 + x_base 
    y = dy_cm / 100.0
    psi = math.radians(drone_yaw_deg)
    dN =  math.cos(psi) * x - math.sin(psi) * y
    dE =  math.sin(psi) * x + math.cos(psi) * y
    dlat = dN / 111320.0
    dlon = dE / (111320.0 * math.cos(math.radians(drone_lat)))
    lat = drone_lat + dlat
    lon = drone_lon + dlon
    yaw = init_yaw + dyaw_deg
    if rel_h == 0:
        rel_h = 6
    return [name, lat, lon, yaw, rel_h]


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
        
def recv_message(client_socket, server_socket, address, map):
    a = True
    init_yaw = -777
    offset =[-5, 5]
    while True:
        try:
            data_byte = client_socket.recv(1024)
            data : Dict = pickle.loads(data_byte)
            if data['message'] == 'l':
                if data['data']['drone_location'][0] == 0:
                    if a:
                        print('connect')
                        a = False
                else:
                    if init_yaw == -777:
                        init_yaw = data['data']['drone_location'][2]
                    drone = data['data']['drone_location']
                    tello1 = data['data']['tello_location'][0:5]
                    tello2 = data['data']['tello_location'][5:]
                    tello1_g = compute_tello_global(init_yaw, drone, tello1, offset[0])
                    tello2_g = compute_tello_global(init_yaw, drone, tello2, offset[1])
                    tellos = tello1_g + tello2_g
                    drone.pop(3)
                    if data['data']['detection'] == '':
                        frame = map.update_map(drone, tellos)
                    else:
                        'compute code'
                        loc =[10,10]
                        frame = map.update_map(drone, tellos, loc)
                    cv2.imshow("Map", frame)
                    key=cv2.waitKey(1) & 0xFF
                    if key==ord('q'):
                        server_socket.close()
            else:
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
        
if __name__ == "__main__":
    map = Map.MAP(zoom=18)
    server_ip = socket.gethostbyname(socket.gethostname())
    print(f'server_ip: {server_ip}')
    server_port = 5270
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind((server_ip, server_port))
    server_socket.listen(10)
    while True:
        print('Waiting')
        try:
            client_socket, address = server_socket.accept()
            send_thread = threading.Thread(target=send_message, args=(client_socket, address))
            send_thread.daemon=True
            send_thread.start()
            recv_thread = threading.Thread(target=recv_message, args=(client_socket, server_socket, address, map))
            recv_thread.daemon=True
            recv_thread.start()
        except Exception as e:
            print(e)
            print(type(e))
            break
        