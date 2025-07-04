# config_template.py

# CHOOSE WHERE TO GET YOUR DATA:
# Options:
# "dropbox" -> Use Dropbox links
# "switch"  -> Use SWITCHdrive links
DATA_SOURCE = "dropbox"

# DATA_URLS for Dropbox (public or private links)
DATA_URLS_DROPBOX = {
    "groundwater_map_norm": "https://www.dropbox.com/scl/fi/0tzhzcbmj64ii9faq0jp9/Grundwasservorkommen_-OGD.gpkg?rlkey=8zwfw4nv8nskmrm1h7urgsz9y&st=wz2o6bsu&dl=1", 
    "dem": "https://www.dropbox.com/scl/fi/6xqcy9jwf2smamrmd0dr0/dem_converted_bbox.tif?rlkey=hp9mn5txfb1px0wzqmylqv0t1&dl=1", 
}

DATA_URLS_SWITCH = {
    "groundwater_map_norm": "https://ethz-my.sharepoint.com/:u:/r/personal/XXXX/applied_gw_modelling_zurich_case_study_data/Grundwasservorkommen_-OGD/Grundwasservorkommen_-OGD.gpkg?csf=1&web=1&e=henbgz", 
}
