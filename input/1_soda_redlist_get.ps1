# THIS SCRIPT MUST BE RUN WITH A VALID APP TOKEN. OTHERWISE, IT WILL NOT WORK
# source dataset: https://dev.socrata.com/foundry/analisi.transparenciacatalunya.cat/i8eg-aynu

# ensure the script is running with UTF-8 encoding
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# define endpoint
$url = "https://analisi.transparenciacatalunya.cat/resource/i8eg-aynu.csv" # .json works as well

# define apptoken
$apptoken = "4gDwViWUUgxQqk4w8IuJ7KFj2" # insert "app symbol", not "id key" or "secret key"

# set header to accept JSON
$headers = New-Object "System.Collections.Generic.Dictionary[[String],[String]]"
$headers.Add("Accept","text/csv") # application/json works as well
$headers.Add("X-App-Token", $apptoken)

$results = Invoke-RestMethod -Uri $url -Method get -Headers $headers

# show results in a table
$results | ft

## TO SAVE AS CSV
# use Invoke-WebRequest to get SV data
$response = Invoke-WebRequest -Uri $url -Method Get -Headers $headers

# convert content to CSV
$csvContent = $response.Content

# define the output file path
$outputFilePath = "regional_redlist_api.csv"

# save CSV content to a file
$csvContent | Out-File -FilePath $outputFilePath -Encoding utf8

Write-Output "Data on regional species saved to $outputFilePath"

# TODO - language translation? - seems to be unavailable through specifications of the original dataset

