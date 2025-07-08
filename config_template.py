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
            }, 
            "dem": {
                "url": "https://www.dropbox.com/scl/fi/6wq78jlj14gmmj75kzjm3/dem_converted_bbox.tif?rlkey=4tenmorf5hbyt428xkih8lt2g&dl=1",
                "filename": "dem_converted_bbox.tif",
                "layer": None,  # No specific layer for DEM
            },   
            "gauges": {
                "url": "https://www.dropbox.com/scl/fi/vvrdo3fotxy9ewebfqiw4/Wasserpegel_-OGD.gpkg?rlkey=74tg568yvn1lv2ouo6wcyl212&dl=1", 
                "filename": "Wasserpegel_-OGD.gpkg",
                "layer": "GS_GRUNDWASSERPEGEL_P",  # Layer name for gauges
            }, 
            "rivers": {
                "url": "https://www.dropbox.com/scl/fi/c2o69m3cqqonlqkxo1u7v/AV_Gewasser_-OGD.gpkg?rlkey=7k7mvr1z17i2eyswst2374dpr&dl=1",
                "filename": "AV_Gewasser_-OGD.gpkg",
                "layer": "AVZH_GEWAESSER_F",  # Layer name for rivers
            },  
            # Add other public limmat data URLs
            "model_boundary": {
                "url": "https://www.dropbox.com/scl/fi/0q5z2n343ne9g4kttrecs/model_boundary.gpkg?rlkey=epwc8zjxn6u2tvnvqwu0gx70g&dl=1", 
                "filename": "limmat_model_boundary.gpkg",
                "layer": "id",  # Layer name for model boundary
            }
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
