# THIS SCRIPT MUST BE RUN WITH A VALID APP TOKEN. OTHERWISE, IT WILL NOT WORK
# source dataset: https://dev.socrata.com/foundry/analisi.transparenciacatalunya.cat/i8eg-aynu

# ensure the script is running with UTF-8 encoding
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# define endpoint
$url = "https://analisi.transparenciacatalunya.cat/resource/i8eg-aynu.json" # native one

# define apptoken
$apptoken = "4gDwViWUUgxQqk4w8IuJ7KFj2" # insert "app symbol", not "id key" or "secret key"

# define query to filter out non-mammal species
# single quotation mark is not recognised through this condition, so workarounds needed
# $whereCondition = "classe='Invertebrat'" # this condition works
$whereCondition = 'classe="Mamífer"'

# URL-encode the filter condition
$encodedWhere = [System.Web.HttpUtility]::UrlEncode($whereCondition)
# $encodedWhere = [System.Net.WebUtility]::UrlEncode($whereCondition) # another solution
$encodedWhere = $encodedWhere -replace '%c3%83%c2%ad', '%C3%AD' # introduced because of the unknown issue with encoding

Write-Output "SQL Query: $encodedWhere"

# construct the full URL with the encoded query
$url_filter = "$url`?$where`$where=" + $encodedWhere # $where should be inserted as a text too becaise otherwise it is recognised as a variable

@'
## OTHER ATTEMPTS TO BUILD URL FILTER
# $url_filter = "$url'?$where=$encodedWhere"
# $url_filter = "$url?\$where=$encodedWhere"
# $url_filter = "$url`?$where=$encodedWhere"
# $url_filter = $url + "?$where=" + $encodedWhere
# $url_filter = "$url`?$where=classe%3D%22Mam%C3%ADfer%22"

# $queryParam = "where=" + $encodedWhere
# $url_filter = "$url`?$queryParam"

# $url_filter = "$url`?$where=" + $encodedWhere
'@

Write-Output "Full Query: $url_filter"

# final output must be: "https://analisi.transparenciacatalunya.cat/resource/i8eg-aynu.json?$where=classe%3D%22Mam%C3%ADfer%22""

# set header to accept JSON
$headers = New-Object "System.Collections.Generic.Dictionary[[String],[String]]"
$headers.Add("Accept","application/json")
$headers.Add("X-App-Token", $apptoken)

$results = Invoke-RestMethod -Uri $url_filter -Method get -Headers $headers

# show results in a table
$results | ft

