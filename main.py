#!/usr/bin/env pybricks-micropython
from pybricks.hubs import EV3Brick
from pybricks.ev3devices import (Motor, ColorSensor, GyroSensor)
from pybricks.nxtdevices import ColorSensor as nxtColorSensor
from pybricks.parameters import Port, Stop, Direction, Button, Color
from pybricks.tools import wait, StopWatch, DataLog
from pybricks.robotics import DriveBase
from pybricks.media.ev3dev import SoundFile, ImageFile
from pybricks.iodevices import Ev3devSensor

import math, time
import sys
from helper import *
from pid import *

# declare global variables
Houses = [[], [], []]
numYellow = 4
numBlue = 4
numGreen = 4
numSurplus = 4

# initialise ev3
ev3 = EV3Brick()

# initialise motors
frontClaw = FrontClaw(Port.A)
backClaw = BackClaw(Port.D)
leftMotor = Motor(Port.B, positive_direction = Direction.COUNTERCLOCKWISE)
rightMotor =  Motor(Port.C)

# initialise sensors

ev3Col = Ev3devSensor(Port.S1)
gyro = GyroSensor(Port.S2)
colLeft = ColorSensor(Port.S3)
colRight = ColorSensor(Port.S4)

base = Base(leftMotor, rightMotor, colLeft, colRight, frontClaw, backClaw)

# set up defaults for PID functions
LineTrack = PID_LineTrack(base, 0.16, 0, 5, 50)
GyroStraight = PID_GyroStraight(base, 1.2, 0, 5, gyro)
GyroTurn = PID_GyroTurn(base, 0.9, 0.0001, 2.5, gyro)

# battery alert
print(ev3.battery.voltage())
if ev3.battery.voltage() <= 7400:
  print('LOW BATTERY')
  ev3.speaker.beep()
  sys.exit()

def scanHouseEV3(house, sensor, speed, condition):   
  # initialise pid for gyrostraight
  kp, ki, kd = GyroStraight.kp, GyroStraight.ki, GyroStraight.kd
  gyro.reset_angle(0)
  gyroPID = PID(kp, ki, kd)
  
  while condition():
    detected = False
    gyroPID.update(gyro.angle(), kp, ki, kd)
    base.run(speed - gyroPID.correction, speed + gyroPID.correction)
    r, g, b = sensor.read('RGB-RAW')
    if r + g + b > 15:
      detected = True     
      if r - b >= 3 and r - g >= 3:
        house.append(Color.YELLOW)
      elif b - r >= 3 and b - g >= 3:
        house.append(Color.BLUE)
      elif g - r >= 3 and g - b >= 3:
        house.append(Color.GREEN) 
      else:
        detected = False
    
    # once an indicator has been detected, move until nothing is detected
    if detected:
      while r + g + b > 12:
        r, g, b = sensor.read('RGB-RAW')
        gyroPID.update(gyro.angle(), kp, ki, kd)
        base.run(speed - gyroPID.correction, speed + gyroPID.correction)
      detected = False

  print(house)
  base.stop()

def checkSurplus(degrees):
  # reverse for certain amount of degrees to check if surplus is present
  speed = -30
  kp, ki, kd = GyroStraight.kp, GyroStraight.ki, GyroStraight.kd
  gyroPID = PID(kp, ki, kd)
  base.reset()
  while leftMotor.angle() >= degrees:
    r, g, b = ev3Col.read('RGB-RAW')
    gyroPID.update(gyro.angle(), kp, ki, kd)
    base.run(speed - gyroPID.correction, speed + gyroPID.correction)
    if (r + g + b) > 20:
      return True

  return False

def collectSurplus(degrees, col):
  # align robot using surplus
  base.reset()
  frontClaw.reset(1500)
  if col != Color.BLUE:
    GyroStraight.move(-30, condition = lambda: leftMotor.angle() > -250)
    GyroTurn.turn(90)
    gyro.reset_angle(0)

  GyroStraight.move(-30, condition = lambda: colRight.reflection() > 40)
  base.hold()
  PID_LineSquare(base, direction = -1)
  gyro.reset_angle(0)
  base.hold()
  base.reset()
  # move forward to collect surplus
  GyroStraight.move(30, condition = lambda: leftMotor.angle() <= degrees)
  base.hold()
  # grab front surplus using claw
  frontClaw.run_target(-40, -470)
  
