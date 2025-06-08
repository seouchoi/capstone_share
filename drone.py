import asyncio
import math
import time
import threading
from typing import Dict, List
from mavsdk import System
from mavsdk.offboard import OffboardError, VelocityBodyYawspeed
from mavsdk.gimbal import GimbalMode, ControlMode
from typing import Any, Dict, Optional, Union


class DroneObject:
    def __init__(self, drone_locaion_Array, main_to_gcs_pipe, mission_callback) -> None:
        self.end = False
        self.drone_locaion_Array = drone_locaion_Array
        self.main_to_gcs_pipe = main_to_gcs_pipe
        self.mission_callback = mission_callback
        self.drone :Optional[System] = None
        self.state : Dict = dict(
            speed=0.0,
            location_latitude=37.5665,
            location_longitude=126.9780,
            altitude=0.0,
            battery=0.0,
            yaw=0.0,
            pitch=0.0,
            roll=0.0,
        )
        
    
    async def connect_drone(self) -> None:
        print("Connecting to drone...")
        self.drone = System()
        await self.drone.connect(system_address="serial:///dev/ttyACM0")
        async for state in self.drone.core.connection_state():
            print(f"Connection state: {state.is_connected}")
            if state.is_connected:
                print("Drone connected successfully.")
                break
            await asyncio.sleep(1)
    
    
    async def update_drone_state(self) -> None:
        print('update_drone_state started')
        while True:
            try:
                if self.end:
                    return
                async for pos in self.drone.telemetry.position():
                    self.state['location_latitude'] = round(pos.latitude_deg, 6)
                    self.state['location_longitude'] = round(pos.longitude_deg, 6)
                    break
                async for att in self.drone.telemetry.attitude_euler():
                    self.state['yaw'] = round(att.yaw_deg ,2)
                    break
                async for vel in self.drone.telemetry.velocity_ned():
                    self.state['speed'] = round(math.sqrt(vel.north_m_s**2 + vel.east_m_s**2 + vel.down_m_s**2 ))
                    break
                with self.drone_locaion_Array.get_lock():
                    self.drone_locaion_Array[0] = self.state['location_latitude']
                    self.drone_locaion_Array[1] = self.state['location_longitude']
                    self.drone_locaion_Array[2] = self.state['yaw']
                    self.drone_locaion_Array[3] = self.state['speed']

                '''
                if self.end:
                    return
                async for pos in self.drone.telemetry.position():
                    self.state['location_latitude'] = round(pos.latitude_deg, 6)
                    self.state['location_longitude'] = round(pos.longitude_deg, 6)
                    self.state['altitude'] = round(pos.relative_altitude_m, 2)
                    break
                async for bat in self.drone.telemetry.battery():
                    self.state['battery'] = round(bat.remaining_percent * 100,2)
                    break
                async for att in self.drone.telemetry.attitude_euler():
                    self.state['yaw'] = round(att.yaw_deg ,2)
                    self.state['pitch'] = round(att.pitch_deg ,2)
                    self.state['roll'] = round(att.roll_deg ,2)
                    break
                async for vel in self.drone.telemetry.velocity_ned():
                    self.state['speed'] = round(math.sqrt(vel.north_m_s**2 + vel.east_m_s**2 + vel.down_m_s**2 ))
                    break
                '''
            except Exception as e:
                print(f'update_drone_state : {str(e)}')
                self.state['msg'] = str(e)
            await asyncio.sleep(0.1)
            
    
    async def drone_action(self) -> None:
        while True:
            try:
                if self.end:
                    return
                command = self.main_to_gcs_pipe.recv()
                if command == 'start':
                    self.mission_callback('takeoff')
                    await asyncio.sleep(3)
                    self.mission_callback('up')
                    await asyncio.sleep(10)
                    await drone.action.takeoff()
                    await asyncio.sleep(5)
                    await drone.offboard.set_velocity_body(VelocityBodyYawspeed(0.0, 0.0, 0.0, 0.0))
                    await drone.offboard.start()
                    await drone.offboard.set_velocity_body(VelocityBodyYawspeed(0.35, 0.0, 0.0, 0.0))
                    await asyncio.sleep(0.5)
                    self.mission_callback('ready')
                    await asyncio.sleep(29.5)
                    await drone.offboard.set_velocity_body(VelocityBodyYawspeed(0.0, 0.0, 0.0, 0.0))
                    await drone.offboard.stop()
                    await drone.action.land()
                    await asyncio.sleep(5)
                    await drone.action.disarm()
                    
                if command == 'end':
                    self.mission_callback('land')
                    await self.drone.action.land()
                    await asyncio.sleep(5)
                    await drone.action.disarm()
                    exit(1)
                
            except Exception as e:
                print(f'drone_action : {str(e)}')
    
    async def command_main(self) -> None:
        self.drone = System()
        await self.connect_drone()
        state_task  = asyncio.create_task(self.update_drone_state())
        action_task = asyncio.create_task(self.drone_action())
        await asyncio.wait(
            [state_task, action_task],
            return_when=asyncio.FIRST_COMPLETED
        )
