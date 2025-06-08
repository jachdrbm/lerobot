#!/usr/bin/env python3
"""
Simple Motor Test Script for LeRobot

This script provides a simple way to test your robot arm motors without a leader arm.
It uses the existing LeRobot ManipulatorRobot infrastructure.

Usage:
    python simple_motor_test.py [robot_type] [port]
    
Examples:
    python simple_motor_test.py so100 /dev/ttyACM0
    python simple_motor_test.py moss COM3
    python simple_motor_test.py lekiwi /dev/ttyUSB0
"""

import sys
import time
import numpy as np
from pathlib import Path

# Add the lerobot path
sys.path.append(str(Path(__file__).parent))

from lerobot.common.robot_devices.robots.manipulator import ManipulatorRobot
from lerobot.common.robot_devices.robots.configs import (
    So100RobotConfig, 
    MossRobotConfig, 
    LeKiwiRobotConfig,
    FeetechMotorsBusConfig
)


def create_robot_config(robot_type, port):
    """Create a robot configuration with only follower arm (no leader)."""
    
    # Common motor configuration for Feetech-based robots
    motors_config = {
        "shoulder_pan": [1, "sts3215"],
        "shoulder_lift": [2, "sts3215"],
        "elbow_flex": [3, "sts3215"],
        "wrist_flex": [4, "sts3215"],
        "wrist_roll": [5, "sts3215"],
        "gripper": [6, "sts3215"],
    }
    
    follower_config = FeetechMotorsBusConfig(
        port=port,
        motors=motors_config
    )
    
    if robot_type.lower() == "so100":
        return So100RobotConfig(
            leader_arms={},  # No leader arm
            follower_arms={"main": follower_config},
            cameras={},  # No cameras for testing
        )
    elif robot_type.lower() == "moss":
        return MossRobotConfig(
            leader_arms={},  # No leader arm
            follower_arms={"main": follower_config},
            cameras={},  # No cameras for testing
        )
    elif robot_type.lower() == "lekiwi":
        # LeKiwi might have additional wheel motors
        motors_config.update({
            "left_wheel": [7, "sts3215"],
            "back_wheel": [8, "sts3215"],
            "right_wheel": [9, "sts3215"],
        })
        follower_config = FeetechMotorsBusConfig(
            port=port,
            motors=motors_config
        )
        return LeKiwiRobotConfig(
            leader_arms={},  # No leader arm
            follower_arms={"main": follower_config},
            cameras={},  # No cameras for testing
        )
    else:
        raise ValueError(f"Unsupported robot type: {robot_type}. Use 'so100', 'moss', or 'lekiwi'")


def test_individual_motors(robot):
    """Test each motor individually."""
    print("\n" + "="*50)
    print("INDIVIDUAL MOTOR TEST")
    print("="*50)
    
    follower_arm = robot.follower_arms["main"]
    motor_names = follower_arm.motor_names
    
    # Filter out wheel motors for arm testing
    arm_motors = [name for name in motor_names if not name.startswith(("left_", "back_", "right_"))]
    
    print(f"Testing {len(arm_motors)} arm motors: {arm_motors}")
    print("Each motor will move +30°, then -30°, then back to 0°")
    input("Press Enter to start individual motor test...")
    
    for motor_name in arm_motors:
        print(f"\nTesting {motor_name}...")
        
        # Read current position
        current_pos = follower_arm.read("Present_Position", motor_name)
        print(f"  Current position: {current_pos:.2f}°")
        
        # Move +30 degrees
        print("  Moving +30°...")
        follower_arm.write("Goal_Position", current_pos + 30, motor_name)
        time.sleep(2)
        
        # Move -30 degrees from original
        print("  Moving -30°...")
        follower_arm.write("Goal_Position", current_pos - 30, motor_name)
        time.sleep(2)
        
        # Return to original position
        print("  Returning to original position...")
        follower_arm.write("Goal_Position", current_pos, motor_name)
        time.sleep(2)
        
        print(f"  {motor_name} test complete!")


def test_coordinated_movement(robot):
    """Test coordinated movement of multiple motors."""
    print("\n" + "="*50)
    print("COORDINATED MOVEMENT TEST")
    print("="*50)
    
    follower_arm = robot.follower_arms["main"]
    
    # Read current positions
    current_positions = follower_arm.read("Present_Position")
    print(f"Current positions: {current_positions}")
    
    print("Testing coordinated movement...")
    input("Press Enter to start coordinated movement test...")
    
    # Move all motors by small amounts
    print("Moving all motors by +15°...")
    new_positions = current_positions + 15
    follower_arm.write("Goal_Position", new_positions)
    time.sleep(3)
    
    print("Moving all motors by -30°...")
    new_positions = current_positions - 15
    follower_arm.write("Goal_Position", new_positions)
    time.sleep(3)
    
    print("Returning to original positions...")
    follower_arm.write("Goal_Position", current_positions)
    time.sleep(3)
    
    print("Coordinated movement test complete!")


