{% macro test_data_freshness(model, column_name, max_age_days=90) %}
    {# 
    Test that data is not too old (data freshness check).
    
    Args:
        model: The model to test
        column_name: The timestamp column to check
        max_age_days: Maximum age in days (default: 90)
    #}
    
    select count(*) as failures
    from {{ model }}
    where {{ column_name }} < current_date - interval '{{ max_age_days }} days'
    
{% endmacro %}

