# stock market simulator app using PySide6 and yfinance

import sys
import sqlite3
import yfinance as yf
import time
from PySide6.QtCore import Qt, QTimer, QDateTime
from PySide6.QtGui import QColor, QFont, QPainter
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QTableWidget, QTableWidgetItem, QMessageBox, QInputDialog, QComboBox, QSizePolicy,
    QSplitter, QScrollArea
)
import PySide6.QtCharts as QtCharts

DB_FILE = "portfolio.db"
UPDATE_INTERVAL_MS = 60_000  # 60 seconds
STARTING_CASH = 5000.0
MAX_WATCHLIST = 10

# --- DB setup ---
conn = sqlite3.connect(DB_FILE)
c = conn.cursor()
c.execute('''
CREATE TABLE IF NOT EXISTS watchlist (
    symbol TEXT PRIMARY KEY
)
''')
c.execute('''
CREATE TABLE IF NOT EXISTS portfolio (
    symbol TEXT PRIMARY KEY,
    shares INTEGER,
    avg_price REAL
)
''')
c.execute('''
CREATE TABLE IF NOT EXISTS account (
    cash REAL
)
''')
c.execute('SELECT cash FROM account')
if not c.fetchone():
    c.execute('INSERT INTO account (cash) VALUES (?)', (STARTING_CASH,))
conn.commit()


def get_cash():
    c.execute('SELECT cash FROM account')
    return c.fetchone()[0]


def set_cash(amount):
    c.execute('UPDATE account SET cash=?', (amount,))
    conn.commit()


# --- Timeframe mapping ---
TIMEFRAMES = {
    "1D": {"period": "1d", "interval": "5m"},
    "1W": {"period": "7d", "interval": "15m"},
    "1M": {"period": "1mo", "interval": "60m"},
    "6M": {"period": "6mo", "interval": "1d"},
    "1Y": {"period": "1y", "interval": "1d"},
}


