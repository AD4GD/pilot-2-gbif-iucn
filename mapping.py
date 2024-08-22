# "pip install openpyxl" to work with xslx through pandas
import pandas as pd
import argparse

"""
Attempt to combine GBIF-derived datacube with tabular GBIF, IUCN and other (national and regional Red Lists) through a command line tool.
"""

# TODO - needs to be rewritten as the vice-versa direction of workflow is more meaningful (enriching list of species with other data sources and extracting datacube for the subset of species)


# for compound arguments with subarguments: to parse pairs of key (subargument) and value (value of subargument)
class ValidateKeyValuePairs(argparse.Action):
    """
    argparse action to parse KEY=VALUE pairs and validate them.
    """
    def __call__(self, parser, args, values, option_string=None):
        required_keys = {'path', 'columns_to_join', 'protection_category'}
        try:
            d = dict(map(lambda x: x.split('=', 1), values)) # splitting string into two parts using = as a separator (only first symbol)
            print (d)
        except ValueError as ex:
            raise argparse.ArgumentError(self, f"Could not parse argument \"{values}\" as key=value pairs.")
        
        missing_keys = required_keys - d.keys() # d.keys() is a view object of keys in dictionary
        extra_keys = d.keys() - required_keys

        if missing_keys:
            raise argparse.ArgumentError(self, f"Missing required keys: {missing_keys}") # if user didn't specified some keys
        if extra_keys:
            raise argparse.ArgumentError(self, f"Unexpected keys: {extra_keys}") # if user specified more keys
        
        setattr(args, self.dest, d) # setting the attribute on args from self.dest which is user-determined name (used in add_atribute method), and assign value from d dictionary


## Specify command-line interface for this plugin
# to run in command line:
# python SCRIPT_NAME.py path_to_gbif_csv path_to_iucn_habitat_csv path_to_iucn_categories_csv path_to_national_redlist_xlsx path_to_regional_redlist_csv path_to_output_csv path_to_iucn_output
# set up command-line argument parsing
parser = argparse.ArgumentParser(prog = "gbif_enrich", description='Harmonisation of species data (IUCN, GBIF, custom Red Lists)')
parser.add_argument('-fetch_IUCN', type=str, choices=['yes', 'no'], required=True, help='Specify whether to fetch IUCN data: yes or no')
parser.add_argument('gbif', help='Path to GBIF occurrence data (CSV)')
parser.add_argument('output', help='Path to the output enriched dataset (CSV)')
parser.add_argument('-IUCN_habitat', help='Path to IUCN habitat file (CSV)') # optional argument
parser.add_argument('-IUCN_categories', help='Path to IUCN categories file (CSV)') # optional argument
# parser.add_argument('-national_redlist', help='Path to national redlist dataset (XSLX or CSV)') # optional argument, CSV should be supported as well
# parser.add_argument('-regional_redlist', help='Path to regional redlist dataset (CSV)') # optional argument
parser.add_argument('-log_level', help='Set the logging level (e.g., DEBUG, INFO, WARNING)', default='DEBUG') # optional argument to look up issues

# add compound arguments with subarguments using key-value pairs
# for national redlist 
parser.add_argument('-national_redlist', 
                    nargs=3, 
                    action=ValidateKeyValuePairs, # call class defined above
                    metavar="KEY=VALUE", 
                    help='Specify the national redlist parameters as: path=path/to/file columns_to_join="column_1,column_2" protection_category="category". "columns to join" is not restricted by any number, while protection_category can be only one.')

# for regional redlist
parser.add_argument('-regional_redlist', 
                    nargs=3, 
                    action=ValidateKeyValuePairs, # call class defined above
                    metavar="KEY=VALUE", 
                    help='Specify the regional redlist parameters as: path=path/to/file columns_to_join="column_1,column_2" protection_category="category". "columns to join" is not restricted by any number, while protection_category can be only one.')

# parse arguments
args = parser.parse_args() # process arguments returned as argparse.Namespace object and write them into a variable

"""
# add subparsers - or TODO - move to subarguments (class KeyValuePairsAction)
subparsers = parser.add_subparsers(dest='operation') 

# add subparser for the national redlist
national_redlist_parser = subparsers.add_parser('national_redlist', help='National redlist dataset (XSLX or CSV)') # define subparser for national redlist
national_redlist_parser.add_argument ('--path', type=str, help = 'Path to the national redlist dataset (XSLX or CSV)') 
national_redlist_parser.add_argument ('--columns_to_join', type=str, nargs='+', help = 'Columns from the national redlust dataset to be joined') # Typically it is just one column (protection category), but might be more (therefore, 'nargs' = '+'))
national_redlist_parser.add_argument('--protection_category', type=str, help='Specify which column is the protection category of species')

# TODO - to add subarguments for regional redlist as well
"""

