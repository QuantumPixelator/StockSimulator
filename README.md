# Stock Simulator

A desktop application for simulating stock trading with real-time (delayed) data from Yahoo Finance. Built with PySide6 and Qt Charts for a professional UI.

## Features

- Watchlist management (up to 10 stocks)
- Portfolio simulation (buy/sell stocks)
- Real-time price updates with caching
- Interactive charts with multiple timeframes (1D, 1W, 1M, 6M, 1Y)
- SQLite database for persistence
- Adjustable UI panels with scroll bars

## Screenshots

![Stock Simulator Screenshot](screenshot.png)

## Installation

1. Clone or download the repository.
2. Install dependencies:
   ```
   pip install PySide6 yfinance
   ```
3. Run the application:
   ```
   python stocksim.py
   ```

## Usage

- Enter a stock symbol (e.g., TSLA) and click "Add / Search" to add to watchlist.
- Use the buttons to buy/sell stocks from the watchlist.
- Select timeframes to view charts.
- Prices update every 60 seconds (cached for 5 minutes to reduce API calls).

## Requirements

- Python 3.8+
- PySide6
- yfinance
- SQLite (built-in)

## License

# IDGAF License

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and its documentation files ("the Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software.

**THE SOFTWARE IS PROVIDED "AS IS," WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY OR FITNESS FOR A PARTICULAR PURPOSE.**

**IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES, OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.**

## Clear Conditions

### Zero Requirement
You are granted all permissions without any conditions. You do not need to retain, reproduce, or include any copyright notice or a copy of this license when you redistribute the Software.

### Total Waiver of Liability
By choosing to use, copy, or modify the Software in any way, you are agreeing to completely and permanently release the original author(s) from all liability. If anything goes wrong, you are entirely responsible.

---

**END**

## Contributing

Feel free to submit issues or pull requests.
