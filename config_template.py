# config_template.py

# CHOOSE CASE STUDY:
# Options:
# "limmat" -> Use the Limmat valley aquifer in Zurich, Switzerland (publicly available, default)
# "zarafshan" -> Use the Zarafshan aquifer in Uzbekistan (not publicly available)
CASE_STUDY = "limmat"

# CHOOSE WHERE TO GET YOUR DATA:
# Options:
# "dropbox" -> Use Dropbox links
# "switch"  -> Use SWITCHdrive links
DATA_SOURCE = "dropbox"

# DATA_URLS for different case studies and sources
DATA_URLS = {
    "limmat": {
        "dropbox": {
            "groundwater_map_norm": {
                "url": "https://www.dropbox.com/scl/fi/0tzhzcbmj64ii9faq0jp9/Grundwasservorkommen_-OGD.gpkg?rlkey=8zwfw4nv8nskmrm1h7urgsz9y&st=wz2o6bsu&dl=1",
                "filename": "Grundwasservorkommen_-OGD.gpkg",
                "layer": "GS_GW_LEITER_F", 
                "readme_url": "https://www.dropbox.com/scl/fi/4w76qtxe8w3i6eztyh3p8/Produktblatt_AV_Gewasser_-OGD.pdf?rlkey=o8dt6qkrvxuqf0jagau5rz1yr&dl=1", 
            }, 
            "dem": {
                "url": "https://www.dropbox.com/scl/fi/6wq78jlj14gmmj75kzjm3/dem_converted_bbox.tif?rlkey=4tenmorf5hbyt428xkih8lt2g&dl=1",
                "filename": "dem_converted_bbox.tif",
                "layer": None,  # No specific layer for DEM
                "readme_url": "https://www.dropbox.com/scl/fi/okvjstbm078v9nghbisjv/DHM25_Documentation.pdf?rlkey=j9crdkettepfe5k5eh60eoza4&dl=1", 
            },   
            "dem_hres": {
                "url": "https://www.dropbox.com/scl/fi/cbo2vescztrryn1s8z8lp/swissalti3d_merged_lv95.tif?rlkey=y97k2qhwyjd4gb20jw73ti7ri&dl=1", 
                #"url": "https://www.dropbox.com/scl/fi/xwshpm2pz8e6o3wp2pcrc/swissalti3d_merged_lv03.tif?rlkey=fkxt22bhb64gs9ipj1cvg6xf6&dl=1", 
                "filename": "swissalti3d_merged_lv95.tif",
                "layer": None,  # No specific layer for high-resolution DEM
                "readme_url": "https://www.dropbox.com/scl/fi/96lsuixlydxbnxg63jwx7/swissALTI3D_Dokumentation.pdf?rlkey=onmpfh3j6ambjtnr3sm97qxj5&dl=1", 
            },   
            "gauges": {
                "url": "https://www.dropbox.com/scl/fi/vvrdo3fotxy9ewebfqiw4/Wasserpegel_-OGD.gpkg?rlkey=74tg568yvn1lv2ouo6wcyl212&dl=1", 
                "filename": "Wasserpegel_-OGD.gpkg",
                "layer": "GS_GRUNDWASSERPEGEL_P",  # Layer name for gauges
                "readme_url": "https://www.dropbox.com/scl/fi/hd3nsm610zh36zniu2m7t/Produktblatt_Wasserpegel_-OGD.pdf?rlkey=wtb4r72s68zzl88ahspju7u83&dl=1", 
            }, 
            "rivers": {
                "url": "https://www.dropbox.com/scl/fi/c2o69m3cqqonlqkxo1u7v/AV_Gewasser_-OGD.gpkg?rlkey=7k7mvr1z17i2eyswst2374dpr&dl=1",
                "filename": "AV_Gewasser_-OGD.gpkg",
                "layer": "AVZH_GEWAESSER_F",  # Layer name for rivers
                "readme_url": "https://www.dropbox.com/scl/fi/4w76qtxe8w3i6eztyh3p8/Produktblatt_AV_Gewasser_-OGD.pdf?rlkey=o8dt6qkrvxuqf0jagau5rz1yr&dl=1", 
            },  
            "river_cells": {
                "url": "https://www.dropbox.com/scl/fi/qycx9qgeawpm1qsced5fu/river_cells.gpkg?rlkey=te5u031dturd8zgn6krsh5feg&dl=1", 
                "filename": "river_cells.gpkg",
                "layer": "river_cells",  # Layer name for river cells
                "readme_url": "https://www.dropbox.com/scl/fi/9cswdxy7txst0z2dq4jaq/readme.md?rlkey=czk96vo2lxfx81axxycz4eajn&dl=1"
            }, 
            "wells": {
                "url": "https://www.dropbox.com/scl/fi/ka40fw4te7dbb5sygrtdj/Wasserfassungen_-OGD.gpkg?rlkey=aoskogf8eg1hswswwncpnbpzk&dl=1", 
                "filename": "Wasserfassungen_-OGD.gpkg",
                "layer": "GS_GRUNDWASSERFASSUNGEN_OGD_P",  # Layer name for wells
                "readme_url": "https://www.dropbox.com/scl/fi/n9m4wihx012lus1h11750/Produktblatt_Wasserfassungen_-OGD.pdf?rlkey=c42kikrdl3fmo2bssjynxx9hp&dl=1",
            },
            "model_boundary": {
                "url": "https://www.dropbox.com/scl/fi/0q5z2n343ne9g4kttrecs/model_boundary.gpkg?rlkey=epwc8zjxn6u2tvnvqwu0gx70g&dl=1", 
                "filename": "limmat_model_boundary.gpkg",
                "layer": "id",  # Layer name for model boundary
                "readme_url": "https://www.dropbox.com/scl/fi/8aiw2dnfly2i1stetsdjq/readme.md?rlkey=xbi96i69wki4la5y6gflvydk2&dl=1",
            }, 
            "chd_cells": {
                "url": "https://www.dropbox.com/scl/fi/gurjv5q4zwtgzoe2amgoh/chd_boundary_cells.gpkg?rlkey=v1ryll6u8d3xbtoz9nqdt7ozy&dl=1", 
                "filename": "chd_boundary_cells.gpkg",
                "readme_url": "https://www.dropbox.com/scl/fi/ivp5ngb46mzrvhhp59g0u/readme.md?rlkey=x33astkfk74jp3cd9w3v12xo1&dl=1"
            }, 
            "wells_north": {
                "url": "https://www.dropbox.com/scl/fi/asbo1aez3uhn41an1rfif/lateral_north_boundary_cells.gpkg?rlkey=kwmmp3npl0iciqcx4vlxxk06w&dl=1", 
                "filename": "lateral_north_boundary_cells.gpkg",
                "readme_url": "https://www.dropbox.com/scl/fi/w797isz5zcipyvyhc9tyd/readme.md?rlkey=p6ka92kzgc461v0e4s7gcpulj&dl=1",
            }, 
            "wells_south": {
                "url": "https://www.dropbox.com/scl/fi/zh3fekwdqwv7f7xni3bzc/lateral_south_boundary_cells.gpkg?rlkey=q1e86panedhpwkagsmssv8r93&dl=1", 
                "filename": "lateral_south_boundary_cells.gpkg",
                "readme_url": "https://www.dropbox.com/scl/fi/xmtwi59jnwk63qfr5nws0/readme.md?rlkey=fjg31qrciwdslcvsocf8u00a7&dl=1",
            }, 
            "groundwater_timeseries": {
                "url": "https://www.dropbox.com/scl/fi/rv71re30u5isprp66kxtj/all_wells_long_format.csv?rlkey=xil7rw09yys36k421skhqyr1r&dl=1",
                "filename": "all_wells_long_format.csv",
                "readme_url": "https://www.dropbox.com/scl/fi/nk2tdlgv3g93lpgfakd61/readme.md?rlkey=ub0wm2d0ggt3ex72lnhmxdhn4&dl=1",
            },
        },
        "switch": {
            "groundwater_map_norm": "https://ethz-my.sharepoint.com/:u:/r/personal/XXXX/applied_gw_modelling_zurich_case_study_data/Grundwasservorkommen_-OGD/Grundwasservorkommen_-OGD.gpkg?csf=1&web=1&e=henbgz",
            "climate_data": "https://ethz-my.sharepoint.com/...",
            # Add other private limmat data URLs
        }
    },
    "zarafshan": {
        "dropbox": {
            # Add private zarafshan data URLs
            "groundwater_map": "", 
            "dem": "", 
        }
    }
}
