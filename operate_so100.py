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

# For the control diagram popup
try:
    from PIL import Image, ImageDraw, ImageFont
    import tkinter as tk
    from tkinter import Label
    from PIL import ImageTk
    DIAGRAM_AVAILABLE = True
except ImportError:
    DIAGRAM_AVAILABLE = False

from lerobot.common.robot_devices.motors.feetech import FeetechMotorsBus as MotorBus
from lerobot.common.robot_devices.motors.configs import FeetechMotorsBusConfig

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
    motor_bus.write_with_motor_ids(
        motor_models=[MOTOR_MODEL] * len(values), # All same for this arm
        motor_ids=motor_ids,
        data_name=data_name,
        values=values,
    )


def write_value(motor_bus, data_name, value):
    '''Write same value to all motors'''
    write_values(
        motor_bus,
        data_name=data_name,
        values=[value] * len(MOTOR_IDS),
        motor_ids=MOTOR_IDS,
    )


def read_value(motor_bus, data_name):
    '''Read value from ALL motors'''
    return motor_bus.read_with_motor_ids(
        motor_models=MOTOR_MODELS,
        motor_ids=MOTOR_IDS,
        data_name=data_name,
    )


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
    write_value(motor_bus, data_name="Torque_Enable", value=1 if enable else 0)


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


def prepare(motor_bus):
    '''Prepare bot for automated movement'''
    # Disable torque -> configure motors -> enable torque
    set_torque(motor_bus, enable=False)
    for field, value in (
        ("Mode", 0), # Hold position mode (it's the default anyways)
        ("P_Coefficient", PID_P),
        ("I_Coefficient", PID_I),
        ("D_Coefficient", PID_D),
        ("Maximum_Acceleration", ACCELERATION), # XXX: Write lock needed?
        ("Acceleration", ACCELERATION),
    ):
        write_value(motor_bus, data_name=field, value=value)
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


def manual_control(motor_bus):
    prepare(motor_bus)

    # Save and open control diagram
    diagram_file = show_control_diagram()
    
    # Simple console instructions
    print("\nManual Control Active")
    if diagram_file:
        print("Control diagram saved - open robot_controls.png if you need key reference")
    print("Press any key to start controlling the robot...")
    print("(Press 'Q' uppercase to quit)")
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
    position = HOME_POSITION[:] # init to home
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
        elif char == 'Q':
            break
        else:
            continue
        print(position, f"torque:{torque_active}")
    
    print("\nExiting manual control...")


def info(motor_bus):
    '''Display info about bus/joints'''
    baud_rate = motor_bus.port_handler.getBaudRate()
    motors_identified = motor_bus.find_motor_indices(possible_ids=SCAN_IDS)
    fields = [
        "Mode",
        "P_Coefficient",
        "I_Coefficient",
        "D_Coefficient",
        "Maximum_Acceleration",
        "Acceleration",
        "Torque_Enable",
        "Offset",
        "Present_Position",
        "Goal_Position",
    ]
    values = []
    for field in fields:
        values.append(read_value(motor_bus, field))

    print("\n[Bus Info]")
    fields = ["Bus Baud", "Motor IDs Detected"] + fields
    values = [baud_rate, motors_identified] + values
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


def main_menu(motor_bus):
    # Generate routine submenu choices
    routine_choices = []
    for seq_name in SEQUENCES:
        cback = lambda x=seq_name: run_routine(motor_bus, x) # noqa; x=seqname required to capture!
        routine_choices.append((seq_name, cback))

    # Main menu
    main_choices = (
        ("Manual control", lambda: manual_control(motor_bus)),
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
        motors[f"motor_{motor_id}"] = (motor_id, MOTOR_MODEL)
    
    config = FeetechMotorsBusConfig(
        port=PORT,
        motors=motors
    )
    motor_bus = MotorBus(config)
    motor_bus.connect()

    try:
        # Display info first
        info(motor_bus)

        # Choose/start task
        main_menu(motor_bus)

    finally:
        shut_down(motor_bus)