def collectGreen(degrees):  
  # reset claw to maintain consistency
  backClaw.run_time(100, 1200, wait = False)
  
  # line track and turn to collect first 2 green 
  base.reset()
  LineTrack.move(colRight, 30, condition = lambda: leftMotor.angle() < 200)
  LineTrack.move(colRight, 50, condition = lambda: colLeft.reflection() > 15)
  base.reset()
  LineTrack.move(colRight, 40, condition = lambda: leftMotor.angle() < 220)
  base.hold()

  GyroTurn.turn(-90)
  while colRight.reflection() < 60:
    base.run(-40, -40)
  base.hold()
  
  PID_LineSquare(base, direction = -1)
  gyro.reset_angle(0)
   
  # move forward, lower claw then reverse to collect green
  base.run_target(40, 200)
  backClaw.mid()
  GyroStraight.move(-30, condition = lambda: colRight.reflection() < 70)
  GyroStraight.move(-30, condition = lambda: colRight.reflection() > 15)
  base.hold()

  # reset claw again
  backClaw.run_time(100, 1200)
  
  # linetrack and turn to grab other 2 green
  GyroStraight.move(40, condition = lambda: colRight.reflection() < 70)
  GyroStraight.move(40, condition = lambda: colRight.reflection() > 40)
  base.hold()
  GyroTurn.turn(90)
  base.reset()
  GyroStraight.move(40, condition = lambda: leftMotor.angle() <= degrees)
  base.hold()

  GyroTurn.turn(-90)
  while colRight.reflection() < 70:
    base.run(-40, -40)
  base.hold()
  
  PID_LineSquare(base, direction = -1)

  gyro.reset_angle(0)
  base.reset()
  GyroStraight.move(50, condition = lambda: leftMotor.angle() < 200)
  base.hold()
  backClaw.mid()
  GyroStraight.move(-30, condition = lambda: colRight.reflection() < 60)
  base.hold()
  backClaw.run_target(50, 80)
  
  # cap speed of turns after grabbing green to stop them from jerking
  GyroTurn.maxSpeed = 50
  GyroTurn.turn(-90)

def returnHouse1():
  pass

