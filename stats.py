import pandas as pd
import os
import numpy as np
import seaborn as sns
import matplotlib.pyplot as plt
import statsmodels.formula.api as smf

df = pd.read_csv("sec_transfers_srs_sos.csv")

# Find last row per player
last_rows = df.groupby('full_name').tail(1)

# Keep only players whose last conference is SEC
sec_players = last_rows[last_rows['Conf'] == 'SEC']['full_name']

# Filter original dataset to only those players
df_sec = df[df['full_name'].isin(sec_players)]
# For each player, find the last row before SEC and the first SEC row
result = []
for player, group in df_sec.groupby('full_name'):
    group = group.sort_values('Year')
    sec_index = group[group['Conf'] == 'SEC'].index[0]  # first SEC row
    before_sec = group.loc[:sec_index - 1].tail(1) if sec_index > group.index.min() else pd.DataFrame()
    first_sec = group.loc[[sec_index]]
    result.append(pd.concat([before_sec, first_sec]))

sectransfer_df = pd.concat(result).sort_values(['full_name', 'Year'])

playerStats = ['sos', 'srs', 'minutes', 'FG/40', 'FGA/40', 'FG%',
       'FG3/40', 'FG3A/40', 'FG3%', 'FG2/40', 'FG2A/40', 'FG2%', 'FT/40',
       'FTA/40', 'FT%', 'ORB/40', 'DRB/40', 'TRB/40', 'AST/40', 'STL/40',
       'BLK/40', 'TOV/40', 'PF/40', 'PTS/40', 'PER', 'TS%', '3PAr', 'FTr',
       'ORB%', 'DRB%', 'TRB%', 'AST%', 'STL%', 'BLK%', 'TOV%', 'USG%', 'OWS',
       'DWS', 'WS', 'WS/40', 'OBPM', 'DBPM', 'BPM']

# Create Categorization directly on sectransfer_df
# This will be used for grouping and unstacking
sectransfer_df['is_sec'] = sectransfer_df['Conf'] == 'SEC'

# Group by full_name and is_sec
grouped = sectransfer_df.groupby(['full_name', 'is_sec'])

# Define the aggregation dictionary
# For numeric metrics, calculate the mean.
# For 'Conf', get the first value (since there's only one conference per player per is_sec group)
agg_operations = {metric: 'mean' for metric in playerStats}
agg_operations['Conf'] = 'first' # Include 'Conf' and get its value (e.g., first or unique)

# Apply the aggregation
stats_and_conf_df = grouped.agg(agg_operations)

# Unstack to create wide-format DataFrame
secstats_df = stats_and_conf_df.unstack(level='is_sec')

# Filter to keep only players with data for both SEC and Non-SEC (remove NaNs)
secstats_df = secstats_df.dropna()

# Rename columns to flatten MultiIndex
new_columns = []
for col_name, is_sec_val in secstats_df.columns:
    suffix = '_SEC' if is_sec_val else '_Non_SEC'
    new_columns.append(f"{col_name}{suffix}")

secstats_df.columns = new_columns

# Initialize a dictionary to store delta and percentage-change values
calculated_deltas = {}

for metric in playerStats:
    # Calculate the delta for each metric
    delta = secstats_df[f'{metric}_SEC'] - secstats_df[f'{metric}_Non_SEC']
    non_sec = secstats_df[f'{metric}_Non_SEC']

    # Percentage change relative to non-SEC baseline
    # % change = ((SEC - Non-SEC) / Non-SEC) * 100
    pct_change = np.where(non_sec.abs() > 1e-9, (delta / non_sec) * 100, np.nan)

    calculated_deltas[f'{metric}_Delta'] = delta
    calculated_deltas[f'{metric}_Pct_Change'] = pct_change

# Create sec_deltas_df directly from the calculated delta values
sec_deltas_df = pd.DataFrame(calculated_deltas)

# Join 'Conf_Non_SEC' from the original secstats_df to sec_deltas_df
sec_deltas_df = sec_deltas_df.join(secstats_df['Conf_Non_SEC'])

# Make full_name a regular column (for Streamlit filtering)
sec_deltas_df = sec_deltas_df.reset_index().rename(columns={"index": "full_name"})