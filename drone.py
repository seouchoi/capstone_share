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
    def __init__(self) -> None:
        self.end = False
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
            except Exception as e:
                print(str(e))
                self.state['msg'] = str(e)
            await asyncio.sleep(0.1)