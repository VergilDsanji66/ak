# ak

## Overview

This repository ("ak") contains a small collection of tools and example code focused on water-level monitoring and alerting. The primary purpose is to detect water levels from configured inputs and notify users via SMS and USSD.

## Key Features

* Water-level detection and monitoring pipeline (sensor or data feed ingestion)
* SMS notifications using the Africa's Talking API (implementation lives in sms.py)
* USSD handling to provide interactive options and send different messages based on user selection
* Lightweight utilities and example scripts for preprocessing and analysis

## Suggested Repository Layout

- src/                — core source code (Python, optional C/C++)
- scripts/            — utility scripts and helpers
- data/               — sample input data and metadata
- notebooks/          — exploratory Jupyter notebooks
- tests/              — unit and integration tests
- docs/               — documentation and examples

## Prerequisites

* Python 3.8+  
* pip / virtualenv  
* Node.js + npm (optional, only if you add web visualizations)

## Installation

1. Clone the repository

```bash
git clone https://github.com/VergilDsanji66/ak.git
cd ak
```

2. Python dependencies (recommended inside a virtualenv)

```bash
python3 -m venv venv
source venv/bin/activate  # On Linux/macOS
# venv\Scripts\activate  # On Windows (PowerShell use: .\venv\Scripts\Activate.ps1)
pip install -r requirements.txt
```

## Configuration

Create a .env or other config file with your Africa's Talking credentials and any USSD gateway settings if used. Example variables:

```
AFRICASTALKING_USERNAME=your_username
AFRICASTALKING_APIKEY=your_api_key
USSD_GATEWAY_URL=https://example.com/ussd
```

Ensure sms.py reads these credentials from environment variables or a config file before running.

## Usage

- Run the main application (starts detection and notification handlers):

```bash
py main.py
```

or

```bash
python main.py
```

Behavior summary:
- The application monitors configured water-level inputs (sensors or feeds).
- When thresholds/conditions are met, sms.py sends SMS alerts to subscribed users using Africa's Talking.
- USSD interactions are retrieved and parsed to send different messages based on the user's chosen option.

## Testing

To run a local test of detection and notification flows, run:

```bash
py main.py
```

This will exercise the detection pipeline and the SMS/USSD notification handlers (use test credentials or mocks in development).

## Contributing

Contributions welcome:

1. Fork the repository.  
2. Create a feature branch.  
3. Add tests for new behavior.  
4. Submit a pull request with a clear description.

## License

Add a LICENSE file (e.g., MIT) to specify the project license.

## Contact

Maintainer: @VergilDsanji66
