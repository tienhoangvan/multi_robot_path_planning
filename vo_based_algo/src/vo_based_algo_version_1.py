#!/usr/bin/env python

import rospy
from nav_msgs.msg import Odometry
from tf.transformations import euler_from_quaternion, quaternion_from_euler
from geometry_msgs.msg import Point
from geometry_msgs.msg import Twist
from std_msgs.msg import Bool
from sensor_msgs.msg import LaserScan
from collections import OrderedDict, deque
from tf import transformations
from math import *
import itertools
import numpy
import os
import time


class Turtlebot3_burger:

    def __init__(self): # Constructor of the Class

        
        rospy.init_node('Algo_Based_on_Velocity_Obstacle', anonymous=True)
        self.robot_name = rospy.get_param('~robot_name')
        self.k_linear = 0.1 #0.1 best so far by experimenting
        self.k_angular = 0.5 #0.5 best so far by experimenting
        self.distance_tolerance = 0.1
 
        self.sub = rospy.Subscriber('/'+self.robot_name+'/odom', Odometry, self.call_back_odom)

        self.x = 0.0
        self.y = 0.0
        self.yaw = 0.0
        self.yaw_error = 0.0
        self.previous_yaw = 0.0
        self.roll = 0.0
        self.pitch = 0.0
        self.orientation_list = [0.0,0.0,0.0,0.0]
        self.goal = Point()
        self.new_goal= Point()
        self.finished = Bool()

        self.pub = rospy.Publisher( '/'+self.robot_name+'/cmd_vel', Twist, queue_size= 1)

        self.speed = Twist()

        self.sub = rospy.Subscriber('/'+self.robot_name+'/scan', LaserScan, self.call_back_laser)

        self.laser_msg = LaserScan()

        self.finished_subscriber = rospy.Subscriber('/'+self.robot_name+'/benchmark/finished',Bool, self.callback_finished)

        self.goal_subscriber = rospy.Subscriber('/'+self.robot_name+'/benchmark/waypoint', Point, self.callback_target)

        self.r = rospy.Rate(1) 
        
        self.end = rospy.get_param('/end_procedure')
        self.angles_and_ranges_dict = OrderedDict() 
        self.outside_vo = list()
        self.vo = list()
        self.final_angle_list = list()
        self.final_angle_list_1 = list()
        self.current_heading_1 = 0.0
        self.inf = itertools.repeat(numpy.inf, 360)
        self.full_laser_ranges = list(self.inf)
        self.array_final_angle_list = []
        self.array_final_angle_list_1 = []
        self.full_laser_ranges_array= []
        
        #.............................#
        self.angle_list1 = range(180) 
        self.angle_list2 = range(180)
        self.temp1 = 0.0
        self.temp2 = 3.141

        for i in self.angle_list1:

            if i==0:
                self.angle_list1[i] = self.temp1
                self.temp1 += 0.0175

            else:
                self.angle_list1[i] = -(self.temp1)
                self.temp1 += 0.0175
                self.temp1 = round(self.temp1,4)

        for i in self.angle_list2:

            self.angle_list2[i] = self.temp2
            self.temp2 -= 0.0175
            self.temp2 = round (self.temp2,4)

        self.final_angle_list = self.angle_list1 + self.angle_list2
        self.array_final_angle_list = numpy.array(self.final_angle_list)
        self.final_angle_list_1 = self.angle_list2 + self.angle_list1
        self.array_final_angle_list_1 = numpy.array(self.array_final_angle_list_1)

    #................................................................................................................................#   

    def callback_target(self, data):
        self.goal = data

    def callback_finished(self, data):
        self.finished = data
    
    def call_back_odom(self,msg):
    
        self.x = msg.pose.pose.position.x
        self.y = msg.pose.pose.position.y

        self.orientation_q = msg.pose.pose.orientation

        self.orientation_list = [self.orientation_q.x,self.orientation_q.y,self.orientation_q.z,self.orientation_q.w]
  
        (self.roll, self.pitch, self.yaw) = euler_from_quaternion (self.orientation_list) 
   
    def call_back_laser(self,data):

        self.laser_msg = data
        self.full_laser_ranges = self.laser_msg.ranges
        self.full_laser_ranges_array = numpy.asarray(self.full_laser_ranges)

    #####################################################################################

    def set_heading (self,angle_to_goal):

        self.desired_heading = angle_to_goal

        (self.quaternion_x, self.quaternion_y, self.quaternion_z, self.quaternion_w) = quaternion_from_euler(self.roll, self.pitch, self.desired_heading)

        self.orientation_list_desired = [self.quaternion_x, self.quaternion_y, self.quaternion_z, -self.quaternion_w]

        self.quat_error = transformations.quaternion_multiply(self.orientation_list, self.orientation_list_desired)

        (self.roll_error, self.pitch_error, self.yaw_error) = transformations.euler_from_quaternion(self.quat_error)

        self.speed.angular.z = -self.k_angular *(self.yaw_error)

        self.pub.publish(self.speed)

    def euclidean_distance(self,goal):
        
        #Euclidean distance between current pose and the goal.
        
        return (sqrt(pow((goal.x - self.x), 2) + pow((goal.y - self.y), 2)))

    ################################################################################
   
    def filterTheDict(self, dictObj, callback):

        self.newDict = OrderedDict()
        
        # Iterate over all the items in dictionary
        for (key, value) in dictObj.items():
            # Check if item satisfies the given condition then add to newDict
            if callback((key, value)):
                self.newDict[key] = value
        return self.newDict

    def legal_velocities(self):

        #Rotate the self.array_final_angle_list in a way that current.yaw conicides with the 0 of self.full_laser_ranges_filtered_array

        self.array_final_angle_list_temp = self.array_final_angle_list

        self.index_rotate = (numpy.abs(self.array_final_angle_list_temp - self.yaw)).argmin()
         
        self.array_final_angle_list_temp = deque(self.array_final_angle_list_temp)

        self.array_final_angle_list_temp.rotate(-self.index_rotate)
        
        #Making ordered dictionary

        self.angles_and_ranges_dict = OrderedDict(zip(self.array_final_angle_list_temp, self.full_laser_ranges_array))

        #Filter vo and outside_vo
        
        self.newDict = self.filterTheDict(self.angles_and_ranges_dict, lambda elem: elem[1] == numpy.inf or elem[1] > 0.5)
        self.outside_vo = list(self.newDict.keys())
        self.outside_vo = self.outside_vo[30::20]
        self.array_outside_vo = numpy.asarray(self.outside_vo)

        self.newDict = self.filterTheDict(self.angles_and_ranges_dict, lambda elem: elem[1] < 0.5)
        self.vo = list(self.newDict.keys())
        self.array_vo = numpy.asarray(self.vo)

    #################################################################################
   
    def check_for_collision(self,current_heading): 

        current_heading = round(current_heading, 4)  
        
        self.temp3 = False
        self.temp4 = 0.0
        self.distance_to_obstacle = 0.0
        self.index_vo_min = 0.0
        self.index_vo_max = 0.0

        if len(self.array_vo) != 0:

            self.index_vo_min = (numpy.abs(self.array_vo - current_heading)).argmin()
            self.index_vo_max = (numpy.abs(self.array_vo - current_heading)).argmax()

            c1 = abs(self.array_vo[self.index_vo_min] - current_heading) <= 1.575
            #c2 = abs(self.array_vo[self.index_vo_max] - current_heading) >= 6.00 #6.1945
            c2 = False
          
            if c1|c2:

                self.temp3 = True

                print ('"Velocity_Heading is inside of VO, collision in future. Choose velocity outside VO"')

                if c1:

                    self.temp4 = (self.array_vo[self.index_vo_min])
                    self.distance_to_obstacle = self.angles_and_ranges_dict[self.temp4]

                if c2:
                    self.temp4 = (self.array_vo[self.index_vo_max])
                    self.distance_to_obstacle = self.angles_and_ranges_dict[self.temp4]
            
        return self.temp3, self.distance_to_obstacle

    ##############################################################################

    def choose_new_velocity(self, distance_to_obstacle):

        self.index_outside_vo_min = 0.0
        self.index_outside_vo_max = 0.0

        if len(self.array_outside_vo) != 0:

            self.diff_x = self.goal.x - self.x
            self.diff_y = self.goal.y - self.y

            self.angle_to_goal = atan2(self.diff_y,self.diff_x)

            self.angle_to_goal += 0.5
            self.angle_to_goal = round(self.angle_to_goal,4)

            self.index_outside_vo_min = (numpy.abs(self.array_outside_vo - self.angle_to_goal)).argmin()
            self.index_outside_vo_max = (numpy.abs(self.array_outside_vo - self.angle_to_goal)).argmax()

            c4 = numpy.abs(self.array_outside_vo[self.index_outside_vo_max] - self.angle_to_goal) >= 6.1945

            self.angle_to_goal = self.array_outside_vo[self.index_outside_vo_min] 

            if c4:

                self.angle_to_goal = self.array_outside_vo[self.index_outside_vo_max] 

            self.set_heading(self.angle_to_goal)
            time.sleep(1)
            print ('the selected_legal_velocity is, if ', self.angle_to_goal)
            print ('The current heading', self.yaw)

        else:
            #choose penality velocity heading

            self.speed.linear.x = 0.00
            self.pub.publish(self.speed)
            self.diff_x = self.goal.x - self.x
            self.diff_y = self.goal.y - self.y
            self.angle_to_goal = atan2(self.diff_y,self.diff_x)
            self.angle_to_goal += 0.5 
            self.set_heading(self.angle_to_goal)
            print('running on penality Velocity')
            self.speed.linear.x = 0.01
            self.pub.publish(self.speed)
            print ('the selected_legal_velocity is, else ', self.angle_to_goal)
            print ('The current heading', self.yaw)

        
 
    ############################################################################ 
    def end_procedure(self):

        if self.end_procedure == 'start':

            while (self.euclidean_distance(self.goal) > self.distance_tolerance):
    
                #what are illegal and legal velocity heading
                
                self.legal_velocities()

                #check the condition for collision
                
                self.collision, self.distance_to_obstacle = self.check_for_collision(self.yaw)


                if self.collision:

                    self.speed.linear.x = self.k_linear * self.distance_to_obstacle
                    self.pub.publish(self.speed)
                    if self.distance_to_obstacle < 0.5:
                        self.choose_new_velocity(self.distance_to_obstacle) 

                else:

                    self.distance_to_goal = self.euclidean_distance(self.goal)

                    self.speed.linear.x = self.k_linear * self.distance_to_goal

                    self.pub.publish(self.speed)

                    self.diff_x = self.goal.x - self.x
                    self.diff_y = self.goal.y - self.y

                    self.angle_to_goal = atan2(self.diff_y,self.diff_x)

                    self.angle_to_goal = round(self.angle_to_goal,3)
                    
                    self.set_heading(self.angle_to_goal)

                    self.pub.publish(self.speed)

                self.speed.linear.x = 0.00
                self.speed.angular.z = 0.00
                self.pub.publish(self.speed)
                print('The goal has been achieved by', self.robot_name)
                print ('goal_x coordinate',self.x)
                print ('goal_y coordinate',self.y)
         
        elif self.end_procedure == 'despawn':

            print(self.robot_name,' will be despawned')

        elif self.end_procedure == 'stop':

            self.speed.linear.x = 0.00   
            self.speed.angular.z = 0.00 
            self.pub.publish(self.speed)
            print(self.robot_name, 'has been stopped')

    ######## STARTING METHOD ##############################################

    def move_towards_goal (self):
        
        #Initializing the velocities and the heading towards goal location
        while not rospy.is_shutdown():

            self.speed.linear.x = 0
            self.speed.linear.y = 0
            self.speed.linear.z = 0
            self.speed.angular.x = 0
            self.speed.angular.y = 0
            self.speed.angular.z = 0
            self.pub.publish(self.speed)

            self.diff_x = self.goal.x - self.x
            self.diff_y = self.goal.y - self.y

            self.angle_to_goal = atan2(self.diff_y,self.diff_x)
            
            self.angle_to_goal = round(self.angle_to_goal,4)

            self.set_heading(self.angle_to_goal)

            if self.finished == Bool(True):

                self.speed.linear.x = 0.00
                self.speed.angular.z = 0.00
                self.pub.publish(self.speed)
                print('The goal has been achieved by', self.robot_name)
                print('goal_x coordinate',self.goal.x)
                print('goal_y coordinate',self.goal.y)
                self.end_procedure()

            elif self.finished == Bool(False) and self.new_goal == self.goal:

                self.speed.linear.x = 0.00
                self.speed.angular.z = 0.00
                self.pub.publish(self.speed)
                print('Waiting for new goal', self.robot_name)
                print('curret x coordinate',self.x)
                print('current y coordinate',self.y)

            elif self.finished == Bool(False) and self.new_goal != self.goal:
            
                self.new_goal = self.goal
                print('New goal position has been Recieved by', self.robot_name)
                print('goal x', self.goal.x)
                print('goal y', self.goal.y)
                print('current_pos', self.x)
                print('current_pos', self.y)

                while (self.euclidean_distance(self.goal) > self.distance_tolerance):

                    #what are illegal and legal velocity heading

                    self.legal_velocities()

                    #check the condition for collision

                    self.collision, self.distance_to_obstacle = self.check_for_collision(self.yaw)

                    if self.collision:

                        self.previous_yaw = self.yaw
                        self.speed.linear.x = self.k_linear * self.distance_to_obstacle
                        self.pub.publish(self.speed)
                        self.choose_new_velocity(self.distance_to_obstacle)

                    else:

                        self.distance_to_goal = self.euclidean_distance(self.goal)

                        self.speed.linear.x = self.k_linear * self.distance_to_goal
                        if self.speed.linear.x > 0.22:
                            self.speed.linear.x = 0.5

                        self.pub.publish(self.speed)

                        self.diff_x = self.goal.x - self.x
                        self.diff_y = self.goal.y - self.y

                        self.angle_to_goal = atan2(self.diff_y,self.diff_x)

                        self.angle_to_goal = round(self.angle_to_goal,3)
                        
                        self.set_heading(self.angle_to_goal)

                        if abs(self.yaw - self.previous_yaw) < 0.175:
                            
                            pass

                        self.pub.publish(self.speed)

                        print('In colllosion free mode')

                self.speed.linear.x = 0.00   
                self.speed.angular.z = 0.00 
                self.pub.publish(self.speed)
                print('The goal has been achieved by', self.robot_name)
                print ('goal_x coordinate',self.x)
                print ('goal_y coordinate',self.y)
        rospy.spin()

if __name__ == '__main__':
    
    #while not rospy.is_shutdown():

    class_instance = Turtlebot3_burger()
    class_instance.move_towards_goal()
    
    #rospy.spin()
