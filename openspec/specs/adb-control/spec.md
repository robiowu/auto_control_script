## ADDED Requirements

### Requirement: Device connection
The system SHALL connect to an Android device via ADB using either a device ID (USB) or IP:port (wireless).

#### Scenario: Connect via device ID
- **WHEN** a device ID without colon is provided
- **THEN** `adb devices` is executed to verify the device is connected

#### Scenario: Connect via IP and port
- **WHEN** a device ID containing colon (IP:port format) is provided
- **THEN** `adb connect <ip:port>` is executed to establish a wireless connection

### Requirement: Screen capture via ADB
The system SHALL capture a screenshot from the connected Android device using ADB screencap command.

#### Scenario: Get PIL image
- **WHEN** `get_image()` is called
- **THEN** the system returns a PIL Image object of the device screen

#### Scenario: Get OpenCV numpy image
- **WHEN** `get_opencv_image()` is called
- **THEN** the system returns an RGB numpy array suitable for OpenCV processing

#### Scenario: Handle CRLF on Windows
- **WHEN** running on Windows (`os.name == 'nt'`)
- **THEN** the raw screencap bytes have `\r\n` replaced with `\n` before parsing

### Requirement: Touch input
The system SHALL simulate touch events on the device screen via ADB input tap.

#### Scenario: Click at coordinates
- **WHEN** `click(x, y)` is called with valid screen coordinates
- **THEN** the system executes `adb shell input tap <x> <y>` and returns the coordinates

### Requirement: Swipe gesture
The system SHALL simulate swipe gestures on the device screen via ADB input swipe.

#### Scenario: Perform swipe
- **WHEN** `scroll(x_begin, y_begin, x_end, y_end)` is called
- **THEN** the system executes `adb shell input swipe` with a 300ms duration

### Requirement: App lifecycle management
The system SHALL start and stop applications on the device via ADB.

#### Scenario: Launch app
- **WHEN** `__lunch__()` is called with valid `app_name` and `activity_name`
- **THEN** `adb shell am start -n <app_name>/<activity_name>` is executed

#### Scenario: Force stop app
- **WHEN** `__kill_app__()` is called
- **THEN** `adb shell am force-stop <app_name>` is executed and returns success/failure status

### Requirement: Device info retrieval
The system SHALL retrieve physical screen dimensions from the device.

#### Scenario: Get physical screen size
- **WHEN** `get_physical_size()` is called
- **THEN** the system parses `adb shell wm size` output and returns (width, height) as integers

### Requirement: App running status check
The system SHALL check whether a specified app is currently running on the device.

#### Scenario: App is running
- **WHEN** the app process is found via `adb shell ps | grep <app_name>`
- **THEN** the system returns True

#### Scenario: App is not running
- **WHEN** no process matches the app name
- **THEN** the system returns False