def depositHouse(house, time, houseNum):
  global numGreen, numBlue, numYellow, numSurplus
  
  if time == 1:
    # first visit to house deposits surplus and green
    numCol = numGreen
    RingCol = Color.GREEN
    if len(house) == 1: # surplus to be deposited
      # only 2 surplus ever need to be deposited
      
      if houseNum == 1:
        GyroTurn.turn(-90)
      else:
        GyroTurn.turn(90)
       
      if houseNum == 1:
        base.reset()
        LineTrack.move(colRight, 35, condition = lambda: leftMotor.angle() < 300)
        base.hold()
      
      # lift claw, move forward then reverse to deposit surplus from within catchment area
      frontClaw.run_target(-70, -300)
      GyroStraight.move(40, condition = lambda: colLeft.color() != Color.RED)
      base.reset()
      GyroStraight.move(40, condition = lambda: leftMotor.angle() < 100)  
      base.reset()
      GyroStraight.move(-40, condition = lambda: leftMotor.angle() > -300)
      base.hold()
      if Color.GREEN in house:
        GyroTurn.turn(-180)
      else:
        GyroStraight.move(-40, condition = lambda: colLeft.reflection() > 15 or colRight.reflection() > 15)
        base.hold()
        if house == 1:
          GyroTurn.turn(-90)
        elif house == 2: 
          GyroTurn.turn(90)
        
      frontClaw.run_target(30, 300, wait=False)
      
  else:
    # second visit to house deposits yellow and blue
    numCol = numBlue
    RingCol = Color.BLUE
  
    if Color.YELLOW in house: 
      # check number of yellow in house
      tmp = 1
      if len(house) == 2:
        if house[0] == Color.YELLOW and house[1] == Color.YELLOW:
          tmp = 2
      if houseNum == 1:
        GyroTurn.turn(90)
      
      if tmp == 2:
        # deposit both yellow
        frontClaw.run_target(70, 200)
        base.reset()
        GyroStraight.move(-40, condition = lambda: leftMotor.angle() > -200)
        base.hold()
        frontClaw.run_target(-70, -500)
        base.reset()
        LineTrack.move(colRight, 35, condition = lambda: leftMotor.angle() < 300)
        base.hold()
        GyroStraight.move(40, condition = lambda: colLeft.color() != Color.RED)
        base.reset()
        GyroStraight.move(40, condition = lambda: leftMotor.angle() < 100)
        base.hold()
        base.reset()
        GyroStraight.move(-40, condition = lambda: leftMotor.angle() > -200)
        base.hold()
      
      elif tmp == 1 and numYellow == 2:
        # deposit yellow from claw
        LineTrack.move(colRight, 35, condition = lambda: leftMotor.angle() < 200)
        base.hold()
        frontClaw.run_target(70, 200)
        GyroStraight.move(-40, condition = lambda: leftMotor.angle() > -200)
        base.hold()
        
      else:
        # deposit yellow from catchment area
        base.reset()
        LineTrack.move(colRight, 35, condition = lambda: leftMotor.angle() < 100)
        frontClaw.run_target(-70, -300)
        GyroStraight.move(40, condition = lambda: colLeft.color() != Color.RED)
        base.reset()
        GyroStraight.move(40, condition = lambda: leftMotor.angle() < 100)
        base.hold()
        base.reset()
        GyroStraight.move(-40, condition = lambda: leftMotor.angle() > -200)
        base.hold()
  
  if RingCol in house: # green/blue to be deposited
    tmp = 1
    
    # check number of green/blue indicators for house
    if len(house) == 2:
      if house[0] == RingCol and house[1] == RingCol:
        tmp = 2

      if houseNum == 1 and tmp == 2:
        GyroTurn.turn(90)
        
      elif tmp == 2:
        GyroTurn.turn(-90)
    base.reset()
    base.hold()
    base.reset()
    GyroStraight.move(-40, condition = lambda: leftMotor.angle() < -150)
    base.hold()
    backClaw.run_target(-20, -140)
    base.reset()
    # reverse more if 2 ring blocks have to be deposited
    if numCol == 4 and tmp == 1:
      GyroStraight.move(30, condition = lambda: leftMotor.angle() < 50) 
      numCol -= 2       
    else:
      GyroStraight.move(30, condition = lambda: leftMotor.angle() < 100)
      numCol -= 4
    base.hold()
    backClaw.run_target(40, 140)

    if houseNum == 1 or houseNum == 2:
      GyroStraight.move(40, condition = lambda: colLeft.reflection() > 15 or colRight.reflection() > 15)
      base.hold()
      base.reset()
      GyroStraight.move(40, condition = lambda: leftMotor.angle() < 150)
      base.hold()
      if house == 1:
        GyroTurn.turn(90)
      else:
        GyroTurn.turn(-90)
         
    # if no more ring blocks are on the bot, reset the maximum turn speed
    if numCol == 0:
      GyroTurn.maxspeed = 100

def collectBlue():
  backClaw.reset(1000, speed = 50)
  backClaw.run_target(-50, -170)
  base.reset()
  GyroStraight.move(-40, condition = lambda: leftMotor.angle() > -100)
  base.hold()
  wait(1000)

def depositBattery(side = 1):
  pass

