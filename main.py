import sys
import traceback
import av
import cv2
import numpy
import time
import av
import keyboard
import threading
import numpy as np
import socket
from queue import Queue
from kivy.app import App
from kivy.core.window import Window
from joystick import Joystick
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.behaviors import CoverBehavior
from kivy.uix.video import Video
from kivy.core.video import VideoBase
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.button import Button
from kivy.clock import Clock
from kivy.lang import Builder
from threading import Thread
from colorama import Fore, Back, Style
from djitellopy import tello
from ffpyplayer.player import MediaPlayer
from kivy.properties import ObjectProperty

IS_STREAM_ON = False
color_state = 'Blue'


# Builder.load_file('kivytello.kv')

def send_socket_command(command):
    clientsocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    clientsocket.connect(('localhost', 8089))
    clientsocket.send(command.encode())


class VideoStreamThread(Thread):
    def __init__(self, drone):
        super(VideoStreamThread, self).__init__()
        self.drone = drone
        self.stopped = False
        #  print("XXXXXXXX")

    def run(self):
        try:
            while not self.stopped:
                img = self.drone.get_frame_read().frame
                img = cv2.resize(img, (1920, 1080), interpolation=cv2.INTER_LINEAR)
                img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                img = cv2.addWeighted(img, 1.5, np.zeros_like(img), 0, 0)
                cv2.imshow("VideoFrame", img)
                key = cv2.waitKey(1) & 0xFF
                if key == ord('q'):
                    break
        except Exception as e:
            print("Failed to create video stream")
        finally:
            cv2.destroyAllWindows()
            self.drone.streamoff()
            self.drone.end()


class DroneThread(Thread):
    def __init__(self, drone):
        super(DroneThread, self).__init__()
        self.drone = drone
        self.command_queue = Queue()
        self.result_dict = {}
        self.hover = False
        self.start()

    def run(self):
        while True:
            command, args = self.command_queue.get()
            if command == 'end':
                break
            self.result_dict[command] = getattr(self.drone, command)(*args)
        self.drone.end()

    def add_command(self, command, *args):
        self.command_queue.put((command, args))
        while command not in self.result_dict:
            time.sleep(0.01)  # Wait for the command to be executed
        result = self.result_dict.pop(command)
        return result

    def hover_movement(self):
        while self.drone.is_flying and self.hover:
            self.add_command('move_down', 20)
            time.sleep(10)
            if self.drone.is_flying and self.hover:
                self.add_command('move_down', 20)
                time.sleep(10)


class KivyTelloRoot(FloatLayout):
    def __init__(self, drone=None, drone_thread=None, **kwargs):
        super(KivyTelloRoot, self).__init__(**kwargs)
        self.drone = drone
        self.drone_thread = drone_thread
        self.sm = ScreenManager()
        self.sm.add_widget(MainScreen())
        # self.sm.add_widget(MissionScreen(drone=self.drone))
        self.add_widget(self.sm)

    def stop(self):
        self.drone_thread.add_command("end")
        App.get_running_app().stop()


class KivyTelloApp(App):
    def __init__(self, drone=None, drone_thread=None, **kwargs):
        global IS_STREAM_ON
        super(KivyTelloApp, self).__init__(**kwargs)
        self.sm = None
        self.main_screen = None
        self.mission_screen = None
        self.drone = drone
        self.drone_thread = drone_thread
        if not IS_STREAM_ON:
            self.drone_thread.add_command("streamon")
            IS_STREAM_ON = True

    def build_config(self, config):
        return KivyTelloRoot(drone=self.drone, drone_thread=self.drone_thread)

    def build(self):
        self.sm = ScreenManager()
        self.main_screen = MainScreen()
        self.mission_screen = MissionScreen(drone=self.drone, drone_thread=self.drone_thread)

        # Add screens to the ScreenManager
        self.sm.add_widget(self.main_screen)
        self.sm.add_widget(self.mission_screen)

        return self.sm

    def on_pause(self):
        return True

    def on_stop(self):
        Window.close()


