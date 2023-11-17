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
from djitellopy import Tello
from threading import Thread
from flask import Response, request
from perfume import route, Perfume


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


class KivyTelloRoot(FloatLayout):
    def __init__(self, drone=None, flask_app=None, **kwargs):
        super(KivyTelloRoot, self).__init__(**kwargs)
        # self.stick_data = [0.0] * 4
        Window.allow_vkeyboard = False
        self.ids.takeoff.bind(state=self.on_state_takeoff)
        self.ids.quit.bind(on_press=lambda x: self.stop())
        self.drone = drone
        self.flask_app = flask_app

    def on_state_takeoff(self, instance, value):
        if value == 'down':
            print('take off')
            self.drone.takeoff()
        else:
            print('land')
            self.drone.land()


class KivyTelloApp(App):
    def __init__(self, drone=None, flask_app=None, **kwargs):
        super(KivyTelloApp, self).__init__(**kwargs)
        self.drone = drone
        self.flask_app = flask_app

    def build(self):
        # Example usage:
        initial_button_texts = ["Dragon", "Fire", "Cops and Robbers"]

        # Create an instance of MainScreen
        main_screen = MainScreen(self.mission_callback, initial_button_texts, name="main")

        # Create ScreenManager and add MainScreen instance to it
        sm = ScreenManager()
        sm.add_widget(main_screen)

        # Add MissionScreens to ScreenManager
        for i in range(1, 3):
            sm.add_widget(MissionScreen(i, self.mission_callback, name=f"mission{i}"))

        # Return KivyTelloRoot with ScreenManager as a child
        return KivyTelloRoot(drone=self.drone, flask_app=self.flask_app, sm=sm)

    def on_pause(self):
        return True

    def on_stop(self):
        Window.close()


class MissionScreen(Screen):
    def __init__(self, mission_number, mission_callback, **kwargs):
        super(MissionScreen, self).__init__(**kwargs)
        self.mission_number = mission_number
        self.mission_callback = mission_callback
        self.setup_mission()
        self.buttons = []  # To store references to created buttons
        # Clear existing widgets
        self.clear_widgets()
        # Set up the video feed as a kivy widget
        self.cover_video = CoverVideo()
        self.add_widget(self.cover_video)

    def setup_mission(self):
        # Adds the video widget to all missions, if clear all widgets is not called
        self.add_widget(self.cover_video)

        if self.mission_number == 1:
            self.setup_mission_1()
        elif self.mission_number == 2:
            self.setup_mission_2()
        elif self.mission_number == 3:
            self.setup_mission_3()

    def setup_mission_1(self):
        # Shows button to start mission after 5 seconds
        Clock.schedule_once(self.show_first_button, 5)

    def show_first_button(self, dt):
        # Create a button with custom text
        button_1 = Button(text="Click me!", on_press=self.button_1_clicked, pos_hint={'center_x': 0.5, 'center_y': 0.5})
        self.add_widget(button_1)
        self.buttons.append(button_1)  # Store the reference to the button

    def button_1_clicked(self, instance):
        # Handle button click action (send command to the drone, etc.)
        self.drone_command_1()

        # Clear only the first button, i.e. the one that was clicked and is in pos 0 of the list
        self.clear_specific_button(self.buttons[0])

        # After the action is done, schedule the appearance of the second button after 3 seconds
        Clock.schedule_once(self.show_second_button, 3)

    def show_second_button(self, dt):
        # Create a button with custom text
        button_2 = Button(text="Click me again!", on_press=self.button_2_clicked,
                          pos_hint={'center_x': 0.5, 'center_y': 0.5})
        self.add_widget(button_2)
        self.buttons.append(button_2)  # Store the reference to the button

    def button_2_clicked(self, instance):
        # Handle button click action (send another command to the drone, etc.)
        self.drone_command_2()

        # Clear only the second button
        self.clear_specific_button(self.buttons[1])

        # After the action is done, schedule the appearance of the final button after 3 seconds
        Clock.schedule_once(self.show_final_button, 3)

    def show_final_button(self, dt):
        # Create a button with custom text
        final_button = Button(text="Return to Main Screen", on_press=self.return_to_main_screen,
                              pos_hint={'center_x': 0.5, 'center_y': 0.5})
        self.add_widget(final_button)
        self.buttons.append(final_button)  # Store the reference to the button

    def clear_specific_button(self, button):
        # Clear only the specified button
        self.remove_widget(button)
        self.buttons.remove(button)

    def setup_mission_2(self):
        mission_successful = self.mission_callback(self.mission_number)
        video_path = "successful_mission.mp4" if mission_successful else "failed_mission.mp4"

        # Create CoverVideo dynamically
        cover_video = CoverVideo(source='http://127.0.0.1:30660/video_feed', state='play', options={'eos': 'loop'})
        self.add_widget(cover_video)

        Clock.schedule_once(self.return_to_main_screen, 5)

    def setup_mission_3(self):
        mission_successful = self.mission_callback(self.mission_number)
        video_path = "successful_mission.mp4" if mission_successful else "failed_mission.mp4"

        # Create CoverVideo dynamically
        cover_video = CoverVideo(source='http://127.0.0.1:30660/video_feed', state='play', options={'eos': 'loop'})
        self.add_widget(cover_video)

        Clock.schedule_once(self.return_to_main_screen, 5)

    def on_enter(self, *args):
        self.setup_mission()

    def return_to_main_screen(self, dt):
        self.manager.current = "main"


class MainScreen(Screen):
    def __init__(self, mission_callback, initial_button_texts, **kwargs):
        super(MainScreen, self).__init__(**kwargs)
        self.mission_callback = mission_callback
        self.create_buttons(initial_button_texts)

    def create_buttons(self, button_texts):
        for text in button_texts:
            button = Button(text=text, on_press=self.start_mission)
            self.add_widget(button)

    def start_mission(self, instance):
        mission_number = int(instance.text.split()[1])
        self.manager.current = f"mission{mission_number}"

    def on_enter(self, *args):
        Clock.schedule_once(self.show_new_button, 2)

    def show_new_button(self, dt):
        self.clear_widgets()
        new_button = Button(text="New Mission", on_press=self.create_buttons)
        self.add_widget(new_button)


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
        print(ex)
        self.drone.streamoff()
        drone.end()
        Window.close()
