# tsimsim — Trading Simulator

A browser-based options trading simulator built with Flask. Practice pricing options using Black-Scholes, make markets, and sharpen your intuition for Greeks and volatility.

## Features

- Real-time options board with randomly generated scenarios
- Black-Scholes pricing engine (calls & puts)
- Delta calculation and display
- Interactive market-making — submit bids and offers, get filled by a simulated market
- P&L tracking across rounds
- Text-to-speech trade announcements (Windows)

## Requirements

- Python 3.8+
- Windows (for the TTS component via `pyttsx3` / `pywin32`)

## Setup

```bash
# Clone the repo
git clone https://github.com/<your-username>/tsimsim.git
cd tsimsim

# Create and activate a virtual environment
python -m venv venv
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the app
python app.py
```

Then open your browser to `http://127.0.0.1:5000`.

## Project Structure

```
tsimsim/
├── app.py              # Flask app and simulation logic
├── templates/
│   └── index.html      # Main UI
├── static/
│   └── style.css       # Styles
└── requirements.txt
```

## License

MIT
