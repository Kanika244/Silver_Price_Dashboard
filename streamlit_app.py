import json
from pathlib import Path

import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt
import plotly.express as px

try:
	import geopandas as gpd
	from shapely.geometry import shape
except Exception:
	gpd = None

ROOT = Path(__file__).parent
DATA_DIR = ROOT / "data"

st.set_page_config(layout="wide", page_title="Silver Price Calculator & Sales Dashboard")

st.title("Silver Price Calculator & Silver Sales Dashboard")

def load_historical_prices():
	path = DATA_DIR / "historical_silver_price.csv"
	if not path.exists():
		return pd.DataFrame(columns=["date", "price_per_gram"])
	df = pd.read_csv(path)
	
	if set(["date", "price_per_gram"]).issubset(df.columns):
		df["date"] = pd.to_datetime(df["date"])
		return df.sort_values("date")
	if set(["Year", "Month", "Silver_Price_INR_per_kg"]).issubset(df.columns):
		
		df["month_num"] = df["Month"].apply(lambda m: pd.to_datetime(m, format="%b").month if isinstance(m, str) else int(m))
		df["date"] = pd.to_datetime(df["Year"].astype(str) + "-" + df["month_num"].astype(str) + "-01")
		# convert per-kg to per-gram
		df["price_per_gram"] = df["Silver_Price_INR_per_kg"] / 1000.0
		return df[["date", "price_per_gram"]].sort_values("date")
	
	try:
		df.columns = [c.strip() for c in df.columns]
		df.iloc[:, 0] = pd.to_datetime(df.iloc[:, 0], errors="coerce")
		df.iloc[:, 1] = pd.to_numeric(df.iloc[:, 1], errors="coerce")
		df = df.rename(columns={df.columns[0]: "date", df.columns[1]: "price_per_gram"})
		return df[["date", "price_per_gram"]].dropna().sort_values("date")
	except Exception:
		return pd.DataFrame(columns=["date", "price_per_gram"])

def load_state_purchases():
	path = DATA_DIR / "state_wise_silver_purchased_kg.csv"
	if not path.exists():
		return pd.DataFrame(columns=["state", "total_kg"])
	df = pd.read_csv(path)
	
	cols = {c.lower(): c for c in df.columns}
	# common patterns
	if "state" in cols or "state" in [c.lower() for c in df.columns]:
		# find state column
		state_col = next((c for c in df.columns if c.lower() == "state"), None)
	else:
		state_col = df.columns[0]
	# find quantity column
	qty_col = None
	for candidate in ["total_kg", "silver_purchased_kg", "silver_purchased_kg", "silver_purchased_kg", "silver_purchased_kg"]:
		for c in df.columns:
			if c.lower() == candidate:
				qty_col = c
				break
		if qty_col:
			break
	if qty_col is None:
		# fallback: assume second column
		qty_col = df.columns[1] if len(df.columns) > 1 else None

	if qty_col is None:
		df = pd.DataFrame(columns=["state", "total_kg"])
	else:
		df = df.rename(columns={state_col: "state", qty_col: "total_kg"})
		df["total_kg"] = pd.to_numeric(df["total_kg"], errors="coerce").fillna(0)
	return df[["state", "total_kg"]]

def load_karnataka_monthly():
	path = DATA_DIR / "karnataka_monthly.csv"
	if not path.exists():
		return pd.DataFrame(columns=["month", "kg"])
	return pd.read_csv(path, parse_dates=["month"]).sort_values("month")

def load_january_sales():

	path1 = DATA_DIR / "state_monthly_sales.csv"
	path2 = DATA_DIR / "state_wise_silver_purchased_kg.csv"
	if path1.exists():
		df = pd.read_csv(path1)
		if "Jan" in df.columns:
			df = df.rename(columns={"Jan": "jan_kg"})
			df["jan_kg"] = pd.to_numeric(df["jan_kg"], errors="coerce").fillna(0)
			return df[[c for c in df.columns if c.lower() in ["state", "State", "STATE"] or c=="jan_kg"]].rename(columns={next((c for c in df.columns if c.lower()=="state"), df.columns[0]): "state"})
	if path2.exists():
		df2 = pd.read_csv(path2)
		# If there's a Jan column
		jan_col = next((c for c in df2.columns if c.lower() == "jan"), None)
		if jan_col:
			df2 = df2.rename(columns={jan_col: "jan_kg"})
			df2["jan_kg"] = pd.to_numeric(df2["jan_kg"], errors="coerce").fillna(0)
			state_col = next((c for c in df2.columns if c.lower() == "state"), df2.columns[0])
			return df2.rename(columns={state_col: "state"})[["state", "jan_kg"]]
		# fallback estimate from annual totals
		total_col = next((c for c in df2.columns if "total" in c.lower() or "silver" in c.lower()), None)
		if total_col is None and len(df2.columns) >= 2:
			total_col = df2.columns[1]
		if total_col is not None:
			df2 = df2.rename(columns={next((c for c in df2.columns if c.lower()=="state"), df2.columns[0]): "state", total_col: "annual_kg"})
			df2["annual_kg"] = pd.to_numeric(df2["annual_kg"], errors="coerce").fillna(0)
			df2["jan_kg"] = (df2["annual_kg"] / 12.0).round(2)
			return df2[["state", "jan_kg"]]
	# last fallback: empty
	return pd.DataFrame(columns=["state", "jan_kg"])

