## ADDED Requirements

### Requirement: Window screenshot capture
The system SHALL capture a screenshot of a specified Windows window handle and return it as a numpy array for image processing.

#### Scenario: Capture active window screenshot
- **WHEN** a valid window handle is provided to `FindPictureHelper`
- **THEN** the system returns a numpy array representing the window's client area image in RGB format

#### Scenario: Capture with DPI scaling
- **WHEN** a non-default DPI scaling factor is provided
- **THEN** the captured image dimensions SHALL be adjusted by the scaling factor

### Requirement: Image file loading
The system SHALL load an image file from disk and return it as a numpy array in RGB format.

#### Scenario: Load valid image file
- **WHEN** a valid image file path is provided
- **THEN** the system returns a numpy array in RGB color space

#### Scenario: Load non-existent file
- **WHEN** an invalid or non-existent file path is provided
- **THEN** the system returns None

### Requirement: Template matching (find sub-image)
The system SHALL locate a smaller template image within a larger source image using OpenCV template matching, returning the matched position and confidence score.

#### Scenario: Template found with high confidence
- **WHEN** the template exists in the source image above the specified threshold
- **THEN** the system returns the top-left coordinates (x, y) and the confidence value

#### Scenario: Template not found
- **WHEN** no region in the source image exceeds the confidence threshold
- **THEN** the system returns (-1, -1) with the best-match confidence value

#### Scenario: Grayscale matching mode
- **WHEN** `is_gray=True` is specified
- **THEN** both source and template are converted to grayscale before matching for improved performance

#### Scenario: Search within sub-region
- **WHEN** `left`, `top`, `right`, `bottom` crop coordinates are specified
- **THEN** matching is performed only within the cropped region of the source image

### Requirement: Resource cleanup
The system SHALL release Windows GDI resources acquired during window capture to prevent memory leaks.

#### Scenario: Explicit resource release
- **WHEN** `release_resource()` is called on a `FindPictureHelper` instance
- **THEN** the GDI bitmap handle and device contexts are freed
