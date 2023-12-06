import sys
import traceback
import av
import cv2
import numpy
import time
import av
import keyboard
import threading
import queue
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
from flask import Response, request
from perfume import route, Perfume
from colorama import Fore, Back, Style
from djitellopy import tello
from ffpyplayer.player import MediaPlayer

IS_STREAM_ON = False
color_state = 'Blue'
# Builder.load_file('kivytello.kv')


class FlaskApp(Perfume):
    def __init__(self, drone=None, **kwargs):
        super(FlaskApp, self).__init__(**kwargs)
        self.drone = drone

    @route('/video_feed')
    def video_feed(self):
        print("Received video feed request from:", request.remote_addr)

        def generate():
            frame_counter = 0
            n = 2 #  defines numbers of frames to skip
            try:
                while True:
                    img = self.drone.get_frame_read().frame
                    img = cv2.resize(img, (360, 240))
                    _, jpeg = cv2.imencode('.jpg', img)

                    if frame_counter % n == 0:  # Only yield every nth frame
                        yield (b'--frame\r\n'
                               b'Content-Type: image/jpeg\r\n\r\n' +
                               jpeg.tobytes() +
                               b'\r\n\r\n')
                    frame_counter += 1

            except Exception as ex:
                exc_type, exc_value, exc_traceback = sys.exc_info()
                traceback.print_exception(exc_type, exc_value, exc_traceback)
                print(ex)

            finally:
                self.drone.end()
                App.get_running_app().stop()

        return Response(generate(),
                        mimetype='multipart/x-mixed-replace; boundary=frame')


def start_flask_app(flask_app=None):
    print("Starting Flask app...")
    flask_app.run(port=30660, debug=True,
                  use_reloader=False, threaded=True)


class CoverVideo(CoverBehavior, Video):
    def _on_video_frame(self, *largs):
        video = self._video
        if not video:
            return
        texture = video.texture
        self.reference_size = texture.size
        self.calculate_cover()
        self.duration = video.duration
        self.position = video.position
        self.texture = texture
        self.canvas.ask_update()


'''
class DragableJoystick(Joystick):
    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            self.pos = touch.x - self.width / 2, touch.y - self.height / 2
            return super(DragableJoystick, self).on_touch_down(touch)
            '''


class KivyTelloRoot(FloatLayout):
    def __init__(self, drone=None, flask_app=None, **kwargs):
        super(KivyTelloRoot, self).__init__(**kwargs)
        self.drone = drone
        self.flask_app = flask_app
        self.sm = ScreenManager()
        self.sm.add_widget(MainScreen())
        # self.sm.add_widget(MissionScreen(drone=self.drone))
        self.add_widget(self.sm)

    def stop(self):
        self.drone.end()
        App.get_running_app().stop()