def collectYellow():
  # push solar panels
  base.reset()
  frontClaw.reset(1500)
  frontClaw.run_target(-50, -390)
  frontClaw.hold()
  LineTrack.move(colRight, 40, condition = lambda: leftMotor.angle() < 200)
  while colLeft.color() != Color.BLACK or colRight.color() != Color.BLACK:
    base.run(20, 20)
  base.reset()
  while leftMotor.angle() < 100:
    base.run(20, 20)
  base.hold()
  frontClaw.reset(1500, dir = -1, speed = 40)
  
  # track to first 2 yellow and grab with claw
  GyroTurn.turn(-90)
  base.reset()
  LineTrack.move(colRight, 40, condition = lambda: leftMotor.angle() < 500)
  GyroStraight.move(40, condition = lambda: leftMotor.angle() < 600)
  base.hold()
  frontClaw.reset(1500)
  GyroTurn.turn(90)
  base.reset()
  GyroStraight.move(20, condition = lambda: leftMotor.angle() < 30)
  base.hold()
  frontClaw.run_target(-50, -470)
  base.reset()
  GyroStraight.move(-40, condition = lambda: leftMotor.angle() > -60)
  base.hold()
  wait(1000)
  
  # collect next 2 in catchment area
  GyroTurn.turn(90)
  LineTrack.move(colLeft, 50, condition = lambda: colRight.color() != Color.BLACK)
  base.reset()  
  LineTrack.move(colLeft, 40, condition = lambda: leftMotor.angle() < 550)
  GyroStraight.move(40, condition = lambda: leftMotor.angle() < 750)
  base.hold()
  frontClaw.run_target(-40, -250)
  GyroTurn.turn(-90)
  base.reset()
  GyroStraight.move(40, condition = lambda: leftMotor.angle() < 200)
  base.hold()
  frontClaw.run_target(30, 250)
  GyroTurn.turn(90)
  GyroStraight.move(60, condition=lambda: colRight.color() != Color.BLACK)
  
