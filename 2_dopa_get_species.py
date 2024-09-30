import requests
import pandas as pd
from io import StringIO
import yaml
import os
import urllib.parse

"""

This block:
- fixes spelling of scientific names of species
- fetches IUCN IDs of species
- fetches all available columns by IUCN ID
- concatenates it into the table with all available columns for each species

INPUT
- Table of species with scientific names filled in by user. One column is required ('scientificName').
Format: CSV
Mandatory: yes


OUTPUT
- Combined table with scientific names of species and columns from IUCN.
Format: CSV
Mandatory: yes

"""

# open configuration files
with open('config.yaml', 'r') as file:
    config = yaml.safe_load(file)

# paths from the config file
input_dir = config['input_dir']
output_dir = config['output_dir']

# input file from the config
input_species_csv = os.path.join(input_dir, config['input_species'])
output_iucn_csv = os.path.join(output_dir, config['iucn_csv'])

# Debug: Print paths
print(f"Path to the input CSV with scientific names: {input_species_csv}")
print(f"Path to the output CSV with IUCN data: {output_iucn_csv}")
print('-' * 40)


# 1st function to fetch IUCN IDs by scientific names
def fetch_id_from_name_IUCN(scientific_name):
    """
    Fetches IUCN species IDs through the DOPA REST service.

    Parameters:
    - species_name: The scientific name of the species.

    Returns:
    - IUCN ID or None if not found.
    """
    url = "https://dopa-services.jrc.ec.europa.eu/services/d6dopa/dopa_43/get_dopa_species_list"
    params = {
        "format": "json",
        "f_binomial": scientific_name,
        "includemetadata": "true",
        "fields": "id_no"
    }

    encoded_params = urllib.parse.urlencode(params, quote_via=urllib.parse.quote)
    response = requests.get(url, params=encoded_params)

    try:
        if response.status_code in [200, 201]:
            response_data = response.json()
            if 'records' in response_data and len(response_data['records']) > 0:
                iucn_id = response_data['records'][0]['id_no']
                print(f"Unique IUCN ID for {scientific_name}: {iucn_id}")
                return iucn_id
            else:
                print(f"No IUCN ID found for species: {scientific_name}")
                return None
        else:
            print(f"Error fetching IUCN ID for {scientific_name}: {response.status_code}")
            return None
    except requests.exceptions.RequestException as e:
        print(f"An error occurred: {e}")
        return None


# 2nd function to fetch all available data by IUCN IDs
def fetch_IUCN_data_by_id(iucn_id):
    """
    Fetches IUCN data (habitats, threats, etc.) by IUCN IDs through the DOPA REST service for each species.

    Parameters:
    - a_id_no: IUCN unique ID of the species.

    Returns:
    - IUCN data as a dictionary or None if not found.
    """
    url = "https://dopa-services.jrc.ec.europa.eu/services/d6dopa/dopa_43/get_dopa_species"
    params = {
        "format": "json",
        "a_id_no": iucn_id,
        "includemetadata": "true",
        "fields": "binomial,research_needed_code,genus,family,research_needed_name,order_,class,id_no,"
                  "conservation_needed_code,usetrade_code,conservation_needed_name,ecosystems,habitat_code,"
                  "usetrade_name,habitat_name,country_code,country_name,stress_code,stress_name,threat_code,"
                  "threat_name,endemic,country_n,threatened,category"
    }

    try:
        response = requests.get(url, params=params)
        if response.status_code in [200, 201]:
            species_data = response.json()
            if 'records' in species_data and len(species_data['records']) > 1:
                print(f"Detailed IUCN data found for ID: {iucn_id}.")
                return species_data
            else:
                print(f"No detailed IUCN data found for ID: {iucn_id}.")
                return None
        else:
            print(f"Error fetching species details for ID: {iucn_id}: {response.status_code}")
            return None
    except requests.exceptions.RequestException as e:
        print(f"An error occurred: {e}")
        return None


# main function to fetch IUCN data using species names from the CSV
def dopa_fetch_iucn(input_species_csv):
    """
    Fetches IUCN species data from the DOPA REST service for species listed in an input CSV file.

    Parameters:
    - input_species_csv: A path to the input CSV file with the scientific names of species.

    Returns:
    - df_list: A list of dataframes, each containing data for one species.
    """
    df_list = []

    # read species names directly from the CSV
    try:
        species_df = pd.read_csv(input_species_csv)
        first_column = species_df.iloc[:, 0]
        species_list = first_column.tolist()
    except (FileNotFoundError, KeyError) as e:
        print(f"Error reading species from CSV: {e}")
        return []

    for species_name in species_list:
        # Step 1: fetch the IUCN ID using the species name
        iucn_id = fetch_id_from_name_IUCN(species_name)
        if iucn_id:
            # Step 2: fetch full IUCN data using the IUCN ID
            iucn_data = fetch_IUCN_data_by_id(iucn_id)
            if iucn_data:
                # convert JSON to dataframe
                df = pd.DataFrame(iucn_data['records'])
                df_list.append(df)
                print('-'*40)
            else:
                print(f"No detailed data found for {species_name}.")
                print('-'*40)
        else:
            print(f"No IUCN ID found for {species_name}.")
            print('-'*40)
    
    return df_list


# fetch the data and list of species, get a list of dataframes
df_list = dopa_fetch_iucn(input_species_csv)

# combine all dataframes into one
combined_df = pd.concat(df_list, ignore_index=True, sort=False)

# group the dataframe by 'id_no'
grouped_df = combined_df.groupby('id_no')

# concatenate values for the rest of the columns
concat_columns = combined_df.drop(columns = ['id_no']).columns.tolist() # create a list of all columns, excluding ID

# select only the columns that need to be concatenated
df_columns_to_concat = grouped_df[concat_columns]

# define a function to concatenate non-null, unique values with '|'
def concatenate_unique_values(column):
    return '|'.join(column.dropna().astype(str).unique()) # remove null values, convert to string, choose only unique values and concatenate with '|' separator
# apply the concatenation function to each column in the group
concatenated_df = df_columns_to_concat.agg(concatenate_unique_values)

# reset the index so that 'id_no' becomes a regular column again
df_final = concatenated_df.reset_index()

# save the final dataframe to a new CSV file
df_final.to_csv(output_iucn_csv, index=False, sep='|')
print (f"Data from IUCN has been fetched and concatenated for the species in {input_species_csv}")

# TODO - to implement other scopes of IUCN assessment, continental and regional ones(not only global ones): https://www.iucnredlist.org/regions/european-red-list, https://www.iucnredlist.org/regions/mediterranean-red-lis

# TODO - check Catalonian red list through Datos Gob ES API: https://datos.gob.es/es/apidata (not through Socrata API). SPARQL available: https://datos.gob.es/en/sparql
