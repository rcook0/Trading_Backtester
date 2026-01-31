import pandas as pd
import numpy as np

class MeanReversionOnPriceChanges:
    def __init__(self, df, window=100, k=2.0):
        self.df = df
        self.window = window
        self.k = k

    def run(self):
        df = self.df.copy()
        df["delta"] = df["Close"].diff()
        df["mu"] = df["delta"].rolling(self.window).mean()
        df["sd"] = df["delta"].rolling(self.window).std()
        trades = []
        for i in range(self.window, len(df)):
            d = df["delta"].iloc[i]
            mu = df["mu"].iloc[i]
            sd = df["sd"].iloc[i]
            if pd.isna(sd) or sd == 0:
                continue
            z = (d - mu) / sd
            price = df["Close"].iloc[i]
            if z <= -self.k:
                trades.append((df["Date"].iloc[i], "LONG", price))
            elif z >= self.k:
                trades.append((df["Date"].iloc[i], "SHORT", price))
        return trades