def main():
  surplus = None
  gyro.reset_angle(0)
  base.reset()
  GyroStraight.move(70, condition = lambda: leftMotor.angle() <= 200)   
  LineTrack.move(colRight, 50, side = -1, condition = lambda: colLeft.reflection() > 15)   
  base.reset()
  GyroStraight.move(50, condition = lambda: leftMotor.angle() <= 300)
  base.hold()
  GyroTurn.turn(-90)
  
  # wall align and scan indicators 
  base.run_time(-100, 1.3)
  gyro.reset_angle(0)  
  scanHouseEV3(Houses[0], ev3Col, 50, lambda: colRight.reflection() > 15)
  PID_LineSquare(base, direction = -1)
  PID_SingleMotorTurn(rightMotor, gyro, -179)
  gyro.reset_angle(0)
  
  # if yellow surplus is present, collect it 
  # move toward green energy
  if checkSurplus(-140):
    surplus = Color.YELLOW
    collectSurplus(360, Color.YELLOW)
    GyroStraight.move(-40, condition = lambda: colRight.reflection() > 15)
    base.reset()
    GyroStraight.move(40, condition = lambda: leftMotor.angle() <= 100)
    base.hold()
    GyroTurn.turn(90)

  else:
    gyro.reset_angle(0)
    GyroTurn.turn(180)
    PID_AngleOffSet(base, gyro, 42)
    
  # collect green energy
  collectGreen(360)
  
  # collect green surplus if present, else go collect blue surplus
  if surplus is None:
    if checkSurplus(-200, Color.GREEN):
      surplus = Color.GREEN
      collectSurplus(200)
      PID_SingleMotorTurn(leftMotor, gyro, -90)
      
    else:
      surplus = Color.BLUE
      GyroTurn.turn(180)
      gyro.reset_angle(0)
      base.reset()
      LineTrack.move(colLeft, 60, condition = lambda: colRight.color() != Color.BLACK)
      base.hold()
      base.reset()
      GyroStraight.move(-30, condition = lambda: leftMotor.angle() > -150)
      base.hold()
      GyroTurn.turn(-90)
      collectSurplus(610, Color.BLUE)

      GyroStraight.move(-60, condition = lambda: colLeft.color() != Color.BLACK)
      base.hold()
      GyroStraight.move(40, condition = lambda: colLeft.color() != Color.WHITE)
      GyroStraight.move(40, condition = lambda: colLeft.color() != Color.BLACK)
      base.reset()
      GyroStraight.move(40, condition = lambda: leftMotor.angle() < 50)
      base.hold()
      GyroTurn.turn(-90)
      
    LineTrack.move(colRight, 70, side = -1,  condition = lambda: colLeft.color() != Color.BLACK)
    LineTrack.move(colRight, 70, side = -1, condition = lambda: colLeft.color() != Color.WHITE)
      
  else:
    gyro.reset_angle(0)
    LineTrack.move(colRight, 70, side = -1,  condition = lambda: leftMotor.angle() < 500)

  LineTrack.move(colRight, 70, side = -1, condition = lambda: colLeft.color() != Color.BLACK)
  base.reset() 
  LineTrack.move(colRight, 40, side = -1,  condition = lambda: leftMotor.angle() < 90)
  base.hold()
  
  # start first round of deposition (green + surplus)
  depositHouse(Houses[0], 1, 1)
  
  LineTrack.move(colRight, 70, side = -1, condition = lambda: colLeft.color() != Color.BLACK)
  LineTrack.move(colRight, 70, side = -1, condition = lambda: colLeft.color() != Color.WHITE)
  LineTrack.move(colRight, 70, side = -1, condition = lambda: colLeft.color() != Color.BLACK)
  base.reset()
  LineTrack.move(colRight, 60, side = -1, condition = lambda: leftMotor.angle() < 650)
  base.hold()
  PID_AngleOffSet(base, gyro, 80)
  base.hold()
  GyroTurn.maxSpeed = 40
  PID_LineSquare(base, direction = -1)
  gyro.reset_angle(0)
  base.reset()
  GyroStraight.move(-50, condition = lambda: leftMotor.angle() > -300)
  base.hold()
  scanHouseEV3(Houses[1], ev3Col, 50)  
  
  depositHouse(Houses[1], 1, 2)
  
  LineTrack.move(colLeft, 50, condition = lambda: colRight.reflection() > 15)
  
  scanHouse3(Houses[2], ev3Col, 50)
  depositHouse(Houses[2], 1, 3)
  # always deposit two surplus into battery storage from claw, deposit any remaining green
  depositBattery()
  
  # collect yellow and blue energy

  collectBlue()  
  collectYellow()
  if Color.YELLOW or Color.BLUE in Houses[2]:
    depositHouse(Houses[2], 2, 3)
  
  # based on houses, determine which energy is extra and deposit it
  depositBattery()
  
  # clear remaining houses 
  if Color.BLUE or Color.YELLOW in Houses[1]:
    depositHouse(Houses[1], 2, 2)
    
  if Color.BLUE or Color.YELLOW in Houses[0]:
    depositHouse(Houses[0], 2, 1)
    
  # go back to base
  returnBase()

# gyro.reset_angle(0)
# collectYellow()
frontClaw.run_target(-40, -250)
frontClaw.run_target(30, 250)
# wait(1000)

# base.reset()
# LineTrack.move(colRight, 70, side = -1,  condition = lambda: leftMotor.angle() < 500)
# LineTrack.move(colRight, 70, side = -1, condition = lambda: colLeft.color() != Color.BLACK)
# base.hold()
# wait(1000)
# wait(4000)
# backClaw.run_target(-20, -140)
# base.reset()
# wait(3000)
# GyroStraight.move(20, condition = lambda: leftMotor.angle() < 200)
# base.hold()
# backClaw.run_target(20, 140)


# scanHouseEV3(Houses[1], ev3Col, 50, lambda: colRight.reflection() > 15)  
# base.hold()
# GyroStraight.move(40, condition = lambda: colRight.reflection() < 80)
# GyroStraight.move(40, condition = lambda: colRight.reflection() > 40)
# base.hold()
# depositHouse(Houses[1], 1, 2)
# # SHOULD SHIFT SOLAR PANELS TO PART FOR COLLECTING YELLOW FOR BETTER ROUTING