class StockSimulator(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Stock Simulator")
        self.resize(1100, 700)
        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        # Price cache to reduce API calls
        self.price_cache = {}
        self.last_fetch_time = 0
        self.cache_duration = 300  # 5 minutes

        # Top: search / add
        top_layout = QHBoxLayout()
        self.input_symbol = QLineEdit()
        self.input_symbol.setPlaceholderText("Stock symbol (e.g. TSLA)")
        self.btn_add = QPushButton("Add / Search")
        self.btn_add.clicked.connect(self.add_stock)
        top_layout.addWidget(self.input_symbol)
        top_layout.addWidget(self.btn_add)
        self.layout.addLayout(top_layout)

        # Middle left: watchlist (table) and portfolio (table)

        left_col = QVBoxLayout()
        # Watchlist table
        self.watchlist_table = QTableWidget()
        self.watchlist_table.setColumnCount(5)
        self.watchlist_table.setHorizontalHeaderLabels(["Symbol", "Price", "Buy", "Sell", "Remove"])
        self.watchlist_table.horizontalHeader().setStretchLastSection(True)
        self.watchlist_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.watchlist_table.cellClicked.connect(self.on_watchlist_click)
        left_col.addWidget(QLabel("Watchlist (Max 10)"))
        left_col.addWidget(self.watchlist_table)

        # Portfolio table
        self.portfolio_table = QTableWidget()
        self.portfolio_table.setColumnCount(4)
        self.portfolio_table.setHorizontalHeaderLabels(["Symbol", "Shares", "Avg Price", "P/L"])
        self.portfolio_table.horizontalHeader().setStretchLastSection(True)
        left_col.addWidget(QLabel("Portfolio"))
        left_col.addWidget(self.portfolio_table)

        left_widget = QWidget()
        left_widget.setLayout(left_col)
        left_scroll = QScrollArea()
        left_scroll.setWidget(left_widget)
        left_scroll.setWidgetResizable(True)

        # Right column: chart + controls + cash
        right_col = QVBoxLayout()

        # Cash / totals
        self.cash_label = QLabel()
        font = QFont()
        font.setBold(True)
        font.setPointSize(12)
        self.cash_label.setFont(font)
        right_col.addWidget(self.cash_label)

        # Chart controls (buttons + combo)
        ctl_layout = QHBoxLayout()
        self.btn_1d = QPushButton("1D")
        self.btn_1w = QPushButton("1W")
        self.btn_1m = QPushButton("1M")
        self.btn_6m = QPushButton("6M")
        self.btn_1y = QPushButton("1Y")
        for btn in (self.btn_1d, self.btn_1w, self.btn_1m, self.btn_6m, self.btn_1y):
            btn.setCursor(Qt.PointingHandCursor)
            btn.setCheckable(True)
            btn.clicked.connect(self.on_timeframe_button)
            ctl_layout.addWidget(btn)

        ctl_layout.addStretch(1)
        self.combo_tf = QComboBox()
        self.combo_tf.addItems(list(TIMEFRAMES.keys()))
        self.combo_tf.currentTextChanged.connect(self.on_combo_change)
        ctl_layout.addWidget(QLabel(" | View:"))
        ctl_layout.addWidget(self.combo_tf)
        right_col.addLayout(ctl_layout)

        # Chart (QtCharts)
        self.chart = QtCharts.QChart()
        self.chart_view = QtCharts.QChartView(self.chart)
        self.chart_view.setRenderHint(QPainter.Antialiasing)
        right_col.addWidget(self.chart_view, 85)

        right_widget = QWidget()
        right_widget.setLayout(right_col)
        right_scroll = QScrollArea()
        right_scroll.setWidget(right_widget)
        right_scroll.setWidgetResizable(True)

        # Use QSplitter for adjustable panels
        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.addWidget(left_scroll)
        self.splitter.addWidget(right_scroll)
        self.splitter.setSizes([400, 600])  # Initial sizes
        self.layout.addWidget(self.splitter)

        # Style
        self.setStyleSheet("""
            QWidget { background: #fafafa; color: #111; font-family: Arial, Helvetica, sans-serif; }
            QLabel { font-size: 11pt; }
            QTableWidget { font-size: 10pt; }
            QPushButton { background-color: #1f6feb; color: white; padding: 6px 10px; border-radius: 6px; }
            QPushButton:checked { background-color: #0b59d6; }
            QPushButton:hover { background-color: #3590ff; }
            QComboBox { padding: 4px; }
        """)

        # state
        self.selected_symbol = None
        self.active_tf = "1D"
        self._set_timeframe_button("1D")  # default
        self.combo_tf.setCurrentText("1D")

        # Timer
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_prices)
        self.timer.start(UPDATE_INTERVAL_MS)

        # Load data
        self.load_watchlist()
        self.load_portfolio()
        self.update_cash_label()

    # ---------- Watchlist ----------
    def add_stock(self):
        symbol = self.input_symbol.text().upper().strip()
        if not symbol:
            return
        c.execute('SELECT COUNT(*) FROM watchlist')
        if c.fetchone()[0] >= MAX_WATCHLIST:
            QMessageBox.warning(self, "Limit Reached", f"Cannot watch more than {MAX_WATCHLIST} stocks.")
            return
        # validate via yfinance
        try:
            info = yf.Ticker(symbol).history(period="1d")
            if info.empty:
                raise ValueError("No data")
        except Exception:
            QMessageBox.warning(self, "Invalid Symbol", "Could not fetch data for this symbol.")
            return
        c.execute('INSERT OR IGNORE INTO watchlist (symbol) VALUES (?)', (symbol,))
        conn.commit()
        self.input_symbol.clear()
        self.load_watchlist()

    def remove_stock(self, symbol):
        c.execute('DELETE FROM watchlist WHERE symbol=?', (symbol,))
        conn.commit()
        if self.selected_symbol == symbol:
            self.selected_symbol = None
            self.chart.removeAllSeries()
        self.load_watchlist()

    def load_watchlist(self):
        c.execute('SELECT symbol FROM watchlist')
        rows = c.fetchall()
        self.watchlist_table.setRowCount(len(rows))
        for i, (symbol,) in enumerate(rows):
            self.watchlist_table.setItem(i, 0, QTableWidgetItem(symbol))
            price_item = QTableWidgetItem("Fetching...")
            price_item.setTextAlignment(Qt.AlignCenter)
            self.watchlist_table.setItem(i, 1, price_item)

            buy_btn = QPushButton("Buy")
            buy_btn.clicked.connect(lambda _, s=symbol: self.buy_dialog(s))
            self.watchlist_table.setCellWidget(i, 2, buy_btn)

            sell_btn = QPushButton("Sell")
            sell_btn.clicked.connect(lambda _, s=symbol: self.sell_dialog(s))
            self.watchlist_table.setCellWidget(i, 3, sell_btn)

            rm_btn = QPushButton("Remove")
            rm_btn.clicked.connect(lambda _, s=symbol: self.remove_stock(s))
            self.watchlist_table.setCellWidget(i, 4, rm_btn)

        self.update_prices()

    # ---------- Portfolio ----------
    def load_portfolio(self):
        c.execute('SELECT symbol, shares, avg_price FROM portfolio')
        rows = c.fetchall()
        self.portfolio_table.setRowCount(len(rows))
        for i, (symbol, shares, avg_price) in enumerate(rows):
            self.portfolio_table.setItem(i, 0, QTableWidgetItem(symbol))
            self.portfolio_table.setItem(i, 1, QTableWidgetItem(str(shares)))
            self.portfolio_table.setItem(i, 2, QTableWidgetItem(f"{avg_price:.2f}"))

            try:
                current_price = self.price_cache.get(symbol, 0)
                if current_price == 0:
                    # Fallback fetch if not cached
                    current_price = yf.Ticker(symbol).history(period="1d")['Close'].iloc[-1]
                    self.price_cache[symbol] = current_price
                pl = (current_price - avg_price) * shares
                pl_item = QTableWidgetItem(f"{pl:.2f}")
                if pl > 0:
                    pl_item.setForeground(QColor("green"))
                elif pl < 0:
                    pl_item.setForeground(QColor("red"))
                self.portfolio_table.setItem(i, 3, pl_item)
            except Exception:
                self.portfolio_table.setItem(i, 3, QTableWidgetItem("Error"))

    # ---------- Buy / Sell dialogs ----------
    def buy_dialog(self, symbol):
        cash = get_cash()
        try:
            price = yf.Ticker(symbol).history(period="1d")['Close'].iloc[-1]
        except Exception:
            QMessageBox.warning(self, "Fetch Error", "Could not fetch price for buy.")
            return
        max_shares = int(cash // price)
        if max_shares <= 0:
            QMessageBox.warning(self, "Insufficient Cash", "Not enough cash to buy shares.")
            return
        shares, ok = QInputDialog.getInt(self, "Buy Shares",
                                         f"Price: ${price:.2f}\nEnter shares to buy (max {max_shares}):",
                                         1, 1, max_shares)
        if ok:
            self.buy_stock(symbol, shares)

    def sell_dialog(self, symbol):
        c.execute('SELECT shares FROM portfolio WHERE symbol=?', (symbol,))
        row = c.fetchone()
        if not row:
            QMessageBox.information(self, "No Holdings", "You have no shares to sell for this symbol.")
            return
        owned = row[0]
        shares, ok = QInputDialog.getInt(self, "Sell Shares",
                                         f"Enter shares to sell (max {owned}):",
                                         1, 1, owned)
        if ok:
            self.sell_stock(symbol, shares)

    def buy_stock(self, symbol, shares_to_buy):
        cash = get_cash()
        try:
            price = yf.Ticker(symbol).history(period="1d")['Close'].iloc[-1]
        except Exception:
            QMessageBox.warning(self, "Fetch Error", "Could not fetch price for buy.")
            return
        total_cost = shares_to_buy * price
        if total_cost > cash + 1e-6:
            QMessageBox.warning(self, "Insufficient Cash", "Not enough cash.")
            return
        c.execute('SELECT shares, avg_price FROM portfolio WHERE symbol=?', (symbol,))
        row = c.fetchone()
        if row:
            old_shares, old_avg = row
            new_shares = old_shares + shares_to_buy
            new_avg = ((old_shares * old_avg) + (shares_to_buy * price)) / new_shares
            c.execute('UPDATE portfolio SET shares=?, avg_price=? WHERE symbol=?',
                      (new_shares, new_avg, symbol))
        else:
            c.execute('INSERT INTO portfolio (symbol, shares, avg_price) VALUES (?, ?, ?)',
                      (symbol, shares_to_buy, price))
        set_cash(cash - total_cost)
        conn.commit()
        self.load_portfolio()
        self.update_cash_label()
        self.plot_symbol(symbol)

    def sell_stock(self, symbol, shares_to_sell):
        c.execute('SELECT shares, avg_price FROM portfolio WHERE symbol=?', (symbol,))
        row = c.fetchone()
        if not row:
            return
        owned, avg_price = row
        if shares_to_sell > owned:
            return
        try:
            price = yf.Ticker(symbol).history(period="1d")['Close'].iloc[-1]
        except Exception:
            QMessageBox.warning(self, "Fetch Error", "Could not fetch price for sell.")
            return
        set_cash(get_cash() + shares_to_sell * price)
        if shares_to_sell == owned:
            c.execute('DELETE FROM portfolio WHERE symbol=?', (symbol,))
        else:
            c.execute('UPDATE portfolio SET shares=? WHERE symbol=?', (owned - shares_to_sell, symbol))
        conn.commit()
        self.load_portfolio()
        self.update_cash_label()
        self.plot_symbol(symbol)

    # ---------- Price updates ----------
    def update_prices(self):
        current_time = time.time()
        c.execute('SELECT symbol FROM watchlist')
        symbols = [r[0] for r in c.fetchall()]
        
        # Fetch prices if cache is stale
        if current_time - self.last_fetch_time > self.cache_duration:
            for symbol in symbols:
                try:
                    price = yf.Ticker(symbol).history(period="1d")['Close'].iloc[-1]
                    self.price_cache[symbol] = price
                except Exception:
                    self.price_cache[symbol] = None
            self.last_fetch_time = current_time
        
        # Update table with cached prices
        for i, symbol in enumerate(symbols):
            price = self.price_cache.get(symbol)
            if price is not None:
                item = QTableWidgetItem(f"{price:.2f}")
                item.setTextAlignment(Qt.AlignCenter)
                self.watchlist_table.setItem(i, 1, item)
            else:
                self.watchlist_table.setItem(i, 1, QTableWidgetItem("Error"))
        self.load_portfolio()
        self.update_cash_label()

    # ---------- Selection / plotting ----------
    def on_watchlist_click(self, row, column):
        item = self.watchlist_table.item(row, 0)
        if item:
            symbol = item.text()
            self.selected_symbol = symbol
            self.plot_symbol(symbol)

    def plot_symbol(self, symbol):
        # uses TIMEFRAMES[self.active_tf]
        if symbol is None:
            return
        tf = TIMEFRAMES.get(self.active_tf, TIMEFRAMES["1D"])
        try:
            df = yf.Ticker(symbol).history(period=tf["period"], interval=tf["interval"])
            if df.empty:
                raise ValueError("No data")
        except Exception:
            # clear chart and show message
            self.chart = QtCharts.QChart()
            self.chart_view.setChart(self.chart)
            return

        self.chart = QtCharts.QChart()
        self.chart_view.setChart(self.chart)
        series = QtCharts.QLineSeries()
        series.setName(symbol)

        # Add points (QDateTime axis expects msecs since epoch)
        for idx, row in df.iterrows():
            msecs = int(idx.to_pydatetime().timestamp() * 1000)
            price = float(row['Close'])
            series.append(msecs, price)

        pen = series.pen()
        pen.setWidth(2)
        series.setPen(pen)
        self.chart.addSeries(series)

        # Axes
        # X: datetime
        axis_x = QtCharts.QDateTimeAxis()
        axis_x.setFormat("MM-dd hh:mm" if self.active_tf in ("1D", "1W") else "MM-dd")
        axis_x.setTitleText("Date")
        # Set range
        first_dt = df.index[0].to_pydatetime()
        last_dt = df.index[-1].to_pydatetime()
        axis_x.setMin(QDateTime(first_dt))
        axis_x.setMax(QDateTime(last_dt))
        # Y: linear axis
        axis_y = QtCharts.QValueAxis()
        ymin = float(df['Close'].min())
        ymax = float(df['Close'].max())
        padding = (ymax - ymin) * 0.12 if ymax > ymin else ymin * 0.1 if ymin else 1.0
        axis_y.setRange(max(0.0, ymin - padding), ymax + padding)
        axis_y.setLabelFormat("%.2f")
        axis_y.setTitleText("Price ($)")

        self.chart.setTitle(f"{symbol} — {self.active_tf} view")
        self.chart.addAxis(axis_x, Qt.AlignBottom)
        self.chart.addAxis(axis_y, Qt.AlignLeft)
        series.attachAxis(axis_x)
        series.attachAxis(axis_y)
        self.chart.legend().setVisible(True)
        self.chart_view.repaint()

    # ---------- timeframe controls ----------
    def _set_timeframe_button(self, label):
        # uncheck all first
        for btn in (self.btn_1d, self.btn_1w, self.btn_1m, self.btn_6m, self.btn_1y):
            btn.setChecked(False)
        mapping = {"1D": self.btn_1d, "1W": self.btn_1w, "1M": self.btn_1m, "6M": self.btn_6m, "1Y": self.btn_1y}
        mapping[label].setChecked(True)
        self.active_tf = label
        self.combo_tf.setCurrentText(label)

    def on_timeframe_button(self):
        btn = self.sender()
        if not btn:
            return
        label = btn.text()
        self._set_timeframe_button(label)
        if self.selected_symbol:
            self.plot_symbol(self.selected_symbol)

    def on_combo_change(self, text):
        if text not in TIMEFRAMES:
            return
        self._set_timeframe_button(text)
        if self.selected_symbol:
            self.plot_symbol(self.selected_symbol)

    # ---------- totals ----------
    def update_cash_label(self):
        total_portfolio = 0.0
        c.execute('SELECT symbol, shares FROM portfolio')
        for symbol, shares in c.fetchall():
            price = self.price_cache.get(symbol, 0)
            if price > 0:
                total_portfolio += shares * price
        cash = get_cash()
        self.cash_label.setText(f"Cash: ${cash:.2f}   |   Portfolio Value: ${total_portfolio:.2f}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = StockSimulator()
    window.show()
    sys.exit(app.exec())
