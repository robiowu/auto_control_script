## ADDED Requirements

### Requirement: Registry key operations
The system SHALL provide functions to read, enumerate, and check existence of Windows registry keys and values.

#### Scenario: Open registry key
- **WHEN** `OpenFullPathReg()` is called with a full registry path (e.g., `HKEY_LOCAL_MACHINE\SOFTWARE\...`)
- **THEN** the system parses the root key, extracts the subkey path, and returns the opened registry key handle

#### Scenario: Invalid registry path
- **WHEN** an unrecognized root key is provided
- **THEN** the system prints an error and returns None

#### Scenario: Check key existence
- **WHEN** `IsKeyExist()` is called for an existing key
- **THEN** the system returns True, and the key handle is properly closed

#### Scenario: Get registry value
- **WHEN** `GetRegValue()` is called with a valid key path and value name
- **THEN** the system returns the value data

#### Scenario: Enumerate subkeys
- **WHEN** `GetSubKeys()` is called
- **THEN** the system returns a list of subkey name strings

#### Scenario: Enumerate values
- **WHEN** `GetValues()` is called
- **THEN** the system returns a list of `(name, value, type)` tuples

#### Scenario: Check value existence
- **WHEN** `IsValueExist()` is called with a value name
- **THEN** the system returns True if the value exists, False otherwise

#### Scenario: Set DWORD value
- **WHEN** `SetValue()` is called with a value name and integer value
- **THEN** the system sets the registry value as REG_DWORD type

### Requirement: Registry file import
The system SHALL import a `.reg` file into the Windows registry silently.

#### Scenario: Import valid reg file
- **WHEN** a valid `.reg` file path is provided to `ImportRegistry()`
- **THEN** `regedit /s <path>` is executed and returns True on success

#### Scenario: Import non-existent file
- **WHEN** the provided path is not a file
- **THEN** the system returns False with an error message

### Requirement: File operations
The system SHALL provide file copy, move, and delete operations.

#### Scenario: Copy file
- **WHEN** `copy(source, destination)` is called
- **THEN** `shutil.copyfile()` copies the file from source to destination

#### Scenario: Move file
- **WHEN** `move(source, destination)` is called
- **THEN** `shutil.move()` moves the file from source to destination

#### Scenario: Remove existing file
- **WHEN** `remove_file(path)` is called for an existing file
- **THEN** the file is deleted from the filesystem

#### Scenario: Remove non-existent file
- **WHEN** `remove_file(path)` is called for a non-existent file
- **THEN** an error message is printed and no exception is raised

#### Scenario: Remove folder
- **WHEN** `remove_folder(path)` is called for an existing directory
- **THEN** the directory and all its contents are removed via `shutil.rmtree()`

### Requirement: Command execution
The system SHALL execute shell commands synchronously or asynchronously.

#### Scenario: Blocking command execution
- **WHEN** `cmd_block(cmd_str)` is called
- **THEN** the command runs synchronously via `os.popen().read()`

#### Scenario: Asynchronous command execution
- **WHEN** `cmd_asyn(cmd_str)` is called
- **THEN** the command runs asynchronously via `subprocess.Popen`

### Requirement: AppData path retrieval
The system SHALL return the current user's AppData/Roaming directory path.

#### Scenario: Get AppData path
- **WHEN** `get_abs_appdata_path()` is called
- **THEN** the system returns the value of the `APPDATA` environment variable as an absolute path
