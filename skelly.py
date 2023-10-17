import asyncio
import os
import time
import random

from speech import SpeechService

from viam import logging
from viam.robot.client import RobotClient
from viam.rpc.dial import Credentials, DialOptions
from viam.components.camera import Camera
from viam.components.servo import Servo
from viam.services.vision import VisionClient

# these must be set, you can get them from your robot's 'CODE SAMPLE' tab
robot_secret = os.getenv('ROBOT_SECRET') or ''
robot_address = os.getenv('ROBOT_ADDRESS') or ''
time_between_speaking = 10

class robot_resources:
    robot = None
    speech =  None
    face_detector = None
    camera = None
    head = None
    jaw = None
    arm = None
    mouth_led = None

class robot_status:
    last_spoke: time.time()

async def connect():
    creds = Credentials(type="robot-location-secret", payload=robot_secret)
    opts = RobotClient.Options(refresh_interval=0, dial_options=DialOptions(credentials=creds), log_level=logging.DEBUG)
    return await RobotClient.at_address(robot_address, opts)

async def move_jaw_when_speaking():
    while True:
        is_speaking = await robot_resources.speech.is_speaking()
        if is_speaking:
            await robot_resources.mouth_led.move(180)
            move_deg = random.randrange(10,30)
            move_sleep = random.randrange(1,5)
            move_sleep = move_sleep * .1
            await robot_resources.jaw.move(move_deg)
            time.sleep(move_sleep)
            await robot_resources.jaw.move(0)
            time.sleep(move_sleep)
        else:
            await robot_resources.mouth_led.move(0)

async def detect_and_talk():
    while True:
        frame = await robot_resources.camera.get_image()   
        detections = await robot_resources.face_detector.get_detections(frame)
        if len(detections) == 1:
            asyncio.ensure_future(track_face(frame, detections[0]))
            asyncio.ensure_future(reach_if_close(frame, detections[0]))
            if (time.time() - robot_status.last_spoke) > time_between_speaking:
                text = await robot_resources.speech.completion("Give me a quote one might say if they were saying 'Welcome to the party!'", False)
                print(f"The robot said '{text}'")
                robot_status.last_spoke = time.time()

async def reach_if_close(im, detection):
    closeness = (detection.x_max-detection.x_min)/im.size[0]
    print(closeness)
    if closeness < .20 and closeness >= .15:
        await robot_resources.arm.move(50)
        time.sleep(.1)
    else:
        await robot_resources.arm.move(1)
        time.sleep(.1)

async def track_face(im, detection):
    # offset a bit since the camera eye is on one side of the head
    offset = -.2
    # position 0-1, where .5 is in the center of vision
    face_pos = ((detection.x_max-detection.x_min)/2 + detection.x_min)/im.size[0] + offset
    # how many degrees (positive or negative) to move out of a max move size of 10
    move_degs = (1 - face_pos * 2) * 10
    new_position = int(await robot_resources.head.get_position() + move_degs)
    if new_position > 180:
        new_position = 180
    elif new_position < 0:
        new_position = 0
    await robot_resources.head.move(new_position)

async def main():
    robot_resources.robot = await connect()

    robot_resources.speech = SpeechService.from_robot(robot_resources.robot, name="speechio")
    robot_resources.face_detector = VisionClient.from_robot(robot_resources.robot, name="face-detector")
    robot_resources.camera = Camera.from_robot(robot=robot_resources.robot, name="cam")
    robot_resources.head = Servo.from_robot(robot=robot_resources.robot, name="head-servo")
    robot_resources.jaw = Servo.from_robot(robot=robot_resources.robot, name="jaw-servo")
    robot_resources.arm = Servo.from_robot(robot=robot_resources.robot, name="right-arm-servo")
    robot_resources.mouth_led = Servo.from_robot(robot=robot_resources.robot, name="mouth-led")
    robot_status.last_spoke = time.time()

    move_jaw_task = asyncio.create_task(move_jaw_when_speaking())
    talk_to_people = asyncio.create_task(detect_and_talk())

    results= await asyncio.gather(move_jaw_task, talk_to_people, return_exceptions=True)
    print(results)

    await robot_resources.robot.close()


if __name__ == "__main__":
    asyncio.run(main())