# assign file paths from command-line arguments (see parser.add_argument)
gbif_csv = args.gbif
iucn_habitat_csv = args.IUCN_habitat
iucn_categories_csv = args.IUCN_categories
national_redlist = args.national_redlist
regional_redlist_csv = args.regional_redlist
iucn_output = args.output

# conditional requirement check on fetching data from IUCN
if args.fetch_IUCN == 'yes':
    if not args.IUCN_habitat or not args.IUCN_categories:
        parser.error("--IUCN_habitat and --IUCN_categories are required when --fetch_iucn is 'yes'") # it will stop the script and raise the error

# assign flag on fetching data from IUCN (true or false)
fetch_iucn = args.fetch_IUCN


# open GBIF data (CSV)
df = pd.read_csv(gbif_csv)

# TODO - to add filtering by bbox of area needed

# drop attributes unique by record (date, location and basis of record)
columns_to_drop = ['yearmonth', 'lat', 'lon', 'basisofrecord', 'x_cart', 'y_cart', 'bbox']
# add new attributes from IUCN describing other scopes of assessment by IUCN + data on habitat importance
columns_to_add = [
    'IUCNGlobalScopeCategory',
    'IUCNEuropeScopeCategory',
    'IUCNMediterrScopeCategory', # to find categories from different scopes of assessment
    'OtherNationalCategory', # to find categories from national redlist, eg Spain
    'OtherRegionalCategory', # to find categories from regional redlist, eg Catalonia
    'IUCNHabitatCodes', # to find all habitat codes from IUCN that particular species might inhabit
    'IUCNSuitability_Suitable', # to list all habitat codes which are suitable for particular species
    'IUCNMajorImportance_Yes', # to list habitat codes only which are suitable species from the previous column
    'Analysis', # to choose whether species are suitable for calculations of habitat connectivity - boolean values
    'Note' # any other researcher-derived comments
]

# perform dropping attributes
df_filtered = df.drop(columns=columns_to_drop)

# perform adding attributes through pd_concat
df_filtered = pd.concat([df_filtered, pd.DataFrame(columns=columns_to_add)])

# filter to keep only rows with unique 'specieskey'
df_unique_species = df_filtered.drop_duplicates(subset=['specieskey'])

if fetch_iucn == 'yes': # if user specified to fetch data from IUCN
    print ("Fetching IUCN data...")
    # load iucn_habitat_csv into dataframe
    df_iucn_habitat = pd.read_csv(iucn_habitat_csv)

    # to choose columns if they are deriving from IUCN
    columns_to_add_iucn = [col for col in df_iucn_habitat.columns if col.lower().startswith('iucn')]
    print (f"Columns to link with GBIF data from IUCN are: {columns_to_add_iucn}")

    # to map species name with corresponding data from IUCN on habitats (currently fetched manually through IUCN search)
    # loop over columns of IUCN data to find and update matching columns in GBIF intermediate dataframe

    for col in columns_to_add:
        if col in columns_to_add_iucn:
            # map values from iucn_habitat_df to df_unique_specieskey - match of 'species' and 'speciesName'
            df_unique_species[col] = df_unique_species['species'].map(df_iucn_habitat.set_index('speciesName')[col])

    # update 'IUCNGlobalScopeCategory' with values from 'iucnredlistcategory'
    df_unique_species['IUCNGlobalScopeCategory'] = df_unique_species['iucnredlistcategory']
    # drop the 'iucnredlistcategory' column to have the same style of columns' names
    df_unique_species.drop(columns=['iucnredlistcategory'], inplace=True)
else:
    print ("Not fetching IUCN data.")



# TODO for habitats - perform automatically through DOPA-managed requests to IUCN database OR IUCN API v.4 once it is openly published
# https://dopa-services.jrc.ec.europa.eu/services/services/?dataset_name=IUCN_NSP
# functions:
# get_dopa_species
# get_dopa_species_list_category
# get_dopa_species_list_habitat
# get_dopa_species_list_threat

# TODO the same for IUCN continental and regional categories (not only global ones): https://www.iucnredlist.org/regions/european-red-list, https://www.iucnredlist.org/regions/mediterranean-red-lis