def load_states_geo():
	geojson_path = DATA_DIR / "india_states_geo.json"
	if not geojson_path.exists() or gpd is None:
		return None
	return gpd.read_file(geojson_path)


st.sidebar.header("Silver Price Calculator")

weight = st.sidebar.number_input("Weight", min_value=0.0, value=100.0, step=1.0)
unit = st.sidebar.selectbox("Unit", ["g", "kg"]) 
price_per_gram = st.sidebar.number_input("Current price per gram (INR)", min_value=0.0, value=100.0, step=1.0)
currency = st.sidebar.selectbox("Display currency", ["INR", "USD", "EUR"])
exchange_rates = st.sidebar.text_area("Exchange rates (JSON)", value='{"INR": 1.0, "USD": 0.012, "EUR": 0.011}')

try:
	rates = json.loads(exchange_rates)
except Exception:
	rates = {"INR": 1.0, "USD": 0.012, "EUR": 0.011}

grams = weight if unit == "g" else weight * 1000.0
total_inr = grams * price_per_gram
converted = total_inr * rates.get(currency, 1.0)

st.subheader("Calculator")
col1, col2 = st.columns(2)
with col1:
	st.metric("Weight", f"{weight} {unit}")
	st.metric("Price per gram (INR)", f"{price_per_gram:,.2f}")
with col2:
	st.metric("Total (INR)", f"{total_inr:,.2f}")
	st.metric(f"Total ({currency})", f"{converted:,.2f}")

st.subheader("Historical Silver Prices")
hist = load_historical_prices()
hist["price_per_kg"] = hist["price_per_gram"] * 1000.0

price_filter = st.radio("Filter by per-kg ranges", ["All", "≤ 20,000 INR/kg", "20,000–30,000 INR/kg", "≥ 30,000 INR/kg"]) 
if price_filter == "≤ 20,000 INR/kg":
	hist_f = hist[hist["price_per_kg"] <= 20000]
elif price_filter == "20,000–30,000 INR/kg":
	hist_f = hist[(hist["price_per_kg"] > 20000) & (hist["price_per_kg"] < 30000)]
elif price_filter == "≥ 30,000 INR/kg":
	hist_f = hist[hist["price_per_kg"] >= 30000]
else:
	hist_f = hist

if hist_f.empty:
	st.info("No historical data for selected filter.")
else:
	fig = px.line(hist_f, x="date", y="price_per_gram", title="Silver price per gram (INR)")
	st.plotly_chart(fig, use_container_width=True)


st.header("Silver Sales Dashboard")

states_geo = load_states_geo()
state_df = load_state_purchases()

st.markdown("State-wise silver purchases (kg)")

if states_geo is None:
	st.warning("GeoPandas not available or `india_states_geo.json` missing — map disabled. Install GeoPandas and ensure `data/india_states_geo.json` exists.")
else:
	# Merge
	merged = states_geo.merge(state_df, left_on="state", right_on="state", how="left")
	merged["total_kg"] = merged["total_kg"].fillna(0)

	fig_map, ax = plt.subplots(1, 1, figsize=(10, 8))
	merged.plot(column="total_kg", cmap="OrRd", linewidth=0.8, ax=ax, edgecolor="0.8", legend=True)
	ax.set_axis_off()
	ax.set_title("India — State-wise Silver Purchases (kg)")
	st.pyplot(fig_map)

	st.subheader("Top 5 states by silver purchases")
	top5 = state_df.sort_values("total_kg", ascending=False).head(5)
	fig_bar = px.bar(top5, x="state", y="total_kg", labels={"total_kg": "Total (kg)"}, title="Top 5 States")
	st.plotly_chart(fig_bar, use_container_width=True)

	st.subheader("January month silver sales (state-wise)")
	jan = load_january_sales()
	if not jan.empty:
		# ensure columns
		if "jan_kg" not in jan.columns and "kg" in jan.columns:
			jan = jan.rename(columns={"kg": "jan_kg"})
		jan_sample = jan.sort_values("jan_kg", ascending=False).head(20)
		fig_bar_jan = px.bar(jan_sample, x="state", y="jan_kg", labels={"jan_kg": "January (kg)"}, title="January Silver Purchases by State")
		st.plotly_chart(fig_bar_jan, use_container_width=True)
		st.dataframe(jan.sort_values("jan_kg", ascending=False))
	else:
		st.info("No January sales data available; provide `data/state_monthly_sales.csv` with a 'Jan' column or a yearly totals file to estimate.")

	st.subheader("Merged data sample")
	st.dataframe(merged[["state", "total_kg"]].sort_values("total_kg", ascending=False))

st.markdown("---")
st.markdown("Data files used: `data/historical_prices.csv`, `data/state_purchases.csv`, `data/india_states_geo.json`")

st.title("Sales Data Analysis")
st.write("Upload your sales data csv file to visualize sales trends over time. ")
