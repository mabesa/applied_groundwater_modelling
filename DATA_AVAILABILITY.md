# Data Availability

This course uses public data for the Limmat Valley case study. The repository may use mirrored or preprocessed teaching copies to keep notebooks reliable during class, but those mirrors are not the authoritative data sources.

Operational download metadata lives in `config_template.py`:

- `url` points to the teaching download location used by the notebooks.
- `readme_url` points to provider documentation or local processing notes where available.

This file is the canonical place for provenance, terms of use, and raw-versus-derived status.

Maintenance note: keep the raw-versus-derived table below in sync with the data keys in `config_template.py`. If a config key is renamed, added, or removed, update this file in the same change.

## Public Data Providers

| Provider | Role in course material | Terms / documentation |
| --- | --- | --- |
| AWEL / GIS-ZH / Canton Zurich open data | Groundwater occurrence, groundwater gauges, groundwater wells, water bodies, and related geodata | Canton Zurich open data page: https://www.zh.ch/de/politik-staat/opendata.html |
| BAFU / FOEN | Hydrological observations such as river gauge daily values | FOEN hydrological data portal: https://www.hydrodaten.admin.ch/en/ |
| MeteoSwiss | Climate normals used for recharge and climate-context teaching data | MeteoSwiss open data terms: https://opendatadocs.meteoswiss.ch/general/terms-of-use |
| swisstopo | Elevation products such as DHM25 and swissALTI3D-derived terrain data | swisstopo free geodata terms: https://www.swisstopo.admin.ch/en/terms-of-use-free-geodata-and-geoservices |
| opendata.swiss | General Swiss open-government-data terms model and dataset catalogue | https://opendata.swiss/en/terms-of-use |

## Terms Summary

Swiss open-government-data datasets can have dataset-specific terms. The opendata.swiss portal distinguishes several usage models, including open use with recommended attribution and open use with mandatory source citation. Check the specific dataset entry or provider documentation before redistributing data outside this course.

Canton Zurich states that open data may be copied, distributed, made accessible, enriched, edited, and used commercially. For datasets under CC BY 4.0, the source must be named using the organization listed in the dataset contact plus a link to the dataset.

MeteoSwiss states that its open meteorological and climatological data may be shared, processed, remixed, changed, built upon, and used commercially. MeteoSwiss requires source acknowledgement and publishes its Open Data under CC BY 4.0.

swisstopo states that its free geodata and geoservices may be used, distributed, made accessible, enriched, processed, and used commercially, with mandatory source reference.

The BAFU/FOEN daily river data used in this course were provided directly by FOEN Hydrology for teaching use. The dataset contains daily discharge and water-level values for stations 2099 Limmat - Zurich, Unterhard and 2176 Sihl - Zurich, Sihlholzli for 2000-2024. Values from 2021-01-01 onward are provisional. BAFU conditions for covered hydrological raw data permit commercial and non-commercial use and recommend source attribution. Treat these data as BAFU/FOEN provider-terms data, not as project-owned CC BY material.

## Raw And Derived Items

The table below is a working provenance map for the items referenced in `config_template.py`. "Redistribution status" is intentionally conservative where derived artifacts combine multiple public sources.

