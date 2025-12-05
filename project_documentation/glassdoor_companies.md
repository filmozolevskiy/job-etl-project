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

RESPONSE EXAMPLE
{
  "status": "OK",
  "request_id": "606b4278-6893-4c88-ac9f-a0ad3578c3a0",
  "parameters": {
    "query": "flighthub.com",
    "domain": "www.glassdoor.com",
    "limit": 10
  },
  "data": [
    {
      "company_id": 961018,
      "name": "FlightHub",
      "company_link": "https://www.glassdoor.com/Overview/Working-at-FlightHub-EI_IE961018.11,20.htm",
      "rating": 3,
      "review_count": 245,
      "salary_count": 204,
      "job_count": 9,
      "headquarters_location": "Montreal, Canada",
      "logo": "https://media.glassdoor.com/sql/961018/flighthub-squarelogo-1561559353561.png",
      "company_size": "51 to 200 Employees",
      "company_size_category": "SMALL_TO_MEDIUM",
      "company_description": "Based in Ontario, Canada, FlightHub is one of the Canada's fastest growing online travel companies. With a dedicated team with over 20 years experience of serving Canada's travel needs offline, we decided to take our expertise to the web and develop amazing software to improve every aspect of the travel process. We are a well skilled team software engineers and travel specialists that work tirelessly to make FlightHub one of the best sites to plan, book, and manage your travel plans.",
      "industry": "Internet & Web Services",
      "website": "https://www.flighthub.com",
      "company_type": "Company - Private",
      "revenue": "Unknown / Non-Applicable",
      "business_outlook_rating": 0.42,
      "career_opportunities_rating": 2.8,
      "ceo": null,
      "ceo_rating": 0,
      "compensation_and_benefits_rating": 3.1,
      "culture_and_values_rating": 3.2,
      "diversity_and_inclusion_rating": 3.4,
      "recommend_to_friend_rating": 0.46,
      "senior_management_rating": 2.6,
      "work_life_balance_rating": 3.4,
      "stock": null,
      "year_founded": 2012,
      "reviews_link": "https://www.glassdoor.com/Reviews/FlightHub-Reviews-E961018.htm",
      "jobs_link": "https://www.glassdoor.com/Jobs/FlightHub-Jobs-E961018.htm",
      "faq_link": "https://www.glassdoor.com/FAQ/FlightHub-Questions-E961018.htm",
      "competitors": [
        {
          "id": 9876,
          "name": "Expedia Group"
        },
        {
          "id": 318644,
          "name": "Cheapflights.com"
        }
      ],
      "office_locations": [
        {
          "city": "Montreal, QC",
          "country": "Canada"
        },
        {
          "city": "Saint-Laurent, QC",
          "country": "Canada"
        }
      ],
      "best_places_to_work_awards": []
    }
  ]
}