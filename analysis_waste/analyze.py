"""Join EPD disposal data to the project snapshot and reproduce the report charts."""
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

HERE = Path(__file__).resolve().parent
points = pd.read_csv(HERE.parent / 'data/RecycleMatch_HK_public_points_clean.csv')
supply = points.groupby('district_id').size().rename('point_count')
disposal = pd.read_csv(HERE / 'district_disposal_2024.csv').set_index('district_id')
assert len(points) == 5868 and len(supply) == 18
assert disposal.index.is_unique and set(disposal.index) == set(supply.index) - {'Islands'}
assert (disposal.msw_tpd - disposal.domestic_tpd - disposal.commercial_industrial_tpd).abs().max() <= 1
districts = disposal.join(supply, validate='one_to_one')
districts['points_per_1000_tpd'] = districts.point_count / districts.msw_tpd * 1000
districts.to_csv(HERE / 'district_results.csv')
for column in ['msw_tpd', 'domestic_tpd', 'commercial_industrial_tpd']:
    print(column, f"Spearman rho = {districts[column].rank().corr(districts.point_count.rank()):.3f}")
print(districts.nsmallest(3, 'points_per_1000_tpd')[['point_count','msw_tpd','points_per_1000_tpd']])
fig, ax = plt.subplots(figsize=(9, 5))
ax.scatter(districts.msw_tpd, districts.point_count, color='#16826c')
for district, row in districts.nsmallest(3, 'points_per_1000_tpd').iterrows():
    ax.annotate(district.replace('_', ' '), (row.msw_tpd, row.point_count), xytext=(5,-12), textcoords='offset points')
ax.set(title='Public collection points and landfill disposal | 17 matched districts',
       xlabel='2024 municipal solid waste sent to landfill (tonnes/day)', ylabel='Public collection points (July 2026 snapshot)')
ax.grid(alpha=.2)
fig.savefig(HERE / 'district_scatter.png', dpi=180, bbox_inches='tight')
plt.close(fig)

annual = pd.read_csv(HERE / 'msw_2009_2024.csv')
assert annual.year.tolist() == list(range(2009, 2025))
annual['recalculated_rate_pct'] = annual.recovered_million_tonnes / annual.generation_million_tonnes * 100
assert (annual.recalculated_rate_pct - annual.official_rate_pct).abs().max() < 0.6
annual.to_csv(HERE / 'annual_results.csv', index=False)
fig, ax = plt.subplots(figsize=(9, 5))
ax.plot(annual.year, annual.official_rate_pct, color='#16826c', marker='o', label='EPD published rate')
ax.scatter(annual.year, annual.recalculated_rate_pct, facecolors='none', edgecolors='#c87527', label='Recomputed from reported quantities')
ax.set(title='Hong Kong municipal solid waste recovery rate, 2009–2024', xlabel='Year', ylabel='Recovery rate (%)', ylim=(20, 60))
ax.set_xticks(range(2009, 2025, 2))
ax.grid(alpha=.2)
ax.legend()
fig.savefig(HERE / 'recovery_trend.png', dpi=180, bbox_inches='tight')
plt.close(fig)
print('Largest difference vs official rate (percentage points):', round((annual.recalculated_rate_pct - annual.official_rate_pct).abs().max(), 3))