| Config key / item | Status | Source provider | Derived from | Redistribution / license notes |
| --- | --- | --- | --- | --- |
| `climate_data` | Raw public data / mirrored teaching copy | MeteoSwiss | Not derived in this repository | MeteoSwiss Open Data are CC BY 4.0 with source acknowledgement required. |
| `groundwater_map_norm` | Raw public geodata / mirrored teaching copy | AWEL / GIS-ZH / Canton Zurich | Not derived in this repository | Public OGD source. Attribute provider and dataset according to Canton Zurich terms. |
| `dem` | Processed terrain raster | swisstopo | DHM25-derived terrain data | swisstopo attribution required. Processing should preserve provider attribution. |
| `dem_hres` | Processed terrain raster | swisstopo | swissALTI3D-derived terrain data | swisstopo attribution required. Processing should preserve provider attribution. |
| `gauges` | Raw public geodata / mirrored teaching copy | AWEL / GIS-ZH / Canton Zurich | Not derived in this repository | Public OGD source. Attribute provider and dataset according to Canton Zurich terms. |
| `rivers` | Raw public geodata / mirrored teaching copy | AWEL / GIS-ZH / Canton Zurich | Not derived in this repository | Public OGD source. Attribute provider and dataset according to Canton Zurich terms. |
| `wells` | Raw public geodata / mirrored teaching copy | AWEL / GIS-ZH / Canton Zurich | Not derived in this repository | Public OGD source. Attribute provider and dataset according to Canton Zurich terms. |
| `river_data` | Raw public hydrological data / mirrored teaching copy | BAFU / FOEN | Not derived in this repository | Provided directly by FOEN Hydrology for teaching use; source attribution recommended. Contains daily discharge and water-level values for stations 2099 and 2176 from 2000-2024; values from 2021-01-01 onward are provisional. |
| `river_cells` | Derived geodata / teaching artifact | Project-owned processing; based on public geodata | River geodata, model grid, and modelling choices | Reuse under applicable source-provider terms plus project attribution. |
| `model_boundary` | Derived geodata / teaching artifact | Project-owned processing; based on public geodata and teaching choices | Aquifer/geodata interpretation and modelling scope | Reuse under applicable source-provider terms plus project attribution. |
| `model_boundary_segments` | Derived geodata / teaching artifact | Project-owned processing; based on public geodata and teaching choices | `model_boundary` and boundary-condition interpretation | Reuse under applicable source-provider terms plus project attribution. |
| `chd_cells` | Derived model input / teaching artifact | Project-owned processing; based on public geodata and model grid | Model grid, boundary segments, groundwater/river context | Reuse under applicable source-provider terms plus project attribution. |
| `wells_north` | Derived model input / teaching artifact | Project-owned processing; based on public geodata and model grid | Model grid and lateral-boundary interpretation | Reuse under applicable source-provider terms plus project attribution. |
| `wells_south` | Derived model input / teaching artifact | Project-owned processing; based on public geodata and model grid | Model grid and lateral-boundary interpretation | Reuse under applicable source-provider terms plus project attribution. |
| `groundwater_timeseries` | Processed observation table | AWEL / GIS-ZH / Canton Zurich | Groundwater gauge observations transformed to long format | Attribute source data provider; preserve processing notes. |
| `parameter_zones` | Derived geodata / teaching artifact | Project-owned processing; based on public geodata and modelling judgement | Aquifer interpretation, model grid, parameterization choices | Reuse under applicable source-provider terms plus project attribution. |
| `baseline_model` | Derived model artifact | Project-owned model setup | Public geodata, terrain, hydrological data, and modelling assumptions | Reuse under project teaching-content terms where compatible with provider terms. Attribute public data providers. |
| `calibrated_model` | Derived model artifact | Project-owned model setup/calibration | Baseline model, observations, calibration choices | Reuse under project teaching-content terms where compatible with provider terms. Attribute public data providers. |
| `flow_model_mf6` | Derived model artifact | Project-owned model setup/calibration | Calibrated flow model converted/prepared for transport notebooks | Reuse under project teaching-content terms where compatible with provider terms. Attribute public data providers. |

## Attribution Guidance

When reusing the material, cite this repository and retain the source attribution required by the public data providers. At minimum, include attribution for:

- Canton Zurich / AWEL / GIS-ZH open data where Canton Zurich geodata are used;
- MeteoSwiss where climate normals are used;
- Federal Office of Topography swisstopo where swisstopo elevation products are used;
- Federal Office for the Environment FOEN/BAFU where hydrological observations are used.

## Adaptation Notes

The Limmat Valley workflow is place-based. It can be studied or adapted as a modelling workflow, but adaptation to a different aquifer requires replacing the data pipeline, conceptual model, boundary conditions, and validation targets.
