import os
os.environ['KMP_DUPLICATE_LIB_OK'] = 'TRUE'

from dataclasses import dataclass
import os
import sys
import time
try:
    import msvcrt  # Windows
    WINDOWS = True
except ImportError:
    import termios  # Unix/Linux
    import tty
    WINDOWS = False
import numpy as np

# For the control diagram popup
try:
    from PIL import Image, ImageDraw, ImageFont
    import tkinter as tk
    from tkinter import Label
    from PIL import ImageTk
    DIAGRAM_AVAILABLE = True
except ImportError:
    DIAGRAM_AVAILABLE = False

from lerobot.common.kinematics.kinematics import Robot, RobotKinematics
from lerobot.common.motors.feetech import FeetechMotorsBus as MotorBus, OperatingMode
from lerobot.common.motors import Motor, MotorNormMode

PORT = "COM4"  # Windows COM port
MOTOR_IDS = [1, 2, 3, 4, 5, 6]
# MOTOR_IDS = [1, 2, 3, 5, 4, 6] # Mine were installed w/ 4 & 5 swapped... :-/

MOTOR_MODEL = "sts3215"
MOTOR_MODELS = [MOTOR_MODEL] * len(MOTOR_IDS)
N_MOTORS = len(MOTOR_IDS)
BAUDRATE = 1_000_000
SCAN_IDS = list(range(1, 10)) # Motor IDs to check for; SO100 only has 6, but higher possible if misconfigured
PID_P, PID_I, PID_D = 16, 0, 32
ACCELERATION = 20 # HF is using 256

SEQUENCES = {
    "high_five": [ # [[position, wait_secs], ...]
        [[3006, 1285, 2284, 1458, 1029, 2370], 2.0],
        [[3006, 2227, 1397, 1458, 1029, 2370], 2.0],
    ],
}


@dataclass
class Joint:
    range_low: int # lowest servo position
    range_high: int # highest servo position
    resolution: int # n steps
    home: int # position when homed
    limit_low: int # lowest joint position; >= range_low
    limit_high: int # highest joint position; <= range_high


JOINTS = [
    #     l  h     res   home  lim_l lim_h
    Joint(0, 4096, 4096, 2100,  478, 3492), # shoulder pan (1) - extended ±45 degrees
    Joint(0, 4096, 4096, 1070, 1070, 3030), # shoulder lift (2)
    Joint(0, 4096, 4096, 2975, 1090, 3020), # elbow flex (3)

    Joint(0, 4096, 4096, 2500, 1060, 2790), # wrist flex (4)
    Joint(0, 4096, 4096, 3070,  590, 4000), # wrist roll (5) - corrected +180 degrees
    Joint(0, 4096, 4096, 2374, 1800, 3260), # gripper (6) - extended lower limit
]

HOME_POSITION = [x.home for x in JOINTS]
SHUTDOWN_SEQUENCE = [
    [2095, 1482, 2347, 1460, 3070, 2368], # safe upright pose - corrected axis 5
    HOME_POSITION,
]


def clamp(low, val, high):
    if val > high:
        return high
    if val < low:
        return low
    return val