def interactive_control(robot):
    """Interactive control mode."""
    print("\n" + "="*50)
    print("INTERACTIVE CONTROL MODE")
    print("="*50)
    print("Commands:")
    print("  'read' or 'r'     - Read current positions")
    print("  'move <motor> <degrees>' - Move specific motor")
    print("  'zero <motor>'    - Move motor to 0°")
    print("  'zero all'        - Move all motors to 0°")
    print("  'list'            - List available motors")
    print("  'help' or 'h'     - Show this help")
    print("  'quit' or 'q'     - Exit")
    print("="*50)
    
    follower_arm = robot.follower_arms["main"]
    motor_names = follower_arm.motor_names
    
    # Filter out wheel motors for arm control
    arm_motors = [name for name in motor_names if not name.startswith(("left_", "back_", "right_"))]
    
    while True:
        try:
            cmd = input("\nControl > ").strip().lower()
            
            if cmd in ['quit', 'q']:
                break
                
            elif cmd in ['read', 'r']:
                positions = follower_arm.read("Present_Position")
                print("Current positions:")
                for name, pos in zip(motor_names, positions):
                    print(f"  {name}: {pos:.2f}°")
                    
            elif cmd == 'list':
                print("Available motors:")
                for i, name in enumerate(arm_motors):
                    print(f"  {i+1}. {name}")
                    
            elif cmd in ['help', 'h']:
                print("Commands:")
                print("  'read' - Read current positions")
                print("  'move <motor> <degrees>' - Move specific motor")
                print("  'zero <motor>' - Move motor to 0°")
                print("  'zero all' - Move all motors to 0°")
                print("  'list' - List available motors")
                print("  'quit' - Exit")
                
            elif cmd.startswith('move'):
                parts = cmd.split()
                if len(parts) >= 3:
                    motor_name = parts[1]
                    try:
                        degrees = float(parts[2])
                        if motor_name in arm_motors:
                            current_pos = follower_arm.read("Present_Position", motor_name)
                            new_pos = current_pos + degrees
                            follower_arm.write("Goal_Position", new_pos, motor_name)
                            print(f"Moving {motor_name} by {degrees}° (to {new_pos:.2f}°)")
                        else:
                            print(f"Unknown motor: {motor_name}")
                            print(f"Available motors: {arm_motors}")
                    except ValueError:
                        print("Invalid degrees value")
                else:
                    print("Usage: move <motor> <degrees>")
                    
            elif cmd.startswith('zero'):
                parts = cmd.split()
                if len(parts) >= 2:
                    if parts[1] == 'all':
                        print("Moving all motors to 0°...")
                        zero_positions = np.zeros(len(arm_motors))
                        follower_arm.write("Goal_Position", zero_positions, arm_motors)
                    else:
                        motor_name = parts[1]
                        if motor_name in arm_motors:
                            print(f"Moving {motor_name} to 0°...")
                            follower_arm.write("Goal_Position", 0.0, motor_name)
                        else:
                            print(f"Unknown motor: {motor_name}")
                else:
                    print("Usage: zero <motor> or zero all")
                    
            else:
                print("Unknown command. Type 'help' for available commands.")
                
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"Error: {e}")


def main():
    if len(sys.argv) < 2:
        print("Usage: python simple_motor_test.py <robot_type> [port]")
        print("Robot types: so100, moss, lekiwi")
        print("Example: python simple_motor_test.py so100 /dev/ttyACM0")
        sys.exit(1)
    
    robot_type = sys.argv[1]
    port = sys.argv[2] if len(sys.argv) > 2 else "/dev/ttyACM0"
    
    print("Simple Motor Test Script")
    print("=" * 40)
    print(f"Robot type: {robot_type}")
    print(f"Port: {port}")
    print("=" * 40)
    
    try:
        # Create robot configuration
        config = create_robot_config(robot_type, port)
        robot = ManipulatorRobot(config)
        
        print("Connecting to robot...")
        robot.connect()
        print("Robot connected successfully!")
        
        # Show menu
        while True:
            print("\n" + "="*40)
            print("MOTOR TEST MENU")
            print("="*40)
            print("1. Test individual motors")
            print("2. Test coordinated movement")
            print("3. Interactive control")
            print("4. Read current positions")
            print("5. Quit")
            print("="*40)
            
            choice = input("Select option (1-5): ").strip()
            
            if choice == '1':
                test_individual_motors(robot)
            elif choice == '2':
                test_coordinated_movement(robot)
            elif choice == '3':
                interactive_control(robot)
            elif choice == '4':
                follower_arm = robot.follower_arms["main"]
                positions = follower_arm.read("Present_Position")
                motor_names = follower_arm.motor_names
                print("\nCurrent positions:")
                for name, pos in zip(motor_names, positions):
                    print(f"  {name}: {pos:.2f}°")
            elif choice == '5':
                break
            else:
                print("Invalid choice. Please select 1-5.")
        
    except Exception as e:
        print(f"Error: {e}")
        print("\nTroubleshooting:")
        print("1. Make sure your robot is connected to the correct port")
        print("2. Check that you have permission to access the serial port")
        print("3. Ensure your robot is calibrated")
        print("4. Verify no other programs are using the serial port")
        print("5. Check that the robot type matches your hardware")
        
    finally:
        try:
            robot.disconnect()
            print("Robot disconnected safely.")
        except:
            pass


if __name__ == "__main__":
    main() 