# TODO - implement lists for Spain and Catalonia:
# https://www.miteco.gob.es/es/biodiversidad/temas/conservacion-de-especies/especies-proteccion-especial/ce-proteccion-listado-situacion.html
# https://analisi.transparenciacatalunya.cat/en/Medi-Ambient/Esp-cies-protegides-i-amena-ades-de-la-fauna-aut-c/i8eg-aynu/about_data 
# https://datos.gob.es/en/catalogo/a09002970-especies-protegidas-y-amenazadas-de-la-fauna-autoctona-de-cataluna (another one)
# TODO - Catalonian red list through API: https://datos.gob.es/es/apidata. SPARQL available: https://datos.gob.es/en/sparql
# TODO - check JSON/RDF for Catalonian red list. Seems like there is also no valud unique id of species compliant with oter vocabularies

# 2. HARMONISE REGIONAL REDLIST

# retrieve path from dictionary object above as a value
regional_redlist_path = regional_redlist_csv.get('path')
# load regional redlist
df_regional_redlist = pd.read_csv(regional_redlist_path, encoding='utf-8')
# print heads of this dataframe
# print(df_regional_redlist.head())

"""
## THIS PART TO CHECK WHETHER THERE ANY MATCHES IN SPECIES NAME BETWEEN CSVs 
# convert species names to lowercase for case-insensitive comparison
unique_species_list = df_unique_species['species'].str.lower().tolist()
regional_redlist_list = df_regional_redlist['esp_cies_nom_cient_fic'].str.lower().tolist()
# create sets of species names in lowercase for case-insensitive comparison
unique_species_set = set(df_unique_species['species'].str.lower())
regional_redlist_set = set(df_regional_redlist['esp_cies_nom_cient_fic'].str.lower())
# find the intersection between two sets
matches = unique_species_set.intersection(regional_redlist_set)
num_matches = len(matches)
print(f"Number of matches (case-insensitive): {num_matches}")


# find matches where species names are substrings of each other (parts of names to handle cases like "Lynx pardina (= L. pardinus)")
matches = set()
for unique_species in unique_species_list:
    for regional_species in regional_redlist_list:
        if unique_species in regional_species or regional_species in unique_species:
            matches.add((unique_species, regional_species))

# print unique matches 
for match in matches:
    print(f"Matched pair: {match[0]} - {match[1]}")
# calculate the number of unique matches
num_matches = len(matches)
print(f"Number of matches (case-insensitive, including substrings): {num_matches}")
"""

## Map regional categories with GBIF-derived data
# create temporary columns - convert species names to lowercase for case-insensitive comparison
df_unique_species['species_lower'] = df_unique_species['species'].str.lower()
df_regional_redlist['esp_cies_nom_cient_fic_lower'] = df_regional_redlist['esp_cies_nom_cient_fic'].str.lower()

# define function to generate possible abbreviations from a species name (genus name shorthanded, eg L. pardinus)
def generate_abbreviations(name):
    parts = name.split()
    # generate abbreviations using the first letter of each part
    abbreviations = [f"{part[0]}." for part in parts if len(part) > 1]
    return [name] + abbreviations

# build abbreviation dictionary for lookup
abbreviation_dict = {}
for name in df_unique_species['species']:
    expanded_name = name.lower()
    abbreviations = generate_abbreviations(expanded_name)
    abbreviation_dict[expanded_name] = abbreviations
# print (abbreviation_dict) # for troubleshooting

# define function to check if one name matches another or if their abbreviations match
def is_match(name_1, name_2, abbreviation_dict):
    # check if names match exactly
    if name_1 == name_2:
        return True
    # check if name_1 or name_2 is in the list of abbreviations for the other
    abbreviations_1 = abbreviation_dict.get(name_1, [])
    return any(abbr in name_2 for abbr in abbreviations_1) or any(name_2 in abbr for abbr in abbreviations_1)

# iterate over df_unique_specieskey and update CataloniaCategory if there is a match
for i, unique_row in df_unique_species.iterrows():
    unique_species = unique_row['species_lower']
    for j, regional_row in df_regional_redlist.iterrows(): # i and j as indices in dataframes
        regional_species = regional_row['esp_cies_nom_cient_fic_lower']
        if is_match(unique_species, regional_species, abbreviation_dict): # is species name has been met anywhere (see function above)
            df_unique_species.at[i, 'OtherRegionalCategory'] = regional_row['categoria_cat_leg'] # perform mapping (was 'Categoria \ncatàleg' in file downloaded directly from the website, not through API)
            break  # stop after the first match for this species

# 3. HARMONISE NATIONAL REDLIST

