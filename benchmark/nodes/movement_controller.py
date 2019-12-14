#!/usr/bin/env python

""" --------------------------------------------------------------
@author:    Johann Schmidt
@date:      November 2019
@brief:     Node for movement
@todo:
------------------------------------------------------------- """


import rospy
import src.movement as movement
import src.utils.topic_handler as topic_handler
from geometry_msgs.msg import Point
from std_msgs.msg import Bool


def callback_target(data, args):
    """ Callback for robot target points to move to.
    :param data:
    :param args:
    """
    global robot_targets, robot_rounds
    if not robot_rounds[args[0]]:
        robot_targets[args[0]] = [data.x, data.y, data.z]


def callback_rounds(data, args):
    """ Callback for rounds completed.
    :param data:
    :param args:
    """
    global robot_rounds
    robot_rounds[args[0]] = data


def setup_move_controller(_namespace, _number_of_robots):
    """ Init. all required movement controller.
    :param _namespace:
    :param _number_of_robots:
    """
    for robot_id in range(_number_of_robots):
        move_controller[robot_id] = movement.MovementController(
            robot_name=str(robot_id), namespace=_namespace)


def setup_subscribers(_namespace, _number_of_robots):
    """ Setup all subscribers.
    :param _namespace:
    :param _number_of_robots:
    """
    global robot_rounds
    for robot_id in range(_number_of_robots):
        robot_rounds[robot_id] = False
        topic_name = _namespace + str(robot_id) + "/waypoint"
        topic_handler.SubscribingHandler(topic_name, Point, callback_target, robot_id)
        topic_name = _namespace + str(robot_id) + "/rounds"
        topic_handler.SubscribingHandler(topic_name, Bool, callback_rounds, robot_id)


def wait_for_targets(_number_of_robots, quiet=False, frequency=1):
    """ Waits until target points have been received.
    :param _number_of_robots:
    :param quiet:
    :param frequency:
    :return True:   received
            False:  waiting
    """
    while len(robot_targets) != _number_of_robots:
        if not quiet:
            rospy.loginfo("Waiting for target points ...")
        rospy.Rate(frequency).sleep()


def update_movement(_number_of_robots, frequency=0.5):
    """ Updates the movement to the target points.
    :param _number_of_robots:
    :param frequency:
    """
    while not rospy.is_shutdown():
        for robot_id in range(_number_of_robots):
            if robot_id in robot_targets:
                move_controller[robot_id].linear_move_to(
                    robot_targets[robot_id], quiet=False)
            else:
                rospy.loginfo("Robot {} not found".format(robot_id))
        rospy.Rate(frequency).sleep()


move_controller = {}
robot_targets = {}
robot_rounds = {}
rospy.init_node('movement_controller', anonymous=True)
namespace = rospy.get_param('namespace')
number_of_robots = rospy.get_param('number_of_robots')
setup_subscribers(namespace, number_of_robots)
setup_move_controller(namespace, number_of_robots)
wait_for_targets(number_of_robots)
update_movement(number_of_robots)
