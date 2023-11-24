import time
from enum import Enum
from djitellopy import Tello
import keyboard

tello = Tello()
tello.connect()
tello.get_battery()

# current_Mission = Enum('Mission', ['0', '1', '2', '3'])
current_Mission = '1'
do_once = True
mission_state = 0
x = 1

tello.enable_mission_pads()
tello.set_mission_pad_detection_direction(0)


def mission1():
    global mission_state, x
    global do_once

    if do_once:
        mission_state = 1
        x = 1
        do_once = False
        print("Mission 1 Started")

    if mission_state == 1:
        if keyboard.is_pressed("q"):
            print("m1s1")
            mission_state = 0

            tello.takeoff()
            pad = 5
            print(pad)
            c = 0

            while pad != 2:
                if pad == 6:
                    print(pad)
                    print("Pad 6 found")
                    break
                if keyboard.is_pressed("w"):
                    break
                if c < 8:
                    tello.move_forward(20)
                if c > 8:
                    break
                pad = tello.get_mission_pad_id()
                c += 1
                print(c)
                time.sleep(0.2)

            print(pad)
            tello.disable_mission_pads()
            tello.land()
            tello.end()


    if mission_state == 2:
        if keyboard.is_pressed("q"):
            print("m1s2")
            mission_state = 3
            tello.takeoff()
            tello.move_left(20)
            tello.land()

    if mission_state == 3:
        if keyboard.is_pressed("q"):
            print("m1s3")
            mission_state = 0
            tello.takeoff()
            tello.move_right(20)
            tello.move_back(20)
            tello.rotate_clockwise(360)
            tello.land()


while current_Mission == '1':
    mission1()
