import pandas as pd
import matplotlib.pyplot as plt

TRACE_FILE = r".\data\re2ob_checkoutservice_delay_1\traces.parquet"
INJECT_FILE = r".\data\re2ob_checkoutservice_delay_1\inject_time.txt"

df = pd.read_parquet(TRACE_FILE)

with open(INJECT_FILE, "r") as f:
    inject_time = int(f.read().strip())

inject_time_ms = inject_time * 1000

# --------------------------------------------------
# Convert timestamp to relative seconds
# --------------------------------------------------

df["relative_seconds"] = (
    df["startTimeMillis"] - inject_time_ms
) / 1000

# --------------------------------------------------
# Create 10-second windows
# --------------------------------------------------

df["window"] = (
    df["relative_seconds"] // 10
) * 10

# --------------------------------------------------
# Service list
# --------------------------------------------------

services = sorted(
    df["serviceName"].dropna().unique()
)

# --------------------------------------------------
# Plot each service separately
# --------------------------------------------------

for service in services:

    service_df = df[
        df["serviceName"] == service
    ].copy()

    timeline = (
        service_df
        .groupby("window")["duration"]
        .median()
        .reset_index()
    )

    plt.figure(figsize=(12, 5))

    plt.plot(
        timeline["window"],
        timeline["duration"]
    )

    plt.axvline(
        0,
        linestyle="--",
        label="Fault injection"
    )

    plt.title(
        f"{service} — Median Span Duration"
    )

    plt.xlabel(
        "Seconds relative to fault injection"
    )

    plt.ylabel(
        "Median duration"
    )

    plt.legend()

    plt.tight_layout()

    filename = (
        "results/figures/timeline_"
        + service
        + ".png"
    )

    plt.savefig(filename)

    plt.close()

    print(f"Saved {filename}")

print("\nTimeline plots complete.")