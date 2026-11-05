# RecycleMatch HK · waste data validation and analysis

Verified 5 November 2026 against the Environmental Protection Department's
[official report archive](https://www.wastereduction.gov.hk/en-hk/resources-centre/waste-statistics).
Install the plotting dependencies with `python -m pip install -r analysis_waste/requirements.txt`,
then run `python analysis_waste/analyze.py` from the project root.

## District comparison

`district_disposal_2024.csv` transcribes the domestic, commercial and industrial,
and municipal solid waste columns of
[2024 Waste Statistics, Plate 2.6, printed p. 10](https://www.wastereduction.gov.hk/sites/default/files/resources_centre/waste_statistics/msw2024_eng.pdf).
Units are tonnes per day sent to landfill. EPD estimates geographical attribution
mainly from facility intake records and describes the figures as indicative.
The reported MSW column is retained because components are independently rounded.
The 17 explicitly named districts join one-to-one to the July 2026 project snapshot.
The report lists island locations and a regional subtotal (including Ma Wan),
so that subtotal is not assigned to the project's Islands district.

Across 17 matched districts, Spearman rho between site count and 2024 MSW
disposal is 0.505. Domestic and commercial/industrial rho are 0.525 and 0.399.
Yau Tsim Mong has the lowest site-to-disposal ratio in this comparison
(249 sites, 794 t/day, 314 sites per 1,000 t/day). The different reference years,
site capacity, operating hours and cross-district use limit interpretation.
The ratio describes relative provision in the project inventory.

## Annual recovery

The project uses the official PDFs. The screenshot's claims about separate
downloadable CSVs were not independently verified.
- [2013 report](https://www.wastereduction.gov.hk/sites/default/files/resources_centre/waste_statistics/msw2013_eng.pdf),
  Plates 2.3, 3.2 and 3.5 for 2009–2013. Generation is estimated by adding recovered
  tonnes to the rounded domestic and commercial/industrial daily disposal
  figures multiplied by the number of calendar days.
- [2018 report](https://www.wastereduction.gov.hk/sites/default/files/resources_centre/waste_statistics/msw2018_eng.pdf),
  Plate 3.8 for 2014.
- [2019 report](https://www.wastereduction.gov.hk/sites/default/files/resources_centre/waste_statistics/msw2019_eng.pdf),
  Plate 3.8 for 2015–2019.
- [2024 report](https://www.wastereduction.gov.hk/sites/default/files/resources_centre/waste_statistics/msw2024_eng.pdf),
  Plate 3.7 for 2020–2024.

The recalculated rates differ from published whole percentages by at most
0.523 percentage points. The published series goes from 49% (2009) to 52%
(2010), falls to 28% (2020), and recovers to 34% (2024). The 2013 report flags
fluctuations in waste-plastics export statistics for the 2011–2012 decreases.
There is only one collection-point snapshot in this comparison, so the annual
analysis does not estimate any effect of network expansion.

## Application checks

23 Python project checks passed. Local HTTP served the page and scripts and
returned recommendations and route links for the one-stop, few-stop and
RVM workflows. JavaScript checks passed for rebate and points estimation,
redemption thresholds, and category filters. Anchor targets were checked
in the served page. Desktop/mobile browser rendering was not verified.
