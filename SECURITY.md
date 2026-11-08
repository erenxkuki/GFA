# Security Policy

GFA stores credentials in an encrypted local file (Fernet) and optionally the OS keyring.
API keys are never written to the main config file or logs.

Adapters run as separate processes with declared permissions; community code is never auto-executed.

Please report vulnerabilities privately to the maintainers. Do not open public issues for security bugs.