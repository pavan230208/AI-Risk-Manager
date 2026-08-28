import pandas as pd
import numpy as np

class FeatureEngineeringError(Exception):
    pass

def extract_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Extract temporal features from transaction dataset.
    STRICT DATA LEAKAGE PREVENTION: Uses only past information up to the current transaction.
    Assumes df is ordered by timestamp.
    """
    try:
        if df.empty:
            raise FeatureEngineeringError("Empty DataFrame provided")
            
        # Ensure critical columns exist
        required_cols = ['timestamp', 'user_id', 'amount', 'device_id', 'location']
        for col in required_cols:
            if col not in df.columns:
                raise FeatureEngineeringError(f"Missing required column: {col}")

        # Fill nulls in groupby keys to prevent length mismatch errors
        df['user_id'] = df['user_id'].fillna('UNKNOWN_USER')
        df['device_id'] = df['device_id'].fillna('UNKNOWN_DEVICE')
        df['location'] = df['location'].fillna('UNKNOWN_LOCATION')
        
        # Ensure amount is numeric, coercing errors to NaN and filling with 0
        df['amount'] = pd.to_numeric(df['amount'], errors='coerce').fillna(0.0)

        # Ensure sorted by time
        if not pd.api.types.is_datetime64_any_dtype(df['timestamp']):
            df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
            if df['timestamp'].isnull().any():
                raise FeatureEngineeringError("Malformed timestamp detected")
        
        df = df.sort_values("timestamp").copy()
        
        # 1. Historical Transaction Statistics (expanding window, shifted to avoid current row leakage)
        # We group by user_id. We need historical average of amounts.
        df['user_hist_amt_sum'] = df.groupby('user_id')['amount'].transform(lambda x: x.shift(1).expanding().sum().fillna(0))
        df['user_hist_tx_count'] = df.groupby('user_id')['amount'].transform(lambda x: x.shift(1).expanding().count().fillna(0))
        
        df['user_hist_avg_amt'] = np.where(
            df['user_hist_tx_count'] > 0, 
            df['user_hist_amt_sum'] / df['user_hist_tx_count'], 
            df['amount'] # Fallback to current amount if it's the first transaction
        )
        
        df['amount_deviation'] = df['amount'] / df['user_hist_avg_amt']
        df['amount_deviation'] = df['amount_deviation'].replace([np.inf, -np.inf], 1.0).fillna(1.0)

        # 2. Velocity features (using rolling windows on time index)
        # First, set index to timestamp for rolling operations
        df_time = df.set_index('timestamp')
        
        # Calculate counts in 1H and 24H windows, excluding the current transaction by subtracting 1
        # Rolling includes current row, so we subtract 1. If it's the only row, count is 0.
        df['velocity_1h'] = df_time.groupby('user_id')['amount'].transform(lambda x: x.rolling('1h').count() - 1).values
        df['velocity_24h'] = df_time.groupby('user_id')['amount'].transform(lambda x: x.rolling('24h').count() - 1).values

        # 3. New Device and Location Flags
        # Group by user, check if we've seen this device before the current transaction.
        df['is_new_device'] = ~df.duplicated(subset=['user_id', 'device_id'], keep='first')
        df['is_new_location'] = ~df.duplicated(subset=['user_id', 'location'], keep='first')

        # Convert booleans to int for ML compatibility
        df['is_new_device'] = df['is_new_device'].astype(int)
        df['is_new_location'] = df['is_new_location'].astype(int)
        
        df.drop(columns=['user_hist_amt_sum'], inplace=True, errors='ignore')
        
        return df
    except FeatureEngineeringError:
        raise
    except Exception as e:
        raise FeatureEngineeringError(f"Feature engineering failed: {str(e)}")
