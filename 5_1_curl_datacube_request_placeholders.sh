## DEPENDENCIES
# to run this block in Anaconda prompt on local machine (Windows):
# "C:\Users\kriukovv\AppData\Local\Programs\Git\bin\sh.exe" 5_1_curl_datacube_request_placeholders.sh (use your local path for bash.exe)
# if it doesn't work, try "C:\Users\kriukovv\AppData\Local\Programs\Git\bin\bash.exe" 5_1_curl_datacube_request_placeholders.sh
# in Powershell: & "C:\Users\kriukovv\AppData\Local\Programs\Git\bin\sh.exe" -- 5_1_curl_datacube_request_placeholders.sh

# required: to install jq, yq and curl 
# on Windows, jq installed manually as executable through official page (https://jqlang.github.io/jq/download/) and editing environment variables-path
# yq package installed through scoop: https://github.com/mikefarah/yq?tab=readme-ov-file

## ACCESS
# required: to have GBIF user registration: https://www.gbif.org/user/profile

## INPUT (all inputs are specified by user in config_gbif.json file)
# - taxon key pr keys (unique identifier) in GBIF for class(es) or species, depending on user choice (for example, https://www.gbif.org/species/212)
# - year (minimum year in date of GBIF occurrence), depending on user choice
# - country to extract GBIF occurrence data for, depending on user choice
# - GBIF user credentials 
# All inputs are mandatory

## OUTPUT (filename and path are specified by user in config_gbif.json file)
# - list of all occurrence records for specified filters on taxons, years, countries and data issues, CSV (mandatory)
# - metadata for the CSV output with DOI (which is scheduled to be erased), JSON (mandatory)
# - (under development) metadata on licences of all data sources comprising the first output, CSV (optional?). In the end, should be ingested into the JSON output (replace value for 'license' key).

# this block also dynamically updates config.yaml file (two values - 'gbif_datacube_csv' and 'gbif_taxon_key' for further processing)

## ISSUES AND LIMITATIONS
# 1. No more than 3 concurrent downloads for a standard user allowed.
# 2. Some of large requests might become frozen without any visible outcome (probably due to internet issues), while being active and successful on https://www.gbif.org/user/download
# 3. GBIF backbone taxonomy does not define Reptilia as a separate class (class with id=358 dedicated to Reptilia database fetches 0 downloaded records). For the purposes of the case study, two Reptilia classes (Testudines, taxon key 11418114) and (Squamata, taxon key, 11592253) have been used.

## HELP
# GBIF occurrence datacube: https://techdocs.gbif.org/en/data-use/data-cubes
# GBIF licence metadata: https://techdocs.gbif.org/en/data-use/b-cubed/generate-cube-databricks#generating-cube-metadata
# To check outputs on GBIF, cancel requests etc: https://www.gbif.org/user/download



## PROCESSING

## Extract year of record, classKey and credentials from the configuration file and prepare the JSON request
# assign the variables from config_gbif.json
classKey=$(jq -r '.classKey' config_gbif.json) # -r extracts raw output without any quotes
speciesKey=$(jq -r '.speciesKey' config_gbif.json)
country=$(jq -r '.country' config_gbif.json)
year=$(jq -r '.min_year' config_gbif.json)
notificationEmail=$(jq -r '.notificationEmail' config_gbif.json)
username=$(jq -r '.username' config_gbif.json)
password=$(jq -r '.password' config_gbif.json)
output_dir_gbif=$(jq -r '.output_dir_gbif' config_gbif.json)
gbif_query_classes=$(jq -r '.gbif_query_classes' config_gbif.json) # to choose query to extract classes
gbif_query_species=$(jq -r '.gbif_query_species' config_gbif.json) # to choose query to extract species
gbif_query_classes_metadata=$(jq -r '.gbif_query_classes_metadata' config_gbif.json) # to choose query to extract licence metadata for classes
gbif_query_species_metadata=$(jq -r '.gbif_query_species_metadata' config_gbif.json) # to choose query to extract licence metadata for species