def getch():
    if WINDOWS:
        return msvcrt.getch().decode('utf-8')
    else:
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(sys.stdin.fileno())
            ch = sys.stdin.read(1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        return ch


def announce_active():
    if WINDOWS:
        os.system('powershell -Command "Add-Type -AssemblyName System.Speech; (New-Object System.Speech.Synthesis.SpeechSynthesizer).Speak(\'Robot activated\')"')
    else:
        os.system('say -v "Zarvox" -r 200 "Robot... activated"')


def announce_shutdown():
    if WINDOWS:
        os.system('powershell -Command "Add-Type -AssemblyName System.Speech; (New-Object System.Speech.Synthesis.SpeechSynthesizer).Speak(\'Robot Shutting Down\')"')
    else:
        os.system('say -v "Zarvox" -r 200 "Robot... Shutting Down"')


def announce_fetch():
    if WINDOWS:
        os.system('powershell -Command "Add-Type -AssemblyName System.Speech; (New-Object System.Speech.Synthesis.SpeechSynthesizer).Speak(\'EV Time to play fetch\')"')
    else:
        os.system('say -v "Zarvox" -r 200 "EV... Time to play fetch"')


def create_control_diagram():
    """Create and display the robot arm control diagram in a popup window"""
    if not DIAGRAM_AVAILABLE:
        print("Control diagram popup not available. Install required packages: pip install pillow")
        return None
    
    # Create image
    width, height = 600, 800
    img = Image.new('RGB', (width, height), 'white')
    draw = ImageDraw.Draw(img)
    
    # Try to use a better font, fall back to default if not available
    try:
        title_font = ImageFont.truetype("arial.ttf", 28)
        header_font = ImageFont.truetype("arial.ttf", 18)
        text_font = ImageFont.truetype("arial.ttf", 16)
        key_font = ImageFont.truetype("consola.ttf", 18)
        small_font = ImageFont.truetype("consola.ttf", 12)
    except:
        title_font = ImageFont.load_default()
        header_font = ImageFont.load_default()
        text_font = ImageFont.load_default()
        key_font = ImageFont.load_default()
        small_font = ImageFont.load_default()
    
    # Colors
    bg_color = '#f0f0f0'
    border_color = '#333333'
    text_color = '#000000'
    key_color = '#0066cc'
    special_color = '#cc6600'
    
    # Title
    draw.text((width//2, 30), "SO100 ROBOT ARM CONTROLS", fill=text_color, font=title_font, anchor="mm")
    
    # Robot arm components (from top to bottom)
    y_start = 80
    box_height = 80
    box_width = 500
    x_center = width // 2
    
    components = [
        ("GRIPPER (Motor 6)", "U = Full Close | O = Full Open", '#ff9999'),
        ("WRIST ROLL (Motor 5)", "J = ↻ Rotate | L = ↺ Rotate", '#ffcc99'),
        ("WRIST FLEX (Motor 4)", "K = ↓ Down | I = ↑ Up", '#ffff99'),
        ("ELBOW FLEX (Motor 3)", "S = ↓ Down | W = ↑ Up", '#ccff99'),
        ("SHOULDER LIFT (Motor 2)", "Q = ↓ Down | E = ↑ Up", '#99ffcc', "(F/R)"),
        ("BASE PAN (Motor 1)", "A = ← Left | D = → Right", '#99ccff'),
    ]
    
    y_pos = y_start
    for i, component in enumerate(components):
        if len(component) == 4:  # Has alternative keys
            name, controls, color, alt_keys = component
        else:
            name, controls, color = component
            alt_keys = None
            
        # Draw component box
        box_left = x_center - box_width//2
        box_right = x_center + box_width//2
        box_top = y_pos
        box_bottom = y_pos + box_height
        
        # Fill box with color
        draw.rectangle([box_left, box_top, box_right, box_bottom], fill=color, outline=border_color, width=2)
        
        # Component name
        draw.text((x_center, y_pos + 20), name, fill=text_color, font=header_font, anchor="mm")
        
        # Main controls (bigger font)
        draw.text((x_center, y_pos + 45), controls, fill=key_color, font=key_font, anchor="mm")
        
        # Alternative keys (smaller font, if present)
        if alt_keys:
            draw.text((x_center, y_pos + 65), alt_keys, fill=key_color, font=small_font, anchor="mm")
        
        # Connection line to next component (except for last one)
        if i < len(components) - 1:
            line_start = (x_center, box_bottom)
            line_end = (x_center, box_bottom + 20)
            draw.line([line_start, line_end], fill=border_color, width=3)
            # Arrow
            draw.polygon([(x_center-5, box_bottom+15), (x_center+5, box_bottom+15), (x_center, box_bottom+20)], fill=border_color)
        
        y_pos += box_height + 20
    
    # Special commands section
    y_pos += 30
    draw.text((x_center, y_pos), "SPECIAL COMMANDS", fill=special_color, font=header_font, anchor="mm")
    y_pos += 30
    
    special_commands = [
        "H = Return to Home Position",
        "T = Toggle Torque On/Off", 
        "Q = Quit Manual Control (UPPERCASE!)"
    ]
    
    for cmd in special_commands:
        y_pos += 25
        draw.text((x_center, y_pos), cmd, fill=special_color, font=text_font, anchor="mm")
    
    return img


def show_control_diagram():
    """Save the control diagram as an image file"""
    if not DIAGRAM_AVAILABLE:
        print("Control diagram not available. Install Pillow: conda install pillow")
        return None
    
    img = create_control_diagram()
    if img is None:
        return None
    
    # Save the image to a file
    diagram_path = "robot_controls.png"
    img.save(diagram_path)
    print(f"Control diagram saved as: {diagram_path}")
    print("You can open it manually if needed for reference.")
    
    return diagram_path


def write_values(motor_bus, data_name, values, motor_ids):
    '''Write value_i to motor_i'''
    assert len(values) == len(motor_ids)
    # Create a dictionary mapping motor names to values
    motor_names = list(motor_bus.motors.keys())
    values_dict = {}
    for i, motor_id in enumerate(motor_ids):
        # Find motor name for this motor_id
        motor_name = None
        for name, motor in motor_bus.motors.items():
            if motor.id == motor_id:
                motor_name = name
                break
        if motor_name:
            values_dict[motor_name] = values[i]
    
    motor_bus.sync_write(data_name, values_dict, normalize=False)


def write_value(motor_bus, data_name, value):
    '''Write same value to all motors'''
    motor_bus.sync_write(data_name, value, normalize=False)


def read_value(motor_bus, data_name):
    '''Read value from ALL motors'''
    result = motor_bus.sync_read(data_name, normalize=False)
    # Convert from {motor_name: value} to list in motor_id order
    values = []
    for motor_id in MOTOR_IDS:
        motor_name = None
        for name, motor in motor_bus.motors.items():
            if motor.id == motor_id:
                motor_name = name
                break
        if motor_name and motor_name in result:
            values.append(result[motor_name])
        else:
            values.append(0)  # Default value if motor not found
    return values


def make_safe(position):
    '''Ensure joint positions are within limits'''
    assert len(position) == len(MOTOR_IDS)
    safe_pos = position[:]
    for motor_i in range(len(position)):
        joint_i = JOINTS[motor_i]
        safe_pos[motor_i] = clamp(joint_i.limit_low, position[motor_i], joint_i.limit_high)
    return safe_pos


def get_position(motor_bus) -> list[int]:
    '''Get position of all joints'''
    return read_value(motor_bus, "Present_Position")


def set_goal(motor_bus, position):
    '''Set goal state for motors
    Note that this can target unsafe position, use make_safe if safety required
    '''
    assert len(position) == len(MOTOR_IDS)
    write_values(motor_bus, data_name="Goal_Position", values=position, motor_ids=MOTOR_IDS)


def set_torque(motor_bus, enable=False):
    '''1 is on; 0 is off'''
    if enable:
        motor_bus.enable_torque()
    else:
        motor_bus.disable_torque()


def move_gripper_full(motor_bus, position, close=True):
    '''Move gripper to full open or close position smoothly'''
    gripper_motor_idx = 5  # Motor 6 is at index 5 in the position array
    gripper_joint = JOINTS[gripper_motor_idx]
    
    if close:
        target_pos = gripper_joint.limit_low  # 1800 - fully closed
        print("Closing gripper...")
    else:
        target_pos = gripper_joint.limit_high  # 3260 - fully open
        print("Opening gripper...")
    
    # Create new position with gripper at target
    new_position = position[:]
    new_position[gripper_motor_idx] = target_pos
    
    # Move to target position
    set_goal(motor_bus, make_safe(new_position))
    time.sleep(1.5)  # Half the speed of home sequence (3 seconds / 2)
    
    return new_position


def configure(motor_bus):
    '''Configure motor parameters'''
    motor_bus.disable_torque()
    motor_bus.configure_motors()
    for motor_name in motor_bus.motors:
        motor_bus.write("Operating_Mode", motor_name, OperatingMode.POSITION.value)

def prepare(motor_bus):
    '''Prepare bot for automated movement'''
    # Configure and enable torque
    configure(motor_bus)
    set_torque(motor_bus, enable=True)

    # Move to home position
    set_goal(motor_bus, HOME_POSITION)
    announce_active()
    print("Arm is ready for action!")


def shut_down(motor_bus):
    print("Shutting down...")
    announce_shutdown()

    # Safely move to home position
    for pos in SHUTDOWN_SEQUENCE:
        set_goal(motor_bus, make_safe(pos))
        time.sleep(3) # Wait until moved to goal XXX: Make fxn to await close enough

    # Turn off torque
    set_torque(motor_bus, enable=False)

    # Tell motor bus we're done
    motor_bus.disconnect()
    print("Motor bus disconnected")


def run_routine(motor_bus, name):
    prepare(motor_bus)
    info(motor_bus)
    if name not in SEQUENCES:
        raise KeyError(f"No sequence with name {name}")
    for position, wait_secs in SEQUENCES[name]:
        print("keyframe:", position)
        set_goal(motor_bus, make_safe(position))
        time.sleep(wait_secs)


def manual_control(motor_bus, start_position=None):
    if start_position is None:
        prepare(motor_bus)
        position = HOME_POSITION[:] # init to home
    else:
        position = start_position[:]
        print("Starting manual control from current position...")

    # Save and open control diagram
    diagram_file = show_control_diagram()
    
    # Simple console instructions
    print("\nManual Control Active")
    if diagram_file:
        print("Control diagram saved - open robot_controls.png if you need key reference")
    print("Press any key to start controlling the robot...")
    print("(Press 'Q' to quit, 'x' to switch to IK mode)")
    print()

    incr = 20 # amount moved each input loop
    torque_active = True # Starts w/ torque since prepare
    char_config = {
        # Shoulder/Arm
        'a': (1, -1), 'd': (1, +1),
        's': (3, +1), 'w': (3, -1),
        'q': (2, -1), 'e': (2, +1),
        'f': (2, -1), 'r': (2, +1), # same as q/e, for convenience

        # Wrist/Hand
        'j': (5, +1), 'l': (5, -1),
        'k': (4, +1), 'i': (4, -1),
        # Note: 'u' and 'o' for gripper are handled separately for full open/close
    }
    
    set_goal(motor_bus, make_safe(position))
    while True:
        char = getch()
        if char in char_config: # move w/ keyboard
            motor_id, direc = char_config[char]
            motor_idx = motor_id - 1
            position[motor_idx] = position[motor_idx] + direc*incr
            set_goal(motor_bus, make_safe(position))
        elif char == "u": # close gripper fully
            position = move_gripper_full(motor_bus, position, close=True)
        elif char == "o": # open gripper fully
            position = move_gripper_full(motor_bus, position, close=False)
        elif char == "h": # go to home position
            position = HOME_POSITION[:]
            set_goal(motor_bus, make_safe(position))
            print("Moving to home position...")
        elif char == "t": # toggle torque
            torque_active = not torque_active
            curr_position = get_position(motor_bus)
            position = curr_position
            set_torque(motor_bus, enable=torque_active)
        elif char == 'x':
            print("\nSwitching to IK control...")
            return ("ik", position)
        elif char == 'Q':
            break
        else:
            continue
        print(position, f"torque:{torque_active}")
    
    print("\nExiting manual control...")
    return ("quit", position)


def ik_control(motor_bus, robot, robot_kin, start_position=None):
    """Control the robot's end-effector position using inverse kinematics."""
    if start_position is None:
        prepare(motor_bus)
        current_servo_pos = HOME_POSITION[:]
    else:
        current_servo_pos = start_position[:]
        print("Starting IK control from current position...")

    print("\nInverse Kinematics Control Active")
    print("Controls:")
    print("  W/S: Move along +Z / -Z")
    print("  A/D: Move along -X / +X")
    print("  R/F: Move along +Y / -Y")
    print("\nPress 'M' to switch to manual mode, 'Q' to quit.")

    # Conversion helpers
    servo_limits_low = np.array([j.limit_low for j in JOINTS])
    servo_limits_high = np.array([j.limit_high for j in JOINTS])
    mech_limits_low = robot.mech_joint_limits_low
    mech_limits_high = robot.mech_joint_limits_up

    def servo_to_rad(servo_pos):
        servo_pos_np = np.array(servo_pos)
        rad_pos = mech_limits_low + (servo_pos_np - servo_limits_low) * (mech_limits_high - mech_limits_low) / (servo_limits_high - servo_limits_low)
        return rad_pos

    def rad_to_servo(rad_pos):
        rad_pos_np = np.array(rad_pos)
        servo_pos = servo_limits_low + (rad_pos_np - mech_limits_low) * (servo_limits_high - servo_limits_low) / (mech_limits_high - mech_limits_low)
        return servo_pos.astype(int).tolist()
    pos_delta = 0.01  # 1 cm

    while True:
        # FK to get current pose
        current_mech_rad = servo_to_rad(current_servo_pos)
        current_q_dh = robot.from_mech_to_dh(current_mech_rad)
        current_worldTtool = robot_kin.forward_kinematics(robot, current_q_dh)
        
        pos = current_worldTtool[:3, 3]
        print(f"\rEnd-Effector at: x={pos[0]:.3f}, y={pos[1]:.3f}, z={pos[2]:.3f}", end="")

        char = getch()

        if char == 'M':
            print("\nSwitching to manual control...")
            return ("manual", current_servo_pos)
        elif char == 'Q':
            print("\nExiting IK control...")
            return ("quit", current_servo_pos)

        desired_worldTtool = current_worldTtool.copy()
        
        moved = False
        if char == 'w':
            desired_worldTtool[2, 3] += pos_delta
            moved = True
        elif char == 's':
            desired_worldTtool[2, 3] -= pos_delta
            moved = True
        elif char == 'd':
            desired_worldTtool[0, 3] += pos_delta
            moved = True
        elif char == 'a':
            desired_worldTtool[0, 3] -= pos_delta
            moved = True
        elif char == 'r':
            desired_worldTtool[1, 3] += pos_delta
            moved = True
        elif char == 'f':
            desired_worldTtool[1, 3] -= pos_delta
            moved = True
        
        if not moved:
            continue

        try:
            next_q_dh = robot_kin.inverse_kinematics(robot, current_q_dh, desired_worldTtool, use_orientation=False)
            
            next_mech_rad_arm = robot.from_dh_to_mech(next_q_dh)
            
            # Keep gripper position unchanged
            gripper_rad = current_mech_rad[5]
            full_next_mech_rad = np.append(next_mech_rad_arm, gripper_rad)

            robot.check_joint_limits(full_next_mech_rad)

            next_servo_pos = rad_to_servo(full_next_mech_rad)
            
            set_goal(motor_bus, make_safe(next_servo_pos))
            
            current_servo_pos = next_servo_pos

        except Exception as e:
            # Flashing the error message would be better, but this is fine.
            print(f"\n[IK Error] Could not reach target: {e}")
            pass


def info(motor_bus):
    '''Display info about bus/joints'''
    baud_rate = motor_bus.port_handler.getBaudRate()
    motors_identified = list(motor_bus.motors.keys())  # Get configured motor names
    motor_ids = [motor_bus.motors[name].id for name in motors_identified]
    
    fields = [
        "Operating_Mode",
        "P_Coefficient",
        "I_Coefficient",
        "D_Coefficient",
        "Maximum_Acceleration",
        "Acceleration",
        "Torque_Enable",
        "Homing_Offset",
        "Present_Position",
        "Goal_Position",
    ]
    values = []
    for field in fields:
        try:
            values.append(read_value(motor_bus, field))
        except Exception as e:
            print(f"Warning: Could not read {field}: {e}")
            values.append([0] * len(MOTOR_IDS))

    print("\n[Bus Info]")
    fields = ["Bus Baud", "Motor Names", "Motor IDs"] + fields
    values = [baud_rate, motors_identified, motor_ids] + values
    for field, val in zip(fields, values):
        print(f"{field}:".ljust(30), val)
    print()


def monitor_position(motor_bus):
    print("\nPosition Monitoring")
    prev_positions = [0] * N_MOTORS
    while True:
        time.sleep(1)
        positions = get_position(motor_bus)
        positions_delta = [positions[i] - prev_positions[i] for i in range(N_MOTORS)]
        prev_positions = positions
        print(
            "[P]",
            " ".join([str(x).rjust(6) for x in positions]),
            "[Δ]".rjust(6),
            " ".join([str(x).rjust(6) for x in positions_delta]),
        )


def menu(choices):
    '''
    choices ~ (("Menu Option 1", lambda: do_something(...)), ...)
    '''
    # Get choice from user
    while True:
        print("\nWhat do you want to do?")
        for i, info in enumerate(choices):
            print(f"{i+1}. {info[0]}")
        choice = input(f"\nEnter your choice (1-{len(choices)}): ")
        if choice in [str(x) for x in range(1, len(choices) + 1)]:
            break

    # Run callback corresponding to choice
    choices[int(choice)-1][1]()


def seamless_manual_control(motor_bus, robot, robot_kin):
    """Manual control with seamless IK switching."""
    prepare(motor_bus)
    current_position = HOME_POSITION[:]
    
    while True:
        result = manual_control(motor_bus, current_position)
        if result[0] == "ik":
            current_position = result[1]
            ik_result = ik_control(motor_bus, robot, robot_kin, current_position)
            if ik_result[0] == "manual":
                current_position = ik_result[1]
                continue  # Back to manual control
            else:  # quit
                break
        else:  # quit
            break

def seamless_ik_control(motor_bus, robot, robot_kin):
    """IK control with seamless manual switching."""
    prepare(motor_bus)
    current_position = HOME_POSITION[:]
    
    while True:
        result = ik_control(motor_bus, robot, robot_kin, current_position)
        if result[0] == "manual":
            current_position = result[1]
            manual_result = manual_control(motor_bus, current_position)
            if manual_result[0] == "ik":
                current_position = manual_result[1]
                continue  # Back to IK control
            else:  # quit
                break
        else:  # quit
            break

def main_menu(motor_bus, robot, robot_kin):
    # Generate routine submenu choices
    routine_choices = []
    for seq_name in SEQUENCES:
        cback = lambda x=seq_name: run_routine(motor_bus, x) # noqa; x=seqname required to capture!
        routine_choices.append((seq_name, cback))

    # Main menu
    main_choices = (
        ("Manual control", lambda: seamless_manual_control(motor_bus, robot, robot_kin)),
        ("IK control", lambda: seamless_ik_control(motor_bus, robot, robot_kin)),
        ("Run routine", lambda: menu(routine_choices)),
        ("Monitor position", lambda: monitor_position(motor_bus)),
        ("Quit", lambda: print("Goodbye!")),
    )
    menu(main_choices)


if __name__ == "__main__":

    # Initialize the MotorBus
    # Create motors dictionary with proper motor IDs and models
    motors = {}
    for i, motor_id in enumerate(MOTOR_IDS):
        motors[f"motor_{motor_id}"] = Motor(motor_id, MOTOR_MODEL, MotorNormMode.RANGE_M100_100)
    
    motor_bus = MotorBus(
        port=PORT,
        motors=motors
    )
    motor_bus.connect()

    # Initialize kinematics
    robot = Robot(robot_type="so100")
    robot_kin = RobotKinematics()

    try:
        # Display info first
        info(motor_bus)

        # Choose/start task
        main_menu(motor_bus, robot, robot_kin)

    finally:
        shut_down(motor_bus)