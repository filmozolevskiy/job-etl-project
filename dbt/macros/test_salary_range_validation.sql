{% macro test_salary_range_validation(model, min_salary_column, max_salary_column) %}
    {# 
    Test that min_salary <= max_salary when both are present.
    
    Args:
        model: The model to test
        min_salary_column: Column name for minimum salary
        max_salary_column: Column name for maximum salary
    #}
    
    select *
    from {{ model }}
    where 
        {{ min_salary_column }} is not null 
        and {{ max_salary_column }} is not null
        and {{ min_salary_column }} > {{ max_salary_column }}
    
{% endmacro %}

