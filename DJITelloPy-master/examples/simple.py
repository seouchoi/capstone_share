from djitellopy import Tello
import time

tello = Tello()

tello.connect()
tello.takeoff()

time.sleep(2)
tello.rotate_clockwise(90)
time.sleep(2)

tello.land()
