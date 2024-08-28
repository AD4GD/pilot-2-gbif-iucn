import os
import pandas as pd
import requests
import time
import yaml

# open configuration files
with open('config.yaml', 'r') as file:
    config = yaml.safe_load(file)

# paths from the config file
input_dir = config['input_dir']
output_dir = config['output_dir']

# input file from the config file
input_filename = config['input_species']
input_path = os.path.join(input_dir, input_filename)
input_path = os.path.normpath(input_path)
print (input_path)

# output file with fixed scientific names of the species and enriched with GBIF ID keys
output_filename = config['gbif_key_csv']
output_path = os.path.join(output_dir, output_filename)
output_path = os.path.normpath(output_path)
print (output_path)

"""
This block access GBIF Species Lookup tool through Species API: https://techdocs.gbif.org/en/openapi/v1/species#/Searching%20names/matchNames
Species names derive from the user-defined CSV or XSLX file with scientific names.

This tool is able to provide fuzzy matching (to cover synonyms of species names and spelling error) between scientific names and GBIF Taxon IDs, but common names of species are not supported.

Output: CSV with fixed scientific names and GBIF keys pointing out sub(species).
"""

# to fix scientific names of species
def fix_species_name(species_name):
    # GBIF Species Look-up tool endpoint
    url = "https://api.gbif.org/v1/species/match"
    params = {
        'name': species_name, # define species to be looked up from the variable
        'strict': 'false', # if true it fuzzy matches only the given name, but never a taxon in the upper classification.
        }
    
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Request failed for {species_name}: {e}")
        return None

# to fetch taxon IDs for fixed scientific names
def fetch_gbif_id(scientific_name):
    # use the scientific name to fetch GBIF ID
    url = "https://api.gbif.org/v1/species/search"
    params = {
        'datasetKey': 'd7dddbf4-2cf0-4f39-9b2a-bb099caae36c', # unique id of GBIF Backbone dataset (otherwise, keys from other datasets will be fetched)
        # TODO - try to implement 'datasetkey' = IUCN
        'q': scientific_name,
        'limit': 1, # only one value
        'offset': 0,
        #'rank': 'species' # exclude to bring subspecies as well
    }
    
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        
        results = data.get("results", [])
        if results:
            gbif_key = results[0].get("key") # GBIF key (might point out to subspecies it differentiated)
            gbif_species_key = results[0].get("speciesKey") # GBIF species key
            return gbif_key, gbif_species_key
        else:
            return None
        
    except requests.exceptions.RequestException as e:
        print(f"Request failed for {scientific_name}: {e}")
        return None

# to define output fields to fetch through Species APi
def process_species_data(data):
    if not data:
        return {}
    
    # cast the scientific name (previously fixed) to the variable
    scientific_name = data.get('scientificName', '')
    
    # listing all parameters
    return {
        "usageKey": data.get('usageKey', None),
        "acceptedUsageKey": data.get('acceptedUsageKey', None),
        "scientificName": scientific_name,
        "canonicalName": data.get('canonicalName', ''),
        "rank": data.get('rank', ''),
        "status": data.get('status', ''),
        "confidence": data.get('confidence', 0),
        "note": data.get('note', ''),
        "matchType": data.get('matchType', ''),
        #"alternatives": data.get('alternatives', []) # to show alternative scientific names
    }

# TODO - to bring the fixed name of species, not subspecies as DOPA REST service doesn't support them!

# Overarching function if input file is csv
def lookup_species_from_csv(file_path, output_path):
    try:
        # try reading the CSV with UTF-8 encoding
        df = pd.read_csv(file_path, encoding='utf-8')
    except UnicodeDecodeError:
        # if there is a Unicode error, try with a different encoding
        print("UTF-8 decoding failed. Trying ISO-8859-1 encoding...")
        df = pd.read_csv(file_path, encoding='ISO-8859-1')  # or 'Windows-1252'

    if df.empty:
        print("The CSV file is empty.")
        return
    
    # use the first column of input file without specifying its name
    first_column = df.iloc[:, 0]
    species_names = first_column.tolist()  # TODO - add as a parameter for function
    
    results = []  # list to store results
    
    for species_name in species_names:
        print(f"Fetching data for (sub)species: {species_name}")
        data = fix_species_name(species_name)
        species_info = process_species_data(data)
        if species_info:
            scientific_name = species_info.get('scientificName', '')
            gbif_key, gbif_species_key = fetch_gbif_id(scientific_name) # call the function to fetch GBIF Species ID for the fixed scientific name
            # species_info["inputName"] = species_name  # add the original species name to the output
            species_info['gbifKey'] = gbif_key
            species_info['gbifSpeciesKey'] = gbif_species_key
            results.append(species_info)

        time.sleep(1)
    
    # save results to CSV
    results_df = pd.DataFrame(results)
    results_df.to_csv(output_path, index=False)
    print(f"Final results saved to {output_path}")

# TODO - rewrite XLSX block to match CSV block
# Overarching function if input file is xlsx
def lookup_species_from_xlsx(file_path, output_path):
    df = pd.read_excel(file_path)
    if df.empty:
        print("The XLSX file is empty.")
        return
    
    # use the first column of input file without specifying its name
    first_column = df.iloc[:, 0]
    species_names = first_column.tolist()  # TODO - add as a parameter for function
    
    results = []  # list to storeresults
    
    for species_name in species_names:
        print(f"Fetching data for species: {species_name}")
        data = fix_species_name(species_name)
        species_info = process_species_data(data)
        if species_info:
            scientific_name = species_info.get('scientificName', '')
            gbif_id = fetch_gbif_id(scientific_name)
            species_info['gbifID'] = gbif_id
            results.append(species_info)

        time.sleep(1)
    
    # save final results to csv
    final_results_df = pd.DataFrame(results)
    final_results_df.to_csv(output_path, index=False)
    print(f"Final results saved to {output_path}")

# define function to choose from csv or xlsx formats
def map_gbif_id(input_path):
    # define the file extension
    _, file_extension = os.path.splitext(input_path) # split the filename to find the extension

    if file_extension.lower() == '.csv':
        lookup_species_from_csv(input_path, output_path)
    elif file_extension.lower() == '.xlsx':
        lookup_species_from_xlsx(input_path, output_path) # use different functions depending on the extension of input dataset
    else:
        print(f"Unsupported file type: {file_extension}. Please provide a .csv or .xlsx file.")

# usage
map_gbif_id(input_path)

# ISSUES
# 1. Subspecies which may be listed by user instead of species are not always assigned with correct GBIF IDs (sometimes with species IDs)
# 2. Code performance is significantly lower than front-end tool for lookup implemented by GBIF (without Taxon IDs): https://www.gbif.org/tools/species-lookup
# 3. Canonical name cannot be used for searching over GBIF Species Taxon IDs - wrong matches are possible. Only scientific name should be used
# 4. Plenty of keys (IDs) in GBIF (key, nameKey, nubKey, speciesKey) which may be confused
# 5. IUCN taxon ID of every species is different from unique id for this species written in the IUCN dataset embedded into GBIF backbone. Some redefining of IDs is conducted behind the ingestion of IUCN dataset into GBIF.
