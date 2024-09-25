# to run it in Anaconda prompt on local machine (Windows):
# "C:\Users\kriukovv\AppData\Local\Programs\Git\bin\sh.exe" 5_1_curl_datacube_request_placeholders.sh (use your local path for bash.exe)
# if it doesn't work, try "C:\Users\kriukovv\AppData\Local\Programs\Git\bin\bash.exe" 5_1_curl_datacube_request_placeholders.sh
# Powershell: & "C:\Users\kriukovv\AppData\Local\Programs\Git\bin\sh.exe" -- 5_1_curl_datacube_request_placeholders.sh

# required: to install jq, yq and curl (on Windows, jq installed manually through official page and editing environment variables-path)
# yq package installed through scoop: https://github.com/mikefarah/yq?tab=readme-ov-file

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

# to specify taxon key from config file - if species key is not defined, then use class key
# Determine the taxon key and gbif query based on speciesKey
if [ -z "$speciesKey" ]; then
    echo "speciesKey is empty or not defined. Using classKey instead."
    taxonKey="$classKey"
    gbif_query="$gbif_query_classes"
else
    echo "speciesKey is defined. Using speciesKey."
    taxonKey="$speciesKey"
    gbif_query="$gbif_query_species"
fi
echo "Taxon key to extract GBIF datacube: $taxonKey"
echo "Query to access GBIF datacube: $gbif_query"

# TODO - to test multiple countries

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
  while [[ "$status" == "RUNNING" || "$status" == "PREPARING" ]]; do
    sleep 120 # wait before checking the status again (increased from 60 to reduce frequency of requests)
    status_response=$(curl -v -L -Ss "https://api.gbif.org/v1/occurrence/download/${download_code}") # enable verbose logging
    status=$(echo "$status_response" | jq -r '.status') # extract raw text from the status of the response
    echo "Current status: $status"
  done

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
    mkdir -p "${output_dir_gbif}" # don't cause errors if directory already exists

    # move the .zip file to the output directory
    mv "$filename" "${output_dir_gbif}/${filename}"

    # unzip the file
    echo "Unzipping ${filename}..."
    if unzip "${output_dir_gbif}/${filename}" -d "${output_dir_gbif}/temp_unzip"; then # TODO - unzip to the same folder and apply the key number berfore the filename
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