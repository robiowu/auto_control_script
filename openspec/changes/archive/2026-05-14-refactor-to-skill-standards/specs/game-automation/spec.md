## ADDED Requirements

### Requirement: Feature image definition
The system SHALL allow defining a feature image with its position, click area, randomness, and matching parameters.

#### Scenario: Define feature with all parameters
- **WHEN** a `FeaturePic` is created with `sizetuple`, `path`, `clicktuple`, `randomtuple`, and `msg`
- **THEN** the instance stores all parameters for later feature detection

#### Scenario: Default randomness from feature size
- **WHEN** `randomtuple` is None
- **THEN** the randomness defaults to the feature image's own width and height

#### Scenario: Custom matching threshold
- **WHEN** `threshold` is provided in kwargs
- **THEN** the feature uses the custom threshold instead of the default 0.95

#### Scenario: Grayscale mode toggle
- **WHEN** `is_gray` is provided in kwargs
- **THEN** the feature uses the specified value; otherwise defaults to True

### Requirement: Feature proportion calculation
The system SHALL calculate a feature image's proportional position within a larger source image.

#### Scenario: Calculate proportional coordinates
- **WHEN** `get_sizetuple()` is called with a source image and feature image
- **THEN** the system returns `[left_ratio, top_ratio, right_ratio, bottom_ratio]` rounded to the specified precision

#### Scenario: Feature not found in source
- **WHEN** the feature image cannot be located in the source image
- **THEN** the system returns None

### Requirement: Feature detection in resized window
The system SHALL detect feature images within a window screenshot, resized to a baseline resolution for consistent matching.

#### Scenario: Detect feature in window
- **WHEN** `find_feature()` is called with a sub-image path and optional crop tuple
- **THEN** the window screenshot is captured, resized to `base_size`, and template matching is performed

#### Scenario: Feature found with adjusted coordinates
- **WHEN** a match is found within a cropped region
- **THEN** the returned coordinates are offset by the crop region's top-left position

#### Scenario: Full-image template trimming
- **WHEN** the sub-image has the same dimensions as `base_size`
- **THEN** the sub-image is cropped according to the subsize tuple before matching

### Requirement: Feature check with click info
The system SHALL check a `FeaturePic` for presence and calculate click target coordinates with randomness.

#### Scenario: Feature found
- **WHEN** `check_feature()` finds the feature image in the window
- **THEN** the result dict contains `result: True`, `intx`, `inty`, `threshold`, `point_x`, `point_y`, `random_x`, `random_y`

#### Scenario: Feature not found
- **WHEN** `check_feature()` does not find the feature image
- **THEN** the result dict contains `result: False` and coordinates are -1

### Requirement: Game automation base class
The system SHALL provide a base class `MyGameCase` that initializes window capture, logging, and DPI settings for game scripting.

#### Scenario: Initialize game case
- **WHEN** a `MyGameCase` is created with a window handle, game name, base size, and DPI multiplier
- **THEN** the system initializes a `Window` handler, `FindPictureHelper`, and logger with the specified game name

#### Scenario: Log directory auto-creation
- **WHEN** the log directory for the game does not exist
- **THEN** the system creates it under `%APPDATA%/ScriptElf/<game_name>/`

### Requirement: Window management
The system SHALL provide window control operations: show, hide, set topmost, resize, and highlight.

#### Scenario: Set window topmost
- **WHEN** `setTop()` is called
- **THEN** the window is positioned at `HWND_TOPMOST` without changing its position or size

#### Scenario: Resize window
- **WHEN** `resize(width, height)` is called
- **THEN** the window's size changes to the specified dimensions while maintaining its current position

#### Scenario: Simulate click with randomness
- **WHEN** `randomClick(point_x, point_y, random_x, random_y)` is called
- **THEN** the system clicks at `point_x + random(0, random_x)`, `point_y + random(0, random_y)`

#### Scenario: Full mock click
- **WHEN** `randomClick()` is called with `full_mock=True`
- **THEN** the system moves the mouse cursor to the screen position and uses pyautogui to click
