param(
    [Parameter(Mandatory=$true)]
    [string]$Client,

    [string]$Month = ""
)

if ($Month -eq "") {
    python -m social_reports.cli --client $Client
} else {
    python -m social_reports.cli --client $Client --month $Month
}

