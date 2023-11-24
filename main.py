import sys
import traceback
import av
import cv2
import numpy
import time
import av
import keyboard
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
from djitellopy import Tello
from threading import Thread
from flask import Response, request
from perfume import route, Perfume


# IS_STREAM_ON = False


class FlaskApp(Perfume):
    def __init__(self, drone=None, **kwargs):
        super(FlaskApp, self).__init__(**kwargs)
        self.drone = drone

    @route('/video_feed')
    def video_feed(self):
        print("Received video feed request from:", request.remote_addr)

        def generate():
            try:
                self.drone.streamon()

                retry = 3
                cap = self.drone.get_video_capture()
                while cap is None and 0 < retry:
                    retry -= 1
                    print('retry...')
                    time.sleep(1)
                    cap = self.drone.get_video_capture()

                frame_skip = 300
                while True:
                    ret, frame = cap.read()
                    if not ret:
                        break

                    if 0 < frame_skip:
                        frame_skip -= 1
                        continue

                    start_time = time.time()
                    color = frame
                    # color = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                    ret, jpeg = cv2.imencode('.jpg', color)
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' +
                           jpeg.tobytes() +
                           b'\r\n\r\n')

                    if cap.get(cv2.CAP_PROP_FPS) < 1.0 / 60:
                        time_base = 1.0 / 60
                    else:
                        time_base = 1.0 / cap.get(cv2.CAP_PROP_FPS)

                    frame_skip = int((time.time() - start_time) / time_base)

            except Exception as ex:
                exc_type, exc_value, exc_traceback = sys.exc_info()
                traceback.print_exception(exc_type, exc_value, exc_traceback)
                print(ex)

            finally:
                # self.drone.streamoff()
                self.drone.end()
                App.get_running_app().stop()

        return Response(generate(),
                        mimetype='multipart/x-mixed-replace; boundary=frame')


def start_flask_app(flask_app=None):
    print("Starting Flask app...")
    flask_app.run(port=30660, debug=True,
                  use_reloader=False, threaded=True)


class CoverVideo(CoverBehavior, Video):
    def __init__(self, drone=None, **kwargs):
        super(CoverVideo, self).__init__(**kwargs)
        self.drone = drone

    def start_video(self):
        # start the video feed here
        self.source = 'http://127.0.0.1:30660/video_feed'
        print(f'self.source: {self.source}')
        self.options = {'eos': 'loop'}
        self.state = 'play'
        print("Video started")

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


class DragableJoystick(Joystick):
    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            self.pos = touch.x - self.width / 2, touch.y - self.height / 2
            return super(DragableJoystick, self).on_touch_down(touch)


class KivyTelloRoot(FloatLayout):
    def __init__(self, drone=None, flask_app=None, **kwargs):
        super(KivyTelloRoot, self).__init__(**kwargs)
        self.drone = drone
        self.flask_app = flask_app
        self.sm = ScreenManager()
        self.sm.add_widget(MainScreen())
        self.sm.add_widget(MissionScreen(drone=self.drone))
        self.add_widget(self.sm)

    def stop(self):
        self.drone.end()
        App.get_running_app().stop()


class KivyTelloApp(App):
    def __init__(self, drone=None, flask_app=None, **kwargs):
        super(KivyTelloApp, self).__init__(**kwargs)
        self.sm = None
        self.main_screen = None
        self.mission_screen = None
        self.drone = drone
        self.flask_app = flask_app
        Builder.load_file('kivytello.kv')

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