# if multiple classes - converting the list from json file to comma-separated list, otherwise bring it just as a string (for SQL syntax)
classKey_to_edit=$(jq -r '
  if (.classKey | type == "array") then
    .classKey | join(",")
  else
    .classKey | tostring
  end
' config_gbif.json)
# remove any leading or trailing whitespace
classKey_to_edit=$(echo "$classKey_to_edit" | xargs)
# format the speciesKey correctly for SQL (in parentheses)
classKey="($classKey_to_edit)"
echo "$classKey" # debug

# if multiple species - converting the list from json file to comma-separated list, otherwise bring it just as a string (for SQL syntax)
speciesKey_to_edit=$(jq -r '
  if (.speciesKey | type == "array") then
    .speciesKey | join(",")
  else
    .speciesKey | tostring
  end
' config_gbif.json)
# remove any leading or trailing whitespace
speciesKey_to_edit=$(echo "$speciesKey_to_edit" | xargs)
# format the speciesKey correctly for SQL (in parentheses)
speciesKey="($speciesKey_to_edit)"
echo "$speciesKey" # debug

# SQL supports 'classKey IN (358)' for single and multiple (classKey IN (358,212)) features, so no need to create queries for single taxon separately (calssKey=358)

# to use further: normalize speciesKey by converting to lowercase and removing parentheses
norm_speciesKey=$(echo "$speciesKey" | tr '[:upper:]' '[:lower:]' | tr -d '()')

# echo the variables to check the values
echo "Class key: $classKey"
echo "Species key: $speciesKey"
echo "Country code: $country"
echo "Minimum year of record: $year"
echo "Notification email: $notificationEmail"
echo "Username: $username"
echo "Password: [Hidden for security]"
echo "Query to GBIF datacube (classes): $gbif_query_classes"
echo "Query to GBIF datacube (species): $gbif_query_species"

## to specify taxon key from config file - if species key is not defined, then use class key
# check if speciesKey is empty or one of the invalid values
if [[ -z "$norm_speciesKey" || "$norm_speciesKey" =~ ^(none|null|nan|nodata|no_data|0)$ ]]; then # list possible values for defining no data
    echo "speciesKey is not defined. Using classKey instead."
    taxonKey="$classKey"
    gbif_query="$gbif_query_classes"
    gbif_query_metadata="$gbif_query_classes_metadata" # ancillary to get licence metadata
else
    echo "speciesKey is defined. Using speciesKey."
    taxonKey="$speciesKey"
    gbif_query="$gbif_query_species"
    gbif_query_metadata="$gbif_query_species_metadata" # ancillary to get licence metadata
fi

# to remove
# taxonKey=$(echo "$taxonKey" | tr '[:upper:]' '[:lower:]' | tr -d '()')
# speciesKey="$taxonKey"
#classKey="$taxonKey"
# echo "$speciesKey"
# echo "$classKey"

echo "Taxon key to extract GBIF datacube: $taxonKey"
echo "Query to access GBIF datacube: $gbif_query"

# TODO - to test multiple countries
# TODO - to include a case when classKey is empty 

# prepare the JSON request by substituting values - defining arguments and replacing placeholders with variables from the configuration file
jq --arg classKey "$classKey" \
   --arg speciesKey "$speciesKey" \
   --arg country "$country" \
   --arg year "$year" \
   --arg notificationEmail "$notificationEmail" \
   '
   .notificationAddresses[0] |= $notificationEmail |
   .sql |= sub("\\{\\{year\\}\\}"; $year) |
   .sql |= sub("\\{\\{classKey\\}\\}"; $classKey) |
   .sql |= sub("\\{\\{speciesKey\\}\\}"; $speciesKey) |
   .sql |= sub("\\{\\{country\\}\\}"; $country)
   ' "$gbif_query" > prepared_request.json

# debug: echo the prepared JSON request to check if it looks correct
echo "Prepared Request:"
cat prepared_request.json
printf '%0.s-' {1..40}; printf '\n' # %0.s means to print - without any arguments

# use curl to send the request
response=$(curl --include \
     --user "$username:$password" \
     --header "Content-Type: application/json" \
     --data @prepared_request.json \
     https://api.gbif.org/v1/occurrence/download/request)

# \ is used to continue the command on the next line

# debug: print the entire HTTP response
echo "Full HTTP Response:"
echo -e "\n$response"
printf '%0.s-' {1..40}; printf '\n'

# TODO - if http code == 40*, raise error and break, if == 20* - keep running.
# probably should be done through saving headers as temporary txt and then extract http code from there


# to extract the download code
download_code=$(echo "$response" | tail -n 1)

# previous expression: extract the download code from the last non-empty line of the response body (isolates the part of the response that starts after download/)
# download_code=$(echo "$response" | grep -oP 'download/\K[^\"]+')

echo -e "\nDownload Code: $download_code"

# use the download code to check the status and download the data
if [[ "$download_code" != "null" ]]; then
  echo -e "Fetching the download URL for code $download_code and taxon key $taxonKey... \n It may take dozens of minutes, depending on the size of data fetched." # -e enables identification of backlash escapes
  
  # wait until the download is ready, and then download it
  status="RUNNING"
  while [[ "$status" == "RUNNING" || "$status" == "PENDING" || "$status" == "PREPARING" || "$status" == "" ]]; do
    sleep 120 # wait before checking the status again (increased from 60 to reduce frequency of requests)
    status_response=$(curl -v -L -Ss  "https://api.gbif.org/v1/occurrence/download/${download_code}") # enable verbose logging
    status=$(echo "$status_response" | jq -r '.status') # extract raw text from the status of the response
    echo "Current status: $status"
  done

  # TODO - to check what other statuses might be (apart from mentioned above)
  # TODO (to consider usage of Schannel on Windows):
  # - * schannel: disabled automatic use of client certificate
  # * schannel: failed to decrypt data, need more data

  # if the status is 'SUCCEEDED', download the file
  if [[ "$status" == "SUCCEEDED" ]]; then
    echo "Download ready. Fetching the file..."

    # define the output filename
    filename="key_${taxonKey}_${download_code}.zip"
    # TODO - truncate filename if it is too long - many species. Particular species/classes can be extracted from metadata (json)

    # added just in case as zip file had been brought empty
    sleep 20

    # download the file
    curl --max-time 600 -L -Ss "https://api.gbif.org/v1/occurrence/download/request/${download_code}" -o "${filename}" # enable verbose logging
    echo "Download completed: ${filename}"

    # ensure the output directory exists before moving the output
    mkdir -p "${output_dir_gbif}" # but doesn't cause errors if directory already exists

    # move the .zip file to the output directory
    mv "$filename" "${output_dir_gbif}/${filename}"

    # unzip the file
    echo "Unzipping ${filename}..."
    if unzip "${output_dir_gbif}/${filename}" -d "${output_dir_gbif}/temp_unzip"; then
        echo "Unzipping completed."

        # find the .csv file
        csv_file=$(find "${output_dir_gbif}/temp_unzip" -type f -name "*.csv")

        # extract the base name of the CSV file (without directory and extension)
        base_csv_name=$(basename "$csv_file")

        # rename csv file, adding the taxon key
        mv "$csv_file" "${output_dir_gbif}/key_${taxonKey}_${base_csv_name}"

        # remove the temporary directory
        rm -r "${output_dir_gbif}/temp_unzip"

        # delete the zip file after successful extraction
        rm "${output_dir_gbif}/${filename}"
        echo "Deleted the zip file."
    else
        echo "Unzipping failed. Zip file will not be deleted."
    fi

    # to save metadata (anonymized?)
    curl -Ss "https://api.gbif.org/v1/occurrence/download/${download_code}" -o "${output_dir_gbif}/${filename%.zip}.json" #-S means show errors, but -s means silent mode
    echo "Metadata saved for: ${filename%.zip}."
    printf '%0.s-' {1..40}; printf '\n'
  else
    echo "Download failed or still processing."
    printf '%0.s-' {1..40}; printf '\n'
  fi

else
  echo "Failed to get download code."
  printf '%0.s-' {1..40}; printf '\n'
fi

# delete the intermediate json file with the prepared request
rm "prepared_request.json"

# use yq to update the filename of gbif datacube in the YAML file
yq eval ".gbif_datacube_csv = \"${filename%.zip}.csv\"" -i config.yaml

# use yq to write the taxon key to the YAML file
yq eval ".gbif_taxon_key = \"${taxonKey}\"" -i config.yaml


## FETCHING LICENCE METADATA - https://techdocs.gbif.org/en/data-use/b-cubed/generate-cube-databricks#generating-cube-metadata
# TODO - to revisit the following block and transform it to another datacube (with request status, unzipping output etc.). 
# Currently fetches csv with all datasets and their licence policy. Finally, it should choose the most strict one (https://techdocs.gbif.org/en/data-use/b-cubed/generate-cube-databricks#generating-cube-metadata) and replace the value for 'license' key in other json.

# preparing query with placeholders from variable
jq --arg classKey "$classKey" \
   --arg speciesKey "$speciesKey" \
   --arg country "$country" \
   --arg year "$year" \
   --arg notificationEmail "$notificationEmail" \
   '
   .notificationAddresses[0] |= $notificationEmail |
   .sql |= sub("\\{\\{year\\}\\}"; $year) |
   .sql |= sub("\\{\\{classKey\\}\\}"; $classKey) |
   .sql |= sub("\\{\\{speciesKey\\}\\}"; $speciesKey) |
   .sql |= sub("\\{\\{country\\}\\}"; $country)
   ' "$gbif_query_metadata" > prepared_request_metadata.json

# prepare curl query
response_metadata=$(curl --include \
     --user "$username:$password" \
     --header "Content-Type: application/json" \
     --data @prepared_request_metadata.json \
     https://api.gbif.org/v1/occurrence/download/request)


# debug: print the entire HTTP response for licence metadata
echo "Metadata licence: response:"
echo -e "\n$response_metadata"
printf '%0.s-' {1..40}; printf '\n'

# to extract the download code
download_code_licence=$(echo "$response_metadata" | tail -n 1)
echo "Download code for licence metadata: $download_code_licence"
printf '%0.s-' {1..40}; printf '\n'

# delete the intermediate json file with the prepared request
rm "prepared_request_metadata.json"

# to save metadata on licence (anonymized?)
# curl -Ss "https://api.gbif.org/v1/occurrence/download/request/" -o "${output_dir_gbif}/${filename%.zip}_licence.json" #-S means show errors, but -s means silent mode
# echo "Licence metadata saved for: ${filename%.zip}_licence."
# printf '%0.s-' {1..40}; printf '\n'

