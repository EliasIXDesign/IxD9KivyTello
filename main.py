import sys
import traceback
import av
import cv2
import numpy
import time
import av
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

                    if cap.get(cv2.CAP_PROP_FPS) < 1.0 / 30:
                        time_base = 1.0 / 30
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


IDX_ROLL = 0
IDX_PITCH = 1
IDX_THR = 2
IDX_YAW = 3


class CoverVideo(CoverBehavior, Video):
    def __init__(self, drone=None, **kwargs):
        super(CoverVideo, self).__init__(**kwargs)
        self.drone = drone

    def start_video(self):
        # start the video feed here
        self.source = 'http://127.0.0.1:30660/video_feed'
        self.play = True

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
        self.drone = drone
        self.flask_app = flask_app
        Builder.load_file('kivytello.kv')

    def build_config(self, config):
        return KivyTelloRoot(drone=self.drone, flask_app=self.flask_app)

    def build(self):
        sm = ScreenManager()

        sm.add_widget(MainScreen(name='main'))

        sm.add_widget(MissionScreen(name='mission'))

        return sm

    def on_pause(self):
        return True

    def on_stop(self):
        Window.close()


class MainScreen(Screen):
    def __init__(self, **kwargs):
        super(MainScreen, self).__init__(**kwargs)
        self.name = 'main'
        self.drone = drone
        self.add_widget(Button(text='Mission 1', on_release=self.start_mission))
        self.add_widget(Button(text='Mission 2', on_release=self.start_mission))
        self.add_widget(Button(text='Mission 3', on_release=self.start_mission))
        self.add_widget(Button(text='Mission 4', on_release=self.start_mission))

    def start_mission(self, instance):
        self.manager.current = 'mission'

    def on_enter(self, *args):
        self.drone.streamon()


class MissionScreen(Screen):
    def __init__(self, drone=None, **kwargs):
        super(MissionScreen, self).__init__(**kwargs)
        self.name = 'mission'
        self.add_widget(Button(text='Return', on_release=self.stop_mission))
        self.stick_data = [0.0] * 4
        self.drone = drone
        Clock.schedule_once(self._finish_init, 5)

    def _finish_init(self, dt):
        print("available ids in MissionScreen", self.ids)
        self.video = self.ids.video
        # self.video.start_video()
        print("available ids in Pad_left", self.ids)
        self.ids.pad_left.bind(pad=self.on_pad_left)
        print("available ids in PadRight", self.ids)
        self.ids.pad_right.bind(pad=self.on_pad_right)
        self.ids.takeoff.bind(state=self.on_state_takeoff)
        self.ids.rotcw.bind(state=self.on_state_rotcw)
        self.ids.rotccw.bind(state=self.on_state_rotccw)
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

    def on_state_rotcw(self, instance, value):
        if value == 'down':
            print('start cw')
            self.drone.clockwise(50)
        else:
            print('stop cw')
            self.drone.clockwise(0)

    def on_state_rotccw(self, instance, value):
        if value == 'down':
            print('start ccw')
            self.drone.counter_clockwise(50)
        else:
            print('stop ccw')
            self.drone.counter_clockwise(0)

    def on_pad_left(self, instance, value):
        x, y = value
        self.stick_data[IDX_YAW] = x
        self.stick_data[IDX_THR] = y
        self.drone.set_throttle(self.stick_data[IDX_THR])
        self.drone.set_yaw(self.stick_data[IDX_YAW])

    def on_pad_right(self, instance, value):
        x, y = value
        self.stick_data[IDX_ROLL] = x
        self.stick_data[IDX_PITCH] = y
        self.drone.set_roll(self.stick_data[IDX_ROLL])
        self.drone.set_pitch(self.stick_data[IDX_PITCH])

    def stop_mission(self, instance):
        self.manager.current = 'main'

    def stop(self):
        self.drone.end()
        App.get_running_app().stop()


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