class MissionButton(Button):
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
    state = 0  # 0 = not started, 1 = started, 2 = finished

    def __init__(self, drone=None, **kwargs):
        super(MissionScreen, self).__init__(**kwargs)
        self.mission_number = None
        self.name = 'mission'
        # self.add_widget(Button(text='Return', on_release=self.stop_mission))
        self.stick_data = [0.0] * 4
        self.drone = drone
        self.drone.enable_mission_pads()
        self.drone.set_mission_pad_detection_direction(0)
        Clock.schedule_once(self._finish_init, 2)

    def _finish_init(self, dt):
        print("available ids in MissionScreen", self.ids)
        self.video = self.ids.video
        # self.video.start_video()
        # print("available ids in Pad_left", self.ids)
        # self.ids.pad_left.bind(pad=self.on_pad_left)
        # print("available ids in PadRight", self.ids)
        # self.ids.pad_right.bind(pad=self.on_pad_right)
        # self.ids.takeoff.bind(state=self.on_state_takeoff)
        self.ids.quit.bind(on_press=lambda x: self.stop())

    def on_enter(self, *args):
        self.video.start_video()

    def on_state_takeoff(self, instance, value):
        if value == 'down':
            print('take off')
            self.drone.takeoff()
        else:
            print('land')
            self.drone.land()

    '''def on_pad_left(self, instance, value):
        x, y = value
        self.stick_data[IDX_YAW] = x
        self.stick_data[IDX_THR] = y
        self.drone.set_throttle(self.stick_data[IDX_THR])
        self.drone.set_yaw(self.stick_data[IDX_YAW])'''

    '''def on_pad_right(self, instance, value):
        x, y = value
        self.stick_data[IDX_ROLL] = x
        self.stick_data[IDX_PITCH] = y
        self.drone.set_roll(self.stick_data[IDX_ROLL])
        self.drone.set_pitch(self.stick_data[IDX_PITCH])'''

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
        elif self.mission_number == 3:
            self.setup_mission3()
        elif self.mission_number == 4:
            self.setup_mission4()

    def setup_mission1(self):
        print("Mission 1 triggered good")

    def setup_mission2(self, dt=None):
        print("Mission 2 triggered good")

        button_takeoff = MissionButton(text='Go!')
        button_takeoff.bind(on_press=self.on_button_press)

        Clock.schedule_once(lambda dt: self.ids.button_layer.add_widget(button_takeoff), 3)

    def spawn_dragon_button(self):
        button_dragon = MissionButton(text='Dragon')
        button_dragon.bind(on_press=self.on_button_press)
        Clock.schedule_once(lambda dt: self.ids.button_layer.add_widget(button_dragon), 3)

    def spawnthreecolorbuttons(self):
        button_blue = BlueButton(text='Blue')
        button_blue.bind(on_press=self.on_button_press)
        button_red = RedButton
        button_red.bind(on_press=self.on_button_press)
        button_green = GreenButton
        button_green.bind(on_press=self.on_button_press)

        self.ids.button_layer.add_widget(button_blue)
        self.ids.button_layer.add_widget(button_red)
        self.ids.button_layer.add_widget(button_green)


    def dragonfightvideo(self):
        print('Starting video playback')
        video_player = VideoPlayer(source='path_to_your_video_file.mp4', state='play', options={'allow_stretch': True})
        self.add_widget(video_player)
        Clock.schedule_once(lambda dt: self.stop_video(video_player), 5)

    def setup_mission3(self, dt=None):
        print("Mission 3 triggered good")
        # Schedule the transition to the next set of buttons after 5 seconds
        Clock.schedule_once(self.setup_mission4, 5)

    def setup_mission4(self, dt=None):
        print("Mission 4 triggered good")
        # Schedule the transition to the next set of buttons after 5 seconds
        Clock.schedule_once(self.finish_mission, 5)

    def on_button_press(self, button_instance):
        print(f'Button "{button_instance.text}" pressed good')
        self.ids.button_layer.remove_widget(button_instance)
        print('removed button')

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
            self.drone.takeoff()
            MissionScreen.state = 1  # 1 = Drone is in the air
            print(MissionScreen.state)
            print('Change State sucess')
            MissionScreen.spawn_dragon_button(self)

        elif button_instance.text == 'Dragon':
            pad = 1
            print(pad)
            c = 0

            while True:
                if pad == 3:
                    print(pad)
                    print("Pad 3 found")
                    break
                if keyboard.is_pressed("w"):
                    break
                if c < 8:
                    self.drone.move_forward(20)
                if c > 8:
                    break
                pad = self.drone.get_mission_pad_id()

                c += 1
                print(c)
                time.sleep(0.2)

            self.drone.land()
            # call function spawnthreecolorbuttons
        elif button_instance.text == 'Blue':
            # Add logic for Mission 2 button
            print('Mission 2 Button pressed')

        # Add more elif clauses for additional buttons as needed

        # Remove the button from the widget hierarchy

    def finish_mission(self, dt=None):
        # Perform any cleanup or finalization for the mission
        self.manager.current = 'main'


if __name__ in ('__main__', '__android__'):
    drone = Tello()
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
