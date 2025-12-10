REQUEST EXAMPLE 
requests.get(
    "https://api.openwebninja.com/realtime-glassdoor-data/company-search",
    headers={
      "x-api-key": "YOUR_SECRET_TOKEN"
    },
    params={
      "query": "flighthub",
      "limit": "10",
      "domain": "www.glassdoor.com"
    }
)
