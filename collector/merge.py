import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler
import joblib
# -------------------------------
# STEP 1: Load data safely
# -------------------------------
dorm = pd.read_csv("../data/dorm.csv", on_bad_lines='skip')
home = pd.read_csv("../data/home.csv", on_bad_lines='skip')
lab = pd.read_csv("../data/lab.csv", on_bad_lines='skip')

# -------------------------------
# STEP 2: Sort by time (important)
# -------------------------------
dorm = dorm.sort_values(by="timestamp")
home = home.sort_values(by="timestamp")
lab = lab.sort_values(by="timestamp")

# -------------------------------
# STEP 3: Drop timestamp
# -------------------------------
dorm = dorm.drop(columns=["timestamp"], errors='ignore')
home = home.drop(columns=["timestamp"], errors='ignore')
lab = lab.drop(columns=["timestamp"], errors='ignore')

# -------------------------------
# STEP 4: Select features
# -------------------------------
features = ['latency_ms','packet_loss_pct','download_mbps',
            'upload_mbps','connected_devices','dns_response_ms',
            'gateway_ping_ms','jitter_ms']

dorm_data = dorm[features].values
home_data = home[features].values
lab_data = lab[features].values 
# -------------------------------
# STEP 5: Normalize (IMPORTANT)
# -------------------------------
scaler = StandardScaler()

# Fit on BOTH (so model sees full range)
all_data = np.vstack([dorm_data, home_data, lab_data])
scaler.fit(all_data)

dorm_scaled = scaler.transform(dorm_data)
home_scaled = scaler.transform(home_data)
lab_scaled = scaler.transform(lab_data)

# Save the scaler — this is the critical missing step
joblib.dump(scaler, "../models/scaler.pkl")
print("Scaler saved.")
# -------------------------------
# STEP 6: Create sequences
# -------------------------------
def create_sequences(data, timesteps=60):
    return np.array([
        data[i:i+timesteps]
        for i in range(len(data)-timesteps)
    ])

X_dorm = create_sequences(dorm_scaled)
X_home = create_sequences(home_scaled)
X_lab = create_sequences(lab_scaled)

# -------------------------------
# STEP 7: FINAL MERGE (SAFE)
# -------------------------------
X = np.concatenate([X_dorm, X_home, X_lab])

print("Final shape:", X.shape)
    # -------------------------------
# SAVE SEQUENCES
# -------------------------------
np.save("../data/X_sequences.npy", X)

print("Saved X_sequences.npy")