class MissionButton(Button):  # MissionButton styling is defined in the.kv file
    pass


class GreenButton(Button):
    pass


class YellowButton(Button):
    pass


class BlueButton(Button):
    pass


class RedButton(Button):
    pass


class MainScreen(Screen):
    def __init__(self, **kwargs):
        super(MainScreen, self).__init__(**kwargs)
        self.name = 'main'
        self.drone = drone

    def start_mission(self, instance):
        self.manager.current = 'mission'


class MissionScreen(Screen):
    drone_thread = ObjectProperty(None)

    # is_initialized = False

    def __init__(self, drone=None, **kwargs):
        '''if MissionScreen.is_initialized:
            return'''
        super(MissionScreen, self).__init__(**kwargs)
        self.land_button = None
        self.go_2_batman_button = None
        self.yellow_button = None
        self.success_dragon_killed_button = None
        self.spawn_dragon_button = None
        self.takeoff_button = None
        self.mission_number = None
        self.name = 'mission'
        # self.add_widget(Button(text='Return', on_release=self.stop_mission))
        # self.stick_data = [0.0] * 4
        self.drone = drone
        self.drone_thread.add_command("enable_mission_pads")
        self.drone_thread.add_command("set_mission_pad_detection_direction", 0)
        self.drone.set_mission_pad_detection_direction(0)
        self.blue_button = None
        self.green_button = None
        self.red_button = None
        self.drone_finished = False
        self.go_removed = False

    def stop_mission(self, instance):
        self.manager.current = 'main'

    def stop(self):
        self.drone_thread.add_command("end")
        App.get_running_app().stop()

    def start_mission(self, mission_number):
        self.mission_number = mission_number
        self.setup_mission()

    def setup_mission(self):
        if self.mission_number == 1:
            self.setup_mission1()
        elif self.mission_number == 2:
            self.setup_mission2()

    def setup_mission1(self):
        print("Mission 1 triggered good")
        self.takeoff_button_func('Takeoff')

    def setup_mission2(self, dt=None):
        print("Mission 2 triggered good")
        #  send_socket_command("Go!")
        self.takeoff_button_func('Go!')  # 1

    def takeoff_button_func(self, text):
        button_takeoff = MissionButton(text=text)
        button_takeoff.bind(on_press=self.on_button_press)

        self.takeoff_button = button_takeoff

        keyboard.add_hotkey('a', self.on_button_press, args=(button_takeoff,))

        Clock.schedule_once(lambda dt: self.ids.button_layer.add_widget(button_takeoff), 3)

    def spawn_dragon_button_func(self):  # 2
        button_dragon = MissionButton(text='Dragon')
        button_dragon.bind(on_press=self.on_button_press)

        self.spawn_dragon_button = button_dragon

        keyboard.add_hotkey('s', self.on_button_press, args=(button_dragon,))

        Clock.schedule_once(lambda dt: self.ids.button_layer.add_widget(button_dragon), 3)

    def spawn_blue_button(self):
        button_blue = BlueButton(text='Blue')
        button_blue.bind(on_press=self.on_button_press)
        self.blue_button = button_blue

        keyboard.add_hotkey('d', self.on_button_press, args=(button_blue,))

        self.ids.button_layer.add_widget(button_blue)

    def spawn_yellow_button(self):
        button_yellow = YellowButton(text='Yellow')
        button_yellow.bind(on_press=self.on_button_press)
        self.yellow_button = button_yellow

        keyboard.add_hotkey('f', self.on_button_press, args=(button_yellow,))

        self.ids.button_layer.add_widget(button_yellow)

    def spawn_green_button(self):
        button_green = GreenButton(text='Green')
        button_green.bind(on_press=self.on_button_press)
        self.green_button = button_green

        keyboard.add_hotkey('g', self.on_button_press, args=(button_green,))

        self.ids.button_layer.add_widget(button_green)

    def spawn_red_button(self):
        button_red = RedButton(text='Red')
        button_red.bind(on_press=self.on_button_press)
        self.red_button = button_red

        keyboard.add_hotkey('h', self.on_button_press, args=(button_red,))

        self.ids.button_layer.add_widget(button_red)

    def dragon_fight_video(self):
        print('Starting video playback')
        video_player = VideoPlayer(source='path_to_your_video_file.mp4', state='play', options={'allow_stretch': True})
        self.add_widget(video_player)
        Clock.schedule_once(lambda dt: self.stop_video(video_player), 5)

    def success_dragon_killed_button(self):
        print('Dragon killed, landing..')
        success_button = MissionButton(text='Dragon defeated!')
        success_button.bind(on_press=self.on_button_press)

        self.success_dragon_killed_button = success_button

        keyboard.add_hotkey('j', self.on_button_press, args=(success_button,))

        Clock.schedule_once(lambda dt: self.ids.button_layer.add_widget(success_button), 2)

    def go_2_batman_button(self):
        print('start Go to Batman')
        batman_button = MissionButton(text='Rescue Batman!')
        batman_button.bind(on_press=self.on_button_press)

        self.go_2_batman_button = batman_button

        keyboard.add_hotkey('k', self.on_button_press, args=(success_button,))

        self.ids.button_layer.add_widget(batman_button)

    def land_button(self):
        print('land button pressed')
        land_button = MissionButton(text='LAND')
        land_button.bind(on_press=self.on_button_press)

        self.land_button = land_button

        keyboard.add_hotkey('l', self.on_button_press, args=(success_button,))

        self.ids.button_layer.add_widget(land_button)

    def on_button_press(self, button_instance):
        print(f'Button "{button_instance.text}" pressed good')

        global color_state

        if button_instance.text == 'Launch Drone':
            # Add logic for Mission 1 button
            print('Mission 1 Button pressed')
            print('Taking off.. command sent')
            # Tell drone to take off
            # Clock.schedule_once(lambda dt: self.drone.takeoff(), 2)

            Clock.schedule_once(lambda dt: self.start_overlayvideo(), 6)

        elif button_instance.text == 'Mission 2 Button':
            # Add logic for Mission 2 button
            print('Mission 2 Button pressed')

        elif button_instance.text == 'Go!':

            Clock.schedule_once(lambda dt: self.ids.button_layer.remove_widget(button_instance), 0)

            print('removed button ', button_instance.text)

            self.drone_thread.add_command("takeoff")
            #  self.drone.move_down(20)  # go 20 cm down

            drone_thread.hover = False

            Clock.schedule_once(lambda dt: self.spawn_dragon_button_func(), 0)
            # MissionScreen.spawn_dragon_button(self)

        elif button_instance.text == 'Dragon':
            Clock.schedule_once(lambda dt: self.ids.button_layer.remove_widget(button_instance), 0)
            print('removed button ', button_instance.text)

            drone_thread.hover = False

            send_socket_command("dragon")  # Activates health bar of dragon

            self.drone_moving(2)

            while not self.drone_finished:
                pass
            self.drone_finished = False

            Clock.schedule_once(lambda dt: self.spawn_blue_button(), 5)

        elif button_instance.text == 'Blue':
            # Add logic for Mission 2 button
            print('Blue Button pressed')
            if color_state == 'Blue':
                print(Back.BLUE + 'Blue True')

                send_socket_command("blue")  # Scores on hit

                color_state = 'Yellow'
                print(color_state)

                Clock.schedule_once(lambda dt: self.ids.button_layer.remove_widget(button_instance), 0)
                Clock.schedule_once(lambda dt: self.spawn_yellow_button(), 5)

        elif button_instance.text == 'Yellow':
            # Add logic for Mission 2 button
            print('Yellow Button pressed')
            if color_state == 'Yellow':
                print(Back.YELLOW + 'Yellow True')

                send_socket_command("yellow")  # Scores one hit

                color_state = 'Green'
                print(color_state)

                Clock.schedule_once(lambda dt: self.ids.button_layer.remove_widget(button_instance), 0)
                Clock.schedule_once(lambda dt: self.spawn_green_button(), 5)

        elif button_instance.text == 'Green':
            # Add logic for Mission 2 button
            print('Green Button pressed')
            if color_state == 'Green':
                print(Back.GREEN + 'Green True')

                send_socket_command("green")

                color_state = 'Red'

                Clock.schedule_once(lambda dt: self.ids.button_layer.remove_widget(button_instance), 0)
                Clock.schedule_once(lambda dt: self.spawn_red_button(), 5)

        elif button_instance.text == 'Red':
            # Add logic for Mission 2 button
            print('Red Button pressed')
            if color_state == 'Red':
                print(Back.RED + 'Red True')

                send_socket_command("red")

                drone_thread.hover = False

                #  color_state = 'Blue'

                #  print(color_state)

                Clock.schedule_once(lambda dt: self.ids.button_layer.remove_widget(button_instance), 0)
                Clock.schedule_once(lambda dt: self.success_dragon_killed_button(), 3)

        elif button_instance.text == 'Dragon defeated!':
            print(button_instance.text, ' button pressed')
            Clock.schedule_once(lambda dt: self.ids.button_layer.remove_widget(button_instance), 0)
            print('removed button ', button_instance.text)
            self.drone_thread.add_command("land")

            Clock.schedule_once(lambda dt: self.go_2_batman_button(), 3)

        elif button_instance.text == 'Rescue Batman!':
            print(button_instance.text, ' button pressed')
            Clock.schedule_once(lambda dt: self.ids.button_layer.remove_widget(button_instance), 0)
            print('removed button ', button_instance.text)

            self.drone_thread.add_command("takeoff")

            self.drone_moving(3)

            while not self.drone_finished:
                pass
            self.drone_finished = False

            drone_thread.hover = True

            Clock.schedule_once(lambda dt: self.land_button(), 3)

        elif button_instance.text == 'LAND':
            self.drone_thread.add_command("land")
            print(button_instance.text, ' button pressed')
            Clock.schedule_once(lambda dt: self.ids.button_layer.remove_widget(button_instance), 0)
            print('removed button ', button_instance.text)

            Clock.schedule_once(lambda dt: self.finish_mission(), 60)

    def drone_moving(self, pad_end):

        pad = 1
        print('Current pad = ', pad)
        c = 0

        while True:
            if pad == pad_end:
                print("Pad 2 found")
                break
            if keyboard.is_pressed("w"):
                break
            if c < 3:
                self.drone_thread.add_command("move_forward", 20)
            else:
                break

            #  pad = self.drone.get_mission_pad_id()
            pad = self.drone_thread.add_command("get_mission_pad_id")
            print('current pad: ', pad)
            time.sleep(1)  # Can be adjusted lower

            c += 1  # increments count
            print('current iteration (c) = ', c)  # prints current count state

        #  Once While loop breaks/is done
        # self.drone.move_forward(20)  # Move directly over Mission pad
        #  self.drone_thread.add_command("land")
        self.drone_finished = True

    def finish_mission(self, dt=None):
        # Perform any cleanup or finalization for the mission
        self.manager.current = 'main'


if __name__ in ('__main__', '__android__'):
    drone = tello.Tello()
    drone_thread = DroneThread(drone)

    video_thread = VideoStreamThread(drone)
    video_thread.start()

    hover_thread = Thread(target=drone_thread.hover_movement)
    hover_thread.start()

    try:
        drone.connect()
        # drone.wait_for_connection(60.0)
        # flask_app = FlaskApp(drone=drone)
        # t = Thread(target=start_flask_app, args=(flask_app,))
        # t.daemon = True
        # t.start()
        KivyTelloApp(drone=drone, drone_thread=drone_thread).run()
    except Exception as ex:
        print(traceback.format_exc())
        # drone.streamoff()
        drone.end()
        Window.close()
