#!/usr/bin/env python3
"""
Manual Robot Arm Control Script

This script allows you to manually control your robot arm follower using keyboard input.
No leader arm is required - you can test individual motors and move the arm to different positions.

Controls:
- 1-6: Select motor (shoulder_pan, shoulder_lift, elbow_flex, wrist_flex, wrist_roll, gripper)
- +/-: Increase/decrease selected motor position by small steps
- Shift + +/-: Increase/decrease by larger steps
- 0: Move selected motor to zero position
- r: Read and display current positions
- h: Show help
- q: Quit

Make sure your robot is calibrated before running this script.
"""

import sys
import time
from pathlib import Path

try:
    import keyboard
    KEYBOARD_AVAILABLE = True
except ImportError:
    print("Warning: 'keyboard' library not available. Install with: pip install keyboard")
    KEYBOARD_AVAILABLE = False

import numpy as np

# Add the lerobot path
sys.path.append(str(Path(__file__).parent))

from lerobot.common.robot_devices.motors.feetech import FeetechMotorsBus, TorqueMode
from lerobot.common.robot_devices.robots.configs import FeetechMotorsBusConfig


class ManualArmController:
    def __init__(self, port="/dev/ttyACM0"):
        """
        Initialize the manual arm controller.
        
        Args:
            port: Serial port for the robot arm (adjust for your system)
        """
        # Motor configuration - adjust port and motor IDs as needed
        self.motor_config = FeetechMotorsBusConfig(
            port=port,
            motors={
                "shoulder_pan": [1, "sts3215"],
                "shoulder_lift": [2, "sts3215"], 
                "elbow_flex": [3, "sts3215"],
                "wrist_flex": [4, "sts3215"],
                "wrist_roll": [5, "sts3215"],
                "gripper": [6, "sts3215"],
            },
        )
        
        self.motor_bus = FeetechMotorsBus(self.motor_config)
        self.motor_names = list(self.motor_config.motors.keys())
        self.selected_motor_idx = 0
        self.small_step = 10  # degrees
        self.large_step = 30  # degrees
        
        # Speed and smoothness settings
        self.movement_speed = 50  # degrees per second (adjustable)
        self.interpolation_steps = 20  # number of intermediate steps for smooth motion
        self.step_delay = 0.05  # seconds between interpolation steps
        
        print(f"Initializing manual arm controller on port {port}")
        print(f"Motors: {self.motor_names}")
        print(f"Movement speed: {self.movement_speed}°/s, Interpolation steps: {self.interpolation_steps}")
        
    def connect(self):
        """Connect to the robot arm."""
        print("Connecting to robot arm...")
        self.motor_bus.connect()
        
        # Enable torque on all motors
        print("Enabling torque on all motors...")
        self.motor_bus.write("Torque_Enable", TorqueMode.ENABLED.value)
        
        # Read initial positions
        self.read_positions()
        print("Robot arm connected successfully!")
        
    def disconnect(self):
        """Safely disconnect from the robot arm."""
        print("Disabling torque and disconnecting...")
        try:
            self.motor_bus.write("Torque_Enable", TorqueMode.DISABLED.value)
            self.motor_bus.disconnect()
        except:
            pass
        print("Disconnected.")
        
    def read_positions(self):
        """Read and display current motor positions."""
        try:
            positions = self.motor_bus.read("Present_Position")
            print("\nCurrent positions (raw values):")
            for i, (name, pos) in enumerate(zip(self.motor_names, positions)):
                # Convert to float if needed
                if hasattr(pos, '__len__') and len(pos) == 1:
                    pos = float(pos[0])
                else:
                    pos = float(pos)
                marker = " <--" if i == self.selected_motor_idx else ""
                print(f"  {i+1}. {name:12}: {pos:8.0f}{marker}")
            print()
        except Exception as e:
            print(f"Error reading positions: {e}")
            
    def move_motor(self, motor_name, delta_degrees):
        """Move a specific motor by a delta amount."""
        try:
            current_pos = self.motor_bus.read("Present_Position", motor_name)
            # Ensure current_pos is a float/number, not an array
            if hasattr(current_pos, '__len__') and len(current_pos) == 1:
                current_pos = float(current_pos[0])
            else:
                current_pos = float(current_pos)
            
            new_pos = current_pos + float(delta_degrees)
            self.motor_bus.write("Goal_Position", new_pos, motor_name)
            print(f"Moving {motor_name} by {delta_degrees:+.1f}° (to {new_pos:.1f}°)")
        except Exception as e:
            print(f"Error moving motor {motor_name}: {e}")
            
    def move_motor_to_position(self, motor_name, position_degrees):
        """Move a specific motor to an absolute position."""
        try:
            position_degrees = float(position_degrees)
            self.motor_bus.write("Goal_Position", position_degrees, motor_name)
            print(f"Moving {motor_name} to {position_degrees:.1f}°")
        except Exception as e:
            print(f"Error moving motor {motor_name}: {e}")
            
    def show_help(self):
        """Display help information."""
        print("\n" + "="*50)
        print("MANUAL ARM CONTROL - HELP")
        print("="*50)
        print("Motor Selection:")
        print("  1-6    : Select motor (1=shoulder_pan, 2=shoulder_lift, etc.)")
        print("\nMovement:")
        print("  +/=    : Move selected motor +10°")
        print("  -      : Move selected motor -10°")
        print("  Shift++: Move selected motor +30°")
        print("  Shift+-: Move selected motor -30°")
        print("  0      : Move selected motor to 0°")
        print("\nInfo:")
        print("  r      : Read and display current positions")
        print("  h      : Show this help")
        print("  q/ESC  : Quit")
        print("\nCurrently selected motor:")
        print(f"  {self.selected_motor_idx + 1}. {self.motor_names[self.selected_motor_idx]}")
        print("="*50 + "\n")
        
    def run_keyboard_control(self):
        """Run the keyboard control loop."""
        if not KEYBOARD_AVAILABLE:
            print("Keyboard library not available. Falling back to text input mode.")
            self.run_text_control()
            return
            
        print("\nStarting keyboard control mode...")
        self.show_help()
        
        try:
            while True:
                event = keyboard.read_event()
                if event.event_type == keyboard.KEY_DOWN:
                    key = event.name
                    
                    # Motor selection (1-6)
                    if key in ['1', '2', '3', '4', '5', '6']:
                        self.selected_motor_idx = int(key) - 1
                        print(f"Selected motor: {self.motor_names[self.selected_motor_idx]}")
                        
                    # Movement controls
                    elif key in ['+', '=']:
                        motor_name = self.motor_names[self.selected_motor_idx]
                        step = self.large_step if keyboard.is_pressed('shift') else self.small_step
                        self.move_motor(motor_name, step)
                        
                    elif key == '-':
                        motor_name = self.motor_names[self.selected_motor_idx]
                        step = self.large_step if keyboard.is_pressed('shift') else self.small_step
                        self.move_motor(motor_name, -step)
                        
                    elif key == '0':
                        motor_name = self.motor_names[self.selected_motor_idx]
                        self.move_motor_to_position(motor_name, 0.0)
                        
                    # Info commands
                    elif key == 'r':
                        self.read_positions()
                        
                    elif key == 'h':
                        self.show_help()
                        
                    # Quit
                    elif key in ['q', 'esc']:
                        break
                        
        except KeyboardInterrupt:
            pass
            
    def run_text_control(self):
        """Run a text-based control mode as fallback."""
        print("\nStarting text control mode...")
        print("Commands:")
        print("  motor_num +/- degrees     - Move single motor (e.g., '1 +10')")
        print("  'smooth motor_num +/- deg' - Move single motor smoothly (e.g., 'smooth 1 +10')")
        print("  'all +/- degrees'         - Move all motors by same amount")
        print("  'smooth all +/- degrees'  - Move all motors smoothly")
        print("  'move motor1:deg motor2:deg' - Move multiple motors (e.g., 'move 1:10 3:-20')")
        print("  'smooth move motor1:deg motor2:deg' - Move multiple motors smoothly")
        print("  'speed value'             - Set movement speed in degrees/sec (e.g., 'speed 30')")
        print("  'zero motor_num'          - Move motor to zero (e.g., 'zero 1')")
        print("  'zero all'                - Move all motors to zero")
        print("  'r' to read, 'h' for help, 'q' to quit")
        print("Examples:")
        print("  '1 +10'           - Move shoulder_pan by +10 (instant)")
        print("  'smooth 1 +10'    - Move shoulder_pan by +10 (smooth)")
        print("  'all +5'          - Move all motors by +5 (instant)")
        print("  'smooth all +5'   - Move all motors by +5 (smooth)")
        print("  'move 1:20 2:-10' - Move shoulder_pan +20, shoulder_lift -10 (instant)")
        print("  'smooth move 1:20 2:-10' - Same but smooth")
        print("  'speed 30'        - Set movement speed to 30°/s")
        
        while True:
            try:
                cmd = input(f"\nSpeed: {self.movement_speed}°/s | Selected: {self.motor_names[self.selected_motor_idx]} > ").strip().lower()
                
                if cmd == 'q':
                    break
                elif cmd == 'r':
                    self.read_positions()
                elif cmd == 'h':
                    self.show_help()
                    
                # Speed control
                elif cmd.startswith('speed '):
                    try:
                        new_speed = float(cmd.split()[1])
                        if new_speed > 0:
                            self.movement_speed = new_speed
                            print(f"Movement speed set to {self.movement_speed}°/s")
                        else:
                            print("Speed must be positive")
                    except (ValueError, IndexError):
                        print("Usage: speed value (e.g., 'speed 30')")
                    
                # Smooth move all motors
                elif cmd.startswith('smooth all '):
                    try:
                        delta = float(cmd.split()[2])
                        motor_deltas = {name: float(delta) for name in self.motor_names}
                        self.move_multiple_motors_smooth(motor_deltas)
                    except (ValueError, IndexError):
                        print("Usage: smooth all +/-degrees (e.g., 'smooth all +10')")
                        
                # Move all motors by same amount (instant)
                elif cmd.startswith('all '):
                    try:
                        delta = float(cmd.split()[1])
                        self.move_all_motors(delta)
                    except (ValueError, IndexError):
                        print("Usage: all +/-degrees (e.g., 'all +10')")
                        
                # Zero all motors
                elif cmd == 'zero all':
                    self.zero_all_motors()
                        
                # Zero single motor
                elif cmd.startswith('zero '):
                    try:
                        motor_num = int(cmd.split()[1]) - 1
                        if 0 <= motor_num < len(self.motor_names):
                            motor_name = self.motor_names[motor_num]
                            self.move_motor_to_position(motor_name, 0.0)
                        else:
                            print(f"Invalid motor number. Use 1-{len(self.motor_names)}")
                    except (ValueError, IndexError):
                        print("Usage: zero motor_num (e.g., 'zero 1')")
                        
                # Smooth move multiple motors with different amounts
                elif cmd.startswith('smooth move '):
                    try:
                        parts = cmd.split()[2:]  # Remove 'smooth move'
                        motor_deltas = {}
                        for part in parts:
                            if ':' in part:
                                motor_str, delta_str = part.split(':')
                                motor_num = int(motor_str) - 1
                                delta = float(delta_str)
                                if 0 <= motor_num < len(self.motor_names):
                                    motor_deltas[self.motor_names[motor_num]] = delta
                                else:
                                    print(f"Invalid motor number: {motor_num + 1}")
                                    break
                        
                        if motor_deltas:
                            self.move_multiple_motors_smooth(motor_deltas)
                    except (ValueError, IndexError):
                        print("Usage: smooth move motor1:degrees motor2:degrees (e.g., 'smooth move 1:10 3:-20')")
                        
                # Move multiple motors with different amounts (instant)
                elif cmd.startswith('move '):
                    try:
                        parts = cmd.split()[1:]  # Remove 'move'
                        motor_deltas = {}
                        for part in parts:
                            if ':' in part:
                                motor_str, delta_str = part.split(':')
                                motor_num = int(motor_str) - 1
                                delta = float(delta_str)
                                if 0 <= motor_num < len(self.motor_names):
                                    motor_deltas[self.motor_names[motor_num]] = delta
                                else:
                                    print(f"Invalid motor number: {motor_num + 1}")
                                    break
                        
                        if motor_deltas:
                            self.move_multiple_motors(motor_deltas)
                    except (ValueError, IndexError):
                        print("Usage: move motor1:degrees motor2:degrees (e.g., 'move 1:10 3:-20')")
                        
                # Smooth single motor movement
                elif cmd.startswith('smooth ') and not cmd.startswith(('smooth all', 'smooth move')):
                    try:
                        parts = cmd.split()
                        if len(parts) >= 3:
                            motor_num = int(parts[1]) - 1
                            delta = float(parts[2])
                            if 0 <= motor_num < len(self.motor_names):
                                motor_name = self.motor_names[motor_num]
                                self.move_motor_smooth(motor_name, delta)
                            else:
                                print(f"Invalid motor number. Use 1-{len(self.motor_names)}")
                        else:
                            print("Usage: smooth motor_num +/-degrees (e.g., 'smooth 1 +10')")
                    except (ValueError, IndexError):
                        print("Usage: smooth motor_num +/-degrees (e.g., 'smooth 1 +10')")
                        
                # Single motor selection and movement (instant)
                elif cmd.startswith(('1', '2', '3', '4', '5', '6')):
                    parts = cmd.split()
                    if len(parts) >= 2:
                        motor_idx = int(parts[0]) - 1
                        if 0 <= motor_idx < len(self.motor_names):
                            motor_name = self.motor_names[motor_idx]
                            try:
                                delta = float(parts[1])
                                self.move_motor(motor_name, delta)
                            except ValueError:
                                print("Invalid number format")
                        else:
                            print("Invalid motor number")
                    else:
                        # Just select the motor
                        motor_idx = int(parts[0]) - 1
                        if 0 <= motor_idx < len(self.motor_names):
                            self.selected_motor_idx = motor_idx
                            print(f"Selected motor: {self.motor_names[self.selected_motor_idx]}")
                             
                # Move selected motor (instant)
                elif cmd.startswith(('+', '-')):
                    try:
                        delta = float(cmd)
                        motor_name = self.motor_names[self.selected_motor_idx]
                        self.move_motor(motor_name, delta)
                    except ValueError:
                        print("Invalid number format")
                else:
                    print("Unknown command. Type 'h' for help.")
                    
            except KeyboardInterrupt:
                break
            except EOFError:
                break

    def move_multiple_motors(self, motor_deltas):
        """
        Move multiple motors simultaneously.
        
        Args:
            motor_deltas: Dictionary of {motor_name: delta_degrees}
        """
        try:
            # Read current positions for all motors to be moved
            current_positions = {}
            for motor_name in motor_deltas.keys():
                current_pos = self.motor_bus.read("Present_Position", motor_name)
                if hasattr(current_pos, '__len__') and len(current_pos) == 1:
                    current_pos = float(current_pos[0])
                else:
                    current_pos = float(current_pos)
                current_positions[motor_name] = current_pos
            
            # Calculate new positions and ensure they're all floats
            new_positions = {}
            for motor_name, delta in motor_deltas.items():
                new_positions[motor_name] = float(current_positions[motor_name] + float(delta))
                
            # Write each motor position individually to avoid type issues
            print(f"Moving {len(motor_deltas)} motors simultaneously:")
            for motor_name, delta in motor_deltas.items():
                new_pos = new_positions[motor_name]
                self.motor_bus.write("Goal_Position", new_pos, motor_name)
                print(f"  {motor_name}: {delta:+.1f}° (to {new_pos:.1f}°)")
                
        except Exception as e:
            print(f"Error moving multiple motors: {e}")
            
    def move_all_motors(self, delta_degrees):
        """Move all motors by the same amount simultaneously."""
        motor_deltas = {name: float(delta_degrees) for name in self.motor_names}
        self.move_multiple_motors(motor_deltas)
        
    def zero_all_motors(self):
        """Move all motors to zero position simultaneously."""
        try:
            print("Moving all motors to zero position...")
            for motor_name in self.motor_names:
                self.motor_bus.write("Goal_Position", 0.0, motor_name)
                print(f"  {motor_name}: to 0.0°")
        except Exception as e:
            print(f"Error zeroing all motors: {e}")

    def move_motor_smooth(self, motor_name, delta_degrees):
        """Move a specific motor smoothly by interpolating the movement."""
        try:
            current_pos = self.motor_bus.read("Present_Position", motor_name)
            if hasattr(current_pos, '__len__') and len(current_pos) == 1:
                current_pos = float(current_pos[0])
            else:
                current_pos = float(current_pos)
            
            target_pos = current_pos + float(delta_degrees)
            
            # Calculate movement parameters
            total_distance = abs(delta_degrees)
            movement_time = total_distance / self.movement_speed
            actual_steps = max(1, int(movement_time / self.step_delay))
            
            print(f"Moving {motor_name} smoothly by {delta_degrees:+.1f}° (to {target_pos:.1f}°) in {actual_steps} steps")
            
            # Interpolate movement
            for i in range(actual_steps + 1):
                progress = i / actual_steps
                intermediate_pos = current_pos + (delta_degrees * progress)
                self.motor_bus.write("Goal_Position", float(intermediate_pos), motor_name)
                if i < actual_steps:  # Don't delay after the last step
                    time.sleep(self.step_delay)
                    
        except Exception as e:
            print(f"Error moving motor {motor_name} smoothly: {e}")
            
    def move_multiple_motors_smooth(self, motor_deltas):
        """
        Move multiple motors smoothly and simultaneously with interpolation.
        
        Args:
            motor_deltas: Dictionary of {motor_name: delta_degrees}
        """
        try:
            # Read current positions for all motors to be moved
            current_positions = {}
            for motor_name in motor_deltas.keys():
                current_pos = self.motor_bus.read("Present_Position", motor_name)
                if hasattr(current_pos, '__len__') and len(current_pos) == 1:
                    current_pos = float(current_pos[0])
                else:
                    current_pos = float(current_pos)
                current_positions[motor_name] = current_pos
            
            # Calculate target positions
            target_positions = {}
            max_distance = 0
            for motor_name, delta in motor_deltas.items():
                target_positions[motor_name] = float(current_positions[motor_name] + float(delta))
                max_distance = max(max_distance, abs(float(delta)))
            
            # Calculate movement parameters based on the largest movement
            movement_time = max_distance / self.movement_speed
            actual_steps = max(1, int(movement_time / self.step_delay))
            
            print(f"Moving {len(motor_deltas)} motors smoothly in {actual_steps} steps:")
            for motor_name, delta in motor_deltas.items():
                target_pos = target_positions[motor_name]
                print(f"  {motor_name}: {delta:+.1f}° (to {target_pos:.1f}°)")
            
            # Interpolate movement for all motors simultaneously
            for i in range(actual_steps + 1):
                progress = i / actual_steps
                for motor_name, delta in motor_deltas.items():
                    current_pos = current_positions[motor_name]
                    intermediate_pos = current_pos + (float(delta) * progress)
                    self.motor_bus.write("Goal_Position", float(intermediate_pos), motor_name)
                
                if i < actual_steps:  # Don't delay after the last step
                    time.sleep(self.step_delay)
                    
        except Exception as e:
            print(f"Error moving multiple motors smoothly: {e}")


def main():
    # You may need to adjust the port for your system
    # Common ports: "/dev/ttyACM0", "/dev/ttyUSB0" (Linux), "COM3", "COM4" (Windows)
    port = "/dev/ttyACM0"  # Adjust this for your system
    
    if len(sys.argv) > 1:
        port = sys.argv[1]
        
    print("Manual Robot Arm Controller")
    print("=" * 40)
    print(f"Using port: {port}")
    print("Make sure your robot arm is connected and calibrated!")
    print()
    
    controller = ManualArmController(port)
    
    try:
        controller.connect()
        
        # Choose control mode
        if KEYBOARD_AVAILABLE:
            print("Keyboard control available. Press 'h' for help.")
            controller.run_keyboard_control()
        else:
            controller.run_text_control()
            
    except Exception as e:
        print(f"Error: {e}")
        print("Make sure:")
        print("1. Your robot arm is connected to the correct port")
        print("2. You have the right permissions to access the serial port")
        print("3. Your robot arm is calibrated")
        print("4. No other programs are using the serial port")
        
    finally:
        controller.disconnect()


if __name__ == "__main__":
    main() 