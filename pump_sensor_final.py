import time
import board
import digitalio
import pulseio

# === PARAMETERS ===
THRESHOLD_DISTANCE_CM = 40
DETECTION_CYCLES = 15
PUMP_MAX_ON_TIME = 20      # seconds
PUMP_COOLDOWN_TIME = 4     # seconds
MEASUREMENT_DELAY = 0.2    # seconds

# === SETUP PUMP ===
pump = digitalio.DigitalInOut(board.GP13)
pump.direction = digitalio.Direction.OUTPUT
pump.value = False  # Ensure OFF initially

# === SENSOR PINS ===
sensor_pins = [
    {"trig": board.GP2, "echo": board.GP3},  # Sensor 1
    {"trig": board.GP4, "echo": board.GP5},  # Sensor 2
    {"trig": board.GP6, "echo": board.GP7},  # Sensor 3
]

# === SETUP SENSORS ===
for s in sensor_pins:
    trig = digitalio.DigitalInOut(s["trig"])
    trig.direction = digitalio.Direction.OUTPUT
    trig.value = False
    s["trigger"] = trig

    echo = pulseio.PulseIn(s["echo"], maxlen=1, idle_state=False)
    echo.pause()
    echo.clear()
    s["echo"] = echo
    s["detection_count"] = 0

# === STATE VARIABLES ===
pump_running = False
in_cooldown = False
pump_start_time = None
cooldown_start_time = None

# === DISTANCE MEASUREMENT FUNCTION ===
def measure_distance(trigger, echo):
    echo.clear()
    trigger.value = True
    time.sleep(0.00001)  # 10 µs pulse
    trigger.value = False

    echo.resume()
    timeout = time.monotonic() + 0.05  # 50ms max wait
    while not echo:
        if time.monotonic() > timeout:
            echo.pause()
            return None
    echo.pause()

    pulse = echo[0]
    distance_cm = (pulse * 0.0343) / 2
    return distance_cm

# === MAIN LOOP ===
while True:
    current_time = time.monotonic()
    object_detected = False
    distances = []

    # === Handle Cooldown ===
    if in_cooldown:
        if current_time - cooldown_start_time >= PUMP_COOLDOWN_TIME:
            in_cooldown = False
            for s in sensor_pins:
                s["detection_count"] = 0
        else:
            pump.value = False
            print((0, 0, 0, 0))  # Output placeholder
            time.sleep(MEASUREMENT_DELAY)
            continue

    # === Check Sensors ===
    for s in sensor_pins:
        d = measure_distance(s["trigger"], s["echo"])
        if d is None:
            d = 0
        distances.append(d)

        if 0 < d < THRESHOLD_DISTANCE_CM:
            s["detection_count"] += 1
        else:
            s["detection_count"] = 0

        if s["detection_count"] >= DETECTION_CYCLES:
            object_detected = True

    # === Pump Logic ===
    pump_state = 0
    if object_detected and not pump_running:
        pump_running = True
        pump_start_time = current_time
        pump.value = True
        pump_state = 1

    elif pump_running:
        elapsed = current_time - pump_start_time
        if not object_detected or elapsed >= PUMP_MAX_ON_TIME:
            pump_running = False
            pump.value = False
            in_cooldown = True
            cooldown_start_time = current_time
            pump_state = 0
        else:
            pump_state = 1  # Keep running

    else:
        pump.value = False  # Just in case

    # === Output to console/plotter ===
    distances.append(pump_state)
    print(tuple(distances))  # e.g., (123.4, 432.1, 0.0, 1)

    time.sleep(MEASUREMENT_DELAY)
