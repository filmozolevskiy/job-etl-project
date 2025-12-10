REQUEST EXAMPLE

requests.get(
    "https://api.openwebninja.com/jsearch/search",
    headers={
      "x-api-key": "YOUR_SECRET_TOKEN"
    },
    params={
      "query": "developer jobs in chicago",
      "page": "1",
      "num_pages": "1",
      "country": "ca",
      "language": "en",
      "date_posted": "today",
      "work_from_home": "false",
      "employment_types": "FULLTIME",
      "job_requirements": "no_experience",
      "radius": "1",
      "exclude_job_publishers": "BeeBe,Dice",
      "fields": "employer_name,job_publisher,job_title,job_country"
    }
)