# retrieve path from dictionary object above as a value
national_redlist_path=national_redlist.get('path')
if national_redlist_path.endswith('.xlsx'): # if input file is xlsx

    # load national redlist - Excel file and the sheet 2 (index = 1)
    df_national_redlist = pd.read_excel(national_redlist_path, sheet_name=1) # load from the value from dictionary object
    print('-'*30)
    print("Headers in the dataset on National Red List:")
    print(df_national_redlist.columns)

    df_national_redlist['Nombre científico actualizado_lower'] = df_national_redlist['Nombre científico actualizado '].str.lower() # create temporary column with lowercase valies

    # loop over df_unique_species and update SpainCategory if there is a match
    for i, unique_row in df_unique_species.iterrows():
        unique_species = unique_row['species_lower']  # case-insensitive temporary column
        if pd.notna(unique_species):
            for j, national_row in df_national_redlist.iterrows():
                national_species = national_row['Nombre científico actualizado_lower']
                if pd.notna(national_species) and (unique_species in national_species or national_species in unique_species):
                    df_unique_species.at[i, 'OtherNationalCategory'] = national_row['Listado de Especies Silvestres en Régimen de Protección Especial (LESRPE)/\nCategorías en el Catálogo Español de Especies Amenazadas (CEEA)']
                    break  # stop after the first match for this species

elif national_redlist.endswith('.csv'): # if input file is csv
    # load national redlist
    df_national_redlist = pd.read_csv(national_redlist, encoding='utf-8')
    # TODO - add block on [ronan;e csv]
else:
    print ("National Red List file format is not supported.")

# TODO - to aks user to define columns required for processing (scientific name)

# drop temporary lowercase columns
df_unique_species.drop(columns=['species_lower'], inplace=True)
df_regional_redlist.drop(columns=['esp_cies_nom_cient_fic_lower'], inplace=True)
df_national_redlist.drop(columns=['Nombre científico actualizado_lower'], inplace=True)

# for troubleshooting
# print(df_unique_species.columns) 

# printing statements
print('-'*30)
print ("Extracted regional protection categories are:")
print (df_unique_species['OtherRegionalCategory'].unique()) # extract unique values from categories

# TODO - to include some mapping vocabulary from Catalan/Spanish to English?
# TODO - clarify meaning of categories

# save the filtered dataframe to a new csv file
df_unique_species.to_csv(iucn_output, index=False, encoding = 'utf-8')
print('-'*30)
print(f"Filtered data for each unique species saved to {iucn_output}")

# TODO - to check other API for regional dataset on rare and endangered species: https://datos.gob.es/en/apidata

"""
# TO MAP manual csv with habitat codes to data on global IUCN categories
# Load the CSV and Excel files into pandas DataFrames
df1 = pd.read_csv(gbif_csv)
df2 = pd.read_excel(iucn_xslx)

# cast column to string data type
df2['IucnGlobalScopeCategory'] = df2['IucnGlobalScopeCategory'].astype(str)

# Create a dictionary from df1 for quick lookup with zip to combine two sequences
species_to_iucn = dict(zip(df1['species'], df1['iucnredlistcategory']))

print (species_to_iucn)

# Iterate over the rows of df2 to update the 'IucnGlobalScopeCategory' column
for index, row in df2.iterrows():
    species_name = row['speciesName']
    if species_name in species_to_iucn: #if species found in
        df2.at[index, 'IucnGlobalScopeCategory'] = species_to_iucn[species_name]

# Save the updated DataFrame to the original Excel file
iucn_output = r'C:\\Users\\kriukovv\\Documents\\gbif\\output\\iucn_gbif_habitat_mapped.xlsx'
df2.to_excel(iucn_output, index=False)
print("Mapping with global IUCN categories completed.")
"""

"""
## TO DEFINE INPUT AND OUTPUT DATA PATHS MANUALLY
import os

input_dir = r'input'
output_dir = r'output'
# define input files
gbif_csv = os.path.join(output_dir, 'filtered_datacube.csv') # GBIF occurrence data aligned with custom grid through previous preprocessing
print(gbif_csv)
iucn_habitat_csv = os.path.join(output_dir, 'iucn_habitat.csv') # IUCN data on habitats for each species
iucn_categories_csv = os.path.join(output_dir,'iucn_categories.csv') # to add other scopes of assessment (continent, large region)
national_redlist_xlsx = os.path.join(input_dir,'national_redlist.xlsx')  # to add national redlists, eg Spain
regional_redlist_csv = os.path.join(input_dir, 'red_lists', 'regional_redlist_api.csv') # to add regional redlists, eg Catalonia
# define output data
iucn_csv = os.path.join(output_dir,'enriched_datacube.csv') # enriched GBIF ocurrence data with data on habitats and protection categories
"""