class KivyTelloApp(App):
    def __init__(self, drone=None, flask_app=None, **kwargs):
        global IS_STREAM_ON
        super(KivyTelloApp, self).__init__(**kwargs)
        self.sm = None
        self.main_screen = None
        self.mission_screen = None
        self.drone = drone
        self.flask_app = flask_app
        if not IS_STREAM_ON:
            self.drone.streamon()
            IS_STREAM_ON = True

    def build_config(self, config):
        return KivyTelloRoot(drone=self.drone, flask_app=self.flask_app)

    def build(self):
        self.sm = ScreenManager()
        self.main_screen = MainScreen()
        self.mission_screen = MissionScreen(drone=self.drone)

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
    state = 0  # 0 = not started, 1 = drone in air, 2 = drone moving, 3 = hovering, 4 = landed
    # is_initialized = False

    def __init__(self, drone=None, **kwargs):
        '''if MissionScreen.is_initialized:
            return'''
        super(MissionScreen, self).__init__(**kwargs)
        self.mission_number = None
        self.name = 'mission'
        # self.add_widget(Button(text='Return', on_release=self.stop_mission))
        # self.stick_data = [0.0] * 4
        self.drone = drone
        self.drone.enable_mission_pads()
        self.drone.set_mission_pad_detection_direction(0)
        self.blue_button = None
        self.green_button = None
        self.red_button = None
        self.drone_finished = False

    def stop_mission(self, instance):
        self.manager.current = 'main'

    def stop(self):
        self.drone.end()
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
        self.takeoff_button('Takeoff')

    def setup_mission2(self, dt=None):
        print("Mission 2 triggered good")
        self.takeoff_button('Go!')  # 1

    def takeoff_button(self, text):
        button_takeoff = MissionButton(text=text)
        button_takeoff.bind(on_press=self.on_button_press)

        Clock.schedule_once(lambda dt: self.ids.button_layer.add_widget(button_takeoff), 3)

    def spawn_dragon_button(self):  # 2
        button_dragon = MissionButton(text='Dragon')
        button_dragon.bind(on_press=self.on_button_press)
        Clock.schedule_once(lambda dt: self.ids.button_layer.add_widget(button_dragon), 3)

    def spawn_three_color_buttons(self):
        button_blue = BlueButton(text='Blue')
        button_blue.bind(on_press=self.on_button_press)
        button_red = RedButton(text='Red')
        button_red.bind(on_press=self.on_button_press)
        button_green = GreenButton(text='Green')
        button_green.bind(on_press=self.on_button_press)

        self.blue_button = button_blue
        self.green_button = button_green
        self.red_button = button_red

        self.ids.button_layer.add_widget(button_blue)
        self.ids.button_layer.add_widget(button_red)
        self.ids.button_layer.add_widget(button_green)

    def dragon_fight_video(self):
        print('Starting video playback')
        video_player = VideoPlayer(source='path_to_your_video_file.mp4', state='play', options={'allow_stretch': True})
        self.add_widget(video_player)
        Clock.schedule_once(lambda dt: self.stop_video(video_player), 5)

    def success_dragon_killed_button(self):
        print('Dragon killed, landing..')
        success_button = MissionButton(text='Dragon defeated!')
        success_button.bind(on_press=self.on_button_press)

        Clock.schedule_once(lambda dt: self.ids.button_layer.add_widget(success_button), 2)

    def go_2_batman_button(self):
        print('start Go to Lloyd')
        batman_button = MissionButton(text='Rescue Batman!')
        batman_button.bind(on_press=self.on_button_press)

        self.ids.button_layer.add_widget(batman_button)

    def land_button(self):
        print('land button pressed')
        land_button = MissionButton(text='LAND')
        land_button.brind(on_press=self.on_button_press)

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
            self.ids.button_layer.remove_widget(button_instance)
            print('removed button ', button_instance.text)

            self.drone.takeoff()
            #  self.drone.move_down(20)  # go 20 cm down

            MissionScreen.state = 1  # 1 = Drone is in the air
            print(MissionScreen.state, 'Change State success')

            MissionScreen.spawn_dragon_button(self)

        elif button_instance.text == 'Dragon':
            self.ids.button_layer.remove_widget(button_instance)
            print('removed button ', button_instance.text)

            self.drone_moving(3)

            while not self.drone_finished:
                pass
            self.drone_finished = False

            Clock.schedule_once(lambda dt: self.spawn_three_color_buttons(), 2)

        elif button_instance.text == 'Blue':
            # Add logic for Mission 2 button
            print('Blue Button pressed')
            if color_state == 'Blue':
                print(Back.BLUE + 'Blue True')
                color_state = 'Red'
                print(color_state)
                # Send command to LED to turn RED
                # minus one health bar

        elif button_instance.text == 'Red':
            # Add logic for Mission 2 button
            print('Red Button pressed')
            if color_state == 'Red':
                print(Back.RED + 'Red True')
                color_state = 'Green'
                print(color_state)
                # Send command to LED to turn Green
                # minus one health bar

        elif button_instance.text == 'Green':
            # Add logic for Mission 2 button
            print('Green Button pressed')
            if color_state == 'Green':
                print(Back.GREEN + 'Green True')
                color_state = 'Blue'
                # minus last health bar
                # turn all LED's on

                self.remove_buttons()  # remove all color buttons
                Clock.schedule_once(lambda dt: self.success_dragon_killed_button(), 3)

        elif button_instance.text == 'Dragon defeated!':
            print(button_instance.text, ' button pressed')
            self.ids.button_layer.remove_widget(button_instance)
            print('removed button ', button_instance.text)
            self.drone.land()

            Clock.schedule_once(lambda dt: self.go_2_batman_button(), 3)

        elif button_instance.text == 'Rescue Batman!':
            print(button_instance.text, ' button pressed')
            self.ids.button_layer.remove_widget(button_instance)
            print('removed button ', button_instance.text)

            self.drone.takeoff()

            self.drone_moving(4)

            while not self.drone_finished:
                pass
            self.drone_finished = False

            lock.schedule_once(lambda dt: self.success_dragon_killed_button(), 3)

        elif button_instance.text == 'LAND':
            self.drone.land()
            print(button_instance.text, ' button pressed')
            self.ids.button_layer.remove_widget(button_instance)
            print('removed button ', button_instance.text)

            lock.schedule_once(lambda dt: self.finish_mission(), 60)

    def drone_moving(self, pad_end):

        pad = 1
        print('Current pad = ', pad)
        c = 0

        while True:
            if pad == pad_end:
                print("Pad 3 found")
                break
            if keyboard.is_pressed("w"):
                self.drone.land()
            if c < 8:
                self.drone.move_forward(20)

            if c > 8:
                self.drone.land()
            pad = self.drone.get_mission_pad_id()

            c += 1  # increments count
            print('current iteration (c) = ', c)  # prints current count state
            time.sleep(0.2)  # Can be adjusted lower

        #  Once While loop breaks/is done
        # self.drone.move_forward(20)  # Move directly over Mission pad
        self.drone_finished = True

    def remove_buttons(self):
        if self.blue_button in self.ids.button_layer.children:
            self.ids.button_layer.remove_widget(self.blue_button)
        if self.green_button in self.ids.button_layer.children:
            self.ids.button_layer.remove_widget(self.green_button)
        if self.red_button in self.ids.button_layer.children:
            self.ids.button_layer.remove_widget(self.red_button)

    def finish_mission(self, dt=None):
        # Perform any cleanup or finalization for the mission
        self.manager.current = 'main'


if __name__ in ('__main__', '__android__'):
    drone = tello.Tello()
    try:
        drone.connect()
        # drone.wait_for_connection(60.0)
        flask_app = FlaskApp(drone=drone)
        t = Thread(target=start_flask_app, args=(flask_app,))
        t.daemon = True
        t.start()
        KivyTelloApp(drone=drone, flask_app=flask_app).run()
    except Exception as ex:
        print(traceback.format_exc())
        # drone.streamoff()
        drone.end()
        Window.close()
